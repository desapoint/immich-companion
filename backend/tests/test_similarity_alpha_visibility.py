"""Low-alpha color noise is weighted by visibility instead of raw hidden RGB."""

from io import BytesIO

from PIL import Image

from companion.similarity_detail import compare_detail_features, extract_detail_feature
from companion.similarity_features import compare_visual_features, extract_visual_features


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _coarse(image: Image.Image):
    feature = extract_visual_features(BytesIO(_png(image)), "png")
    assert feature is not None
    return feature


def _detail(image: Image.Image):
    feature = extract_detail_feature(BytesIO(_png(image)), "png")
    assert feature is not None
    return feature


def test_low_alpha_color_difference_does_not_become_an_opaque_local_change() -> None:
    red = Image.new("RGBA", (128, 128), (255, 0, 0, 16))
    cyan = Image.new("RGBA", (128, 128), (0, 255, 255, 16))

    comparison = compare_detail_features(_detail(red), _detail(cyan))

    assert comparison.changed_percent == 0
    assert comparison.similarity_percent > 99


def test_low_alpha_color_difference_scores_closer_than_same_opaque_colors() -> None:
    translucent_red = Image.new("RGBA", (128, 128), (255, 0, 0, 16))
    translucent_cyan = Image.new("RGBA", (128, 128), (0, 255, 255, 16))
    opaque_red = Image.new("RGBA", (128, 128), (255, 0, 0, 255))
    opaque_cyan = Image.new("RGBA", (128, 128), (0, 255, 255, 255))

    translucent = compare_visual_features(_coarse(translucent_red), _coarse(translucent_cyan))
    opaque = compare_visual_features(_coarse(opaque_red), _coarse(opaque_cyan))

    assert translucent.similarity_percent > opaque.similarity_percent
