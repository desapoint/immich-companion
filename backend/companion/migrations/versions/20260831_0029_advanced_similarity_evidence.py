"""Persist advanced compact similarity evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0029"
down_revision: str | Sequence[str] | None = "20260831_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVIDENCE_COLUMNS = (
    "normalized_luminance_mae",
    "normalized_luminance_rmse",
    "normalized_luminance_ssim",
    "aspect_ratio_difference",
)


def upgrade() -> None:
    for table in ("asset_similarity_edges", "similarity_scan_pairs"):
        for column in EVIDENCE_COLUMNS:
            op.add_column(table, sa.Column(column, sa.Float(), nullable=True))
        op.add_column(table, sa.Column("dimensions_equal", sa.Boolean(), nullable=True))


def downgrade() -> None:
    for table in ("similarity_scan_pairs", "asset_similarity_edges"):
        op.drop_column(table, "dimensions_equal")
        for column in reversed(EVIDENCE_COLUMNS):
            op.drop_column(table, column)
