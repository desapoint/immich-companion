"""Record the media origin of coarse search fingerprints.

Revision ID: 20260913_0041
Revises: 20260912_0040
"""

import sqlalchemy as sa
from alembic import op

revision = "20260913_0041"
down_revision = "20260912_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "asset_similarity_search_features", "preview_sha256",
        new_column_name="media_sha256",
    )
    op.add_column(
        "asset_similarity_search_features",
        sa.Column(
            "fingerprint_origin", sa.String(length=16),
            nullable=False, server_default="preview",
        ),
    )


def downgrade() -> None:
    op.drop_column("asset_similarity_search_features", "fingerprint_origin")
    op.alter_column(
        "asset_similarity_search_features", "media_sha256",
        new_column_name="preview_sha256",
    )
