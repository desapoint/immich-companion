"""Persist duplicate member decisions and workspace selection."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0030"
down_revision: str | Sequence[str] | None = "20260831_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "duplicate_group_reviews",
        sa.Column("member_decisions", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "duplicate_group_reviews",
        sa.Column("stack_primary_asset_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "duplicate_group_reviews",
        sa.Column("metadata_keeper_asset_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "duplicate_group_reviews",
        sa.Column("draft_status", sa.String(length=24), nullable=False, server_default="pending"),
    )
    op.create_table(
        "duplicate_review_workspaces",
        sa.Column("workspace_key", sa.String(length=32), nullable=False),
        sa.Column("selected_groups", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active_group", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("workspace_key"),
    )


def downgrade() -> None:
    op.drop_table("duplicate_review_workspaces")
    op.drop_column("duplicate_group_reviews", "draft_status")
    op.drop_column("duplicate_group_reviews", "metadata_keeper_asset_id")
    op.drop_column("duplicate_group_reviews", "stack_primary_asset_id")
    op.drop_column("duplicate_group_reviews", "member_decisions")
