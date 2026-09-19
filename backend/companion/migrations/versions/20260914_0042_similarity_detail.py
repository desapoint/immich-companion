"""Persist candidate-only high-detail evidence and scoring provenance.

Revision ID: 20260914_0042
Revises: 20260913_0041
"""

import sqlalchemy as sa
from alembic import op

revision = "20260914_0042"
down_revision = "20260913_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_similarity_detail_features",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("source_identity", sa.String(length=64), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=24), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sample", sa.LargeBinary(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        "ix_asset_similarity_detail_features_analyzed_at",
        "asset_similarity_detail_features", ["analyzed_at"],
    )
    op.add_column(
        "asset_similarity_edges",
        sa.Column("detail_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "asset_similarity_edges",
        sa.Column("detail_changed_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "asset_similarity_edges",
        sa.Column("detail_source", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "similarity_scan_pairs",
        sa.Column("detail_changed_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "similarity_scan_pairs",
        sa.Column("detail_source", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("similarity_scan_pairs", "detail_source")
    op.drop_column("similarity_scan_pairs", "detail_changed_percent")
    op.drop_column("asset_similarity_edges", "detail_source")
    op.drop_column("asset_similarity_edges", "detail_changed_percent")
    op.drop_column("asset_similarity_edges", "detail_version")
    op.drop_index(
        "ix_asset_similarity_detail_features_analyzed_at",
        table_name="asset_similarity_detail_features",
    )
    op.drop_table("asset_similarity_detail_features")
