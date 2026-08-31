"""Persisted global policy for the Immich duplicate workflow."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from companion.database import DatabaseManager
from companion.duplicate_schema import DuplicateAnalysisOptions, DuplicateKeeperPolicy
from companion.models import DuplicatePolicyRecord

ExactFilePolicyAction = Literal["resolve", "keep_all", "stack_all", "review"]


class DuplicatePolicy(BaseModel):
    automatic_handling_enabled: bool = True
    preselect_safe_groups: bool = True
    exact_file_action: ExactFilePolicyAction = "resolve"
    keeper_policy: DuplicateKeeperPolicy = "prefer_upload"
    analyze_automatically: bool = True
    verify_upload_streams: bool = False
    external_library_ids: list[UUID] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def unique_libraries(self) -> DuplicatePolicy:
        self.external_library_ids = list(dict.fromkeys(self.external_library_ids))
        return self

    def analysis_options(self) -> DuplicateAnalysisOptions:
        return DuplicateAnalysisOptions(
            keeper_policy=self.keeper_policy,
            external_library_ids=self.external_library_ids,
            verify_upload_streams=self.verify_upload_streams,
            automatic_handling_enabled=self.automatic_handling_enabled,
            preselect_safe_groups=self.preselect_safe_groups,
            exact_file_action=self.exact_file_action,
            analyze_automatically=self.analyze_automatically,
        )


class DuplicatePolicyRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def get(self) -> DuplicatePolicy:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicatePolicyRecord)
                .where(DuplicatePolicyRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                policy = DuplicatePolicy()
                record = DuplicatePolicyRecord(
                    id=1,
                    **policy.model_dump(mode="json"),
                )
                session.add(record)
                return policy
            return DuplicatePolicy.model_validate(
                {
                    "automatic_handling_enabled": record.automatic_handling_enabled,
                    "preselect_safe_groups": record.preselect_safe_groups,
                    "exact_file_action": record.exact_file_action,
                    "keeper_policy": record.keeper_policy,
                    "analyze_automatically": record.analyze_automatically,
                    "verify_upload_streams": record.verify_upload_streams,
                    "external_library_ids": record.external_library_ids,
                }
            )

    async def update(self, policy: DuplicatePolicy) -> DuplicatePolicy:
        async with self._database.sessions() as session, session.begin():
            record = await session.scalar(
                select(DuplicatePolicyRecord)
                .where(DuplicatePolicyRecord.id == 1)
                .with_for_update()
            )
            if record is None:
                record = DuplicatePolicyRecord(id=1)
                session.add(record)
            values = policy.model_dump(mode="json")
            for key, value in values.items():
                setattr(record, key, value)
        return policy
