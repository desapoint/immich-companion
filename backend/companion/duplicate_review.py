"""Duplicate review state, scoring, and workspace mixin."""

from __future__ import annotations

import logging

from companion.action_service import (
    ActionPlanConflictError,
)
from companion.duplicate_schema import (
    DuplicateAnalysisOptions,
    DuplicateReviewUpdate,
    ExactDuplicateGroup,
)
from companion.duplicate_scoring import DuplicateScoringMixin
from companion.duplicate_workspace import DuplicateWorkspaceMixin

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"

logger = logging.getLogger(__name__)

class DuplicateReviewMixin(DuplicateWorkspaceMixin, DuplicateScoringMixin):
    """Assemble scored groups and persist review/workspace state."""

    async def save_review(
        self,
        request: DuplicateReviewUpdate,
        options: DuplicateAnalysisOptions | None = None,
    ) -> ExactDuplicateGroup:
        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        resolved_options = await self._options(options)
        discovered = await self._groups_by_ids([request.group_id])
        _, _, _, result = await self._snapshot_groups(discovered, resolved_options)
        group = next(
            (candidate for candidate in result.groups if candidate.group_id == request.group_id),
            None,
        )
        if group is None:
            raise ActionPlanConflictError("The duplicate group is no longer available")
        member_ids = {member.id for member in group.members}
        action = request.manual_action
        primary_id = request.manual_primary_asset_id
        if primary_id is not None and primary_id not in member_ids:
            raise ActionPlanConflictError("The selected primary is not a group member")
        if action == "resolve" and not group.eligible:
            raise ActionPlanConflictError(
                "This duplicate group is not eligible for reviewed resolution"
            )
        if action == "stack_all" and any(
            member.is_offline or member.is_stacked for member in group.members
        ):
            raise ActionPlanConflictError(
                "Offline or already-stacked members cannot form a new stack"
            )
        review_status = (
            "pending"
            if action is None
            else "review_later"
            if action == "none"
            else "manually_configured"
        )
        await self._reviews.save(
            discovery_source=group.discovery_source,
            provider_group_id=group.provider_group_id or group.group_id,
            stable_group_key=group.stable_group_key,
            member_set_key=group.member_set_key,
            member_fingerprint=group.member_fingerprint,
            manual_action=action,
            manual_primary_asset_id=primary_id,
            review_status=review_status,
        )
        refreshed_discovered = await self._groups_by_ids([request.group_id])
        _, _, _, refreshed = await self._snapshot_groups(
            refreshed_discovered,
            resolved_options,
        )
        updated = next(
            (candidate for candidate in refreshed.groups if candidate.group_id == request.group_id),
            None,
        )
        if updated is None:
            raise ActionPlanConflictError("The duplicate group is no longer available")
        return updated
