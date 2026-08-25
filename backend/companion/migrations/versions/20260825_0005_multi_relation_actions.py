"""Add reviewed multi-relation action data.

Revision ID: 20260825_0005
Revises: 20260825_0004
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0005"
down_revision: str | None = "20260825_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist all requested relations and their reviewed applicability."""

    op.add_column(
        "action_plans",
        sa.Column("relation_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "action_plans",
        sa.Column("relation_work", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    """Remove multi-relation action data."""

    op.drop_column("action_plans", "relation_work")
    op.drop_column("action_plans", "relation_ids")
