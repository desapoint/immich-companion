"""Add reusable schedule dependency keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0010"
down_revision: str | None = "20260826_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("task_schedules", sa.Column("blocked_by", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE task_schedules
        SET blocked_by = CASE name
            WHEN 'asset-sync-incremental'
                THEN '["asset-sync:full", "schedule:asset-sync-full"]'::json
            ELSE '[]'::json
        END
        """
    )


def downgrade() -> None:
    op.drop_column("task_schedules", "blocked_by")
