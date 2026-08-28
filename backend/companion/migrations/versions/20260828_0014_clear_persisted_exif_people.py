"""Clear persisted EXIF and people payloads from the lightweight asset index."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0014"
down_revision: str | Sequence[str] | None = "20260827_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE assets SET exif_info = NULL, people = '[]'::json")


def downgrade() -> None:
    # Cleared API payloads cannot be reconstructed without fetching Immich again.
    pass
