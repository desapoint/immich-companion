"""Persist compact per-asset visual similarity features."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0023"
down_revision: str | Sequence[str] | None = "20260830_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_similarity_features",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("source_file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("luminance_vector", sa.LargeBinary(), nullable=False),
        sa.Column("perceptual_hash", sa.String(length=16), nullable=False),
        sa.Column("color_histogram", sa.LargeBinary(), nullable=False),
        sa.Column("thumbnail_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        "ix_asset_similarity_features_version",
        "asset_similarity_features",
        ["model_version", "feature_version"],
    )
    op.create_index(
        "ix_asset_similarity_features_analyzed_at",
        "asset_similarity_features",
        ["analyzed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_similarity_features_analyzed_at",
        table_name="asset_similarity_features",
    )
    op.drop_index(
        "ix_asset_similarity_features_version",
        table_name="asset_similarity_features",
    )
    op.drop_table("asset_similarity_features")
