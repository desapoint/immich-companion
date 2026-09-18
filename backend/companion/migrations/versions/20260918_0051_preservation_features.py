"""Separate preservation/integrity evidence from Appearance search.

Revision ID: 20260918_0051
Revises: 20260917_0050
"""

from collections.abc import Sequence
import hashlib

import sqlalchemy as sa
from alembic import op

revision: str = "20260918_0051"
down_revision: str | Sequence[str] | None = "20260917_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRESERVATION_VERSION = 1
PRESERVATION_CONFIG_FINGERPRINT = hashlib.sha256(
    (
        "image-preservation-v1:"
        "feature=1:"
        "pixel-normalization=1:"
        "metadata=exif-capture-camera-gps-orientation-icc-v1"
    ).encode(),
    usedforsecurity=False,
).hexdigest()


def upgrade() -> None:
    # Rename rather than copy so all previously captured hashes, decoded-image facts,
    # metadata flags, and compact appearance samples survive the migration unchanged.
    op.rename_table("asset_similarity_features", "asset_image_preservation_features")
    op.execute(
        "ALTER INDEX ix_asset_similarity_features_analyzed_at "
        "RENAME TO ix_asset_image_preservation_features_analyzed_at"
    )
    op.drop_index(
        "ix_asset_similarity_features_version",
        table_name="asset_image_preservation_features",
    )

    # Preserve the old version/config values explicitly as extractor provenance. They
    # are no longer the freshness boundary for the Appearance pipeline.
    op.alter_column(
        "asset_image_preservation_features",
        "model_version",
        new_column_name="extractor_model_version",
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "asset_image_preservation_features",
        "feature_version",
        new_column_name="extractor_feature_version",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "asset_image_preservation_features",
        "config_fingerprint",
        new_column_name="extractor_config_fingerprint",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )

    op.add_column(
        "asset_image_preservation_features",
        sa.Column("preservation_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "asset_image_preservation_features",
        sa.Column(
            "preservation_config_fingerprint",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "asset_image_preservation_features",
        sa.Column("origin", sa.String(length=24), nullable=True),
    )

    # Integrity preview fallbacks historically used normalization version 0. Keep that
    # provenance rather than claiming those rows are original-derived evidence.
    op.execute(
        sa.text(
            "UPDATE asset_image_preservation_features "
            "SET preservation_version = :preservation_version, "
            "preservation_config_fingerprint = :preservation_config, "
            "origin = CASE "
            "WHEN pixel_normalization_version = 0 THEN 'preview' "
            "ELSE 'original' END"
        ).bindparams(
            preservation_version=PRESERVATION_VERSION,
            preservation_config=PRESERVATION_CONFIG_FINGERPRINT,
        )
    )
    op.alter_column(
        "asset_image_preservation_features",
        "preservation_version",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "asset_image_preservation_features",
        "preservation_config_fingerprint",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "asset_image_preservation_features",
        "origin",
        existing_type=sa.String(length=24),
        nullable=False,
    )

    op.create_index(
        "ix_asset_image_preservation_features_extractor_version",
        "asset_image_preservation_features",
        [
            "extractor_model_version",
            "extractor_feature_version",
            "extractor_config_fingerprint",
        ],
    )
    op.create_index(
        "ix_asset_image_preservation_features_version",
        "asset_image_preservation_features",
        ["preservation_version", "preservation_config_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_asset_image_preservation_features_version",
        table_name="asset_image_preservation_features",
    )
    op.drop_index(
        "ix_asset_image_preservation_features_extractor_version",
        table_name="asset_image_preservation_features",
    )
    op.drop_column("asset_image_preservation_features", "origin")
    op.drop_column(
        "asset_image_preservation_features",
        "preservation_config_fingerprint",
    )
    op.drop_column("asset_image_preservation_features", "preservation_version")

    op.alter_column(
        "asset_image_preservation_features",
        "extractor_config_fingerprint",
        new_column_name="config_fingerprint",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "asset_image_preservation_features",
        "extractor_feature_version",
        new_column_name="feature_version",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "asset_image_preservation_features",
        "extractor_model_version",
        new_column_name="model_version",
        existing_type=sa.String(length=32),
        existing_nullable=False,
    )
    op.create_index(
        "ix_asset_similarity_features_version",
        "asset_image_preservation_features",
        ["model_version", "feature_version"],
    )
    op.execute(
        "ALTER INDEX ix_asset_image_preservation_features_analyzed_at "
        "RENAME TO ix_asset_similarity_features_analyzed_at"
    )
    op.rename_table("asset_image_preservation_features", "asset_similarity_features")
