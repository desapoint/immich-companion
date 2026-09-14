"""Fault-isolated execution for LibRaw/rawpy image decoding."""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryFile
from typing import Any, BinaryIO, Iterator

logger = logging.getLogger("uvicorn.error")

RAW_WORKER_TIMEOUT_SECONDS = float(
    os.environ.get("IMMICH_COMPANION_RAW_WORKER_TIMEOUT_SECONDS", "90")
)
RAW_WORKER_MEMORY_LIMIT_BYTES = int(
    os.environ.get(
        "IMMICH_COMPANION_RAW_WORKER_MEMORY_BYTES",
        str(1024 * 1024 * 1024),
    )
)
RAW_WORKER_STDERR_TAIL_BYTES = 4096
RAW_COPY_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RawDecodeResult:
    """Structured result returned by the isolated RAW decoder worker."""

    valid: bool | None
    width: int | None = None
    height: int | None = None
    issue: str | None = None
    feature: dict[str, Any] | None = None


def _stderr_tail(stream: BinaryIO) -> str:
    try:
        stream.flush()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(max(0, size - RAW_WORKER_STDERR_TAIL_BYTES))
        return stream.read().decode("utf-8", errors="replace").strip()
    except (OSError, ValueError):
        return ""


def _returncode_description(returncode: int) -> str:
    if returncode >= 0:
        return f"exit={returncode}"
    try:
        return f"signal={signal.Signals(-returncode).name}"
    except ValueError:
        return f"signal={-returncode}"


def _restore_position(stream: BinaryIO, position: int | None) -> None:
    if position is None:
        return
    try:
        stream.seek(position)
    except (OSError, ValueError):
        pass


@contextmanager
def _worker_input(stream: BinaryIO) -> Iterator[tuple[list[str], tuple[int, ...]]]:
    """Expose a stream to a child without copying when a real file descriptor exists."""

    try:
        original_position = stream.tell()
    except (AttributeError, OSError, ValueError):
        original_position = None

    try:
        stream.seek(0)
        flush = getattr(stream, "flush", None)
        if callable(flush):
            flush()

        if os.name == "posix":
            try:
                fd = stream.fileno()
            except (AttributeError, OSError, ValueError):
                fd = -1
            if fd >= 0:
                yield ["--fd", str(fd)], (fd,)
                return

        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(prefix="immich-companion-raw-", suffix=".bin", delete=False) as copy:
                temporary_path = Path(copy.name)
                shutil.copyfileobj(stream, copy, length=RAW_COPY_CHUNK_BYTES)
            yield ["--input", str(temporary_path)], ()
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    finally:
        _restore_position(stream, original_position)


def _decode_feature_payload(payload: object) -> dict[str, Any] | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("RAW worker returned an invalid feature payload")
    decoded = dict(payload)
    for field in ("luminance_vector", "color_histogram"):
        value = decoded.get(field)
        if not isinstance(value, str):
            raise ValueError(f"RAW worker feature field {field!r} is invalid")
        decoded[field] = bytes.fromhex(value)
    return decoded


def decode_raw_isolated(
    stream: BinaryIO,
    *,
    max_decoded_pixels: int,
    extract_features: bool = False,
    include_pixel_hash: bool = True,
    timeout_seconds: float = RAW_WORKER_TIMEOUT_SECONDS,
    memory_limit_bytes: int = RAW_WORKER_MEMORY_LIMIT_BYTES,
) -> RawDecodeResult:
    """Decode RAW input in a child so native LibRaw faults cannot kill Uvicorn."""

    mode = "features" if extract_features else "decode"
    command = [
        sys.executable,
        "-m",
        "companion.raw_decode_worker",
        "--mode",
        mode,
        "--max-pixels",
        str(max_decoded_pixels),
        "--memory-limit",
        str(max(0, memory_limit_bytes)),
    ]
    if include_pixel_hash:
        command.append("--include-pixel-hash")

    environment = os.environ.copy()
    environment.update(
        {
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )

    try:
        with _worker_input(stream) as (source_args, pass_fds), TemporaryFile() as stderr:
            try:
                completed = subprocess.run(
                    [*command, *source_args],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=stderr,
                    text=True,
                    timeout=timeout_seconds,
                    env=environment,
                    pass_fds=pass_fds,
                    start_new_session=True,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "RAW decoder worker timed out after %.1fs",
                    timeout_seconds,
                )
                return RawDecodeResult(
                    valid=None,
                    issue="image_decode_raw_timeout",
                )

            diagnostics = _stderr_tail(stderr)
            if completed.returncode != 0:
                logger.warning(
                    "RAW decoder worker terminated unexpectedly: %s%s",
                    _returncode_description(completed.returncode),
                    f" diagnostics={diagnostics}" if diagnostics else "",
                )
                return RawDecodeResult(
                    valid=None,
                    issue="image_decode_raw_worker_failed",
                )

            try:
                payload = json.loads(completed.stdout)
                if not isinstance(payload, dict):
                    raise ValueError("worker response is not an object")
                result = RawDecodeResult(
                    valid=payload.get("valid"),
                    width=payload.get("width"),
                    height=payload.get("height"),
                    issue=payload.get("issue"),
                    feature=_decode_feature_payload(payload.get("feature")),
                )
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                logger.warning(
                    "RAW decoder worker returned an invalid response: error=%s%s",
                    error,
                    f" diagnostics={diagnostics}" if diagnostics else "",
                )
                return RawDecodeResult(
                    valid=None,
                    issue="image_decode_raw_worker_failed",
                )

            if result.valid is not True and diagnostics:
                logger.warning(
                    "RAW decoder worker could not decode input: issue=%s diagnostics=%s",
                    result.issue,
                    diagnostics,
                )
            return result
    except (OSError, ValueError) as error:
        logger.warning(
            "RAW decoder worker could not be started: error_type=%s reason=%s",
            type(error).__name__,
            error,
        )
        return RawDecodeResult(
            valid=None,
            issue="image_decode_raw_worker_failed",
        )
