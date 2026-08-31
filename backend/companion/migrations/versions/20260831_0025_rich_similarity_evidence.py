"""Persist normalized-pixel identity and compact preservation evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0025"
down_revision: str | Sequence[str] | None = "20260830_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "asset_similarity_features"
    op.add_column(
        table,
        sa.Column("pixel_normalization_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        table, sa.Column("pixel_sha256", sa.String(length=64), nullable=False, server_default="")
    )
    op.add_column(table, sa.Column("bit_depth", sa.Integer(), nullable=False, server_default="8"))
    op.add_column(
        table, sa.Column("channel_count", sa.Integer(), nullable=False, server_default="3")
    )
    op.add_column(
        table, sa.Column("has_alpha", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        table,
        sa.Column("color_space", sa.String(length=24), nullable=False, server_default="unknown"),
    )
    op.add_column(table, sa.Column("orientation", sa.Integer(), nullable=True))
    op.add_column(
        table,
        sa.Column("icc_profile_present", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        table, sa.Column("has_exif", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        table,
        sa.Column("has_capture_time", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        table, sa.Column("has_camera_info", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        table, sa.Column("has_gps", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        table,
        sa.Column(
            "has_orientation_metadata", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        table, sa.Column("metadata_richness", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_index("ix_asset_similarity_features_pixel_sha256", table, ["pixel_sha256"])
    op.add_column(
        "asset_similarity_edges",
        sa.Column("exact_pixel_match", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("asset_similarity_edges", "exact_pixel_match")
    table = "asset_similarity_features"
    op.drop_index("ix_asset_similarity_features_pixel_sha256", table_name=table)
    for column in (
        "metadata_richness",
        "has_orientation_metadata",
        "has_gps",
        "has_camera_info",
        "has_capture_time",
        "has_exif",
        "icc_profile_present",
        "orientation",
        "color_space",
        "has_alpha",
        "channel_count",
        "bit_depth",
        "pixel_sha256",
        "pixel_normalization_version",
    ):
        op.drop_column(table, column)
