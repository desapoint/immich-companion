"""Add ordered duplicate source and keeper tie-break priorities.

Revision ID: 20260911_0039
Revises: 20260911_0038
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0039"
down_revision = "20260911_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "duplicate_policy",
        sa.Column("source_priority", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column(
        "duplicate_policy",
        sa.Column("keeper_tiebreakers", sa.JSON(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("duplicate_policy", "keeper_tiebreakers")
    op.drop_column("duplicate_policy", "source_priority")
