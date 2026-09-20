"""Album and tag management route registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response

from companion.asset_schema import TagOption
from companion.immich import ImmichAlbum, ImmichApiError, ImmichTag
from companion.relation_schema import (
    AlbumCreateRequest,
    AlbumManagementItem,
    AlbumUpdateRequest,
    RelationBatchDeleteRequest,
    RelationPage,
    TagCreateRequest,
    TagManagementItem,
    TagUpdateRequest,
)


def register_relation_management_routes(
    app: FastAPI,
    *,
    require_immich: Callable[[], object],
    require_asset_repository: Callable[[], object],
    tag_subtree_ids: Callable[[list[ImmichTag]], dict[UUID, list[UUID]]],
) -> None:
    """Register album and tag catalog management endpoints."""

    def album_management_item(
        album: ImmichAlbum, *, asset_count: int | None = None
    ) -> AlbumManagementItem:
        return AlbumManagementItem(
            id=album.id,
            name=album.album_name,
            description=album.description,
            album_thumbnail_asset_id=album.album_thumbnail_asset_id,
            asset_count=album.asset_count if asset_count is None else asset_count,
            created_at=album.created_at,
            updated_at=album.updated_at,
        )

    @app.get("/api/albums/manage", response_model=RelationPage[AlbumManagementItem])
    async def manage_albums(
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=200),
        search: str | None = Query(None, max_length=255),
        sort: Literal["name", "asset_count", "description"] = "name",
        direction: Literal["asc", "desc"] = "asc",
    ):
        albums = await require_immich().list_album_catalog()
        counts = await require_asset_repository().album_asset_counts()
        if search:
            needle = search.casefold()
            albums = [
                album
                for album in albums
                if needle in album.album_name.casefold() or needle in album.description.casefold()
            ]
        albums.sort(
            key=lambda album: (
                album.album_name.casefold()
                if sort == "name"
                else album.description.casefold()
                if sort == "description"
                else counts.get(album.id, 0)
            ),
            reverse=direction == "desc",
        )
        total = len(albums)
        start = (page - 1) * page_size
        items = [
            album_management_item(album, asset_count=counts.get(album.id, 0))
            for album in albums[start : start + page_size]
        ]
        return RelationPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @app.get("/api/albums/manage/{album_id}", response_model=AlbumManagementItem)
    async def get_managed_album(album_id: UUID) -> AlbumManagementItem:
        return album_management_item(await require_immich().get_album(album_id))

    @app.post("/api/albums/manage", response_model=AlbumManagementItem)
    async def create_managed_album(request: AlbumCreateRequest):
        album = await require_immich().create_album(request.name, request.description)
        return album_management_item(
            album
        )

    @app.post("/api/albums/manage/batch-delete")
    async def batch_delete_albums(request: RelationBatchDeleteRequest):
        client = require_immich()
        completed: list[UUID] = []
        failed: list[UUID] = []
        for identifier in request.ids:
            try:
                await client.delete_album(identifier)
            except ImmichApiError:
                failed.append(identifier)
            else:
                completed.append(identifier)
        return {"completed": completed, "failed": failed, "total": len(request.ids)}

    @app.patch("/api/albums/manage/{album_id}", response_model=AlbumManagementItem)
    async def update_managed_album(album_id: UUID, request: AlbumUpdateRequest):
        album = await require_immich().update_album(
            album_id, name=request.name, description=request.description
        )
        return album_management_item(album)

    @app.delete("/api/albums/manage/{album_id}", status_code=204)
    async def delete_managed_album(album_id: UUID) -> Response:
        await require_immich().delete_album(album_id)
        return Response(status_code=204)

    @app.get("/api/tags", response_model=list[TagOption])
    async def search_tag_options() -> list[TagOption]:
        repository = require_asset_repository()
        return await repository.list_tags()

    @app.get("/api/tags/manage", response_model=RelationPage[TagManagementItem])
    async def manage_tags(
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=200),
        search: str | None = Query(None, max_length=255),
        sort: Literal["name", "asset_count", "path", "child_count"] = "name",
        direction: Literal["asc", "desc"] = "asc",
        flat: bool = False,
        include_hierarchy: bool = False,
    ):
        catalog = await require_immich().list_tag_catalog()
        counts = await require_asset_repository().tag_asset_counts()
        tags_by_id = {tag.id: tag for tag in catalog}
        subtree_ids = tag_subtree_ids(catalog)
        children_by_parent: dict[UUID, list[ImmichTag]] = {}
        roots: list[ImmichTag] = []
        for tag in catalog:
            if tag.parent_id is not None and tag.parent_id in tags_by_id:
                children_by_parent.setdefault(tag.parent_id, []).append(tag)
            else:
                roots.append(tag)

        def resolve_parent_path(tag: ImmichTag) -> list[str]:
            path: list[str] = []
            parent_id = tag.parent_id
            visited = {tag.id}
            while parent_id is not None and parent_id not in visited:
                parent = tags_by_id.get(parent_id)
                if parent is None:
                    break
                path.append(parent.name)
                visited.add(parent.id)
                parent_id = parent.parent_id
            return list(reversed(path))

        parent_paths = {tag.id: resolve_parent_path(tag) for tag in catalog}

        def canonical_path(tag: ImmichTag) -> str:
            return " / ".join([*parent_paths[tag.id], tag.name])

        def sort_key(tag: ImmichTag) -> str | int:
            if sort == "asset_count":
                return counts.get(tag.id, 0)
            if sort == "child_count":
                return len(children_by_parent.get(tag.id, []))
            if sort == "path":
                return canonical_path(tag).casefold()
            return tag.name.casefold()

        def management_item(
            tag: ImmichTag, *, children: list[TagManagementItem] | None = None
        ) -> TagManagementItem:
            return TagManagementItem(
                id=tag.id,
                name=tag.name,
                color=tag.color,
                parent_id=tag.parent_id,
                parent_path=parent_paths[tag.id],
                asset_count=counts.get(tag.id, 0),
                child_count=len(children_by_parent.get(tag.id, [])),
                real_tag_ids=subtree_ids[tag.id],
                children=children or [],
            )

        needle = search.casefold().strip() if search else ""
        if flat:
            matching_tags = [
                tag
                for tag in catalog
                if not needle
                or needle in tag.name.casefold()
                or (include_hierarchy and needle in canonical_path(tag).casefold())
            ]
            matching_tags.sort(key=sort_key, reverse=direction == "desc")
            total = len(matching_tags)
            start = (page - 1) * page_size
            return RelationPage(
                items=[management_item(tag) for tag in matching_tags[start : start + page_size]],
                total=total,
                page=page,
                page_size=page_size,
                pages=(total + page_size - 1) // page_size,
            )

        matching_ids = {tag.id for tag in catalog if not needle or needle in tag.name.casefold()}
        included_ids = set(matching_ids)
        for tag in catalog:
            if tag.id not in matching_ids:
                continue
            parent_id = tag.parent_id
            visited = {tag.id}
            while parent_id is not None and parent_id not in visited:
                included_ids.add(parent_id)
                visited.add(parent_id)
                parent = tags_by_id.get(parent_id)
                parent_id = parent.parent_id if parent is not None else None

        def build_node(tag: ImmichTag) -> TagManagementItem | None:
            if tag.id not in included_ids:
                return None
            child_nodes = [
                node
                for child in sorted(
                    children_by_parent.get(tag.id, []), key=sort_key, reverse=direction == "desc"
                )
                if (node := build_node(child)) is not None
            ]
            return management_item(tag, children=child_nodes)

        visible_roots = [
            node
            for root in sorted(roots, key=sort_key, reverse=direction == "desc")
            if (node := build_node(root)) is not None
        ]
        total = len(visible_roots)
        start = (page - 1) * page_size
        items = visible_roots[start : start + page_size]
        return RelationPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    @app.get("/api/tags/manage/{tag_id}", response_model=TagManagementItem)
    async def get_managed_tag(tag_id: UUID) -> TagManagementItem:
        catalog = await require_immich().list_tag_catalog()
        tags_by_id = {tag.id: tag for tag in catalog}
        tag = tags_by_id.get(tag_id)
        if tag is None:
            raise HTTPException(status_code=404, detail="Tag not found.")
        path: list[str] = []
        parent_id = tag.parent_id
        visited = {tag.id}
        while parent_id is not None and parent_id not in visited:
            parent = tags_by_id.get(parent_id)
            if parent is None:
                break
            path.append(parent.name)
            visited.add(parent.id)
            parent_id = parent.parent_id
        return TagManagementItem(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            parent_id=tag.parent_id,
            parent_path=list(reversed(path)),
            asset_count=tag.asset_count,
            child_count=sum(item.parent_id == tag.id for item in catalog),
            real_tag_ids=tag_subtree_ids(catalog)[tag.id],
        )

    @app.post("/api/tags/manage", response_model=TagManagementItem)
    async def create_managed_tag(request: TagCreateRequest):
        tag = await require_immich().create_tag(request.name, request.color, request.parent_id)
        return TagManagementItem(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            parent_id=tag.parent_id,
            asset_count=tag.asset_count,
            real_tag_ids=[tag.id],
        )

    @app.post("/api/tags/manage/batch-delete")
    async def batch_delete_tags(request: RelationBatchDeleteRequest):
        client = require_immich()
        catalog = await client.list_tag_catalog()
        children = {tag.parent_id for tag in catalog if tag.parent_id is not None}
        completed: list[UUID] = []
        failed: list[UUID] = [identifier for identifier in request.ids if identifier in children]
        for identifier in request.ids:
            if identifier in children:
                continue
            try:
                await client.delete_tag(identifier)
            except ImmichApiError:
                failed.append(identifier)
            else:
                completed.append(identifier)
        return {"completed": completed, "failed": failed, "total": len(request.ids)}

    @app.patch("/api/tags/manage/{tag_id}", response_model=TagManagementItem)
    async def update_managed_tag(tag_id: UUID, request: TagUpdateRequest):
        client = require_immich()
        tag = await client.update_tag(tag_id, color=request.color)
        return TagManagementItem(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            parent_id=tag.parent_id,
            asset_count=tag.asset_count,
        )

    @app.delete("/api/tags/manage/{tag_id}", status_code=204)
    async def delete_managed_tag(tag_id: UUID) -> Response:
        client = require_immich()
        if any(tag.parent_id == tag_id for tag in await client.list_tag_catalog()):
            raise HTTPException(
                status_code=409, detail="Delete child tags before deleting this parent tag."
            )
        await client.delete_tag(tag_id)
        return Response(status_code=204)
