"""Durable, reversible Booru tagging with companion-owned policy."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select

from companion.booru_engine import BooruEngine, BooruModelError
from companion.config import Settings
from companion.models import (
    AlbumAssetRecord,
    AlbumRecord,
    AssetRecord,
    BooruAssetFailureRecord,
    BooruSettingsRecord,
    BooruTaggedAssetRecord,
    BooruTagPolicyRecord,
    BooruTagRunRecord,
    TagAssetRecord,
    TagRecord,
)
from companion.task_coordinator import PermanentTaskError
from companion.tasks.contracts import TaskResult

MODELS = (
    "SmilingWolf/wd-swinv2-tagger-v3",
    "SmilingWolf/wd-convnext-tagger-v3",
    "SmilingWolf/wd-vit-tagger-v3",
)
logger = logging.getLogger(__name__)


class BooruSettingsView(BaseModel):
    model_repo: str
    idle_seconds: int = Field(ge=0, le=86400)
    confidence_threshold: float = Field(ge=0, le=1)
    character_threshold: float = Field(ge=0, le=1)
    batch_size: int = Field(ge=1, le=1000)
    processed_tag_name: str = Field(default="auto:processed", max_length=255)
    content_rating_tag_name: str = Field(default="content-rating", max_length=255)
    target_albums: str = Field(default="", max_length=2048)
    max_batches_per_run: int = Field(default=4, ge=1, le=100)
    unload_model_after_run: bool = True
    failure_timeout: int = Field(default=3, ge=0, le=100)
    tag_cache_ttl: int = Field(default=300, ge=1, le=86400)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("content_rating_tag_name")
    @classmethod
    def valid_rating_parent(cls, value: str) -> str:
        value = value.strip()
        if not value or "/" in value or any(char in value for char in "\r\n\t"):
            raise ValueError("Content rating parent must be a single tag name")
        return value


class BooruService:
    def __init__(self, database, immich, settings: Settings, assets=None) -> None:
        self.database = database
        self.immich = immich
        self.defaults = settings
        self.assets = assets
        self.engine = BooruEngine(settings)
        self._tag_catalog = None
        self._tag_catalog_expires = 0.0

    async def settings(self) -> BooruSettingsView:
        async with self.database.sessions() as session:
            row = await session.get(BooruSettingsRecord, 1)
            if row is None:
                view = BooruSettingsView(
                    model_repo=self.defaults.booru_model_repo,
                    idle_seconds=self.defaults.booru_model_idle_seconds,
                    confidence_threshold=self.defaults.booru_confidence_threshold,
                    character_threshold=self.defaults.booru_character_threshold,
                    batch_size=self.defaults.booru_batch_size,
                    processed_tag_name="auto:processed",
                    content_rating_tag_name="content-rating",
                    target_albums="",
                    max_batches_per_run=4,
                    unload_model_after_run=True,
                    failure_timeout=3,
                    tag_cache_ttl=300,
                    log_level="INFO",
                )
            else:
                view = BooruSettingsView(
                    model_repo=row.model_repo,
                    idle_seconds=row.idle_seconds,
                    confidence_threshold=row.confidence_threshold,
                    character_threshold=row.character_threshold,
                    batch_size=row.batch_size,
                    processed_tag_name=row.processed_tag_name,
                    content_rating_tag_name=row.content_rating_tag_name,
                    target_albums=row.target_albums,
                    max_batches_per_run=row.max_batches_per_run,
                    unload_model_after_run=row.unload_model_after_run,
                    failure_timeout=row.failure_timeout,
                    tag_cache_ttl=row.tag_cache_ttl,
                    log_level=row.log_level,
                )
        for name in (__name__, "companion.booru_engine"):
            logging.getLogger(name).setLevel(view.log_level)
        return view

    async def save_settings(self, value: BooruSettingsView) -> BooruSettingsView:
        if value.model_repo not in MODELS:
            raise ValueError("Unsupported Booru model")
        value = value.model_copy(update={
            "processed_tag_name": value.processed_tag_name.strip(),
            "target_albums": ",".join(
                name.strip() for name in value.target_albums.split(",") if name.strip()
            ),
        })
        self._tag_catalog = None
        for name in (__name__, "companion.booru_engine"):
            logging.getLogger(name).setLevel(value.log_level)
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
            row.processed_tag_name = value.processed_tag_name
            row.content_rating_tag_name = value.content_rating_tag_name
            row.target_albums = value.target_albums
            row.max_batches_per_run = value.max_batches_per_run
            row.unload_model_after_run = value.unload_model_after_run
            row.failure_timeout = value.failure_timeout
            row.tag_cache_ttl = value.tag_cache_ttl
            row.log_level = value.log_level
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

    async def _remove_tag_ids_verified(
        self,
        asset_id: UUID,
        intended: set[UUID],
        *,
        label: str,
    ) -> tuple[set[UUID], object]:
        """Remove tag memberships and wait until Immich reports the final state."""

        removed: set[UUID] = set()
        current = await self.immich.get_asset(asset_id)
        for attempt in range(4):
            present = {
                UUID(str(tag["id"]))
                for tag in current.tags
                if isinstance(tag, dict) and tag.get("id")
            }
            remaining = intended & present
            if not remaining:
                return removed, current
            for tag_id in remaining:
                await self.immich.remove_assets_from_tag(tag_id, [asset_id])
                removed.add(tag_id)
            await asyncio.sleep(0.2 * (attempt + 1))
            current = await self.immich.get_asset(asset_id)
        raise RuntimeError(
            f"Immich still reports {len(intended & present)} {label} tag(s) "
            f"on asset {asset_id}"
        )

    async def _undo_asset(self, asset_id: UUID, run_id: UUID) -> int:
        async with self.database.sessions() as session:
            record = await session.get(BooruTaggedAssetRecord, asset_id)
            if record is None or record.run_id != run_id:
                return 0
            intended = {UUID(value) for value in record.added_tag_ids}
        removed, current = await self._remove_tag_ids_verified(
            asset_id, intended, label="Booru"
        )
        await self._refresh_cached_asset_tags(current)
        async with self.database.sessions.begin() as session:
            record = await session.get(BooruTaggedAssetRecord, asset_id)
            if record is not None and record.run_id == run_id:
                await session.delete(record)
        return len(removed)

    async def _candidate_ids(self, limit: int, config: BooruSettingsView) -> list[UUID]:
        album_names = [name.casefold() for name in config.target_albums.split(",") if name]
        async with self.database.sessions() as session:
            query = (
                select(AssetRecord.id)
                .outerjoin(
                    BooruAssetFailureRecord,
                    BooruAssetFailureRecord.asset_id == AssetRecord.id,
                )
                .where(AssetRecord.asset_type == "IMAGE", AssetRecord.is_trashed.is_(False))
                .where(
                    or_(
                        BooruAssetFailureRecord.asset_id.is_(None),
                        (BooruAssetFailureRecord.attempts < config.failure_timeout)
                        & (BooruAssetFailureRecord.next_retry_at <= datetime.now(UTC)),
                    )
                )
            )
            if config.processed_tag_name:
                processed_tags = select(TagRecord.id).where(
                    func.lower(TagRecord.tag_name) == config.processed_tag_name.casefold()
                )
                query = query.where(
                    ~AssetRecord.id.in_(
                        select(TagAssetRecord.asset_id).where(
                            TagAssetRecord.tag_id.in_(processed_tags)
                        )
                    )
                )
            else:
                query = query.where(
                    ~AssetRecord.id.in_(select(BooruTaggedAssetRecord.asset_id))
                )
            if album_names:
                album_ids = select(AlbumRecord.id).where(
                    func.lower(AlbumRecord.album_name).in_(album_names)
                )
                query = query.where(
                    AssetRecord.id.in_(
                        select(AlbumAssetRecord.asset_id).where(
                            AlbumAssetRecord.album_id.in_(album_ids)
                        )
                    )
                )
            query = query.order_by(
                func.coalesce(BooruAssetFailureRecord.attempts, 0),
                AssetRecord.id,
            ).limit(limit)
            return list((await session.scalars(query)).all())

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

    async def _remove_manual_booru_tags(
        self,
        asset,
        prior,
        config: BooruSettingsView,
    ) -> tuple[set[UUID], object]:
        """Remove only Companion-managed/model-valid tags before an explicit re-tag."""

        managed_ids = {
            UUID(value)
            for value in (prior.added_tag_ids if prior is not None else [])
        }
        known_names = self.engine.known_tag_names()
        marker = config.processed_tag_name.casefold() if config.processed_tag_name else ""
        for tag in asset.tags:
            if not isinstance(tag, dict) or not tag.get("id"):
                continue
            name = str(tag.get("name", "")).casefold()
            if name in known_names or (marker and name == marker):
                managed_ids.add(UUID(str(tag["id"])))
        if not managed_ids:
            return set(), asset

        removed, current = await self._remove_tag_ids_verified(
            asset.id, managed_ids, label="old Booru"
        )
        await self._refresh_cached_asset_tags(current)
        return removed, current

    async def _restore_manual_retag(
        self,
        asset_id: UUID,
        removed_ids: set[UUID],
        prior_run_id: UUID | None,
        prior_added_tag_ids: list[str],
    ) -> None:
        """Restore the pre-re-tag state when an explicit re-tag fails."""

        if removed_ids:
            await self.immich.add_tags_to_asset(asset_id, list(removed_ids))
            await asyncio.sleep(0.2)
            current = await self.immich.get_asset(asset_id)
            present = {
                UUID(str(tag["id"]))
                for tag in current.tags
                if isinstance(tag, dict) and tag.get("id")
            }
            if not removed_ids.issubset(present):
                raise RuntimeError("Immich did not restore the previous Booru tags")
            await self._refresh_cached_asset_tags(current)
        if prior_run_id is not None:
            async with self.database.sessions.begin() as session:
                record = await session.get(BooruTaggedAssetRecord, asset_id)
                if record is None:
                    session.add(
                        BooruTaggedAssetRecord(
                            asset_id=asset_id,
                            run_id=prior_run_id,
                            added_tag_ids=list(prior_added_tag_ids),
                        )
                    )
                else:
                    record.run_id = prior_run_id
                    record.added_tag_ids = list(prior_added_tag_ids)

    async def reset_handled(self, ids: list[UUID], context=None) -> TaskResult:
        """Clear the processed marker and local Booru state for explicit retries."""

        config = await self.settings()
        completed = failed = markers_removed = records_removed = 0
        marker = config.processed_tag_name.casefold() if config.processed_tag_name else ""
        for index, asset_id in enumerate(ids):
            if context is not None:
                await context.ensure_active()
            try:
                current = await self.immich.get_asset(asset_id)
                marker_ids = {
                    UUID(str(tag["id"]))
                    for tag in current.tags
                    if isinstance(tag, dict)
                    and tag.get("id")
                    and marker
                    and str(tag.get("name", "")).casefold() == marker
                }
                removed, current = await self._remove_tag_ids_verified(
                    asset_id, marker_ids, label="processed marker"
                )
                markers_removed += len(removed)
                await self._refresh_cached_asset_tags(current)
                async with self.database.sessions.begin() as session:
                    handled = await session.get(BooruTaggedAssetRecord, asset_id)
                    failure = await session.get(BooruAssetFailureRecord, asset_id)
                    if handled is not None:
                        await session.delete(handled)
                        records_removed += 1
                    if failure is not None:
                        await session.delete(failure)
                completed += 1
            except Exception as error:
                failed += 1
                await self._record_failure(asset_id, context.task.id if context else uuid4(), error)
            if context is not None:
                await context.checkpoint(
                    checkpoint={"cursor": str(index + 1)},
                    counters={
                        "completed": completed,
                        "failed": failed,
                        "markers_removed": markers_removed,
                        "records_removed": records_removed,
                    },
                    progress={
                        "phase": "resetting",
                        "completed": index + 1,
                        "total": len(ids),
                    },
                )
        if failed and not completed:
            raise PermanentTaskError(
                f"Booru reset failed for all {failed} selected images"
            )
        return TaskResult(
            summary={"reset": True},
            counters={
                "completed": completed,
                "failed": failed,
                "markers_removed": markers_removed,
                "records_removed": records_removed,
            },
        )

    async def tag(
        self,
        ids: list[UUID] | None,
        context=None,
        *,
        manual_retag: bool = False,
    ) -> TaskResult:
        config = await self.settings()
        targets = ids if ids is not None else await self._candidate_ids(
            config.batch_size * config.max_batches_per_run, config
        )
        run_id = context.task.id if context is not None else uuid4()
        async with self.database.sessions.begin() as session:
            if await session.get(BooruTagRunRecord, run_id) is None:
                session.add(BooruTagRunRecord(id=run_id))
        completed = failed = skipped = 0
        model_error = False
        for index, asset_id in enumerate(targets):
            if context is not None:
                await context.ensure_active()
            prior_run_id: UUID | None = None
            prior_added_tag_ids: list[str] = []
            removed_for_retag: set[UUID] = set()
            try:
                async with self.database.sessions() as session:
                    prior = await session.get(BooruTaggedAssetRecord, asset_id)
                if prior is not None:
                    prior_run_id = prior.run_id
                    prior_added_tag_ids = list(prior.added_tag_ids)
                asset = await self.immich.get_asset(asset_id)
                if asset.asset_type != "IMAGE" or asset.is_trashed:
                    skipped += 1
                    continue
                marker = config.processed_tag_name.casefold() if config.processed_tag_name else ""
                marker_present = bool(marker) and any(
                    str(tag.get("name", "")).casefold() == marker
                    for tag in asset.tags
                    if isinstance(tag, dict)
                )
                if not manual_retag and (
                    marker_present or (not marker and prior is not None)
                ):
                    skipped += 1
                    continue
                media = await self.immich.get_thumbnail(asset_id, size="thumbnail")
                predictions = await self.engine.predict(
                    media.content, config.model_repo, config.confidence_threshold,
                    config.character_threshold, config.idle_seconds,
                )
                if manual_retag:
                    removed_for_retag, asset = await self._remove_manual_booru_tags(
                        asset, prior, config
                    )
                async with self.database.sessions.begin() as session:
                    record = await session.get(BooruTaggedAssetRecord, asset_id)
                    if record is None:
                        session.add(BooruTaggedAssetRecord(
                            asset_id=asset_id, run_id=run_id, added_tag_ids=[],
                        ))
                    else:
                        record.run_id = run_id
                        record.added_tag_ids = []
                await self._apply(asset, predictions, config)
                async with self.database.sessions.begin() as session:
                    failure = await session.get(BooruAssetFailureRecord, asset_id)
                    if failure is not None:
                        await session.delete(failure)
                completed += 1
            except Exception as error:
                failed += 1
                model_error = isinstance(error, BooruModelError)
                cleanup_errors: list[str] = []
                try:
                    await self._undo_asset(asset_id, run_id)
                except Exception as rollback_error:
                    cleanup_errors.append(f"cleanup: {rollback_error}")
                if manual_retag and (removed_for_retag or prior_run_id is not None):
                    try:
                        await self._restore_manual_retag(
                            asset_id,
                            removed_for_retag,
                            prior_run_id,
                            prior_added_tag_ids,
                        )
                    except Exception as restore_error:
                        cleanup_errors.append(f"restore: {restore_error}")
                if cleanup_errors:
                    error = RuntimeError(f"{error}; {'; '.join(cleanup_errors)}")
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

    async def _refresh_cached_asset_tags(self, asset, catalog=None) -> None:
        """Write an authoritative Immich tag snapshot into the companion cache."""

        if self.assets is None:
            return
        current_ids = {
            UUID(str(tag["id"]))
            for tag in asset.tags
            if isinstance(tag, dict) and tag.get("id")
        }
        resolved_catalog = list(catalog) if catalog is not None else list(self._tag_catalog or [])
        catalog_ids = {tag.id for tag in resolved_catalog}
        if not current_ids.issubset(catalog_ids):
            resolved_catalog = await self.immich.list_tag_catalog()
            self._tag_catalog = resolved_catalog
            catalog_ids = {tag.id for tag in resolved_catalog}
        if not current_ids.issubset(catalog_ids):
            raise RuntimeError("Immich tag catalog did not contain every tag on the asset")
        await self.assets.refresh_asset_tag_snapshot(asset, resolved_catalog)

    async def _apply(self, asset, predictions: list[str], config: BooruSettingsView) -> list[UUID]:
        if self._tag_catalog is None or monotonic() >= self._tag_catalog_expires:
            self._tag_catalog = await self.immich.list_tag_catalog()
            self._tag_catalog_expires = monotonic() + config.tag_cache_ttl
        catalog = self._tag_catalog
        disabled = await self.disabled_tag_ids()
        by_name = {tag.name.casefold(): tag for tag in catalog if tag.parent_id is None}
        existing = {UUID(str(tag["id"])) for tag in asset.tags if "id" in tag}
        added: list[UUID] = []
        rating_parent = by_name.get(config.content_rating_tag_name.casefold())
        names = [*predictions]
        if config.processed_tag_name:
            names.append(config.processed_tag_name)
        for name in names:
            rating = name.casefold() in {"general", "sensitive", "questionable", "explicit"}
            if rating:
                if rating_parent is None:
                    rating_parent = await self.immich.create_tag(config.content_rating_tag_name)
                    catalog.append(rating_parent)
                    by_name[config.content_rating_tag_name.casefold()] = rating_parent
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
                    catalog.append(tag)
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
        if added:
            present = {UUID(str(tag["id"])) for tag in current.tags if "id" in tag}
            if not set(added).issubset(present):
                raise RuntimeError("Immich did not retain every Booru tag on this asset")
        await self._refresh_cached_asset_tags(current, catalog)
        return added


class BooruTaskHandler:
    task_type = "booru_tagging"
    # Tagging mutates the same asset/tag cache as synchronization. Keep it in
    # the sync lane so a staged sync cannot race an out-of-band Booru write.
    lane_key = "asset_sync"
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
        if payload.get("mode") == "reset":
            ids = [UUID(value) for value in payload.get("asset_ids", [])]
            if not ids:
                raise PermanentTaskError("Select at least one image to reset")
            return await self.service.reset_handled(ids, context)
        config = await self.service.settings()
        try:
            return await self.service.tag(
                [UUID(value) for value in payload["asset_ids"]] if "asset_ids" in payload else None,
                context,
                manual_retag=bool(payload.get("manual_retag", False)),
            )
        finally:
            if config.unload_model_after_run:
                await self.service.engine.unload()
