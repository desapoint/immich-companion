"""Persist the provider-neutral composite duplicate snapshot.

Revision ID: 20260914_0044
Revises: 20260914_0043
"""

import sqlalchemy as sa
from alembic import op

revision = "20260914_0044"
down_revision = "20260914_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "composite_duplicate_sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("authoritative_generation", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("group_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "composite_duplicate_groups",
        sa.Column("group_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("discovery_source", sa.String(length=48), nullable=False),
        sa.Column("provider_group_id", sa.Text(), nullable=True),
        sa.Column("provider_metadata", sa.JSON(), nullable=False),
        sa.Column("similarity_validation", sa.JSON(), nullable=True),
        sa.Column("sync_generation", sa.BigInteger(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("group_id"),
    )
    op.create_index(
        "ix_composite_duplicate_groups_position",
        "composite_duplicate_groups",
        ["position"],
    )
    op.create_index(
        "ix_composite_duplicate_groups_discovery_source",
        "composite_duplicate_groups",
        ["discovery_source"],
    )
    op.create_index(
        "ix_composite_duplicate_groups_sync_generation",
        "composite_duplicate_groups",
        ["sync_generation"],
    )
    op.create_index(
        "ix_composite_duplicate_groups_synced_at",
        "composite_duplicate_groups",
        ["synced_at"],
    )
    op.create_table(
        "composite_duplicate_group_members",
        sa.Column("group_id", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sync_generation", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["composite_duplicate_groups.group_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "asset_id"),
    )
    op.create_index(
        "ix_composite_duplicate_group_members_asset_id",
        "composite_duplicate_group_members",
        ["asset_id"],
    )
    op.create_index(
        "ix_composite_duplicate_group_members_group_position",
        "composite_duplicate_group_members",
        ["group_id", "position"],
    )
    op.create_index(
        "ix_composite_duplicate_group_members_sync_generation",
        "composite_duplicate_group_members",
        ["sync_generation"],
    )
    op.create_table(
        "composite_duplicate_group_evidence",
        sa.Column("group_id", sa.Text(), nullable=False),
        sa.Column("discovery_source", sa.String(length=48), nullable=False),
        sa.Column("provider_group_id", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("sync_generation", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["composite_duplicate_groups.group_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "discovery_source"),
    )
    op.create_index(
        "ix_composite_duplicate_group_evidence_sync_generation",
        "composite_duplicate_group_evidence",
        ["sync_generation"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_composite_duplicate_group_evidence_sync_generation",
        table_name="composite_duplicate_group_evidence",
    )
    op.drop_table("composite_duplicate_group_evidence")
    op.drop_index(
        "ix_composite_duplicate_group_members_sync_generation",
        table_name="composite_duplicate_group_members",
    )
    op.drop_index(
        "ix_composite_duplicate_group_members_group_position",
        table_name="composite_duplicate_group_members",
    )
    op.drop_index(
        "ix_composite_duplicate_group_members_asset_id",
        table_name="composite_duplicate_group_members",
    )
    op.drop_table("composite_duplicate_group_members")
    op.drop_index(
        "ix_composite_duplicate_groups_synced_at",
        table_name="composite_duplicate_groups",
    )
    op.drop_index(
        "ix_composite_duplicate_groups_sync_generation",
        table_name="composite_duplicate_groups",
    )
    op.drop_index(
        "ix_composite_duplicate_groups_discovery_source",
        table_name="composite_duplicate_groups",
    )
    op.drop_index(
        "ix_composite_duplicate_groups_position",
        table_name="composite_duplicate_groups",
    )
    op.drop_table("composite_duplicate_groups")
    op.drop_table("composite_duplicate_sync_state")
