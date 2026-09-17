"""Alpha-aware search evidence preserves transparency when previews flatten it."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest
from PIL import Image, ImageDraw

from companion.similarity_index_service import SimilarityIndexMaintainer
from companion.similarity_transparency import source_can_have_alpha

ASSET = UUID(int=1)
MODIFIED = datetime(2026, 9, 16, tzinfo=UTC)


def _encoded(image: Image.Image, image_format: str) -> bytes:
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def _source(*, name: str = "transparent.png", mime: str = "image/png"):
    return SimpleNamespace(
        id=ASSET,
        original_file_name=name,
        original_mime_type=mime,
        asset_type="IMAGE",
        is_trashed=False,
        is_offline=False,
        file_modified_at=MODIFIED,
        file_size_bytes=4096,
        checksum=None,
    )


@pytest.mark.parametrize(
    ("name", "mime", "expected"),
    [
        ("image.png", "image/png", True),
        ("image.webp", "application/octet-stream", True),
        ("image.avif", "image/avif; charset=binary", True),
        ("image.jpg", "image/jpeg", False),
    ],
)
def test_alpha_capable_source_detection(name: str, mime: str, expected: bool) -> None:
    assert source_can_have_alpha(_source(name=name, mime=mime)) is expected


@pytest.mark.asyncio
async def test_opaque_preview_for_alpha_capable_source_falls_back_to_original() -> None:
    preview = _encoded(Image.new("RGB", (64, 64), (40, 80, 120)), "JPEG")
    original_image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(original_image).rectangle((16, 16, 47, 47), fill=(40, 80, 120, 160))
    original = _encoded(original_image, "PNG")
    source = _source()

    class Immich:
        original_calls = 0

        async def get_bounded_preview(self, _asset_id, *, max_bytes):
            assert len(preview) < max_bytes
            return preview

        @asynccontextmanager
        async def stream_original(self, _asset_id):
            self.original_calls += 1

            async def chunks():
                yield original

            yield SimpleNamespace(content_length=len(original), chunks=chunks())

        async def get_asset(self, _asset_id):
            return source

    class Features:
        saved_origin = None
        saved_feature = None

        async def save(self, _source, _digest, feature, *, origin="preview"):
            self.saved_origin = origin
            self.saved_feature = feature
            return True

    class Context:
        async def ensure_active(self):
            return None

    immich = Immich()
    features = Features()
    maintainer = SimilarityIndexMaintainer(
        immich,  # type: ignore[arg-type]
        SimpleNamespace(),  # type: ignore[arg-type]
        features,  # type: ignore[arg-type]
    )

    succeeded, reason = await maintainer._fingerprint_unbounded(
        Context(), ASSET, source, attempt="test"  # type: ignore[arg-type]
    )

    assert succeeded is True
    assert reason is None
    assert immich.original_calls == 1
    assert features.saved_origin == "original"
    assert features.saved_feature is not None
    assert features.saved_feature.has_alpha is True
    assert maintainer.metrics()["alpha_preserving_original_fallbacks"] == 1
