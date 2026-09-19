"""Bounded disposable caches for duplicate comparison media and working files."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(frozen=True, slots=True)
class CachedPreview:
    content: bytes
    media_type: str
    etag: str | None
    cache_control: str | None


@dataclass(frozen=True, slots=True)
class DiskCacheStatus:
    path: str
    healthy: bool
    used_bytes: int
    max_bytes: int
    free_bytes: int
    entry_count: int
    hits: int
    misses: int
    evictions: int
    cleanup_failures: int


class BoundedPreviewCache:
    """A process-safe-enough, atomic, age-aware disk LRU for Immich derivatives."""

    def __init__(self, path: Path, *, max_bytes: int, max_age_seconds: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.max_age = timedelta(seconds=max_age_seconds)
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.cleanup_failures = 0
        self._lock = threading.Lock()
        self._prepare()

    def _prepare(self) -> None:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            for candidate in self.path.glob("*.tmp"):
                candidate.unlink(missing_ok=True)
            self._evict_locked()
        except OSError:
            self.cleanup_failures += 1

    @staticmethod
    def cache_key(identity: str) -> str:
        return hashlib.sha256(identity.encode(), usedforsecurity=False).hexdigest()

    def _paths(self, key: str) -> tuple[Path, Path]:
        safe_key = self.cache_key(key)
        return self.path / f"{safe_key}.data", self.path / f"{safe_key}.json"

    def get(self, key: str) -> CachedPreview | None:
        data_path, metadata_path = self._paths(key)
        with self._lock:
            try:
                if not data_path.is_file() or not metadata_path.is_file():
                    self.misses += 1
                    return None
                age = datetime.now(UTC).timestamp() - data_path.stat().st_mtime
                if age > self.max_age.total_seconds():
                    self._remove(data_path, metadata_path)
                    self.evictions += 1
                    self.misses += 1
                    return None
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                content = data_path.read_bytes()
                now = datetime.now(UTC).timestamp()
                os.utime(data_path, (now, now))
                os.utime(metadata_path, (now, now))
                self.hits += 1
                return CachedPreview(
                    content=content,
                    media_type=str(metadata.get("media_type") or "application/octet-stream"),
                    etag=metadata.get("etag"),
                    cache_control=metadata.get("cache_control"),
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                self.cleanup_failures += 1
                self._remove(data_path, metadata_path)
                self.misses += 1
                return None

    def put(self, key: str, preview: CachedPreview) -> bool:
        if not preview.content:
            return False
        data_path, metadata_path = self._paths(key)
        metadata = json.dumps(
            {
                "media_type": preview.media_type,
                "etag": preview.etag,
                "cache_control": preview.cache_control,
            },
            separators=(",", ":"),
        ).encode()
        if len(preview.content) + len(metadata) > self.max_bytes:
            return False
        with self._lock:
            try:
                with NamedTemporaryFile(dir=self.path, suffix=".tmp", delete=False) as data_file:
                    data_file.write(preview.content)
                    temporary_data = Path(data_file.name)
                with NamedTemporaryFile(dir=self.path, suffix=".tmp", delete=False) as meta_file:
                    meta_file.write(metadata)
                    temporary_metadata = Path(meta_file.name)
                os.replace(temporary_data, data_path)
                os.replace(temporary_metadata, metadata_path)
                self._evict_locked(protected=data_path)
                return data_path.exists()
            except OSError:
                self.cleanup_failures += 1
                return False

    def clear(self) -> int:
        removed = 0
        with self._lock:
            for data_path in self.path.glob("*.data"):
                metadata_path = data_path.with_suffix(".json")
                try:
                    self._remove(data_path, metadata_path)
                    removed += 1
                except OSError:
                    self.cleanup_failures += 1
        return removed

    def status(self) -> DiskCacheStatus:
        with self._lock:
            entries = list(self.path.glob("*.data")) if self.path.is_dir() else []
            used = sum(self._entry_size(path) for path in entries if path.is_file())
            try:
                free = shutil.disk_usage(self.path).free
                healthy = os.access(self.path, os.W_OK)
            except OSError:
                free = 0
                healthy = False
            return DiskCacheStatus(
                path=str(self.path),
                healthy=healthy,
                used_bytes=used,
                max_bytes=self.max_bytes,
                free_bytes=free,
                entry_count=len(entries),
                hits=self.hits,
                misses=self.misses,
                evictions=self.evictions,
                cleanup_failures=self.cleanup_failures,
            )

    def _evict_locked(self, *, protected: Path | None = None) -> None:
        now = datetime.now(UTC).timestamp()
        entries = sorted(
            (path for path in self.path.glob("*.data") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
        )
        used = sum(self._entry_size(path) for path in entries)
        for data_path in entries:
            expired = now - data_path.stat().st_mtime > self.max_age.total_seconds()
            over_limit = used > self.max_bytes
            if not expired and not over_limit:
                continue
            if protected is not None and data_path == protected and not expired:
                continue
            size = self._entry_size(data_path)
            self._remove(data_path, data_path.with_suffix(".json"))
            used -= size
            self.evictions += 1

    @staticmethod
    def _remove(data_path: Path, metadata_path: Path) -> None:
        data_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

    @staticmethod
    def _entry_size(data_path: Path) -> int:
        metadata_path = data_path.with_suffix(".json")
        return data_path.stat().st_size + (
            metadata_path.stat().st_size if metadata_path.is_file() else 0
        )


class SimilarityCacheManager:
    """Own the disposable filesystem layout without touching Immich-managed files."""

    def __init__(
        self,
        root: Path,
        *,
        preview_max_bytes: int,
        preview_max_age_seconds: int,
        decode_max_bytes: int,
    ) -> None:
        self.root = root
        self.preview = BoundedPreviewCache(
            root / "previews",
            max_bytes=preview_max_bytes,
            max_age_seconds=preview_max_age_seconds,
        )
        self.decode_path = root / "decode"
        self.decode_max_bytes = decode_max_bytes
        self.decode_cleanup_failures = 0
        try:
            self.decode_path.mkdir(parents=True, exist_ok=True)
            for candidate in self.decode_path.glob("*.tmp"):
                candidate.unlink(missing_ok=True)
        except OSError:
            self.decode_cleanup_failures += 1

    def clear_decode(self) -> int:
        removed = 0
        for candidate in self.decode_path.glob("*.tmp"):
            try:
                candidate.unlink(missing_ok=True)
                removed += 1
            except OSError:
                self.decode_cleanup_failures += 1
        return removed

    def decode_status(self) -> DiskCacheStatus:
        entries = list(self.decode_path.glob("*.tmp")) if self.decode_path.is_dir() else []
        used = sum(path.stat().st_size for path in entries if path.is_file())
        try:
            free = shutil.disk_usage(self.decode_path).free
            healthy = os.access(self.decode_path, os.W_OK)
        except OSError:
            free = 0
            healthy = False
        return DiskCacheStatus(
            path=str(self.decode_path),
            healthy=healthy,
            used_bytes=used,
            max_bytes=self.decode_max_bytes,
            free_bytes=free,
            entry_count=len(entries),
            hits=0,
            misses=0,
            evictions=0,
            cleanup_failures=self.decode_cleanup_failures,
        )
