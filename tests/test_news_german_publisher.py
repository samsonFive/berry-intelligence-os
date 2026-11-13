"""Offline publisher-metadata controls; no prospective pilot credit."""
from datetime import date, datetime, UTC

import httpx
import pytest

from app.services.industry_pulse import german_publisher as publisher
from app.services.industry_pulse.specialist_feeds import SpecialistRssProvider, week_specialist_feed_queries
from app.services.industry_pulse.qualify import qualify_hit
from app.services.today_relevance import apply_today_relevance
from app.services.feed_first_live import hit_to_record
from app.services.news_workspace import model

TITLE = 'Brombeeren: Portugal baut seine Exportposition weiter aus'
PATH = '/news/brombeeren-portugal-baut-seine-exportposition-weiter-aus'
# Reduced source-shaped markup from the frozen November 12 public snapshot.
LISTING = f'<a href="{PATH}">{TITLE}</a><a href="/nachrichten/produkt/brombeeren">Brombeeren</a>'
ARTICLE = f'<article class="news-banner-pool node node--type-news"><h1>{TITLE}</h1><time datetime="2026-11-12T13:07:13+01:00">12. November 2026</time></article><aside><time datetime="2026-11-13T10:00:00+01:00">Tomorrow</time></aside>'


def query():
    return next(q for q in week_specialist_feed_queries(include_priority=True) if q.id == publisher.FEED['id'])


def test_bounded_native_listing_reaches_unreviewed_news_with_article_date():
    calls = []
    def fetch(url):
        calls.append(url)
        return LISTING.encode() if url == publisher.FEED['feed_url'] else ARTICLE.encode()
    hits = SpecialistRssProvider(fetch=fetch).discover(query())
    assert len(hits) == 1 and len(calls) == 2
    hit = qualify_hit(hits[0])
    assert hit.qualifying
    assert apply_today_relevance([hit], entities=[])[0] == [hit]
    record = hit_to_record(hit, entities=[], today=date(2026, 11, 12))
    assert record['review_state'] == 'UNREVIEWED' and record['berry_ids'] == ['berry-blackberry']
    assert record['discovery_provenance']['first_public_visibility'] == 'unknown'
    assert record['published_date'] == '2026-11-12'
    assert record['discovery_provenance']['publisher_publication_time'] == '2026-11-12T13:07:13+01:00'
    projected = model(records={record['id']: record}, entities={}, relationships=[], facts=[], state={}, params={},
                      now=datetime(2026, 11, 12, 23, tzinfo=UTC))
    assert projected['matching_ids'] == [record['id']]


def test_article_time_never_comes_from_sidebar_mismatched_heading_or_naive_time():
    assert publisher.publication_time(ARTICLE.encode(), TITLE) == '2026-11-12T13:07:13+01:00'
    assert publisher.publication_time(ARTICLE.encode(), 'Other blackberry article') is None
    assert publisher.publication_time(ARTICLE.replace('<article', '<div').replace('</article>', '</div>').encode(), TITLE) is None
    assert publisher.publication_time(ARTICLE.replace('2026-11-12T13:07:13+01:00', '2026-11-12T13:07:13').encode(), TITLE) is None


def test_fixed_request_budget_and_no_navigation_or_off_host_targets():
    raw = ''.join(f'<a href="/news/blackberry-{i}">Brombeeren Exportposition {i}</a>' for i in range(20))
    raw += '<a href="https://evil.example/news/blackberry-leak">Brombeeren Exportposition</a>'
    raw += '<a href="https://user@www.fruchthandel.de/news/blackberry-leak">Brombeeren Exportposition</a>'
    assert len(publisher.listing_rows(raw.encode())) == 4
    calls = []
    def fetch(url):
        calls.append(url)
        return raw.encode() if len(calls) == 1 else b'<article><h1>Unrelated</h1></article>'
    hits = publisher.listing_hits(query(), fetch=fetch)
    assert len(calls) == 5 and all(hit.published_date is None for hit in hits)


def test_failed_metadata_and_changed_layout_are_failed_not_empty_success():
    with pytest.raises(ValueError, match='structure-missing'):
        publisher.listing_rows(b'<html>Access denied</html>')
    def fetch(url):
        if url == publisher.FEED['feed_url']:
            return LISTING.encode()
        raise httpx.ReadTimeout('metadata timed out')
    with pytest.raises(httpx.ReadTimeout):
        publisher.listing_hits(query(), fetch=fetch)
    assert publisher.listing_rows(b'<a href="/news/tomatoes">Tomato prices</a>') == []
