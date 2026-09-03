"""Configure adaptive tag association concurrency."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0031"
down_revision: str | Sequence[str] | None = "20260831_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sync_runtime_settings",
        sa.Column(
            "tag_association_concurrency",
            sa.Integer(),
            nullable=False,
            server_default="4",
        ),
    )


def downgrade() -> None:
    op.drop_column("sync_runtime_settings", "tag_association_concurrency")
