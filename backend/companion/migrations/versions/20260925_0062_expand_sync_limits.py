"""Expand persisted synchronization runtime limits and refresh duplicate projection.

Revision ID: 20260925_0062
Revises: 20260925_0061
"""

from __future__ import annotations

from alembic import op

revision = "20260925_0062"
down_revision = "20260925_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_sync_runtime_metadata_concurrency", "sync_runtime_settings", type_="check"
    )
    op.drop_constraint("ck_sync_runtime_page_prefetch", "sync_runtime_settings", type_="check")
    op.drop_constraint(
        "ck_sync_runtime_incremental_overlap", "sync_runtime_settings", type_="check"
    )
    op.create_check_constraint(
        "ck_sync_runtime_metadata_concurrency",
        "sync_runtime_settings",
        "metadata_request_concurrency BETWEEN 1 AND 64",
    )
    op.create_check_constraint(
        "ck_sync_runtime_page_prefetch",
        "sync_runtime_settings",
        "page_prefetch BETWEEN 0 AND 16",
    )
    op.create_check_constraint(
        "ck_sync_runtime_incremental_overlap",
        "sync_runtime_settings",
        "incremental_overlap_seconds BETWEEN 0 AND 604800",
    )

    # Rebuild the active projection once so groups persisted by older versions are
    # republished through the new video-exclusion rules.
    op.execute("UPDATE composite_duplicate_sync_state SET last_success_at = NULL")


def downgrade() -> None:
    op.drop_constraint(
        "ck_sync_runtime_metadata_concurrency", "sync_runtime_settings", type_="check"
    )
    op.drop_constraint("ck_sync_runtime_page_prefetch", "sync_runtime_settings", type_="check")
    op.drop_constraint(
        "ck_sync_runtime_incremental_overlap", "sync_runtime_settings", type_="check"
    )
    op.execute(
        """
        UPDATE sync_runtime_settings
        SET metadata_request_concurrency = LEAST(metadata_request_concurrency, 16),
            page_prefetch = LEAST(page_prefetch, 4),
            incremental_overlap_seconds = LEAST(incremental_overlap_seconds, 86400)
        """
    )
    op.create_check_constraint(
        "ck_sync_runtime_metadata_concurrency",
        "sync_runtime_settings",
        "metadata_request_concurrency BETWEEN 1 AND 16",
    )
    op.create_check_constraint(
        "ck_sync_runtime_page_prefetch",
        "sync_runtime_settings",
        "page_prefetch BETWEEN 0 AND 4",
    )
    op.create_check_constraint(
        "ck_sync_runtime_incremental_overlap",
        "sync_runtime_settings",
        "incremental_overlap_seconds BETWEEN 0 AND 86400",
    )
