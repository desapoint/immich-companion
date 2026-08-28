"""Remove persisted trash records and obsolete restoration-context settings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0015"
down_revision: str | Sequence[str] | None = "20260828_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM assets WHERE is_trashed = true")
    op.drop_column("sync_runtime_settings", "sync_trashed_tag_context")
    op.drop_column("sync_runtime_settings", "sync_trashed_album_context")


def downgrade() -> None:
    op.add_column(
        "sync_runtime_settings",
        sa.Column(
            "sync_trashed_album_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "sync_runtime_settings",
        sa.Column(
            "sync_trashed_tag_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
