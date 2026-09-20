"""Restore target validation and accounting contract tests."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from companion.config import Settings
from companion.immich import ImmichApiError
from companion.main import RestoreRequest, create_app, restore_batch_with_accounting

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")


def test_restore_request_accepts_server_side_exclusions() -> None:
    request = RestoreRequest(all=True, excluded_ids=[ASSET_TWO])

    assert request.ids == []
    assert request.excluded_ids == [ASSET_TWO]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"all": True, "ids": [ASSET_ONE]},
        {"ids": [ASSET_ONE], "excluded_ids": [ASSET_TWO]},
        {"all": True, "excluded_ids": [ASSET_TWO, ASSET_TWO]},
    ],
)
def test_restore_request_rejects_ambiguous_or_duplicate_targets(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RestoreRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_restore_batch_response_accounts_for_provider_partial_success() -> None:
    states = {ASSET_ONE: False, ASSET_TWO: True}

    async def restore(_asset_ids: list[UUID]) -> None:
        states[ASSET_ONE] = False
        raise ImmichApiError("restore", 503)

    async def get_asset(asset_id: UUID) -> object:
        return type("Asset", (), {"is_trashed": states[asset_id]})()

    restored, failed = await restore_batch_with_accounting(
        [ASSET_ONE, ASSET_TWO], restore, get_asset
    )

    assert restored == 1
    assert failed == [ASSET_TWO]


def test_restore_endpoint_uses_async_trash_iterator_and_exclusions() -> None:
    class FakeAsset:
        def __init__(self, asset_id: UUID) -> None:
            self.id = asset_id
            self.is_trashed = True

    class FakeImmich:
        def __init__(self) -> None:
            self.assets = [FakeAsset(ASSET_ONE), FakeAsset(ASSET_TWO)]

        async def iter_trashed_assets(self):
            for asset in self.assets:
                yield asset

        async def get_asset(self, asset_id: UUID) -> FakeAsset:
            return next(asset for asset in self.assets if asset.id == asset_id)

    class FakeRuntimeSettings:
        full_batch_size = 50
        full_min_batch_delay_seconds = 0

        async def get(self) -> FakeRuntimeSettings:
            return self

    class FakeSync:
        _runtime_sync_settings = FakeRuntimeSettings()

        def __init__(self) -> None:
            self.restored: list[list[UUID]] = []

        async def restore_targets(self, asset_ids: list[UUID]) -> None:
            self.restored.append(asset_ids)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 3, "minor": 1, "patch": 0})
        return httpx.Response(200, json={"res": "pong"})

    app = create_app(
        Settings(
            companion_env="test",
            companion_version="test",
            immich_url="http://immich.test",
            immich_api_key="test-key",
        ),
        httpx.MockTransport(handler),
    )
    fake_immich = FakeImmich()
    fake_sync = FakeSync()
    app.state.immich_override = fake_immich
    app.state.asset_sync_override = fake_sync

    with TestClient(app) as client:
        response = client.post(
            "/api/restore",
            json={"all": True, "excluded_ids": [str(ASSET_TWO)]},
        )

    assert response.status_code == 200
    assert response.json() == {"restored": 1, "requested": 1, "failed_ids": []}
    assert fake_sync.restored == [[ASSET_ONE]]
