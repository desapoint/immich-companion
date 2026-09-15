"""Rule-driven keeper selection for V2 duplicate review drafts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from companion.discovery.base import DiscoveredGroup
from companion.duplicate_schema import DuplicateKeeperRule, ExactDuplicateGroup


@dataclass(frozen=True, slots=True)
class DuplicateKeeperChoice:
    keeper_asset_id: UUID | None
    reason: str
    used_reference_tiebreaker: bool = False


def _text(value: object | None) -> str:
    return "" if value is None else str(value)


def _folder(path: str | None) -> str:
    if not path:
        return ""
    normalized = path.replace("\\", "/")
    return str(PurePosixPath(normalized).parent)


def _extension(name: str) -> str:
    suffix = PurePosixPath(name).suffix.casefold()
    return suffix[1:] if suffix.startswith(".") else suffix


def _format_quality(asset: Any) -> float:
    extension = _extension(asset.original_file_name)
    mime = (asset.original_mime_type or "").casefold()
    if extension in {"dng", "nef", "cr2", "cr3", "arw", "raf", "rw2", "orf", "pef"}:
        return 5.0
    if "raw" in mime or "dng" in mime:
        return 5.0
    if extension in {"tif", "tiff", "png"} or mime in {"image/tiff", "image/png"}:
        return 4.0
    if extension in {"heic", "heif", "avif"} or any(
        marker in mime for marker in ("heic", "heif", "avif")
    ):
        return 3.0
    if extension in {"jpg", "jpeg", "webp"} or any(
        marker in mime for marker in ("jpeg", "webp")
    ):
        return 2.0
    return 1.0


def _stack_primary(asset: Any) -> bool:
    stack = asset.stack or {}
    primary = (
        stack.get("primaryAssetId")
        or stack.get("primary_asset_id")
        or stack.get("primaryId")
        or stack.get("primary_id")
    )
    return primary is not None and str(primary) == str(asset.id)


def _tag_values(asset: Any, relation_ids: tuple[set[UUID], set[UUID]]) -> list[str]:
    values = {str(tag_id) for tag_id in relation_ids[1]}
    for tag in asset.tags or []:
        if not isinstance(tag, dict):
            continue
        for key in ("id", "name", "value"):
            value = tag.get(key)
            if value:
                values.add(str(value))
    return sorted(values)


def _metadata_richness(asset: Any, member: Any) -> float:
    preservation = getattr(member, "preservation", None)
    value = getattr(preservation, "metadata_richness", None)
    if isinstance(value, int | float):
        return float(value)
    return float(
        sum(
            value not in (None, "", False, [], {})
            for value in (asset.exif_info or {}).values()
        )
    )


def _member_value(
    field: str,
    *,
    asset: Any,
    member: Any,
    reference_asset: Any | None,
    reference_asset_id: UUID | None,
    relation_ids: tuple[set[UUID], set[UUID]],
) -> object | None:
    if field == "library":
        return "upload" if asset.library_id is None else str(asset.library_id)
    if field == "folder":
        return _folder(asset.original_path)
    if field == "filename":
        return asset.original_file_name
    if field == "extension":
        return _extension(asset.original_file_name)
    if field == "mime_type":
        return asset.original_mime_type
    if field == "media_type":
        return asset.asset_type.casefold()
    if field == "date":
        return asset.local_date_time or asset.file_created_at
    if field == "modified_date":
        return asset.file_modified_at
    if field == "immich_created_at":
        return asset.created_at
    if field == "immich_updated_at":
        return asset.updated_at
    if field == "file_size":
        return asset.file_size_bytes
    if field == "resolution":
        return (
            asset.width * asset.height
            if asset.width is not None and asset.height is not None
            else None
        )
    if field == "width":
        return asset.width
    if field == "height":
        return asset.height
    if field == "aspect_ratio":
        return (
            asset.width / asset.height
            if asset.width is not None and asset.height not in {None, 0}
            else None
        )
    if field == "favorite":
        return asset.is_favorite
    if field == "archived":
        return asset.is_archived
    if field == "availability":
        return "offline" if asset.is_offline else "online"
    if field == "edited":
        return asset.is_edited
    if field == "has_metadata":
        return asset.has_metadata
    if field == "visibility":
        return asset.visibility or ""
    if field == "live_photo":
        return bool(asset.live_photo_video_id)
    if field == "tag":
        return _tag_values(asset, relation_ids)
    if field == "album":
        return sorted(str(album_id) for album_id in relation_ids[0])
    if field == "has_tag":
        return bool(relation_ids[1] or asset.tags)
    if field == "has_album":
        return bool(relation_ids[0])
    if field == "stack_membership":
        return asset.stack is not None
    if field == "stack_primary":
        return _stack_primary(asset)
    if field == "owner":
        return str(asset.owner_id) if asset.owner_id else ""
    if field == "checksum":
        return asset.checksum or getattr(member, "content_checksum", None)
    if field == "reference":
        return reference_asset_id is not None and asset.id == reference_asset_id
    similarity = getattr(member, "similarity", None)
    if field == "similarity":
        return getattr(similarity, "similarity_percent", None)
    if field == "structural_similarity":
        return getattr(similarity, "structural_percent", None)
    if field == "perceptual_similarity":
        return getattr(similarity, "perceptual_percent", None)
    if field == "color_similarity":
        return getattr(similarity, "color_percent", None)
    if field == "detail_change":
        return getattr(similarity, "detail_changed_percent", None)
    admission = getattr(member, "admission", None)
    if field == "admission_similarity":
        return getattr(admission, "admission_similarity_percent", None)
    if field == "link_depth":
        return getattr(admission, "link_depth", None)
    if field == "duration":
        return asset.duration
    if field == "same_folder_as_reference":
        return reference_asset is not None and _folder(asset.original_path) == _folder(
            reference_asset.original_path
        )
    if field == "same_library_as_reference":
        return reference_asset is not None and asset.library_id == reference_asset.library_id
    if field == "same_mime_as_reference":
        return (
            reference_asset is not None
            and asset.original_mime_type == reference_asset.original_mime_type
        )
    if field == "metadata_richness":
        return _metadata_richness(asset, member)
    if field == "format_quality":
        return _format_quality(asset)
    return None


def _values(value: str) -> list[str]:
    return [part.strip().casefold() for part in value.split(",") if part.strip()]


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _as_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _matches(actual: object | None, rule: DuplicateKeeperRule) -> bool:
    operator = rule.operator
    expected = rule.value.strip()

    if operator == "is_true":
        return actual is True
    if operator == "is_false":
        return actual is False

    if isinstance(actual, list):
        actual_values = {_text(item).casefold() for item in actual}
        wanted = set(_values(expected))
        if operator == "has_any":
            return bool(actual_values & wanted)
        if operator == "has_all":
            return bool(wanted) and wanted.issubset(actual_values)
        if operator == "has_none":
            return not bool(actual_values & wanted)
        return False

    if isinstance(actual, bool):
        normalized = expected.casefold()
        expected_bool = normalized in {"true", "1", "yes", "online"}
        if operator == "is":
            return actual is expected_bool
        if operator == "is_not":
            return actual is not expected_bool
        return False

    if isinstance(actual, datetime):
        other = _as_datetime(expected)
        if other is None:
            return False
        if actual.tzinfo is None and other.tzinfo is not None:
            other = other.replace(tzinfo=None)
        if actual.tzinfo is not None and other.tzinfo is None:
            other = other.replace(tzinfo=actual.tzinfo)
        if operator == "gt":
            return actual > other
        if operator == "gte":
            return actual >= other
        if operator == "lt":
            return actual < other
        if operator == "lte":
            return actual <= other
        if operator == "is":
            return actual == other
        if operator == "is_not":
            return actual != other
        return False

    if isinstance(actual, int | float):
        other = _as_float(expected)
        if other is None:
            return False
        if operator == "gt":
            return actual > other
        if operator == "gte":
            return actual >= other
        if operator == "lt":
            return actual < other
        if operator == "lte":
            return actual <= other
        if operator == "is":
            return float(actual) == other
        if operator == "is_not":
            return float(actual) != other
        return False

    actual_text = _text(actual).casefold()
    expected_text = expected.casefold()
    if operator == "is":
        if "," in expected:
            return actual_text in set(_values(expected))
        return actual_text == expected_text
    if operator == "is_not":
        if "," in expected:
            return actual_text not in set(_values(expected))
        return actual_text != expected_text
    if operator == "contains":
        return expected_text in actual_text
    if operator == "not_contains":
        return expected_text not in actual_text
    if operator == "starts_with":
        return actual_text.startswith(expected_text)
    if operator == "ends_with":
        return actual_text.endswith(expected_text)
    return False


def choose_keeper(
    exact_group: ExactDuplicateGroup,
    source_group: DiscoveredGroup,
    rules: list[DuplicateKeeperRule],
    relations: dict[UUID, tuple[set[UUID], set[UUID]]],
) -> DuplicateKeeperChoice:
    """Choose one keeper lexicographically from ordered require/prefer/avoid rules."""

    assets = {asset.id: asset for asset in source_group.assets}
    members = {member.id: member for member in exact_group.members}
    reference_id = exact_group.reference_asset_id
    reference_asset = assets.get(reference_id) if reference_id is not None else None
    candidates = [asset_id for asset_id in assets if asset_id in members]
    if len(candidates) < 2:
        return DuplicateKeeperChoice(None, "missing_members")

    def value(asset_id: UUID, rule: DuplicateKeeperRule) -> object | None:
        return _member_value(
            rule.field,
            asset=assets[asset_id],
            member=members[asset_id],
            reference_asset=reference_asset,
            reference_asset_id=reference_id,
            relation_ids=relations.get(asset_id, (set(), set())),
        )

    for rule in rules:
        if rule.effect != "require":
            continue
        matched = [
            asset_id
            for asset_id in candidates
            if rule.operator not in {"highest", "lowest"}
            and _matches(value(asset_id, rule), rule)
        ]
        if not matched:
            return DuplicateKeeperChoice(None, "requirement_unmatched")
        candidates = matched

    for rule in rules:
        if rule.effect == "require":
            continue
        if rule.operator in {"highest", "lowest"}:
            valued = []
            for asset_id in candidates:
                item_value = value(asset_id, rule)
                if item_value is not None:
                    valued.append((item_value, asset_id))
            if not valued:
                continue
            best_value = (
                max(item[0] for item in valued)
                if rule.operator == "highest"
                else min(item[0] for item in valued)
            )
            selected = [asset_id for item_value, asset_id in valued if item_value == best_value]
            if rule.effect == "prefer":
                candidates = selected
            elif rule.effect == "avoid":
                survivors = [asset_id for asset_id in candidates if asset_id not in selected]
                if survivors:
                    candidates = survivors
            continue

        matching = [asset_id for asset_id in candidates if _matches(value(asset_id, rule), rule)]
        if rule.effect == "prefer":
            if matching:
                candidates = matching
        elif rule.effect == "avoid":
            matching_set = set(matching)
            survivors = [asset_id for asset_id in candidates if asset_id not in matching_set]
            if survivors:
                candidates = survivors

    if len(candidates) == 1:
        return DuplicateKeeperChoice(candidates[0], "rules")
    if reference_id is not None and reference_id in candidates:
        return DuplicateKeeperChoice(reference_id, "reference_tiebreaker", True)
    return DuplicateKeeperChoice(None, "ambiguous")
