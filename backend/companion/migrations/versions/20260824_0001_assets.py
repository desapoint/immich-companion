"""Create synchronized assets table.

Revision ID: 20260824_0001
Revises:
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the first companion-owned searchable asset index."""

    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("library_id", sa.Uuid(), nullable=True),
        sa.Column("asset_type", sa.String(length=24), nullable=False),
        sa.Column("original_file_name", sa.Text(), nullable=False),
        sa.Column("original_path", sa.Text(), nullable=True),
        sa.Column("original_mime_type", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration", sa.BigInteger(), nullable=True),
        sa.Column("thumbhash", sa.Text(), nullable=True),
        sa.Column("file_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_date_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("immich_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("immich_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_trashed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_offline", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_metadata", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("visibility", sa.String(length=32), nullable=True),
        sa.Column("live_photo_video_id", sa.String(length=64), nullable=True),
        sa.Column("exif_info", sa.JSON(), nullable=True),
        sa.Column("people", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("stack", sa.JSON(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_owner_id", "assets", ["owner_id"])
    op.create_index("ix_assets_library_id", "assets", ["library_id"])
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"])
    op.create_index("ix_assets_checksum", "assets", ["checksum"])
    op.create_index("ix_assets_file_created_at", "assets", ["file_created_at"])
    op.create_index("ix_assets_is_favorite", "assets", ["is_favorite"])
    op.create_index("ix_assets_is_archived", "assets", ["is_archived"])
    op.create_index("ix_assets_is_trashed", "assets", ["is_trashed"])
    op.create_index("ix_assets_visibility", "assets", ["visibility"])
    op.create_index("ix_assets_synced_at", "assets", ["synced_at"])
    op.create_index(
        "ix_assets_original_file_name_lower",
        "assets",
        [sa.text("lower(original_file_name)")],
    )
    op.create_index("ix_assets_dimensions", "assets", ["width", "height"])


def downgrade() -> None:
    """Remove the synchronized asset index."""

    op.drop_table("assets")
