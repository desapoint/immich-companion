"""Local differences remain visible after bounded candidate-detail extraction."""

import asyncio
import zlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image, ImageDraw

from companion.similarity_detail import (
    DETAIL_FEATURE_VERSION,
    DETAIL_GRID_SIDE,
    DETAIL_SAMPLE_BYTES,
    DetailFeature,
    compare_detail_features,
    detail_diagnostics,
    extract_detail_feature,
)
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


def _notification_shade_scene(version: int) -> Image.Image:
    """Synthetic shared-UI screenshot whose notification content changes locally."""

    image = Image.new("RGB", (432, 768), (58, 36, 77))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 432, 260), fill=(96, 61, 124))
    for x in (24, 104, 184, 264, 344):
        draw.rounded_rectangle((x, 45, x + 56, 101), radius=20, fill=(132, 88, 165))
    draw.rounded_rectangle((25, 130, 407, 160), radius=15, fill=(127, 85, 159))
    draw.rectangle((0, 180, 432, 260), fill=(73, 48, 93))

    card_colors = (
        [(240, 238, 245), (224, 224, 235), (235, 235, 240)]
        if version == 0
        else [(240, 238, 245), (232, 232, 239), (240, 240, 244)]
    )
    icon_colors = (
        [(65, 90, 180), (120, 60, 140), (40, 120, 100)]
        if version == 0
        else [(180, 70, 80), (50, 110, 175), (150, 90, 60)]
    )
    text_widths = [210, 250, 180] if version == 0 else [155, 275, 235]
    y = 285
    for index in range(3):
        draw.rounded_rectangle((18, y, 414, y + 115), radius=18, fill=card_colors[index])
        draw.rectangle((35, y + 25, 90, y + 70), fill=icon_colors[index])
        draw.rectangle((110, y + 30, 110 + text_widths[index], y + 40), fill=(80, 80, 90))
        draw.rectangle(
            (110, y + 55, 110 + int(text_widths[index] * 0.75), y + 65),
            fill=(110, 110, 120),
        )
        y += 130
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


def test_detail_diagnostics_reuse_scoring_mask_and_expose_grid() -> None:
    original_image = _scene()
    changed_image = original_image.copy()
    ImageDraw.Draw(changed_image).rectangle((128, 192, 260, 330), fill=(15, 210, 210))

    original = extract_detail_feature(BytesIO(_encoded(original_image)), "png")
    changed = extract_detail_feature(BytesIO(_encoded(changed_image)), "png")

    assert original is not None and changed is not None
    identical = detail_diagnostics(original, original)
    diagnostics = detail_diagnostics(original, changed)
    score = compare_detail_features(original, changed)

    assert identical.changed_percent == 0
    assert identical.localized_changed_percent == 0
    assert identical.coherent_changed_percent == 0
    assert identical.largest_changed_region_percent == 0
    assert identical.substantial_region_count == 0
    assert identical.rows == DETAIL_GRID_SIDE
    assert identical.columns == DETAIL_GRID_SIDE
    assert len(identical.tile_changed_percents) == DETAIL_GRID_SIDE
    assert all(len(row) == DETAIL_GRID_SIDE for row in identical.tile_changed_percents)
    assert all(value == 0 for row in identical.tile_changed_percents for value in row)

    assert diagnostics.changed_percent == pytest.approx(score.changed_percent)
    assert diagnostics.localized_changed_percent > diagnostics.changed_percent > 0
    assert diagnostics.coherent_changed_percent > 0
    assert diagnostics.largest_changed_region_percent > 0
    assert diagnostics.substantial_region_count >= 1
    assert max(value for row in diagnostics.tile_changed_percents for value in row) >= 95


def test_localized_diagnostics_distinguish_coherent_edit_from_jpeg_noise() -> None:
    original_image = _scene()
    changed_image = original_image.copy()
    ImageDraw.Draw(changed_image).rectangle((145, 215, 240, 320), fill=(25, 100, 205))

    original = extract_detail_feature(BytesIO(_encoded(original_image)), "png")
    transcoded = extract_detail_feature(BytesIO(_encoded(original_image, "JPEG")), "jpeg")
    changed = extract_detail_feature(BytesIO(_encoded(changed_image)), "png")

    assert original is not None and transcoded is not None and changed is not None
    transcode_diagnostics = detail_diagnostics(original, transcoded)
    changed_diagnostics = detail_diagnostics(original, changed)

    assert transcode_diagnostics.coherent_changed_percent == 0
    assert transcode_diagnostics.largest_changed_region_percent == 0
    assert transcode_diagnostics.substantial_region_count == 0
    assert (
        changed_diagnostics.localized_changed_percent
        > transcode_diagnostics.localized_changed_percent
    )
    assert changed_diagnostics.changed_percent > transcode_diagnostics.changed_percent
    assert changed_diagnostics.coherent_changed_percent > 0
    assert changed_diagnostics.largest_changed_region_percent > 0
    assert max(value for row in changed_diagnostics.tile_changed_percents for value in row) > max(
        value for row in transcode_diagnostics.tile_changed_percents for value in row
    )


def test_shared_ui_with_changed_notifications_falls_below_95_percent() -> None:
    first = extract_detail_feature(BytesIO(_encoded(_notification_shade_scene(0))), "png")
    second = extract_detail_feature(BytesIO(_encoded(_notification_shade_scene(1))), "png")

    assert first is not None and second is not None
    score = compare_detail_features(first, second)
    diagnostics = detail_diagnostics(first, second)

    assert score.similarity_percent < 95
    assert diagnostics.changed_percent > 0
    assert diagnostics.coherent_changed_percent > 1
    assert diagnostics.largest_changed_region_percent > 0.5
    assert diagnostics.substantial_region_count >= 2


def test_coherent_face_and_swimsuit_edits_are_not_hidden_by_unchanged_background() -> None:
    original = Image.new("RGB", (1024, 1024), (90, 115, 145))
    draw = ImageDraw.Draw(original)
    draw.ellipse((300, 80, 720, 500), fill=(235, 190, 155))
    draw.rectangle((355, 470, 670, 930), fill=(205, 70, 100))
    strap = original.copy()
    ImageDraw.Draw(strap).rectangle((472, 470, 492, 615), fill=(30, 80, 180))
    face = original.copy()
    ImageDraw.Draw(face).rectangle((405, 265, 620, 330), fill=(35, 35, 45))
    swimsuit = original.copy()
    ImageDraw.Draw(swimsuit).rectangle((390, 590, 640, 850), fill=(45, 95, 180))

    reference = extract_detail_feature(BytesIO(_encoded(original)), "png")
    jpeg = extract_detail_feature(BytesIO(_encoded(original, "JPEG")), "jpeg")
    variants = [
        extract_detail_feature(BytesIO(_encoded(image)), "png")
        for image in (strap, face, swimsuit)
    ]
    assert reference is not None and jpeg is not None and all(variants)
    scores = [compare_detail_features(reference, variant) for variant in variants]

    assert DETAIL_FEATURE_VERSION == 2
    assert compare_detail_features(reference, reference).similarity_percent == 100
    assert compare_detail_features(reference, jpeg).similarity_percent >= 98.5
    assert scores[2].similarity_percent < scores[1].similarity_percent < 95
    assert 95 < scores[0].similarity_percent < 100
    assert 0 < scores[0].changed_percent < scores[1].changed_percent


def test_old_256_pixel_detail_sample_cannot_be_scored_as_current() -> None:
    current = extract_detail_feature(BytesIO(_encoded(_scene())), "png")
    assert current is not None
    old = DetailFeature(384, 384, zlib.compress(bytes(256 * 256 * 3)))
    assert len(zlib.decompress(current.sample)) == DETAIL_SAMPLE_BYTES
    with pytest.raises(ValueError, match="incompatible"):
        compare_detail_features(current, old)


def test_oversized_detail_sample_is_rejected() -> None:
    current = extract_detail_feature(BytesIO(_encoded(_scene())), "png")
    assert current is not None
    oversized = DetailFeature(384, 384, zlib.compress(bytes(DETAIL_SAMPLE_BYTES + 1)))
    with pytest.raises(ValueError, match="incompatible"):
        compare_detail_features(current, oversized)


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
