"""Track pruning of historical similarity pair evidence.

Revision ID: 20260922_0058
Revises: 20260922_0057
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260922_0058"
down_revision = "20260922_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "similarity_scans",
        sa.Column("pair_evidence_pruned_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("similarity_scans", "pair_evidence_pruned_at")
