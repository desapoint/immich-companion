"""Persist full-decode image dimensions and Immich comparison."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0020"
down_revision: str | Sequence[str] | None = "20260830_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "asset_integrity_reports",
        sa.Column("decoded_width", sa.Integer(), nullable=True),
    )
    op.add_column(
        "asset_integrity_reports",
        sa.Column("decoded_height", sa.Integer(), nullable=True),
    )
    op.add_column(
        "asset_integrity_reports",
        sa.Column("dimensions_match_immich", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("asset_integrity_reports", "dimensions_match_immich")
    op.drop_column("asset_integrity_reports", "decoded_height")
    op.drop_column("asset_integrity_reports", "decoded_width")
