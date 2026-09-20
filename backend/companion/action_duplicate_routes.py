"""Asset action, selection, and duplicate route registration."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import (
    FastAPI,
    HTTPException,
    status,
)

from companion.action_schema import (
    AssetActionExecuteRequest,
    AssetActionPlan,
    AssetActionPlanRequest,
    AssetActionResult,
    AssetActionTaskStart,
    AssetSelectionCapabilities,
    AssetSelectionRelationships,
    AssetSelectionRequest,
    AssetSelectionResolution,
    SelectionSetMembershipRequest,
    SelectionSetMembershipResponse,
    SelectionSetMembersRequest,
    SelectionSetView,
)
from companion.action_service import (
    selection_digest,
)
from companion.asset_schema import (
    StructuredAssetSearchQuery,
)
from companion.collection_delete_service import (
    CollectionDeletePlanBusyError,
    CollectionDeletePlanError,
    CollectionDeleteService,
    tag_delete_targets,
)
from companion.immich import (
    ImmichApiError,
    ImmichTag,
)
from companion.relation_schema import (
    CollectionDeleteExecuteRequest,
    CollectionDeleteItemResult,
    CollectionDeletePlan,
    CollectionDeletePlanRequest,
    RelationMatchingSelectionRequest,
    RelationMatchingSelectionState,
    RelationSelectAllRequest,
    RelationSelectionMembershipRequest,
    RelationSelectionMembersRequest,
)
from companion.selection_repository import RelationEntityKind, RelationSelectionRepository


def matching_tag_ids(
    catalog: list[ImmichTag], query: str, include_hierarchy: bool
) -> list[UUID]:
    """Resolve matching tag rows to their real subtree members."""

    needle = query.strip().casefold()
    by_id = {tag.id: tag for tag in catalog}
    subtrees = {tag.id: [tag.id] for tag in catalog}
    for tag in catalog:
        parent_id = tag.parent_id
        visited = {tag.id}
        while parent_id is not None and parent_id in by_id and parent_id not in visited:
            subtrees[parent_id].append(tag.id)
            visited.add(parent_id)
            parent_id = by_id[parent_id].parent_id
    if not needle:
        return [tag.id for tag in catalog]

    def path(tag: ImmichTag) -> str:
        names = [tag.name]
        parent_id = tag.parent_id
        visited = {tag.id}
        while parent_id is not None and parent_id not in visited:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            names.append(parent.name)
            visited.add(parent.id)
            parent_id = parent.parent_id
        return " / ".join(reversed(names))

    matching = [
        tag
        for tag in catalog
        if needle in (path(tag) if include_hierarchy else tag.name).casefold()
    ]
    return list(dict.fromkeys(child for tag in matching for child in subtrees[tag.id]))


def register_action_duplicate_routes(
    app: FastAPI,
    *,
    relation_selection_repository,
    runtime_settings,
    require_immich,
    require_asset_repository,
    require_action_service,
    require_integrity_service,
    require_duplicate_service,
    require_similarity_scan_service,
    require_similarity_index_service,
    task_coordinator,
    action_repository,
    duplicate_review_repository,
    duplicate_discovery,
    database,
    v2_duplicate_review_state_refresh_service,
    map_action_error,
    map_immich_error,
) -> None:
    """Register relation actions, asset actions, and duplicate workflows."""

    def require_relation_selections() -> RelationSelectionRepository:
        if relation_selection_repository is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        return relation_selection_repository

    async def matching_relation_ids(
        kind: RelationEntityKind, request: RelationSelectAllRequest
    ) -> list[UUID]:
        needle = request.query.strip().casefold()
        if kind == "album":
            catalog = await require_immich().list_album_catalog()
            return [
                album.id
                for album in catalog
                if not needle
                or needle in album.album_name.casefold()
                or needle in album.description.casefold()
            ]
        catalog = await require_immich().list_tag_catalog()
        return matching_tag_ids(catalog, request.query, request.include_hierarchy)

    def register_relation_selection_routes(kind: RelationEntityKind) -> None:
        plural = f"{kind}s"

        @app.post(
            f"/api/{plural}/selections",
            response_model=SelectionSetView,
            name=f"create_{kind}_selection",
        )
        async def create_relation_selection() -> SelectionSetView:
            record = await require_relation_selections().create(
                kind, runtime_settings.action_plan_ttl_seconds
            )
            return selection_view(record)

        @app.post(
            f"/api/{plural}/selections/{{selection_id}}/members",
            response_model=SelectionSetView,
            name=f"update_{kind}_selection",
        )
        async def update_relation_selection(
            selection_id: UUID,
            request: RelationSelectionMembersRequest,
        ) -> SelectionSetView:
            try:
                record = await require_relation_selections().update(
                    selection_id,
                    kind,
                    request.ids,
                    selected=request.selected,
                    revision=request.revision,
                )
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return selection_view(record)

        @app.post(
            f"/api/{plural}/selections/{{selection_id}}/membership",
            response_model=SelectionSetMembershipResponse,
            name=f"{kind}_selection_membership",
        )
        async def relation_selection_membership(
            selection_id: UUID,
            request: RelationSelectionMembershipRequest,
        ) -> SelectionSetMembershipResponse:
            repository = require_relation_selections()
            record = await repository.get(selection_id, kind)
            if record is None:
                raise HTTPException(status_code=404, detail="Selection set was not found.")
            return SelectionSetMembershipResponse(
                selection=selection_view(record),
                selected_ids=await repository.membership(selection_id, kind, request.ids),
            )

        @app.post(
            f"/api/{plural}/selections/{{selection_id}}/select-all",
            response_model=SelectionSetView,
            name=f"select_all_{kind}_relations",
        )
        async def select_all_relations(
            selection_id: UUID,
            request: RelationSelectAllRequest,
        ) -> SelectionSetView:
            try:
                ids = await matching_relation_ids(kind, request)
                record = await require_relation_selections().replace(selection_id, kind, ids)
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return selection_view(record)

        @app.post(
            f"/api/{plural}/selections/{{selection_id}}/matching",
            response_model=SelectionSetView,
            name=f"update_matching_{kind}_relations",
        )
        async def update_matching_relations(
            selection_id: UUID,
            request: RelationMatchingSelectionRequest,
        ) -> SelectionSetView:
            try:
                ids = await matching_relation_ids(kind, request)
                record = await require_relation_selections().update_matching(
                    selection_id,
                    kind,
                    ids,
                    selected=request.selected,
                    revision=request.revision,
                )
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return selection_view(record)

        @app.post(
            f"/api/{plural}/selections/{{selection_id}}/matching-status",
            response_model=RelationMatchingSelectionState,
            name=f"{kind}_matching_selection_state",
        )
        async def relation_matching_selection_state(
            selection_id: UUID,
            request: RelationSelectAllRequest,
        ) -> RelationMatchingSelectionState:
            ids = await matching_relation_ids(kind, request)
            try:
                selected_count = await require_relation_selections().matching_count(
                    selection_id, kind, ids
                )
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return RelationMatchingSelectionState(
                matching_count=len(set(ids)), selected_matching_count=selected_count
            )

    register_relation_selection_routes("album")
    register_relation_selection_routes("tag")

    def collection_plan_view(record) -> CollectionDeletePlan:
        work = record.relation_work or {}
        results = (record.result or {}).get("items", [])
        status_value = record.status
        if status_value == "planned" and record.expires_at <= datetime.now(UTC):
            status_value = "expired"
        return CollectionDeletePlan(
            id=record.id,
            entity_kind=work["entity_kind"],
            selection_id=UUID(work["selection_id"]),
            target_digest=record.target_digest,
            target_count=len(record.target_ids),
            applicable_count=len(record.applicable_ids),
            skipped_count=len(record.skipped_ids),
            status=status_value,
            expires_at=record.expires_at,
            results=[CollectionDeleteItemResult.model_validate(item) for item in results],
        )

    @app.post("/api/{kind}s/actions/delete/plan", response_model=CollectionDeletePlan)
    async def plan_relation_delete(
        kind: RelationEntityKind, request: CollectionDeletePlanRequest
    ) -> CollectionDeletePlan:
        repository = require_relation_selections()
        if action_repository is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        try:
            target_ids = await repository.ids(request.selection_id, kind)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if not target_ids:
            raise HTTPException(status_code=400, detail="No relations are selected.")
        if kind == "album":
            existing = {item.id for item in await require_immich().list_album_catalog()}
            applicable = [identifier for identifier in target_ids if identifier in existing]
            skipped = [identifier for identifier in target_ids if identifier not in existing]
        else:
            tags = await require_immich().list_tag_catalog()
            applicable, skipped = tag_delete_targets(target_ids, tags)
        record = await action_repository.create_collection_delete_plan(
            entity_kind=kind,
            selection_id=request.selection_id,
            target_ids=target_ids,
            applicable_ids=applicable,
            skipped_ids=skipped,
            target_digest=selection_digest(target_ids),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=runtime_settings.action_plan_ttl_seconds),
        )
        return collection_plan_view(record)

    @app.post("/api/{kind}s/actions/delete/execute", response_model=CollectionDeletePlan)
    async def execute_relation_delete(
        kind: RelationEntityKind, request: CollectionDeleteExecuteRequest
    ) -> CollectionDeletePlan:
        if action_repository is None:
            raise HTTPException(status_code=503, detail="The companion database is not configured.")
        service = CollectionDeleteService(
            action_repository,
            require_relation_selections(),
            require_immich(),
            allow_destructive_actions=runtime_settings.allow_destructive_actions,
        )
        try:
            return collection_plan_view(await service.execute(kind, request.plan_id))
        except CollectionDeletePlanBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except CollectionDeletePlanError as error:
            code = 404 if "not found" in str(error) else 403 if "safe mode" in str(error) else 409
            raise HTTPException(status_code=code, detail=str(error)) from error

    @app.post("/api/assets/selection/resolve", response_model=AssetSelectionResolution)
    async def resolve_asset_selection(
        selection: AssetSelectionRequest,
    ) -> AssetSelectionResolution:
        service = require_action_service()
        try:
            resolution = await service.resolve_selection(selection)
            if selection.selection_id is not None:
                return resolution.model_copy(update={"ids": [], "missing_ids": []})
            return resolution
        except ValueError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/selection/capabilities",
        response_model=AssetSelectionCapabilities,
    )
    async def asset_selection_capabilities(
        selection: AssetSelectionRequest,
    ) -> AssetSelectionCapabilities:
        repository = require_asset_repository()
        try:
            return await repository.selection_capabilities(selection)
        except ValueError as error:
            raise map_action_error(error) from error

    @app.post(
        "/api/assets/selection/relationships",
        response_model=AssetSelectionRelationships,
    )
    async def asset_selection_relationships(
        selection: AssetSelectionRequest,
    ) -> AssetSelectionRelationships:
        repository = require_asset_repository()
        try:
            return await repository.selection_relationships(selection)
        except ValueError as error:
            raise map_action_error(error) from error

    @app.post("/api/assets/selection/ids", response_model=list[UUID])
    async def materialize_asset_selection(selection: AssetSelectionRequest) -> list[UUID]:
        repository = require_asset_repository()
        if selection.mode != "all_matching" or selection.expression is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Select-all materialization requires an all-matching expression.",
            )
        return await repository.list_matching_asset_ids(
            selection.expression, selection.excluded_ids
        )

    def selection_view(record) -> SelectionSetView:
        if record.expires_at <= datetime.now(record.expires_at.tzinfo):
            record.status = "expired"
        return SelectionSetView(
            id=record.id,
            entity_kind=record.entity_kind,
            revision=record.revision,
            selected_count=record.selected_count,
            status=record.status,
            expires_at=record.expires_at,
        )

    @app.post("/api/assets/selections", response_model=SelectionSetView)
    async def create_asset_selection() -> SelectionSetView:
        repository = require_asset_repository()
        return selection_view(
            await repository.create_selection(ttl_seconds=runtime_settings.action_plan_ttl_seconds)
        )

    @app.post(
        "/api/assets/selections/{selection_id}/select-all",
        response_model=SelectionSetView,
    )
    async def select_all_asset_selection(
        selection_id: UUID,
        expression: StructuredAssetSearchQuery,
    ) -> SelectionSetView:
        repository = require_asset_repository()
        try:
            record = await repository.replace_selection_with_matching(
                selection_id, expression.expression
            )
        except ValueError as error:
            raise map_action_error(error) from error
        return selection_view(record)

    @app.post(
        "/api/assets/selections/{selection_id}/members",
        response_model=SelectionSetView,
    )
    async def update_asset_selection_members(
        selection_id: UUID,
        request: SelectionSetMembersRequest,
    ) -> SelectionSetView:
        repository = require_asset_repository()
        try:
            record = await repository.update_selection_members(
                selection_id,
                request.asset_ids,
                selected=request.selected,
                revision=request.revision,
            )
        except ValueError as error:
            raise map_action_error(error) from error
        return selection_view(record)

    @app.post(
        "/api/assets/selections/{selection_id}/membership",
        response_model=SelectionSetMembershipResponse,
    )
    async def asset_selection_membership(
        selection_id: UUID,
        request: SelectionSetMembershipRequest,
    ) -> SelectionSetMembershipResponse:
        repository = require_asset_repository()
        record = await repository.get_selection(selection_id)
        if record is None or record.entity_kind != "asset":
            raise HTTPException(status_code=404, detail="Selection set was not found.")
        return SelectionSetMembershipResponse(
            selection=selection_view(record),
            selected_ids=await repository.selection_membership(selection_id, request.asset_ids),
        )

    @app.post("/api/assets/actions/plan", response_model=AssetActionPlan)
    async def plan_asset_action(request: AssetActionPlanRequest) -> AssetActionPlan:
        service = require_action_service()
        try:
            return await service.plan(request)
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.post("/api/assets/actions/execute", response_model=AssetActionResult)
    async def execute_asset_action(
        request: AssetActionExecuteRequest,
    ) -> AssetActionResult:
        service = require_action_service()
        try:
            return await service.execute(request)
        except ImmichApiError as error:
            raise map_immich_error(error) from error
        except (RuntimeError, ValueError) as error:
            raise map_action_error(error) from error

    @app.post("/api/assets/actions/execute-task", response_model=AssetActionTaskStart)
    async def execute_asset_action_task(
        request: AssetActionExecuteRequest,
    ) -> AssetActionTaskStart:
        if task_coordinator is None:
            raise HTTPException(status_code=503, detail="Task coordinator is unavailable.")
        task = await task_coordinator.submit(
            "asset_action",
            {"plan_id": str(request.plan_id)},
            priority=80,
            lane_key="asset_action",
            deduplication_key=f"plan:{request.plan_id}",
        )
        await task_coordinator.start()
        return AssetActionTaskStart(task_id=task.id)
