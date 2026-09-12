"""Separate preview search evidence from original verification evidence.

Revision ID: 20260912_0040
Revises: 20260911_0039
"""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0040"
down_revision = "20260911_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_similarity_search_features",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source_checksum", sa.Text(), nullable=True),
        sa.Column("source_identity", sa.String(length=64), nullable=False),
        sa.Column("preview_sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("luminance_vector", sa.LargeBinary(), nullable=False),
        sa.Column("perceptual_hash", sa.String(length=16), nullable=False),
        sa.Column("color_histogram", sa.LargeBinary(), nullable=False),
        sa.Column("thumbnail_sha256", sa.String(length=64), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        "ix_asset_similarity_search_features_version",
        "asset_similarity_search_features",
        ["model_version", "feature_version", "config_fingerprint"],
    )
    op.create_index(
        "ix_asset_similarity_search_features_analyzed_at",
        "asset_similarity_search_features",
        ["analyzed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_similarity_search_features_analyzed_at",
        table_name="asset_similarity_search_features",
    )
    op.drop_index(
        "ix_asset_similarity_search_features_version",
        table_name="asset_similarity_search_features",
    )
    op.drop_table("asset_similarity_search_features")
