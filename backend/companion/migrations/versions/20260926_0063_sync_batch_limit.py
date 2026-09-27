"""Keep persisted sync batch settings within the supported editable range.

Revision ID: 20260926_0063
Revises: 20260925_0062
"""

from __future__ import annotations

from alembic import op

revision = "20260926_0063"
down_revision = "20260925_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE sync_runtime_settings SET full_batch_size = 1000 "
        "WHERE full_batch_size > 1000"
    )
    op.create_check_constraint(
        "ck_sync_runtime_full_batch_size",
        "sync_runtime_settings",
        "full_batch_size BETWEEN 1 AND 1000",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_sync_runtime_full_batch_size", "sync_runtime_settings", type_="check"
    )
