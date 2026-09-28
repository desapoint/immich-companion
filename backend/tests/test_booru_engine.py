"""WD v3 category and threshold compatibility without downloading a model."""

import asyncio
import io

import numpy as np
import pytest

from companion.booru_engine import BooruEngine
from companion.config import Settings


class FakeSession:
    def run(self, outputs, inputs):
        assert outputs == ["scores"]
        assert list(inputs) == ["pixels"]
        return [np.array([[0.7, 0.34, 0.89, 0.95, 0.8, 0.5]], dtype=np.float32)]


def test_predictions_match_wd_general_character_and_best_rating_rules() -> None:
    engine = BooruEngine(Settings())
    engine._session = FakeSession()
    engine._repo = "SmilingWolf/wd-swinv2-tagger-v3"
    engine._names = ["sky", "below", "character_low", "character_high", "general", "explicit"]
    engine._categories = [0, 0, 4, 4, 9, 9]
    engine._input = "pixels"
    engine._output = "scores"
    engine._prepare = lambda data: np.zeros((2, 2, 3), dtype=np.float32)

    assert engine._predict(b"image", engine._repo, 0.35, 0.9) == [
        "character_high", "general", "sky"
    ]


def test_model_download_reports_hugging_face_byte_progress(monkeypatch, tmp_path) -> None:
    updates = []

    def fake_download(*, filename, tqdm_class, **kwargs):
        assert kwargs["revision"]
        path = tmp_path / filename
        path.write_bytes(b"x" * 100)
        with tqdm_class(total=100, desc=filename, file=io.StringIO()) as progress:
            progress.update(25)
        return str(path)

    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_download)
    engine = BooruEngine(Settings(booru_model_cache_dir=tmp_path))
    engine._paths("SmilingWolf/wd-swinv2-tagger-v3", lambda *update: updates.append(update))
    assert ("model.onnx", 25, 100) in updates
    assert updates[-1] == ("model.onnx", 100, 100)


@pytest.mark.asyncio
async def test_model_download_publishes_progress_while_running(monkeypatch) -> None:
    engine = BooruEngine(Settings())

    def fake_paths(repo, observe):
        observe("model.onnx", 25, 100)
        import time
        time.sleep(0.6)
        observe("model.onnx", 100, 100)
        return {}

    monkeypatch.setattr(engine, "_paths", fake_paths)
    updates = []

    async def report(name, completed, total):
        updates.append((name, completed, total))

    await asyncio.wait_for(engine.download("SmilingWolf/wd-swinv2-tagger-v3", report), 3)
    assert ("model.onnx", 25, 100) in updates
    assert updates[-1] == ("model.onnx", 100, 100)
