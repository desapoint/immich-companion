"""Persist Booru retry state and make cron batch size editable.

Revision ID: 20260928_0065
Revises: 20260928_0064
"""

import sqlalchemy as sa
from alembic import op

revision = "20260928_0065"
down_revision = "20260928_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booru_settings",
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="250"),
    )
    op.create_check_constraint(
        "ck_booru_settings_batch_size", "booru_settings", "batch_size BETWEEN 1 AND 1000"
    )
    op.create_table(
        "booru_asset_failures",
        sa.Column(
            "asset_id", sa.Uuid(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "run_id", sa.Uuid(),
            sa.ForeignKey("booru_tag_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(512), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_booru_asset_failures_run_id", "booru_asset_failures", ["run_id"])
    op.create_index(
        "ix_booru_asset_failures_next_retry_at",
        "booru_asset_failures", ["next_retry_at"],
    )


def downgrade() -> None:
    op.drop_table("booru_asset_failures")
    op.drop_constraint("ck_booru_settings_batch_size", "booru_settings", type_="check")
    op.drop_column("booru_settings", "batch_size")
