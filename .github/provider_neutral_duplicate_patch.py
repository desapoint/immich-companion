from pathlib import Path
import re


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1))


schema = "backend/companion/duplicate_schema.py"
replace_once(
    schema,
    '''    @model_validator(mode="after")
    def manual_resolution_eligibility(self) -> ExactDuplicateGroup:
        """Allow explicit review of available Immich groups without relaxing automation."""

        self.eligible = (
            self.discovery_source == "immich_duplicate"
            and self.provider_group_id is not None
            and self.status != "ineligible"
            and len(self.members) >= 2
            and all(not member.is_offline for member in self.members)
        )
        if not self.discovery_sources:
            self.discovery_sources = [self.discovery_source]
        return self
''',
    '''    @model_validator(mode="after")
    def manual_resolution_eligibility(self) -> ExactDuplicateGroup:
        """Allow explicit review for any current multi-member duplicate group."""

        self.eligible = self.status != "ineligible" and len(self.members) >= 2
        if not self.discovery_sources:
            self.discovery_sources = [self.discovery_source]
        return self
''',
)

state = "backend/companion/v2_duplicate_review_state.py"
replace_once(
    state,
    '''    if (
        not group.eligible
        or group.status == "ineligible"
        or any(member.is_offline for member in group.members)
    ):
        return "blocked"
''',
    '''    if not group.eligible or group.status == "ineligible":
        return "blocked"
''',
)

service = "backend/companion/duplicate_service.py"
replace_once(service, "    ImmichDuplicateResolution,\n", "")
replace_once(
    service,
    '''def _reviewed_immich_delete_supported(group: ExactDuplicateGroup) -> bool:
    """Return whether a reviewed delete can be delegated to an Immich duplicate group."""

    return (
        group.discovery_source == DiscoverySource.IMMICH_DUPLICATE.value
        and group.provider_group_id is not None
        and group.status != "ineligible"
        and len(group.members) >= 2
    )
''',
    '''def _reviewed_delete_supported(group: ExactDuplicateGroup) -> bool:
    """Return whether reviewed member deletion is valid for the current group."""

    return group.status != "ineligible" and len(group.members) >= 2
''',
)
text = Path(service).read_text().replace(
    "_reviewed_immich_delete_supported", "_reviewed_delete_supported"
)
Path(service).write_text(text)
replace_once(
    service,
    '''        if action == "resolve" and not group.eligible:
            raise ActionPlanConflictError("Only verified exact groups can be resolved")
''',
    '''        if action == "resolve" and not group.eligible:
            raise ActionPlanConflictError(
                "This duplicate group is not eligible for reviewed resolution"
            )
''',
)
replace_once(
    service,
    '''                invalid = (
                    not exact.eligible
                    or len(exact.members) < 2
                    or any(member.is_offline for member in exact.members)
                )
''',
    '''                invalid = not exact.eligible or len(exact.members) < 2
''',
)
replace_once(
    service,
    '''            if (
                not group.eligible
                or group.status == "ineligible"
                or any(member.is_offline for member in group.members)
                or (draft is not None and draft.stale)
            ):
                state = "Blocked"
''',
    '''            if (
                not group.eligible
                or group.status == "ineligible"
                or (draft is not None and draft.stale)
            ):
                state = "Blocked"
''',
)
replace_once(
    service,
    '''            invalid = (
                not group.members
                or (request.disposition == "delete" and not group.eligible)
                or (
                    request.disposition in {"delete", "stack"}
                    and any(member.is_offline for member in group.members)
                )
                or (request.disposition == "stack" and len(group.members) < 2)
            )
''',
    '''            invalid = (
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
''',
)
replace_once(
    service,
    '''            if has_deletions and not _reviewed_delete_supported(group):
                raise ActionPlanConflictError(
                    "Deleting duplicate members requires an available Immich duplicate group"
                )
''',
    '''            if has_deletions and not _reviewed_delete_supported(group):
                raise ActionPlanConflictError(
                    "Deleting duplicate members requires a current multi-member duplicate group"
                )
''',
)
replace_once(
    service,
    '''        reviewed = (
            {group.stable_group_key: group for group in (await self.result(options)).groups}
            if pending_resolution
            else {}
        )
''',
    '''        if pending_resolution:
            discovered = await self._groups_by_ids(
                [planned["group_id"] for planned in pending_resolution]
            )
            _, _, _, live_result = await self._snapshot_groups(discovered, options)
            reviewed = {group.stable_group_key: group for group in live_result.groups}
        else:
            reviewed = {}
''',
)
replace_once(
    service,
    '''            else:
                planned["provider_group_id"] = live_group.provider_group_id or live_group.group_id
                preflight_ready.append(planned)
''',
    '''            else:
                planned["provider_group_id"] = live_group.provider_group_id
                preflight_ready.append(planned)
''',
)
replace_once(
    service,
    '''        unsupported = [
            item
            for item in pending_resolution
            if item["discovery_source"] != DiscoverySource.IMMICH_DUPLICATE.value
            or item.get("provider_group_id") is None
        ]
        if unsupported:
            await self._actions.finish_plan(
                plan_id,
                "failed",
                {"error": "unsupported_discovery_provider"},
            )
            raise PermanentTaskError(
                "Duplicate resolution is not supported for this discovery provider"
            )

''',
    "",
)

path = Path(service)
text = path.read_text()
pattern = re.compile(
    r'''        resolution_batches = \[\n.*?        resolution_done = perf_counter\(\)\n''',
    re.S,
)
replacement = '''        action_batches = [
            pending_resolution[offset : offset + batch_size]
            for offset in range(0, len(pending_resolution), batch_size)
        ]
        for batch_index, batch in enumerate(action_batches):
            await context.ensure_active()
            for planned in batch:
                identifier = planned["group_id"]
                group_trash_ids = [
                    UUID(value) for value in planned.get("trash_asset_ids", [])
                ]
                try:
                    if group_trash_ids:
                        await self._immich.trash_assets(group_trash_ids)
                        refreshed = [
                            await self._immich.get_asset(asset_id)
                            for asset_id in group_trash_ids
                        ]
                        if any(not asset.is_trashed for asset in refreshed):
                            raise ImmichApiError("verify trashed duplicate members")
                except ImmichApiError:
                    if identifier not in failed_ids:
                        failed_ids.append(identifier)
                    stored_execution[identifier] = {
                        "state": "failed",
                        "error": "duplicate_member_trash_failed",
                    }
                    await self._actions.record_duplicate_group_execution(
                        plan_id,
                        identifier,
                        "failed",
                        error="duplicate_member_trash_failed",
                    )
                    continue

                resolved_ids.add(identifier)
                trashed_ids.extend(group_trash_ids)
                state = (
                    "follow_up_pending"
                    if planned.get("follow_up") is not None
                    else "completed"
                )
                stored_execution[identifier] = {"state": state, "error": None}
                await self._actions.record_duplicate_group_execution(
                    plan_id,
                    identifier,
                    state,
                )
                completed_steps += 1

            await checkpoint("Applied reviewed duplicate member actions.")
            if batch_index + 1 < len(action_batches):
                await asyncio.sleep(pacing.full_min_batch_delay_seconds)

        if trashed_ids:
            await self._assets.remove_assets(trashed_ids)

        resolution_done = perf_counter()
'''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"{service}: resolution block match count={count}")
path.write_text(text)

actions = "backend/companion/action_repository.py"
replace_once(
    actions,
    '        """Persist an immutable reviewed Immich duplicate resolution."""\n',
    '        """Persist an immutable reviewed duplicate resolution."""\n',
)
replace_once(
    actions,
    '        """Reopen a failed plan when durable native or stack work remains."""\n',
    '        """Reopen a failed plan when durable asset or stack work remains."""\n',
)

tests = "backend/tests/test_duplicate_plan_selected_snapshot.py"
text = Path(tests).read_text()
text = text.replace("from companion.action_service import ActionPlanConflictError\n", "")
old = '''@pytest.mark.asyncio
async def test_reviewed_delete_still_rejects_similarity_only_group() -> None:
    group_id = "similarity:review-target"
    service, _ = _service(
        [group_id],
        dispositions=["keep", "delete"],
        eligible=False,
        status="unverified",
        discovery_source="companion_similarity",
    )

    with pytest.raises(
        ActionPlanConflictError,
        match="available Immich duplicate group",
    ):
        await service.plan(
            DuplicateResolutionPlanRequest(
                options=DuplicateAnalysisOptions(analyze_automatically=False),
                group_ids=[group_id],
            )
        )
'''
new = '''@pytest.mark.asyncio
async def test_reviewed_delete_allows_similarity_only_group_without_provider_id() -> None:
    group_id = "similarity:review-target"
    service, asset_ids = _service(
        [group_id],
        dispositions=["keep", "delete"],
        eligible=True,
        status="unverified",
        discovery_source="companion_similarity",
    )

    plan = await service.plan(
        DuplicateResolutionPlanRequest(
            options=DuplicateAnalysisOptions(analyze_automatically=False),
            group_ids=[group_id],
        )
    )

    assert plan.group_count == 1
    assert plan.groups[0].provider_group_id is None
    assert plan.groups[0].keep_asset_ids == [asset_ids[0]]
    assert plan.groups[0].trash_asset_ids == [asset_ids[1]]
'''
if old not in text:
    raise SystemExit("selected-snapshot similarity regression block missing")
Path(tests).write_text(text.replace(old, new, 1))

state_tests = "backend/tests/test_v2_duplicate_review_state.py"
replace_once(
    state_tests,
    '    assert v2_policy_state(group(offline=True)) == "blocked"\n',
    '    assert v2_policy_state(group(offline=True)) == "needs_review"\n',
)
