"""Separate original-image preservation evidence from Appearance search.

Revision ID: 20260918_0051
Revises: 20260917_0050
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0051"
down_revision: str | Sequence[str] | None = "20260917_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename instead of copying so every legacy field remains available during the
    # transition. Similarity consumers are rewired separately to the current search
    # and detail repositories; this table becomes preservation/integrity evidence.
    op.rename_table("asset_similarity_features", "asset_image_preservation_features")
    op.execute(
        "ALTER INDEX ix_asset_similarity_features_version "
        "RENAME TO ix_asset_image_preservation_features_version"
    )
    op.execute(
        "ALTER INDEX ix_asset_similarity_features_analyzed_at "
        "RENAME TO ix_asset_image_preservation_features_analyzed_at"
    )
    op.add_column(
        "asset_image_preservation_features",
        sa.Column("origin", sa.String(length=24), nullable=True),
    )
    # Integrity preview fallbacks have always used normalization version 0. Preserve
    # that provenance rather than pretending the migrated record came from an original.
    op.execute(
        "UPDATE asset_image_preservation_features "
        "SET origin = CASE "
        "WHEN pixel_normalization_version = 0 THEN 'preview' "
        "ELSE 'original' END"
    )
    op.alter_column(
        "asset_image_preservation_features",
        "origin",
        existing_type=sa.String(length=24),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("asset_image_preservation_features", "origin")
    op.execute(
        "ALTER INDEX ix_asset_image_preservation_features_analyzed_at "
        "RENAME TO ix_asset_similarity_features_analyzed_at"
    )
    op.execute(
        "ALTER INDEX ix_asset_image_preservation_features_version "
        "RENAME TO ix_asset_similarity_features_version"
    )
    op.rename_table("asset_image_preservation_features", "asset_similarity_features")
