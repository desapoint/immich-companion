"""Regression coverage for persisted selection route registration."""

from fastapi.testclient import TestClient

from companion.config import Settings
from companion.main import create_app


def settings() -> Settings:
    return Settings(
        companion_env="test",
        companion_version="test-version",
        immich_url="http://immich.test",
        immich_api_key="test-key",
        allow_destructive_actions=False,
    )


def test_selection_routes_are_static_and_do_not_shadow_assets_or_duplicates() -> None:
    app = create_app(settings())
    paths = {getattr(route, "path", "") for route in app.routes}

    relation_suffixes = (
        "/selections",
        "/selections/{selection_id}/members",
        "/selections/{selection_id}/membership",
        "/selections/{selection_id}/select-all",
        "/selections/{selection_id}/matching",
        "/selections/{selection_id}/matching-status",
    )
    for namespace in ("albums", "tags"):
        for suffix in relation_suffixes:
            assert f"/api/{namespace}{suffix}" in paths

    assert not any(path.startswith("/api/{kind}s/selections") for path in paths)
    assert "/api/assets/selections" in paths
    assert "/api/assets/duplicates/workspace" in paths

    with TestClient(app) as client:
        asset_selection = client.post("/api/assets/selections", json={})
        album_selection = client.post("/api/albums/selections", json={})
        tag_selection = client.post("/api/tags/selections", json={})
        duplicate_workspace = client.get("/api/assets/duplicates/workspace")

    for response in (
        asset_selection,
        album_selection,
        tag_selection,
        duplicate_workspace,
    ):
        assert response.status_code == 503
        assert response.json()["detail"] == "The companion database is not configured."
