"""Persist the exact file-size fact used for cross-source candidates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0017"
down_revision: str | Sequence[str] | None = "20260828_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.create_index(
        "ix_assets_cross_source_candidate",
        "assets",
        ["file_size_bytes", "asset_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_assets_cross_source_candidate", table_name="assets")
    op.drop_column("assets", "file_size_bytes")
