"""Persist versioned Companion similarity scan snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0026"
down_revision: str | Sequence[str] | None = "20260831_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "similarity_scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("comparison_version", sa.Integer(), nullable=False),
        sa.Column("similarity_threshold", sa.Float(), nullable=False),
        sa.Column("maximum_perceptual_distance", sa.Integer(), nullable=False),
        sa.Column("maximum_aspect_difference", sa.Float(), nullable=False),
        sa.Column("maximum_neighbors_per_asset", sa.Integer(), nullable=False),
        sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_similarity_scans_status", "similarity_scans", ["status"])
    op.create_index("ix_similarity_scans_created_at", "similarity_scans", ["created_at"])
    op.create_index("ix_similarity_scans_completed_at", "similarity_scans", ["completed_at"])
    op.create_table(
        "similarity_scan_pairs",
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id_low", sa.Uuid(), nullable=False),
        sa.Column("asset_id_high", sa.Uuid(), nullable=False),
        sa.Column("asset_low_source_sha256", sa.String(length=64), nullable=False),
        sa.Column("asset_high_source_sha256", sa.String(length=64), nullable=False),
        sa.Column("similarity_percent", sa.Float(), nullable=False),
        sa.Column("structural_percent", sa.Float(), nullable=False),
        sa.Column("perceptual_percent", sa.Float(), nullable=False),
        sa.Column("color_percent", sa.Float(), nullable=False),
        sa.Column("exact_thumbnail_match", sa.Boolean(), nullable=False),
        sa.Column("exact_pixel_match", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["similarity_scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id_low"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id_high"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scan_id", "asset_id_low", "asset_id_high"),
        sa.CheckConstraint(
            "asset_id_low <> asset_id_high",
            name="ck_similarity_scan_pair_distinct",
        ),
    )
    op.create_index(
        "ix_similarity_scan_pairs_assets",
        "similarity_scan_pairs",
        ["asset_id_low", "asset_id_high"],
    )


def downgrade() -> None:
    op.drop_index("ix_similarity_scan_pairs_assets", table_name="similarity_scan_pairs")
    op.drop_table("similarity_scan_pairs")
    op.drop_index("ix_similarity_scans_completed_at", table_name="similarity_scans")
    op.drop_index("ix_similarity_scans_created_at", table_name="similarity_scans")
    op.drop_index("ix_similarity_scans_status", table_name="similarity_scans")
    op.drop_table("similarity_scans")
