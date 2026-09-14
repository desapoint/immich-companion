"""Regressions for fault-isolated LibRaw/rawpy execution."""

from __future__ import annotations

import signal
import subprocess
from io import BytesIO

from companion import image_decode, similarity_features
from companion.raw_isolation import RawDecodeResult, decode_raw_isolated


def test_native_worker_signal_is_contained(monkeypatch) -> None:
    def crashed(command, **kwargs):
        kwargs["stderr"].write(b"unknown file: data corrupted at 1223523\n")
        return subprocess.CompletedProcess(command, -signal.SIGSEGV, stdout="")

    monkeypatch.setattr(subprocess, "run", crashed)

    result = decode_raw_isolated(BytesIO(b"corrupt raw"), max_decoded_pixels=100)

    assert result.valid is None
    assert result.issue == "image_decode_raw_worker_failed"


def test_worker_timeout_is_contained(monkeypatch) -> None:
    def timed_out(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timed_out)

    result = decode_raw_isolated(
        BytesIO(b"slow raw"),
        max_decoded_pixels=100,
        timeout_seconds=0.01,
    )

    assert result.valid is None
    assert result.issue == "image_decode_raw_timeout"


def test_worker_result_and_feature_bytes_are_parsed(monkeypatch) -> None:
    payload = (
        '{"valid":true,"width":12,"height":8,"issue":null,'
        '"feature":{"luminance_vector":"0001","color_histogram":"0203"}}'
    )

    def succeeded(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=payload)

    monkeypatch.setattr(subprocess, "run", succeeded)

    result = decode_raw_isolated(
        BytesIO(b"raw"),
        max_decoded_pixels=100,
        extract_features=True,
    )

    assert result.valid is True
    assert (result.width, result.height) == (12, 8)
    assert result.feature is not None
    assert result.feature["luminance_vector"] == b"\x00\x01"
    assert result.feature["color_histogram"] == b"\x02\x03"


def test_image_decode_tiff_fallback_uses_isolated_worker(monkeypatch) -> None:
    calls = 0

    def isolated(*args, **kwargs):
        nonlocal calls
        calls += 1
        return RawDecodeResult(valid=None, issue="image_decode_raw_worker_failed")

    monkeypatch.setattr(image_decode, "decode_raw_isolated", isolated)

    result = image_decode.decode_image(BytesIO(b"not a real tiff"), "tiff")

    assert calls == 1
    assert result.supported is True
    assert result.valid is None
    assert result.issue == "image_decode_raw_worker_failed"


def test_similarity_tiff_fallback_attempts_raw_worker_once(monkeypatch) -> None:
    calls = 0

    def isolated(*args, **kwargs):
        nonlocal calls
        calls += 1
        return RawDecodeResult(valid=False, issue="image_decode_failed")

    monkeypatch.setattr(similarity_features, "decode_raw_isolated", isolated)

    decoded, feature = similarity_features.decode_and_extract_features(
        BytesIO(b"not a real tiff"),
        "tiff",
    )

    assert calls == 1
    assert decoded.supported is True
    assert decoded.valid is False
    assert decoded.issue == "image_decode_failed"
    assert feature is None
