"""Add a persisted runtime generation for similarity evidence rebuilds.

Revision ID: 20260917_0050
Revises: 20260916_0049
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260917_0050"
down_revision = "20260916_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "similarity_evidence_state",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("epoch", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("code_generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "descriptor_fingerprint",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
        sa.Column("rebuilt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_similarity_evidence_state_singleton"),
        sa.CheckConstraint("epoch >= 1", name="ck_similarity_evidence_state_epoch_positive"),
    )
    op.execute(
        "INSERT INTO similarity_evidence_state "
        "(id, epoch, code_generation, descriptor_fingerprint) VALUES (1, 1, 1, '')"
    )


def downgrade() -> None:
    op.drop_table("similarity_evidence_state")
