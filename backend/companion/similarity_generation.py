"""One explicit generation boundary for durable Appearance discovery evidence.

Component-specific versions remain useful for describing the active pipeline, but
``SIMILARITY_EVIDENCE_CODE_GENERATION`` is the required broad compatibility handle:
bump it whenever fingerprint extraction, candidate selection, detailed validation,
comparison/scoring, or grouping semantics change in a way that can alter results.

The persisted runtime epoch is different. It is advanced by the user-facing rebuild
or destroy action. Long-running writers capture an epoch before doing external work and
verify that same epoch inside their commit transaction. This prevents work started before
an evidence boundary from repopulating evidence after it. The persisted descriptor is part
of that fence: a process from a different code generation may inspect status and perform
an evidence reset, but it may not produce durable evidence in an incompatible generation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from companion.database import DatabaseManager
from companion.models import TaskAttemptRecord, TaskLaneRecord, TaskRecord
from companion.task_coordinator import TaskCancelledError
from companion.v2.legacy_task_coordinator import TASK_UPDATE_CHANNEL

# Required broad compatibility kill-switch. Bump for any semantic Appearance-pipeline
# change that can alter fingerprints, candidates, validation, scores, or grouping.
SIMILARITY_EVIDENCE_CODE_GENERATION = 4

EVIDENCE_BOUND_TASK_TYPES = (
    "similarity_scan",
    "similarity_index",
    "similarity_maintenance",
    "composite_duplicate_rebuild",
)

_REPLACEMENT_SCAN_TASK_TYPE = "similarity_scan"
_REPLACEMENT_SCAN_LANE_KEY = "asset_integrity"
_REPLACEMENT_SCAN_PRIORITY = 45


class StaleSimilarityEvidenceEpochError(TaskCancelledError):
    """A writer crossed an evidence-generation boundary before it could commit."""


@dataclass(frozen=True, slots=True)
class SimilarityEvidenceGenerationState:
    epoch: int
    code_generation: int
    recorded_descriptor_fingerprint: str
    current_descriptor_fingerprint: str
    descriptor_current: bool
    rebuilt_at: datetime | None


@dataclass(frozen=True, slots=True)
class SimilarityEvidenceDestroyResult:
    state: SimilarityEvidenceGenerationState
    cancelled_task_count: int
    removed_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class SimilarityEvidenceRebuildResult(SimilarityEvidenceDestroyResult):
    task_id: UUID


def similarity_generation_descriptor() -> dict[str, object]:
    """Describe every code/config generation that can change Appearance evidence."""

    # Late imports intentionally avoid cycles: feature modules import the broad
    # generation constant above, while this diagnostic descriptor is evaluated only
    # after application module initialization.
    from companion.discovery import CANDIDATE_INDEX_VERSION
    from companion.similarity_bounded_state import (
        BOUNDED_CAPABILITY_VERSION,
        BOUNDED_POLICY_FINGERPRINT,
    )
    from companion.similarity_detail import DETAIL_FEATURE_VERSION
    from companion.similarity_grouping import SIMILARITY_GROUPING_VERSION
    from companion.similarity_repository import SIMILARITY_COMPARISON_VERSION
    from companion.similarity_search_features import (
        SEARCH_CONFIG_FINGERPRINT,
        SEARCH_FEATURE_VERSION,
        SEARCH_MODEL_VERSION,
    )

    return {
        "code_generation": SIMILARITY_EVIDENCE_CODE_GENERATION,
        "search": {
            "model": SEARCH_MODEL_VERSION,
            "feature": SEARCH_FEATURE_VERSION,
            "config": SEARCH_CONFIG_FINGERPRINT,
        },
        "detail": {"feature": DETAIL_FEATURE_VERSION},
        "comparison": {"version": SIMILARITY_COMPARISON_VERSION},
        "candidate_index": {"version": CANDIDATE_INDEX_VERSION},
        "grouping": {"version": SIMILARITY_GROUPING_VERSION},
        "bounded": {
            "capability": BOUNDED_CAPABILITY_VERSION,
            "policy": BOUNDED_POLICY_FINGERPRINT,
        },
    }


def similarity_generation_fingerprint() -> str:
    payload = json.dumps(
        similarity_generation_descriptor(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(payload, usedforsecurity=False).hexdigest()


def _scan_request_key(payload: dict[str, object]) -> str:
    """Match the coordinator dedupe key used by normal similarity-scan submission."""

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode(), usedforsecurity=False).hexdigest()


class SimilarityEvidenceEpochRepository:
    """Persist and enforce the runtime Appearance evidence generation boundary."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @staticmethod
    async def _ensure_state(
        session: AsyncSession, *, lock: bool
    ) -> tuple[int, int, str, datetime | None]:
        current_fingerprint = similarity_generation_fingerprint()
        await session.execute(
            text(
                "INSERT INTO similarity_evidence_state "
                "(id, epoch, code_generation, descriptor_fingerprint) "
                "VALUES (1, 1, :code_generation, :descriptor) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "code_generation": SIMILARITY_EVIDENCE_CODE_GENERATION,
                "descriptor": current_fingerprint,
            },
        )
        suffix = " FOR UPDATE" if lock else ""
        row = (
            await session.execute(
                text(
                    "SELECT epoch, code_generation, descriptor_fingerprint, rebuilt_at "
                    f"FROM similarity_evidence_state WHERE id = 1{suffix}"
                )
            )
        ).one()
        epoch, code_generation, descriptor, rebuilt_at = row
        if not descriptor:
            descriptor = current_fingerprint
            code_generation = SIMILARITY_EVIDENCE_CODE_GENERATION
            await session.execute(
                text(
                    "UPDATE similarity_evidence_state SET "
                    "code_generation = :code_generation, descriptor_fingerprint = :descriptor, "
                    "updated_at = now() WHERE id = 1"
                ),
                {
                    "code_generation": code_generation,
                    "descriptor": descriptor,
                },
            )
        return int(epoch), int(code_generation), str(descriptor), rebuilt_at

    async def status(self) -> SimilarityEvidenceGenerationState:
        async with self._database.sessions() as session, session.begin():
            epoch, code_generation, recorded, rebuilt_at = await self._ensure_state(
                session, lock=False
            )
        current = similarity_generation_fingerprint()
        return SimilarityEvidenceGenerationState(
            epoch=epoch,
            code_generation=code_generation,
            recorded_descriptor_fingerprint=recorded,
            current_descriptor_fingerprint=current,
            descriptor_current=(
                recorded == current
                and code_generation == SIMILARITY_EVIDENCE_CODE_GENERATION
            ),
            rebuilt_at=rebuilt_at,
        )

    async def capture_epoch(self) -> int:
        """Capture an epoch only when this process belongs to its code generation."""

        state = await self.status()
        if not state.descriptor_current:
            raise StaleSimilarityEvidenceEpochError(
                "Similarity evidence generation does not match this process; "
                "rebuild evidence before producing new durable results."
            )
        return state.epoch

    async def assert_current(self, session: AsyncSession, expected_epoch: int) -> None:
        """Hold a shared lock and fence both runtime epoch and code generation."""

        statement = text(
            "SELECT epoch, code_generation, descriptor_fingerprint "
            "FROM similarity_evidence_state WHERE id = 1 FOR SHARE"
        )
        row = (await session.execute(statement)).first()
        if row is None:
            await self._ensure_state(session, lock=False)
            row = (await session.execute(statement)).one()
        current_epoch = int(row[0])
        recorded_code_generation = int(row[1])
        recorded_descriptor = str(row[2])
        current_descriptor = similarity_generation_fingerprint()
        if current_epoch != expected_epoch:
            raise StaleSimilarityEvidenceEpochError(
                f"Similarity evidence epoch changed from {expected_epoch} to {current_epoch}."
            )
        if (
            recorded_code_generation != SIMILARITY_EVIDENCE_CODE_GENERATION
            or recorded_descriptor != current_descriptor
        ):
            raise StaleSimilarityEvidenceEpochError(
                "Similarity evidence generation does not match this process; "
                "the write belongs to an incompatible code generation."
            )

    async def _invalidate(
        self,
        session: AsyncSession,
        *,
        update_rebuilt_at: bool,
        reason_type: str,
        reason_message: str,
    ) -> tuple[int, dict[str, int]]:
        """Advance the epoch, retire writers, and delete all derived Appearance evidence."""

        current_descriptor = similarity_generation_fingerprint()
        removed: dict[str, int] = {}

        # Keep the historical advisory-lock key so destroy requests also serialize with
        # rebuilds issued by an older process during a rolling deployment.
        await session.execute(
            text(
                "SELECT pg_advisory_xact_lock(hashtext("
                "'immich-companion:similarity-evidence-rebuild'))"
            )
        )
        epoch, _code_generation, _recorded, _rebuilt_at = await self._ensure_state(
            session, lock=True
        )
        next_epoch = epoch + 1
        rebuilt_sql = ", rebuilt_at = now()" if update_rebuilt_at else ""
        await session.execute(
            text(
                "UPDATE similarity_evidence_state SET "
                "epoch = :epoch, code_generation = :code_generation, "
                f"descriptor_fingerprint = :descriptor{rebuilt_sql}, "
                "updated_at = now() WHERE id = 1"
            ),
            {
                "epoch": next_epoch,
                "code_generation": SIMILARITY_EVIDENCE_CODE_GENERATION,
                "descriptor": current_descriptor,
            },
        )

        # This is intentionally a hard task boundary instead of the normal cooperative
        # cancel transition. Revoking leases prevents an old worker from completing its
        # task record, while generation-guarded writes reject already-running stale work.
        cancelled = await session.execute(
            update(TaskRecord)
            .where(
                TaskRecord.task_type.in_(EVIDENCE_BOUND_TASK_TYPES),
                TaskRecord.status.in_(
                    (
                        "queued",
                        "running",
                        "retrying",
                        "recovering",
                        "pause_requested",
                        "paused",
                        "cancel_requested",
                    )
                ),
            )
            .values(
                status="cancelled",
                completed_at=func.now(),
                next_attempt_at=None,
                lease_owner=None,
                lease_expires_at=None,
            )
            .returning(TaskRecord.id)
        )
        cancelled_task_ids = list(cancelled.scalars().all())
        cancelled_task_count = len(cancelled_task_ids)

        if cancelled_task_ids:
            await session.execute(
                update(TaskAttemptRecord)
                .where(
                    TaskAttemptRecord.status == "running",
                    TaskAttemptRecord.task_id.in_(cancelled_task_ids),
                )
                .values(
                    status="cancelled",
                    completed_at=func.now(),
                    details={
                        "type": reason_type,
                        "message": reason_message,
                    },
                )
            )
            for task_id in cancelled_task_ids:
                await session.execute(
                    text("SELECT pg_notify(:channel, :payload)"),
                    {"channel": TASK_UPDATE_CHANNEL, "payload": str(task_id)},
                )

        # The composite duplicate projection is derived output. Remove it too so the UI
        # cannot keep displaying groups backed by invalidated similarity evidence. Review
        # decisions/history live in separate durable tables and are deliberately preserved.
        composite = await session.execute(text("DELETE FROM composite_duplicate_groups"))
        removed["composite_groups"] = int(composite.rowcount or 0)
        await session.execute(
            text(
                "UPDATE composite_duplicate_sync_state SET "
                "group_count = 0, member_count = 0, evidence_count = 0, "
                "last_success_at = NULL WHERE id = 1"
            )
        )

        for label, table_name in (
            ("scan_pairs", "similarity_scan_pairs"),
            ("scans", "similarity_scans"),
            ("pair_results", "asset_similarity_edges"),
            ("detail_features", "asset_similarity_detail_features"),
            ("bounded_state", "asset_similarity_bounded_state"),
            ("search_features", "asset_similarity_search_features"),
            ("pending_asset_changes", "similarity_asset_changes"),
        ):
            result = await session.execute(text(f"DELETE FROM {table_name}"))
            removed[label] = int(result.rowcount or 0)

        return cancelled_task_count, removed

    async def destroy(self) -> SimilarityEvidenceDestroyResult:
        """Invalidate all durable Appearance evidence without queuing replacement work."""

        async with self._database.sessions() as session, session.begin():
            cancelled_task_count, removed = await self._invalidate(
                session,
                update_rebuilt_at=False,
                reason_type="evidence_destroy",
                reason_message="Retired by similarity evidence destroy",
            )

        state = await self.status()
        return SimilarityEvidenceDestroyResult(
            state=state,
            cancelled_task_count=cancelled_task_count,
            removed_counts=removed,
        )

    async def rebuild(
        self, scan_payload: dict[str, object]
    ) -> SimilarityEvidenceRebuildResult:
        """Invalidate evidence and durably queue its replacement in one transaction."""

        if not scan_payload:
            raise ValueError("A replacement similarity scan payload is required")
        replacement_task_id = uuid4()
        replacement_dedupe_key = _scan_request_key(scan_payload)
        async with self._database.sessions() as session, session.begin():
            cancelled_task_count, removed = await self._invalidate(
                session,
                update_rebuilt_at=True,
                reason_type="evidence_rebuild",
                reason_message="Retired by similarity evidence rebuild",
            )

            # The replacement scan is created before the destructive transaction can
            # commit. If task creation fails, the epoch advance and every deletion roll
            # back with it. A lost HTTP response or closed browser therefore cannot leave
            # the library with invalidated evidence and no durable rebuild work.
            lane_statement = insert(TaskLaneRecord).values(
                lane_key=_REPLACEMENT_SCAN_LANE_KEY,
                max_concurrency=1,
            )
            await session.execute(
                lane_statement.on_conflict_do_update(
                    index_elements=[TaskLaneRecord.lane_key],
                    set_={
                        "max_concurrency": func.greatest(
                            TaskLaneRecord.max_concurrency,
                            lane_statement.excluded.max_concurrency,
                        ),
                        "updated_at": func.now(),
                    },
                )
            )
            await session.execute(
                insert(TaskRecord).values(
                    id=replacement_task_id,
                    task_type=_REPLACEMENT_SCAN_TASK_TYPE,
                    payload=scan_payload,
                    priority=_REPLACEMENT_SCAN_PRIORITY,
                    status="queued",
                    deduplication_key=replacement_dedupe_key,
                    lane_key=_REPLACEMENT_SCAN_LANE_KEY,
                    checkpoint={},
                    counters={},
                    progress={},
                    attempt=0,
                    next_attempt_at=datetime.now(UTC),
                )
            )
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": TASK_UPDATE_CHANNEL, "payload": str(replacement_task_id)},
            )

        state = await self.status()
        return SimilarityEvidenceRebuildResult(
            state=state,
            cancelled_task_count=cancelled_task_count,
            removed_counts=removed,
            task_id=replacement_task_id,
        )
