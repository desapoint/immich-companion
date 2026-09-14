"""Persist V2 duplicate policy state for SQL-native review filters.

Revision ID: 20260914_0047
Revises: 20260914_0046
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0047"
down_revision = "20260914_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "composite_duplicate_groups",
        sa.Column(
            "v2_policy_state",
            sa.String(length=24),
            nullable=False,
            server_default="blocked",
        ),
    )
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("v2_state_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_composite_duplicate_groups_v2_policy_state",
        "composite_duplicate_groups",
        ["v2_policy_state"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_composite_duplicate_groups_v2_policy_state",
        table_name="composite_duplicate_groups",
    )
    op.drop_column("composite_duplicate_groups", "v2_state_updated_at")
    op.drop_column("composite_duplicate_groups", "v2_policy_state")
