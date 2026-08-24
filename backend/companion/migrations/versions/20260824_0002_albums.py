"""Create synchronized albums and membership tables.

Revision ID: 20260824_0002
Revises: 20260824_0001
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0002"
down_revision: str | None = "20260824_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create companion-owned album metadata and current memberships."""

    op.create_table(
        "albums",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("album_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("album_thumbnail_asset_id", sa.Uuid(), nullable=True),
        sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("immich_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("immich_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_albums_album_name", "albums", ["album_name"])
    op.create_index("ix_albums_synced_at", "albums", ["synced_at"])
    op.create_table(
        "album_assets",
        sa.Column("album_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["album_id"], ["albums.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("album_id", "asset_id"),
    )
    op.create_index("ix_album_assets_asset_id", "album_assets", ["asset_id"])


def downgrade() -> None:
    """Remove synchronized album metadata."""

    op.drop_table("album_assets")
    op.drop_table("albums")
