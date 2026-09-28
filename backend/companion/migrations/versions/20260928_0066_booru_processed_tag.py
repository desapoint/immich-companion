"""Make the Booru processed marker tag configurable.

Revision ID: 20260928_0066
Revises: 20260928_0065
"""

import sqlalchemy as sa
from alembic import op

revision = "20260928_0066"
down_revision = "20260928_0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booru_settings",
        sa.Column(
            "processed_tag_name", sa.String(255), nullable=False,
            server_default="auto:processed",
        ),
    )


def downgrade() -> None:
    op.drop_column("booru_settings", "processed_tag_name")
