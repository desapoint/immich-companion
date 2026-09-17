"""Regression coverage for destroy-only similarity evidence invalidation."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

import companion.similarity_generation as generation_module
from companion.similarity_generation import (
    SimilarityEvidenceEpochRepository,
    similarity_generation_fingerprint,
)


class _Result:
    def __init__(self, *, row=None, rowcount: int = 0) -> None:
        self._row = row
        self.rowcount = rowcount

    def one(self):
        if self._row is None:
            raise AssertionError("Expected one row")
        return self._row

    def first(self):
        return self._row


class _Session:
    def __init__(self, database: _Database) -> None:
        self.database = database

    @asynccontextmanager
    async def begin(self):
        yield self

    async def execute(self, statement, parameters=None):
        sql = str(statement)
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
        if "UPDATE tasks SET status = 'cancelled'" in sql:
            self.database.task_update_sql = sql
            return _Result(rowcount=4)
        if sql.lstrip().startswith("DELETE FROM"):
            return _Result(rowcount=1)
        return _Result(rowcount=1)


class _Database:
    def __init__(self) -> None:
        self.epoch = 1
        self.code_generation = generation_module.SIMILARITY_EVIDENCE_CODE_GENERATION
        self.descriptor = similarity_generation_fingerprint()
        self.statements: list[str] = []
        self.task_update_sql = ""

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
    assert "status = 'cancelled'" in database.task_update_sql
    assert "lease_owner = NULL" in database.task_update_sql
    assert "composite_duplicate_rebuild" in database.task_update_sql
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
