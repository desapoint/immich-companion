"""Focused tests for deterministic Immich bootstrap reconciliation."""

import json

import httpx

from companion.test_bootstrap import reconcile_tags


def test_reconcile_tags_creates_updates_and_converges_seed_assignments() -> None:
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": "tag-existing", "name": "Existing", "color": "#000000"}],
            )
        if request.method == "POST":
            return httpx.Response(
                201,
                json={"id": "tag-created", "name": "Created", "color": "#222222"},
            )
        return httpx.Response(200, json=[])

    relationships = {
        "tags": [
            {"name": "Existing", "color": "#111111", "paths": ["one", "two"]},
            {"name": "Created", "color": "#222222", "paths": ["two", "three"]},
        ]
    }
    asset_ids = {"one": "asset-one", "two": "asset-two", "three": "asset-three"}

    with httpx.Client(
        base_url="http://immich.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = reconcile_tags(client, "test-key", relationships, asset_ids)

    assert result == {"tags": 2, "tagged_assets": 3, "tag_assignments": 4}
    assert ("PATCH", "/api/tags/tag-existing", {"color": "#111111"}) in requests
    assert (
        "PUT",
        "/api/tags/tag-existing/assets",
        {"ids": ["asset-one", "asset-two"]},
    ) in requests
    assert (
        "DELETE",
        "/api/tags/tag-existing/assets",
        {"ids": ["asset-three"]},
    ) in requests
    assert ("POST", "/api/tags", {"name": "Created", "color": "#222222"}) in requests
    assert (
        "PUT",
        "/api/tags/tag-created/assets",
        {"ids": ["asset-three", "asset-two"]},
    ) in requests
