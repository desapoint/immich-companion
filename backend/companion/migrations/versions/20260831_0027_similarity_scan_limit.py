"""Persist the bounded result limit for similarity scans."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0027"
down_revision: str | Sequence[str] | None = "20260831_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "similarity_scans",
        sa.Column("maximum_matches", sa.Integer(), nullable=False, server_default="5000"),
    )


def downgrade() -> None:
    op.drop_column("similarity_scans", "maximum_matches")
