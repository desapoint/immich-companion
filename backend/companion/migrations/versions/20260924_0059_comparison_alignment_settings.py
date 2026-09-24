"""Persist localized comparison alignment limits.

Revision ID: 20260924_0059
Revises: 20260922_0058
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260924_0059"
down_revision = "20260922_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "duplicate_discovery_settings",
        sa.Column(
            "comparison_max_displacement_percent",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.add_column(
        "duplicate_discovery_settings",
        sa.Column(
            "comparison_max_rotation_degrees",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_duplicate_discovery_settings_comparison_max_displacement",
        "duplicate_discovery_settings",
            "comparison_max_displacement_percent BETWEEN 0 AND 50",
    )
    op.create_check_constraint(
        "ck_duplicate_discovery_settings_comparison_max_rotation",
        "duplicate_discovery_settings",
            "comparison_max_rotation_degrees BETWEEN 0 AND 30",
    )
    op.add_column(
        "duplicate_discovery_settings",
        sa.Column(
            "comparison_max_zoom_percent",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_duplicate_discovery_settings_comparison_max_zoom",
        "duplicate_discovery_settings",
        "comparison_max_zoom_percent BETWEEN 0 AND 50",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_duplicate_discovery_settings_comparison_max_zoom",
        "duplicate_discovery_settings",
        type_="check",
    )
    op.drop_column("duplicate_discovery_settings", "comparison_max_zoom_percent")
    op.drop_constraint(
        "ck_duplicate_discovery_settings_comparison_max_rotation",
        "duplicate_discovery_settings",
        type_="check",
    )
    op.drop_constraint(
        "ck_duplicate_discovery_settings_comparison_max_displacement",
        "duplicate_discovery_settings",
        type_="check",
    )
    op.drop_column("duplicate_discovery_settings", "comparison_max_rotation_degrees")
    op.drop_column("duplicate_discovery_settings", "comparison_max_displacement_percent")
