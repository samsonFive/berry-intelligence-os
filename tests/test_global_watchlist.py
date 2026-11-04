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
    corpus['params'] = {'company': 'company-a'}
    corpus['assessments'] = [{'id': 'assessment-ai', 'entity_ids': ['company-a'], 'title': 'Provisional source interpretation',
                               'ai_proposed': True, 'confidence': 'medium', 'status': 'active'}]
    corpus['relationships'] = [{'id': 'rel-parent', 'subject_id': 'company-b', 'predicate': 'owns', 'object_id': 'company-a', 'status': 'active'}]
    model = gw.build(**corpus)
    model['capabilities'] = None
    pdf = render(model)
    assert pdf.startswith(b'%PDF-')
    # ReportLab compression off solely for a deterministic content assertion.
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf))
    text = '\n'.join(page.extract_text() for page in reader.pages)
    assert 'Global Watchlist' in text and 'Africa Blue' in text
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


def test_seeded_landscapes_are_global_durable_and_never_reset_customizations(corpus):
    from app.services import landscape_workspace as views
    inbox = corpus['store'].inbox
    seeded = views.seed_watchlist_views(inbox)
    assert [row['name'] for row in seeded] == [f'Global {berry.title()} Landscape' for berry in views.DEFAULT_WATCHLIST_BERRIES]
    assert all(row['filters']['region'] == row['filters']['group'] == '' for row in seeded)
    path = inbox / views.VIEW_FILE
    original = path.read_bytes()
    views.seed_watchlist_views(inbox)
    assert path.read_bytes() == original
    first = seeded[0]
    changed = views.save_view(inbox, view_id=first['id'], revision=1, name='European blueberry research',
        filters={**first['filters'], 'region': 'Europe'}, kind='overview', surface='watchlist')
    second = seeded[1]
    views.save_view(inbox, view_id=second['id'], revision=1, name=second['name'], filters=second['filters'],
        archive=True, surface='watchlist')
    customized = path.read_bytes()
    views.seed_watchlist_views(inbox)
    assert path.read_bytes() == customized
    assert views.load_views(inbox)['views'][first['id']] == changed
    assert views.load_views(inbox)['views'][second['id']]['archived']
    assert views.watchlist_scope(changed) == {'berry': 'blueberry', 'region': 'Europe'}
    assert views.view_href(changed) == '/global-watchlist?saved_view=' + first['id']
    with pytest.raises(ValueError, match='original Landscape surface'):
        views.save_view(inbox, view_id=first['id'], revision=2, name='Wrong surface', filters={}, kind='overview')


def test_seeded_landscapes_preserve_existing_views_and_reject_unreadable_state(tmp_path):
    from app.services import landscape_workspace as views
    existing = views.save_view(tmp_path, name='Existing research', filters={'berry': 'berry-blueberry'})
    views.seed_watchlist_views(tmp_path)
    assert views.load_views(tmp_path)['views'][existing['id']] == existing
    path = tmp_path / views.VIEW_FILE
    path.write_text('{corrupt', encoding='utf-8')
    with pytest.raises(ValueError):
        views.seed_watchlist_views(tmp_path)
    assert path.read_text(encoding='utf-8') == '{corrupt'


@pytest.fixture
def saved_landscape_client(corpus, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    from app.services import landscape_workspace as views
    import app.global_watchlist_routes as routes
    monkeypatch.setattr(main, 'INBOX_DIR', corpus['store'].inbox)
    monkeypatch.setattr(main, 'DATA_DIR', corpus['data_dir'])
    monkeypatch.setattr(main, 'all_entities', lambda: corpus['entities'])
    monkeypatch.setattr(main, 'published_evidence', lambda: corpus['evidence'])
    for name in ('all_relationships', 'all_signals', 'all_assessments', 'all_facts', 'load_sources'):
        monkeypatch.setattr(main, name, lambda: [])
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setenv('BIOS_REMOTE_INTERACTIVE', 'false')
    monkeypatch.setattr(main.templates, 'context_processors', [])
    monkeypatch.setattr(routes, 'comparison', lambda *args: {'assessments': [], 'rubrics': {}})
    views.seed_watchlist_views(main.INBOX_DIR)
    return TestClient(main.app)


def test_all_four_saved_landscapes_scope_current_companies_news_and_pdf(corpus, saved_landscape_client):
    import io
    from lxml import html
    from pypdf import PdfReader
    from app.services import landscape_workspace as views
    for berry in ('blackberry', 'strawberry', 'raspberry'):
        corpus['entities'].append({'id': 'company-' + berry, 'name': berry.title() + ' Organization',
            'entity_type': 'company', 'berry_ids': ['berry-' + berry]})
        corpus['evidence'].append({'id': 'ev-' + berry, 'title': berry.title() + ' story', 'status': 'published',
            'entity_ids': ['company-' + berry], 'berry_ids': ['berry-' + berry], 'published_date': '2026-11-04'})
    for berry in views.DEFAULT_WATCHLIST_BERRIES:
        key = 'lview-watchlist-global-' + berry
        response = saved_landscape_client.get('/global-watchlist', params={'saved_view': key})
        assert response.status_code == 200
        doc = html.fromstring(response.text)
        assert doc.xpath('//select[@name="berry"]/option[@selected]/@value') == [berry]
        names = doc.xpath('//a[@class="gw-company"]/text()')
        assert names == (['Africa Blue', 'African Farms'] if berry == 'blueberry' else [berry.title() + ' Organization'])
        assert len(doc.xpath('//nav[@aria-label="Saved watchlist landscapes"]/a')) == 4
        pdf = saved_landscape_client.get('/global-watchlist/export.pdf', params={'saved_view': key})
        assert pdf.status_code == 200
        text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
        assert f'Global {berry.title()} Landscape' in text
        for other in ('blackberry', 'strawberry', 'raspberry'):
            if other != berry:
                assert other.title() + ' Organization' not in text
    # Saved scopes use current corpus data rather than frozen membership lists.
    corpus['entities'].append({'id': 'company-new', 'name': 'New Blueberry Organization',
        'entity_type': 'company', 'berry_ids': ['berry-blueberry']})
    response = saved_landscape_client.get('/global-watchlist?saved_view=lview-watchlist-global-blueberry')
    assert 'New Blueberry Organization' in response.text


def test_saved_landscape_edits_conflicts_archives_and_overrides(corpus, saved_landscape_client):
    from app.services import landscape_workspace as views
    inbox = corpus['store'].inbox
    key = 'lview-watchlist-global-blueberry'
    before = (inbox / views.VIEW_FILE).read_bytes()
    response = saved_landscape_client.get('/global-watchlist', params={'saved_view': key, 'region': 'Asia'})
    assert response.status_code == 200 and 'No organizations match' in response.text
    assert (inbox / views.VIEW_FILE).read_bytes() == before
    form = {'action': 'save', 'view_id': key, 'revision': '1', 'name': 'European blueberry research',
            'berry': 'blueberry', 'region': 'Europe'}
    assert saved_landscape_client.post('/global-watchlist/views', data=form, follow_redirects=False).status_code == 303
    row = views.load_views(inbox)['views'][key]
    assert row['filters']['berry'] == 'berry-blueberry' and row['filters']['region'] == 'Europe'
    assert saved_landscape_client.post('/global-watchlist/views', data=form).status_code == 409
    assert saved_landscape_client.post('/global-watchlist/views', headers={'origin': 'https://evil.example'}, data=form).status_code == 403
    archived = {'action': 'archive', 'view_id': key, 'revision': 2}
    assert saved_landscape_client.post('/global-watchlist/views', data=archived).status_code == 200
    views.seed_watchlist_views(inbox)
    assert saved_landscape_client.get('/global-watchlist?saved_view=' + key).status_code == 422
    assert saved_landscape_client.post('/global-watchlist/views', data={'action': 'restore', 'view_id': key, 'revision': 3}).status_code == 200
    copy = saved_landscape_client.post('/global-watchlist/views', data={**form, 'name': 'Separate blueberry scope', 'action': 'copy'}, follow_redirects=False)
    assert copy.status_code == 303
    assert len(views.load_views(inbox)['views']) == 5


def test_saved_watchlist_landscapes_link_to_workspace_with_the_same_scope(corpus, saved_landscape_client):
    from app import main
    from app.services import workspace_landscapes
    key = 'lview-watchlist-global-blueberry'
    choices = workspace_landscapes.choices(main)
    assert next(row for row in choices if row['id'] == key)['href'] == '/global-watchlist?saved_view=' + key
    resolved = workspace_landscapes.resolve(main, None, [key])
    assert [row['id'] for row in resolved[0]['data']['companies']] == ['company-a', 'company-b']
    scope = workspace_landscapes.coverage_scope({}, resolved)
    assert scope['berry'] == 'berry-blueberry' and scope['companies'] == ['company-a', 'company-b']
    assert all(row['status'] == 'published' for row in resolved[0]['data']['sources'])
    assert 'Invented sensory' not in json.dumps(resolved)


def test_route_access_csrf_follow_and_export(corpus, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
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
