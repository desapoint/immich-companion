from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from companion.duplicate_keeper_rules import choose_keeper
from companion.duplicate_schema import DuplicateKeeperRule


def _asset(**overrides):
    values = {
        "id": uuid4(),
        "library_id": None,
        "owner_id": None,
        "original_file_name": "photo.jpg",
        "original_path": "/photos/photo.jpg",
        "original_mime_type": "image/jpeg",
        "checksum": "abc",
        "asset_type": "IMAGE",
        "file_size_bytes": 100,
        "width": 100,
        "height": 100,
        "duration": None,
        "file_created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "file_modified_at": datetime(2024, 1, 1, tzinfo=UTC),
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC),
        "is_favorite": False,
        "is_archived": False,
        "is_offline": False,
        "is_edited": False,
        "has_metadata": False,
        "visibility": None,
        "live_photo_video_id": None,
        "tags": [],
        "stack": None,
        "exif_info": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _member(asset, **overrides):
    values = {
        "id": asset.id,
        "similarity": None,
        "admission": None,
        "preservation": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _group(assets, *, reference=None, members=None):
    return (
        SimpleNamespace(assets=tuple(assets)),
        SimpleNamespace(
            members=members or [_member(asset) for asset in assets],
            reference_asset_id=reference,
        ),
    )


def test_keeper_rules_prefer_highest_resolution_then_file_size() -> None:
    smaller = _asset(width=1920, height=1080, file_size_bytes=10_000)
    larger = _asset(width=6000, height=4000, file_size_bytes=8_000)
    source, exact = _group([smaller, larger])
    choice = choose_keeper(
        exact,
        source,
        [
            DuplicateKeeperRule(effect="prefer", field="resolution", operator="highest"),
            DuplicateKeeperRule(effect="prefer", field="file_size", operator="highest"),
        ],
        {},
    )
    assert choice.keeper_asset_id == larger.id
    assert choice.reason == "rules"


def test_keeper_rules_avoid_edited_when_original_exists() -> None:
    edited = _asset(is_edited=True, file_size_bytes=20_000)
    original = _asset(is_edited=False, file_size_bytes=10_000)
    source, exact = _group([edited, original])
    choice = choose_keeper(
        exact,
        source,
        [
            DuplicateKeeperRule(effect="avoid", field="edited", operator="is_true"),
            DuplicateKeeperRule(effect="prefer", field="file_size", operator="highest"),
        ],
        {},
    )
    assert choice.keeper_asset_id == original.id


def test_keeper_rules_require_folder_can_reject_group() -> None:
    first = _asset(original_path="/imports/a.jpg")
    second = _asset(original_path="/imports/b.jpg")
    source, exact = _group([first, second])
    choice = choose_keeper(
        exact,
        source,
        [
            DuplicateKeeperRule(
                effect="require",
                field="folder",
                operator="starts_with",
                value="/originals",
            )
        ],
        {},
    )
    assert choice.keeper_asset_id is None
    assert choice.reason == "requirement_unmatched"


def test_keeper_rules_reference_breaks_remaining_tie() -> None:
    first = _asset()
    second = _asset()
    source, exact = _group([first, second], reference=second.id)
    choice = choose_keeper(
        exact,
        source,
        [DuplicateKeeperRule(effect="prefer", field="availability", operator="is", value="online")],
        {},
    )
    assert choice.keeper_asset_id == second.id
    assert choice.used_reference_tiebreaker


def test_keeper_rules_album_membership_uses_relation_snapshot() -> None:
    album_id = uuid4()
    first = _asset()
    second = _asset()
    source, exact = _group([first, second])
    relations = {
        first.id: ({album_id}, set()),
        second.id: (set(), set()),
    }
    choice = choose_keeper(
        exact,
        source,
        [
            DuplicateKeeperRule(
                effect="prefer",
                field="album",
                operator="has_any",
                value=str(album_id),
            )
        ],
        relations,
    )
    assert choice.keeper_asset_id == first.id
