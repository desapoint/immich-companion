from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, got {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1))


schema = "backend/companion/duplicate_schema.py"
replace_once(
    schema,
    '''DuplicateReviewStatus = Literal[\n    "pending",\n    "manually_configured",\n    "reviewed_keep_all",\n    "reviewed_resolve",\n    "reviewed_stack_all",\n    "review_later",\n    "drifted",\n]\n''',
    '''DuplicateReviewStatus = Literal[\n    "pending",\n    "manually_configured",\n    "reviewed_keep_all",\n    "reviewed_resolve",\n    "reviewed_stack_all",\n    "reviewed_mixed",\n    "review_later",\n    "drifted",\n]\nCOMPLETED_DUPLICATE_REVIEW_STATUSES = frozenset(\n    {"reviewed_keep_all", "reviewed_resolve", "reviewed_stack_all", "reviewed_mixed"}\n)\n''',
)

reviews = "backend/companion/duplicate_review_repository.py"
replace_once(
    reviews,
    '''from companion.database import DatabaseManager\nfrom companion.models import DuplicateGroupReviewRecord, DuplicateReviewWorkspaceRecord\n''',
    '''from companion.database import DatabaseManager\nfrom companion.duplicate_schema import COMPLETED_DUPLICATE_REVIEW_STATUSES\nfrom companion.models import DuplicateGroupReviewRecord, DuplicateReviewWorkspaceRecord\n''',
)
replace_once(
    reviews,
    '''            .where(\n                or_(\n                    func.coalesce(\n                        func.json_array_length(DuplicateGroupReviewRecord.member_decisions), 0\n                    )\n                    > 0,\n                    DuplicateGroupReviewRecord.stack_primary_asset_id.is_not(None),\n                )\n            )\n''',
    '''            .where(\n                ~DuplicateGroupReviewRecord.review_status.in_(\n                    COMPLETED_DUPLICATE_REVIEW_STATUSES\n                ),\n                or_(\n                    func.coalesce(\n                        func.json_array_length(DuplicateGroupReviewRecord.member_decisions), 0\n                    )\n                    > 0,\n                    DuplicateGroupReviewRecord.stack_primary_asset_id.is_not(None),\n                ),\n            )\n''',
)
replace_once(
    reviews,
    '''            record.member_decisions = [\n                {**decision, "status": "completed"}\n                for decision in list(record.member_decisions or [])\n            ]\n            record.draft_status = "completed"\n            record.updated_at = datetime.now(UTC)\n''',
    '''            record.member_decisions = [\n                {**decision, "status": "completed"}\n                for decision in list(record.member_decisions or [])\n            ]\n            if record.manual_action == "mixed" and record.review_status == "manually_configured":\n                record.review_status = "reviewed_mixed"\n            record.draft_status = "completed"\n            record.updated_at = datetime.now(UTC)\n''',
)

composite = "backend/companion/composite_duplicate_repository.py"
replace_once(composite, "    func,\n    select,\n", "    func,\n    or_,\n    select,\n")
replace_once(
    composite,
    '''from companion.discovery.base import DiscoveredGroup, DiscoveryEvidence\nfrom companion.duplicate_identity import member_set_key, stable_group_key\n''',
    '''from companion.discovery.base import DiscoveredGroup, DiscoveryEvidence\nfrom companion.duplicate_identity import member_set_key, stable_group_key\nfrom companion.duplicate_schema import COMPLETED_DUPLICATE_REVIEW_STATUSES\n''',
)
replace_once(
    composite,
    '''SNAPSHOT_STATE_ID = 1\nWRITE_BATCH_SIZE = 1_000\n\n\nclass CompositeDuplicateSnapshotAssetMissingError''',
    '''SNAPSHOT_STATE_ID = 1\nWRITE_BATCH_SIZE = 1_000\n\n\ndef _unresolved_review_filter():\n    return or_(\n        DuplicateGroupReviewRecord.review_status.is_(None),\n        ~DuplicateGroupReviewRecord.review_status.in_(COMPLETED_DUPLICATE_REVIEW_STATUSES),\n    )\n\n\nclass CompositeDuplicateSnapshotAssetMissingError''',
)
replace_once(
    composite,
    '''        statement = select(CompositeDuplicateGroupRecord.group_id)\n        if state != "all":\n            review_join = and_(\n                DuplicateGroupReviewRecord.stable_group_key\n                == CompositeDuplicateGroupRecord.stable_group_key,\n                DuplicateGroupReviewRecord.member_fingerprint\n                == CompositeDuplicateGroupRecord.member_fingerprint,\n            )\n            decision_count = func.coalesce(\n''',
    '''        review_join = and_(\n            DuplicateGroupReviewRecord.stable_group_key\n            == CompositeDuplicateGroupRecord.stable_group_key,\n            DuplicateGroupReviewRecord.member_fingerprint\n            == CompositeDuplicateGroupRecord.member_fingerprint,\n        )\n        statement = (\n            select(CompositeDuplicateGroupRecord.group_id)\n            .outerjoin(DuplicateGroupReviewRecord, review_join)\n            .where(_unresolved_review_filter())\n        )\n        if state != "all":\n            decision_count = func.coalesce(\n''',
)
replace_once(
    composite,
    '''            statement = statement.outerjoin(DuplicateGroupReviewRecord, review_join)\n            if state == "auto_ready":\n''',
    '''            if state == "auto_ready":\n''',
)
replace_once(
    composite,
    '''            count_statement = select(func.count()).select_from(CompositeDuplicateGroupRecord)\n            group_statement = select(CompositeDuplicateGroupRecord)\n\n            if state != "all":\n                review_join = and_(\n                    DuplicateGroupReviewRecord.stable_group_key\n                    == CompositeDuplicateGroupRecord.stable_group_key,\n                    DuplicateGroupReviewRecord.member_fingerprint\n                    == CompositeDuplicateGroupRecord.member_fingerprint,\n                )\n                decision_count = func.coalesce(\n''',
    '''            review_join = and_(\n                DuplicateGroupReviewRecord.stable_group_key\n                == CompositeDuplicateGroupRecord.stable_group_key,\n                DuplicateGroupReviewRecord.member_fingerprint\n                == CompositeDuplicateGroupRecord.member_fingerprint,\n            )\n            count_statement = (\n                select(func.count())\n                .select_from(CompositeDuplicateGroupRecord)\n                .outerjoin(DuplicateGroupReviewRecord, review_join)\n                .where(_unresolved_review_filter())\n            )\n            group_statement = (\n                select(CompositeDuplicateGroupRecord)\n                .outerjoin(DuplicateGroupReviewRecord, review_join)\n                .where(_unresolved_review_filter())\n            )\n\n            if state != "all":\n                decision_count = func.coalesce(\n''',
)
replace_once(
    composite,
    '''                count_statement = count_statement.outerjoin(DuplicateGroupReviewRecord, review_join)\n                group_statement = group_statement.outerjoin(DuplicateGroupReviewRecord, review_join)\n                if state == "auto_ready":\n''',
    '''                if state == "auto_ready":\n''',
)

service = "backend/companion/duplicate_service.py"
replace_once(
    service,
    '''from companion.duplicate_schema import (\n    CrossSourceDuplicateResult,\n''',
    '''from companion.duplicate_schema import (\n    COMPLETED_DUPLICATE_REVIEW_STATUSES,\n    CrossSourceDuplicateResult,\n''',
)
replace_once(
    service,
    '''            if state.member_fingerprint != group.member_fingerprint:\n                groups.append(group.model_copy(update={"review_status": "drifted"}))\n                continue\n            manual_action = state.manual_action\n''',
    '''            if state.member_fingerprint != group.member_fingerprint:\n                groups.append(group.model_copy(update={"review_status": "drifted"}))\n                continue\n            if state.review_status in COMPLETED_DUPLICATE_REVIEW_STATUSES:\n                continue\n            manual_action = state.manual_action\n''',
)
replace_once(
    service,
    '''        return result.model_copy(update={"groups": groups})\n\n    @staticmethod\n    def _verification_candidates''',
    '''        counts = {\n            name: sum(group.status == name for group in groups)\n            for name in ("exact", "unverified", "mismatch", "ineligible")\n        }\n        return result.model_copy(\n            update={\n                "groups": groups,\n                "group_count": len(groups),\n                "exact_group_count": counts["exact"],\n                "unverified_group_count": counts["unverified"],\n                "mismatch_group_count": counts["mismatch"],\n                "ineligible_group_count": counts["ineligible"],\n            }\n        )\n\n    @staticmethod\n    def _verification_candidates''',
)
replace_once(
    service,
    '''                "stack_all": "reviewed_stack_all",\n                "mixed": "manually_configured",\n''',
    '''                "stack_all": "reviewed_stack_all",\n                "mixed": "reviewed_mixed",\n''',
)

tests = "backend/tests/test_duplicate_service.py"
append = '''\n\n@pytest.mark.asyncio\nasync def test_completed_review_is_suppressed_without_native_group_removal() -> None:\n    content = b"same"\n    candidate_group = group(\n        asset(UPLOAD_1, external=False, checksum=immich_sha1(content), filename="one.jpg"),\n        asset(EXTERNAL_1, external=True, checksum="path", filename="two.jpg"),\n    )\n    baseline = assemble(candidate_group, [report(EXTERNAL_1, content)])\n    reviewed = baseline.groups[0]\n    reviews = FakeReviews(\n        SimpleNamespace(\n            stable_group_key=reviewed.stable_group_key,\n            member_fingerprint=reviewed.member_fingerprint,\n            manual_action="keep_all",\n            manual_primary_asset_id=None,\n            member_decisions=[\n                {\n                    "asset_id": str(member.id),\n                    "disposition": "keep",\n                    "source": "manual",\n                    "status": "completed",\n                }\n                for member in reviewed.members\n            ],\n            stack_primary_asset_id=None,\n            stack_resolution="move_selected",\n            metadata_keeper_asset_id=None,\n            draft_status="completed",\n            review_status="reviewed_keep_all",\n        )\n    )\n    service = CrossSourceDuplicateService(\n        SimpleNamespace(action_plan_ttl_seconds=900),\n        FakeImmich(candidate_group),\n        FakeAssets(),\n        FakeReports([report(EXTERNAL_1, content)]),\n        FakeActions(),\n        FakeTasks(),\n        FakeRuntimeSettings(),\n        reviews,\n    )\n\n    result = await service.result()\n\n    assert result.groups == []\n    assert result.group_count == 0\n    assert result.exact_group_count == 0\n''' 
text = Path(tests).read_text()
if "test_completed_review_is_suppressed_without_native_group_removal" in text:
    raise SystemExit("lifecycle regression test already exists")
Path(tests).write_text(text + append)
