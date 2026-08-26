"""Add server-owned scalable selection sets."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0011"
down_revision: str | None = "20260826_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "selection_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selected_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_selection_sets_status", "selection_sets", ["status"])
    op.create_index("ix_selection_sets_expires_at", "selection_sets", ["expires_at"])
    op.create_table(
        "selection_set_members",
        sa.Column("selection_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["selection_id"], ["selection_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("selection_id", "asset_id"),
    )
    op.create_index("ix_selection_set_members_asset_id", "selection_set_members", ["asset_id"])


def downgrade() -> None:
    op.drop_table("selection_set_members")
    op.drop_table("selection_sets")
