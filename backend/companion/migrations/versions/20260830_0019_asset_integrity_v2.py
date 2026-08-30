"""Persist content-first format and decoder evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0019"
down_revision: str | Sequence[str] | None = "20260829_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_integrity_reports",
        sa.Column("format_matches_declared", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "asset_integrity_reports",
        sa.Column("container_valid", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "asset_integrity_reports",
        sa.Column(
            "decode_supported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "asset_integrity_reports",
        sa.Column("decode_valid", sa.Boolean(), nullable=True),
    )
    op.alter_column("asset_integrity_reports", "decode_supported", server_default=None)


def downgrade() -> None:
    op.drop_column("asset_integrity_reports", "decode_valid")
    op.drop_column("asset_integrity_reports", "decode_supported")
    op.drop_column("asset_integrity_reports", "container_valid")
    op.drop_column("asset_integrity_reports", "format_matches_declared")
