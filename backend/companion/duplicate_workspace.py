"""Duplicate workspace and keeper-selection mixin."""

from __future__ import annotations

import logging
from typing import Any

from companion.action_service import (
    ActionPlanConflictError,
)
from companion.duplicate_identity import stable_group_key
from companion.duplicate_keeper_rules import choose_keeper
from companion.duplicate_schema import (
    DuplicateAnalysisOptions,
    DuplicateGroupDraft,
    DuplicateGroupDraftUpdate,
    DuplicateKeeperSelectionRequest,
    DuplicateKeeperSelectionResult,
    DuplicateWorkspaceGroupReference,
    DuplicateWorkspaceMembership,
    DuplicateWorkspaceMembershipRequest,
    DuplicateWorkspacePresetRequest,
    DuplicateWorkspaceResetRequest,
    DuplicateWorkspaceSelectionDelta,
    DuplicateWorkspaceSelectionUpdate,
    DuplicateWorkspaceState,
)
from companion.group_decision import (
    DiscoverySource,
)

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"

logger = logging.getLogger(__name__)



class DuplicateWorkspaceMixin:
    """Persist workspace decisions, keeper selections, and review drafts."""

    async def workspace(
        self,
        options: DuplicateAnalysisOptions | None = None,
    ) -> DuplicateWorkspaceState:
        """Restore durable selections/drafts without hydrating the duplicate universe."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        workspace = await self._reviews.get_workspace()
        selected_references = list(getattr(workspace, "selected_groups", []) or [])
        active_reference = getattr(workspace, "active_group", None)
        parsed_references = [
            DuplicateWorkspaceGroupReference.model_validate(raw) for raw in selected_references
        ]
        parsed_active = (
            DuplicateWorkspaceGroupReference.model_validate(active_reference)
            if active_reference
            else None
        )

        list_drafts = getattr(self._reviews, "list_drafts", None)
        if not callable(list_drafts):
            raise RuntimeError(
                "Duplicate workspace restore requires persisted V2 draft storage"
            )
        records = await list_drafts()
        stable_keys = [
            reference.stable_group_key
            or stable_group_key(
                reference.discovery_source,
                reference.member_set_key or reference.member_fingerprint,
            )
            for reference in [
                *parsed_references,
                *([parsed_active] if parsed_active else []),
            ]
        ]
        stable_keys.extend(record.stable_group_key for record in records)
        identities = await self._group_identities(
            stable_group_keys=list(dict.fromkeys(stable_keys))
        )

        def source_value(item: Any) -> str:
            value = item.discovery_source
            return value.value if isinstance(value, DiscoverySource) else str(value)

        groups_by_stable_key = {item.stable_group_key: item for item in identities}
        selected_ids: list[str] = []
        stale_selected: list[DuplicateWorkspaceGroupReference] = []
        for reference in parsed_references:
            reference_key = reference.stable_group_key or stable_group_key(
                reference.discovery_source,
                reference.member_set_key or reference.member_fingerprint,
            )
            current = groups_by_stable_key.get(reference_key)
            if (
                current is not None
                and source_value(current) == reference.discovery_source
                and current.member_fingerprint == reference.member_fingerprint
            ):
                selected_ids.append(current.group_id)
            else:
                stale_selected.append(reference)

        active_group_id = None
        if parsed_active is not None:
            active_key = parsed_active.stable_group_key or stable_group_key(
                parsed_active.discovery_source,
                parsed_active.member_set_key or parsed_active.member_fingerprint,
            )
            current = groups_by_stable_key.get(active_key)
            if (
                current is not None
                and source_value(current) == parsed_active.discovery_source
                and current.member_fingerprint == parsed_active.member_fingerprint
            ):
                active_group_id = current.group_id

        drafts: list[DuplicateGroupDraft] = []
        for record in records:
            current = groups_by_stable_key.get(record.stable_group_key)
            if current is None:
                continue
            record_source = getattr(record, "discovery_source", None)
            if record_source is not None and source_value(current) != record_source:
                continue
            decisions = list(getattr(record, "member_decisions", []) or [])
            if not decisions and not getattr(record, "stack_primary_asset_id", None):
                continue
            drafts.append(
                DuplicateGroupDraft(
                    group_id=current.group_id,
                    discovery_source=source_value(current),
                    member_fingerprint=record.member_fingerprint,
                    decisions=decisions,
                    stack_primary_asset_id=getattr(record, "stack_primary_asset_id", None),
                    stack_resolution=getattr(record, "stack_resolution", "move_selected"),
                    metadata_keeper_asset_id=getattr(record, "metadata_keeper_asset_id", None),
                    status=getattr(record, "draft_status", "pending"),
                    stale=record.member_fingerprint != current.member_fingerprint,
                )
            )
        return DuplicateWorkspaceState(
            initialized=workspace is not None,
            revision=int(getattr(workspace, "revision", 0) or 0),
            selected_count=len(selected_ids),
            selected_group_ids=selected_ids,
            active_group_id=active_group_id,
            stale_selected_groups=stale_selected,
            drafts=drafts,
        )

    async def save_workspace_selection(
        self,
        request: DuplicateWorkspaceSelectionUpdate,
    ) -> DuplicateWorkspaceState:
        """Save persisted group identities without materializing duplicate evidence."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        requested_ids = list(
            dict.fromkeys(
                [
                    *request.selected_group_ids,
                    *([request.active_group_id] if request.active_group_id else []),
                ]
            )
        )
        identities = await self._group_identities(group_ids=requested_ids)
        groups_by_id: dict[str, Any] = {group.group_id: group for group in identities}
        missing = [group_id for group_id in requested_ids if group_id not in groups_by_id]
        if missing:
            raise ActionPlanConflictError("A selected duplicate group is no longer available")

        def reference(group_id: str) -> dict[str, str]:
            group = groups_by_id[group_id]
            source = group.discovery_source
            source_name = source.value if isinstance(source, DiscoverySource) else str(source)
            fingerprint = group.member_fingerprint
            return DuplicateWorkspaceGroupReference(
                group_id=group.group_id,
                discovery_source=source_name,
                member_fingerprint=fingerprint,
                stable_group_key=group.stable_group_key,
                member_set_key=getattr(group, "member_set_key", fingerprint),
            ).model_dump(mode="json")

        try:
            await self._reviews.save_workspace(
                selected_groups=[reference(group_id) for group_id in request.selected_group_ids],
                active_group=(
                    reference(request.active_group_id)
                    if request.active_group_id is not None
                    else None
                ),
                revision=request.revision,
            )
        except ValueError as error:
            # The repository uses ValueError for an optimistic-concurrency miss.
            # Keep that storage detail out of the HTTP layer so stale viewer writes
            # become a retryable 409 instead of an opaque 500.
            raise ActionPlanConflictError(str(error)) from error
        return await self.workspace(request.options)

    async def update_workspace_selection(
        self, request: DuplicateWorkspaceSelectionDelta
    ) -> DuplicateWorkspaceState:
        current = await self.workspace(request.options)
        if current.revision != request.revision:
            raise ActionPlanConflictError("Duplicate workspace changed; reload its membership")
        selected = set(current.selected_group_ids)
        selected.difference_update(request.removed_group_ids)
        selected.update(request.added_group_ids)
        return await self.save_workspace_selection(
            DuplicateWorkspaceSelectionUpdate(
                options=request.options,
                selected_group_ids=sorted(selected),
                active_group_id=request.active_group_id,
                revision=request.revision,
            )
        )

    async def workspace_membership(
        self, request: DuplicateWorkspaceMembershipRequest
    ) -> DuplicateWorkspaceMembership:
        current = await self.workspace(request.options)
        requested = set(request.group_ids)
        return DuplicateWorkspaceMembership(
            revision=current.revision,
            selected_count=current.selected_count,
            selected_group_ids=[
                group_id for group_id in current.selected_group_ids if group_id in requested
            ],
        )

    async def apply_rules(
        self,
        options: DuplicateAnalysisOptions,
    ) -> DuplicateWorkspaceState:
        """Persist automatic recommendations in bounded projection-backed batches."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        safe_options = options.model_copy(update={"analyze_automatically": False})
        limit = getattr(self._settings, "action_max_targets", 5000)
        target_ids = await self._matching_group_ids(
            source="both",
            state="auto_ready",
            limit=limit + 1,
        )
        if len(target_ids) > limit:
            raise ValueError(
                f"Automatic duplicate rules match more than the configured {limit} group limit"
            )
        current_workspace = await self.workspace(safe_options)
        applied_group_ids: list[str] = []
        batch_size = max(
            1,
            min(250, getattr(self._settings, "sync_batch_size", 250)),
        )
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            _, _, _, snapshot = await self._snapshot_groups(discovered, safe_options)
            for discovery_source in {
                group.discovery_source for group in snapshot.groups
            }:
                groups = [
                    group
                    for group in snapshot.groups
                    if group.discovery_source == discovery_source and group.auto_selected
                ]
                records = await self._reviews.get_many(
                    discovery_source,
                    [group.stable_group_key for group in groups],
                )
                for group in groups:
                    record = records.get(group.stable_group_key)
                    existing_decisions = (
                        list(getattr(record, "member_decisions", []) or [])
                        if record
                        else []
                    )
                    if getattr(record, "manual_action", None) is not None or any(
                        decision.get("source") == "manual"
                        for decision in existing_decisions
                        if isinstance(decision, dict)
                    ):
                        continue
                    recommended = [
                        {
                            "asset_id": str(member.id),
                            "disposition": member.recommended_disposition,
                            "source": "automatic",
                            "status": "pending",
                        }
                        for member in group.members
                        if member.recommended_disposition is not None
                    ]
                    if len(recommended) != len(group.members):
                        continue
                    await self._reviews.save_draft(
                        discovery_source=group.discovery_source,
                        provider_group_id=group.provider_group_id or group.group_id,
                        stable_group_key=group.stable_group_key,
                        member_set_key=group.member_set_key,
                        member_fingerprint=group.member_fingerprint,
                        member_decisions=recommended,
                        stack_primary_asset_id=(
                            group.recommended_primary_asset_id
                            if group.recommended_action == "stack_all"
                            else None
                        ),
                        stack_resolution="move_selected",
                        metadata_keeper_asset_id=None,
                        draft_status="pending",
                    )
                    applied_group_ids.append(group.group_id)

        selected_group_ids = list(
            dict.fromkeys([*current_workspace.selected_group_ids, *applied_group_ids])
        )
        return await self.save_workspace_selection(
            DuplicateWorkspaceSelectionUpdate(
                options=safe_options,
                selected_group_ids=selected_group_ids,
                active_group_id=current_workspace.active_group_id,
                revision=current_workspace.revision,
            )
        )

    async def reset_workspace_decisions(
        self,
        request: DuplicateWorkspaceResetRequest,
    ) -> DuplicateWorkspaceState:
        """Clear saved choices and remove those groups from the durable selection."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        if request.all_decisions:
            cleared_group_count = await self._reviews.reset_all_decisions()
            return DuplicateWorkspaceState(cleared_group_count=cleared_group_count)
        requested_ids = list(dict.fromkeys(request.group_ids))
        identities = await self._group_identities(group_ids=requested_ids)
        groups_by_id: dict[str, Any] = {group.group_id: group for group in identities}
        missing = [group_id for group_id in requested_ids if group_id not in groups_by_id]
        if missing:
            raise ActionPlanConflictError("A duplicate group is no longer available")

        stable_keys_by_source: dict[str, list[str]] = {}
        for group_id in requested_ids:
            group = groups_by_id[group_id]
            source = group.discovery_source
            source_name = source.value if isinstance(source, DiscoverySource) else str(source)
            stable_keys_by_source.setdefault(source_name, []).append(group.stable_group_key)
        for discovery_source, stable_group_keys in stable_keys_by_source.items():
            await self._reviews.clear_decisions(discovery_source, stable_group_keys)

        await self._reviews.consume_workspace_groups(
            [groups_by_id[group_id].stable_group_key for group_id in requested_ids],
            requested_ids,
        )
        return await self.workspace(request.options)

    @staticmethod
    def _review_state_query(review_filter: str) -> str:
        return {
            "All groups": "all",
            "Needs review": "needs_review",
            "Auto-ready": "auto_ready",
            "Blocked": "blocked",
            "Actionable": "actionable",
            "Needs decisions": "needs_decisions",
        }.get(review_filter, "all")

    async def _matching_group_ids(
        self,
        *,
        source: str,
        state: str,
        limit: int,
    ) -> list[str]:
        resolver = getattr(self._discovery, "resolve_matching_group_ids", None)
        if not callable(resolver):
            raise RuntimeError(
                "Filtered duplicate ID lookup requires the persisted V2 projection"
            )
        return await resolver(source=source, state=state, limit=limit)

    async def _keeper_target_ids(
        self,
        request: DuplicateKeeperSelectionRequest,
    ) -> tuple[list[str], bool]:
        if request.scope == "current_page":
            return list(dict.fromkeys(request.group_ids)), False

        limit = self._settings.action_max_targets
        group_ids = await self._matching_group_ids(
            source=request.source_filter,
            state=self._review_state_query(request.review_filter),
            limit=limit + 1,
        )
        return group_ids[:limit], len(group_ids) > limit

    async def _run_keeper_selection(
        self,
        request: DuplicateKeeperSelectionRequest,
        *,
        apply: bool,
    ) -> DuplicateKeeperSelectionResult:
        """Preview or persist bounded rule-driven keep/delete drafts."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        target_ids, limit_exceeded = await self._keeper_target_ids(request)
        counts = {
            "matched_group_count": len(target_ids),
            "valid_group_count": 0,
            "resolved_group_count": 0,
            "would_apply_group_count": 0,
            "applied_group_count": 0,
            "ambiguous_group_count": 0,
            "blocked_group_count": 0,
            "preserved_manual_group_count": 0,
            "missing_group_count": 0,
            "keeper_count": 0,
            "trash_count": 0,
        }
        if limit_exceeded:
            counts["matched_group_count"] = self._settings.action_max_targets + 1
            return DuplicateKeeperSelectionResult(**counts, limit_exceeded=True)

        options = await self._options(request.options)
        batch_size = max(1, min(250, getattr(self._settings, "sync_batch_size", 250)))
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            discovered_by_id = {group.group_id: group for group in discovered}
            _, _, _, snapshot = await self._snapshot_groups(discovered, options)
            exact_by_id = {group.group_id: group for group in snapshot.groups}
            missing = set(batch_ids) - set(exact_by_id)
            counts["missing_group_count"] += len(missing)

            asset_ids = {asset.id for group in discovered for asset in group.assets}
            relations = await self._assets.get_relation_ids(asset_ids)

            review_records: dict[tuple[str, str], Any] = {}
            for discovery_source in {group.discovery_source for group in snapshot.groups}:
                source_groups = [
                    group for group in snapshot.groups if group.discovery_source == discovery_source
                ]
                records = await self._reviews.get_many(
                    discovery_source,
                    [group.stable_group_key for group in source_groups],
                )
                review_records.update(
                    ((discovery_source, key), record) for key, record in records.items()
                )

            drafts: list[dict[str, Any]] = []
            for group_id in batch_ids:
                exact = exact_by_id.get(group_id)
                source = discovered_by_id.get(group_id)
                if exact is None or source is None:
                    continue
                invalid = not exact.eligible or len(exact.members) < 2
                if invalid:
                    counts["blocked_group_count"] += 1
                    continue
                counts["valid_group_count"] += 1

                record = review_records.get((exact.discovery_source, exact.stable_group_key))
                existing_decisions = list(getattr(record, "member_decisions", []) or [])
                has_manual = any(
                    isinstance(decision, dict) and decision.get("source") == "manual"
                    for decision in existing_decisions
                )
                if has_manual and not request.overwrite_manual:
                    counts["preserved_manual_group_count"] += 1
                    continue

                choice = choose_keeper(exact, source, request.rules, relations)
                if choice.keeper_asset_id is None:
                    counts["ambiguous_group_count"] += 1
                    continue
                counts["resolved_group_count"] += 1
                counts["would_apply_group_count"] += 1
                counts["keeper_count"] += 1
                counts["trash_count"] += len(exact.members) - 1

                if apply:
                    drafts.append(
                        {
                            "discovery_source": exact.discovery_source,
                            "provider_group_id": exact.provider_group_id or exact.group_id,
                            "stable_group_key": exact.stable_group_key,
                            "member_set_key": exact.member_set_key,
                            "member_fingerprint": exact.member_fingerprint,
                            "member_decisions": [
                                {
                                    "asset_id": str(member.id),
                                    "disposition": (
                                        "keep"
                                        if member.id == choice.keeper_asset_id
                                        else "delete"
                                    ),
                                    "source": "automatic",
                                    "status": "pending",
                                }
                                for member in exact.members
                            ],
                            "stack_primary_asset_id": None,
                            "stack_resolution": "move_selected",
                            "metadata_keeper_asset_id": choice.keeper_asset_id,
                            "draft_status": "completed",
                        }
                    )

            if apply and drafts:
                save_many = getattr(self._reviews, "save_drafts", None)
                if callable(save_many):
                    await save_many(drafts)
                else:
                    for draft in drafts:
                        await self._reviews.save_draft(**draft)
                counts["applied_group_count"] += len(drafts)

        return DuplicateKeeperSelectionResult(**counts, limit_exceeded=False)

    async def preview_keeper_selection(
        self,
        request: DuplicateKeeperSelectionRequest,
    ) -> DuplicateKeeperSelectionResult:
        return await self._run_keeper_selection(request, apply=False)

    async def apply_keeper_selection(
        self,
        request: DuplicateKeeperSelectionRequest,
    ) -> DuplicateKeeperSelectionResult:
        return await self._run_keeper_selection(request, apply=True)

    async def apply_workspace_preset(
        self, request: DuplicateWorkspacePresetRequest
    ) -> DuplicateWorkspaceState:
        """Persist a preset without hydrating the complete duplicate projection."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        options = await self._options(request.options)
        if request.scope == "all_matching":
            limit = getattr(self._settings, "action_max_targets", 5000)
            resolved_ids = await self._matching_group_ids(
                source=request.source_filter,
                state=self._review_state_query(request.review_filter),
                limit=limit + 1,
            )
            if len(resolved_ids) > limit:
                raise ValueError(
                    f"Duplicate preset matches more than the configured {limit} group limit"
                )
            target_ids = resolved_ids
        else:
            target_ids = list(dict.fromkeys(request.group_ids))

        expected_source = (
            "immich_duplicate"
            if request.source_filter == "immich"
            else "companion_similarity"
        )
        applied: list[str] = []
        skipped: list[str] = []
        batch_size = max(1, min(250, self._settings.sync_batch_size))
        for offset in range(0, len(target_ids), batch_size):
            batch_ids = target_ids[offset : offset + batch_size]
            discovered = await self._groups_by_ids(batch_ids)
            _, _, _, snapshot = await self._snapshot_groups(discovered, options)
            groups_by_id = {group.group_id: group for group in snapshot.groups}
            for group_id in batch_ids:
                group = groups_by_id.get(group_id)
                if group is None:
                    skipped.append(group_id)
                    continue
                if (
                    request.source_filter != "both"
                    and expected_source not in group.discovery_sources
                ):
                    skipped.append(group_id)
                    continue
                invalid = (
                    not group.members
                    or (request.disposition == "delete" and not group.eligible)
                    or (
                        request.disposition == "stack"
                        and (
                            len(group.members) < 2
                            or any(member.is_offline for member in group.members)
                        )
                    )
                )
                if invalid:
                    skipped.append(group.group_id)
                    continue
                primary = group.effective_primary_asset_id or group.keeper_asset_id
                member_ids = {member.id for member in group.members}
                if primary not in member_ids:
                    primary = group.members[0].id
                await self._reviews.save_draft(
                    discovery_source=group.discovery_source,
                    provider_group_id=group.provider_group_id or group.group_id,
                    stable_group_key=group.stable_group_key,
                    member_set_key=group.member_set_key,
                    member_fingerprint=group.member_fingerprint,
                    member_decisions=[
                        {
                            "asset_id": str(member.id),
                            "disposition": request.disposition,
                            "source": "manual",
                            "status": "pending",
                        }
                        for member in group.members
                    ],
                    stack_primary_asset_id=(
                        primary if request.disposition == "stack" else None
                    ),
                    stack_resolution="move_selected",
                    metadata_keeper_asset_id=None,
                    draft_status="completed",
                )
                applied.append(group.group_id)

        workspace = await self.workspace(options)
        updated = await self.save_workspace_selection(
            DuplicateWorkspaceSelectionUpdate(
                options=options,
                selected_group_ids=list(
                    dict.fromkeys([*workspace.selected_group_ids, *applied])
                ),
                active_group_id=workspace.active_group_id,
                revision=workspace.revision,
            )
        )
        return updated.model_copy(
            update={
                "last_applied_group_ids": applied,
                "last_skipped_group_ids": skipped,
            }
        )

    async def save_group_draft(
        self,
        request: DuplicateGroupDraftUpdate,
    ) -> DuplicateGroupDraft:
        """Validate and save member-level choices independently of execution."""

        if self._reviews is None:
            raise RuntimeError("Duplicate review persistence is unavailable")
        options = await self._options(request.options)
        groups = await self._groups_by_ids([request.group_id])
        _, _, _, result = await self._snapshot_groups(groups, options)
        group = next(
            (candidate for candidate in result.groups if candidate.group_id == request.group_id),
            None,
        )
        if group is None or group.member_fingerprint != request.member_fingerprint:
            raise ActionPlanConflictError("The duplicate group changed before its draft was saved")
        member_ids = {member.id for member in group.members}
        decisions = {decision.asset_id: decision for decision in request.decisions}
        if not set(decisions).issubset(member_ids):
            raise ActionPlanConflictError("A draft decision references a non-member asset")
        if request.stack_primary_asset_id is not None:
            primary = decisions.get(request.stack_primary_asset_id)
            if primary is None or primary.disposition != "stack":
                raise ActionPlanConflictError(
                    "The stack primary must first have the Stack disposition"
                )
        persisted_stacks: dict[str, list[object]] = {}
        for decision in request.decisions:
            if decision.stack_id is not None:
                persisted_stacks.setdefault(decision.stack_id, []).append(decision)
        if persisted_stacks:
            if any(
                decision.disposition == "stack" and decision.stack_id is None
                for decision in request.decisions
            ):
                raise ActionPlanConflictError(
                    "Every Stack decision must keep its pending-stack assignment"
                )
            for stack_members in persisted_stacks.values():
                primaries = [
                    decision for decision in stack_members if decision.stack_primary
                ]
                if len(primaries) != 1:
                    raise ActionPlanConflictError(
                        "Each pending stack must have exactly one primary image"
                    )
                resolutions = {
                    decision.stack_resolution
                    for decision in stack_members
                    if decision.stack_resolution is not None
                }
                if len(resolutions) > 1:
                    raise ActionPlanConflictError(
                        "A pending stack cannot have conflicting saved resolutions"
                    )
        stack_ids = [
            decision.asset_id for decision in request.decisions if decision.disposition == "stack"
        ]
        stack_primary_asset_id = request.stack_primary_asset_id
        if stack_ids and stack_primary_asset_id is None:
            preferred_primary = group.effective_primary_asset_id or group.keeper_asset_id
            stack_primary_asset_id = (
                preferred_primary if preferred_primary in stack_ids else stack_ids[0]
            )
        survivor_ids = [
            decision.asset_id for decision in request.decisions if decision.disposition != "delete"
        ]
        has_deletions = any(decision.disposition == "delete" for decision in request.decisions)
        metadata_keeper_asset_id = (
            survivor_ids[0]
            if request.status == "completed"
            and len(decisions) == len(member_ids)
            and has_deletions
            and len(survivor_ids) == 1
            else None
        )
        record = await self._reviews.save_draft(
            discovery_source=group.discovery_source,
            provider_group_id=group.provider_group_id or group.group_id,
            stable_group_key=group.stable_group_key,
            member_set_key=group.member_set_key,
            member_fingerprint=group.member_fingerprint,
            member_decisions=[decision.model_dump(mode="json") for decision in request.decisions],
            stack_primary_asset_id=stack_primary_asset_id,
            stack_resolution=request.stack_resolution,
            metadata_keeper_asset_id=metadata_keeper_asset_id,
            draft_status=request.status,
        )
        return DuplicateGroupDraft(
            group_id=group.group_id,
            discovery_source=group.discovery_source,
            member_fingerprint=record.member_fingerprint,
            decisions=record.member_decisions,
            stack_primary_asset_id=record.stack_primary_asset_id,
            stack_resolution=record.stack_resolution,
            metadata_keeper_asset_id=record.metadata_keeper_asset_id,
            status=record.draft_status,
            stale=False,
        )
