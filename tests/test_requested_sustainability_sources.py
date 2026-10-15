"""Requested source coverage survives acquisition and News metadata selection."""
from datetime import UTC, date, datetime
import json
from pathlib import Path

import pytest

from app.services.feed_first_live import _keep_window_hits, hit_to_record
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.specialist_feeds import (
    WEEK_SPECIALIST_FEEDS, requested_sustainability_record, week_specialist_feed_queries,
)
from app.services.today_relevance import filter_today_records
from app.services import news_workspace


FEEDS = [f for f in WEEK_SPECIALIST_FEEDS if f.get('coverage') == 'sustainability']


@pytest.mark.parametrize('feed', FEEDS, ids=lambda f: f['id'])
def test_requested_source_reaches_news_without_inventing_berry_identity(feed):
    hit = DiscoveryHit(title='Companies cut supply chain emissions with sustainable packaging',
        snippet='A new industry report explores carbon disclosure and climate resilience.',
        url=f"https://{feed['host']}/blog/example", source_domain=feed['host'],
        published_date='2026-10-14', query_id=feed['id'], query_text='', geography='global',
        berry=None, topic='specialist_feed', provider='specialist_rss',
        origin_publisher_url=f"https://{feed['host']}/blog/example")
    kept, _ = _keep_window_hits([hit], entities=[], sources=[], today=date(2026, 10, 14))
    assert kept == [hit]
    record = hit_to_record(hit, entities=[], today=date(2026, 10, 14))
    assert record['berry_ids'] == []
    assert record['trust_state'] == 'LIVE'
    assert record['review_state'] == 'UNREVIEWED'
    assert requested_sustainability_record(record)
    assert filter_today_records([record], entities=[])[0] == [record]
    result = news_workspace.model(records={record['id']: record}, entities={}, relationships=[],
        facts=[], state={}, params={}, now=datetime(2026, 10, 14, 12, tzinfo=UTC))
    assert result['counts']['unreviewed'] == 1
    record['source_url'] = record['origin_publisher_url'] = 'https://unrequested.example/article'
    assert not requested_sustainability_record(record)


def test_requested_sources_have_scheduled_discovery_and_live_queries():
    sources = json.loads(Path('data/configuration/sources.json').read_text(encoding='utf-8'))
    by_id = {s['id']: s for s in sources}
    queries = {q.id for q in week_specialist_feed_queries()}
    assert len(FEEDS) == 4
    for feed in FEEDS:
        source = by_id[feed['source_id']]
        assert source['enabled'] and source['update_cadence'] == 'daily'
        assert source['discovery']['adapter'] in {'article_rss', 'sitemap_xml', 'news_search_rss'}
        assert feed['id'] in queries


@pytest.mark.parametrize('feed_id,title', [
    ('feed:watershed-blog', 'The latest climate tech news - watershed.com'),
    ('feed:watershed-blog', 'Watershed Blog - watershed.com'),
    ('feed:packer-sustainability-insights', 'Fresh Produce Industry News - The Packer - The Packer'),
    ('feed:packer-sustainability-insights', 'Sustainability Insights - The Packer'),
])
def test_indexed_section_homepages_do_not_become_reader_stories(feed_id, title):
    feed = next(row for row in FEEDS if row['id'] == feed_id)
    hit = DiscoveryHit(title=title, snippet='Sustainability news and articles.',
        url=f"https://{feed['host']}/", source_domain=feed['host'],
        published_date='2026-10-14', query_id=feed_id, query_text='', geography='global',
        berry=None, topic='specialist_feed', provider='specialist_rss',
        origin_publisher_url=f"https://{feed['host']}/")
    kept, _ = _keep_window_hits([hit], entities=[], sources=[], today=date(2026, 10, 14))
    assert kept == []
    record = hit_to_record(hit, entities=[], today=date(2026, 10, 14))
    assert not requested_sustainability_record(record)
