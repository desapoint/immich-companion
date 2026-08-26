"""Persist phase-aware synchronization progress."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0007"
down_revision: str | None = "20260826_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add structured progress alongside existing sync counters."""

    op.add_column(
        "sync_runs",
        sa.Column("progress", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    """Remove structured sync progress."""

    op.drop_column("sync_runs", "progress")
