"""Booru policy changes keep marker and rating tags reversible."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from companion.booru_service import MODELS, BooruService, BooruSettingsView, BooruTaskHandler
from companion.config import Settings
from companion.models import BooruAssetFailureRecord, BooruTaggedAssetRecord, BooruTagRunRecord


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


@pytest.mark.asyncio
async def test_manual_retag_removes_only_booru_managed_tags_and_marker(monkeypatch):
    async def no_delay(_seconds):
        return None

    monkeypatch.setattr("companion.booru_service.asyncio.sleep", no_delay)
    booru_id = uuid4()
    marker_id = uuid4()
    prior_id = uuid4()
    user_id = uuid4()
    asset_id = uuid4()
    remaining = {
        booru_id: {"id": str(booru_id), "name": "sky"},
        marker_id: {"id": str(marker_id), "name": "custom:done"},
        prior_id: {"id": str(prior_id), "name": "legacy-model-tag"},
        user_id: {"id": str(user_id), "name": "vacation"},
    }

    class ManualImmich:
        async def remove_assets_from_tag(self, tag_id, asset_ids):
            assert asset_ids == [asset_id]
            remaining.pop(tag_id, None)

        async def get_asset(self, _asset_id):
            return SimpleNamespace(id=asset_id, tags=list(remaining.values()))

    service = BooruService(
        SimpleNamespace(),
        ManualImmich(),
        Settings(),
    )
    service.engine.known_tag_names = lambda: {"sky", "general"}
    config = BooruSettingsView(
        model_repo=MODELS[0],
        idle_seconds=300,
        confidence_threshold=0.35,
        character_threshold=0.9,
        batch_size=250,
        processed_tag_name="custom:done",
        content_rating_tag_name="content-rating",
    )
    asset = SimpleNamespace(id=asset_id, tags=list(remaining.values()))
    prior = SimpleNamespace(added_tag_ids=[str(prior_id)])

    removed, current = await service._remove_manual_booru_tags(asset, prior, config)

    assert removed == {booru_id, marker_id, prior_id}
    assert current.tags == [{"id": str(user_id), "name": "vacation"}]


@pytest.mark.asyncio
async def test_task_handler_forwards_manual_retag_flag():
    calls = []

    class Service:
        engine = SimpleNamespace(unload=lambda: None)

        async def settings(self):
            return SimpleNamespace(unload_model_after_run=False)

        async def tag(self, ids, context, *, manual_retag=False):
            calls.append((ids, manual_retag))
            return SimpleNamespace()

    service = Service()
    handler = BooruTaskHandler(service)
    asset_id = uuid4()

    await handler.execute(SimpleNamespace(), {
        "asset_ids": [str(asset_id)],
        "manual_retag": True,
    })

    assert calls == [([asset_id], True)]


class MappingSession:
    def __init__(self, records):
        self.records = records

    async def get(self, model, key):
        return self.records.get(model)

    def add(self, record):
        return None

    async def delete(self, record):
        for model, value in list(self.records.items()):
            if value is record:
                self.records[model] = None


class MappingSessions:
    def __init__(self, records):
        self.session = MappingSession(records)

    @asynccontextmanager
    async def __call__(self):
        yield self.session

    @asynccontextmanager
    async def begin(self):
        yield self.session


@pytest.mark.asyncio
async def test_processed_marker_removal_retries_asset_despite_prior_record(monkeypatch):
    asset_id = uuid4()
    prior = SimpleNamespace(run_id=uuid4(), added_tag_ids=[])
    records = {
        BooruTagRunRecord: None,
        BooruTaggedAssetRecord: prior,
        BooruAssetFailureRecord: None,
    }
    database = SimpleNamespace(sessions=MappingSessions(records))

    class Immich:
        async def get_asset(self, _asset_id):
            return SimpleNamespace(
                id=asset_id,
                asset_type="IMAGE",
                is_trashed=False,
                tags=[],
            )

        async def get_thumbnail(self, _asset_id, size):
            assert size == "thumbnail"
            return SimpleNamespace(content=b"image")

    service = BooruService(database, Immich(), Settings())
    config = BooruSettingsView(
        model_repo=MODELS[0],
        idle_seconds=300,
        confidence_threshold=0.35,
        character_threshold=0.9,
        batch_size=250,
        processed_tag_name="auto:processed",
        content_rating_tag_name="content-rating",
    )

    async def settings():
        return config

    async def candidates(_limit, _config):
        return [asset_id]

    async def predict(*_args):
        return ["sky"]

    applied = []

    async def apply(asset, predictions, _config):
        applied.append((asset.id, predictions))
        return []

    monkeypatch.setattr(service, "settings", settings)
    monkeypatch.setattr(service, "_candidate_ids", candidates)
    monkeypatch.setattr(service.engine, "predict", predict)
    monkeypatch.setattr(service, "_apply", apply)

    result = await service.tag(None)

    assert result.counters == {"completed": 1, "failed": 0, "skipped": 0}
    assert applied == [(asset_id, ["sky"])]


@pytest.mark.asyncio
async def test_processed_marker_still_blocks_scheduled_retry(monkeypatch):
    asset_id = uuid4()
    prior = SimpleNamespace(run_id=uuid4(), added_tag_ids=[])
    records = {
        BooruTagRunRecord: None,
        BooruTaggedAssetRecord: prior,
        BooruAssetFailureRecord: None,
    }
    database = SimpleNamespace(sessions=MappingSessions(records))

    class Immich:
        async def get_asset(self, _asset_id):
            return SimpleNamespace(
                id=asset_id,
                asset_type="IMAGE",
                is_trashed=False,
                tags=[{"id": str(uuid4()), "name": "auto:processed"}],
            )

        async def get_thumbnail(self, _asset_id, size):
            raise AssertionError("handled asset should not be downloaded")

    service = BooruService(database, Immich(), Settings())
    config = BooruSettingsView(
        model_repo=MODELS[0],
        idle_seconds=300,
        confidence_threshold=0.35,
        character_threshold=0.9,
        batch_size=250,
        processed_tag_name="auto:processed",
        content_rating_tag_name="content-rating",
    )

    async def settings():
        return config

    async def candidates(_limit, _config):
        return [asset_id]

    monkeypatch.setattr(service, "settings", settings)
    monkeypatch.setattr(service, "_candidate_ids", candidates)

    result = await service.tag(None)

    assert result.counters == {"completed": 0, "failed": 0, "skipped": 1}


@pytest.mark.asyncio
async def test_tag_removal_retries_until_immich_reports_membership_gone(monkeypatch):
    async def no_delay(_seconds):
        return None

    monkeypatch.setattr("companion.booru_service.asyncio.sleep", no_delay)
    asset_id = uuid4()
    tag_id = uuid4()
    remove_calls = 0

    class DelayedImmich:
        async def get_asset(self, _asset_id):
            tags = [] if remove_calls >= 2 else [{"id": str(tag_id), "name": "sky"}]
            return SimpleNamespace(id=asset_id, tags=tags)

        async def remove_assets_from_tag(self, _tag_id, asset_ids):
            nonlocal remove_calls
            assert asset_ids == [asset_id]
            remove_calls += 1

    service = BooruService(SimpleNamespace(), DelayedImmich(), Settings())

    removed, current = await service._remove_tag_ids_verified(
        asset_id, {tag_id}, label="Booru"
    )

    assert removed == {tag_id}
    assert current.tags == []
    assert remove_calls == 2
