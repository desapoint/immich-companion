"""Add the remaining Booru run policy settings.

Revision ID: 20260928_0067
Revises: 20260928_0066
"""

import sqlalchemy as sa
from alembic import op

revision = "20260928_0067"
down_revision = "20260928_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = (
        sa.Column("content_rating_tag_name", sa.String(255), nullable=False,
                  server_default="content-rating"),
        sa.Column("target_albums", sa.Text(), nullable=False, server_default=""),
        sa.Column("max_batches_per_run", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("unload_model_after_run", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("failure_timeout", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("tag_cache_ttl", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("log_level", sa.String(16), nullable=False, server_default="INFO"),
    )
    for column in columns:
        op.add_column("booru_settings", column)


def downgrade() -> None:
    for name in (
        "log_level", "tag_cache_ttl", "failure_timeout", "unload_model_after_run",
        "max_batches_per_run", "target_albums", "content_rating_tag_name",
    ):
        op.drop_column("booru_settings", name)
