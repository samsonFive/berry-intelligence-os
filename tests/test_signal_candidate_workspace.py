"""Private review presentation retains literal boundaries and individual decisions."""
from copy import deepcopy
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import main


def _forbidden(*args, **kwargs):
    raise AssertionError('Private read or decision must not occur')


@pytest.mark.parametrize('path', ['/signals/review', '/signals/candidates/sample'])
def test_readonly_candidate_pages_fail_before_private_reads(monkeypatch, path):
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    for name in ('present_candidates', 'lookup_candidate', '_evidence_index'):
        monkeypatch.setattr(main, name, _forbidden)
    assert TestClient(main.app).get(path).status_code == 403


@pytest.mark.parametrize('headers', [{'Origin': 'https://other.example'}, {'Sec-Fetch-Site': 'cross-site'}])
def test_cross_origin_candidate_decision_fails_before_read_or_write(monkeypatch, headers):
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'candidate_by_id', _forbidden)
    monkeypatch.setattr(main, 'apply_and_persist_decision', _forbidden)
    page = TestClient(main.app).post('/signals/candidates/sample/decision', data={'decision': 'confirm', 'reviewer': 'Analyst'}, headers=headers)
    assert page.status_code == 403


def test_candidate_read_keeps_limits_notes_source_identity_and_safe_links(monkeypatch):
    candidate = {'id': 'sample', 'status': 'proposed'}
    review = {
        'id': 'sample', 'label': 'A proposed pattern', 'support_label': 'One origin',
        'status_label': 'Proposed', 'confidence_label': 'Low',
        'review_notes': 'Literal [reviewer caveat]',
        'why_it_may_matter': 'Observed wording [with qualifications].',
        'does_not_prove': ['Does not establish commercial success.'],
        'supporting_evidence': [{'id': 'ev-source', 'href': '/intelligence/ev-source', 'title': 'Source title', 'source_url': 'javascript:alert(1)', 'trust_label': 'Approved source'}],
        'independence_view': {'headline': 'One origin', 'clusters': []},
        'relationships': [], 'story_threads': [],
    }
    before = deepcopy((candidate, review))
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'lookup_candidate', lambda *args: (candidate, 'live'))
    monkeypatch.setattr(main, '_evidence_index', lambda: {})
    monkeypatch.setattr(main, 'present_review', lambda *args, **kwargs: review)
    monkeypatch.setattr(main, 'apply_and_persist_decision', _forbidden)
    page = TestClient(main.app).get('/signals/candidates/sample')
    assert page.status_code == 200
    body = unescape(page.text)
    assert 'class="intelligence-workspace"' in body
    assert review['why_it_may_matter'] in body
    assert review['review_notes'] in body
    assert body.index('Does not establish commercial success.') < body.index('value="confirm"')
    assert '<details class="judgment-meta"><summary>Review history and metadata</summary>' in body
    assert 'data-open-reader data-item-id="ev-source"' in body
    assert 'href="javascript:' not in body
    assert 'Confirm candidate' in body
    for decision in ('confirm', 'edit', 'defer', 'dismiss', 'dispute'):
        assert f'name="decision" value="{decision}"' in body
    assert (candidate, review) == before


def test_archived_candidate_retains_audit_without_decision_form(monkeypatch):
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    record = {'status': 'deferred', 'reviewer': 'Analyst', 'review_notes': 'Original [notes]'}
    monkeypatch.setattr(main, 'lookup_candidate', lambda *args: (record, 'audit'))
    monkeypatch.setattr(main, '_evidence_index', _forbidden)
    page = TestClient(main.app).get('/signals/candidates/archived-identity')
    assert page.status_code == 410
    assert 'Original [notes]' in page.text
    assert 'archived-identity' in page.text
    assert '<summary>Record reference</summary>' in page.text
    assert 'name="decision"' not in page.text


def test_queue_prioritizes_populated_groups_and_retains_empty_anchors(monkeypatch):
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, '_evidence_index', lambda: {})
    monkeypatch.setattr(main, 'present_candidates', lambda *args, **kwargs: [])
    item = {'id': 'sample', 'href': '/signals/candidates/sample', 'label': 'Visible pattern', 'confidence_label': 'Low', 'status_label': 'Proposed', 'does_not_prove': ['No market-share conclusion.']}
    triage = {'buckets': [
        {'key': 'review_now', 'label': 'Review now', 'count': 0, 'entries': []},
        {'key': 'same_origin_weak', 'label': 'Same-origin / weak', 'count': 1, 'entries': [item]},
    ], 'counts': {'limited_evidence': 0}, 'limited_evidence': []}
    monkeypatch.setattr(main, 'triage_groups', lambda rows: triage)
    page = TestClient(main.app).get('/signals/review')
    assert page.status_code == 200
    assert page.text.index('Visible pattern') < page.text.index('<details class="candidate-empty-group" id="triage-review_now">')
    assert 'id="triage-limited-evidence"' in page.text
    assert 'No market-share conclusion.' in page.text
