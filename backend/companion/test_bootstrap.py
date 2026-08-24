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
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise RuntimeError("Unsupported or invalid deterministic media manifest")
    return manifest, manifest_path


def upload_assets(
    client: httpx.Client,
    api_key: str,
    seed_root: Path,
    manifest: dict[str, Any],
) -> dict[str, int]:
    created = 0
    duplicates = 0
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
        status = response.json().get("status")
        if status == "created":
            created += 1
        elif status == "duplicate":
            duplicates += 1
        else:
            raise RuntimeError(f"Immich returned an unexpected upload status: {status!r}")
    return {"created": created, "duplicates": duplicates}


def asset_statistics(client: httpx.Client, api_key: str) -> dict[str, int]:
    response = client.get("/api/assets/statistics", headers={"x-api-key": api_key})
    response.raise_for_status()
    payload = response.json()
    return {
        "total": int(payload["total"]),
        "images": int(payload["images"]),
        "videos": int(payload["videos"]),
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
    expected = manifest.get("expected", {})
    expected_assets = int(expected.get("unique_assets", 0))
    source_files = int(expected.get("source_files", 0))
    if expected_assets <= 0 or source_files <= 0:
        raise RuntimeError("Media manifest has invalid expected counts")

    with httpx.Client(base_url=base_url, timeout=60, follow_redirects=False) as client:
        wait_for_immich(client)
        access_token = login(client, email, password, name)
        api_key = resolve_api_key(client, access_token, api_key_path)
        upload_result = upload_assets(client, api_key, seed_root, manifest)
        statistics = asset_statistics(client, api_key)

    if statistics["total"] < expected_assets:
        raise RuntimeError("Immich asset count is smaller than the deterministic seed")
    if clean_reset and statistics["total"] != expected_assets:
        raise RuntimeError("A clean reset did not produce the exact deterministic asset count")

    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    state = {
        "ready": True,
        "immich_version": "v3.1.0",
        "clean_reset": clean_reset,
        "manifest_sha256": manifest_hash,
        "source_files": source_files,
        "expected_seed_assets": expected_assets,
        "immich_assets": statistics,
        "upload_result": upload_result,
    }
    write_state(state_path, state)
    print(
        "Immich bootstrap ready: "
        f"{statistics['total']} assets, deterministic manifest {manifest_hash[:12]}"
    )


if __name__ == "__main__":
    main()
