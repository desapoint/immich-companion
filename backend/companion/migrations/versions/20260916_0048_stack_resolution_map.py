"""Allow reviewed per-stack conflict resolutions in duplicate drafts.

Revision ID: 20260916_0048
Revises: 20260914_0047
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260916_0048"
down_revision = "20260914_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "duplicate_group_reviews",
        "stack_resolution",
        existing_type=sa.String(length=24),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE duplicate_group_reviews "
        "SET stack_resolution = 'move_selected' "
        "WHERE length(stack_resolution) > 24"
    )
    op.alter_column(
        "duplicate_group_reviews",
        "stack_resolution",
        existing_type=sa.Text(),
        type_=sa.String(length=24),
        existing_nullable=False,
        postgresql_using="left(stack_resolution, 24)",
    )
