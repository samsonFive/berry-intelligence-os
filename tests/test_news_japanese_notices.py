"""Native official-listing controls, independent of prospective pilot scores."""
from datetime import date
from pathlib import Path

import feedparser
import httpx
import pytest

from app.services.feed_first_live import hit_to_record, _keep_window_hits
from app.services.industry_pulse import japanese_notices as notices
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider, week_specialist_feed_queries, priority_publisher_feeds
from app.services.news_workspace import model

RAW = (Path(__file__).parent / 'fixtures/official_listings/tochigi-pests.html').read_bytes()


def query(route):
    return next(q for q in week_specialist_feed_queries(include_priority=True) if q.id == route)


def test_native_official_notices_keep_originals_dates_and_review_through_normal_services():
    calls = []
    def fetch(url):
        calls.append(url)
        return RAW
    hits = SpecialistRssProvider(fetch=fetch).discover(query(notices.FEED['id']))
    assert calls == [notices.FEED['feed_url']]
    assert len(hits) == 2
    assert {h.published_date for h in hits} == {None, '2026-10-16'}
    for hit in hits:
        title, snippet = hit.title, hit.snippet
        assert qualify_hit(hit).qualifying
        # Use the publisher day for the bounded historical control; this is not
        # a current independent cohort or evidence that an old notice is new.
        kept, _ = _keep_window_hits([hit], entities=[], sources=[], today=date(2026, 10, 16))
        if hit.published_date is None:
            assert not kept  # Raw undated lead retained in discovery, not dated News.
            continue
        assert len(kept) == 1
        record = hit_to_record(hit, entities=[], today=date(2026, 10, 16))
        assert record['title'] == title and record['summary'] == snippet
        assert record['berry_ids'] == ['berry-strawberry']
        assert record['review_state'] == 'UNREVIEWED'
        assert record['source_type'] == 'government_document'
        assert record['discovery_provenance']['first_public_visibility'] == 'unknown'
        assert model(records={record['id']: record}, entities={}, relationships=[], facts=[], state={}, params={})['matching_ids'] == [record['id']]


@pytest.mark.parametrize('text', ['10月16日', '令和8(2026)年度10月', '2026年2月30日', '2025年2026年10月16日'])
def test_ambiguous_partial_or_invalid_listing_days_stay_unknown(text):
    assert notices.listing_day(text) is None


def test_full_width_explicit_calendar_date_and_duplicate_preserve_known_listing_day():
    assert notices.listing_day('２０２６年１０月１６日') == '2026-10-16'
    rows = notices.listing_rows(RAW)
    assert rows[0]['published_date'] is None  # Not page update or 2026 filename.
    assert rows[1]['published_date'] == '2026-10-16'


@pytest.mark.parametrize('target', [
    'https://www.pref.tochigi.lg.jp.evil.test/g59/boujo/documents/test.pdf',
    'https://user:password@www.pref.tochigi.lg.jp/g59/boujo/documents/test.pdf',
    'http://www.pref.tochigi.lg.jp/g59/boujo/documents/test.pdf',
    '/g59/boujo/documents/test.pdf?redirect=outside',
    '/g59/boujo/documents/test.pdf#fragment', '/g05/documents/test.pdf',
])
def test_unverified_links_never_become_notice_targets(target):
    extra = ('<li><a href="' + target + '">いちご病害虫情報</a></li>').encode()
    assert len(notices.listing_rows(RAW.replace(b'</ul>', extra+b'</ul>'))) == 2


def test_structure_size_and_transport_failures_do_not_become_successful_empty_checks():
    for raw in [b'<html>Access denied</html>', '<div id="tmp_contents"><h1>病害虫情報</h1></div>'.encode()]:
        with pytest.raises(ValueError, match='structure-missing'):
            notices.listing_rows(raw)
    with pytest.raises(ValueError, match='response-limit'):
        notices.listing_rows(b'x'*2_000_001)
    def failed(_):
        raise httpx.ReadTimeout('publisher timeout')
    with pytest.raises(httpx.ReadTimeout):
        SpecialistRssProvider(fetch=failed).discover(query(notices.FEED['id']))


def test_nonberry_notices_are_valid_empty_and_rice_never_becomes_strawberry():
    raw = '<div id="tmp_contents"><h1>病害虫情報</h1><li><a href="/g59/boujo/documents/rice.pdf">イネカメムシ類</a></li></div>'.encode()
    assert notices.listing_rows(raw) == []


def test_native_powdery_mildew_notice_qualifies_without_inventing_a_date():
    raw = '<div id="tmp_contents"><h1>病害虫情報</h1><li><a href="/g59/boujo/documents/2026news08.pdf">植物防疫ニュースNo.8（イチゴうどんこ病の発生が多く見られています）</a></li></div>'.encode()
    hit = notices.listing_hits(query(notices.FEED['id']), fetch=lambda _:raw)[0]
    assert qualify_hit(hit).qualifying
    assert hit.published_date is None


@pytest.mark.parametrize('crop,berry', [('ブルーベリー','blueberry'), ('いちご','strawberry'), ('ラズベリー','raspberry'), ('ブラックベリー','blackberry')])
def test_explicit_native_crop_pest_notices_retain_their_own_crop(crop, berry):
    raw = ('<div id="tmp_contents"><h1>病害虫情報</h1><li><a href="/g59/boujo/documents/control.pdf">'+crop+'病害虫情報</a>2026年11月14日</li></div>').encode()
    hit = notices.listing_hits(query(notices.FEED['id']), fetch=lambda _:raw)[0]
    kept, _ = _keep_window_hits([hit], entities=[], sources=[], today=date(2026, 11, 14))
    assert len(kept) == 1
    assert hit_to_record(hit, entities=[], today=date(2026, 11, 14))['berry_ids'] == ['berry-'+berry]


def test_wsj_public_rss_uses_normal_metadata_route_without_article_body_access():
    route = 'feed:priority:wsj-business:rss'
    feed = next(r for r in priority_publisher_feeds() if r['id'] == route)
    raw = b'<rss version="2.0"><channel><item><title>Strawberry growers face rising labor costs</title><description>Strawberry production and farm labor costs are increasing.</description><link>https://www.wsj.com/business/strawberry-growers-control</link><pubDate>Sat, 14 Nov 2026 09:00:00 GMT</pubDate></item></channel></rss>'
    calls = []
    def fetch(url):
        calls.append(url)
        return feedparser.parse(raw), raw
    hits = SpecialistRssProvider(fetch=fetch).discover(query(route))
    assert calls == [feed['feed_url']] and len(hits) == 1
    assert hits[0].source_domain == 'wsj.com'
    assert qualify_hit(hits[0]).qualifying
    record = hit_to_record(hits[0], entities=[], today=date(2026, 11, 14))
    assert record['source_url'].startswith('https://wsj.com/business/')
    assert record['review_state'] == 'UNREVIEWED'
    assert not record.get('article_body') and not record.get('validated')
