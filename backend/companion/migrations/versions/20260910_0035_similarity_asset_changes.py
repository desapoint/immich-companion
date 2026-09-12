"""Add the coalesced incremental similarity change queue."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0035"
down_revision: str | Sequence[str] | None = "20260910_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "similarity_asset_changes",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        "ix_similarity_asset_changes_enqueued_at",
        "similarity_asset_changes",
        ["enqueued_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_similarity_asset_changes_enqueued_at",
        table_name="similarity_asset_changes",
    )
    op.drop_table("similarity_asset_changes")
