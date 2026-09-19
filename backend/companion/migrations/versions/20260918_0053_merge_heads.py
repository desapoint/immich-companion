"""Merge duplicate-settings and preservation migration heads.

Revision ID: 20260918_0053
Revises: 20260917_0052, 20260918_0051
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260918_0053"
down_revision: str | Sequence[str] | None = (
    "20260917_0052",
    "20260918_0051",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join both already-applied migration branches into one Alembic head."""


def downgrade() -> None:
    """Split the version marker back to both parent heads."""
