"""Persist retained-match discovery settings and definitive scan cap telemetry.

Revision ID: 20260922_0057
Revises: 20260921_0056
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260922_0057"
down_revision = "20260921_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "duplicate_discovery_settings",
        sa.Column(
            "maximum_matches",
            sa.Integer(),
            nullable=False,
            server_default="5000",
        ),
    )
    op.create_check_constraint(
        "ck_duplicate_discovery_settings_maximum_matches",
        "duplicate_discovery_settings",
        "maximum_matches BETWEEN 1 AND 50000",
    )
    op.add_column(
        "similarity_scans",
        sa.Column("result_limit_reached", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("similarity_scans", "result_limit_reached")
    op.drop_constraint(
        "ck_duplicate_discovery_settings_maximum_matches",
        "duplicate_discovery_settings",
        type_="check",
    )
    op.drop_column("duplicate_discovery_settings", "maximum_matches")
