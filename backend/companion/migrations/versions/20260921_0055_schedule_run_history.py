"""Track schedule-owned task starts.

Revision ID: 20260921_0055
Revises: 20260918_0054
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_0055"
down_revision = "20260918_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("schedule_name", sa.String(128), nullable=True),
    )
    op.create_index("ix_tasks_schedule_name", "tasks", ["schedule_name"])
    op.add_column(
        "task_schedules",
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Preserve the best available historical value. New executions use the
    # explicit schedule identity and update this field when work actually starts.
    op.execute(
        """
        UPDATE task_schedules AS schedule
        SET last_run_at = (
            SELECT task.started_at
            FROM tasks AS task
            WHERE task.task_type = schedule.task_type
              AND task.started_at IS NOT NULL
              AND task.payload::jsonb @> schedule.payload::jsonb
            ORDER BY task.started_at DESC
            LIMIT 1
        )
        """
    )


def downgrade() -> None:
    op.drop_column("task_schedules", "last_run_at")
    op.drop_index("ix_tasks_schedule_name", table_name="tasks")
    op.drop_column("tasks", "schedule_name")
