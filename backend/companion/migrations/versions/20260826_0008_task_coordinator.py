"""Add generic PostgreSQL-backed task coordination state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0008"
down_revision: str | None = "20260826_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create generic task, lease, attempt, event, lane, and schedule tables."""

    op.create_table(
        "task_lanes",
        sa.Column("lane_key", sa.String(128), primary_key=True),
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("deduplication_key", sa.String(255), nullable=True),
        sa.Column("lane_key", sa.String(128), nullable=False),
        sa.Column("checkpoint", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("counters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("progress", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in {
        "ix_tasks_task_type": ["task_type"],
        "ix_tasks_priority": ["priority"],
        "ix_tasks_status": ["status"],
        "ix_tasks_lane_key": ["lane_key"],
        "ix_tasks_next_attempt_at": ["next_attempt_at"],
        "ix_tasks_lease_owner": ["lease_owner"],
        "ix_tasks_lease_expires_at": ["lease_expires_at"],
        "ix_tasks_created_at": ["created_at"],
        "ix_tasks_claimable": ["status", "next_attempt_at", "priority", "created_at"],
        "ix_tasks_dedupe": ["task_type", "deduplication_key", "status"],
    }.items():
        op.create_index(name, "tasks", columns)

    op.create_table(
        "task_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_attempts_task_id", "task_attempts", ["task_id"])
    op.create_index("ix_task_attempts_status", "task_attempts", ["status"])
    op.create_table(
        "task_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])
    op.create_index("ix_task_events_kind", "task_events", ["kind"])
    op.create_index("ix_task_events_created_at", "task_events", ["created_at"])
    op.create_table(
        "task_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deduplication_policy", sa.String(32), nullable=False, server_default="window"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_task_schedules_name", "task_schedules", ["name"])
    op.create_index("ix_task_schedules_enabled", "task_schedules", ["enabled"])
    op.create_index("ix_task_schedules_next_run_at", "task_schedules", ["next_run_at"])

    op.execute(
        "INSERT INTO task_lanes (lane_key, max_concurrency) VALUES "
        "('asset_sync', 1), ('asset_repair', 4)"
    )

    # Existing active sync run IDs become generic task IDs, preserving their
    # phase/cursor/counters as the first checkpoint for restart recovery.
    op.execute(
        """
        INSERT INTO tasks (
            id, task_type, payload, priority, status, deduplication_key, lane_key,
            checkpoint, counters, progress, attempt, next_attempt_at, created_at,
            started_at, heartbeat_at, completed_at, error
        )
        SELECT id, 'asset_sync',
            json_build_object(
                'mode', mode, 'generation', generation,
                'window_start', window_start, 'window_end', window_end,
                'legacy_run_id', id
            ),
            CASE WHEN mode = 'full' THEN 100 ELSE 10 END,
            CASE WHEN status = 'retrying' THEN 'retrying'
                 WHEN status IN ('running', 'recovering') THEN 'recovering'
                 ELSE status END,
            'legacy-sync-' || id::text, 'asset_sync',
            json_build_object('phase', phase, 'cursor', cursor), counters,
            progress, attempts, NULL, created_at, started_at, heartbeat_at,
            completed_at,
            CASE WHEN error IS NULL THEN NULL ELSE
                json_build_object('type', 'legacy', 'message', error) END
        FROM sync_runs
        WHERE status IN ('queued', 'running', 'recovering', 'retrying')
        """
    )


def downgrade() -> None:
    """Remove generic task coordination state."""

    op.drop_table("task_schedules")
    op.drop_table("task_events")
    op.drop_table("task_attempts")
    op.drop_table("tasks")
    op.drop_table("task_lanes")
