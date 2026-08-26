"""Add persisted cron expressions and disable automatic sync by default."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0009"
down_revision: str | None = "20260826_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("task_schedules", sa.Column("cron_expression", sa.String(128), nullable=True))
    op.execute(
        """
        UPDATE task_schedules
        SET enabled = false,
            interval_seconds = CASE name
                WHEN 'asset-sync-incremental' THEN 900
                WHEN 'asset-sync-full' THEN 604800
                ELSE interval_seconds
            END,
            cron_expression = CASE name
                WHEN 'asset-sync-incremental' THEN '*/15 * * * *'
                WHEN 'asset-sync-full' THEN '0 0 * * 0'
                ELSE cron_expression
            END
        WHERE name IN ('asset-sync-incremental', 'asset-sync-full')
        """
    )


def downgrade() -> None:
    op.drop_column("task_schedules", "cron_expression")
