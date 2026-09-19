"""Similarity evidence generation and rebuild boundary regressions."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

import companion.similarity_generation as generation_module
import companion.similarity_repository as repository_module
from companion.similarity_generation import (
    SimilarityEvidenceEpochRepository,
    StaleSimilarityEvidenceEpochError,
    similarity_generation_fingerprint,
)
from companion.similarity_repository import SimilarityRepository, _pair_config_fingerprint
from companion.similarity_scan_service import _epoch_kwargs
from companion.task_coordinator import TaskCancelledError


class _ScalarRows:
    def __init__(self, values: list[UUID]) -> None:
        self._values = values

    def all(self) -> list[UUID]:
        return self._values


class _Result:
    def __init__(
        self,
        *,
        row=None,
        rowcount: int = 0,
        scalar_rows: list[UUID] | None = None,
    ) -> None:
        self._row = row
        self.rowcount = rowcount
        self._scalar_rows = scalar_rows or []

    def one(self):
        if self._row is None:
            raise AssertionError("Expected one row")
        return self._row

    def first(self):
        return self._row

    def scalars(self) -> _ScalarRows:
        return _ScalarRows(self._scalar_rows)


class _EpochSession:
    def __init__(self, database: _EpochDatabase) -> None:
        self.database = database

    @asynccontextmanager
    async def begin(self):
        yield self

    async def execute(self, statement, parameters=None):
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        parameters = parameters or {}
        self.database.statements.append(sql)
        if "SELECT epoch, code_generation, descriptor_fingerprint, rebuilt_at" in sql:
            return _Result(
                row=(
                    self.database.epoch,
                    self.database.code_generation,
                    self.database.descriptor,
                    self.database.rebuilt_at,
                )
            )
        if "SELECT epoch, code_generation, descriptor_fingerprint" in sql:
            return _Result(
                row=(
                    self.database.epoch,
                    self.database.code_generation,
                    self.database.descriptor,
                )
            )
        if "UPDATE similarity_evidence_state SET" in sql:
            if "epoch" in parameters:
                self.database.epoch = int(parameters["epoch"])
            if "code_generation" in parameters:
                self.database.code_generation = int(parameters["code_generation"])
            if "descriptor" in parameters:
                self.database.descriptor = str(parameters["descriptor"])
            return _Result(rowcount=1)
        if sql.lstrip().startswith("UPDATE tasks SET"):
            self.database.task_update_sql = sql
            self.database.task_update_parameters = {
                **dict(compiled.params),
                **dict(parameters),
            }
            return _Result(
                rowcount=len(self.database.cancelled_task_ids),
                scalar_rows=self.database.cancelled_task_ids,
            )
        if sql.lstrip().startswith("UPDATE task_attempts SET"):
            self.database.attempt_update_sql = sql
            self.database.attempt_update_parameters = {
                **dict(compiled.params),
                **dict(parameters),
            }
            return _Result(rowcount=len(self.database.cancelled_task_ids))
        if "INSERT INTO tasks" in sql:
            self.database.queued_task_parameters = {
                **dict(compiled.params),
                **dict(parameters),
            }
            return _Result(rowcount=1)
        if sql.lstrip().startswith("DELETE FROM"):
            return _Result(rowcount=1)
        return _Result(rowcount=1)


class _EpochDatabase:
    def __init__(self) -> None:
        self.epoch = 1
        self.code_generation = generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION
        self.descriptor = similarity_generation_fingerprint()
        self.rebuilt_at = None
        self.statements: list[str] = []
        self.cancelled_task_ids = [UUID(int=value) for value in range(101, 105)]
        self.task_update_sql = ""
        self.task_update_parameters: dict[str, object] = {}
        self.attempt_update_sql = ""
        self.attempt_update_parameters: dict[str, object] = {}
        self.queued_task_parameters: dict[str, object] | None = None

    @asynccontextmanager
    async def sessions(self):
        yield _EpochSession(self)


def _scan_payload() -> dict[str, object]:
    return {
        "similarity_threshold": 95.0,
        "validation_mode": "strict",
        "anchor_asset_id": None,
        "scope": "all_eligible_assets",
        "maximum_perceptual_distance": 12,
        "maximum_aspect_difference": 0.05,
        "maximum_neighbors_per_asset": 32,
        "maximum_matches": 5000,
    }


def test_generation_descriptor_contains_only_current_appearance_pipeline() -> None:
    descriptor = generation_module.similarity_generation_descriptor()

    assert "search" in descriptor
    assert "detail" in descriptor
    assert "comparison" in descriptor
    assert "legacy_visual" not in descriptor


def test_broad_generation_changes_generation_and_pair_fingerprints(monkeypatch) -> None:
    generation_before = similarity_generation_fingerprint()
    pair_before = _pair_config_fingerprint("feature-config")

    monkeypatch.setattr(
        generation_module,
        "SIMILARITY_EVIDENCE_CODE_GENERATION",
        generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION + 1,
    )
    monkeypatch.setattr(
        repository_module,
        "SIMILARITY_EVIDENCE_CODE_GENERATION",
        repository_module.SIMILARITY_EVIDENCE_CODE_GENERATION + 1,
    )

    assert similarity_generation_fingerprint() != generation_before
    assert _pair_config_fingerprint("feature-config") != pair_before


def test_hot_pair_key_is_scoped_to_runtime_epoch() -> None:
    left = SimpleNamespace(source_identity="left", config_fingerprint="config")
    right = SimpleNamespace(source_identity="right", config_fingerprint="config")

    first = SimilarityRepository._hot_key(  # type: ignore[arg-type]
        SimpleNamespace(int=1),
        SimpleNamespace(int=2),
        left,
        right,
        1,
        0,
    )
    second = SimilarityRepository._hot_key(  # type: ignore[arg-type]
        SimpleNamespace(int=1),
        SimpleNamespace(int=2),
        left,
        right,
        2,
        0,
    )

    assert first != second


@pytest.mark.asyncio
async def test_capture_epoch_rejects_process_from_different_generation() -> None:
    database = _EpochDatabase()
    database.descriptor = "0" * 64
    repository = SimilarityEvidenceEpochRepository(database)  # type: ignore[arg-type]

    with pytest.raises(StaleSimilarityEvidenceEpochError, match="does not match this process"):
        await repository.capture_epoch()


@pytest.mark.asyncio
async def test_assert_current_raises_task_cancellation_for_stale_epoch() -> None:
    class Session:
        async def execute(self, _statement):
            return _Result(
                row=(
                    2,
                    generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION,
                    similarity_generation_fingerprint(),
                )
            )

    repository = SimilarityEvidenceEpochRepository(SimpleNamespace())  # type: ignore[arg-type]

    with pytest.raises(StaleSimilarityEvidenceEpochError, match="changed from 1 to 2"):
        await repository.assert_current(Session(), 1)  # type: ignore[arg-type]

    assert issubclass(StaleSimilarityEvidenceEpochError, TaskCancelledError)


@pytest.mark.asyncio
async def test_assert_current_rejects_same_epoch_from_different_generation() -> None:
    class Session:
        async def execute(self, _statement):
            return _Result(
                row=(
                    1,
                    generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION,
                    "f" * 64,
                )
            )

    repository = SimilarityEvidenceEpochRepository(SimpleNamespace())  # type: ignore[arg-type]

    with pytest.raises(StaleSimilarityEvidenceEpochError, match="incompatible code generation"):
        await repository.assert_current(Session(), 1)  # type: ignore[arg-type]


def test_epoch_keyword_is_only_sent_to_epoch_aware_adapters() -> None:
    async def legacy(_value):
        return None

    async def current(_value, *, evidence_epoch=None):
        return evidence_epoch

    assert _epoch_kwargs(legacy, 7) == {}
    assert _epoch_kwargs(current, 7) == {"evidence_epoch": 7}
    assert _epoch_kwargs(current, None) == {}


@pytest.mark.asyncio
async def test_rebuild_advances_epoch_and_atomically_queues_replacement_scan() -> None:
    database = _EpochDatabase()
    repository = SimilarityEvidenceEpochRepository(database)  # type: ignore[arg-type]
    scan_payload = _scan_payload()

    result = await repository.rebuild(scan_payload)

    assert result.state.epoch == 2
    assert result.state.descriptor_current is True
    assert result.cancelled_task_count == 4
    assert database.task_update_sql.startswith("UPDATE tasks SET")
    assert database.task_update_parameters["status"] == "cancelled"
    assert database.task_update_parameters["lease_owner"] is None
    assert database.task_update_parameters["lease_expires_at"] is None
    assert database.attempt_update_sql.startswith("UPDATE task_attempts SET")
    assert "json_build_object" not in database.attempt_update_sql
    assert "::JSON" in database.attempt_update_sql
    assert database.attempt_update_parameters["status"] == "cancelled"
    assert database.attempt_update_parameters["details"] == {
        "type": "evidence_rebuild",
        "message": "Retired by similarity evidence rebuild",
    }
    assert any("INSERT INTO task_lanes" in sql for sql in database.statements)
    assert any("INSERT INTO tasks" in sql for sql in database.statements)
    assert database.queued_task_parameters is not None
    assert database.queued_task_parameters["task_type"] == "similarity_scan"
    assert database.queued_task_parameters["payload"] == scan_payload
    assert database.queued_task_parameters["id"] == result.task_id
    assert result.removed_counts == {
        "composite_groups": 1,
        "scan_pairs": 1,
        "scans": 1,
    }
    projection_sql = "\n".join(database.statements)
    assert "companion_similarity" in projection_sql
    assert "immich_duplicate" in projection_sql
    assert "similarity_score = NULL" in projection_sql
    assert "last_success_at = NULL" in projection_sql
    assert not any("DELETE FROM asset_similarity_edges" in sql for sql in database.statements)
    assert not any(
        "DELETE FROM asset_similarity_detail_features" in sql
        for sql in database.statements
    )
    assert not any(
        "DELETE FROM asset_similarity_search_features" in sql
        for sql in database.statements
    )
    assert not any("DELETE FROM similarity_asset_changes" in sql for sql in database.statements)


@pytest.mark.asyncio
async def test_destroy_uses_typed_json_for_cancelled_attempt_details() -> None:
    database = _EpochDatabase()
    repository = SimilarityEvidenceEpochRepository(database)  # type: ignore[arg-type]

    result = await repository.destroy()

    assert result.cancelled_task_count == 4
    assert database.attempt_update_parameters["details"] == {
        "type": "evidence_destroy",
        "message": "Retired by similarity evidence destroy",
    }
    assert "json_build_object" not in database.attempt_update_sql
    assert "::JSON" in database.attempt_update_sql
    assert result.removed_counts == {
        "composite_groups": 1,
        "scan_pairs": 1,
        "scans": 1,
        "pair_results": 1,
        "detail_features": 1,
        "bounded_state": 1,
        "search_features": 1,
        "pending_asset_changes": 1,
    }


@pytest.mark.asyncio
async def test_rebuild_recovers_an_incompatible_recorded_generation() -> None:
    database = _EpochDatabase()
    database.code_generation = generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION - 1
    database.descriptor = "0" * 64
    repository = SimilarityEvidenceEpochRepository(database)  # type: ignore[arg-type]

    result = await repository.rebuild(_scan_payload())

    assert result.state.descriptor_current is True
    assert result.state.code_generation == generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION
    assert database.queued_task_parameters is not None
    assert database.queued_task_parameters["task_type"] == "similarity_scan"


@pytest.mark.asyncio
async def test_rebuild_requires_replacement_scan_before_destructive_work() -> None:
    database = _EpochDatabase()
    repository = SimilarityEvidenceEpochRepository(database)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="replacement similarity scan payload"):
        await repository.rebuild({})

    assert database.statements == []
