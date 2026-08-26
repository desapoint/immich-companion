"""Create a relationship-only divergence for the disposable full-sync test."""

import os

import httpx


asset_id = "0197a42c-a2b2-4f05-bc56-c4b8dce933cf"
album_id = "5cfe4494-8314-44ae-8698-2369b761b5fd"
tag_id = "5d248da3-9f06-4d68-925b-afa8cb9e2d89"

with httpx.Client(base_url="http://immich-server:2283", timeout=60) as client:
    login = client.post(
        "/api/auth/login",
        json={
            "email": os.environ["IMMICH_TEST_ADMIN_EMAIL"],
            "password": os.environ["IMMICH_TEST_ADMIN_PASSWORD"],
        },
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    album = client.request(
        "DELETE", f"/api/albums/{album_id}/assets", headers=headers, json={"ids": [asset_id]}
    )
    tag = client.request(
        "DELETE", f"/api/tags/{tag_id}/assets", headers=headers, json={"ids": [asset_id]}
    )
    album.raise_for_status()
    tag.raise_for_status()
    print("relationship divergence prepared")
