"""Add explicit similarity cache configuration identity.

Revision ID: 20260911_0037
Revises: 20260911_0036
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0037"
down_revision = "20260911_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "asset_similarity_features",
        sa.Column(
            "config_fingerprint", sa.String(length=64), server_default="legacy", nullable=False
        ),
    )
    op.add_column(
        "asset_similarity_edges",
        sa.Column(
            "config_fingerprint", sa.String(length=64), server_default="legacy", nullable=False
        ),
    )
    op.add_column(
        "similarity_scans",
        sa.Column(
            "config_fingerprint", sa.String(length=64), server_default="legacy", nullable=False
        ),
    )
    op.create_index(
        "ix_asset_similarity_features_config",
        "asset_similarity_features",
        ["config_fingerprint"],
    )
    op.create_index(
        "ix_asset_similarity_edges_config",
        "asset_similarity_edges",
        ["config_fingerprint"],
    )


def downgrade() -> None:
    op.drop_column("similarity_scans", "config_fingerprint")
    op.drop_index("ix_asset_similarity_edges_config", table_name="asset_similarity_edges")
    op.drop_index("ix_asset_similarity_features_config", table_name="asset_similarity_features")
    op.drop_column("asset_similarity_edges", "config_fingerprint")
    op.drop_column("asset_similarity_features", "config_fingerprint")
