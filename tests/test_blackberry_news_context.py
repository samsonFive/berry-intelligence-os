"""Real feed regression plus fruit, mixed agtech and read-only cache controls."""
from copy import deepcopy
from datetime import UTC, date, datetime

import pytest

from app.services import feed_first, feed_first_live, news_workspace
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import qualify_hit
from app.services.today_relevance import apply_today_relevance, filter_today_records

OBSERVED = 'BlackBerry’s Phil Kurtz on sovereignty, licensing and the long game - Lexpert'
ENTITIES = {'company-fixture': {'id': 'company-fixture', 'entity_type': 'company',
                              'name': 'Fixture Berry Co', 'aliases': []}}


def hit(title, snippet):
    return DiscoveryHit(title=title, snippet=snippet, url='https://example.test/story',
        source_domain='example.test', published_date='2026-10-28',
        query_id='today:blackberry:global:30d', query_text='blackberry licensing',
        geography='global', berry='blackberry', topic='industry_pulse',
        provider='google_news_rss', qualifying=True)


def record(key, title, summary):
    return dict(id=key, title=title, summary=summary, source_name='Fixture news',
        source_type='trade_press', source_url='https://example.test/'+key,
        status='published', published_date='2026-10-28', berry_ids=['berry-blackberry'],
        entity_ids=[], geography_ids=[], live=True, trust_state='LIVE')


@pytest.mark.parametrize('title,snippet', [
    (OBSERVED, OBSERVED),
    ('blackberry QNX expands software licensing', 'The software company reports an enterprise agreement.'),
    ('BlackBerry Limited expands endpoint security', 'Corporate software licensing for connected mobile devices.'),
    ('BlackBerry patent portfolio licensing update', 'A corporate licensing agreement announced by the company.'),
    ('BlackBerry smartphone licensing agreement', 'Mobile device intellectual property and enterprise customers.'),
    ('BlackBerry earnings and shareholder update', 'Company investors discuss the latest earnings announcement.'),
    ('BlackBerry discusses sovereignty', 'A corporate sovereignty and licensing strategy interview.'),
])
def test_software_company_is_excluded_from_acquisition_today_and_cached_metadata(title, snippet):
    qualified = qualify_hit(hit(title, snippet))
    assert not qualified.qualifying and 'BlackBerry device/company' in qualified.qualify_reason
    # Already-qualified old hits must also be filtered at the Today boundary.
    kept, dropped = apply_today_relevance([hit(title, snippet)], entities=ENTITIES.values())
    assert not kept and dropped == 1
    row = record('live-software', title, snippet)
    before = deepcopy(row)
    kept, dropped = filter_today_records([row], entities=ENTITIES.values())
    assert not kept and dropped == 1 and row == before


@pytest.mark.parametrize('title,snippet', [
    ('BlackBerry cultivar licensing expands for growers', 'Commercial blackberry breeding and nursery production for growers.'),
    ('Blackberry plant patent names a new primocane cultivar', 'The breeder describes fruit and commercial production.'),
    ('New blackberry fruit exports from Peru', 'Commercial growers report export acreage and nursery investment.'),
    ('Berry growers evaluate BlackBerry QNX for orchard equipment', 'The agricultural trial tests connected equipment in commercial blackberry fruit production.'),
    ('A blackberry grower tests cybersecurity for harvest sensors', 'Commercial growers test farm equipment during the fruit harvest.'),
    ('Blueberry breeders adopt enterprise software', 'The nursery breeding program supports commercial fruit production.'),
    ('Fixture Berry Co announces nursery licensing', 'A new commercial fruit production agreement for growers.'),
])
def test_fruit_and_mixed_agricultural_technology_remain_available(title, snippet):
    qualified = qualify_hit(hit(title, snippet), company_names=['Fixture Berry Co'])
    assert qualified.qualifying, qualified.qualify_reason
    kept, dropped = apply_today_relevance([qualified], entities=ENTITIES.values())
    assert kept == [qualified] and dropped == 0
    row = record('live-fruit', title, snippet)
    before = deepcopy(row)
    kept, dropped = filter_today_records([row], entities=ENTITIES.values())
    assert kept == [row] and dropped == 0 and row == before


@pytest.mark.live_today
def test_cached_bundle_filters_without_refetch_or_overwriting_source_cache(tmp_path, monkeypatch):
    software = record('live-software', OBSERVED, OBSERVED)
    fruit = record('live-fruit', 'Blackberry cultivar licensing for growers',
                   'The breeder expands commercial fruit production with nursery partners.')
    path = feed_first_live.save_bundle(tmp_path, dict(today='2026-10-28',
        fetched_at='2026-10-28T12:00:00+00:00', records=[software, fruit], stats=dict(week=2, same_day=2)))
    original = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}

    def forbidden(*args, **kwargs):
        raise AssertionError('A stale-cache read must not collect or fetch an article')

    monkeypatch.setattr(feed_first_live, 'collect_same_day_hits', forbidden)
    bundle = feed_first_live.live_feed_bundle(inbox_dir=tmp_path, entities=list(ENTITIES.values()),
        today=date(2026, 10, 28), now=datetime(2026, 10, 28, 20, tzinfo=UTC), acquire_on_miss=False)
    assert bundle['cache_state'] == 'stale'
    assert [r['id'] for r in bundle['records']] == ['live-fruit']
    assert bundle['stats']['week'] == 1 and bundle['stats']['dropped_today_noise'] == 1
    assert path.exists() and {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == original


def test_news_selection_keeps_images_reader_ids_and_human_state_without_software_noise():
    software = record('live-software', OBSERVED, OBSERVED)
    fruit = record('live-fruit', 'Blackberry cultivar licensing for growers',
                   'The breeder expands commercial fruit production with nursery partners.')
    fruit['article'] = dict(image_url='https://example.test/fruit.jpg', paragraphs=[{'text': 'Retained original source text'}])
    records = {r['id']: r for r in [software, fruit]}
    state = feed_first.empty_state()
    state['decisions']['live-software'] = dict(reaction='up', saved=True, notes='Keep my earlier feedback')
    before = deepcopy((records, state))
    model = news_workspace.model(records=records, entities=ENTITIES, relationships=[], facts=[], state=state,
        params={'berry': 'berry-blackberry'}, now=datetime(2026, 10, 28, 20, tzinfo=UTC))
    assert [c['id'] for c in model['cards']] == ['live-fruit']
    assert model['cards'][0]['image_url'] == 'https://example.test/fruit.jpg'
    assert model['counts']['unreviewed'] == 1
    assert (records, state) == before
