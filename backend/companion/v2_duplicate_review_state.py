"""Bounded V2 duplicate policy-state projection for SQL-native list filters."""

from __future__ import annotations

import logging

from companion.composite_duplicate_repository import CompositeDuplicateRepository
from companion.discovery.persisted_composite import PersistedCompositeDuplicateProvider
from companion.duplicate_review_repository import DuplicateReviewRepository
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

    if not group.eligible or group.status == "ineligible":
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
        reviews: DuplicateReviewRepository,
    ) -> None:
        self._discovery = discovery
        self._reports = reports
        self._snapshots = snapshots
        self._reviews = reviews

    async def refresh_after_change(self) -> object | None:
        try:
            return await self.refresh()
        except Exception:
            logger.exception("Could not refresh V2 duplicate policy-state projection")
            return None

    async def refresh(self) -> dict[str, int]:
        initial = await self._discovery.discover_page(
            page=1,
            page_size=V2_DUPLICATE_REVIEW_STATE_BATCH_SIZE,
            source="both",
            sort="discovered",
            direction="asc",
            state="all",
        )
        updated = 0
        inherited = 0
        # Work backwards so inserting inherited completed rows cannot shift an
        # unvisited SQL offset page forward and cause groups to be skipped.
        for page in range(initial.pages, 0, -1):
            discovered = (
                initial
                if initial.pages == 1 and page == 1
                else await self._discovery.discover_page(
                    page=page,
                    page_size=V2_DUPLICATE_REVIEW_STATE_BATCH_SIZE,
                    source="both",
                    sort="discovered",
                    direction="asc",
                    state="all",
                )
            )
            if not discovered.groups:
                continue
            inherited += await self._reviews.inherit_completed_groups(discovered.groups)
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
        logger.info(
            "Refreshed V2 duplicate policy states: groups=%s inherited_resolutions=%s",
            updated,
            inherited,
        )
        return {"groups": updated, "inherited_resolutions": inherited}
