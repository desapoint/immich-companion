from datetime import UTC, datetime
from uuid import UUID

from companion.asset_schema import AssetAlbumSummary, AssetSummary
from companion.models import AssetRecord

ASSET_ONE = UUID("11111111-1111-4111-8111-111111111111")
ASSET_TWO = UUID("22222222-2222-4222-8222-222222222222")
STACK_ID = UUID("55555555-5555-4555-8555-555555555555")
ALBUM_ID = UUID("66666666-6666-4666-8666-666666666666")
LIBRARY_ID = UUID("77777777-7777-4777-8777-777777777777")


def test_asset_summary_exposes_card_relations_and_stack_members() -> None:
    taken_at = datetime(2026, 8, 24, 12, 30, tzinfo=UTC)
    record = AssetRecord(
        id=ASSET_ONE,
        owner_id=None,
        library_id=LIBRARY_ID,
        asset_type="IMAGE",
        original_file_name="stack-primary.png",
        original_path="/external/demo/stack-primary.png",
        original_mime_type="image/png",
        width=1920,
        height=1080,
        duration=None,
        file_created_at=taken_at,
        file_modified_at=taken_at,
        is_favorite=False,
        is_archived=False,
        is_trashed=False,
        is_offline=False,
        is_edited=False,
        has_metadata=True,
        visibility="timeline",
        live_photo_video_id=None,
        exif_info={"fileSizeInByte": 2048},
        people=[],
        tags=[{"id": "tag-one", "name": "Landscape", "color": "#228855"}],
        stack={
            "id": str(STACK_ID),
            "primaryAssetId": str(ASSET_ONE),
            "assetCount": 2,
            "assets": [
                {
                    "id": str(ASSET_ONE),
                    "type": "IMAGE",
                    "originalFileName": "stack-primary.png",
                    "originalMimeType": "image/png",
                    "width": 1920,
                    "height": 1080,
                    "fileCreatedAt": taken_at.isoformat(),
                },
                {
                    "id": str(ASSET_TWO),
                    "type": "IMAGE",
                    "originalFileName": "stack-child.png",
                    "originalMimeType": "image/png",
                    "width": 1280,
                    "height": 720,
                    "fileCreatedAt": taken_at.isoformat(),
                },
            ],
        },
    )

    summary = AssetSummary.from_record(
        record,
        [AssetAlbumSummary(id=ALBUM_ID, name="Stack examples")],
    )

    assert [album.name for album in summary.albums] == ["Stack examples"]
    assert [(tag.id, tag.name, tag.color) for tag in summary.tags] == [
        ("tag-one", "Landscape", "#228855")
    ]
    assert summary.source.kind == "external"
    assert summary.source.library_id == LIBRARY_ID
    assert summary.source.original_path == "/external/demo/stack-primary.png"
    assert summary.stack is not None
    assert summary.stack.primary_asset_id == ASSET_ONE
    assert [member.id for member in summary.stack.assets] == [ASSET_ONE, ASSET_TWO]
    assert summary.stack.assets[1].original_file_name == "stack-child.png"


def test_upload_source_does_not_expose_internal_storage_path() -> None:
    taken_at = datetime(2026, 8, 24, 12, 30, tzinfo=UTC)
    record = AssetRecord(
        id=ASSET_ONE,
        owner_id=None,
        library_id=None,
        asset_type="IMAGE",
        original_file_name="upload.png",
        original_path="/data/upload/internal/upload.png",
        original_mime_type="image/png",
        width=800,
        height=600,
        duration=None,
        file_created_at=taken_at,
        file_modified_at=taken_at,
        is_favorite=False,
        is_archived=False,
        is_trashed=False,
        is_offline=False,
        is_edited=False,
        has_metadata=True,
        visibility="timeline",
        live_photo_video_id=None,
        exif_info={},
        people=[],
        tags=[],
        stack=None,
    )

    summary = AssetSummary.from_record(record)

    assert summary.source.kind == "upload"
    assert summary.source.library_id is None
    assert summary.source.original_path is None
