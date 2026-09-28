"""Bounded WD v3 ONNX inference, following immich-booru-tagger preprocessing."""

from __future__ import annotations

import asyncio
import csv
import gc
import io
import logging
from contextlib import suppress
from pathlib import Path
from time import monotonic

import numpy as np
from PIL import Image

from companion.config import Settings

logger = logging.getLogger(__name__)


class BooruEngine:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._session = None
        self._repo: str | None = None
        self._names: list[str] = []
        self._categories: list[int] = []
        self._input = ""
        self._output = ""
        self._size = 0
        self._last_used = monotonic()
        self._eviction_task: asyncio.Task[None] | None = None

    def start(self, idle_seconds) -> None:
        if self._eviction_task is None:
            self._eviction_task = asyncio.create_task(self._evict_loop(idle_seconds))

    async def stop(self) -> None:
        if self._eviction_task is not None:
            self._eviction_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._eviction_task
            self._eviction_task = None
        async with self._lock:
            self._unload()

    async def _evict_loop(self, idle_seconds) -> None:
        while True:
            await asyncio.sleep(5)
            async with self._lock:
                if self._session is None:
                    continue
                seconds = await idle_seconds()
                if seconds == 0 or monotonic() - self._last_used >= seconds:
                    self._unload()

    def _unload(self) -> None:
        self._session = None
        self._repo = None
        gc.collect()

    def _load(self, repo: str) -> None:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download

        cache = Path(self._settings.booru_model_cache_dir)
        cache.mkdir(parents=True, exist_ok=True)
        paths = {
            name: hf_hub_download(repo_id=repo, filename=name, cache_dir=str(cache))
            for name in ("selected_tags.csv", "model.onnx")
        }
        with open(paths["selected_tags.csv"], newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        self._names = [row["name"].strip() for row in rows]
        self._categories = [int(row["category"]) for row in rows]
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session = ort.InferenceSession(
            paths["model.onnx"], sess_options=options, providers=["CPUExecutionProvider"]
        )
        model_input = session.get_inputs()[0]
        shape = model_input.shape
        if len(shape) != 4 or not isinstance(shape[1], int) or shape[1] != shape[2]:
            raise ValueError(f"Unsupported WD model shape: {shape}")
        self._size = shape[1]
        self._input = model_input.name
        self._output = session.get_outputs()[0].name
        self._session = session
        self._repo = repo
        logger.info("Loaded Booru tagger model %s", repo)

    def _prepare(self, data: bytes) -> np.ndarray:
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            rgba = source.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        canvas.alpha_composite(rgba)
        image = canvas.convert("RGB")
        width, height = image.size
        edge = max(width, height)
        padded = Image.new("RGB", (edge, edge), (255, 255, 255))
        padded.paste(image, ((edge - width) // 2, (edge - height) // 2))
        if edge != self._size:
            padded = padded.resize((self._size, self._size), Image.Resampling.BICUBIC)
        return np.ascontiguousarray(np.asarray(padded, dtype=np.float32)[:, :, ::-1])

    def _predict(self, data: bytes, repo: str, confidence: float, character: float) -> list[str]:
        if self._session is None or self._repo != repo:
            self._unload()
            self._load(repo)
        scores = self._session.run(
            [self._output], {self._input: np.stack([self._prepare(data)])}
        )[0][0]
        if len(scores) != len(self._names):
            raise ValueError("WD model output and label count differ")
        result = [
            (self._names[index], float(score))
            for index, score in enumerate(scores)
            if (self._categories[index] == 0 and score >= confidence)
            or (self._categories[index] == 4 and score >= max(confidence, character))
        ]
        ratings = [index for index, category in enumerate(self._categories) if category == 9]
        if ratings:
            best = max(ratings, key=lambda index: float(scores[index]))
            if scores[best] >= confidence:
                result.append((self._names[best], float(scores[best])))
        result.sort(key=lambda item: item[1], reverse=True)
        return [name for name, _ in result]

    async def predict(
        self, data: bytes, repo: str, confidence: float, character: float, idle_seconds: int
    ) -> list[str]:
        async with self._lock:
            try:
                return await asyncio.to_thread(self._predict, data, repo, confidence, character)
            finally:
                self._last_used = monotonic()
                if idle_seconds == 0:
                    self._unload()
