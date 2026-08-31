"""Persist sparse, versioned visual similarity edges."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0024"
down_revision: str | Sequence[str] | None = "20260830_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_similarity_edges",
        sa.Column("asset_id_low", sa.Uuid(), nullable=False),
        sa.Column("asset_id_high", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("comparison_version", sa.Integer(), nullable=False),
        sa.Column("asset_low_source_sha256", sa.String(length=64), nullable=False),
        sa.Column("asset_high_source_sha256", sa.String(length=64), nullable=False),
        sa.Column("similarity_percent", sa.Float(), nullable=False),
        sa.Column("structural_percent", sa.Float(), nullable=False),
        sa.Column("perceptual_percent", sa.Float(), nullable=False),
        sa.Column("color_percent", sa.Float(), nullable=False),
        sa.Column("exact_thumbnail_match", sa.Boolean(), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("asset_id_low <> asset_id_high", name="ck_similarity_edge_distinct"),
        sa.ForeignKeyConstraint(["asset_id_low"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id_high"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint(
            "asset_id_low",
            "asset_id_high",
            "model_version",
            "feature_version",
            "comparison_version",
        ),
    )
    op.create_index(
        "ix_asset_similarity_edges_version",
        "asset_similarity_edges",
        ["model_version", "feature_version", "comparison_version"],
    )
    op.create_index(
        "ix_asset_similarity_edges_calculated_at",
        "asset_similarity_edges",
        ["calculated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_similarity_edges_calculated_at",
        table_name="asset_similarity_edges",
    )
    op.drop_index(
        "ix_asset_similarity_edges_version",
        table_name="asset_similarity_edges",
    )
    op.drop_table("asset_similarity_edges")
