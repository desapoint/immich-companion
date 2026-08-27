"""Persist user-editable global-sync pacing settings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0012"
down_revision: str | Sequence[str] | None = "20260826_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_runtime_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_batch_size", sa.Integer(), nullable=False),
        sa.Column("full_min_batch_delay_seconds", sa.Float(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sync_runtime_settings")
