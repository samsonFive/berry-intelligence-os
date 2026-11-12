"""Source-shaped Chile/Peru archive controls, separate from pilot recall."""
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.services.feed_first_live import hit_to_record
from app.services.industry_pulse import official_listings as listings
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider, week_specialist_feed_queries
from app.services.news_workspace import model
from app.services.today_relevance import apply_today_relevance

FIXTURES = Path(__file__).parent / 'fixtures' / 'official_listings'


def route(suffix):
    return next(row for row in listings.official_listing_feeds() if suffix in row['id'])


def query(feed):
    return next(q for q in week_specialist_feed_queries(include_priority=True) if q.id == feed['id'])


@pytest.mark.parametrize('suffix,fixture,count', [
    ('chile-sag', 'sag-crop', 1), ('senasa-news', 'senasa-news', 1),
    ('senasa-rules', 'senasa-rules', 2),
])
def test_source_shaped_opaque_records_preserve_crop_description_date_and_review(suffix, fixture, count):
    feed = route(suffix)
    calls = []
    def fetch(url):
        calls.append(url)
        return (FIXTURES / (fixture + '.html')).read_bytes()
    hits = SpecialistRssProvider(fetch=fetch).discover(query(feed))
    assert len(hits) == count  # Overlapping pages/filters deduplicate URLs.
    assert len(calls) == (4 if suffix == 'chile-sag' else 2)
    for hit in hits:
        hit = qualify_hit(hit)
        assert hit.qualifying, hit.qualify_reason
        assert apply_today_relevance([hit], entities=[])[0] == [hit]
        record = hit_to_record(hit, entities=[], today=date(2026, 11, 12))
        assert record['berry_ids'] == ['berry-blueberry']
        assert record['source_type'] == 'government_document'
        assert record['review_state'] == 'UNREVIEWED'
        assert record['discovery_provenance']['date_basis'] == 'publisher_listing_day'
        assert record['discovery_provenance']['first_public_visibility'] == 'unknown'
        assert record['discovery_provenance']['listing_url'] in calls
        assert not record['entity_ids']
        assert model(records={record['id']:record}, entities={}, relationships=[], facts=[], state={}, params={})['matching_ids'] == [record['id']]
    if suffix == 'senasa-rules':
        assert {h.published_date for h in hits} == {'2026-11-04', '2026-10-29'}
        assert all('arándano' not in h.title and 'arándano' in h.snippet for h in hits)
        assert '109,200' in hits[0].snippet and '36,400' in hits[1].snippet
    elif suffix == 'chile-sag':
        assert hits[0].published_date == '2026-09-08'
    else:
        assert hits[0].published_date == '2026-08-13'


def test_page_failure_is_not_silently_reported_as_complete_success():
    feed = route('senasa-rules')
    def fetch(url):
        if 'sheet=2' in url:
            raise httpx.ReadTimeout('publisher timeout')
        return (FIXTURES/'senasa-rules.html').read_bytes()
    with pytest.raises(httpx.ReadTimeout):
        SpecialistRssProvider(fetch=fetch).discover(query(feed))


@pytest.mark.parametrize('body', [b'<html>Sign in</html>', b'<html>Access denied</html>'])
def test_challenge_or_changed_layout_is_failure_not_empty(body):
    with pytest.raises(ValueError, match='structure-missing'):
        listings.parse_listing(body, route('senasa-news'))


def test_unknown_listing_date_is_preserved_without_filename_or_modified_inference():
    raw = (FIXTURES/'senasa-rules.html').read_bytes().replace(b'2026-11-04 00:00:00.000', b'unknown')
    rows = listings.parse_listing(raw, route('senasa-rules'))
    assert rows[0]['published_date'] is None
    assert rows[1]['published_date'] == '2026-10-29'


@pytest.mark.parametrize('target', [
    'http://www.gob.pe/institucion/senasa/normas-legales/1-test',
    'https://www.gob.pe.attacker.test/institucion/senasa/normas-legales/1-test',
    'https://user:secret@www.gob.pe/institucion/senasa/normas-legales/1-test',
    'https://www.gob.pe:wrong/institucion/senasa/normas-legales/1-test',
    'https://www.gob.pe/institucion/other/normas-legales/1-test',
    'https://www.gob.pe/institucion/senasa/normas-legales/tipos/1-test',
])
def test_unverified_or_navigation_links_are_not_record_targets(target):
    assert listings._safe_link(target, route('senasa-rules')) is None


def test_native_empty_sag_query_is_empty_but_response_limits_are_explicit():
    feed = route('chile-sag')
    assert listings.parse_listing(b'<html><div class="view-empty">Sin resultados</div></html>', feed) == []
    with pytest.raises(ValueError, match='response-limit'):
        listings.parse_listing(b'x' * 2_000_001, feed)


def test_nonberry_official_record_does_not_gain_relevance_from_its_authority():
    feed = route('senasa-rules')
    raw = (FIXTURES/'senasa-rules.html').read_bytes().replace('arándano'.encode(), b'pitahaya')
    hits = listings.listing_hits(query(feed), fetch=lambda _: raw)
    assert all(not qualify_hit(hit).qualifying for hit in hits)
    assert apply_today_relevance(hits, entities=[])[0] == []
