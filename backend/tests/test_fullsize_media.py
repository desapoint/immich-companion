import httpx
from fastapi.testclient import TestClient

from companion.config import Settings
from companion.main import create_app


def test_fullsize_asset_media_is_proxied_to_immich() -> None:
    asset_id = "11111111-1111-4111-8111-111111111111"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        assert request.url.path == f"/api/assets/{asset_id}/thumbnail"
        assert request.url.params["size"] == "fullsize"
        return httpx.Response(
            200,
            content=b"converted-fullsize-bytes",
            headers={
                "content-type": "image/jpeg",
                "etag": '"fullsize-etag"',
                "cache-control": "private, max-age=600",
            },
        )

    settings = Settings(
        companion_env="test",
        companion_version="test-version",
        immich_url="http://immich.test",
        immich_api_key="test-key",
        allow_destructive_actions=False,
    )

    with TestClient(create_app(settings, httpx.MockTransport(handler))) as client:
        response = client.get(f"/api/assets/{asset_id}/thumbnail?size=fullsize")

    assert response.status_code == 200
    assert response.content == b"converted-fullsize-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["etag"] == '"fullsize-etag"'
    assert response.headers["cache-control"] == "private, max-age=600"
