"""Booru policy changes keep marker and rating tags reversible."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from companion.booru_service import MODELS, BooruService, BooruSettingsView, BooruTaskHandler
from companion.config import Settings


class FakeSession:
    def __init__(self, record):
        self.record = record

    async def get(self, model, key):
        return self.record


class FakeSessions:
    def __init__(self, record):
        self.session = FakeSession(record)

    @asynccontextmanager
    async def __call__(self):
        yield self.session

    @asynccontextmanager
    async def begin(self):
        yield self.session


class FakeAssetRepository:
    def __init__(self):
        self.snapshots = []

    async def refresh_asset_tag_snapshot(self, asset, catalog):
        self.snapshots.append((asset, list(catalog)))


class FakeImmich:
    def __init__(self):
        self.catalog = []
        self.assigned = []

    async def list_tag_catalog(self):
        return list(self.catalog)

    async def create_tag(self, name, parent_id=None):
        tag = SimpleNamespace(id=uuid4(), name=name, parent_id=parent_id)
        self.catalog.append(tag)
        return tag

    async def add_tags_to_asset(self, asset_id, tag_ids):
        self.assigned.extend(tag_ids)

    async def get_asset(self, asset_id):
        return SimpleNamespace(tags=[{"id": str(tag_id)} for tag_id in self.assigned])


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", ["custom:done", ""])
async def test_configured_marker_and_rating_parent_are_recorded_for_undo(
    monkeypatch, marker
):
    async def no_delay(seconds):
        return None

    monkeypatch.setattr("companion.booru_service.asyncio.sleep", no_delay)
    record = SimpleNamespace(added_tag_ids=[])
    database = SimpleNamespace(sessions=FakeSessions(record))
    immich = FakeImmich()
    assets = FakeAssetRepository()
    service = BooruService(database, immich, Settings(), assets)

    async def no_disabled_tags():
        return set()

    service.disabled_tag_ids = no_disabled_tags
    config = BooruSettingsView(
        model_repo=MODELS[0], idle_seconds=300, confidence_threshold=0.35,
        character_threshold=0.9, batch_size=250, processed_tag_name=marker,
        content_rating_tag_name="my-ratings",
    )
    asset = SimpleNamespace(id=uuid4(), tags=[])

    await service._apply(asset, ["general", "sky"], config)

    by_id = {tag.id: tag for tag in immich.catalog}
    assigned_names = {by_id[tag_id].name for tag_id in immich.assigned}
    assert assigned_names == ({"general", "sky", marker} if marker else {"general", "sky"})
    rating_parent = next(tag for tag in immich.catalog if tag.name == "my-ratings")
    rating = next(tag for tag in immich.catalog if tag.name == "general")
    assert rating.parent_id == rating_parent.id
    assert {str(tag_id) for tag_id in immich.assigned} == set(record.added_tag_ids)
    assert len(assets.snapshots) == 1
    snapshot_asset, snapshot_catalog = assets.snapshots[0]
    assert snapshot_asset.tags == [{"id": str(tag_id)} for tag_id in immich.assigned]
    assert {tag.id for tag in snapshot_catalog} == {tag.id for tag in immich.catalog}


def test_booru_tagging_shares_the_asset_sync_lane():
    assert BooruTaskHandler.lane_key == "asset_sync"
