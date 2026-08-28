"""Compare legacy and streamed stack-response memory with deterministic data."""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from companion.immich import ImmichAsset, ImmichStack, _iter_json_array


class LegacyStack(BaseModel):
    """The former full-asset stack representation used for comparison."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: UUID
    primary_asset_id: UUID = Field(alias="primaryAssetId")
    assets: list[ImmichAsset]


class FileStream(httpx.AsyncByteStream):
    def __init__(self, path: Path, chunk_size: int = 65536) -> None:
        self._path = path
        self._chunk_size = chunk_size

    async def __aiter__(self):
        with self._path.open("rb") as source:
            while chunk := source.read(self._chunk_size):
                yield chunk


def asset_payload(index: int) -> dict[str, Any]:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    return {
        "id": str(UUID(int=index + 1)),
        "ownerId": str(UUID(int=1)),
        "type": "IMAGE",
        "originalFileName": f"image-{index:07d}.jpg",
        "originalPath": f"upload/library/{index // 1000}/image-{index:07d}.jpg",
        "originalMimeType": "image/jpeg",
        "checksum": f"checksum-{index:07d}",
        "width": 4032,
        "height": 3024,
        "fileCreatedAt": timestamp,
        "fileModifiedAt": timestamp,
        "localDateTime": timestamp,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "isFavorite": False,
        "isArchived": False,
        "isTrashed": False,
        "exifInfo": {"make": "Synthetic", "model": "Memory profile", "iso": 100},
        "people": [],
        "tags": [],
        "stack": None,
    }


def write_payload(path: Path, asset_count: int, members_per_stack: int) -> int:
    stack_count = (asset_count + members_per_stack - 1) // members_per_stack
    with path.open("w", encoding="utf-8") as output:
        output.write("[")
        for stack_index in range(stack_count):
            start = stack_index * members_per_stack
            members = [
                asset_payload(index)
                for index in range(start, min(start + members_per_stack, asset_count))
            ]
            if stack_index:
                output.write(",")
            json.dump(
                {
                    "id": str(UUID(int=asset_count + stack_index + 1)),
                    "primaryAssetId": members[0]["id"],
                    "assets": members,
                },
                output,
                separators=(",", ":"),
            )
        output.write("]")
    return stack_count


def rss_bytes() -> tuple[int, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        name, separator, raw = line.partition(":")
        if separator and name in {"VmRSS", "VmHWM"}:
            values[name] = int(raw.strip().split()[0]) * 1024
    return values.get("VmRSS", 0), values.get("VmHWM", 0)


def sample(stage: str, started: float, **counts: int) -> dict[str, Any]:
    rss, rss_peak = rss_bytes()
    python_bytes, python_peak = tracemalloc.get_traced_memory()
    return {
        "stage": stage,
        "rss_bytes": rss,
        "rss_peak_bytes": rss_peak,
        "python_bytes": python_bytes,
        "python_peak_bytes": python_peak,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        **counts,
    }


def stack_payload(stack: LegacyStack | ImmichStack) -> tuple[dict[str, Any], list[UUID]]:
    return (
        {
            "id": str(stack.id),
            "primaryAssetId": str(stack.primary_asset_id),
            "assets": [
                {
                    "id": str(member.id),
                    "type": member.asset_type,
                    "originalFileName": member.original_file_name,
                    "originalMimeType": member.original_mime_type,
                    "width": member.width,
                    "height": member.height,
                    "fileCreatedAt": member.file_created_at.isoformat(),
                }
                for member in stack.assets
                if not member.is_trashed
            ],
        },
        [member.id for member in stack.assets],
    )


def profile_legacy(path: Path, batch_size: int, started: float) -> list[dict[str, Any]]:
    samples = [sample("before_http_response", started)]
    response_bytes = path.read_bytes()
    samples.append(sample("after_http_response", started, response_bytes=len(response_bytes)))
    decoded = json.loads(response_bytes)
    stacks = [LegacyStack.model_validate(item) for item in decoded]
    samples.append(sample("after_pydantic_deserialization", started, stacks=len(stacks)))
    payloads = [stack_payload(stack) for stack in stacks]
    samples.append(sample("after_payload_build", started, stacks=len(payloads)))
    for index in range(0, len(payloads), batch_size):
        _ = payloads[index : index + batch_size]
    samples.append(sample("after_persistence_batches", started, stacks=len(payloads)))
    del decoded, stacks, payloads, response_bytes
    return samples


async def profile_streamed(
    path: Path, batch_size: int, started: float
) -> list[dict[str, Any]]:
    samples = [sample("before_http_response", started)]
    response = httpx.Response(200, stream=FileStream(path))
    batch: list[tuple[dict[str, Any], list[UUID]]] = []
    stack_count = 0
    member_count = 0
    batch_count = 0
    async for item in _iter_json_array(response):
        stack = ImmichStack.model_validate(item)
        payload = stack_payload(stack)
        batch.append(payload)
        stack_count += 1
        member_count += len(payload[1])
        if len(batch) >= batch_size:
            batch_count += 1
            batch.clear()
    if batch:
        batch_count += 1
        batch.clear()
    samples.append(
        sample(
            "after_streamed_batches",
            started,
            stacks=stack_count,
            members=member_count,
            batches=batch_count,
        )
    )
    return samples


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("legacy", "streamed"))
    parser.add_argument("--assets", type=int, default=25000)
    parser.add_argument("--members-per-stack", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--settle-seconds", type=float, default=30)
    args = parser.parse_args()
    if min(args.assets, args.members_per_stack, args.batch_size) < 1:
        parser.error("asset, member, and batch counts must be positive")

    with tempfile.TemporaryDirectory(prefix="companion-stack-profile-") as directory:
        payload_path = Path(directory) / "stacks.json"
        stack_count = write_payload(payload_path, args.assets, args.members_per_stack)
        gc.collect()
        tracemalloc.start()
        started = time.perf_counter()
        samples = [sample("profile_start", started, stacks=stack_count, assets=args.assets)]
        if args.mode == "legacy":
            samples.extend(profile_legacy(payload_path, args.batch_size, started))
        else:
            samples.extend(await profile_streamed(payload_path, args.batch_size, started))
        gc.collect()
        samples.append(sample("after_release", started))
        if args.settle_seconds:
            await asyncio.sleep(args.settle_seconds)
        samples.append(sample("settled", started))
        print(json.dumps({"mode": args.mode, "samples": samples}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
