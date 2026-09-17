"""Persist bounded similarity provenance and deterministic unavailable state.

Revision ID: 20260916_0049
Revises: 20260916_0048
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260916_0049"
down_revision = "20260916_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_similarity_bounded_state",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("capability_version", sa.Integer(), nullable=False),
        sa.Column("policy_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source_checksum", sa.Text(), nullable=True),
        sa.Column("source_width", sa.Integer(), nullable=True),
        sa.Column("source_height", sa.Integer(), nullable=True),
        sa.Column("source_identity", sa.String(length=64), nullable=False),
        sa.Column("alpha_state", sa.String(length=24), nullable=False),
        sa.Column("search_status", sa.String(length=16), nullable=False),
        sa.Column("search_reason", sa.Text(), nullable=True),
        sa.Column("detail_status", sa.String(length=16), nullable=True),
        sa.Column("detail_reason", sa.Text(), nullable=True),
        sa.Column("detail_source_identity", sa.String(length=64), nullable=True),
        sa.Column("detail_feature_version", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        "ix_asset_similarity_bounded_state_search_status",
        "asset_similarity_bounded_state",
        ["search_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_similarity_bounded_state_search_status",
        table_name="asset_similarity_bounded_state",
    )
    op.drop_table("asset_similarity_bounded_state")
