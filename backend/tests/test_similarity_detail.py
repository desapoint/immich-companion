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

from companion import similarity_detail
from companion.similarity_detail import (
    DETAIL_FEATURE_VERSION,
    DETAIL_GRID_SIDE,
    DETAIL_SAMPLE_BYTES,
    DetailFeature,
    _aligned_detail_images,
    _analyze_images,
    _detail_images,
    _DetailAlignment,
    _estimate_alignment,
    _estimate_legacy_alignment,
    _inclusive_candidates,
    _transform_alignment_frame,
    compare_detail_features,
    detail_diagnostics,
    extract_detail_feature,
)
from companion.similarity_detail_service import SimilarityDetailMaintainer
from companion.task_coordinator import TaskPausedError

ASSET = UUID(int=1)
MODIFIED = datetime(2026, 9, 14, tzinfo=UTC)


@pytest.mark.parametrize(
    ("limit", "step"),
    [(5, 4), (64, 12), (7, 3)],
)
def test_staged_translation_candidates_include_both_symmetric_limits(
    limit: int, step: int
) -> None:
    candidates = _inclusive_candidates(limit, step)

    assert candidates[0] == -limit
    assert candidates[-1] == limit
    assert -limit in candidates and limit in candidates
    assert set(candidates) == {-candidate for candidate in candidates}


def test_default_alignment_keeps_the_exact_legacy_estimator_result() -> None:
    reference_image = _burst_scene().crop((48, 48, 560, 560))
    selected_image = _burst_scene((5, 3)).crop((64, 56, 576, 568))
    reference = extract_detail_feature(BytesIO(_encoded(reference_image)), "png")
    selected = extract_detail_feature(BytesIO(_encoded(selected_image)), "png")
    assert reference is not None and selected is not None
    left, right = _detail_images(reference, selected)

    assert _estimate_alignment(left, right) == _estimate_legacy_alignment(left, right)


def test_configured_local_alignment_does_not_flow_into_comparison_validation(
    monkeypatch,
) -> None:
    reference_image = _burst_scene().crop((48, 48, 560, 560))
    selected_image = _burst_scene((5, 3)).crop((64, 56, 576, 568))
    reference = extract_detail_feature(BytesIO(_encoded(reference_image)), "png")
    selected = extract_detail_feature(BytesIO(_encoded(selected_image)), "png")
    assert reference is not None and selected is not None
    original = similarity_detail._estimate_alignment
    calls: list[dict[str, object]] = []

    def record_alignment(left_image, right_image, **settings):
        calls.append(settings)
        return original(left_image, right_image, **settings)

    monkeypatch.setattr(similarity_detail, "_estimate_alignment", record_alignment)
    compare_detail_features(reference, selected)
    assert calls[-1] == {
        "max_shift_fraction": similarity_detail.DETAIL_ALIGNMENT_MAX_SHIFT_FRACTION,
        "max_rotation_degrees": similarity_detail.DETAIL_ALIGNMENT_MAX_ROTATION_DEGREES,
        "max_zoom_percent": similarity_detail.DETAIL_ALIGNMENT_MAX_ZOOM_PERCENT,
    }

    detail_diagnostics(
        reference,
        selected,
        max_shift_fraction=0.5,
        max_rotation_degrees=30,
        max_zoom_percent=50,
    )
    assert calls[-1] == {
        "max_shift_fraction": 0.5,
        "max_rotation_degrees": 30,
        "max_zoom_percent": 50,
    }


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


def _burst_scene(subject_offset: tuple[int, int] = (0, 0)) -> Image.Image:
    """Synthetic textured scene for nearby handheld frames."""

    image = Image.new("RGB", (640, 640), (85, 105, 140))
    draw = ImageDraw.Draw(image)
    for x in range(0, 640, 32):
        draw.line((x, 0, x, 640), fill=(75 + (x // 32) % 3 * 8, 95, 125), width=2)
    for y in range(0, 640, 40):
        draw.line((0, y, 640, y), fill=(80, 100 + (y // 40) % 3 * 7, 130), width=2)
    draw.rectangle((70, 80, 220, 180), fill=(150, 120, 90))
    draw.rectangle((445, 110, 575, 250), fill=(90, 150, 110))
    draw.ellipse((480, 360, 590, 500), fill=(170, 120, 170))
    offset_x, offset_y = subject_offset
    draw.ellipse(
        (250 + offset_x, 110 + offset_y, 410 + offset_x, 270 + offset_y),
        fill=(230, 185, 150),
    )
    draw.rectangle(
        (290 + offset_x, 260 + offset_y, 380 + offset_x, 520 + offset_y),
        fill=(205, 75, 100),
    )
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


def test_small_handheld_frame_shift_is_compensated_without_warping_raw_grid() -> None:
    reference_image = _burst_scene().crop((48, 48, 560, 560))
    selected_image = _burst_scene((5, 3)).crop((64, 56, 576, 568))

    reference = extract_detail_feature(BytesIO(_encoded(reference_image)), "png")
    selected = extract_detail_feature(BytesIO(_encoded(selected_image)), "png")

    assert reference is not None and selected is not None
    score = compare_detail_features(reference, selected)
    diagnostics = detail_diagnostics(reference, selected)

    assert diagnostics.alignment_applied is True
    assert 1 < diagnostics.alignment_shift_percent < 10
    assert 90 < diagnostics.alignment_overlap_percent < 100
    assert diagnostics.changed_percent > diagnostics.aligned_changed_percent
    assert diagnostics.aligned_changed_percent < diagnostics.changed_percent / 2
    assert score.changed_percent == pytest.approx(diagnostics.aligned_changed_percent)
    assert diagnostics.raw_similarity_percent < diagnostics.aligned_similarity_percent
    assert diagnostics.aligned_similarity_percent == pytest.approx(score.similarity_percent)
    assert score.similarity_percent > 93


def test_rotation_search_is_disabled_by_default_and_honors_configured_limit(monkeypatch) -> None:
    reference_image = _burst_scene().crop((48, 48, 560, 560))
    rolled_image = reference_image.rotate(3, resample=Image.Resampling.BICUBIC)
    reference = extract_detail_feature(BytesIO(_encoded(reference_image)), "png")
    rolled = extract_detail_feature(BytesIO(_encoded(rolled_image)), "png")

    assert reference is not None and rolled is not None

    def unexpected_rotation(*_args, **_kwargs):
        raise AssertionError("default comparison must not run rotational search")

    monkeypatch.setattr(Image.Image, "rotate", unexpected_rotation)
    default_diagnostics = detail_diagnostics(reference, rolled)
    zero_limit_diagnostics = detail_diagnostics(reference, rolled, max_rotation_degrees=0)
    assert default_diagnostics == zero_limit_diagnostics
    assert default_diagnostics.alignment_rotation_degrees == 0

    monkeypatch.undo()
    configured_diagnostics = detail_diagnostics(
        reference,
        rolled,
        max_rotation_degrees=3,
    )

    assert configured_diagnostics.alignment_rotation_degrees == -3
    assert (
        configured_diagnostics.aligned_changed_percent
        < default_diagnostics.aligned_changed_percent
    )
    assert (
        configured_diagnostics.aligned_similarity_percent
        > default_diagnostics.aligned_similarity_percent
    )
    assert 0 < configured_diagnostics.alignment_overlap_percent < 100


def test_rotation_padding_is_excluded_but_source_transparency_is_counted() -> None:
    opaque = Image.new("RGBA", (512, 512), (40, 70, 100, 255))
    opaque_feature = extract_detail_feature(BytesIO(_encoded(opaque)), "png")
    assert opaque_feature is not None
    left, right = _detail_images(opaque_feature, opaque_feature)
    aligned_left, aligned_right, valid_pixels = _aligned_detail_images(
        left,
        right,
        _DetailAlignment(rotation_degrees=3, applied=True),
    )
    assert valid_pixels is not None

    unmasked = _analyze_images(aligned_left, aligned_right)
    masked = _analyze_images(aligned_left, aligned_right, valid_pixels)
    assert unmasked.changed_fraction > 0
    assert masked.changed_fraction == 0

    changed = opaque.copy()
    changed.putalpha(255)
    changed_draw = ImageDraw.Draw(changed)
    changed_draw.rectangle((220, 220, 290, 290), fill=(40, 70, 100, 0))
    changed_feature = extract_detail_feature(BytesIO(_encoded(changed)), "png")
    assert changed_feature is not None
    _, changed_image = _detail_images(opaque_feature, changed_feature)
    _, aligned_changed, changed_validity = _aligned_detail_images(
        left,
        changed_image,
        _DetailAlignment(rotation_degrees=3, applied=True),
    )
    assert changed_validity is not None
    genuine_transparency = _analyze_images(left, aligned_changed, changed_validity)
    assert genuine_transparency.changed_fraction > 0


def test_scale_compensation_recovers_center_zoom_and_reports_zoom_and_overlap() -> None:
    reference_image = _burst_scene().crop((64, 64, 576, 576))
    enlarged = reference_image.resize((614, 614), Image.Resampling.BICUBIC).crop((51, 51, 563, 563))
    reference = extract_detail_feature(BytesIO(_encoded(reference_image)), "png")
    zoomed = extract_detail_feature(BytesIO(_encoded(enlarged)), "png")
    assert reference is not None and zoomed is not None

    raw = detail_diagnostics(reference, zoomed)
    aligned = detail_diagnostics(reference, zoomed, max_zoom_percent=20)

    assert raw.alignment_zoom_percent == 0
    assert aligned.alignment_applied is True
    assert aligned.alignment_zoom_percent != 0
    assert aligned.aligned_changed_percent < raw.changed_percent
    assert 70 < aligned.alignment_overlap_percent < 100


def test_zoom_padding_mask_excludes_synthetic_pixels_and_keeps_source_alpha() -> None:
    opaque = Image.new("RGBA", (512, 512), (40, 70, 100, 255))
    feature = extract_detail_feature(BytesIO(_encoded(opaque)), "png")
    assert feature is not None
    left, right = _detail_images(feature, feature)
    aligned_left, aligned_right, mask = _aligned_detail_images(
        left, right, _DetailAlignment(zoom_percent=-20, applied=True)
    )
    assert mask is not None
    assert _analyze_images(aligned_left, aligned_right).changed_fraction > 0
    assert _analyze_images(aligned_left, aligned_right, mask).changed_fraction == 0


def test_combined_zoom_rotation_uses_estimator_transform_order_and_masks_padding() -> None:
    reference_image = _burst_scene().crop((32, 32, 544, 544)).convert("RGBA")
    draw = ImageDraw.Draw(reference_image)
    draw.rectangle((0, 195, 24, 320), fill=(255, 210, 30, 255))
    draw.rectangle((488, 170, 511, 340), fill=(20, 240, 240, 255))
    transformed, _ = _transform_alignment_frame(
        reference_image,
        -15,
        8,
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )
    reference = extract_detail_feature(BytesIO(_encoded(reference_image)), "png")
    selected = extract_detail_feature(BytesIO(_encoded(transformed)), "png")
    assert reference is not None and selected is not None

    raw = detail_diagnostics(reference, selected)
    aligned = detail_diagnostics(
        reference,
        selected,
        max_rotation_degrees=12,
        max_zoom_percent=20,
    )
    left, right = _detail_images(reference, selected)
    alignment = similarity_detail._estimate_alignment(
        left,
        right,
        max_rotation_degrees=12,
        max_zoom_percent=20,
    )
    aligned_left, aligned_right, validity = _aligned_detail_images(left, right, alignment)

    assert aligned.alignment_applied is True
    assert aligned.alignment_rotation_degrees != 0
    assert aligned.alignment_zoom_percent != 0
    assert aligned.aligned_changed_percent < raw.changed_percent * 0.6
    assert 0 < aligned.alignment_overlap_percent < 100
    assert validity is not None and not validity.all()
    assert _analyze_images(aligned_left, aligned_right, validity).changed_fraction < (
        _analyze_images(aligned_left, aligned_right).changed_fraction
    )


def test_jpeg_transcode_of_same_scene_remains_high_similarity() -> None:
    original = extract_detail_feature(BytesIO(_encoded(_scene())), "png")
    transcoded = extract_detail_feature(BytesIO(_encoded(_scene(), "JPEG")), "jpeg")

    assert original is not None and transcoded is not None
    assert compare_detail_features(original, transcoded).similarity_percent > 95


def test_hidden_rgb_under_transparency_does_not_create_detail_change() -> None:
    red_hidden = Image.new("RGBA", (128, 128), (255, 0, 0, 0))
    cyan_hidden = Image.new("RGBA", (128, 128), (0, 220, 255, 0))

    first = extract_detail_feature(BytesIO(_encoded(red_hidden)), "png")
    second = extract_detail_feature(BytesIO(_encoded(cyan_hidden)), "png")

    assert first is not None and second is not None
    score = compare_detail_features(first, second)
    diagnostics = detail_diagnostics(first, second)
    assert score.similarity_percent == 100
    assert score.changed_percent == 0
    assert diagnostics.localized_changed_percent == 0
    assert diagnostics.coherent_changed_percent == 0
    assert diagnostics.substantial_region_count == 0


def test_alpha_mask_change_remains_visible_even_for_black_pixels() -> None:
    transparent = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    visible = transparent.copy()
    ImageDraw.Draw(visible).rectangle((32, 32, 95, 95), fill=(0, 0, 0, 255))

    first = extract_detail_feature(BytesIO(_encoded(transparent)), "png")
    second = extract_detail_feature(BytesIO(_encoded(visible)), "png")

    assert first is not None and second is not None
    score = compare_detail_features(first, second)
    diagnostics = detail_diagnostics(first, second)
    assert score.similarity_percent < 100
    assert score.changed_percent > 0
    assert diagnostics.coherent_changed_percent > 0
    assert diagnostics.largest_changed_region_percent > 0
    assert diagnostics.substantial_region_count >= 1


def test_detail_diagnostics_keep_raw_grid_separate_from_aligned_score() -> None:
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

    assert diagnostics.aligned_changed_percent == pytest.approx(score.changed_percent)
    assert diagnostics.changed_percent > 0
    assert diagnostics.localized_changed_percent > diagnostics.changed_percent
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


def test_localized_face_and_outfit_changes_stay_high_when_most_pixels_match() -> None:
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

    assert DETAIL_FEATURE_VERSION == 4
    assert compare_detail_features(reference, reference).similarity_percent == 100
    assert compare_detail_features(reference, jpeg).similarity_percent >= 98.5
    assert 97 < scores[2].similarity_percent < scores[1].similarity_percent
    assert scores[1].similarity_percent < scores[0].similarity_percent < 100
    assert 0 < scores[0].changed_percent < scores[1].changed_percent
    assert scores[1].changed_percent < scores[2].changed_percent


def test_equal_changed_area_scores_lower_when_split_across_distant_zones() -> None:
    original = Image.new("RGB", (1024, 1024), (88, 112, 142))
    draw = ImageDraw.Draw(original)
    for offset in range(0, 1024, 64):
        draw.line((offset, 0, offset, 1024), fill=(80, 103, 132), width=2)
        draw.line((0, offset, 1024, offset), fill=(80, 103, 132), width=2)

    localized = original.copy()
    ImageDraw.Draw(localized).rectangle((392, 392, 631, 631), fill=(210, 70, 105))

    two_zones = original.copy()
    two_draw = ImageDraw.Draw(two_zones)
    two_draw.rectangle((120, 120, 289, 289), fill=(210, 70, 105))
    two_draw.rectangle((735, 735, 904, 904), fill=(210, 70, 105))

    four_zones = original.copy()
    four_draw = ImageDraw.Draw(four_zones)
    for box in (
        (100, 100, 219, 219),
        (804, 100, 923, 219),
        (100, 804, 219, 923),
        (804, 804, 923, 923),
    ):
        four_draw.rectangle(box, fill=(210, 70, 105))

    reference = extract_detail_feature(BytesIO(_encoded(original)), "png")
    variants = [
        extract_detail_feature(BytesIO(_encoded(image)), "png")
        for image in (localized, two_zones, four_zones)
    ]
    assert reference is not None and all(variants)

    scores = [compare_detail_features(reference, variant) for variant in variants]
    changed = [score.changed_percent for score in scores]

    # Keep the changed coverage comparable so the ordering comes from how many
    # places changed and how far those zones are distributed, not simply area.
    assert max(changed) - min(changed) < 1.5
    assert scores[0].similarity_percent > 97
    assert scores[0].similarity_percent > scores[1].similarity_percent
    assert scores[1].similarity_percent > scores[2].similarity_percent
    assert scores[0].similarity_percent - scores[2].similarity_percent > 3


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
@pytest.mark.parametrize("preview_format", ["JPEG", "PNG"])
async def test_invalid_original_uses_preview_fallback_and_reuses_detail(
    preview_format: str,
) -> None:
    preview = _encoded(_scene(), preview_format)
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
        preview_calls = 0

        @asynccontextmanager
        async def stream_original(self, asset_id):
            self.original_calls += 1

            async def chunks():
                yield b"invalid HEIC"

            yield SimpleNamespace(content_length=12, chunks=chunks())

        async def get_bounded_fullsize(self, *_args, **_kwargs):
            pytest.fail("Unified normalizer must not use Immich full-size")

        async def get_bounded_preview(self, asset_id, *, max_bytes):
            self.preview_calls += 1
            assert len(preview) < max_bytes
            return preview

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
    await maintainer.ensure(  # type: ignore[arg-type]
        Context(), [ASSET], {ASSET: search}, evidence_epoch=1
    )
    assert maintainer.counters["detail_features_generated"] == 1
    maintainer.reset_counters()
    await maintainer.ensure(  # type: ignore[arg-type]
        Context(), [ASSET], {ASSET: search}, evidence_epoch=1
    )

    assert repository.origins == ["preview_fallback"]
    assert (immich.original_calls, immich.preview_calls) == (1, 1)
    assert maintainer.counters["detail_features_reused"] == 1
    assert maintainer.counters["detail_features_generated"] == 0
    assert maintainer.counters["detail_original_bytes"] == 0


@pytest.mark.asyncio
async def test_reduced_preview_response_is_labeled_lower_grade() -> None:
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

        async def get_bounded_preview(self, _asset_id, *, max_bytes):
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
    maintainer = SimilarityDetailMaintainer(
        Immich(), repository  # type: ignore[arg-type]
    )
    await maintainer.ensure(  # type: ignore[arg-type]
        Context(), [ASSET], {ASSET: search}, evidence_epoch=1
    )

    assert repository.origin == "preview_fallback"
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
    await maintainer.ensure(  # type: ignore[arg-type]
        context,
        ids,
        {asset_id: search for asset_id in ids},
        evidence_epoch=1,
    )
    assert immich.peak <= 2
    assert len(repository.saved) == 4

    repository.saved.clear()
    context.paused = True
    with pytest.raises(TaskPausedError):
        await maintainer.ensure(  # type: ignore[arg-type]
            context,
            ids,
            {asset_id: search for asset_id in ids},
            evidence_epoch=1,
        )
    assert repository.saved == {}
