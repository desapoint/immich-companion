"""Persist stable composite duplicate identity for bounded workspace reads.

Revision ID: 20260914_0045
Revises: 20260914_0044
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "20260914_0045"
down_revision = "20260914_0044"
branch_labels = None
depends_on = None

BATCH_SIZE = 500


def _member_set_key(values: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(set(values))).encode()).hexdigest()


def upgrade() -> None:
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("stable_group_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "composite_duplicate_groups",
        sa.Column("member_fingerprint", sa.String(length=64), nullable=True),
    )

    bind = op.get_bind()
    groups = sa.table(
        "composite_duplicate_groups",
        sa.column("group_id", sa.Text()),
        sa.column("position", sa.Integer()),
        sa.column("discovery_source", sa.String()),
        sa.column("stable_group_key", sa.Text()),
        sa.column("member_fingerprint", sa.String(length=64)),
    )
    members = sa.table(
        "composite_duplicate_group_members",
        sa.column("group_id", sa.Text()),
        sa.column("asset_id", sa.Uuid()),
        sa.column("position", sa.Integer()),
    )

    last_position = -1
    while True:
        group_rows = bind.execute(
            sa.select(groups.c.group_id, groups.c.position, groups.c.discovery_source)
            .where(groups.c.position > last_position)
            .order_by(groups.c.position)
            .limit(BATCH_SIZE)
        ).mappings().all()
        if not group_rows:
            break
        group_ids = [row["group_id"] for row in group_rows]
        member_rows = bind.execute(
            sa.select(members.c.group_id, members.c.asset_id)
            .where(members.c.group_id.in_(group_ids))
            .order_by(members.c.group_id, members.c.position)
        ).all()
        by_group: dict[str, list[str]] = {}
        for group_id, asset_id in member_rows:
            by_group.setdefault(group_id, []).append(str(asset_id))
        updates = []
        for row in group_rows:
            fingerprint = _member_set_key(by_group.get(row["group_id"], []))
            updates.append(
                {
                    "target_group_id": row["group_id"],
                    "stable_key": f'{row["discovery_source"]}:{fingerprint}',
                    "fingerprint": fingerprint,
                }
            )
        bind.execute(
            sa.update(groups)
            .where(groups.c.group_id == sa.bindparam("target_group_id"))
            .values(
                stable_group_key=sa.bindparam("stable_key"),
                member_fingerprint=sa.bindparam("fingerprint"),
            ),
            updates,
        )
        last_position = int(group_rows[-1]["position"])

    op.alter_column("composite_duplicate_groups", "stable_group_key", nullable=False)
    op.alter_column("composite_duplicate_groups", "member_fingerprint", nullable=False)
    op.create_index(
        "ix_composite_duplicate_groups_stable_group_key",
        "composite_duplicate_groups",
        ["stable_group_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_composite_duplicate_groups_stable_group_key",
        table_name="composite_duplicate_groups",
    )
    op.drop_column("composite_duplicate_groups", "member_fingerprint")
    op.drop_column("composite_duplicate_groups", "stable_group_key")
