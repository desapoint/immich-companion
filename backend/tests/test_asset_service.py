from uuid import UUID

import pytest

from companion.asset_service import AssetSyncService
from companion.immich import ImmichAsset, ImmichStack, ImmichTag

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
STACK_ID = UUID("55555555-5555-4555-8555-555555555555")
TAG_ID = UUID("66666666-6666-4666-8666-666666666666")


def asset(asset_id: UUID, filename: str) -> ImmichAsset:
    return ImmichAsset.model_validate(
        {
            "id": str(asset_id),
            "type": "IMAGE",
            "originalFileName": filename,
            "originalMimeType": "image/png",
            "width": 800,
            "height": 600,
            "fileCreatedAt": "2026-08-24T12:00:00Z",
            "fileModifiedAt": "2026-08-24T12:00:00Z",
        }
    )


class FakeImmich:
    def __init__(self, assets: list[ImmichAsset], stack: ImmichStack) -> None:
        self.assets = assets
        self.stack = stack

    async def iter_assets(self):
        for current in self.assets:
            yield current

    async def list_stacks(self) -> list[ImmichStack]:
        return [self.stack]

    async def list_albums(self, _assets: list[ImmichAsset]) -> list[object]:
        return []

    async def list_tags(self, _assets: list[ImmichAsset]) -> list[ImmichTag]:
        return [
            ImmichTag(
                id=TAG_ID,
                name="Review",
                value="Review",
                color="#d97706",
                asset_ids=[ASSET_ONE],
            )
        ]


class FakeRepository:
    def __init__(self) -> None:
        self.assets: list[ImmichAsset] = []

    async def reconcile(
        self,
        assets: list[ImmichAsset],
        _albums: list[object],
    ) -> tuple[int, int, int]:
        self.assets = assets
        return len(assets), 0, 0


@pytest.mark.asyncio
async def test_sync_retains_compact_stack_members_for_card_previews() -> None:
    members = [asset(ASSET_ONE, "primary.png"), asset(ASSET_TWO, "child.png")]
    stack = ImmichStack(id=STACK_ID, primaryAssetId=ASSET_ONE, assets=members)
    immich = FakeImmich(members, stack)
    repository = FakeRepository()

    result = await AssetSyncService(immich, repository).synchronize()  # type: ignore[arg-type]

    assert result.seen == 2
    assert repository.assets[0].stack is not None
    assert repository.assets[0].stack["primaryAssetId"] == str(ASSET_ONE)
    assert [member["id"] for member in repository.assets[0].stack["assets"]] == [
        str(ASSET_ONE),
        str(ASSET_TWO),
    ]
    assert repository.assets[0].stack["assets"][1]["originalFileName"] == "child.png"
    assert repository.assets[0].tags == [
        {
            "id": str(TAG_ID),
            "name": "Review",
            "value": "Review",
            "color": "#d97706",
        }
    ]
    assert repository.assets[1].tags == []
