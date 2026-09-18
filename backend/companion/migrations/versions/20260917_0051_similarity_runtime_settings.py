"""Add persisted runtime settings for similarity fingerprinting.

Revision ID: 20260917_0051
Revises: 20260917_0050
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260917_0051"
down_revision = "20260917_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "similarity_runtime_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "fingerprint_page_size",
            sa.Integer(),
            nullable=False,
            server_default="250",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_similarity_runtime_settings_singleton"),
        sa.CheckConstraint(
            "fingerprint_page_size BETWEEN 25 AND 2000",
            name="ck_similarity_runtime_settings_fingerprint_page_size",
        ),
    )


def downgrade() -> None:
    op.drop_table("similarity_runtime_settings")
