"""Snapshot news follows the shared News selector, without narrowing other layers."""
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import feed_first, global_explorer, map_regions, map_workspace, news_workspace
from app.services.report_builder import pdf_export
from tests.test_map_workspace import BERRIES, ENTITIES, FACTS, RECORDS, REL, payload

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


def sources():
    base = RECORDS[0]
    return [{**base, 'id': key, **changes} for key, changes in [
        ('ev-news', {'published_date': '2026-09-30'}),
        ('ev-offset', {'published_date': '2026-09-30T22:00:00-03:00'}),
        ('ev-utc', {'published_date': '2026-10-01T00:00:00Z'}),
        ('ev-old', {'published_date': '2026-08-01'}),
        ('ev-other', {'entity_ids': ['company-other'], 'published_date': '2026-09-29'}),
        ('ev-undated', {'published_date': None}),
        ('ev-future', {'published_date': '2026-10-02'}),
        ('ev-auto', {'submitted_by': 'auto', 'review_state': 'pending', 'published_date': '2026-09-30'}),
        ('ev-no-fact', {'published_date': '2026-09-30'}),
        ('ev-filing', {'source_type': 'patent_filing', 'published_date': '2026-09-30'}),
    ]]


def setup():
    records = sources()
    facts = [{'id': 'fact-' + r['id'], 'status': 'active', 'evidence_ids': [r['id']], 'statement': 'A reviewed statement'}
             for r in records if r['id'] != 'ev-no-fact']
    state = feed_first.empty_state()
    state['entity_tiers']['company-grower'] = 'tier1'
    state['entity_favorites']['company-grower'] = True
    state['company_lists']['list-focus'] = {'name': 'Selected competitors', 'company_ids': ['company-grower']}
    return records, facts, state


@pytest.mark.parametrize('filters', [
    {}, {'company': 'company-other'}, {'favorites': '1', 'tier': 'tier1', 'list': 'list-focus'},
    {'window': '7d'}, {'window': '30d'}, {'window': 'ytd'}, {'window': 'today'}, {'window': 'undated'},
    {'window': 'custom', 'start': '2026-09-29', 'end': '2026-09-30', 'tz': 'America/Los_Angeles'},
    {'q': 'not a matching article'},
])
def test_snapshot_matches_all_shared_news_filters_and_actual_timestamp_order(filters):
    records, facts, state = setup()
    before = deepcopy((records, state))
    query = global_explorer.IntelligenceQuery(('geography-peru',), berry_ids=('berry-blueberry',))
    params = {**filters, **query.params(), 'view': 'trusted'}
    news = news_workspace.model(records={r['id']: r for r in records}, entities=ENTITIES, relationships=REL,
                                facts=facts, state=state, params=params, now=NOW)
    model = global_explorer.snapshot_model(query, records, ENTITIES, REL, BERRIES, ['developments'],
                                          facts=facts, state=state, news_params=params, now=NOW)
    assert [r['id'] for r in model['entries']] == news['matching_ids']
    assert [r['id'] for r in model['packet']['recent_developments']] == news['matching_ids']
    assert model['coverage']['counts']['evidence_count'] == news['matching']
    assert {'ev-future', 'ev-auto', 'ev-no-fact', 'ev-filing'}.isdisjoint(news['matching_ids'])
    assert (records, state) == before
    if not filters:
        assert news['matching_ids'][:2] == ['ev-offset', 'ev-utc']
        assert pdf_export._cutoff_date(model['packet']) == '2026-09-30T22:00:00-03:00'


def test_news_dates_do_not_remove_selected_locations_or_annual_figures(tmp_path):
    records, facts, state = setup()
    saved = map_regions.edit(tmp_path, payload=payload(notes='TRIAL ONLY; DATE UNKNOWN'), entities=ENTITIES,
                             relationships=REL, records=RECORDS)
    query = global_explorer.IntelligenceQuery(('geography-peru',), berry_ids=('berry-blueberry',))
    rows = map_workspace.snapshot_regions(query, ENTITIES, REL, RECORDS, state, {'layer': 'varieties'}, inbox_dir=tmp_path, authoring=True)
    model = global_explorer.snapshot_model(query, records, ENTITIES, REL, BERRIES, ['developments', 'locations'],
        facts=facts, state=state, location_options=rows, location_ids=[saved['id']],
        news_params={'window': 'custom', 'start': '2020-01-01', 'end': '2020-01-02'}, now=NOW)
    assert not model['entries'] and model['selected_location_rows'][0]['notes'] == 'TRIAL ONLY; DATE UNKNOWN'
    assert model['selected_location_rows'][0]['observed_on'] == ''
    us = {**ENTITIES, 'geography-united-states': {**ENTITIES['geography-united-states'], 'name': 'United States'}}
    statistics = global_explorer.snapshot_model(global_explorer.IntelligenceQuery(('geography-united-states',)), [], us, REL, BERRIES,
        ['statistics'], facts=[], news_params={'window': '7d'}, now=NOW)
    assert statistics['statistics']['groups'] and not statistics['packet']['news_scope']


def test_pdf_names_the_selected_news_scope_without_reference_ids(monkeypatch):
    records, facts, state = setup()
    model = global_explorer.snapshot_model(global_explorer.IntelligenceQuery(), records, ENTITIES, REL, BERRIES,
        ['developments'], facts=facts, state=state, news_params={'list': 'list-focus', 'favorites': '1', 'tier': 'tier1', 'window': '7d'}, now=NOW)
    rendered = []
    original = pdf_export.Paragraph
    def paragraph(value, style, **kwargs):
        rendered.append(value)
        return original(value, style, **kwargs)
    monkeypatch.setattr(pdf_export, 'Paragraph', paragraph)
    assert pdf_export.render_report_pdf(model['report'], model['packet'], model['coverage']).startswith(b'%PDF')
    text = '\n'.join(rendered)
    assert all(value in text for value in ['Selected competitors', 'Favorite companies', 'Tier 1', 'Past 7 days', 'UTC'])
    assert 'list-focus' not in text and 'ev-offset' not in text and '[ev-' not in text


def test_routes_use_scope_validate_dates_and_never_read_private_marks_when_readonly(tmp_path, monkeypatch):
    records, facts, state = setup()
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'entity_index', lambda: ENTITIES)
    monkeypatch.setattr(main, 'published_evidence', lambda: records)
    monkeypatch.setattr(main, 'all_relationships', lambda: REL)
    monkeypatch.setattr(main, 'all_facts', lambda: facts)
    monkeypatch.setattr(feed_first, 'load_state', lambda *_: state)
    client = TestClient(main.app)
    url = '/explorer/snapshot?sections=developments&company=company-other&window=custom&start=2026-09-29&end=2026-09-29'
    response = client.get(url)
    assert response.status_code == 200 and '/intelligence/ev-other' in response.text
    assert '/intelligence/ev-news' not in response.text and 'Company: Other Grower' in response.text
    for query in ['start=2026-09-30&end=2026-09-29', 'start=invalid', 'end=2026-13-01']:
        assert client.get('/explorer/snapshot?window=custom&' + query).status_code == 422
        assert client.get('/explorer/snapshot.pdf?window=custom&' + query).status_code == 422
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    monkeypatch.setattr(feed_first, 'load_state', lambda *_: pytest.fail('Readonly map/snapshot must not read private marks/lists'))
    assert client.get('/explorer/snapshot?sections=developments').status_code == 200
    assert client.get('/explorer/snapshot?list=list-focus').status_code == 422
