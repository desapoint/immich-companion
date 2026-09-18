"""Add persisted duplicate discovery settings.

Revision ID: 20260917_0052
Revises: 20260917_0051
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260917_0052"
down_revision = "20260917_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "duplicate_discovery_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("include_exact", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("include_similar", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "similarity_threshold",
            sa.Float(),
            nullable=False,
            server_default="95",
        ),
        sa.Column(
            "validation_mode",
            sa.String(length=16),
            nullable=False,
            server_default="strict",
        ),
        sa.Column(
            "max_candidates",
            sa.Integer(),
            nullable=False,
            server_default="8",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_duplicate_discovery_settings_singleton"),
        sa.CheckConstraint(
            "similarity_threshold BETWEEN 50 AND 100",
            name="ck_duplicate_discovery_settings_similarity_threshold",
        ),
        sa.CheckConstraint(
            "validation_mode IN ('reference', 'linked', 'strict')",
            name="ck_duplicate_discovery_settings_validation_mode",
        ),
        sa.CheckConstraint(
            "max_candidates BETWEEN 1 AND 64",
            name="ck_duplicate_discovery_settings_max_candidates",
        ),
    )


def downgrade() -> None:
    op.drop_table("duplicate_discovery_settings")
