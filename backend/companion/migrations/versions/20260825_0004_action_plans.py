"""Create reviewed action plan and audit storage.

Revision ID: 20260825_0004
Revises: 20260824_0003
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0004"
down_revision: str | None = "20260824_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persisted review plans and execution audits."""

    op.create_table(
        "action_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("relation_id", sa.Uuid(), nullable=True),
        sa.Column("selection", sa.JSON(), nullable=False),
        sa.Column("target_ids", sa.JSON(), nullable=False),
        sa.Column("target_digest", sa.String(length=64), nullable=False),
        sa.Column("applicable_ids", sa.JSON(), nullable=False),
        sa.Column("skipped_ids", sa.JSON(), nullable=False),
        sa.Column("missing_ids", sa.JSON(), nullable=False),
        sa.Column("destructive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="planned"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_plans_action", "action_plans", ["action"])
    op.create_index("ix_action_plans_operation", "action_plans", ["operation"])
    op.create_index("ix_action_plans_status", "action_plans", ["status"])
    op.create_index("ix_action_plans_created_at", "action_plans", ["created_at"])
    op.create_index("ix_action_plans_expires_at", "action_plans", ["expires_at"])


def downgrade() -> None:
    """Remove action plan and audit storage."""

    op.drop_table("action_plans")
