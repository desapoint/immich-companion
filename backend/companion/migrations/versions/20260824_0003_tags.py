"""Create synchronized tags and membership tables.

Revision ID: 20260824_0003
Revises: 20260824_0002
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0003"
down_revision: str | None = "20260824_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create companion-owned tag metadata and current memberships."""

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tag_name", sa.Text(), nullable=False),
        sa.Column("tag_value", sa.Text(), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tags_tag_name", "tags", ["tag_name"])
    op.create_index("ix_tags_synced_at", "tags", ["synced_at"])
    op.create_table(
        "tag_assets",
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tag_id", "asset_id"),
    )
    op.create_index("ix_tag_assets_asset_id", "tag_assets", ["asset_id"])


def downgrade() -> None:
    """Remove synchronized tag metadata."""

    op.drop_table("tag_assets")
    op.drop_table("tags")
