"""Bounded V2 duplicate policy-state projection for SQL-native list filters."""

from __future__ import annotations

import logging

from companion.composite_duplicate_repository import CompositeDuplicateRepository
from companion.discovery.persisted_composite import PersistedCompositeDuplicateProvider
from companion.duplicate_schema import DuplicateAnalysisOptions, ExactDuplicateGroup
from companion.duplicate_service import CrossSourceDuplicateService
from companion.integrity_repository import IntegrityRepository

V2_DUPLICATE_REVIEW_STATE_BATCH_SIZE = 250
V2_DUPLICATE_ANALYSIS_OPTIONS = DuplicateAnalysisOptions(
    keeper_policy="prefer_upload",
    external_library_ids=[],
    verify_upload_streams=False,
    automatic_handling_enabled=True,
    preselect_safe_groups=True,
    exact_file_action="resolve",
    analyze_automatically=False,
)

logger = logging.getLogger("uvicorn.error")


def v2_policy_state(group: ExactDuplicateGroup) -> str:
    """Return policy state independent of manual draft progress."""

    if (
        not group.eligible
        or group.status == "ineligible"
        or any(member.is_offline for member in group.members)
    ):
        return "blocked"
    if group.auto_selected:
        return "auto_ready"
    return "needs_review"


class V2DuplicateReviewStateService:
    """Refresh policy summaries in bounded pages outside duplicate list requests."""

    def __init__(
        self,
        discovery: PersistedCompositeDuplicateProvider,
        reports: IntegrityRepository,
        snapshots: CompositeDuplicateRepository,
    ) -> None:
        self._discovery = discovery
        self._reports = reports
        self._snapshots = snapshots

    async def refresh_after_change(self) -> object | None:
        try:
            return await self.refresh()
        except Exception:
            logger.exception("Could not refresh V2 duplicate policy-state projection")
            return None

    async def refresh(self) -> dict[str, int]:
        page = 1
        updated = 0
        while True:
            discovered = await self._discovery.discover_page(
                page=page,
                page_size=V2_DUPLICATE_REVIEW_STATE_BATCH_SIZE,
                source="both",
                sort="discovered",
                direction="asc",
                state="all",
            )
            if not discovered.groups:
                break
            report_ids = list(
                dict.fromkeys(
                    asset.id
                    for group in discovered.groups
                    for asset in group.assets
                    if asset.library_id is not None
                )
            )
            reports = await self._reports.get_many(report_ids)
            result = CrossSourceDuplicateService.assemble(
                discovered.groups,
                reports,
                V2_DUPLICATE_ANALYSIS_OPTIONS,
            )
            states = [
                (
                    group.group_id,
                    group.member_fingerprint,
                    v2_policy_state(group),
                )
                for group in result.groups
            ]
            updated += await self._snapshots.update_v2_policy_states(states)
            if page >= discovered.pages:
                break
            page += 1
        logger.info("Refreshed V2 duplicate policy states: groups=%s", updated)
        return {"groups": updated}
