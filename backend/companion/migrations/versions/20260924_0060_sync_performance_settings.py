"""Persist the complete synchronization performance configuration.

Revision ID: 20260924_0060
Revises: 20260924_0059
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260924_0060"
down_revision = "20260924_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_runtime_settings",
        sa.Column("metadata_request_concurrency", sa.Integer(), nullable=False, server_default="4"),
    )
    op.add_column(
        "sync_runtime_settings",
        sa.Column("page_prefetch", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "sync_runtime_settings",
        sa.Column("api_page_size", sa.Integer(), nullable=False, server_default="1000"),
    )
    op.add_column(
        "sync_runtime_settings",
        sa.Column(
            "incremental_overlap_seconds",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
    )
    op.add_column(
        "sync_runtime_settings",
        sa.Column(
            "incremental_strategy",
            sa.String(length=16),
            nullable=False,
            server_default="automatic",
        ),
    )
    op.add_column(
        "sync_runtime_settings",
        sa.Column("adaptive_throttling", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_check_constraint(
        "ck_sync_runtime_metadata_concurrency", "sync_runtime_settings",
        "metadata_request_concurrency BETWEEN 1 AND 16",
    )
    op.create_check_constraint(
        "ck_sync_runtime_page_prefetch", "sync_runtime_settings", "page_prefetch BETWEEN 0 AND 4"
    )
    op.create_check_constraint(
        "ck_sync_runtime_api_page_size",
        "sync_runtime_settings",
        "api_page_size BETWEEN 25 AND 1000",
    )
    op.create_check_constraint(
        "ck_sync_runtime_incremental_overlap", "sync_runtime_settings",
        "incremental_overlap_seconds BETWEEN 0 AND 86400",
    )
    op.create_check_constraint(
        "ck_sync_runtime_incremental_strategy", "sync_runtime_settings",
        "incremental_strategy IN ('automatic', 'asset', 'relation')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_sync_runtime_incremental_strategy", "sync_runtime_settings", type_="check"
    )
    op.drop_constraint(
        "ck_sync_runtime_incremental_overlap", "sync_runtime_settings", type_="check"
    )
    op.drop_constraint("ck_sync_runtime_api_page_size", "sync_runtime_settings", type_="check")
    op.drop_constraint("ck_sync_runtime_page_prefetch", "sync_runtime_settings", type_="check")
    op.drop_constraint(
        "ck_sync_runtime_metadata_concurrency", "sync_runtime_settings", type_="check"
    )
    op.drop_column("sync_runtime_settings", "adaptive_throttling")
    op.drop_column("sync_runtime_settings", "incremental_strategy")
    op.drop_column("sync_runtime_settings", "incremental_overlap_seconds")
    op.drop_column("sync_runtime_settings", "api_page_size")
    op.drop_column("sync_runtime_settings", "page_prefetch")
    op.drop_column("sync_runtime_settings", "metadata_request_concurrency")
