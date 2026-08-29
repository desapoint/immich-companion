"""Immich-driven exact duplicate review and bounded batch resolution."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

from companion.action_repository import ActionRepository
from companion.action_service import (
    ActionPlanConflictError,
    ActionPlanNotFoundError,
    DestructiveActionsDisabledError,
)
from companion.asset_repository import AssetRepository
from companion.config import Settings
from companion.duplicate_schema import (
    CrossSourceDuplicateResult,
    CrossSourceDuplicateTaskStart,
    DuplicateAnalysisOptions,
    DuplicateMember,
    DuplicateResolutionExecuteRequest,
    DuplicateResolutionPlan,
    DuplicateResolutionPlanGroup,
    DuplicateResolutionPlanRequest,
    ExactDuplicateGroup,
)
from companion.immich import (
    ImmichApiClient,
    ImmichApiError,
    ImmichAsset,
    ImmichDuplicateGroup,
    ImmichDuplicateResolution,
)
from companion.integrity import decode_immich_sha1
from companion.integrity_repository import (
    IntegrityRepository,
    report_freshness,
)
from companion.integrity_service import INTEGRITY_TASK_TYPE, IntegrityTaskHandler
from companion.models import ActionPlanRecord, AssetIntegrityReportRecord
from companion.task_coordinator import (
    PermanentTaskError,
    RetryableTaskError,
    TaskContext,
    TaskCoordinator,
)
from companion.task_schema import TaskResult

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"


def _options_key(options: DuplicateAnalysisOptions) -> str:
    raw = json.dumps(options.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _plan_digest(groups: list[dict[str, Any]]) -> str:
    raw = json.dumps(groups, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode()).hexdigest()


def _preferred_keeper(assets: list[ImmichAsset], policy: str) -> ImmichAsset:
    if policy == "prefer_upload":
        preferred = [asset for asset in assets if asset.library_id is None]
    elif policy == "prefer_external":
        preferred = [asset for asset in assets if asset.library_id is not None]
    else:
        preferred = []
    return (preferred or assets)[0]


def _public_plan(record: ActionPlanRecord) -> DuplicateResolutionPlan:
    groups = [
        DuplicateResolutionPlanGroup.model_validate(item)
        for item in record.relation_work.get("groups", [])
    ]
    return DuplicateResolutionPlan(
        id=record.id,
        status=record.status,
        groups=groups,
        group_count=len(groups),
        trash_asset_count=sum(len(group.trash_asset_ids) for group in groups),
        expires_at=record.expires_at,
    )


class CrossSourceDuplicateService:
    """Read live groups, join cached verification, and manage reviewed plans."""

    def __init__(
        self,
        settings: Settings,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
        actions: ActionRepository,
        tasks: TaskCoordinator,
        runtime_sync_settings: object,
    ) -> None:
        self._settings = settings
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._actions = actions
        self._tasks = tasks
        self._runtime_sync_settings = runtime_sync_settings

    async def start(
        self,
        options: DuplicateAnalysisOptions,
    ) -> CrossSourceDuplicateTaskStart:
        key = _options_key(options)
        active = await self._tasks.find_active(CROSS_SOURCE_DUPLICATE_TASK_TYPE, key)
        if active is None:
            active = await self._tasks.submit(
                CROSS_SOURCE_DUPLICATE_TASK_TYPE,
                options.model_dump(mode="json"),
                priority=50,
                lane_key=INTEGRITY_TASK_TYPE,
                deduplication_key=key,
            )
            await self._tasks.start()
        return CrossSourceDuplicateTaskStart(task_id=active.id)

    async def _live_groups(self) -> list[ImmichDuplicateGroup]:
        groups = await self._immich.list_duplicate_groups()
        hydrated: list[ImmichDuplicateGroup] = []
        for group in groups:
            assets: list[ImmichAsset] = []
            for asset in group.assets:
                if asset.library_id is not None and asset.file_size_bytes is None:
                    asset = await self._immich.get_asset(asset.id)
                assets.append(asset)
            hydrated.append(group.model_copy(update={"assets": assets}))
        return hydrated

    async def result(
        self,
        options: DuplicateAnalysisOptions | None = None,
    ) -> CrossSourceDuplicateResult:
        options = options or DuplicateAnalysisOptions()
        groups = await self._live_groups()
        report_ids = [
            asset.id
            for group in groups
            for asset in group.assets
            if asset.library_id is not None or options.verify_upload_streams
        ]
        reports = await self._reports.get_many(report_ids)
        return self.assemble(groups, reports, options, self._immich)

    @staticmethod
    def assemble(
        groups: list[ImmichDuplicateGroup],
        reports: dict[UUID, AssetIntegrityReportRecord],
        options: DuplicateAnalysisOptions,
        immich: ImmichApiClient | None = None,
    ) -> CrossSourceDuplicateResult:
        allowed = set(options.external_library_ids)
        public_groups: list[ExactDuplicateGroup] = []
        for group in groups:
            assets = group.assets
            reason: str | None = None
            status = "unverified"
            hashes: dict[UUID, str | None] = {}
            invalid_upload_checksum = False

            if len(assets) < 2:
                reason = "Immich returned fewer than two members."
                status = "ineligible"
            elif any(asset.is_trashed for asset in assets):
                reason = "The group contains a trashed asset."
                status = "ineligible"
            elif any(
                asset.library_id is not None
                and allowed
                and asset.library_id not in allowed
                for asset in assets
            ):
                reason = "The group contains an external library excluded by this review."
                status = "ineligible"

            for asset in assets:
                if asset.library_id is None:
                    if options.verify_upload_streams:
                        report = reports.get(asset.id)
                        current = (
                            report is not None
                            and report_freshness(report, asset) == "current"
                        )
                        invalid_upload_checksum = invalid_upload_checksum or bool(
                            current and report.immich_checksum_match is False
                        )
                        hashes[asset.id] = (
                            report.sha1_hex
                            if current and report.immich_checksum_match is True
                            else None
                        )
                    else:
                        digest = decode_immich_sha1(asset.checksum)
                        hashes[asset.id] = digest.hex() if digest is not None else None
                else:
                    report = reports.get(asset.id)
                    hashes[asset.id] = (
                        report.sha1_hex
                        if not asset.is_offline
                        and report is not None
                        and report_freshness(report, asset) == "current"
                        else None
                    )

            known = {value for value in hashes.values() if value is not None}
            if status != "ineligible":
                if any(asset.is_offline for asset in assets):
                    reason = "An original is offline or unavailable."
                elif invalid_upload_checksum:
                    reason = "An upload stream does not match its Immich content checksum."
                elif any(value is None for value in hashes.values()):
                    reason = "Content verification is still required."
                elif len(known) == 1:
                    status = "exact"
                    reason = "Every original has the same content SHA-1."
                else:
                    status = "mismatch"
                    reason = "Immich grouped these assets, but their file contents differ."

            keeper = _preferred_keeper(assets, options.keeper_policy) if assets else None
            reference_hash = hashes.get(keeper.id) if keeper is not None else None
            members = [
                DuplicateMember(
                    id=asset.id,
                    source_kind="upload" if asset.library_id is None else "external",
                    library_id=asset.library_id,
                    original_file_name=asset.original_file_name,
                    original_mime_type=asset.original_mime_type,
                    file_size_bytes=asset.file_size_bytes,
                    file_modified_at=asset.file_modified_at,
                    is_offline=asset.is_offline,
                    immich_url=immich.public_asset_url(asset.id) if immich is not None else None,
                    verification=(
                        "unverified"
                        if hashes.get(asset.id) is None
                        else "matching"
                        if reference_hash is not None and hashes[asset.id] == reference_hash
                        else "mismatch"
                    ),
                    content_checksum=hashes.get(asset.id),
                )
                for asset in assets
            ]
            public_groups.append(
                ExactDuplicateGroup(
                    duplicate_id=group.duplicate_id,
                    status=status,
                    reason=reason,
                    keeper_asset_id=keeper.id if keeper is not None else None,
                    members=members,
                    eligible=status == "exact",
                )
            )

        counts = {name: sum(group.status == name for group in public_groups) for name in (
            "exact", "unverified", "mismatch", "ineligible"
        )}
        return CrossSourceDuplicateResult(
            generated_at=datetime.now(UTC),
            group_count=len(public_groups),
            exact_group_count=counts["exact"],
            unverified_group_count=counts["unverified"],
            mismatch_group_count=counts["mismatch"],
            ineligible_group_count=counts["ineligible"],
            groups=public_groups,
        )

    async def plan(self, request: DuplicateResolutionPlanRequest) -> DuplicateResolutionPlan:
        result = await self.result(request.options)
        selected = (
            [group for group in result.groups if group.eligible]
            if request.all_eligible
            else [group for group in result.groups if group.duplicate_id in request.duplicate_ids]
        )
        if not selected:
            raise ValueError("No eligible exact duplicate groups were selected")
        if not request.all_eligible and {
            group.duplicate_id for group in selected
        } != set(request.duplicate_ids):
            raise ActionPlanConflictError("A selected duplicate group is no longer available")
        if any(not group.eligible for group in selected):
            raise ActionPlanConflictError("Only verified exact groups can be planned")

        plan_groups: list[dict[str, Any]] = []
        for group in selected:
            member_ids = {member.id for member in group.members}
            keeper_id = request.keeper_overrides.get(
                group.duplicate_id,
                group.keeper_asset_id,
            )
            if keeper_id is None or keeper_id not in member_ids:
                raise ActionPlanConflictError("A keeper is no longer a member of its group")
            plan_groups.append(
                {
                    "duplicate_id": str(group.duplicate_id),
                    "keeper_asset_id": str(keeper_id),
                    "trash_asset_ids": [
                        str(member.id) for member in group.members if member.id != keeper_id
                    ],
                }
            )
        plan_groups.sort(key=lambda item: item["duplicate_id"])
        record = await self._actions.create_duplicate_plan(
            groups=plan_groups,
            options=request.options.model_dump(mode="json"),
            target_digest=_plan_digest(plan_groups),
            expires_at=datetime.now(UTC) + timedelta(
                seconds=self._settings.action_plan_ttl_seconds
            ),
        )
        return _public_plan(record)

    async def start_resolution(
        self,
        request: DuplicateResolutionExecuteRequest,
    ) -> CrossSourceDuplicateTaskStart:
        record = await self._actions.get_plan(request.plan_id)
        if record is None or record.action != "resolve_duplicates":
            raise ActionPlanNotFoundError("Duplicate resolution plan was not found")
        if record.status != "planned":
            raise ActionPlanConflictError("Duplicate resolution plan has already been used")
        if record.expires_at <= datetime.now(UTC):
            await self._actions.finish_plan(record.id, "expired", {"error": "expired"})
            raise ActionPlanConflictError("Duplicate resolution plan has expired")
        if not self._settings.allow_destructive_actions:
            raise DestructiveActionsDisabledError("Duplicate resolution is disabled in safe mode")
        task = await self._tasks.submit(
            DUPLICATE_RESOLUTION_TASK_TYPE,
            {"plan_id": str(record.id)},
            priority=90,
            lane_key="asset_action",
            deduplication_key=f"duplicate-plan:{record.id}",
        )
        await self._tasks.start()
        return CrossSourceDuplicateTaskStart(task_id=task.id)

    async def execute_plan(self, context: TaskContext, plan_id: UUID) -> TaskResult:
        existing = await self._actions.get_plan(plan_id)
        if existing is None or existing.action != "resolve_duplicates":
            raise PermanentTaskError("Duplicate resolution plan was not found")
        if existing.status not in {"planned", "running"}:
            raise PermanentTaskError("Duplicate resolution plan has already been used")
        if not self._settings.allow_destructive_actions:
            raise PermanentTaskError("Duplicate resolution is disabled in safe mode")

        raw_groups = list(existing.relation_work.get("groups", []))
        options = DuplicateAnalysisOptions.model_validate(
            existing.relation_work.get("options", {})
        )
        reviewed = {
            group.duplicate_id: group for group in (await self.result(options)).groups
        }
        for planned in raw_groups:
            duplicate_id = UUID(planned["duplicate_id"])
            live_group = reviewed.get(duplicate_id)
            planned_members = {
                UUID(planned["keeper_asset_id"]),
                *(UUID(value) for value in planned["trash_asset_ids"]),
            }
            if (
                live_group is None
                or not live_group.eligible
                or {asset.id for asset in live_group.members} != planned_members
            ):
                await self._actions.finish_plan(plan_id, "drifted", {"error": "group_drift"})
                raise PermanentTaskError("A duplicate group changed after review")

        if existing.status == "planned":
            claimed = await self._actions.claim_plan(plan_id)
            if claimed is None:
                raise PermanentTaskError("Duplicate resolution plan has already been used")

        pacing = await self._runtime_sync_settings.get()
        batch_size = pacing.full_batch_size
        completed = 0
        failed_ids: list[str] = []
        trashed_ids: list[UUID] = []
        try:
            for offset in range(0, len(raw_groups), batch_size):
                await context.ensure_active()
                batch = raw_groups[offset : offset + batch_size]
                resolutions = [
                    ImmichDuplicateResolution(
                        duplicate_id=UUID(item["duplicate_id"]),
                        keep_asset_id=UUID(item["keeper_asset_id"]),
                        trash_asset_ids=[UUID(value) for value in item["trash_asset_ids"]],
                    )
                    for item in batch
                ]
                responses = await self._immich.resolve_duplicate_groups(resolutions)
                for index, resolution in enumerate(resolutions):
                    response = responses[index] if index < len(responses) else {}
                    if response.get("success") is True:
                        completed += 1
                        trashed_ids.extend(resolution.trash_asset_ids)
                    else:
                        failed_ids.append(str(resolution.duplicate_id))
                await context.checkpoint(
                    checkpoint={"phase": "resolving", "groups_completed": completed},
                    counters={"groups_completed": completed, "groups_failed": len(failed_ids)},
                    progress={
                        "phase": "duplicate_resolution",
                        "completed": min(offset + len(batch), len(raw_groups)),
                        "total": len(raw_groups),
                        "percent": round(
                            min(offset + len(batch), len(raw_groups))
                            / len(raw_groups)
                            * 100,
                            1,
                        ),
                        "detail": "Resolving reviewed duplicate groups through Immich…",
                    },
                )
                if offset + len(batch) < len(raw_groups):
                    await asyncio.sleep(pacing.full_min_batch_delay_seconds)
        except ImmichApiError as error:
            await self._assets.remove_assets(trashed_ids)
            await self._actions.finish_plan(
                plan_id,
                "failed",
                {
                    "error": str(error),
                    "resolved_group_count": completed,
                    "trashed_asset_count": len(trashed_ids),
                },
            )
            raise PermanentTaskError("Immich duplicate resolution failed") from error

        await self._assets.remove_assets(trashed_ids)
        remaining = {group.duplicate_id for group in await self._immich.list_duplicate_groups()}
        unresolved = [
            item["duplicate_id"]
            for item in raw_groups
            if UUID(item["duplicate_id"]) in remaining
        ]
        failed_ids.extend(identifier for identifier in unresolved if identifier not in failed_ids)
        status = "completed" if not failed_ids else "failed"
        result = {
            "group_count": len(raw_groups),
            "resolved_group_count": len(raw_groups) - len(failed_ids),
            "failed_group_ids": failed_ids,
            "trashed_asset_count": len(trashed_ids),
            "verified": not failed_ids,
        }
        await self._actions.finish_plan(plan_id, status, result)
        return TaskResult(
            status=status,
            summary=result,
            counters={
                "groups_resolved": len(raw_groups) - len(failed_ids),
                "groups_failed": len(failed_ids),
                "assets_trashed": len(trashed_ids),
            },
        )


class CrossSourceDuplicateTaskHandler:
    """Hash only stale external members of Immich's duplicate groups."""

    task_type = CROSS_SOURCE_DUPLICATE_TASK_TYPE
    lane_key = INTEGRITY_TASK_TYPE
    max_concurrency = 1

    def __init__(
        self,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
        integrity: IntegrityTaskHandler,
    ) -> None:
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._integrity = integrity

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        options = DuplicateAnalysisOptions.model_validate(payload)
        groups = await self._immich.list_duplicate_groups()
        candidates: dict[UUID, ImmichAsset] = {}
        for group in groups:
            for asset in group.assets:
                if asset.library_id is not None or options.verify_upload_streams:
                    if asset.file_size_bytes is None:
                        asset = await self._immich.get_asset(asset.id)
                    candidates[asset.id] = asset

        reports = await self._reports.get_many(list(candidates))
        pending = [
            asset
            for asset in candidates.values()
            if not asset.is_offline
            and (
                asset.library_id is None
                and options.verify_upload_streams
                or asset.library_id is not None
            )
            and report_freshness(reports.get(asset.id), asset) != "current"
        ]
        unavailable = 0
        for index, asset in enumerate(pending, start=1):
            await context.ensure_active()
            await self._assets.refresh_asset(asset)
            try:
                await self._integrity.analyze(context, asset.id)
            except (PermanentTaskError, RetryableTaskError, ImmichApiError):
                unavailable += 1
            await context.checkpoint(
                checkpoint={"phase": "fingerprinting", "asset_id": str(asset.id)},
                counters={"files_attempted": index, "files_unavailable": unavailable},
                progress={
                    "phase": "duplicate_fingerprints",
                    "completed": index,
                    "total": len(pending),
                    "percent": round(index / len(pending) * 100, 1),
                    "detail": "Verifying duplicate candidate contents…",
                },
            )
        await context.checkpoint(
            checkpoint={"phase": "complete"},
            counters={"files_attempted": len(pending), "files_unavailable": unavailable},
            progress={
                "phase": "complete",
                "completed": 1,
                "total": 1,
                "percent": 100.0,
                "detail": "Duplicate candidate verification is ready.",
            },
        )
        return TaskResult(
            summary={"duplicate_group_count": len(groups)},
            counters={
                "duplicate_groups": len(groups),
                "candidate_files": len(candidates),
                "files_attempted": len(pending),
                "files_unavailable": unavailable,
            },
        )


class DuplicateResolutionTaskHandler:
    """Execute one reviewed duplicate plan in the serialized action lane."""

    task_type = DUPLICATE_RESOLUTION_TASK_TYPE
    lane_key = "asset_action"
    max_concurrency = 1

    def __init__(self, service: CrossSourceDuplicateService) -> None:
        self._service = service

    async def execute(self, context: TaskContext, payload: dict[str, Any]) -> TaskResult:
        return await self._service.execute_plan(context, UUID(str(payload["plan_id"])))
