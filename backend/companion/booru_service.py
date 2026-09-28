"""Durable, reversible Booru tagging with companion-owned policy."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select

from companion.booru_engine import BooruEngine
from companion.config import Settings
from companion.models import (
    AssetRecord,
    BooruSettingsRecord,
    BooruTaggedAssetRecord,
    BooruTagPolicyRecord,
    BooruTagRunRecord,
)
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
                )
            return BooruSettingsView(
                model_repo=row.model_repo,
                idle_seconds=row.idle_seconds,
                confidence_threshold=row.confidence_threshold,
                character_threshold=row.character_threshold,
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
                 "undone_at": row.undone_at.isoformat() if row.undone_at else None}
                for row in rows
            ]

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
            # A failed removal remains in the ledger so retrying undo is safe.
            remaining = list(record.added_tag_ids)
            for value in list(remaining):
                await self.immich.remove_assets_from_tag(UUID(value), [record.asset_id])
                remaining.remove(value)
                tags += 1
                async with self.database.sessions.begin() as session:
                    current = await session.get(BooruTaggedAssetRecord, record.asset_id)
                    if current is not None and current.run_id == run_id:
                        current.added_tag_ids = list(remaining)
            async with self.database.sessions.begin() as session:
                current = await session.get(BooruTaggedAssetRecord, record.asset_id)
                if current is not None and current.run_id == run_id:
                    await session.delete(current)
            assets += 1
        async with self.database.sessions.begin() as session:
            run = await session.get(BooruTagRunRecord, run_id)
            run.undone_at = datetime.now(UTC)
        return {"assets": assets, "tags": tags}

    async def _candidate_ids(self, limit: int) -> list[UUID]:
        async with self.database.sessions() as session:
            return list((await session.scalars(
                select(AssetRecord.id)
                .where(AssetRecord.asset_type == "IMAGE", AssetRecord.is_trashed.is_(False))
                .where(~AssetRecord.id.in_(select(BooruTaggedAssetRecord.asset_id)))
                .order_by(AssetRecord.id).limit(limit)
            )).all())

    async def tag(self, ids: list[UUID] | None, context=None) -> TaskResult:
        config = await self.settings()
        targets = ids if ids is not None else await self._candidate_ids(250)
        run_id = context.task.id if context is not None else uuid4()
        async with self.database.sessions.begin() as session:
            if await session.get(BooruTagRunRecord, run_id) is None:
                session.add(BooruTagRunRecord(id=run_id))
        completed = failed = skipped = 0
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
                completed += 1
            except Exception:
                failed += 1
                async with self.database.sessions.begin() as session:
                    record = await session.get(BooruTaggedAssetRecord, asset_id)
                    if record is not None and record.run_id == run_id and not record.added_tag_ids:
                        await session.delete(record)
            if context is not None:
                await context.checkpoint(
                    checkpoint={"cursor": str(index + 1), "run_id": str(run_id)},
                    counters={"completed": completed, "failed": failed, "skipped": skipped},
                    progress={"phase": "tagging", "completed": index + 1, "total": len(targets)},
                )
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
            # Record the intended addition before the remote call. A retryable
            # undo can then clean up even if the worker dies just after Immich writes.
            async with self.database.sessions.begin() as session:
                record = await session.get(BooruTaggedAssetRecord, asset.id)
                record.added_tag_ids = [*record.added_tag_ids, str(tag.id)]
            await self.immich.add_assets_to_tag(tag.id, [asset.id])
            added.append(tag.id)
        return added


class BooruTaskHandler:
    task_type = "booru_tagging"
    lane_key = "booru_tagging"
    max_concurrency = 1

    def __init__(self, service: BooruService) -> None:
        self.service = service

    async def execute(self, context, payload) -> TaskResult:
        return await self.service.tag(
            [UUID(value) for value in payload["asset_ids"]] if "asset_ids" in payload else None,
            context,
        )
