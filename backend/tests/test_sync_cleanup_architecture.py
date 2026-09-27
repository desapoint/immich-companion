"""Architecture guards for the completed first-class synchronization refactor."""

from datetime import UTC, datetime, timedelta
import inspect

from companion.asset_service import AssetSyncService
from companion.sync_schema import SyncRunStatus
from companion.synchronization import runtime as sync_runtime
from companion.synchronization.runtime import SyncStepTaskHandler


def test_legacy_service_stage_and_repair_implementations_are_removed() -> None:
    for name in (
        "_sync_catalogs",
        "_sync_assets",
        "_sync_stacks",
        "_sync_relationships",
        "_run_event_step",
        "_run_validation_step",
        "_run_finalization_step",
        "_repair_targets_now",
        "_repair_relations_now",
        "_repair_tags_from_asset_details",
    ):
        assert not hasattr(AssetSyncService, name)

    source = inspect.getsource(AssetSyncService)
    assert "_PacedCatalogSyncStep" not in source
    assert "_PacedAssetSyncStep" not in source
    assert "_PacedStackSyncStep" not in source
    assert "_PacedRelationshipSyncStep" not in source


def test_generic_manual_runtime_has_no_obsolete_v2_catalog_task() -> None:
    source = inspect.getsource(sync_runtime)

    assert "v2_sync_step_catalogs" not in source
    assert 'lane_key = "v2_sync"' not in source
    assert SyncStepTaskHandler.task_type == "sync_step"
    assert SyncStepTaskHandler.lane_key == "asset_sync"


def test_finalizing_resume_without_durable_evidence_fails_closed() -> None:
    now = datetime.now(UTC)
    run = SyncRunStatus(
        id="11111111-1111-4111-8111-111111111111",
        mode="incremental",
        status="running",
        phase="finalizing",
        generation=91,
        window_start=now - timedelta(minutes=10),
        window_end=now,
        cursor="generation-valid",
        counters={
            "album_strategy_asset_oriented": 1,
            "tag_strategy_asset_oriented": 1,
            "tag_strategy_asset_fallback": 0,
        },
        evidence=[],
        attempts=1,
        error=None,
        created_at=now,
        started_at=now,
        heartbeat_at=now,
        completed_at=None,
    )

    evidence = AssetSyncService._resume_evidence(run, 4)
    domains = {item.domain for item in evidence}

    assert {"albums", "tags", "assets", "stacks"} <= domains
    assert "album_memberships" not in domains
    assert "tag_memberships" not in domains
