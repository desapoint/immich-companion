"""Persist the latest bounded file-integrity report per active asset."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0016"
down_revision: str | Sequence[str] | None = "20260828_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_integrity_reports",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("analyzer_version", sa.Integer(), nullable=False),
        sa.Column("source_checksum", sa.Text(), nullable=True),
        sa.Column("source_file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source_mime_type", sa.String(length=255), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha1_hex", sa.String(length=40), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("detected_format", sa.String(length=24), nullable=False),
        sa.Column("classification", sa.String(length=24), nullable=False),
        sa.Column("structurally_valid", sa.Boolean(), nullable=True),
        sa.Column("jpeg_eoi_offset", sa.BigInteger(), nullable=True),
        sa.Column(
            "trailing_byte_count", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("immich_checksum_match", sa.Boolean(), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        "ix_asset_integrity_reports_classification",
        "asset_integrity_reports",
        ["classification"],
    )
    op.create_index(
        "ix_asset_integrity_reports_analyzed_at",
        "asset_integrity_reports",
        ["analyzed_at"],
    )
    op.create_index(
        "ix_asset_integrity_exact_hash",
        "asset_integrity_reports",
        ["byte_size", "sha256_hex"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_integrity_exact_hash", table_name="asset_integrity_reports")
    op.drop_index(
        "ix_asset_integrity_reports_analyzed_at", table_name="asset_integrity_reports"
    )
    op.drop_index(
        "ix_asset_integrity_reports_classification", table_name="asset_integrity_reports"
    )
    op.drop_table("asset_integrity_reports")
