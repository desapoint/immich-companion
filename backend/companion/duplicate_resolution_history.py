"""Reset completed duplicate-resolution history without undoing Immich mutations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from sqlalchemy import select

from companion.database import DatabaseManager
from companion.duplicate_schema import COMPLETED_DUPLICATE_REVIEW_STATUSES
from companion.models import DuplicateGroupReviewRecord


def _member_ids(record: Any) -> set[str]:
    return {
        str(decision["asset_id"])
        for decision in list(getattr(record, "member_decisions", None) or [])
        if isinstance(decision, dict) and decision.get("asset_id")
    }


def _derived_rows_to_clear(
    target: Any,
    inherited: Iterable[Any],
    remaining_completed: Iterable[Any],
) -> list[Any]:
    """Return derived suppressions that are no longer justified after target is cleared."""

    target_members = _member_ids(target)
    if not target_members:
        return []
    remaining_member_sets = [
        members
        for record in remaining_completed
        if (members := _member_ids(record))
    ]
    stale: list[Any] = []
    for record in inherited:
        members = _member_ids(record)
        if not members or not members.issubset(target_members):
            continue
        if any(members.issubset(other) for other in remaining_member_sets):
            continue
        stale.append(record)
    return stale


async def clear_completed_resolution(
    database: DatabaseManager,
    resolution_id: UUID,
) -> bool:
    """Delete one original completed resolution and its now-orphaned derived suppressions.

    This only resets Companion review/history state. It deliberately does not restore assets,
    undo stacks, or reverse any mutation already completed in Immich.
    """

    async with database.sessions() as session, session.begin():
        target = await session.scalar(
            select(DuplicateGroupReviewRecord)
            .where(
                DuplicateGroupReviewRecord.id == resolution_id,
                DuplicateGroupReviewRecord.review_status.in_(
                    COMPLETED_DUPLICATE_REVIEW_STATUSES
                ),
                DuplicateGroupReviewRecord.draft_status == "completed",
            )
            .with_for_update()
        )
        if target is None:
            return False

        remaining_completed = list(
            (
                await session.scalars(
                    select(DuplicateGroupReviewRecord)
                    .where(
                        DuplicateGroupReviewRecord.id != resolution_id,
                        DuplicateGroupReviewRecord.review_status.in_(
                            COMPLETED_DUPLICATE_REVIEW_STATUSES
                        ),
                        DuplicateGroupReviewRecord.draft_status == "completed",
                    )
                    .with_for_update()
                )
            ).all()
        )
        inherited = list(
            (
                await session.scalars(
                    select(DuplicateGroupReviewRecord)
                    .where(DuplicateGroupReviewRecord.draft_status == "inherited")
                    .with_for_update()
                )
            ).all()
        )
        stale_derived = _derived_rows_to_clear(target, inherited, remaining_completed)

        for record in stale_derived:
            await session.delete(record)
        await session.delete(target)
        return True