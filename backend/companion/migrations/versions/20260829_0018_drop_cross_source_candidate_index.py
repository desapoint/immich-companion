"""Drop the obsolete locally inferred duplicate-candidate index."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0018"
down_revision: str | Sequence[str] | None = "20260829_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_assets_cross_source_candidate", table_name="assets")


def downgrade() -> None:
    op.create_index(
        "ix_assets_cross_source_candidate",
        "assets",
        ["file_size_bytes", "asset_type"],
    )
