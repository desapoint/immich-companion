"""Regression coverage for destroy-only similarity evidence invalidation."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

import companion.similarity_generation as generation_module
from companion.similarity_generation import (
    SimilarityEvidenceEpochRepository,
    similarity_generation_fingerprint,
)


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


class _Session:
    def __init__(self, database: _Database) -> None:
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
                    None,
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
        if sql.lstrip().startswith("DELETE FROM"):
            return _Result(rowcount=1)
        return _Result(rowcount=1)


class _Database:
    def __init__(self) -> None:
        self.epoch = 1
        self.code_generation = generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION
        self.descriptor = similarity_generation_fingerprint()
        self.statements: list[str] = []
        self.cancelled_task_ids = [UUID(int=value) for value in range(101, 105)]
        self.task_update_sql = ""
        self.task_update_parameters: dict[str, object] = {}
        self.attempt_update_sql = ""
        self.attempt_update_parameters: dict[str, object] = {}

    @asynccontextmanager
    async def sessions(self):
        yield _Session(self)


@pytest.mark.asyncio
async def test_destroy_advances_epoch_and_never_queues_replacement_scan() -> None:
    database = _Database()
    repository = SimilarityEvidenceEpochRepository(database)  # type: ignore[arg-type]

    result = await repository.destroy()

    assert result.state.epoch == 2
    assert result.state.descriptor_current is True
    assert result.cancelled_task_count == 4
    assert database.task_update_sql.startswith("UPDATE tasks SET")
    assert database.task_update_parameters["status"] == "cancelled"
    assert database.task_update_parameters["lease_owner"] is None
    assert database.attempt_update_sql.startswith("UPDATE task_attempts SET")
    assert database.attempt_update_parameters["details"] == {
        "type": "evidence_destroy",
        "message": "Retired by similarity evidence destroy",
    }
    assert not any("INSERT INTO task_lanes" in sql for sql in database.statements)
    assert not any("INSERT INTO tasks" in sql for sql in database.statements)
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
