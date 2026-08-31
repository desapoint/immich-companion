"""Persist similarity scan scope and the user's default threshold."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0028"
down_revision: str | Sequence[str] | None = "20260831_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "duplicate_policy",
        sa.Column(
            "similarity_threshold_percent",
            sa.Float(),
            nullable=False,
            server_default="95",
        ),
    )
    op.add_column(
        "similarity_scans",
        sa.Column(
            "scope",
            sa.String(length=32),
            nullable=False,
            server_default="all_eligible_assets",
        ),
    )


def downgrade() -> None:
    op.drop_column("similarity_scans", "scope")
    op.drop_column("duplicate_policy", "similarity_threshold_percent")
