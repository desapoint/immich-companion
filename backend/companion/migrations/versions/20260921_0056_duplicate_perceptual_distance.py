"""Persist the duplicate discovery perceptual-distance limit.

Revision ID: 20260921_0056
Revises: 20260921_0055
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260921_0056"
down_revision = "20260921_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "duplicate_discovery_settings",
        sa.Column(
            "maximum_perceptual_distance",
            sa.Integer(),
            nullable=False,
            server_default="12",
        ),
    )
    op.create_check_constraint(
        "ck_duplicate_discovery_settings_maximum_perceptual_distance",
        "duplicate_discovery_settings",
        "maximum_perceptual_distance BETWEEN 0 AND 64",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_duplicate_discovery_settings_maximum_perceptual_distance",
        "duplicate_discovery_settings",
        type_="check",
    )
    op.drop_column(
        "duplicate_discovery_settings",
        "maximum_perceptual_distance",
    )
