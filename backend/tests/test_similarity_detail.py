"""Local differences remain visible after bounded candidate-detail extraction."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image, ImageDraw

from companion.similarity_detail import compare_detail_features, extract_detail_feature
from companion.similarity_detail_service import SimilarityDetailMaintainer
from companion.task_coordinator import TaskPausedError

ASSET = UUID(int=1)
MODIFIED = datetime(2026, 9, 14, tzinfo=UTC)


def _encoded(image: Image.Image, image_format: str = "PNG") -> bytes:
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def _scene() -> Image.Image:
    image = Image.new("RGB", (384, 384), (85, 105, 140))
    draw = ImageDraw.Draw(image)
    draw.ellipse((115, 20, 275, 180), fill=(230, 185, 150))
    draw.rectangle((140, 175, 245, 345), fill=(210, 80, 100))
    return image


def test_local_outfit_and_face_changes_lower_detail_score() -> None:
    original = _scene()
    outfit = original.copy()
    ImageDraw.Draw(outfit).rectangle((150, 235, 235, 330), fill=(35, 95, 185))
    face_cover = original.copy()
    ImageDraw.Draw(face_cover).rectangle((150, 92, 235, 130), fill=(25, 25, 35))

    first = extract_detail_feature(BytesIO(_encoded(original)), "png")
    changed_outfit = extract_detail_feature(BytesIO(_encoded(outfit)), "png")
    changed_face = extract_detail_feature(BytesIO(_encoded(face_cover)), "png")

    assert first is not None and changed_outfit is not None and changed_face is not None
    assert compare_detail_features(first, first).similarity_percent == 100
    outfit_score = compare_detail_features(first, changed_outfit)
    face_score = compare_detail_features(first, changed_face)
    assert outfit_score.changed_percent > face_score.changed_percent > 0
    assert outfit_score.similarity_percent < face_score.similarity_percent < 100


def test_jpeg_transcode_of_same_scene_remains_high_similarity() -> None:
    original = extract_detail_feature(BytesIO(_encoded(_scene())), "png")
    transcoded = extract_detail_feature(BytesIO(_encoded(_scene(), "JPEG")), "jpeg")

    assert original is not None and transcoded is not None
    assert compare_detail_features(original, transcoded).similarity_percent > 95


@pytest.mark.asyncio
@pytest.mark.parametrize("converted_format", ["JPEG", "PNG"])
async def test_invalid_heic_uses_fullsize_conversion_and_reuses_detail(
    converted_format: str,
) -> None:
    converted = _encoded(_scene(), converted_format)
    search = SimpleNamespace(
        source_identity="a" * 64,
        source_file_modified_at=MODIFIED,
        source_file_size_bytes=100,
        source_checksum=None,
    )

    class Repository:
        saved = {}
        origins = []

        async def get_current_many(self, asset_ids):
            return {
                asset_id: self.saved[asset_id]
                for asset_id in asset_ids if asset_id in self.saved
            }

        async def save(self, source_identity, asset_id, feature, origin):
            self.origins.append(origin)
            self.saved[asset_id] = feature
            return True

    class Immich:
        original_calls = 0
        fullsize_calls = 0

        @asynccontextmanager
        async def stream_original(self, asset_id):
            self.original_calls += 1

            async def chunks():
                yield b"invalid HEIC"

            yield SimpleNamespace(content_length=12, chunks=chunks())

        async def get_bounded_fullsize(self, asset_id, *, max_bytes):
            self.fullsize_calls += 1
            assert len(converted) < max_bytes
            return converted

        async def get_asset(self, asset_id):
            return SimpleNamespace(
                asset_type="IMAGE", is_trashed=False, is_offline=False,
                file_modified_at=MODIFIED, file_size_bytes=100, checksum=None,
                width=384, height=384,
            )

    class Context:
        async def ensure_active(self):
            return None

    immich = Immich()
    repository = Repository()
    maintainer = SimilarityDetailMaintainer(
        immich, repository, max_bytes=10_000_000  # type: ignore[arg-type]
    )
    await maintainer.ensure(Context(), [ASSET], {ASSET: search})  # type: ignore[arg-type]
    assert maintainer.counters["detail_features_generated"] == 1
    maintainer.reset_counters()
    await maintainer.ensure(Context(), [ASSET], {ASSET: search})  # type: ignore[arg-type]

    assert repository.origins == ["transcoded_fullsize"]
    assert (immich.original_calls, immich.fullsize_calls) == (1, 1)
    assert maintainer.counters["detail_features_reused"] == 1
    assert maintainer.counters["detail_features_generated"] == 0
    assert maintainer.counters["detail_original_bytes"] == 0


@pytest.mark.asyncio
async def test_reduced_fullsize_response_is_labeled_lower_grade() -> None:
    reduced = _encoded(_scene().resize((192, 192)))
    search = SimpleNamespace(
        source_identity="a" * 64,
        source_file_modified_at=MODIFIED,
        source_file_size_bytes=100,
        source_checksum=None,
    )

    class Repository:
        origin = None

        async def get_current_many(self, _asset_ids):
            return {}

        async def save(self, _identity, _asset_id, _feature, origin):
            self.origin = origin
            return True

    class Immich:
        @asynccontextmanager
        async def stream_original(self, _asset_id):
            async def chunks():
                yield b"invalid HEIC"

            yield SimpleNamespace(content_length=12, chunks=chunks())

        async def get_bounded_fullsize(self, _asset_id, *, max_bytes):
            assert len(reduced) < max_bytes
            return reduced

        async def get_asset(self, _asset_id):
            return SimpleNamespace(
                asset_type="IMAGE", is_trashed=False, is_offline=False,
                file_modified_at=MODIFIED, file_size_bytes=100, checksum=None,
                width=384, height=384,
            )

    class Context:
        async def ensure_active(self):
            return None

    repository = Repository()
    maintainer = SimilarityDetailMaintainer(Immich(), repository)  # type: ignore[arg-type]
    await maintainer.ensure(Context(), [ASSET], {ASSET: search})  # type: ignore[arg-type]

    assert repository.origin == "preview_fallback"
    assert maintainer.counters["detail_transcoded_fallbacks"] == 0
    assert maintainer.counters["detail_preview_fallbacks"] == 1


@pytest.mark.asyncio
async def test_detail_stage_caps_streams_and_preserves_pause() -> None:
    content = _encoded(_scene())
    ids = [UUID(int=index) for index in range(1, 5)]
    search = SimpleNamespace(
        source_identity="a" * 64,
        source_file_modified_at=MODIFIED,
        source_file_size_bytes=len(content),
        source_checksum=None,
    )

    class Repository:
        saved = {}

        async def get_current_many(self, asset_ids):
            return {
                asset_id: self.saved[asset_id]
                for asset_id in asset_ids if asset_id in self.saved
            }

        async def save(self, _identity, asset_id, feature, _origin):
            self.saved[asset_id] = feature
            return True

    class Immich:
        active = 0
        peak = 0

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.active += 1
            self.peak = max(self.peak, self.active)

            async def chunks():
                await asyncio.sleep(0.01)
                yield content

            try:
                yield SimpleNamespace(content_length=len(content), chunks=chunks())
            finally:
                self.active -= 1

        async def get_asset(self, _asset_id):
            return SimpleNamespace(
                asset_type="IMAGE", is_trashed=False, is_offline=False,
                file_modified_at=MODIFIED, file_size_bytes=len(content), checksum=None,
                width=384, height=384,
            )

    class Context:
        paused = False

        async def ensure_active(self):
            if self.paused:
                raise TaskPausedError()

    immich = Immich()
    repository = Repository()
    context = Context()
    maintainer = SimilarityDetailMaintainer(
        immich, repository, slots=2  # type: ignore[arg-type]
    )
    await maintainer.ensure(context, ids, {asset_id: search for asset_id in ids})  # type: ignore[arg-type]
    assert immich.peak <= 2
    assert len(repository.saved) == 4

    repository.saved.clear()
    context.paused = True
    with pytest.raises(TaskPausedError):
        await maintainer.ensure(context, ids, {asset_id: search for asset_id in ids})  # type: ignore[arg-type]
    assert repository.saved == {}
