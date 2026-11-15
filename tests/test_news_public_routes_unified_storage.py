"""Offline integration: new publisher routes cross the real storage cutover.

Synthetic RSS and the saved Japanese listing are engineering fixtures, never
independent pilot events. All runtime, migration and backup paths are temporary.
"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import socket

import feedparser
import pytest

from app.services import article_acquisition
from app.services import feed_first_live as live
from app.services import information_migration as migration
from app.services import information_storage as storage
from app.services.industry_pulse import japanese_notices
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.specialist_feeds import (
    SpecialistRssProvider,
    priority_publisher_feeds,
    week_specialist_feed_queries,
)
from app.services.news_workspace import model


TODAY = date(2026, 10, 16)
WSJ = 'feed:priority:wsj-business:rss'
JAPANESE = japanese_notices.FEED['id']
JAPANESE_RAW = (Path(__file__).parent / 'fixtures/official_listings/tochigi-pests.html').read_bytes()
WSJ_RAW = b'''<rss version="2.0"><channel><item>
<title>Strawberry growers face rising labor costs</title>
<description>Strawberry production and farm labor costs are increasing.</description>
<link>https://www.wsj.com/business/strawberry-growers-fixture</link>
<pubDate>Fri, 16 Oct 2026 09:00:00 GMT</pubDate>
</item></channel></rss>'''
ORIGINAL_FIELDS = (
    'id', 'title', 'summary', 'source_name', 'source_type', 'source_url',
    'origin_publisher_url', 'published_date', 'captured_date', 'berry_ids',
    'discovery_provenance', 'acquisition_lane', 'review_state', 'trust_state', 'live',
)


@pytest.fixture(autouse=True)
def forbid_network_and_article_acquisition(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Storage round-trip fixtures must not acquire articles or contact the network')
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(article_acquisition, 'fetch_article', forbidden)


def discover(route, tmp_path):
    query = next(q for q in week_specialist_feed_queries(include_priority=True) if q.id == route)
    feed = next(f for f in priority_publisher_feeds() if f['id'] == route)
    calls = []

    def fetch(url):
        calls.append(url)
        assert url == feed['feed_url']
        return JAPANESE_RAW if route == JAPANESE else (feedparser.parse(WSJ_RAW), WSJ_RAW)

    # Never consult an operator's saved publisher coverage directory.
    provider = SpecialistRssProvider(fetch=fetch, coverage_dir=tmp_path / 'publisher-fixtures')
    hits = provider.discover(query)
    assert calls == [feed['feed_url']]
    assert all(qualify_hit(hit).qualifying for hit in hits)
    return hits


def bundle(records):
    return {'today': TODAY.isoformat(), 'records': deepcopy(records),
            'rotating_records': deepcopy(records), 'fixture_only': True}


def source_fields(row):
    return {key: row[key] for key in ORIGINAL_FIELDS}


def assert_private_unreviewed(row):
    assert row['status'] == 'unreviewed'
    assert row['review_state'] == 'UNREVIEWED'
    assert row['information']['review_status'] == 'unreviewed'
    assert row['information']['confidence'] is None
    assert row['publication_scope'] == 'private'
    assert not row.get('validated') and not row.get('human_reviewed')


@pytest.mark.parametrize('route', [WSJ, JAPANESE])
@pytest.mark.parametrize('legacy_cached', [False, True], ids=['new-after-migration', 'existing-migrated-cache'])
def test_new_routes_keep_originals_through_migrated_cache_and_idempotent_replay(tmp_path, route, legacy_cached):
    data, inbox, backups = tmp_path / 'data', tmp_path / 'inbox', tmp_path / 'backups'
    data.mkdir()
    inbox.mkdir()
    hits = discover(route, tmp_path)
    kept, stats = live._keep_window_hits(hits, entities=[], sources=[], today=TODAY)
    assert len(kept) == 1
    assert stats['dropped_undated'] == (1 if route == JAPANESE else 0)
    records = [live.hit_to_record(hit, entities=[], today=TODAY) for hit in kept]
    original = records[0]
    assert original['title'] == kept[0].title
    assert original['summary'] == kept[0].snippet.strip()
    assert original['berry_ids'] == ['berry-strawberry']
    assert original['published_date'] == TODAY.isoformat()
    assert original['discovery_provenance']['query_id'] == route
    if route == JAPANESE:
        assert original['source_url'] == 'https://www.pref.tochigi.lg.jp/g59/boujo/documents/ichigo202610.pdf'
        assert original['source_name'] == 'Tochigi Prefecture'
        assert original['source_type'] == 'government_document'
        assert 'いちご' in original['title'] and 'いちご' in original['summary']
        assert original['discovery_provenance']['date_basis'] == 'publisher_listing_day'
        assert original['discovery_provenance']['first_public_visibility'] == 'unknown'
    else:
        assert original['source_url'] == 'https://wsj.com/business/strawberry-growers-fixture'
        assert original['title'] == 'Strawberry growers face rising labor costs'
        assert original['summary'] == 'Strawberry production and farm labor costs are increasing.'
        assert original['discovery_provenance']['publisher_route'] == 'direct_rss'
    incoming = bundle(records)
    if legacy_cached:
        assert not storage.enabled(inbox_dir=inbox)
        legacy_path = live.save_bundle(inbox, incoming)
        assert json.loads(legacy_path.read_text(encoding='utf-8'))['records'] == records

    # Exercise the migration implementation, not synthetic activation markers.
    result = migration.apply_migration(data, inbox, backups, quiesced=True)
    assert result['state'] == 'complete'
    assert storage.enabled(data_dir=data, inbox_dir=inbox)
    path = live.save_bundle(inbox, incoming)
    envelope = json.loads(path.read_text(encoding='utf-8'))
    assert envelope['information_storage_version'] == 1
    assert envelope['records_ids'] == envelope['rotating_records_ids'] == [original['id']]
    assert 'records' not in envelope and 'rotating_records' not in envelope

    root = data / 'information' / 'records'
    stored_path = root / (original['id'] + '.json')
    stored = storage.get_record(original['id'], inbox_dir=inbox)
    assert source_fields(stored) == source_fields(original)
    assert_private_unreviewed(stored)
    loaded = live.load_cached_bundle(inbox, today=TODAY)
    for field in ('records', 'rotating_records'):
        assert len(loaded[field]) == 1
        assert source_fields(loaded[field][0]) == source_fields(original)
        assert_private_unreviewed(loaded[field][0])
        assert not loaded[field][0].get('article')
    assert model(records={original['id']: loaded['records'][0]}, entities={}, relationships=[],
                 facts=[], state={}, params={})['matching_ids'] == [original['id']]

    before = stored_path.read_bytes()
    history = {p.relative_to(data / 'information'): p.read_bytes()
               for p in (data / 'information' / 'history').rglob('*.json')}
    # Replay both daily and rotating membership; one physical source remains.
    live.save_bundle(inbox, incoming)
    assert stored_path.read_bytes() == before
    assert list(root.glob('*.json')) == [stored_path]
    assert {p.relative_to(data / 'information'): p.read_bytes()
            for p in (data / 'information' / 'history').rglob('*.json')} == history
    assert live.load_cached_bundle(inbox, today=TODAY) == loaded
    assert not list((inbox / 'evidence').glob('*.json'))
    assert not list((data / 'evidence').glob('*.json'))
    for hit in hits:
        if hit.published_date is None:
            unknown = live.hit_to_record(hit, entities=[], today=TODAY)
            assert storage.get_record(unknown['id'], inbox_dir=inbox) is None


def test_unknown_native_notice_does_not_get_a_publication_day_or_cache_membership(tmp_path):
    data, inbox = tmp_path / 'data', tmp_path / 'inbox'
    data.mkdir()
    inbox.mkdir()
    migration.apply_migration(data, inbox, tmp_path / 'backups', quiesced=True)
    hits = [hit for hit in discover(JAPANESE, tmp_path) if hit.published_date is None]
    assert len(hits) == 1 and hits[0].provider_metadata['date_basis'] == 'unknown'
    kept, stats = live._keep_window_hits(hits, entities=[], sources=[], today=TODAY)
    assert not kept and stats['dropped_undated'] == 1
    path = live.save_bundle(inbox, bundle([]))
    envelope = json.loads(path.read_text(encoding='utf-8'))
    assert envelope['records_ids'] == envelope['rotating_records_ids'] == []
    loaded = live.load_cached_bundle(inbox, today=TODAY)
    assert loaded['records'] == loaded['rotating_records'] == []
    assert list((data / 'information' / 'records').glob('*.json')) == []
    assert hits[0].published_date is None


def test_public_route_expansion_keeps_existing_catalog_and_refresh_budgets():
    routes = [feed['id'] for feed in priority_publisher_feeds()]
    assert len(routes) == len(set(routes)) == 57
    assert {WSJ, JAPANESE} <= set(routes)
    assert live.PRIORITY_PUBLISHER_QUERY_CAP == 12
    assert live.REGIONAL_QUERY_CAP == 6
