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


def test_video_playback_is_streamed_with_range_metadata() -> None:
    asset_id = "11111111-1111-4111-8111-111111111111"
    payload = b"compatible-video-range"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        assert request.headers["range"] == "bytes=0-21"
        assert request.url.path == f"/api/assets/{asset_id}/video/playback"
        return httpx.Response(
            206,
            content=payload,
            headers={
                "content-type": "video/mp4",
                "content-length": str(len(payload)),
                "content-range": "bytes 0-21/220",
                "accept-ranges": "bytes",
                "etag": '"playback-etag"',
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
        response = client.get(
            f"/api/assets/{asset_id}/video/playback",
            headers={"range": "bytes=0-21"},
        )

    assert response.status_code == 206
    assert response.content == payload
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-range"] == "bytes 0-21/220"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["etag"] == '"playback-etag"'
