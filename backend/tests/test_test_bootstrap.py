"""Focused tests for deterministic Immich bootstrap reconciliation."""

import json

import httpx

from companion import test_bootstrap
from companion.test_bootstrap import has_reusable_state, reconcile_tags


def test_reusable_bootstrap_state_requires_a_previous_success(tmp_path) -> None:
    state_path = tmp_path / "bootstrap-state.json"

    assert has_reusable_state(state_path) is False

    state_path.write_text('{"ready": false}', encoding="utf-8")
    assert has_reusable_state(state_path) is False

    state_path.write_text('{"ready": true}', encoding="utf-8")
    assert has_reusable_state(state_path) is True

    state_path.write_text("not-json", encoding="utf-8")
    assert has_reusable_state(state_path) is False


def test_bootstrap_skips_all_immich_work_when_state_is_already_ready(
    tmp_path, monkeypatch
) -> None:
    state_path = tmp_path / "bootstrap-state.json"
    state_path.write_text('{"ready": true}', encoding="utf-8")
    values = {
        "IMMICH_URL": "http://immich.test",
        "IMMICH_TEST_ADMIN_EMAIL": "admin@example.test",
        "IMMICH_TEST_ADMIN_PASSWORD": "test-password",
        "IMMICH_TEST_ADMIN_NAME": "Test Admin",
        "IMMICH_API_KEY_FILE": str(tmp_path / "api-key"),
        "COMPANION_TEST_STATE_FILE": str(state_path),
        "COMPANION_TEST_SEED_DIR": str(tmp_path / "seed"),
        "COMPANION_TEST_RESET_MODE": "false",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    def fail_if_bootstrap_continues(*_args, **_kwargs):
        raise AssertionError("Existing state must prevent fixture reconciliation")

    monkeypatch.setattr(test_bootstrap, "load_manifest", fail_if_bootstrap_continues)

    test_bootstrap.main()


def test_resolve_api_key_reuses_the_persisted_valid_secret(
    tmp_path, monkeypatch
) -> None:
    key_path = tmp_path / "api-key"
    key_path.write_text("stable-test-key\n", encoding="utf-8")
    monkeypatch.setattr(test_bootstrap, "api_key_is_valid", lambda *_args: True)
    monkeypatch.setattr(
        test_bootstrap,
        "create_api_key",
        lambda *_args: (_ for _ in ()).throw(AssertionError("API key must not rotate")),
    )

    assert test_bootstrap.resolve_api_key(object(), "token", key_path) == "stable-test-key"
    assert key_path.read_text(encoding="utf-8") == "stable-test-key\n"


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
