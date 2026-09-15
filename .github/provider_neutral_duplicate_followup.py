from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1))


service = "backend/companion/duplicate_service.py"

# Similarity groups remain conservative for automation, but manual reviewed actions are
# provider-neutral. `eligible` is the manual-action gate; auto_resolvable/auto_selected
# remain false for visual-only groups.
replace_once(service, '                        "eligible": False,\n', "")

# Resolve a reviewed snapshot by stable membership first. The persisted production
# provider can do this with an indexed identity lookup, while legacy/test providers
# retain the previous full-snapshot fallback so a provider group ID changing alone
# never invalidates an otherwise unchanged reviewed group.
replace_once(
    service,
    '''        if pending_resolution:
            discovered = await self._groups_by_ids(
                [planned["group_id"] for planned in pending_resolution]
            )
            _, _, _, live_result = await self._snapshot_groups(discovered, options)
            reviewed = {group.stable_group_key: group for group in live_result.groups}
        else:
            reviewed = {}
''',
    '''        if pending_resolution:
            stable_keys = [planned["stable_group_key"] for planned in pending_resolution]
            identities = await self._group_identities(stable_group_keys=stable_keys)
            if identities is None:
                live_result = await self.result(options)
            else:
                discovered = await self._groups_by_ids(
                    [identity.group_id for identity in identities]
                )
                _, _, _, live_result = await self._snapshot_groups(discovered, options)
            reviewed = {group.stable_group_key: group for group in live_result.groups}
        else:
            reviewed = {}
''',
)

# Client-side V2 state must agree with the provider-neutral backend: an offline
# original does not prevent trashing the Immich asset record after explicit review.
frontend = "frontend/src/v2/data/api/duplicateRepository.ts"
replace_once(
    frontend,
    '''function groupState(group: ApiDuplicateGroup, draft: ApiDuplicateDraft | undefined): DuplicateState {
  if (!group.eligible || group.status === 'ineligible' || group.members.some((member) => member.is_offline) || draft?.stale) return 'Blocked';
''',
    '''function groupState(group: ApiDuplicateGroup, draft: ApiDuplicateDraft | undefined): DuplicateState {
  if (!group.eligible || group.status === 'ineligible' || draft?.stale) return 'Blocked';
''',
)

# Direct asset trash test double. Keep the old native methods temporarily because
# unrelated legacy API-client tests may still exercise the fake explicitly, but the
# duplicate service must no longer call them.
tests = "backend/tests/test_duplicate_service.py"
replace_once(
    tests,
    '''        self.fail_stack_attempts = 0
        self.fail_resolution_attempts = 0
        self.album_additions: list[tuple[UUID, list[UUID]]] = []
''',
    '''        self.fail_stack_attempts = 0
        self.fail_resolution_attempts = 0
        self.fail_trash_attempts = 0
        self.trash_calls: list[list[UUID]] = []
        self.album_additions: list[tuple[UUID, list[UUID]]] = []
''',
)
replace_once(
    tests,
    '''    async def get_asset(self, asset_id):
        return next(item for item in self.candidate_group.assets if item.id == asset_id)
''',
    '''    async def trash_assets(self, asset_ids):
        self.events.append("trash")
        self.trash_calls.append(list(asset_ids))
        if self.fail_trash_attempts:
            self.fail_trash_attempts -= 1
            raise ImmichApiError("trash assets")
        selected = set(asset_ids)
        for item in self.candidate_group.assets:
            if item.id in selected:
                item.is_trashed = True

    async def get_asset(self, asset_id):
        return next(item for item in self.candidate_group.assets if item.id == asset_id)
''',
)

# A companion-similarity group is manually actionable even though it is deliberately
# never auto-resolvable from similarity evidence alone.
replace_once(tests, '    assert found.eligible is False\n', '    assert found.eligible is True\n')

# Stack-only plans no longer make a meaningless native duplicate-group resolve call.
replace_once(
    tests,
    '''    assert immich.events == ["resolve", "stack"]
    assert immich.resolutions[0].keep_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert immich.resolutions[0].trash_asset_ids == []
''',
    '''    assert immich.events == ["stack"]
    assert immich.resolutions == []
    assert immich.trash_calls == []
''',
)

# Mixed metadata/delete/stack plans preserve metadata first, trash reviewed asset IDs,
# then perform the stack follow-up.
replace_once(
    tests,
    '''    assert immich.events == ["album", "tag", "resolve", "stack"]
    assert immich.resolutions[0].keep_asset_ids == [UPLOAD_2, EXTERNAL_1, EXTERNAL_2]
    assert immich.resolutions[0].trash_asset_ids == [UPLOAD_1]
''',
    '''    assert immich.events == ["album", "tag", "trash", "stack"]
    assert immich.resolutions == []
    assert immich.trash_calls == [[UPLOAD_1]]
''',
)

replace_once(
    tests,
    '''async def test_rediscovered_group_uses_current_provider_id_during_execution() -> None:
''',
    '''async def test_rediscovered_provider_id_does_not_invalidate_reviewed_membership() -> None:
''',
)
replace_once(
    tests,
    '''    assert outcome.status == "completed"
    assert immich.resolutions[0].duplicate_id == REDISCOVERED_GROUP_ID


@pytest.mark.asyncio
async def test_tampered_plan_fingerprint_is_rejected_before_resolution() -> None:
''',
    '''    assert outcome.status == "completed"
    assert immich.trash_calls == [[EXTERNAL_1]]
    assert immich.resolutions == []


@pytest.mark.asyncio
async def test_tampered_plan_fingerprint_is_rejected_before_resolution() -> None:
''',
)

replace_once(
    tests,
    '''async def test_stack_source_drift_blocks_follow_up_after_native_resolution() -> None:
''',
    '''async def test_stack_source_drift_blocks_follow_up_before_remote_mutation() -> None:
''',
)
replace_once(
    tests,
    '''    assert immich.events == ["resolve"]
    assert immich.created_stacks == []
    assert actions.record.result["group_execution"][PUBLIC_GROUP_ID] == {
''',
    '''    assert immich.events == []
    assert immich.created_stacks == []
    assert actions.record.result["group_execution"][PUBLIC_GROUP_ID] == {
''',
)
replace_once(
    tests,
    '''    assert outcome.status == "failed"
    assert outcome.summary["drifted_group_ids"] == [PUBLIC_GROUP_ID]
    assert immich.events == ["resolve"]
    assert immich.created_stacks == []


@pytest.mark.asyncio
async def test_plan_rejects_an_incomplete_saved_member_draft() -> None:
''',
    '''    assert outcome.status == "failed"
    assert outcome.summary["drifted_group_ids"] == [PUBLIC_GROUP_ID]
    assert immich.events == []
    assert immich.created_stacks == []


@pytest.mark.asyncio
async def test_plan_rejects_an_incomplete_saved_member_draft() -> None:
''',
)

replace_once(
    tests,
    '''async def test_zero_survivor_plan_uses_explicit_all_trash_duplicate_resolution() -> None:
''',
    '''async def test_zero_survivor_plan_trashes_all_reviewed_members_directly() -> None:
''',
)
replace_once(
    tests,
    '''    assert outcome.status == "completed"
    assert outcome.counters["groups_zero_survivor"] == 1
    assert immich.resolutions[0].keep_asset_ids == []
    assert immich.resolutions[0].trash_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert assets.removed == [UPLOAD_1, EXTERNAL_1]
''',
    '''    assert outcome.status == "completed"
    assert outcome.counters["groups_zero_survivor"] == 1
    assert immich.resolutions == []
    assert immich.trash_calls == [[UPLOAD_1, EXTERNAL_1]]
    assert assets.removed == [UPLOAD_1, EXTERNAL_1]
''',
)

replace_once(
    tests,
    '''async def test_keep_all_resolves_provider_group_without_trashing_members() -> None:
''',
    '''async def test_keep_all_completes_without_remote_asset_mutation() -> None:
''',
)
replace_once(
    tests,
    '''    assert outcome.status == "completed"
    assert immich.resolutions[0].keep_asset_ids == [UPLOAD_1, EXTERNAL_1]
    assert immich.resolutions[0].trash_asset_ids == []
    assert await immich.list_duplicate_groups() == []


@pytest.mark.asyncio
async def test_failed_stack_follow_up_resumes_without_replaying_resolution() -> None:
''',
    '''    assert outcome.status == "completed"
    assert immich.resolutions == []
    assert immich.trash_calls == []
    assert immich.events == []


@pytest.mark.asyncio
async def test_failed_stack_follow_up_resumes_without_replaying_resolution() -> None:
''',
)

replace_once(
    tests,
    '''    assert second.status == "completed"
    assert immich.events == ["resolve", "stack", "stack"]
    assert len(immich.resolutions) == 1
    assert record.result["group_execution"][PUBLIC_GROUP_ID]["state"] == "completed"


@pytest.mark.asyncio
async def test_failed_native_resolution_can_resume_without_replaying_completed_groups() -> None:
''',
    '''    assert second.status == "completed"
    assert immich.events == ["stack", "stack"]
    assert immich.resolutions == []
    assert record.result["group_execution"][PUBLIC_GROUP_ID]["state"] == "completed"


@pytest.mark.asyncio
async def test_failed_direct_trash_can_resume_without_replaying_completed_groups() -> None:
''',
)
replace_once(tests, '    immich.fail_resolution_attempts = 1\n', '    immich.fail_trash_attempts = 1\n')
replace_once(
    tests,
    '''    assert second.status == "completed"
    assert len(immich.resolutions) == 2
    assert record.result["group_execution"][PUBLIC_GROUP_ID]["state"] == "completed"
''',
    '''    assert second.status == "completed"
    assert immich.resolutions == []
    assert immich.trash_calls == [[EXTERNAL_1], [EXTERNAL_1]]
    assert immich.events == ["trash", "trash"]
    assert record.result["group_execution"][PUBLIC_GROUP_ID]["state"] == "completed"
''',
)
