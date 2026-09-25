"""Regression guards for the backend domain decomposition boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1] / "companion"


def test_extracted_duplicate_mixins_do_not_import_the_facade() -> None:
    for name in (
        "duplicate_contracts.py",
        "duplicate_evidence.py",
        "duplicate_resolution.py",
        "duplicate_review.py",
        "duplicate_scoring.py",
        "duplicate_workspace.py",
        "duplicate_task_handlers.py",
        "duplicate_routes.py",
    ):
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert "companion.duplicate_service" not in imports


def test_extracted_repository_modules_have_expected_owners() -> None:
    search = (ROOT / "asset_repository_search.py").read_text(encoding="utf-8")
    selection = (ROOT / "asset_repository_selection.py").read_text(encoding="utf-8")
    assert "class AssetSearchMixin" in search
    assert "class AssetSelectionMixin" in selection
    catalog = (ROOT / "asset_repository_catalog.py").read_text(encoding="utf-8")
    assert "class AssetCatalogRelationMixin" in catalog
    facade = (ROOT / "asset_repository.py").read_text(encoding="utf-8")
    assert (
        "class AssetRepository(AssetSearchMixin, AssetSelectionMixin, AssetCatalogRelationMixin)"
        in facade
    )


def test_route_registrars_own_domain_endpoints() -> None:
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    actions = (ROOT / "action_duplicate_routes.py").read_text(encoding="utf-8")
    duplicates = (ROOT / "duplicate_routes.py").read_text(encoding="utf-8")
    relations = (ROOT / "relation_routes.py").read_text(encoding="utf-8")
    media = (ROOT / "media_restore_routes.py").read_text(encoding="utf-8")
    assets = (ROOT / "asset_routes.py").read_text(encoding="utf-8")
    sync = (ROOT / "sync_settings_routes.py").read_text(encoding="utf-8")
    assert '"/api/assets/actions/plan"' in actions
    assert '"/api/assets/duplicates/cross-source/review"' in duplicates
    assert '"/api/assets/duplicates/cross-source"' in duplicates
    assert '"/api/assets/duplicates/cross-source/page"' in duplicates
    assert '"/api/assets/duplicates/history"' in duplicates
    assert '"/api/assets/duplicates/similarity-scan"' in duplicates
    assert '"/api/albums/manage"' in relations
    assert '"/api/restore"' in media
    assert '"/api/assets/{asset_id}/integrity"' in assets
    assert '"/api/assets/{asset_id}/integrity/analyze"' in assets
    assert '"/api/assets/sync"' in sync
    assert '"/api/settings/sync/runtime"' in sync
    assert '"/api/tasks/{task_id}/cancel"' in sync
    assert '"/api/assets/actions/plan"' not in main
    assert '"/api/assets/duplicates/cross-source/review"' not in main
    assert '"/api/albums/manage"' not in main
    assert '"/api/restore"' not in main
    assert '"/api/assets/sync"' not in main
    assert '"/api/settings/sync/runtime"' not in main
    assert '"/api/tasks/{task_id}/cancel"' not in main


def test_duplicate_facade_composes_extracted_runtime_owners() -> None:
    from companion.duplicate_evidence import DuplicateEvidenceMixin
    from companion.duplicate_review import DuplicateReviewMixin
    from companion.duplicate_service import CrossSourceDuplicateService
    from companion.duplicate_workspace import DuplicateWorkspaceMixin

    mro = CrossSourceDuplicateService.__mro__
    assert DuplicateEvidenceMixin in mro
    assert DuplicateReviewMixin in mro
    assert DuplicateWorkspaceMixin in mro


def test_neutral_similarity_helper_is_runtime_importable() -> None:
    from companion.duplicate_contracts import same_normalized_pixels

    assert same_normalized_pixels(None, None) is False


def test_task_subsystem_has_one_runtime_and_contract_owner() -> None:
    from companion import task_coordinator, task_schema
    from companion.tasks import contracts, coordinator
    from companion.v2 import task_coordinator as v2_coordinator
    from companion.v2 import task_schema as v2_schema

    assert not (ROOT / "v2" / "legacy_task_coordinator.py").exists()
    assert task_coordinator.TaskCoordinator is coordinator.TaskCoordinator
    assert v2_coordinator.TaskCoordinator is coordinator.TaskCoordinator
    assert task_schema.TaskStatusView is contracts.TaskStatusView
    assert v2_schema.TaskStatusView is contracts.TaskStatusView

    coordinator_source = (ROOT / "tasks" / "coordinator.py").read_text(encoding="utf-8")
    assert "class TaskRepository" not in coordinator_source
    assert "class TaskScheduler" not in coordinator_source
    assert "class TaskUpdateBroker" not in coordinator_source


def test_asset_sync_has_one_canonical_non_legacy_owner() -> None:
    facade = (ROOT / "asset_service.py").read_text(encoding="utf-8")
    sync_root = ROOT / "synchronization"

    assert not (ROOT / "v2" / "legacy_asset_service.py").exists()
    assert not (ROOT / "v2" / "sync_steps.py").exists()
    assert not (ROOT / "sync_steps.py").exists()
    assert (sync_root / "service.py").exists()
    assert (sync_root / "steps.py").exists()
    assert (sync_root / "batching.py").exists()
    assert "import *" not in facade
    assert "class AssetSyncService" not in facade

    from companion.asset_service import AssetSyncService
    from companion.synchronization.service import AssetSyncService as CanonicalService

    assert AssetSyncService is CanonicalService
