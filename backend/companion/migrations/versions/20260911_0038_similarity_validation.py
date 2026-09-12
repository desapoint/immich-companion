"""Persist the similarity group validation strategy.

Revision ID: 20260911_0038
Revises: 20260911_0037
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0038"
down_revision = "20260911_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "similarity_scans",
        sa.Column(
            "grouping_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.alter_column("similarity_scans", "grouping_version", server_default="2")
    op.add_column(
        "similarity_scans",
        sa.Column(
            "validation_mode",
            sa.String(length=16),
            server_default="strict",
            nullable=False,
        ),
    )
    op.add_column(
        "similarity_scans",
        sa.Column("anchor_asset_id", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("similarity_scans", "anchor_asset_id")
    op.drop_column("similarity_scans", "validation_mode")
    op.drop_column("similarity_scans", "grouping_version")
