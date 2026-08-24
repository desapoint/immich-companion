"""Asset synchronization service."""

from datetime import UTC, datetime

from companion.asset_repository import AssetRepository
from companion.asset_schema import AssetSyncResult
from companion.immich import ImmichApiClient


class AssetSyncService:
    """Reconcile a complete Immich asset traversal into companion storage."""

    def __init__(self, immich: ImmichApiClient, repository: AssetRepository) -> None:
        self._immich = immich
        self._repository = repository

    async def synchronize(self) -> AssetSyncResult:
        """Run one complete, idempotent asset metadata reconciliation."""

        assets = [asset async for asset in self._immich.iter_assets()]
        stacks = await self._immich.list_stacks()
        stack_by_asset = {}
        for stack in stacks:
            stack_members = [
                {
                    "id": str(member.id),
                    "type": member.asset_type,
                    "originalFileName": member.original_file_name,
                    "originalMimeType": member.original_mime_type,
                    "width": member.width,
                    "height": member.height,
                    "fileCreatedAt": member.file_created_at.isoformat(),
                }
                for member in stack.assets
            ]
            stack_payload = {
                "id": str(stack.id),
                "primaryAssetId": str(stack.primary_asset_id),
                "assetCount": len(stack.assets),
                "assets": stack_members,
            }
            for member in stack.assets:
                stack_by_asset[member.id] = stack_payload
        assets = [
            asset.model_copy(update={"stack": stack_by_asset.get(asset.id, asset.stack)})
            for asset in assets
        ]
        albums = await self._immich.list_albums(assets)
        created, updated, removed = await self._repository.reconcile(assets, albums)
        return AssetSyncResult(
            seen=len(assets),
            created=created,
            updated=updated,
            removed=removed,
            completed_at=datetime.now(UTC),
        )
