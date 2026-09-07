"""Persist duplicate stack conflict resolution."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0032"
down_revision: str | Sequence[str] | None = "20260902_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "duplicate_group_reviews",
        sa.Column(
            "stack_resolution",
            sa.String(length=24),
            nullable=False,
            server_default="move_selected",
        ),
    )


def downgrade() -> None:
    op.drop_column("duplicate_group_reviews", "stack_resolution")
