"""Add linked duplicate depth limits.

Revision ID: 20260918_0054
Revises: 20260918_0053
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260918_0054"
down_revision = "20260918_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "duplicate_discovery_settings",
        sa.Column("max_link_depth", sa.Integer(), nullable=False, server_default="2"),
    )
    op.create_check_constraint(
        "ck_duplicate_discovery_settings_max_link_depth",
        "duplicate_discovery_settings",
        "max_link_depth BETWEEN 0 AND 64",
    )

    op.add_column(
        "similarity_scans",
        sa.Column("max_link_depth", sa.Integer(), nullable=False, server_default="2"),
    )
    op.create_check_constraint(
        "ck_similarity_scans_max_link_depth",
        "similarity_scans",
        "max_link_depth BETWEEN 0 AND 64",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_similarity_scans_max_link_depth",
        "similarity_scans",
        type_="check",
    )
    op.drop_column("similarity_scans", "max_link_depth")

    op.drop_constraint(
        "ck_duplicate_discovery_settings_max_link_depth",
        "duplicate_discovery_settings",
        type_="check",
    )
    op.drop_column("duplicate_discovery_settings", "max_link_depth")
