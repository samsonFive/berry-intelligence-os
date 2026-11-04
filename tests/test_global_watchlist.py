from copy import deepcopy
import json

import pytest

from app.services import global_watchlist as gw
from app.services.living_workspaces import Store, Conflict


@pytest.fixture
def corpus(tmp_path):
    entities = [
        {'id': 'company-a', 'entity_type': 'company', 'name': 'Africa Blue', 'aliases': ['AB Berries'], 'berry_ids': ['berry-blueberry']},
        {'id': 'company-b', 'entity_type': 'company', 'name': 'African Farms', 'berry_ids': ['berry-blueberry']},
        {'id': 'geography-uk', 'entity_type': 'geography', 'name': 'United Kingdom'},
        {'id': 'berry-blueberry', 'entity_type': 'berry', 'name': 'Blueberry'},
        {'id': 'company-example-genetics', 'entity_type': 'company', 'name': 'Fictional seed'},
    ]
    records = [
        {'id': 'ev-old', 'status': 'published', 'entity_ids': ['company-a'], 'berry_ids': ['berry-blueberry'],
         'geography_ids': ['geography-uk'], 'published_date': '2020-01-01', 'captured_at': '2026-11-04',
         'source_url': 'https://publisher.example/old', 'title': 'Old development'},
        {'id': 'ev-reprint', 'status': 'published', 'entity_ids': ['company-a'], 'berry_ids': ['berry-blueberry'],
         'published_date': '2020-01-02', 'source_url': 'https://publisher.example/old', 'title': 'Syndicated copy'},
        {'id': 'ev-demo', 'status': 'published', 'entity_ids': ['company-a'], 'is_demo': True, 'title': 'Invented sensory 99'},
        {'id': 'ev-private', 'status': 'in_review', 'entity_ids': ['company-a'], 'title': 'SECRET draft'},
    ]
    return {'entities': entities, 'evidence': records, 'relationships': [], 'signals': [], 'assessments': [],
            'data_dir': tmp_path / 'data', 'store': Store(tmp_path / 'inbox'), 'watches': [], 'params': {}}


def test_full_corpus_unknown_and_exact_links(corpus):
    model = gw.build(**corpus)
    assert model['corpus_count'] == 2
    assert model['rows'][0]['name'] == 'Africa Blue'
    assert not model['rows'][1]['evidence']  # African is not Africa Blue.
    assert model['rows'][0]['tiers']['blueberry'] == 'Unknown/Unassigned'
    assert len(model['news']) == 1
    assert len(model['news'][0]['sources']) == 2
    assert model['news'][0]['lead']['published_date'] == '2020-01-02'
    assert all(r['id'] != 'ev-demo' for r in model['rows'][0]['evidence'])
    corpus['params'] = {'q': 'AB Berries'}
    assert [r['id'] for r in gw.build(**corpus)['rows']] == ['company-a']


@pytest.mark.parametrize('filters,expected', [
    ({'favorites': '1'}, ['company-a']),
    ({'company_tier': 'tier1'}, ['company-b']),
    ({'company_tier': 'untiered'}, ['company-a']),
    ({'list': 'list-north'}, ['company-b']),
    ({'favorites': '1', 'list': 'list-north'}, []),
])
def test_company_filters_match_directory_and_leave_shared_state_unchanged(corpus, filters, expected):
    from app.services import company_directory
    state = {'entity_favorites': {'company-a': True}, 'entity_tiers': {'company-b': 'tier1'},
             'company_lists': {'list-north': {'name': 'Northern peers', 'company_ids': ['company-b', 'unknown-retained']}},
             'digest_subscriptions': ['private-subscription'], 'personal_accounts': {'private': {'secret': 'PRIVATE'}}}
    original = deepcopy(state)
    corpus.update(tracking_state=state, params=filters)
    model = gw.build(**corpus)
    assert [row['id'] for row in model['rows']] == expected
    canonical = {row['id']: row for row in corpus['entities'] if row['id'] in {'company-a', 'company-b'}}
    directory = company_directory.catalog(canonical, state=state)
    assert [row['id'] for row in model['rows']] == [key for key in canonical if company_directory.matches_marks(
        [key], state, favorites=filters.get('favorites', ''), tier=filters.get('company_tier', ''), list_id=filters.get('list', ''))]
    for row in model['all_rows']:
        assert row['tracking']['tier'] == directory[row['id']]['tier']
        assert row['tracking']['favorite'] == directory[row['id']]['favorite']
        assert row['tier'] == 'Select a berry'  # Imported classification never becomes the shared tier.
    assert state == original
    assert 'PRIVATE' not in repr(model) and 'subscribed' not in repr(model['lists'])


@pytest.mark.parametrize('filters', [{'favorites': 'true'}, {'company_tier': 'Tier 1'}, {'list': 'missing'}, {'list': 'archived'}])
def test_invalid_company_filters_never_broaden_the_cohort(corpus, filters):
    corpus.update(params=filters, tracking_state={'company_lists': {'archived': {'name': 'Old', 'company_ids': [], 'archived': True}}})
    with pytest.raises(ValueError, match='company|Company'):
        gw.build(**corpus)


@pytest.mark.parametrize('selection', [{'company': 'company-a'}, {'compare': 'company-a,company-b'}])
def test_excluded_explicit_selection_does_not_fall_back_to_other_news_or_pdf(corpus, selection):
    import io
    from pypdf import PdfReader
    from app.services.global_watchlist_pdf import render
    state = {'entity_favorites': {'company-b': True}, 'entity_tiers': {'company-a': 'old-custom-tier'}}
    corpus.update(params={**selection, 'favorites': '1'}, tracking_state=state)
    model = gw.build(**corpus)
    assert model['focus_selection']
    assert [r['id'] for r in model['excluded_focus']] == ['company-a']
    assert [r['id'] for r in model['focus']] == (['company-b'] if 'compare' in selection else [])
    assert not model['news'] and not model['notes'] and model['record_count'] == 0
    assert model['all_rows'][0]['tracking']['tier'] == 'old-custom-tier'
    assert 'old-custom-tier' in model['all_rows'][0]['tracking']['tier_choices']
    before = deepcopy(model)
    text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(render(model))).pages)
    assert 'Excluded by company filters: Africa Blue' in text
    assert 'Old development' not in text and 'Syndicated copy' not in text
    assert ('Organizations (1)' if 'compare' in selection else 'Organizations (0)') in text
    assert model == before


def test_shared_company_edits_keep_digest_private_and_monitoring_groups_intact(corpus):
    from app.services import company_directory, feed_first, personal_digest, personal_scope
    inbox = corpus['store'].inbox
    allowed = {'company-a', 'company-b'}
    group = gw.edit_group(corpus['store'], actor='Alice', action='create', name='Retained monitoring group')
    with personal_scope.bind('Alice', 'Alice'):
        list_id = personal_digest.edit_list(inbox, action='create', name='Shared peers', company_ids=['company-a'], allowed_companies=allowed)
        state = feed_first.load_state(inbox)
        state['digest_subscriptions'] = [list_id]
        state['decisions'] = {'private-story': {'saved': True}}
        feed_first.save_state(inbox, state)
        company_directory.mark(inbox, entity_id='company-a', action='favorite', value='1', allowed=allowed)
        company_directory.mark(inbox, entity_id='company-a', action='tier', value='tier3', allowed=allowed)
    with personal_scope.bind('Bob', 'Alice'):
        state = feed_first.load_state(inbox)
        assert not state['digest_subscriptions'] and not state['decisions'].get('private-story', {}).get('saved')
        corpus.update(tracking_state=state, params={'favorites': '1', 'company_tier': 'tier3', 'list': list_id})
        model = gw.build(**corpus)
        assert [r['id'] for r in model['rows']] == ['company-a']
        assert model['lists'][0]['name'] == 'Shared peers'
        company_directory.mark(inbox, entity_id='company-a', action='leave', value=list_id, allowed=allowed)
    with personal_scope.bind('Alice', 'Alice'):
        state = feed_first.load_state(inbox)
        assert state['digest_subscriptions'] == [list_id] and state['decisions']['private-story']['saved']
        assert personal_digest.company_lists(state)[0]['company_ids'] == []
        assert len(state['entity_mark_history']) == 3
    assert gw.groups(corpus['store'])[0] == group


def test_undated_company_pages_do_not_become_one_event_by_capture_date():
    pages = [{'id': 'about', 'title': 'Planasa - About us', 'source_url': 'https://example.test/about',
              'entity_ids': ['company-planasa'], 'captured_date': '2026-11-04'},
             {'id': 'variety', 'title': 'Planasa - Blueberry Blue Manila', 'source_url': 'https://example.test/manila',
              'entity_ids': ['company-planasa'], 'captured_date': '2026-11-04'}]
    assert len(gw.grouped_news(pages)) == 2


def test_alphabet_scope_preserves_filters_and_pdf(corpus):
    corpus['entities'].append({'id': 'company-c', 'entity_type': 'company', 'name': 'Élite Berries'})
    corpus['params'] = {'letter': 'E'}
    model = gw.build(**corpus)
    assert [r['name'] for r in model['rows']] == ['Élite Berries']
    assert model['letters'] == {'A', 'E'}
    assert model['record_count'] == 0
    import io
    from pypdf import PdfReader
    from app.services.global_watchlist_pdf import render
    text = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(render(model))).pages)
    assert 'Africa Blue' not in text and 'Élite Berries' in text
    corpus['params'] = {'letter': 'E', 'q': 'Africa'}
    assert gw.build(**corpus)['rows'] == []
    assert gw.build(**corpus)['letters'] == {'A'}
    corpus['params'] = {'letter': 'AB'}
    with pytest.raises(ValueError, match='letter'):
        gw.build(**corpus)


def test_groups_persist_across_filters_with_conflicts_and_tombstones(corpus):
    store = corpus['store']
    entities = {e['id']: e for e in corpus['entities']}
    group = gw.edit_group(store, actor='Alice', action='create', name='Northern opportunities')
    group = gw.edit_group(store, actor='Alice', action='add', group_id=group['id'], entity_id='company-a', version=1, entities=entities)
    corpus['params'] = {'group': group['id'], 'region': 'Asia', 'berry': 'blueberry'}
    assert gw.build(**corpus)['rows'] == []
    assert gw.groups(Store(store.inbox))[0]['member_ids'] == ['company-a']
    with pytest.raises(Conflict):
        gw.edit_group(store, actor='Bob', action='rename', group_id=group['id'], name='stale change', version=1)
    group = gw.edit_group(store, actor='Bob', action='rename', group_id=group['id'], name='Renamed', version=2)
    group = gw.edit_group(store, actor='Bob', action='remove', group_id=group['id'], entity_id='company-a', version=3, entities=entities)
    gw.edit_group(store, actor='Bob', action='delete', group_id=group['id'], version=4)
    assert not gw.groups(Store(store.inbox))
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM history WHERE id=?', (group['id'],)).fetchone()[0] == 5


def test_correction_survives_reprocessing_and_preserves_source(corpus):
    entities = {e['id']: e for e in corpus['entities']}
    original = deepcopy(corpus['evidence'])
    gw.correct_association(corpus['store'], actor='Alice', record_id='ev-old', field='entity_ids',
        entity_id='company-a', action='exclude', reason='Wrong name association', version=0,
        entities=entities, evidence={r['id']: r for r in corpus['evidence']})
    # Simulate a new ingester rebuilding the original associations.
    corpus['evidence'] = deepcopy(original)
    corpus['store'] = Store(corpus['store'].inbox)
    corpus['params'] = {'company': 'company-a'}
    model = gw.build(**corpus)
    assert [r['id'] for r in model['focus'][0]['evidence']] == ['ev-reprint']
    assert original == corpus['evidence']
    assert model['corrections'][0]['updated_by'] == 'Alice'


def test_tier_import_repeatability_and_conflicts(corpus):
    snapshot = {'source': 'operator spreadsheet', 'snapshot_date': '2026-11-03'}
    matrix = {'rows': [{'canonical_entity_id': 'company-a', 'berry_tier': {'blueberry': 'tier_1'},
                        'regions': ['DOTA'], 'effective_date': '2026-01-01'},
                       {'canonical_entity_id': 'company-missing', 'berry_tier': {'blueberry': 'tier_2'}}]}
    entities = {e['id']: e for e in corpus['entities']}
    a = gw.import_tiers(corpus['store'], snapshot, matrix, entities)
    b = gw.import_tiers(corpus['store'], snapshot, matrix, entities)
    assert a == b and len(a['assignments']) == 1 and len(a['unmatched']) == 1
    assert a['assignments'][0]['effective_date'] == '2026-01-01'
    assert a['review_state'] == 'unreviewed_import'
    corpus['params'] = {'berry': 'blueberry', 'tier': 'Tier 1'}
    assert [r['id'] for r in gw.build(**corpus)['rows']] == ['company-a']
    matrix['rows'].append({'canonical_entity_id': 'company-a', 'berry_tier': {'blueberry': 'tier_2'}, 'regions': ['DOTA'], 'effective_date': '2026-01-01'})
    report = gw.tier_report(snapshot, matrix, entities)
    assert len(report['conflicts']) == 1


def test_observation_is_unreviewed_and_private(corpus):
    note = gw.add_note(corpus['store'], actor='Alice', entity_id='company-a', classification='hypothesis',
        text='Investigate licensing strategy', observed_at='2026-11-03', reference='',
        entities={e['id']: e for e in corpus['entities']})
    assert note['visibility'] == 'workspace' and note['review_state'] == 'unreviewed'
    assert gw.build(**corpus)['notes'][0]['author'] == 'Alice'
    with pytest.raises(ValueError):
        gw.add_note(corpus['store'], actor='Alice', entity_id='company-a', classification='verified_fact',
            text='Cannot self-promote', observed_at='2026-11-03', reference='', entities={'company-a': {}})


def test_distinct_regional_tier_scopes_are_not_conflated(corpus):
    snapshot = {'source': 'scoped source', 'snapshot_date': '2026-11-04', 'tier_definitions': {'Tier 1': 'Source-defined'}}
    matrix = {'rows': [
        {'canonical_entity_id': 'company-a', 'berry_tier': {'blueberry': 'tier_1'}, 'regions': ['DOTA']},
        {'canonical_entity_id': 'company-a', 'berry_tier': {'blueberry': 'tier_2'}, 'regions': ['DEMEA']},
    ]}
    report = gw.import_tiers(corpus['store'], snapshot, matrix, {e['id']: e for e in corpus['entities']})
    assert not report['conflicts'] and len(report['assignments']) == 2
    assert report['tier_definitions']['Tier 1'] == 'Source-defined'
    corpus['params'] = {'berry': 'blueberry', 'company': 'company-a'}
    assert gw.build(**corpus)['focus'][0]['tier'] == 'Unknown/Unassigned'
    corpus['params'] = {'berry': 'blueberry', 'region': 'DOTA', 'tier': 'Tier 1'}
    assert [r['id'] for r in gw.build(**corpus)['rows']] == ['company-a']


def test_shared_private_corpus_respects_corrections_without_public_leakage(corpus):
    from types import SimpleNamespace
    from app.services.request_corpus import RequestCorpus
    from app.services.entity_alias_recall import linked_evidence_for_entity
    from app.services.company_source_scope import links
    store = corpus['store']
    entities = {e['id']: e for e in corpus['entities']}
    records = deepcopy(corpus['evidence'])
    records[0]['title'] = 'Africa Blue expands its blueberry business'
    records[0]['company_ids'] = ['company-a']
    gw.correct_association(store, actor='Alice', record_id='ev-old', field='entity_ids', entity_id='company-a',
        action='exclude', reason='Wrong attribution', version=0, entities=entities,
        evidence={r['id']: r for r in records})
    repos = SimpleNamespace(evidence=SimpleNamespace(list=lambda: records))
    private = RequestCorpus(corpus['data_dir'], corpus['data_dir'] / 'schemas', store.inbox,
                            include_workspace_corrections=True, _repos=repos)
    corrected = private.evidence[0]
    assert corrected['entity_ids'] == []
    assert not linked_evidence_for_entity(entities['company-a'], [corrected], entities=entities)
    assert 'company-a' not in links(corrected, [entities['company-a']])[0]
    public = RequestCorpus(corpus['data_dir'], corpus['data_dir'] / 'schemas', store.inbox, _repos=repos)
    assert public.evidence[0]['entity_ids'] == ['company-a']
    assert 'association_corrections' not in public.evidence[0]


def test_pdf_matches_scoped_projection_and_excludes_demo(corpus):
    from app.services.global_watchlist_pdf import render
    corpus['entities'][0]['roles'] = ['breeder_developer', 'rights_holder']
    corpus['evidence'][0]['source_type'] = 'company_website'
    gw.add_note(corpus['store'], actor='Alice', entity_id='company-a', classification='sourced_claim',
                text='Keep my literal do_not_rewrite wording.', observed_at='2026-11-04',
                reference='https://publisher.example/original', entities={r['id']: r for r in corpus['entities']})
    corpus['params'] = {'company': 'company-a'}
    corpus['assessments'] = [{'id': 'assessment-ai', 'entity_ids': ['company-a'], 'title': 'Provisional source interpretation',
                               'ai_proposed': True, 'confidence': 'medium', 'status': 'active'}]
    corpus['relationships'] = [{'id': 'rel-parent', 'subject_id': 'company-b', 'predicate': 'owns', 'object_id': 'company-a', 'status': 'active'}]
    model = gw.build(**corpus)
    model['capabilities'] = None
    before = deepcopy(model)
    pdf = render(model)
    assert model == before
    assert pdf.startswith(b'%PDF-')
    # ReportLab compression off solely for a deterministic content assertion.
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf))
    text = '\n'.join(page.extract_text() for page in reader.pages)
    assert 'Global Watchlist' in text and 'Africa Blue' in text
    assert 'Company: Africa Blue' in text
    assert 'Breeder developer' in text and 'Rights holder' in text and 'Company website' in text
    assert 'Sourced claim / Unreviewed' in text and 'do_not_rewrite' in text
    assert 'breeder_developer' not in text and 'company_website' not in text
    assert '2020-01-01' in text and '2026-11-04' in text
    assert 'Invented sensory' not in text and 'SECRET draft' not in text
    assert 'Internal / Confidential' in text
    assert 'AI PROPOSED' in text
    assert 'African Farms | owns | Africa Blue' in text


def test_pdf_people_keep_their_source_references_on_the_same_page(corpus):
    import io
    from pypdf import PdfReader
    from app.services.global_watchlist_pdf import render
    corpus['params'] = {'company': 'company-a'}
    model = gw.build(**corpus)
    model['people'] = [{
        'company': 'Africa Blue', 'name': f'Person Record {i:02d}', 'type': 'Person observation',
        'role': 'Research director', 'status': 'Source-reported role; current continuity unverified',
        'location': 'United Kingdom', 'date_basis': 'Last observed', 'date': '2026-11-04',
        'scope': 'Blueberry breeding', 'detail': 'Public research presentation and source-attributed role. ' * 4,
        'resolution': 'accepted_structure', 'source_state': 'unverified',
        'sources': [{'id': f'source-{i}', 'fields': {'original_url': f'https://publisher.example/people/record-{i:02d}'}}]
    } for i in range(20)]
    pages = [page.extract_text() for page in PdfReader(io.BytesIO(render(model))).pages]
    for i in range(20):
        assert any(f'Person Record {i:02d}' in page and f'https://publisher.example/people/record-{i:02d}' in page for page in pages)


def test_route_access_csrf_follow_and_export(corpus, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    corpus['entities'][0]['roles'] = ['breeder_developer', 'rights_holder']
    corpus['evidence'][0]['source_type'] = 'company_website'
    monkeypatch.setattr(main, 'INBOX_DIR', corpus['store'].inbox)
    monkeypatch.setattr(main, 'DATA_DIR', corpus['data_dir'])
    monkeypatch.setattr(main, 'all_entities', lambda: corpus['entities'])
    monkeypatch.setattr(main, 'published_evidence', lambda: corpus['evidence'])
    for name in ('all_relationships','all_signals','all_assessments','all_facts'):
        monkeypatch.setattr(main, name, lambda: [])
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    import app.global_watchlist_routes as routes
    monkeypatch.setattr(routes, 'comparison', lambda *args: {'assessments': [], 'rubrics': {}})
    # Stub shell context only; do not load the real runtime corpus for badges.
    monkeypatch.setattr(main.templates, 'context_processors', [])
    client = TestClient(main.app)
    response = client.get('/global-watchlist')
    assert response.status_code == 200
    assert 'Africa Blue' in response.text
    assert 'Breeder developer' in response.text and 'Rights holder' in response.text
    assert 'value="company_website"' in response.text and '>Company website</option>' in response.text
    assert corpus['entities'][0]['roles'] == ['breeder_developer', 'rights_holder']
    assert corpus['evidence'][0]['source_type'] == 'company_website'
    profile = client.get('/global-watchlist?company=company-a')
    assert '<strong class="gw-monitoring-status">No monitoring source</strong>' in profile.text
    assert 'linked_competitor_ids' not in profile.text
    assert 'Shared company tracking'.upper() in profile.text
    assert 'aria-label="Favorite Africa Blue"' in profile.text
    assert 'name="company_tier"' in response.text and 'name="list"' in response.text
    from app.services import feed_first, personal_digest
    from app.company_routes import safe_return
    monkeypatch.setattr(main, 'living_catalog', lambda: corpus['entities'])
    target = '/global-watchlist?company=company-a&favorites=1#gw-results'
    assert safe_return(target, 'company-a') == target
    for unsafe in ('https://evil.example/global-watchlist', '//evil.example/global-watchlist', '/global-watchlist/other'):
        assert safe_return(unsafe, 'company-a') == '/entities/company'
    mark = {'action': 'favorite', 'value': '1', 'return_to': target}
    assert client.post('/companies/company-a/marks', headers={'origin': 'https://evil.example'}, data=mark).status_code == 403
    saved = client.post('/companies/company-a/marks', data=mark, follow_redirects=False)
    assert saved.status_code == 303 and saved.headers['location'] == target
    assert feed_first.load_state(main.INBOX_DIR)['entity_favorites']['company-a']
    scoped = client.get('/global-watchlist?favorites=1')
    assert '★ Favorite' in scoped.text
    company_list = personal_digest.edit_list(main.INBOX_DIR, action='create', name='Named peers', company_ids=['company-b'], allowed_companies={'company-a', 'company-b'})
    excluded = client.get('/global-watchlist', params={'company': 'company-a', 'list': company_list})
    assert excluded.status_code == 200 and 'Clear company filters to restore the selection' in excluded.text
    assert 'data-open-reader href="/intelligence/ev-reprint?personal=1"' not in excluded.text
    assert 'company=company-a' in excluded.text and 'Named peers' in excluded.text
    assert client.get('/global-watchlist?list=nonexistent').status_code == 422
    assert 'class="digest-card news-card"' in response.text
    assert 'data-open-reader href="/intelligence/ev-reprint?personal=1"' in response.text
    assert '2 retained sources' in response.text
    assert 'Captured 2026-11-04' in response.text
    assert 'Organization alphabetical navigation' in response.text
    assert 'site_sheet.js' in response.text
    state = {'revision': 0, 'widths': {'name': 220}, 'order': ['name'], 'hidden': [], 'filters': {'wrap': '1'}}
    assert client.post('/api/ui/sheets/sheet-test', json=state).status_code == 200
    assert client.get('/api/ui/sheets/sheet-test').json()['widths'] == {'name': 220}
    assert client.get('/api/ui/sheets/sheet-test').headers['cache-control'] == 'private, no-store'
    assert client.post('/api/ui/sheets/sheet-test', json=state).status_code == 409
    assert client.post('/api/ui/sheets/sheet-test', headers={'origin': 'https://evil.example'}, json=state).status_code == 403
    response = client.post('/global-watchlist/actions', data={'action': 'follow','entity_id': 'company-a'}, follow_redirects=False)
    assert response.status_code == 303
    from app.services.watchlist import load_watches
    assert load_watches(corpus['store'].inbox)[0]['object_id'] == 'company-a'
    assert client.get('/global-watchlist/export.pdf').headers['content-type'] == 'application/pdf'
    assert client.post('/global-watchlist/actions', headers={'origin': 'https://evil.example'}, data={'action': 'create', 'name': 'Bad'}).status_code == 403
    assert client.get('/competitors?berry=blueberry', follow_redirects=False).headers['location'] == '/global-watchlist?berry=blueberry'
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/global-watchlist').status_code == 403
    assert client.get('/global-watchlist/export.pdf').status_code == 403
    assert client.post('/global-watchlist/actions', data={'action': 'create','name': 'Bad'}).status_code == 403
