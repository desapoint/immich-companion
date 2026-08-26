"""Add hybrid staged synchronization state.

Revision ID: 20260826_0006
Revises: 20260825_0005
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0006"
down_revision: str | None = "20260825_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def add_generation_column(table: str, name: str = "sync_generation") -> None:
    """Add one indexed, backfilled generation marker."""

    op.add_column(
        table,
        sa.Column(name, sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_index(f"ix_{table}_{name}", table, [name])


def upgrade() -> None:
    """Persist staged progress, singleton leases, and entity generations."""

    op.add_column("assets", sa.Column("sync_fingerprint", sa.String(64), nullable=True))
    add_generation_column("assets")
    add_generation_column("assets", "stack_generation")
    add_generation_column("albums")
    add_generation_column("album_assets")
    add_generation_column("tags")
    add_generation_column("tag_assets")

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cursor", sa.String(255), nullable=True),
        sa.Column("counters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("owner_token", sa.Uuid(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("mode", "status", "phase", "generation", "created_at"):
        op.create_index(f"ix_sync_runs_{column}", "sync_runs", [column])

    op.create_table(
        "sync_coordinator",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_run_id", sa.Uuid(), nullable=True),
        sa.Column("pending_run_id", sa.Uuid(), nullable=True),
        sa.Column("generation_counter", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("authoritative_generation", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("successful_watermark", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_coordinator_active_run_id", "sync_coordinator", ["active_run_id"])
    op.create_index("ix_sync_coordinator_pending_run_id", "sync_coordinator", ["pending_run_id"])
    op.execute("INSERT INTO sync_coordinator (id) VALUES (1)")


def downgrade() -> None:
    """Remove hybrid sync state and entity generation markers."""

    op.drop_table("sync_coordinator")
    op.drop_table("sync_runs")
    for table, name in (
        ("tag_assets", "sync_generation"),
        ("tags", "sync_generation"),
        ("album_assets", "sync_generation"),
        ("albums", "sync_generation"),
        ("assets", "stack_generation"),
        ("assets", "sync_generation"),
    ):
        op.drop_index(f"ix_{table}_{name}", table_name=table)
        op.drop_column(table, name)
    op.drop_column("assets", "sync_fingerprint")
