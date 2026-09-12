"""Allow complete duplicate-provider provenance identifiers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0034"
down_revision: str | Sequence[str] | None = "20260910_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "duplicate_group_reviews",
        "provider_group_id",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "duplicate_group_reviews",
        "provider_group_id",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="left(provider_group_id, 255)",
    )
