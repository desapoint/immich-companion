import pytest
from pydantic import ValidationError

from companion.duplicate_discovery_settings import DuplicateDiscoverySettings


def test_duplicate_discovery_settings_defaults_match_v2_discovery_defaults() -> None:
    settings = DuplicateDiscoverySettings()

    assert settings.include_exact is True
    assert settings.include_similar is True
    assert settings.similarity_threshold == 95.0
    assert settings.validation_mode == "strict"
    assert settings.max_link_depth == 2
    assert settings.max_candidates == 8


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("similarity_threshold", 49.9),
        ("similarity_threshold", 100.1),
        ("validation_mode", "unknown"),
        ("max_link_depth", -1),
        ("max_link_depth", 65),
        ("max_candidates", 0),
        ("max_candidates", 65),
    ],
)
def test_duplicate_discovery_settings_reject_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        DuplicateDiscoverySettings(**{field: value})
