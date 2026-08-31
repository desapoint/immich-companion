"""Persist fingerprint-bound duplicate group review decisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0021"
down_revision: str | Sequence[str] | None = "20260830_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "duplicate_group_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discovery_source", sa.String(length=32), nullable=False),
        sa.Column("provider_group_id", sa.String(length=255), nullable=False),
        sa.Column("member_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("manual_action", sa.String(length=24), nullable=True),
        sa.Column("manual_primary_asset_id", sa.Uuid(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "discovery_source",
            "provider_group_id",
            name="uq_duplicate_group_reviews_provider",
        ),
    )
    op.create_index(
        "ix_duplicate_group_reviews_status",
        "duplicate_group_reviews",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_duplicate_group_reviews_status",
        table_name="duplicate_group_reviews",
    )
    op.drop_table("duplicate_group_reviews")
