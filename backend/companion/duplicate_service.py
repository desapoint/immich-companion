"""Immich-driven exact duplicate review and bounded batch resolution."""

from __future__ import annotations

import logging
from uuid import UUID

from companion.action_repository import ActionRepository
from companion.asset_repository import AssetRepository
from companion.config import Settings
from companion.discovery import (
    GroupDiscoveryProvider,
    ImmichDuplicateProvider,
)
from companion.duplicate_contracts import (
    contained_native_resolution as _contained_native_resolution,
)
from companion.duplicate_contracts import (
    metadata_keeper_for_plan as _metadata_keeper_for_plan,
)
from companion.duplicate_contracts import (
    options_key as _options_key,
)
from companion.duplicate_contracts import (
    stable_fingerprint as _stable_fingerprint,
)
from companion.duplicate_evidence import DuplicateEvidenceMixin
from companion.duplicate_policy import DuplicatePolicyRepository
from companion.duplicate_resolution import DuplicateResolutionMixin
from companion.duplicate_review import DuplicateReviewMixin
from companion.duplicate_review_repository import DuplicateReviewRepository
from companion.duplicate_schema import (
    CrossSourceDuplicateTaskStart,
    DuplicateAnalysisOptions,
)
from companion.duplicate_task_handlers import (
    CrossSourceDuplicateTaskHandler,
    DuplicateResolutionTaskHandler,
)
from companion.immich import (
    ImmichApiClient,
)
from companion.integrity_repository import (
    IntegrityRepository,
)
from companion.integrity_service import (
    INTEGRITY_TASK_TYPE,
)
from companion.similarity_repository import (
    SimilarityRepository,
)
from companion.similarity_scan_repository import SimilarityScanRepository
from companion.similarity_search_repository import SimilaritySearchRepository
from companion.stack_service import StackService
from companion.task_coordinator import TaskCoordinator

CROSS_SOURCE_DUPLICATE_TASK_TYPE = "cross_source_duplicates"
DUPLICATE_RESOLUTION_TASK_TYPE = "duplicate_resolution"

logger = logging.getLogger(__name__)

__all__ = [
    "CrossSourceDuplicateService",
    "CrossSourceDuplicateTaskHandler",
    "DuplicateResolutionTaskHandler",
    "_contained_native_resolution",
    "_metadata_keeper_for_plan",
]


class CrossSourceDuplicateService(
    DuplicateEvidenceMixin,
    DuplicateReviewMixin,
    DuplicateResolutionMixin,
):
    """Read live groups, join cached verification, and manage reviewed plans."""

    def __init__(
        self,
        settings: Settings,
        immich: ImmichApiClient,
        assets: AssetRepository,
        reports: IntegrityRepository,
        actions: ActionRepository,
        tasks: TaskCoordinator,
        runtime_sync_settings: object,
        reviews: DuplicateReviewRepository | None = None,
        policy: DuplicatePolicyRepository | None = None,
        similarity: SimilarityRepository | None = None,
        discovery: GroupDiscoveryProvider | None = None,
        stacks: StackService | None = None,
        search_features: SimilaritySearchRepository | None = None,
        scan_evidence: SimilarityScanRepository | None = None,
    ) -> None:
        self._settings = settings
        self._immich = immich
        self._assets = assets
        self._reports = reports
        self._actions = actions
        self._tasks = tasks
        self._runtime_sync_settings = runtime_sync_settings
        self._reviews = reviews
        self._policy = policy
        self._similarity = similarity
        self._search_features = search_features
        self._scan_evidence = scan_evidence
        self._discovery = discovery or ImmichDuplicateProvider(immich)
        self._stacks = stacks

    async def _options(
        self,
        options: DuplicateAnalysisOptions | None,
    ) -> DuplicateAnalysisOptions:
        if options is not None or self._policy is None:
            return options or DuplicateAnalysisOptions()
        return (await self._policy.get()).analysis_options()

    async def start(
        self,
        options: DuplicateAnalysisOptions,
    ) -> CrossSourceDuplicateTaskStart:
        key = _options_key(options)
        active = await self._tasks.find_active(CROSS_SOURCE_DUPLICATE_TASK_TYPE, key)
        if active is None:
            active = await self._tasks.submit(
                CROSS_SOURCE_DUPLICATE_TASK_TYPE,
                options.model_dump(mode="json"),
                priority=50,
                lane_key=INTEGRITY_TASK_TYPE,
                deduplication_key=key,
            )
            await self._tasks.start()
        return CrossSourceDuplicateTaskStart(task_id=active.id)

    async def _relation_snapshot(
        self,
        member_ids: set[UUID],
    ) -> tuple[dict[UUID, tuple[set[UUID], set[UUID]]], str]:
        relations: dict[UUID, tuple[set[UUID], set[UUID]]] = {}
        serialized: dict[str, dict[str, list[str]]] = {}
        for member_id in sorted(member_ids):
            summary = await self._assets.get_asset_summary(member_id)
            albums = {album.id for album in summary.albums} if summary is not None else set()
            tags = {UUID(str(tag.id)) for tag in summary.tags} if summary is not None else set()
            relations[member_id] = (albums, tags)
            serialized[str(member_id)] = {
                "album_ids": sorted(str(identifier) for identifier in albums),
                "tag_ids": sorted(str(identifier) for identifier in tags),
            }
        return relations, _stable_fingerprint(serialized)
