"""Durable, reversible Booru tagging with companion-owned policy."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from companion.booru_engine import BooruEngine, BooruModelError
from companion.config import Settings
from companion.models import (
    AssetRecord,
    BooruAssetFailureRecord,
    BooruSettingsRecord,
    BooruTaggedAssetRecord,
    BooruTagPolicyRecord,
    BooruTagRunRecord,
)
from companion.task_coordinator import PermanentTaskError
from companion.tasks.contracts import TaskResult

MODELS = (
    "SmilingWolf/wd-swinv2-tagger-v3",
    "SmilingWolf/wd-convnext-tagger-v3",
    "SmilingWolf/wd-vit-tagger-v3",
)


class BooruSettingsView(BaseModel):
    model_repo: str
    idle_seconds: int = Field(ge=0, le=86400)
    confidence_threshold: float = Field(ge=0, le=1)
    character_threshold: float = Field(ge=0, le=1)
    batch_size: int = Field(ge=1, le=1000)


class BooruService:
    def __init__(self, database, immich, settings: Settings) -> None:
        self.database = database
        self.immich = immich
        self.defaults = settings
        self.engine = BooruEngine(settings)

    async def settings(self) -> BooruSettingsView:
        async with self.database.sessions() as session:
            row = await session.get(BooruSettingsRecord, 1)
            if row is None:
                return BooruSettingsView(
                    model_repo=self.defaults.booru_model_repo,
                    idle_seconds=self.defaults.booru_model_idle_seconds,
                    confidence_threshold=self.defaults.booru_confidence_threshold,
                    character_threshold=self.defaults.booru_character_threshold,
                    batch_size=self.defaults.booru_batch_size,
                )
            return BooruSettingsView(
                model_repo=row.model_repo,
                idle_seconds=row.idle_seconds,
                confidence_threshold=row.confidence_threshold,
                character_threshold=row.character_threshold,
                batch_size=row.batch_size,
            )

    async def save_settings(self, value: BooruSettingsView) -> BooruSettingsView:
        if value.model_repo not in MODELS:
            raise ValueError("Unsupported Booru model")
        async with self.database.sessions.begin() as session:
            row = await session.get(BooruSettingsRecord, 1)
            if row is None:
                row = BooruSettingsRecord(id=1)
                session.add(row)
            row.model_repo = value.model_repo
            row.idle_seconds = value.idle_seconds
            row.confidence_threshold = value.confidence_threshold
            row.character_threshold = value.character_threshold
            row.batch_size = value.batch_size
        return value

    async def disabled_tag_ids(self) -> set[UUID]:
        async with self.database.sessions() as session:
            return set((await session.scalars(
                select(BooruTagPolicyRecord.tag_id).where(BooruTagPolicyRecord.disabled.is_(True))
            )).all())

    async def set_tag_disabled(self, tag_id: UUID, disabled: bool) -> None:
        if tag_id not in {tag.id for tag in await self.immich.list_tag_catalog()}:
            raise ValueError("Tag does not exist")
        async with self.database.sessions.begin() as session:
            row = await session.get(BooruTagPolicyRecord, tag_id)
            if row is None:
                row = BooruTagPolicyRecord(tag_id=tag_id)
                session.add(row)
            row.disabled = disabled

    async def recent_runs(self, limit: int = 20) -> list[dict]:
        async with self.database.sessions() as session:
            rows = (await session.scalars(
                select(BooruTagRunRecord).order_by(BooruTagRunRecord.created_at.desc()).limit(limit)
            )).all()
            return [
                {"id": str(row.id), "created_at": row.created_at.isoformat(),
                 "undone_at": row.undone_at.isoformat() if row.undone_at else None,
                 "failures": (await session.scalar(select(func.count()).select_from(
                     BooruAssetFailureRecord
                 ).where(BooruAssetFailureRecord.run_id == row.id))) or 0}
                for row in rows
            ]

    async def failures(self, run_id: UUID) -> list[dict]:
        async with self.database.sessions() as session:
            rows = (await session.scalars(select(BooruAssetFailureRecord).where(
                BooruAssetFailureRecord.run_id == run_id
            ).order_by(BooruAssetFailureRecord.failed_at.desc()))).all()
            return [{"asset_id": str(row.asset_id), "error": row.error,
                     "attempts": row.attempts, "next_retry_at": row.next_retry_at.isoformat()}
                    for row in rows]

    async def undo(self, run_id: UUID) -> dict[str, int]:
        async with self.database.sessions() as session:
            run = await session.get(BooruTagRunRecord, run_id)
            if run is None:
                raise ValueError("Tagging run not found")
            if run.undone_at:
                return {"assets": 0, "tags": 0}
            records = (await session.scalars(
                select(BooruTaggedAssetRecord).where(BooruTaggedAssetRecord.run_id == run_id)
            )).all()
        assets = tags = 0
        for record in records:
            tags += await self._undo_asset(record.asset_id, run_id)
            assets += 1
        async with self.database.sessions.begin() as session:
            run = await session.get(BooruTagRunRecord, run_id)
            run.undone_at = datetime.now(UTC)
        return {"assets": assets, "tags": tags}

    async def _undo_asset(self, asset_id: UUID, run_id: UUID) -> int:
        async with self.database.sessions() as session:
            record = await session.get(BooruTaggedAssetRecord, asset_id)
            if record is None or record.run_id != run_id:
                return 0
            intended = {UUID(value) for value in record.added_tag_ids}
        removed: set[UUID] = set()
        for attempt in range(4):
            current = await self.immich.get_asset(asset_id)
            present = {UUID(str(tag["id"])) for tag in current.tags if "id" in tag}
            remaining = intended & present
            if not remaining:
                async with self.database.sessions.begin() as session:
                    record = await session.get(BooruTaggedAssetRecord, asset_id)
                    if record is not None and record.run_id == run_id:
                        await session.delete(record)
                return len(removed)
            for tag_id in remaining:
                await self.immich.remove_assets_from_tag(tag_id, [asset_id])
                removed.add(tag_id)
            await asyncio.sleep(0.2 * (attempt + 1))
        raise RuntimeError(f"Immich still reports Booru tags on asset {asset_id}; retry undo")

    async def _candidate_ids(self, limit: int) -> list[UUID]:
        async with self.database.sessions() as session:
            return list((await session.scalars(
                select(AssetRecord.id)
                .outerjoin(BooruAssetFailureRecord,
                           BooruAssetFailureRecord.asset_id == AssetRecord.id)
                .where(AssetRecord.asset_type == "IMAGE", AssetRecord.is_trashed.is_(False))
                .where(~AssetRecord.id.in_(select(BooruTaggedAssetRecord.asset_id)))
                .where(or_(BooruAssetFailureRecord.asset_id.is_(None),
                           BooruAssetFailureRecord.next_retry_at <= datetime.now(UTC)))
                .order_by(func.coalesce(BooruAssetFailureRecord.attempts, 0), AssetRecord.id)
                .limit(limit)
            )).all())

    async def _record_failure(self, asset_id: UUID, run_id: UUID, error: Exception) -> None:
        now = datetime.now(UTC)
        message = f"{type(error).__name__}: {error}"[:512]
        async with self.database.sessions.begin() as session:
            row = await session.get(BooruAssetFailureRecord, asset_id)
            if row is None:
                row = BooruAssetFailureRecord(asset_id=asset_id, attempts=0)
                session.add(row)
            row.attempts += 1
            row.run_id = run_id
            row.error = message
            row.failed_at = now
            row.next_retry_at = now + timedelta(hours=min(2 ** min(row.attempts - 1, 10), 24 * 30))

    async def tag(self, ids: list[UUID] | None, context=None) -> TaskResult:
        config = await self.settings()
        targets = ids if ids is not None else await self._candidate_ids(config.batch_size)
        run_id = context.task.id if context is not None else uuid4()
        async with self.database.sessions.begin() as session:
            if await session.get(BooruTagRunRecord, run_id) is None:
                session.add(BooruTagRunRecord(id=run_id))
        completed = failed = skipped = 0
        model_error = False
        for index, asset_id in enumerate(targets):
            if context is not None:
                await context.ensure_active()
            try:
                async with self.database.sessions() as session:
                    prior = await session.get(BooruTaggedAssetRecord, asset_id)
                if prior is not None:
                    skipped += 1
                    continue
                asset = await self.immich.get_asset(asset_id)
                if asset.asset_type != "IMAGE" or asset.is_trashed:
                    skipped += 1
                    continue
                media = await self.immich.get_thumbnail(asset_id, size="thumbnail")
                predictions = await self.engine.predict(
                    media.content, config.model_repo, config.confidence_threshold,
                    config.character_threshold, config.idle_seconds,
                )
                async with self.database.sessions.begin() as session:
                    session.add(BooruTaggedAssetRecord(
                        asset_id=asset_id, run_id=run_id, added_tag_ids=[],
                    ))
                await self._apply(asset, predictions)
                async with self.database.sessions.begin() as session:
                    failure = await session.get(BooruAssetFailureRecord, asset_id)
                    if failure is not None:
                        await session.delete(failure)
                completed += 1
            except Exception as error:
                failed += 1
                model_error = isinstance(error, BooruModelError)
                try:
                    await self._undo_asset(asset_id, run_id)
                except Exception as rollback_error:
                    error = RuntimeError(f"{error}; cleanup: {rollback_error}")
                await self._record_failure(asset_id, run_id, error)
            if context is not None:
                await context.checkpoint(
                    checkpoint={"cursor": str(index + 1), "run_id": str(run_id)},
                    counters={"completed": completed, "failed": failed, "skipped": skipped},
                    progress={"phase": "tagging", "completed": index + 1, "total": len(targets)},
                )
            if model_error:
                break
        if model_error:
            raise PermanentTaskError(
                "Booru model unavailable; check the failed image and model download"
            )
        if failed and not completed and not skipped:
            raise PermanentTaskError(f"Booru tagging failed for all {failed} attempted images")
        return TaskResult(summary={"run_id": str(run_id)}, counters={
            "completed": completed, "failed": failed, "skipped": skipped,
        })

    async def _apply(self, asset, predictions: list[str]) -> list[UUID]:
        catalog = await self.immich.list_tag_catalog()
        disabled = await self.disabled_tag_ids()
        by_name = {tag.name.casefold(): tag for tag in catalog if tag.parent_id is None}
        existing = {UUID(str(tag["id"])) for tag in asset.tags if "id" in tag}
        added: list[UUID] = []
        rating_parent = by_name.get("content-rating")
        for name in [*predictions, "auto:processed"]:
            rating = name.casefold() in {"general", "sensitive", "questionable", "explicit"}
            if rating:
                if rating_parent is None:
                    rating_parent = await self.immich.create_tag("content-rating")
                tag = next((item for item in catalog if item.parent_id == rating_parent.id
                            and item.name.casefold() == name.casefold()), None)
                if tag is None:
                    tag = await self.immich.create_tag(name, parent_id=rating_parent.id)
                    catalog.append(tag)
            else:
                tag = by_name.get(name.casefold())
                if tag is None:
                    tag = await self.immich.create_tag(name)
                    by_name[name.casefold()] = tag
            if tag.id in disabled or tag.id in existing or tag.id in added:
                continue
            added.append(tag.id)
        # Record intent before the remote write so an interrupted run is undoable.
        async with self.database.sessions.begin() as session:
            record = await session.get(BooruTaggedAssetRecord, asset.id)
            record.added_tag_ids = [str(tag_id) for tag_id in added]
        await self.immich.add_tags_to_asset(asset.id, added)
        if added:
            await asyncio.sleep(0.2)
            current = await self.immich.get_asset(asset.id)
            present = {UUID(str(tag["id"])) for tag in current.tags if "id" in tag}
            if not set(added).issubset(present):
                raise RuntimeError("Immich did not retain every Booru tag on this asset")
        return added


class BooruTaskHandler:
    task_type = "booru_tagging"
    lane_key = "booru_tagging"
    max_concurrency = 1

    def __init__(self, service: BooruService) -> None:
        self.service = service

    async def execute(self, context, payload) -> TaskResult:
        if payload.get("mode") == "download":
            repo = payload.get("model_repo") or (await self.service.settings()).model_repo
            if repo not in MODELS:
                raise PermanentTaskError("Unsupported Booru model")
            await context.checkpoint(
                checkpoint={"model": repo}, counters={},
                progress={"phase": "downloading", "model": repo,
                          "detail": "Preparing model download…"},
            )

            async def report(filename: str, completed: int, total: int | None) -> None:
                model_file = filename == "model.onnx"
                percent = min(100.0, completed / total * 100) if model_file and total else None
                detail = (
                    f"Downloading model: {completed / 1048576:.1f} of {total / 1048576:.1f} MiB"
                    if model_file and total else "Preparing model files…"
                )
                await context.checkpoint(
                    checkpoint={"model": repo, "file": filename, "bytes": completed},
                    counters={"downloaded_bytes": completed},
                    progress={"phase": "downloading", "model": repo, "file": filename,
                              "completed": completed if model_file else 0,
                              "total": total if model_file else None,
                              "percent": percent, "detail": detail},
                )

            await self.service.engine.download(repo, report)
            return TaskResult(summary={"model": repo, "cached": True})
        return await self.service.tag(
            [UUID(value) for value in payload["asset_ids"]] if "asset_ids" in payload else None,
            context,
        )
