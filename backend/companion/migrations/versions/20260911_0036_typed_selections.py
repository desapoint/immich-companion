"""Add typed relation selections and duplicate workspace revision.

Revision ID: 20260911_0036
Revises: 20260910_0035
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0036"
down_revision = "20260910_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "selection_sets",
        sa.Column("entity_kind", sa.String(length=16), server_default="asset", nullable=False),
    )
    op.create_index("ix_selection_sets_entity_kind", "selection_sets", ["entity_kind"])
    op.create_table(
        "selection_set_key_members",
        sa.Column("selection_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["selection_id"], ["selection_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("selection_id", "entity_id"),
    )
    op.create_index(
        "ix_selection_set_key_members_entity_id",
        "selection_set_key_members",
        ["entity_id"],
    )
    op.add_column(
        "duplicate_review_workspaces",
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("duplicate_review_workspaces", "revision")
    op.drop_index("ix_selection_set_key_members_entity_id", table_name="selection_set_key_members")
    op.drop_table("selection_set_key_members")
    op.drop_index("ix_selection_sets_entity_kind", table_name="selection_sets")
    op.drop_column("selection_sets", "entity_kind")
