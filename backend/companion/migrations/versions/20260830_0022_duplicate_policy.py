"""Persist the global Immich duplicate handling policy."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0022"
down_revision: str | Sequence[str] | None = "20260830_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "duplicate_policy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automatic_handling_enabled", sa.Boolean(), nullable=False),
        sa.Column("preselect_safe_groups", sa.Boolean(), nullable=False),
        sa.Column("exact_file_action", sa.String(length=24), nullable=False),
        sa.Column("keeper_policy", sa.String(length=24), nullable=False),
        sa.Column("analyze_automatically", sa.Boolean(), nullable=False),
        sa.Column("verify_upload_streams", sa.Boolean(), nullable=False),
        sa.Column("external_library_ids", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("duplicate_policy")
