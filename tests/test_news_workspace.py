"""Core feed ordering/scope, source trust and read-only entry points."""
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import feed_first, news_workspace as news, personal_digest
from app.services.feed_first_live import save_bundle

ENTITIES = {
    'company-grower': {'id': 'company-grower', 'entity_type': 'company', 'name': 'Grower'},
    'company-other': {'id': 'company-other', 'entity_type': 'company', 'name': 'Other'},
    'geography-peru': {'id': 'geography-peru', 'entity_type': 'geography', 'name': 'Peru'},
    'geography-lima': {'id': 'geography-lima', 'entity_type': 'geography', 'name': 'Lima'},
    'geography-chile': {'id': 'geography-chile', 'entity_type': 'geography', 'name': 'Chile'},
}
RELATIONSHIPS = [{'predicate': 'part_of', 'subject_id': 'geography-lima', 'object_id': 'geography-peru', 'status': 'active'}]


def article(key='ev-news', **changes):
    row = dict(id=key, title='Blueberry nursery expansion', summary='The nursery expands its blueberry genetics programme.',
               source_type='trade_press', source_url='https://example.org/' + key, source_name='Berry Journal',
               status='published', published_date='2026-09-30', entity_ids=['company-grower'],
               geography_ids=['geography-lima'], berry_ids=['berry-blueberry'])
    row.update(changes)
    return row


def project(rows, params=None, state=None, facts=None, now=None):
    return news.model(records={row['id']: row for row in rows}, entities=ENTITIES,
                      relationships=RELATIONSHIPS, facts=facts or [], state=state or feed_first.empty_state(),
                      params=params or {}, now=now or datetime(2026, 10, 1, 12, tzinfo=UTC))


def ids(model):
    return [card['id'] for card in model['cards']]


def test_compact_filter_summary_retains_named_scope_and_explicit_timezone():
    state = feed_first.empty_state()
    state['company_lists']['list-watch'] = {'name': 'Breeders to watch', 'company_ids': ['company-grower']}
    state['entity_tiers']['company-grower'] = 'tier1'
    state['entity_favorites']['company-grower'] = True
    before = deepcopy(state)
    params = {'company': 'company-grower', 'list': 'list-watch', 'tier': 'tier1', 'favorites': '1',
              'berry': 'blueberry,strawberry', 'countries': 'geography-peru', 'q': 'nursery',
              'window': 'custom', 'start': '2026-01-01', 'end': '2026-09-30', 'tz': 'America/Los_Angeles'}
    model = project([article()], params, state=state)
    assert model['filter_summary'] == ['2026-01-01 through 2026-09-30 / America/Los_Angeles',
        'Grower', 'Blueberry, Strawberry', 'Peru', 'Breeders to watch', 'Tier 1', 'Favorite companies', 'Search: nursery']
    assert model['filters']['tz'] == params['tz'] and ids(model) == ['ev-news']
    assert state == before


def test_compact_filter_summary_names_uncatalogued_country_and_undated_scope():
    model = project([], {'countries': 'iso:DE', 'window': 'undated'})
    assert model['filter_summary'] == ['Publication date unavailable / UTC', 'Germany']


def test_newest_publication_always_first_not_priority_or_capture():
    rows = [article('ev-old', published_date='2026-08-15', captured_date='2026-10-01'),
            article('ev-new', published_date='2026-09-30', entity_ids=['company-other']),
            article('ev-middle', published_date='2026-09-20')]
    state = feed_first.empty_state(); state['entity_tiers']['company-grower'] = 'tier1'
    assert ids(project(rows, state=state)) == ['ev-new', 'ev-middle', 'ev-old']


def test_trusted_requires_reviewed_source_plus_active_escalation():
    rows = [article('ev-escalated'), article('ev-source-reviewed'), article('live-raw', live=True),
            article('ev-auto', submitted_by='auto'), article('ev-retired')]
    facts = [{'id': 'fact-' + key, 'status': 'active', 'evidence_ids': [key]} for key in ['ev-escalated', 'live-raw', 'ev-auto']]
    facts.append({'id': 'fact-retired', 'status': 'withdrawn', 'evidence_ids': ['ev-retired']})
    model = project(rows, {'view': 'trusted'}, facts=facts)
    assert ids(model) == ['ev-escalated']
    assert model['counts'] == {'trusted': 1, 'unreviewed': 5}
    raw = project(rows, facts=facts)
    assert len(raw['cards']) == 5
    by_id = {card['id']: card for card in raw['cards']}
    assert by_id['ev-source-reviewed']['source_reviewed'] and not by_id['ev-source-reviewed']['trusted']


def test_company_list_tier_multi_berries_and_hierarchy_intersect():
    rows = [article(), article('ev-straw', berry_ids=['berry-strawberry']),
            article('ev-other', entity_ids=['company-other']), article('ev-chile', geography_ids=['geography-chile'])]
    state = feed_first.empty_state()
    state['company_lists']['list-watch'] = {'name': 'Watch', 'company_ids': ['company-grower']}
    state['entity_tiers']['company-grower'] = 'tier1'
    assert set(ids(project(rows, {'berry': 'blueberry,strawberry', 'countries': 'geography-peru',
                                 'list': 'list-watch', 'tier': 'tier1'}, state=state))) == {'ev-news', 'ev-straw'}
    assert ids(project(rows, {'company': 'company-other', 'tier': 'untiered'}, state=state)) == ['ev-other']
    assert ids(project(rows, {'countries': 'iso:AD'})) == []


@pytest.mark.parametrize('window,expected', [('7d', {'ev-today', 'ev-week'}), ('30d', {'ev-today', 'ev-week', 'ev-month'}), ('ytd', {'ev-today', 'ev-week', 'ev-month', 'ev-year'})])
def test_exact_quick_dates_no_out_of_window_fallback(window, expected):
    rows = [article('ev-' + key, published_date=stamp) for key, stamp in
            [('today', '2026-10-01'), ('week', '2026-09-25'), ('month', '2026-09-02'), ('year', '2026-01-01'), ('past', '2025-12-31')]]
    assert set(ids(project(rows, {'window': window}))) == expected
    assert ids(project([rows[-1]], {'window': window})) == []


def test_custom_date_inclusive_future_and_unknown_not_capture_dated():
    rows = [article('ev-start', published_date='2026-09-01'), article('ev-end', published_date='2026-09-30'),
            article('ev-unknown', published_date='', captured_date='2026-09-20'), article('ev-future', published_date='2026-10-02')]
    assert set(ids(project(rows, {'window': 'custom', 'start': '2026-09-01', 'end': '2026-09-30'}))) == {'ev-start', 'ev-end'}
    assert ids(project(rows, {'window': 'undated'})) == ['ev-unknown']
    with pytest.raises(ValueError, match='Start date'):
        project(rows, {'window': 'custom', 'start': '2026-10-01', 'end': '2026-09-30'})


def test_local_date_boundary_and_iso_timestamps():
    rows = [article('ev-local', published_date='2026-09-30T23:30:00-07:00'),
            article('ev-tomorrow', published_date='2026-10-01')]
    assert ids(project(rows, {'window': 'today', 'tz': 'America/Los_Angeles'}, now=datetime(2026, 10, 1, 6, 45, tzinfo=UTC))) == ['ev-local']
    assert ids(project([article('ev-east', published_date='2026-10-01')], {'window': 'today', 'tz': 'Asia/Tokyo'},
                       now=datetime(2026, 9, 30, 22, tzinfo=UTC))) == ['ev-east']


def test_preview_keeps_image_not_body_and_pagination_is_bounded(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Grid must not hydrate captures')
    monkeypatch.setattr('app.services.feed_first_reader.load_captures', forbidden)
    rows = [article(f'ev-{index}', article={'image_url': 'https://example.org/image.jpg', 'paragraphs': [{'text': 'PRIVATE FULL BODY'}]}, transcript='PRIVATE TRANSCRIPT') for index in range(80)]
    model = project(rows, {'page': '2'})
    assert model['pages'] == 3 and len(model['cards']) == 36
    assert model['cards'][0]['image_url'] == 'https://example.org/image.jpg'
    assert 'PRIVATE FULL BODY' not in str(model) and 'PRIVATE TRANSCRIPT' not in str(model)
    assert ids(project(rows, {'page': '2'})) == ids(model)


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr('app.services.feed_first_reader.fetch_source_preview_image', lambda *a, **k: '')
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'all_entities', lambda: list(ENTITIES.values()))
    monkeypatch.setattr(main, 'entity_index', lambda: ENTITIES)
    monkeypatch.setattr(main, 'all_relationships', lambda: RELATIONSHIPS)
    monkeypatch.setattr(main, 'all_facts', lambda: [])
    monkeypatch.setattr(main, 'published_evidence', lambda: [article(published_date='2026-01-01')])
    save_bundle(main.INBOX_DIR, {'today': '2026-09-30', 'records': [article('live-raw', published_date='2026-09-30')]})
    return TestClient(main.app)


def test_default_news_aliases_and_bookmark_scope_are_read_only(workspace, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('GET cannot collect or hydrate all articles')
    monkeypatch.setattr('app.services.feed_first_live.live_feed_bundle', forbidden)
    monkeypatch.setattr('app.services.feed_first_reader.capture_item', forbidden)
    monkeypatch.setattr('app.services.feed_first_reader.load_captures', forbidden)
    before = sorted(str(path) for path in main.INBOX_DIR.rglob('*'))
    for path in ['/today', '/news', '/today?refresh=1&item=live-raw', '/today?crop=blueberry&geography=geography-peru&entity=company-grower']:
        response = workspace.get(path)
        assert response.status_code == 200 and 'data-news-workspace' in response.text
        assert 'id="v2ReaderOffcanvas"' in response.text
    assert before == sorted(str(path) for path in main.INBOX_DIR.rglob('*'))
    assert not feed_first.state_path(main.INBOX_DIR).exists()
    assert 'data-initial-story="live-raw"' in workspace.get('/today?item=live-raw').text


def test_native_multi_scope_and_reader_for_raw_news(workspace):
    response = workspace.get('/today?berry_choice=berry-blueberry&berry_choice=berry-strawberry&countries_choice=geography-peru')
    assert response.status_code == 200 and 'data-item-id="live-raw"' in response.text
    assert 'berry-blueberry%2Cberry-strawberry' in response.text
    assert 'view=unreviewed' in response.text
    assert workspace.get('/api/intelligence/live-raw/reader?personal=1').status_code == 200
    assert workspace.post('/digest/stories/live-raw', json={'action': 'save'}).status_code == 200
    assert 'live-raw' in workspace.get('/digest').text
    assert not workspace.get('/today?view=trusted').text.count('data-item-id="live-raw"')


def test_map_receives_retained_raw_scope_but_snapshot_stays_trusted(workspace):
    from app.services.global_explorer import IntelligenceQuery
    query = IntelligenceQuery(('geography-peru',), berry_ids=('berry-blueberry',), view='unreviewed')
    records = list(personal_digest.source_records(main.published_evidence(), main.INBOX_DIR).values())
    assert {row['id'] for row in query.retrieve(records, RELATIONSHIPS)} == {'live-raw', 'ev-news'}
    assert {row['id'] for row in IntelligenceQuery(('geography-peru',), berry_ids=('berry-blueberry',)).retrieve(records, RELATIONSHIPS)} == {'ev-news'}
    from urllib.parse import urlencode
    scoped = '/today?window=custom&start=2026-09-01&end=2026-09-30&company=company-grower'
    page = workspace.get('/explorer?' + urlencode({'countries': 'geography-peru', 'berry': 'berry-blueberry', 'view': 'unreviewed', 'news_return': scoped}))
    assert page.status_code == 200
    assert 'window=custom' in page.text and 'start=2026-09-01' in page.text
    assert 'name="news_return"' in page.text
    assert 'live-raw' in page.text
    unsafe = workspace.get('/explorer?' + urlencode({'news_return': 'https://elsewhere.invalid/attack'}))
    assert 'elsewhere.invalid' not in unsafe.context['news_href']


def test_unrelated_generic_news_is_screened_before_feed():
    assert ids(project([article('ev-noise', title='Tariff Court Ruling', summary='Import duties are refunded.', entity_ids=[])])) == []


def test_feedback_is_personal_only_not_extraction_or_trust(workspace):
    before = deepcopy(main.published_evidence())
    assert workspace.post('/digest/stories/live-raw', json={'action': 'useful'}).status_code == 200
    state = feed_first.load_state(main.INBOX_DIR)
    assert state['decisions']['live-raw']['reaction'] == 'up'
    assert state['statements'] == {} and before == main.published_evidence()
    assert workspace.get('/today?view=trusted').status_code == 200


def test_refresh_is_explicit_locked_public_only_and_has_health(workspace, monkeypatch):
    calls = []
    def collect(**kwargs):
        calls.append(kwargs)
        return {'records': [article()], 'lane_errors': []}
    monkeypatch.setattr('app.services.feed_first_live.live_feed_bundle', collect)
    assert workspace.get('/api/news/refresh').json()['status'] is None
    assert workspace.post('/api/news/refresh').status_code == 202
    assert len(calls) == 1
    assert all(calls[0][key] is False for key in ('enable_perplexity', 'enable_exa', 'enable_apitube', 'enrich_lead'))
    assert workspace.get('/api/news/refresh').json()['status'] == 'ready'
    assert len(list((main.INBOX_DIR / 'operations/pipelines/news_workspace_refresh/runs').glob('*.json'))) == 1


def test_refresh_cross_site_read_only_and_failure_disclosure(workspace, monkeypatch):
    assert workspace.post('/api/news/refresh', headers={'origin': 'https://elsewhere.invalid'}).status_code == 403
    def failure(**kwargs):
        raise RuntimeError('SECRET PROVIDER DETAILS')
    monkeypatch.setattr('app.services.feed_first_live.live_feed_bundle', failure)
    assert workspace.post('/api/news/refresh').status_code == 202
    status = workspace.get('/api/news/refresh').json()
    assert status['status'] == 'failed' and 'SECRET' not in str(status)
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert workspace.post('/api/news/refresh').status_code == 403
