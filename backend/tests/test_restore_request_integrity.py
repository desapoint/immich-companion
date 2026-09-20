"""Restore target validation and accounting contract tests."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from companion.immich import ImmichApiError
from companion.main import RestoreRequest, restore_batch_with_accounting


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
