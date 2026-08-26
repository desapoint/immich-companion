"""Durable queue, singleton lease, and progress persistence for sync runs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from companion.database import DatabaseManager
from companion.models import SyncCoordinatorRecord, SyncRunRecord
from companion.sync_schema import SyncCoordinatorStatus, SyncMode, SyncProgress, SyncRunStatus


class SyncLeaseLostError(RuntimeError):
    """Raised when a worker no longer owns the durable coordinator lease."""


class SyncRepository:
    """Serialize sync intent and worker ownership through PostgreSQL rows."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def next_sync_metadata(
        self,
        mode: SyncMode,
        *,
        overlap: timedelta,
    ) -> tuple[int, datetime | None, datetime]:
        """Reserve durable sync metadata without owning execution or a lease."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            if state is None:
                state = SyncCoordinatorRecord(id=1)
                session.add(state)
                await session.flush()
            state.generation_counter += 1
            window_start = (
                state.successful_watermark - overlap
                if mode == "incremental" and state.successful_watermark
                else None
            )
            return state.generation_counter, window_start, now

    async def record_success(
        self,
        *,
        mode: SyncMode,
        generation: int,
        watermark: datetime,
    ) -> None:
        """Maintain legacy sync metadata as a read-compatible projection."""

        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            if state is None:
                state = SyncCoordinatorRecord(id=1)
                session.add(state)
            state.successful_watermark = watermark
            if mode == "full":
                state.authoritative_generation = generation

    @staticmethod
    def _public(record: SyncRunRecord | None) -> SyncRunStatus | None:
        if record is None:
            return None
        return SyncRunStatus(
            id=record.id,
            task_id=None,
            mode=record.mode,
            status=record.status,
            phase=record.phase,
            generation=record.generation,
            window_start=record.window_start,
            window_end=record.window_end,
            cursor=record.cursor,
            counters={
                str(key): int(value)
                for key, value in (record.counters or {}).items()
                if isinstance(value, int)
            },
            attempts=record.attempts,
            error=record.error,
            created_at=record.created_at,
            started_at=record.started_at,
            heartbeat_at=record.heartbeat_at,
            completed_at=record.completed_at,
            source="full" if record.mode == "full" else "window",
            progress=SyncProgress.model_validate(record.progress or {"phase": record.phase}),
        )

    async def enqueue(
        self,
        mode: SyncMode,
        *,
        overlap: timedelta,
        force_follow_up: bool = False,
    ) -> SyncRunStatus:
        """Coalesce routine requests and retain at most one queued follow-up."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            if state is None:
                state = SyncCoordinatorRecord(id=1)
                session.add(state)
                await session.flush()

            active = await session.get(SyncRunRecord, state.active_run_id)
            if active is not None and active.status in {"queued", "running", "recovering"}:
                should_follow = force_follow_up or (mode == "full" and active.mode != "full")
                if not should_follow:
                    public = self._public(active)
                    assert public is not None
                    return public
                pending = await session.get(SyncRunRecord, state.pending_run_id)
                if pending is not None:
                    if mode == "full" and pending.mode != "full":
                        pending.mode = "full"
                        pending.window_start = None
                    public = self._public(pending)
                    assert public is not None
                    return public
                state.generation_counter += 1
                pending = SyncRunRecord(
                    mode=mode,
                    status="queued",
                    phase="queued",
                    generation=state.generation_counter,
                    window_start=(
                        state.successful_watermark - overlap
                        if mode == "incremental" and state.successful_watermark
                        else None
                    ),
                    window_end=now,
                    counters={},
                    progress={"phase": "queued"},
                )
                session.add(pending)
                await session.flush()
                state.pending_run_id = pending.id
                public = self._public(pending)
                assert public is not None
                return public

            state.generation_counter += 1
            run = SyncRunRecord(
                mode=mode,
                status="queued",
                phase="queued",
                generation=state.generation_counter,
                window_start=(
                    state.successful_watermark - overlap
                    if mode == "incremental" and state.successful_watermark
                    else None
                ),
                window_end=now,
                counters={},
                progress={"phase": "queued"},
            )
            session.add(run)
            await session.flush()
            state.active_run_id = run.id
            state.pending_run_id = None
            public = self._public(run)
            assert public is not None
            return public

    async def claim_next(
        self,
        owner: UUID,
        *,
        lease_duration: timedelta,
    ) -> SyncRunStatus | None:
        """Claim the active run only when no unexpired owner exists."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            if state is None:
                return None
            if (
                state.lease_owner is not None
                and state.lease_owner != owner
                and state.lease_expires_at is not None
                and state.lease_expires_at > now
            ):
                return None

            run = await session.get(SyncRunRecord, state.active_run_id)
            if run is None or run.status in {"completed", "failed"}:
                state.active_run_id = state.pending_run_id
                state.pending_run_id = None
                run = await session.get(SyncRunRecord, state.active_run_id)
            if run is None:
                state.lease_owner = None
                state.lease_expires_at = None
                return None

            recovering = run.status in {"running", "recovering"}
            state.lease_owner = owner
            state.lease_expires_at = now + lease_duration
            run.owner_token = owner
            run.status = "recovering" if recovering else "running"
            run.phase = "catalogs" if run.phase == "queued" else run.phase
            run.started_at = run.started_at or now
            run.heartbeat_at = now
            run.attempts += 1
            run.error = None
            public = self._public(run)
            assert public is not None
            return public

    async def checkpoint(
        self,
        run_id: UUID,
        owner: UUID,
        *,
        phase: str,
        cursor: str | None,
        counters: dict[str, int],
        progress: SyncProgress | None = None,
        lease_duration: timedelta,
    ) -> SyncRunStatus:
        """Atomically renew ownership and persist the latest committed batch."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            run = await session.get(SyncRunRecord, run_id)
            if (
                state is None
                or run is None
                or state.active_run_id != run_id
                or state.lease_owner != owner
                or run.owner_token != owner
            ):
                raise SyncLeaseLostError("The staged sync lease is no longer owned")
            state.lease_expires_at = now + lease_duration
            run.status = "running"
            run.phase = phase
            run.cursor = cursor
            run.counters = dict(counters)
            if progress is not None:
                run.progress = progress.model_dump(mode="json")
            run.heartbeat_at = now
            public = self._public(run)
            assert public is not None
            return public

    async def heartbeat(
        self,
        run_id: UUID,
        owner: UUID,
        *,
        lease_duration: timedelta,
    ) -> None:
        """Renew a running lease independently of batch checkpoints."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            run = await session.get(SyncRunRecord, run_id)
            if (
                state is None
                or run is None
                or state.active_run_id != run_id
                or state.lease_owner != owner
                or run.owner_token != owner
                or run.status not in {"running", "recovering"}
            ):
                raise SyncLeaseLostError("The staged sync lease is no longer owned")
            state.lease_expires_at = now + lease_duration
            run.heartbeat_at = now

    async def complete(
        self,
        run_id: UUID,
        owner: UUID,
        *,
        counters: dict[str, int],
    ) -> SyncRunStatus:
        """Publish successful checkpoints and release the singleton lease."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            run = await session.get(SyncRunRecord, run_id)
            if (
                state is None
                or run is None
                or state.active_run_id != run_id
                or state.lease_owner != owner
            ):
                raise SyncLeaseLostError("The staged sync lease is no longer owned")
            run.status = "completed"
            run.phase = "completed"
            run.cursor = None
            run.counters = dict(counters)
            run.heartbeat_at = now
            run.completed_at = now
            state.successful_watermark = run.window_end
            if run.mode == "full":
                state.authoritative_generation = run.generation
            state.last_success_run_id = run.id
            state.active_run_id = state.pending_run_id
            state.pending_run_id = None
            state.lease_owner = None
            state.lease_expires_at = None
            public = self._public(run)
            assert public is not None
            return public

    async def fail(self, run_id: UUID, owner: UUID, error: Exception) -> None:
        """Persist a safe error and release ownership without finalizing absence."""

        now = datetime.now(UTC)
        async with self._database.sessions() as session, session.begin():
            state = await session.scalar(
                select(SyncCoordinatorRecord).where(SyncCoordinatorRecord.id == 1).with_for_update()
            )
            run = await session.get(SyncRunRecord, run_id)
            owns_run = (
                state is not None
                and run is not None
                and state.active_run_id == run_id
                and state.lease_owner == owner
                and run.owner_token == owner
            )
            if owns_run and run is not None:
                run.status = "failed"
                run.phase = "failed"
                run.error = type(error).__name__
                run.heartbeat_at = now
                run.completed_at = now
            if owns_run and state is not None:
                state.active_run_id = state.pending_run_id
                state.pending_run_id = None
                state.lease_owner = None
                state.lease_expires_at = None

    async def status(self) -> SyncCoordinatorStatus:
        """Return persisted status shared by every browser and process."""

        async with self._database.sessions() as session:
            state = await session.get(SyncCoordinatorRecord, 1)
            if state is None:
                return SyncCoordinatorStatus(
                    active=None,
                    pending=None,
                    last_success=None,
                    successful_watermark=None,
                    authoritative_generation=0,
                )
            active = await session.get(SyncRunRecord, state.active_run_id)
            pending = await session.get(SyncRunRecord, state.pending_run_id)
            last_success = await session.get(SyncRunRecord, state.last_success_run_id)
            return SyncCoordinatorStatus(
                active=self._public(active),
                pending=self._public(pending),
                last_success=self._public(last_success),
                successful_watermark=state.successful_watermark,
                authoritative_generation=state.authoritative_generation,
            )

    async def get_run(self, run_id: UUID) -> SyncRunStatus | None:
        """Return one persisted run for action-triggered waiters."""

        async with self._database.sessions() as session:
            return self._public(await session.get(SyncRunRecord, run_id))


def new_sync_owner() -> UUID:
    """Create an opaque worker ownership token."""

    return uuid4()
