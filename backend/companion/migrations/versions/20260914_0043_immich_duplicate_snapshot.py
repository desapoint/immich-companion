"""Persist the authoritative Immich duplicate-group snapshot.

Revision ID: 20260914_0043
Revises: 20260914_0042
"""

import sqlalchemy as sa
from alembic import op

revision = "20260914_0043"
down_revision = "20260914_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "immich_duplicate_sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("authoritative_generation", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("group_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "immich_duplicate_groups",
        sa.Column("provider_group_id", sa.Text(), nullable=False),
        sa.Column("sync_generation", sa.BigInteger(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider_group_id"),
    )
    op.create_index(
        "ix_immich_duplicate_groups_sync_generation",
        "immich_duplicate_groups",
        ["sync_generation"],
    )
    op.create_index(
        "ix_immich_duplicate_groups_synced_at",
        "immich_duplicate_groups",
        ["synced_at"],
    )
    op.create_table(
        "immich_duplicate_group_members",
        sa.Column("provider_group_id", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sync_generation", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_group_id"],
            ["immich_duplicate_groups.provider_group_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("provider_group_id", "asset_id"),
    )
    op.create_index(
        "ix_immich_duplicate_group_members_asset_id",
        "immich_duplicate_group_members",
        ["asset_id"],
    )
    op.create_index(
        "ix_immich_duplicate_group_members_group_position",
        "immich_duplicate_group_members",
        ["provider_group_id", "position"],
    )
    op.create_index(
        "ix_immich_duplicate_group_members_sync_generation",
        "immich_duplicate_group_members",
        ["sync_generation"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_immich_duplicate_group_members_sync_generation",
        table_name="immich_duplicate_group_members",
    )
    op.drop_index(
        "ix_immich_duplicate_group_members_group_position",
        table_name="immich_duplicate_group_members",
    )
    op.drop_index(
        "ix_immich_duplicate_group_members_asset_id",
        table_name="immich_duplicate_group_members",
    )
    op.drop_table("immich_duplicate_group_members")
    op.drop_index(
        "ix_immich_duplicate_groups_synced_at",
        table_name="immich_duplicate_groups",
    )
    op.drop_index(
        "ix_immich_duplicate_groups_sync_generation",
        table_name="immich_duplicate_groups",
    )
    op.drop_table("immich_duplicate_groups")
    op.drop_table("immich_duplicate_sync_state")
