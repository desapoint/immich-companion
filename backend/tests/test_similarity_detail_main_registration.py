"""Keep the localized diagnostics router wired into the real application factory."""

from fastapi.testclient import TestClient

from companion.config import Settings
from companion.main import create_app


def test_main_app_registers_local_change_diagnostics_route() -> None:
    app = create_app(Settings(
        companion_env="test",
        companion_version="test-version",
        immich_url=None,
        immich_api_key=None,
    ))

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/api/v2/duplicates/similarity-local-changes" in paths

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/duplicates/similarity-local-changes",
            params={
                "selected_asset_id": "11111111-1111-4111-8111-111111111111",
                "reference_asset_id": "22222222-2222-4222-8222-222222222222",
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "The companion database is not configured."
