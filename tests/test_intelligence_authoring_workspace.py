"""Named authoring choices retain legacy fields, literal edits and trust boundaries."""
from copy import deepcopy
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.intelligence_authoring import reference_catalog


def _forbidden(*args, **kwargs):
    raise AssertionError('Denied or read-only request must not read or write records')


def test_reference_catalog_uses_metadata_and_preserves_classification_and_records():
    rows = {
        'evidence': [{'id': 'ev-a', 'title': 'Published source', 'source_name': 'Publisher', 'published_date': '2026-10-01', 'article': {'body': 'BODY MUST NOT BE SERIALIZED'}}],
        'facts': [{'id': 'fact-a', 'statement': 'Literal [limit] remains.', 'classification': 'claim'}],
        'signals': [], 'assessments': [],
        'entities': [{'id': 'company-a', 'name': 'Company A', 'entity_type': 'company'}],
        'questions': [{'id': 'sq-a', 'title': 'Original question'}],
    }
    before = deepcopy(rows)
    catalog = reference_catalog(**rows)
    assert catalog['fact_ids'][0] == {'id': 'fact-a', 'label': 'Literal [limit] remains.', 'detail': 'Claim'}
    assert 'BODY MUST NOT BE SERIALIZED' not in str(catalog)
    assert {row['id'] for row in catalog['counterevidence_ids']} == {'ev-a', 'fact-a'}
    assert catalog['evidence_ids'][0]['detail'] == 'Publisher · 2026-10-01'
    assert rows == before


@pytest.mark.parametrize('path', ['/signals/new', '/assessments/new', '/recommendations/new'])
def test_authoring_forms_share_shell_and_original_submission_fields(path):
    page = TestClient(main.app).get(path)
    assert page.status_code == 200
    assert 'class="intelligence-workspace"' in page.text
    assert 'data-reference-field="evidence_ids"' in page.text
    assert 'name="evidence_ids"' in page.text
    assert '<summary>Reference IDs</summary>' in page.text
    assert 'authoring-reference-catalog' in page.text
    assert '/static/intelligence_authoring.js' in page.text


def test_readonly_catalog_returns_before_record_reads(monkeypatch):
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    for name in ('published_evidence', 'all_facts', 'all_signals', 'all_assessments', 'entity_index', 'load_strategic_questions'):
        monkeypatch.setattr(main, name, _forbidden)
    assert main.intelligence_reference_catalog() == {}


@pytest.mark.parametrize('path', ['/signals/new', '/assessments/new', '/recommendations/new'])
def test_readonly_forms_do_not_render_choice_data(monkeypatch, path):
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    monkeypatch.setitem(main.templates.env.globals, 'intelligence_reference_catalog', _forbidden)
    page = TestClient(main.app).get(path)
    assert page.status_code == 200
    assert 'read-only mode' in page.text
    assert 'authoring-reference-catalog' not in page.text
    assert 'class="intake-form"' not in page.text


@pytest.mark.parametrize('path', ['/signals', '/assessments', '/assessments/existing', '/recommendations'])
@pytest.mark.parametrize('headers', [{'Origin': 'https://other.example'}, {'Sec-Fetch-Site': 'cross-site'}])
def test_authoring_posts_deny_cross_site_before_canonical_access(monkeypatch, path, headers):
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    for name in ('published_evidence', 'all_facts', 'all_signals', 'all_assessments', 'assessment_by_id', 'save_signal', 'save_assessment', 'save_recommendation'):
        monkeypatch.setattr(main, name, _forbidden)
    assert TestClient(main.app).post(path, data={'title': 'No write'}, headers=headers).status_code == 403


def test_assessment_edit_retains_unknown_references_and_literal_notes(monkeypatch):
    record = deepcopy(main.all_assessments()[0])
    record['rationale'] = 'Original [analyst qualification] and notes.'
    record['counterevidence_ids'] = ['ev-unavailable', 'fact-original']
    before = deepcopy(record)
    monkeypatch.setattr(main, 'assessment_by_id', lambda record_id: record)
    monkeypatch.setattr(main, 'update_assessment', _forbidden)
    page = TestClient(main.app).get('/assessments/original/edit')
    assert page.status_code == 200
    assert record['rationale'] in unescape(page.text)
    assert 'name="counterevidence_ids" type="text" value="ev-unavailable, fact-original"' in page.text
    assert record == before
