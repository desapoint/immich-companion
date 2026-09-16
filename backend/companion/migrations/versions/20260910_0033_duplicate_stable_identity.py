"""Persist stable duplicate group and member-set identities."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0033"
down_revision: str | Sequence[str] | None = "20260906_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "duplicate_group_reviews",
        sa.Column("stable_group_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "duplicate_group_reviews",
        sa.Column("member_set_key", sa.String(length=64), nullable=True),
    )
    op.execute(
        """
        UPDATE duplicate_group_reviews
        SET member_set_key = member_fingerprint,
            stable_group_key = discovery_source || ':' || member_fingerprint
        """
    )
    op.execute(
        """
        DELETE FROM duplicate_group_reviews AS older
        USING duplicate_group_reviews AS newer
        WHERE older.stable_group_key = newer.stable_group_key
          AND (older.updated_at, older.id) < (newer.updated_at, newer.id)
        """
    )
    op.alter_column("duplicate_group_reviews", "stable_group_key", nullable=False)
    op.alter_column("duplicate_group_reviews", "member_set_key", nullable=False)
    op.drop_constraint(
        "uq_duplicate_group_reviews_provider",
        "duplicate_group_reviews",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_duplicate_group_reviews_stable_key",
        "duplicate_group_reviews",
        ["stable_group_key"],
    )
    op.create_index(
        "ix_duplicate_group_reviews_member_set_key",
        "duplicate_group_reviews",
        ["member_set_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_duplicate_group_reviews_member_set_key",
        table_name="duplicate_group_reviews",
    )
    op.drop_constraint(
        "uq_duplicate_group_reviews_stable_key",
        "duplicate_group_reviews",
        type_="unique",
    )
    op.execute(
        """
        DELETE FROM duplicate_group_reviews AS older
        USING duplicate_group_reviews AS newer
        WHERE older.discovery_source = newer.discovery_source
          AND older.provider_group_id = newer.provider_group_id
          AND (older.updated_at, older.id) < (newer.updated_at, newer.id)
        """
    )
    op.create_unique_constraint(
        "uq_duplicate_group_reviews_provider",
        "duplicate_group_reviews",
        ["discovery_source", "provider_group_id"],
    )
    op.drop_column("duplicate_group_reviews", "member_set_key")
    op.drop_column("duplicate_group_reviews", "stable_group_key")
