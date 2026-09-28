"""Track Booru tag opt-outs and reversible additions.

Revision ID: 20260928_0064
Revises: 20260926_0063
"""

import sqlalchemy as sa
from alembic import op

revision = "20260928_0064"
down_revision = "20260926_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "booru_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_repo", sa.String(128), nullable=False),
        sa.Column("idle_seconds", sa.Integer(), nullable=False),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
        sa.Column("character_threshold", sa.Float(), nullable=False),
    )
    op.create_table(
        "booru_tag_policies",
        sa.Column("tag_id", sa.Uuid(), primary_key=True),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "booru_tag_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("undone_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "booru_tagged_assets",
        sa.Column(
            "asset_id", sa.Uuid(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("booru_tag_runs.id"), nullable=False),
        sa.Column("added_tag_ids", sa.JSON(), nullable=False),
    )
    op.create_index("ix_booru_tagged_assets_run_id", "booru_tagged_assets", ["run_id"])


def downgrade() -> None:
    op.drop_table("booru_tagged_assets")
    op.drop_table("booru_tag_runs")
    op.drop_table("booru_tag_policies")
    op.drop_table("booru_settings")
