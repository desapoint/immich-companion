"""Idempotently provision the disposable Immich integration environment."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx

FIXED_MEDIA_TIME = "2025-01-15T12:00:00.000Z"


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is missing")
    return value


def wait_for_immich(client: httpx.Client, timeout_seconds: int = 240) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = client.get("/api/server/ping")
            if response.is_success:
                return
        except httpx.RequestError:
            pass
        time.sleep(2)
    raise RuntimeError("Immich did not become reachable before bootstrap timed out")


def login(client: httpx.Client, email: str, password: str, name: str) -> str:
    sign_up = client.post(
        "/api/auth/admin-sign-up",
        json={"email": email, "password": password, "name": name},
    )
    if sign_up.status_code not in {201, 400, 409}:
        sign_up.raise_for_status()

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    token = response.json().get("accessToken")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Immich login response did not contain an access token")
    return token


def api_key_is_valid(client: httpx.Client, api_key: str) -> bool:
    response = client.get("/api/assets/statistics", headers={"x-api-key": api_key})
    return response.is_success


def create_api_key(client: httpx.Client, access_token: str) -> str:
    response = client.post(
        "/api/api-keys",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"name": "Immich Companion disposable test key", "permissions": ["all"]},
    )
    response.raise_for_status()
    secret = response.json().get("secret")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("Immich API-key response did not contain a secret")
    return secret


def write_private_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, 0o600)
    with suppress(PermissionError):
        os.chown(temporary, 10001, 10001)
    temporary.replace(path)


def resolve_api_key(client: httpx.Client, access_token: str, path: Path) -> str:
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing and api_key_is_valid(client, existing):
            return existing

    api_key = create_api_key(client, access_token)
    write_private_file(path, api_key + "\n")
    return api_key


def load_manifest(seed_root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = seed_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2 or not isinstance(manifest.get("files"), list):
        raise RuntimeError("Unsupported or invalid deterministic media manifest")
    return manifest, manifest_path


def upload_assets(
    client: httpx.Client,
    api_key: str,
    seed_root: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    created = 0
    duplicates = 0
    asset_ids: dict[str, str] = {}
    for record in manifest["files"]:
        relative_path = record.get("path")
        if not isinstance(relative_path, str):
            raise RuntimeError("Media manifest contains an invalid path")
        media_path = (seed_root / relative_path).resolve()
        if seed_root.resolve() not in media_path.parents:
            raise RuntimeError("Media manifest path escapes the seed directory")

        content_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
        with media_path.open("rb") as media:
            response = client.post(
                "/api/assets",
                headers={"x-api-key": api_key},
                data={
                    "fileCreatedAt": FIXED_MEDIA_TIME,
                    "fileModifiedAt": FIXED_MEDIA_TIME,
                    "filename": media_path.name,
                },
                files={"assetData": (media_path.name, media, content_type)},
            )
        response.raise_for_status()
        payload = response.json()
        status = payload.get("status")
        asset_id = payload.get("id")
        if not isinstance(asset_id, str) or not asset_id:
            raise RuntimeError("Immich upload response did not contain an asset ID")
        asset_ids[relative_path] = asset_id
        if status == "created":
            created += 1
        elif status == "duplicate":
            duplicates += 1
        else:
            raise RuntimeError(f"Immich returned an unexpected upload status: {status!r}")
    return {"created": created, "duplicates": duplicates, "asset_ids": asset_ids}


def manifest_relationships(manifest: dict[str, Any]) -> dict[str, Any]:
    relationships = manifest.get("relationships")
    if not isinstance(relationships, dict):
        raise RuntimeError("Media manifest does not define relationships")
    return relationships


def resolve_paths(asset_ids: dict[str, str], paths: object, label: str) -> list[str]:
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise RuntimeError(f"Media manifest contains invalid {label} paths")
    try:
        return list(dict.fromkeys(asset_ids[path] for path in paths))
    except KeyError as error:
        raise RuntimeError(f"Media manifest {label} references an unknown path") from error


def reconcile_albums(
    client: httpx.Client,
    api_key: str,
    relationships: dict[str, Any],
    asset_ids: dict[str, str],
) -> int:
    headers = {"x-api-key": api_key}
    configured = relationships.get("albums")
    if not isinstance(configured, list):
        raise RuntimeError("Media manifest albums must be a list")

    response = client.get("/api/albums", headers=headers, params={"isOwned": "true"})
    response.raise_for_status()
    existing = {
        album.get("albumName"): album
        for album in response.json()
        if isinstance(album, dict) and isinstance(album.get("albumName"), str)
    }

    desired_by_name: dict[str, set[str]] = {}
    album_ids_by_name: dict[str, str] = {}
    for album in configured:
        if not isinstance(album, dict):
            raise RuntimeError("Media manifest contains an invalid album")
        name = album.get("name")
        description = album.get("description", "")
        if not isinstance(name, str) or not isinstance(description, str):
            raise RuntimeError("Media manifest contains invalid album metadata")
        desired_ids = resolve_paths(asset_ids, album.get("paths"), f"album {name}")
        desired_by_name[name] = set(desired_ids)
        current = existing.get(name)
        if current is None:
            created = client.post(
                "/api/albums",
                headers=headers,
                json={"albumName": name, "description": description, "assetIds": desired_ids},
            )
            created.raise_for_status()
            album_id = created.json().get("id")
        else:
            album_id = current.get("id")
            if isinstance(album_id, str):
                updated = client.patch(
                    f"/api/albums/{album_id}",
                    headers=headers,
                    json={"albumName": name, "description": description},
                )
                updated.raise_for_status()
                if desired_ids:
                    added = client.put(
                        f"/api/albums/{album_id}/assets",
                        headers=headers,
                        json={"ids": desired_ids},
                    )
                    added.raise_for_status()
        if not isinstance(album_id, str):
            raise RuntimeError(f"Immich album {name!r} did not provide an ID")
        album_ids_by_name[name] = album_id

    # Remove seed assets from a managed album when the manifest does not assign
    # them there, preserving unrelated user albums even in the disposable stack.
    for asset_id in set(asset_ids.values()):
        membership = client.get("/api/albums", headers=headers, params={"assetId": asset_id})
        membership.raise_for_status()
        for album in membership.json():
            name = album.get("albumName") if isinstance(album, dict) else None
            album_id = album.get("id") if isinstance(album, dict) else None
            if (
                isinstance(name, str)
                and isinstance(album_id, str)
                and name in desired_by_name
                and asset_id not in desired_by_name[name]
            ):
                removed = client.request(
                    "DELETE",
                    f"/api/albums/{album_id}/assets",
                    headers=headers,
                    json={"ids": [asset_id]},
                )
                removed.raise_for_status()
    return len(album_ids_by_name)


def reconcile_stacks(
    client: httpx.Client,
    api_key: str,
    relationships: dict[str, Any],
    asset_ids: dict[str, str],
) -> int:
    configured = relationships.get("stacks")
    if not isinstance(configured, list):
        raise RuntimeError("Media manifest stacks must be a list")
    desired = [
        resolve_paths(asset_ids, stack.get("paths"), "stack")
        for stack in configured
        if isinstance(stack, dict)
    ]
    if len(desired) != len(configured) or any(len(stack) < 2 for stack in desired):
        raise RuntimeError("Media manifest contains an invalid stack")

    headers = {"x-api-key": api_key}
    response = client.get("/api/stacks", headers=headers)
    response.raise_for_status()
    seed_ids = set(asset_ids.values())
    managed: list[dict[str, Any]] = []
    existing_sets: list[frozenset[str]] = []
    for stack in response.json():
        if not isinstance(stack, dict):
            continue
        members = {
            asset.get("id")
            for asset in stack.get("assets", [])
            if isinstance(asset, dict) and isinstance(asset.get("id"), str)
        }
        if members & seed_ids:
            managed.append(stack)
            existing_sets.append(frozenset(members))

    desired_sets = [frozenset(stack) for stack in desired]
    if sorted(existing_sets, key=sorted) == sorted(desired_sets, key=sorted):
        return len(desired)

    stack_ids = [stack.get("id") for stack in managed if isinstance(stack.get("id"), str)]
    if stack_ids:
        deleted = client.request(
            "DELETE",
            "/api/stacks",
            headers=headers,
            json={"ids": stack_ids},
        )
        deleted.raise_for_status()
    for member_ids in desired:
        created = client.post(
            "/api/stacks",
            headers=headers,
            json={"assetIds": member_ids},
        )
        created.raise_for_status()
    return len(desired)


def reconcile_tags(
    client: httpx.Client,
    api_key: str,
    relationships: dict[str, Any],
    asset_ids: dict[str, str],
) -> dict[str, int]:
    """Create managed demo tags and converge their seed-asset assignments."""

    configured = relationships.get("tags")
    if not isinstance(configured, list):
        raise RuntimeError("Media manifest tags must be a list")

    headers = {"x-api-key": api_key}
    response = client.get("/api/tags", headers=headers)
    response.raise_for_status()
    existing = {
        tag.get("name"): tag
        for tag in response.json()
        if isinstance(tag, dict) and isinstance(tag.get("name"), str)
    }
    all_seed_ids = set(asset_ids.values())
    tagged_asset_ids: set[str] = set()
    assignment_count = 0

    for fixture in configured:
        if not isinstance(fixture, dict):
            raise RuntimeError("Media manifest contains an invalid tag")
        name = fixture.get("name")
        color = fixture.get("color")
        if not isinstance(name, str) or not isinstance(color, str):
            raise RuntimeError("Media manifest contains invalid tag metadata")
        desired_ids = set(resolve_paths(asset_ids, fixture.get("paths"), f"tag {name}"))
        current = existing.get(name)
        if current is None:
            created = client.post(
                "/api/tags",
                headers=headers,
                json={"name": name, "color": color},
            )
            created.raise_for_status()
            current = created.json()
        tag_id = current.get("id") if isinstance(current, dict) else None
        if not isinstance(tag_id, str):
            raise RuntimeError(f"Immich tag {name!r} did not provide an ID")
        if current.get("color") != color:
            updated = client.patch(
                f"/api/tags/{tag_id}",
                headers=headers,
                json={"color": color},
            )
            updated.raise_for_status()

        if desired_ids:
            added = client.put(
                f"/api/tags/{tag_id}/assets",
                headers=headers,
                json={"ids": sorted(desired_ids)},
            )
            added.raise_for_status()
        undesired_ids = all_seed_ids - desired_ids
        if undesired_ids:
            removed = client.request(
                "DELETE",
                f"/api/tags/{tag_id}/assets",
                headers=headers,
                json={"ids": sorted(undesired_ids)},
            )
            removed.raise_for_status()
        tagged_asset_ids.update(desired_ids)
        assignment_count += len(desired_ids)

    return {
        "tags": len(configured),
        "tagged_assets": len(tagged_asset_ids),
        "tag_assignments": assignment_count,
    }


def reconcile_asset_states(
    client: httpx.Client,
    api_key: str,
    relationships: dict[str, Any],
    asset_ids: dict[str, str],
) -> dict[str, int]:
    headers = {"x-api-key": api_key}
    all_ids = list(dict.fromkeys(asset_ids.values()))
    restored = client.post(
        "/api/trash/restore/assets",
        headers=headers,
        json={"ids": all_ids},
    )
    restored.raise_for_status()
    reset = client.put(
        "/api/assets",
        headers=headers,
        json={"ids": all_ids, "isFavorite": False, "visibility": "timeline"},
    )
    reset.raise_for_status()

    favorites = resolve_paths(asset_ids, relationships.get("favorite_paths"), "favorite")
    archived = resolve_paths(asset_ids, relationships.get("archived_paths"), "archived")
    trashed = resolve_paths(asset_ids, relationships.get("trashed_paths"), "trashed")
    if favorites:
        response = client.put(
            "/api/assets", headers=headers, json={"ids": favorites, "isFavorite": True}
        )
        response.raise_for_status()
    if archived:
        response = client.put(
            "/api/assets", headers=headers, json={"ids": archived, "visibility": "archive"}
        )
        response.raise_for_status()
    if trashed:
        response = client.request(
            "DELETE", "/api/assets", headers=headers, json={"ids": trashed, "force": False}
        )
        response.raise_for_status()
    return {"favorite": len(favorites), "archived": len(archived), "trashed": len(trashed)}


def asset_statistics(client: httpx.Client, api_key: str) -> dict[str, int]:
    headers = {"x-api-key": api_key}
    active_response = client.get(
        "/api/assets/statistics", headers=headers, params={"isTrashed": "false"}
    )
    active_response.raise_for_status()
    trashed_response = client.get(
        "/api/assets/statistics", headers=headers, params={"isTrashed": "true"}
    )
    trashed_response.raise_for_status()
    active = active_response.json()
    trashed = trashed_response.json()
    return {
        "total": int(active["total"]) + int(trashed["total"]),
        "active": int(active["total"]),
        "trashed": int(trashed["total"]),
        "images": int(active["images"]) + int(trashed["images"]),
        "videos": int(active["videos"]) + int(trashed["videos"]),
    }


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(state, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, 0o644)
    with suppress(PermissionError):
        os.chown(temporary, 10001, 10001)
    temporary.replace(path)


def main() -> None:
    base_url = required_environment("IMMICH_URL").rstrip("/")
    email = required_environment("IMMICH_TEST_ADMIN_EMAIL")
    password = required_environment("IMMICH_TEST_ADMIN_PASSWORD")
    name = required_environment("IMMICH_TEST_ADMIN_NAME")
    api_key_path = Path(required_environment("IMMICH_API_KEY_FILE"))
    state_path = Path(required_environment("COMPANION_TEST_STATE_FILE"))
    seed_root = Path(required_environment("COMPANION_TEST_SEED_DIR")).resolve()
    clean_reset = os.environ.get("COMPANION_TEST_RESET_MODE", "false").lower() == "true"

    manifest, manifest_path = load_manifest(seed_root)
    relationships = manifest_relationships(manifest)
    expected = manifest.get("expected", {})
    expected_assets = int(expected.get("unique_assets", 0))
    source_files = int(expected.get("source_files", 0))
    expected_tags = int(expected.get("tags", 0))
    expected_tagged_assets = int(expected.get("tagged_assets", 0))
    if min(expected_assets, source_files, expected_tags, expected_tagged_assets) <= 0:
        raise RuntimeError("Media manifest has invalid expected counts")

    with httpx.Client(base_url=base_url, timeout=60, follow_redirects=False) as client:
        wait_for_immich(client)
        access_token = login(client, email, password, name)
        api_key = resolve_api_key(client, access_token, api_key_path)
        upload_result = upload_assets(client, api_key, seed_root, manifest)
        resolved_ids = upload_result["asset_ids"]
        assert isinstance(resolved_ids, dict)
        album_count = reconcile_albums(client, api_key, relationships, resolved_ids)
        stack_count = reconcile_stacks(client, api_key, relationships, resolved_ids)
        tag_counts = reconcile_tags(client, api_key, relationships, resolved_ids)
        state_counts = reconcile_asset_states(client, api_key, relationships, resolved_ids)
        statistics = asset_statistics(client, api_key)

    if statistics["total"] < expected_assets:
        raise RuntimeError("Immich asset count is smaller than the deterministic seed")
    if clean_reset and statistics["total"] != expected_assets:
        raise RuntimeError("A clean reset did not produce the exact deterministic asset count")
    if tag_counts["tags"] != expected_tags:
        raise RuntimeError("Immich tag count does not match the deterministic manifest")
    if tag_counts["tagged_assets"] != expected_tagged_assets:
        raise RuntimeError("Immich tagged asset count does not match the deterministic manifest")

    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    state = {
        "ready": True,
        "immich_version": "v3.1.0",
        "clean_reset": clean_reset,
        "manifest_sha256": manifest_hash,
        "source_files": source_files,
        "expected_seed_assets": expected_assets,
        "immich_assets": statistics,
        "upload_result": {
            "created": upload_result["created"],
            "duplicates": upload_result["duplicates"],
        },
        "fixture_relations": {
            "albums": album_count,
            "stacks": stack_count,
            **tag_counts,
            **state_counts,
        },
    }
    write_state(state_path, state)
    print(
        "Immich bootstrap ready: "
        f"{statistics['total']} assets, deterministic manifest {manifest_hash[:12]}"
    )


if __name__ == "__main__":
    main()
