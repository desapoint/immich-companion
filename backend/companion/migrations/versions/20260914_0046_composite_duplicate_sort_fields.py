"""Persist list-level duplicate sort summaries.

Revision ID: 20260914_0046
Revises: 20260914_0045
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0046"
down_revision = "20260914_0045"
branch_labels = None
depends_on = None

BATCH_SIZE = 500


def upgrade() -> None:
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("member_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("reclaimable_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("similarity_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("oldest_taken_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("newest_taken_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=True),
    )

    bind = op.get_bind()
    groups = sa.table(
        "composite_duplicate_groups",
        sa.column("group_id", sa.Text()),
        sa.column("position", sa.Integer()),
        sa.column("similarity_validation", sa.JSON()),
        sa.column("synced_at", sa.DateTime(timezone=True)),
        sa.column("member_count", sa.Integer()),
        sa.column("reclaimable_bytes", sa.BigInteger()),
        sa.column("similarity_score", sa.Float()),
        sa.column("oldest_taken_at", sa.DateTime(timezone=True)),
        sa.column("newest_taken_at", sa.DateTime(timezone=True)),
        sa.column("first_discovered_at", sa.DateTime(timezone=True)),
    )
    members = sa.table(
        "composite_duplicate_group_members",
        sa.column("group_id", sa.Text()),
        sa.column("asset_id", sa.Uuid()),
    )
    assets = sa.table(
        "assets",
        sa.column("id", sa.Uuid()),
        sa.column("file_size_bytes", sa.BigInteger()),
        sa.column("file_created_at", sa.DateTime(timezone=True)),
    )

    last_position = -1
    while True:
        group_rows = (
            bind.execute(
                sa.select(
                    groups.c.group_id,
                    groups.c.position,
                    groups.c.similarity_validation,
                    groups.c.synced_at,
                )
                .where(groups.c.position > last_position)
                .order_by(groups.c.position)
                .limit(BATCH_SIZE)
            )
            .mappings()
            .all()
        )
        if not group_rows:
            break
        group_ids = [row["group_id"] for row in group_rows]
        member_rows = bind.execute(
            sa.select(
                members.c.group_id,
                assets.c.file_size_bytes,
                assets.c.file_created_at,
            )
            .select_from(members.join(assets, assets.c.id == members.c.asset_id))
            .where(members.c.group_id.in_(group_ids))
        ).all()
        by_group: dict[str, list[tuple[int | None, object]]] = {}
        for group_id, file_size_bytes, file_created_at in member_rows:
            by_group.setdefault(group_id, []).append((file_size_bytes, file_created_at))

        updates = []
        for row in group_rows:
            values = by_group.get(row["group_id"], [])
            sizes = [value[0] for value in values]
            dates = [value[1] for value in values if value[1] is not None]
            validation = row["similarity_validation"]
            score = (
                validation.get("minimum_similarity_percent")
                if isinstance(validation, dict)
                else None
            )
            updates.append(
                {
                    "target_group_id": row["group_id"],
                    "member_count_value": len(values),
                    "reclaimable_value": (
                        sum(size for size in sizes if size is not None)
                        - max(size for size in sizes if size is not None)
                        if sizes and all(size is not None for size in sizes)
                        else None
                    ),
                    "similarity_value": float(score) if score is not None else None,
                    "oldest_value": min(dates) if dates else None,
                    "newest_value": max(dates) if dates else None,
                    "first_discovered_value": row["synced_at"],
                }
            )
        bind.execute(
            sa.update(groups)
            .where(groups.c.group_id == sa.bindparam("target_group_id"))
            .values(
                member_count=sa.bindparam("member_count_value"),
                reclaimable_bytes=sa.bindparam("reclaimable_value"),
                similarity_score=sa.bindparam("similarity_value"),
                oldest_taken_at=sa.bindparam("oldest_value"),
                newest_taken_at=sa.bindparam("newest_value"),
                first_discovered_at=sa.bindparam("first_discovered_value"),
            ),
            updates,
        )
        last_position = int(group_rows[-1]["position"])

    op.alter_column("composite_duplicate_groups", "member_count", nullable=False)
    op.alter_column("composite_duplicate_groups", "first_discovered_at", nullable=False)
    for name in (
        "member_count",
        "reclaimable_bytes",
        "similarity_score",
        "oldest_taken_at",
        "newest_taken_at",
        "first_discovered_at",
    ):
        op.create_index(
            f"ix_composite_duplicate_groups_{name}",
            "composite_duplicate_groups",
            [name],
        )


def downgrade() -> None:
    for name in reversed(
        (
            "member_count",
            "reclaimable_bytes",
            "similarity_score",
            "oldest_taken_at",
            "newest_taken_at",
            "first_discovered_at",
        )
    ):
        op.drop_index(
            f"ix_composite_duplicate_groups_{name}",
            table_name="composite_duplicate_groups",
        )
    op.drop_column("composite_duplicate_groups", "first_discovered_at")
    op.drop_column("composite_duplicate_groups", "newest_taken_at")
    op.drop_column("composite_duplicate_groups", "oldest_taken_at")
    op.drop_column("composite_duplicate_groups", "similarity_score")
    op.drop_column("composite_duplicate_groups", "reclaimable_bytes")
    op.drop_column("composite_duplicate_groups", "member_count")
