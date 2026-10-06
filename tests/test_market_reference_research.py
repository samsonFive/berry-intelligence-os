"""Public-scoped requests, evidence-bound proposals and private figure review."""
from copy import deepcopy
from datetime import UTC, datetime
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app import map_market_research_routes as routes
from app.services import market_reference_research as research, market_statistics_reference as reference
from app.services.ai_gateway.perplexity_deep_research import ResearchError
from app.services.global_explorer import IntelligenceQuery, snapshot_model
from app.services.map_statistics_refresh import references
from app.services.market_statistics_reference import group_id

COUNTRY = {'id': 'geography-chile', 'name': 'Chile', 'entity_type': 'geography', 'attributes': {'iso_3166_1_alpha_2': 'CL'}}
URL = 'https://example.org/fictional-national-statistics?original=1&crop=blueberry'
TOKEN = 'market-research-fixture-one'


def source_group(**updates):
    value = {'country_code': 'CL', 'berry': 'Blueberry', 'coverage': 'National', 'crop_scope': 'single_crop',
             'reported_commodity': 'Blueberries (cultivated)', 'year': 2025, 'source': 'Fictional statistics agency',
             'source_url': URL, 'locator': 'Fictional table 2', 'published_date': '', 'source_updated_at': '2026-09-20',
             'date_note': 'The report gives September 2026, not a precise publication day.', 'methodology_url': '',
             'basis': 'Fictional fixture: national harvested production, not exports. [web:1]',
             'metrics': [{'indicator': 'production', 'value': 148.4, 'unit': '1000 t', 'classification': 'Estimated',
                          'passage': 'Fictional fixture: cultivated blueberries, national 2025 harvested production: 148.4 thousand tonnes.',
                          'definition': 'Harvested fruit; estimate retained. [web:1]'}]}
    value.update(updates)
    return value


def result(groups=None, *, status='completed', citations=None):
    return {'provider_id': 'fictional-market-response-1', 'provider_status': status, 'model': 'fixture', 'usage': {},
            'text': json.dumps({'groups': [source_group()] if groups is None else groups, 'limits': ['Yield not reported.']}),
            'citations': [{'url': URL, 'title': 'Fictional statistical report', 'reference_ids': ['web:1']}] if citations is None else citations}


def ready(inbox, *, token=TOKEN, groups=None):
    job, _ = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), token)
    claimed = research.claim(inbox, job['id'])
    research.apply_result(inbox, job['id'], result(groups), claimed['revision'])
    return research.load(inbox), job['id']


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'all_entities', lambda: [deepcopy(COUNTRY)])
    monkeypatch.setattr(research, 'now', lambda: datetime(2026, 10, 4, 18, 0, tzinfo=UTC))
    return main.INBOX_DIR, TestClient(main.app)


def test_get_never_calls_provider_and_scope_carries_from_map(workspace, monkeypatch):
    inbox, client = workspace
    def forbidden():
        raise AssertionError('Browse cannot request provider work')
    monkeypatch.setattr(routes, 'client_factory', forbidden)
    for path in ['/explorer/statistics', '/explorer/statistics/research']:
        page = client.get(path, params={'return_to': '/explorer?countries=geography-chile&berry=berry-blueberry'})
        assert page.status_code == 200
    assert 'value="geography-chile" selected' in page.text
    assert 'value="berry-blueberry" selected' in page.text
    assert not (inbox / research.FILENAME).exists()


def test_explicit_start_posts_public_scope_once_and_does_not_apply(workspace, monkeypatch):
    inbox, client = workspace
    sent = []
    class Provider:
        def start(self, prompt):
            sent.append(prompt)
            return result(status='in_progress')
    monkeypatch.setattr(routes, 'client_factory', Provider)
    data = {'country': COUNTRY['id'], 'berry': 'berry-blueberry', 'token': TOKEN,
            'return_to': '/explorer?countries=geography-chile&berry=berry-blueberry', 'notes': 'PRIVATE_ANALYST_NOTE'}
    first = client.post(routes.BASE, data=data, follow_redirects=False)
    again = client.post(routes.BASE, data=data, follow_redirects=False)
    assert first.status_code == again.status_code == 303 and first.headers['location'] == again.headers['location']
    assert len(sent) == 1 and 'Chile' in sent[0] and 'Blueberry' in sent[0]
    assert 'PRIVATE_ANALYST_NOTE' not in sent[0] and 'geography-chile' not in sent[0] and 'berry-blueberry' not in sent[0]
    state = research.load(inbox)
    assert state['approved'] == [] and state['history'] == []
    assert next(iter(state['jobs'].values()))['status'] == 'running'
    assert client.post(routes.BASE, data=data, headers={'origin': 'https://other.example'}).status_code == 403


def test_one_resolved_country_and_one_berry_required(workspace, monkeypatch):
    inbox, client = workspace
    for country, berry in [('geography-europe', 'berry-blueberry'), (COUNTRY['id'], 'berry-blueberry,berry-strawberry')]:
        response = client.post(routes.BASE, data={'country': country, 'berry': berry, 'token': TOKEN})
        assert response.status_code == 422
    monkeypatch.setattr(main, 'all_entities', lambda: [COUNTRY, {**COUNTRY, 'id': 'duplicate-chile'}])
    assert routes.countries() == {}
    assert not (inbox / research.FILENAME).exists()


def test_parser_keeps_original_units_dates_estimates_and_no_inferred_yield(workspace):
    inbox, _ = workspace
    state, key = ready(inbox)
    group = state['jobs'][key]['groups'][0]
    assert group['source_url'] == URL and group['published_date'] == ''
    assert group['source_updated_at'] == '2026-09-20' and 'September 2026' in group['date_note']
    assert group['period'] == '2025 reporting year'
    assert group['metrics'][0]['value'] == 148.4 and group['metrics'][0]['unit'] == '1000 t'
    assert group['metrics'][0]['classification'] == 'Estimated' and len(group['metrics']) == 1
    assert '[web:1]' not in group['basis'] and '[web:1]' not in group['metrics'][0]['definition']
    assert '[web:1]' in state['jobs'][key]['text']


@pytest.mark.parametrize('updates', [
    {'country_code': 'PE'}, {'berry': 'Blackberry'}, {'coverage': 'Biobío region'}, {'crop_scope': 'mixed_crops'},
    {'reported_commodity': 'Blueberries and blackberries'}, {'reported_commodity': 'Strawberries'}, {'year': 2019}, {'year': True}, {'year': 2027},
    {'source_url': 'https://example.org/uncited'}, {'source_url': 'http://127.0.0.1./private'},
    {'published_date': '2026-09'}, {'locator': ''},
])
def test_unusable_or_out_of_scope_sources_cannot_become_references(workspace, updates):
    inbox, _ = workspace
    state, key = ready(inbox, groups=[source_group(**updates)])
    assert state['jobs'][key]['groups'] == [] and state['jobs'][key]['warnings']
    assert state['approved'] == []


@pytest.mark.parametrize('updates', [
    {'value': True}, {'value': float('nan')}, {'value': float('inf')}, {'value': -1}, {'unit': ''}, {'unit': 'USD'},
    {'indicator': 'exports'}, {'classification': 'Verified'}, {'passage': ''}, {'definition': ''},
])
def test_invalid_figures_and_missing_support_are_rejected(workspace, updates):
    inbox, _ = workspace
    candidate = source_group()
    candidate['metrics'][0].update(updates)
    state, key = ready(inbox, groups=[candidate])
    assert state['jobs'][key]['groups'] == [] and state['approved'] == []


def test_generated_urls_are_not_citations_and_partial_gaps_remain(workspace):
    inbox, _ = workspace
    job, _ = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), TOKEN)
    claimed = research.claim(inbox, job['id'])
    research.apply_result(inbox, job['id'], result(status='incomplete', citations=[]), claimed['revision'])
    saved = research.load(inbox)['jobs'][job['id']]
    assert saved['status'] == 'partial' and saved['groups'] == []
    assert URL in saved['text'] and saved['warnings']


def test_submission_uncertainty_never_starts_a_second_run(workspace):
    inbox, _ = workspace
    job, _ = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), TOKEN)
    calls = []
    class Uncertain:
        def start(self, prompt):
            calls.append(prompt)
            raise ResearchError('The research start could not be confirmed.', uncertain=True)
    research.submit(inbox, job['id'], Uncertain)
    research.submit(inbox, job['id'], Uncertain)
    original = research.load(inbox)['jobs'][job['id']]
    same, created = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), 'different-request-nonce')
    assert original['status'] == 'submission_uncertain' and len(calls) == 1 and not created and same['id'] == job['id']


def test_recovery_and_explicit_progress_with_stale_guards(workspace, monkeypatch):
    inbox, client = workspace
    job, _ = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), TOKEN)
    claimed = research.claim(inbox, job['id'])
    research.failure(inbox, job['id'], ResearchError('Uncertain', uncertain=True), claimed['revision'], submitting=True)
    job = research.load(inbox)['jobs'][job['id']]
    calls = []
    class Provider:
        def check(self, provider_id):
            calls.append(provider_id)
            return result(status='in_progress' if len(calls) == 1 else 'completed')
    monkeypatch.setattr(routes, 'client_factory', Provider)
    path = routes.BASE + '/' + job['id']
    form = {'revision': job['revision'], 'provider_id': 'fictional-market-response-1'}
    assert client.post(path + '/recover', data=form).status_code == 409 and calls == []
    form['confirm_run'] = 'yes'
    assert client.post(path + '/recover', data=form, follow_redirects=False).status_code == 303
    assert client.post(path + '/check', data={'revision': job['revision']}).status_code == 409
    assert calls == ['fictional-market-response-1']
    job = research.load(inbox)['jobs'][job['id']]
    assert client.get(routes.BASE, params={'job': job['id']}).status_code == 200 and len(calls) == 1
    assert client.post(path + '/check', data={'revision': job['revision']}, follow_redirects=False).status_code == 303
    assert research.load(inbox)['jobs'][job['id']]['groups']
    assert len(calls) == 2


def test_deliberate_selection_history_and_private_public_snapshot_boundaries(workspace, monkeypatch):
    inbox, client = workspace
    state, key = ready(inbox)
    proposal = state['jobs'][key]['groups'][0]
    path = routes.BASE + '/' + key + '/apply'
    before = (inbox / research.FILENAME).read_bytes()
    missing_selection = client.post(path, data={'revision': state['revision'], 'return_to': '/explorer?countries=geography-chile&berry=berry-blueberry'})
    assert missing_selection.status_code == 409
    from html import unescape
    import re
    reload_href = unescape(re.search(r'<a href="([^"]+)">Reload research</a>', missing_selection.text)[1])
    assert reload_href.startswith(routes.BASE + '?') and '/apply' not in reload_href
    assert client.get(reload_href).status_code == 200
    assert (inbox / research.FILENAME).read_bytes() == before
    assert client.post(path, data={'revision': state['revision'], 'group': 'not-offered'}).status_code == 409
    selected = {'revision': state['revision'], 'compared_revision': research.reference_revision([], [proposal]),
                'group': group_id(proposal), 'return_to': '/explorer?countries=geography-chile&berry=berry-blueberry'}
    response = client.post(path, data=selected, follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'].endswith('#gx-statistics')
    saved = research.load(inbox)
    assert saved['history'][0]['before'] == [] and saved['history'][0]['after'] == saved['approved']
    assert saved['history'][0]['actor'] and 'Source checked' in saved['approved'][0]['status']
    assert client.post(path, data=selected).status_code == 409
    assert references([], inbox, False) == [] and references([], inbox, True)[0]['source_url'] == URL
    # Only selected figures enter the report projection; raw research/history remains private.
    monkeypatch.setattr(main, 'entity_index', lambda: {COUNTRY['id']: COUNTRY})
    monkeypatch.setattr(main, 'published_evidence', lambda: [])
    monkeypatch.setattr(main, 'all_relationships', lambda: [])
    monkeypatch.setattr(main, 'all_facts', lambda: [])
    monkeypatch.setattr(reference, 'reference_groups', lambda *args: [])
    query = IntelligenceQuery((COUNTRY['id'],), berry_ids=('berry-blueberry',))
    model = snapshot_model(query, [], {COUNTRY['id']: COUNTRY}, [], research.BERRIES, ['statistics'], inbox_dir=inbox, authoring=True)
    mid = model['metric_options'][0]['metrics'][0]['id']
    params = {**query.params(), 'sections': 'statistics', 'metrics': mid}
    page = client.get('/explorer/snapshot', params=params)
    assert page.status_code == 200 and '148.4' in page.text and 'Estimated' in page.text
    from app.services.report_builder import pdf_export
    texts, paragraph = [], pdf_export.Paragraph
    def capture(text, style, **kwargs):
        texts.append(text)
        return paragraph(text, style, **kwargs)
    monkeypatch.setattr(pdf_export, 'Paragraph', capture)
    pdf = client.get('/explorer/snapshot.pdf', params=params)
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    assert '148.4' in ' '.join(texts) and 'Estimated' in ' '.join(texts)
    assert proposal['date_note'] in texts and '2025 reporting year' in ' '.join(texts)
    assert 'market-research-' not in ' '.join(texts) and '[web:1]' not in ' '.join(texts)
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = snapshot_model(query, [], {COUNTRY['id']: COUNTRY}, [], research.BERRIES, ['statistics'], inbox_dir=inbox, authoring=False)
    assert public['metric_options'] == []
    assert client.get(routes.BASE).status_code == 403 and client.post(path, data=selected).status_code == 403


def test_older_research_cannot_replace_newer_source_period(workspace):
    inbox, _ = workspace
    state, key = ready(inbox)
    proposed = state['jobs'][key]['groups'][0]
    newer = {**proposed, 'period': '2026 calendar year'}
    with pytest.raises(ValueError, match='newer period'):
        research.apply(inbox, key, [group_id(proposed)], state['revision'], 'Analyst', [newer])
    assert research.load(inbox)['approved'] == []


def test_history_can_retain_more_than_eight_distinct_sources(workspace):
    inbox, _ = workspace
    for index in range(10):
        state, key = ready(inbox, token=f'explicit-market-request-{index}', groups=[source_group(source=f'Fictional agency {index}')])
        proposal = state['jobs'][key]['groups'][0]
        research.apply(inbox, key, [group_id(proposal)], state['revision'], 'Fixture analyst', research.load(inbox)['approved'])
    assert len(research.load(inbox)['approved']) == 10 and len(research.load(inbox)['history']) == 10


def test_malformed_history_fails_closed_and_generic_errors_do_not_leak(workspace):
    inbox, _ = workspace
    job, _ = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), TOKEN)
    def unavailable():
        raise RuntimeError('SECRET_UNEXPECTED_DETAIL')
    research.submit(inbox, job['id'], unavailable)
    assert 'SECRET_UNEXPECTED_DETAIL' not in json.dumps(research.load(inbox))
    file = inbox / research.FILENAME
    file.write_text('{ damaged', encoding='utf-8')
    with pytest.raises(ValueError, match='Restore'):
        research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), 'new-request-token')
    assert file.read_text() == '{ damaged'


def test_concurrent_resumes_claim_only_one_paid_submission(workspace):
    from concurrent.futures import ThreadPoolExecutor
    inbox, _ = workspace
    job, _ = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), TOKEN)
    calls = []
    class Provider:
        def start(self, prompt):
            calls.append(prompt)
            return result(status='in_progress')
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(research.submit, inbox, job['id'], Provider) for _ in range(8)]
        for future in futures:
            future.result()
    assert len(calls) == 1
    assert research.load(inbox)['jobs'][job['id']]['status'] == 'running'


def test_stop_before_submission_never_calls_provider(workspace, monkeypatch):
    inbox, client = workspace
    monkeypatch.setattr(routes, 'client_factory', lambda: pytest.fail('Unsubmitted stop must not contact a provider'))
    job, _ = research.reserve(inbox, research.scope(COUNTRY, 'berry-blueberry'), TOKEN)
    response = client.post(routes.BASE + '/' + job['id'] + '/cancel', data={'revision': job['revision']}, follow_redirects=False)
    assert response.status_code == 303
    research.submit(inbox, job['id'], routes.client_factory)
    assert research.load(inbox)['jobs'][job['id']]['status'] == 'cancelled'


def test_zero_is_reported_only_when_source_explicitly_supplies_it(workspace):
    inbox, _ = workspace
    item = source_group()
    item['metrics'][0].update(value=0, passage='Fictional source explicitly reports zero harvested production.')
    state, key = ready(inbox, groups=[item])
    group = state['jobs'][key]['groups'][0]
    assert group['metrics'][0]['value'] == 0 and len(group['metrics']) == 1


def test_changed_baseline_requires_new_comparison_without_overwriting_edits(workspace, monkeypatch):
    inbox, client = workspace
    state, key = ready(inbox)
    proposal = state['jobs'][key]['groups'][0]
    old_token = research.reference_revision([], [proposal])
    operator_reference = deepcopy(proposal)
    operator_reference['metrics'][0]['value'] = 999
    operator_reference['basis'] = 'Retained operator source note.'
    original = deepcopy(operator_reference)
    monkeypatch.setattr(routes, 'references', lambda *args: [operator_reference])
    form = {'revision': state['revision'], 'compared_revision': old_token, 'group': group_id(proposal)}
    before = (inbox / research.FILENAME).read_bytes()
    refusal = client.post(routes.BASE + '/' + key + '/apply', data=form)
    assert refusal.status_code == 409 and 'Current market figures changed' in refusal.text
    assert (inbox / research.FILENAME).read_bytes() == before
    form['compared_revision'] = research.reference_revision([operator_reference], [proposal])
    assert client.post(routes.BASE + '/' + key + '/apply', data=form, follow_redirects=False).status_code == 303
    assert research.load(inbox)['history'][0]['compared'] == [original]
    assert operator_reference == original


def test_unreadable_agency_overlay_prevents_paid_research(workspace, monkeypatch):
    inbox, client = workspace
    def damaged(*args):
        raise ValueError('Restore the existing reference history.')
    monkeypatch.setattr(routes, 'references', damaged)
    monkeypatch.setattr(routes, 'client_factory', lambda: pytest.fail('Unreadable references must not start paid research'))
    response = client.post(routes.BASE, data={'country': COUNTRY['id'], 'berry': 'berry-blueberry', 'token': TOKEN})
    assert response.status_code == 409
    assert not (inbox / research.FILENAME).exists()
