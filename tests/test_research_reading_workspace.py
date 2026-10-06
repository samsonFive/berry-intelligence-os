"""Research reads retain public/private and explicit provider boundaries."""
from copy import deepcopy
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import main


def _scope():
    return main.ResearchScope.from_dict({"question": "Compare Planasa and Fall Creek", "company_ids": ["company-planasa"]})


def _forbidden(*args, **kwargs):
    raise AssertionError("This read must not access a provider or private cache")


def test_saved_research_has_shared_shell_and_never_runs_web_search(monkeypatch):
    monkeypatch.setattr(main, "_pulse_providers", _forbidden)
    monkeypatch.setattr(main, "run_live_research", _forbidden)
    monkeypatch.setattr(main, "maybe_untrusted_completer", _forbidden)
    client = TestClient(main.app)
    assert client.get('/research?q=Planasa').status_code == 200
    page = client.post('/research', data={'question': 'Compare Planasa and Fall Creek'})
    assert page.status_code == 200
    assert 'class="intelligence-workspace"' in page.text
    assert 'Saved intelligence ready' in page.text
    assert 'id="rd-run-live"' in page.text
    assert '/static/research_workspace.js' in page.text
    assert 'data-open-reader' in page.text
    assert 'Checking live sources' not in page.text


def test_readonly_research_skips_private_caches_and_hides_live_and_report_actions(monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    for name in ('compose_moves_board', '_radar_developments_for_scope', '_research_competitive_moves', '_research_move_patterns'):
        monkeypatch.setattr(main, name, _forbidden)
    page = TestClient(main.app).post('/research', data={'question': 'Compare Planasa and Fall Creek'})
    assert page.status_code == 200
    assert 'Saved intelligence ready' in page.text
    assert 'id="rd-run-live"' not in page.text
    assert 'class="rd-create-brief"' not in page.text
    assert 'data-open-reader' not in page.text


@pytest.mark.parametrize('mode,headers', [
    (False, {}), (True, {'Origin': 'https://different.example.com'}),
    (True, {'Sec-Fetch-Site': 'cross-site'}),
])
def test_live_research_refuses_before_provider_or_private_reads(monkeypatch, mode, headers):
    monkeypatch.setattr(main, "AUTHORING_MODE", mode)
    monkeypatch.setattr(main, "_research_packet", _forbidden)
    monkeypatch.setattr(main, "_pulse_providers", _forbidden)
    page = TestClient(main.app).post('/api/research/live', json={'scope': _scope().as_dict()}, headers=headers)
    assert page.status_code == 403


@pytest.mark.parametrize('telemetry,status', [
    ({}, 'unavailable'),
    ({'cached': {'queries': 0, 'errors': 0}}, 'unavailable'),
    ({'one': {'queries': 1, 'errors': 0}}, 'complete'),
    ({'one': {'queries': 1, 'errors': 1}}, 'failed'),
    ({'one': {'queries': 1, 'errors': 1}, 'two': {'queries': 1, 'errors': 0}}, 'partial'),
])
def test_live_capture_outcome_is_honest_without_replacing_review_status(monkeypatch, telemetry, status):
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "_pulse_providers", lambda: [])
    monkeypatch.setattr(main, "maybe_untrusted_completer", lambda: None)
    monkeypatch.setattr(main, "run_live_research", lambda *args, **kwargs: {'items': [], 'telemetry': telemetry, 'failures': [], 'latency_seconds': 0})
    page = TestClient(main.app).post('/api/research/live', json={'scope': _scope().as_dict()}, headers={'Origin': 'http://testserver'})
    assert page.status_code == 200
    assert f'data-live-status="{status}"' in page.text
    assert 'LIVE / UNREVIEWED' in page.text
    if status != 'complete':
        assert 'Source check complete' not in page.text


def test_numbered_citations_keep_exact_text_and_ids_but_disable_unsafe_links(monkeypatch):
    packet = {'evidence': [], 'companies': [], 'varieties': [], 'rights_ip': [], 'signals': [], 'requested_layers': []}
    answer = {
        'findings': [{'kind': 'FACT', 'text': 'Literal [qualification] retained.', 'source_ids': ['ev-private-display-slug']}],
        'sources': [{'id': 'ev-private-display-slug', 'title': 'Original source', 'trust_class': 'APPROVED SOURCE', 'url': 'javascript:alert(1)', 'date': None, 'source_name': 'Publisher'}],
        'current_developments': [], 'weak_signals': [], 'gaps': [], 'competitive_context': {'relationships': []},
        'rights_ip': [], 'market_context': [], 'radar_developments': [], 'implications': [],
    }
    before = deepcopy((packet, answer))
    monkeypatch.setattr(main, '_research_packet', lambda scope: (packet, None, None))
    monkeypatch.setattr(main, 'compose_research_answer', lambda packet: answer)
    page = TestClient(main.app).post('/research', data={'question': 'Planasa'})
    assert page.status_code == 200
    assert 'Literal [qualification] retained.' in unescape(page.text)
    assert 'href="#rd-source-ev-private-display-slug"' in page.text
    assert '>Source 1</a>' in page.text
    assert 'id="rd-source-ev-private-display-slug"' in page.text
    assert 'href="javascript:' not in page.text
    assert 'Original source · link unavailable' in page.text
    assert (packet, answer) == before


def test_empty_live_question_fails_before_packet_or_provider(monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "_research_packet", _forbidden)
    monkeypatch.setattr(main, "_pulse_providers", _forbidden)
    page = TestClient(main.app).post('/api/research/live', json={'scope': {'question': '   '}})
    assert page.status_code == 422


@pytest.mark.parametrize('classification,kind', [('fact', 'FACT'), ('claim', 'CLAIM'), (None, 'UNCLASSIFIED STATEMENT')])
def test_research_does_not_relabel_claims_or_missing_classification_as_facts(classification, kind):
    from app.services.research_desk import assemble_research_packet, compose_research_answer

    source = {'id': 'ev-test', 'title': 'Publisher claim', 'entity_ids': ['company-planasa']}
    proposition = {'id': 'fact-test', 'statement': 'Publisher reports a result [with limits].', 'classification': classification, 'entity_ids': ['company-planasa'], 'evidence_ids': ['ev-test']}
    before = deepcopy((source, proposition))
    packet = assemble_research_packet(_scope(), entities={'company-planasa': {'id': 'company-planasa', 'entity_type': 'company', 'name': 'Planasa'}}, relationships=[], published_evidence=[source], facts=[proposition], signals=[], assessments=[])
    answer = compose_research_answer(packet)
    finding = next(row for row in answer['findings'] if row['text'] == proposition['statement'])
    assert finding['kind'] == kind
    assert finding['source_ids'] == ['ev-test']
    assert packet['facts'][0]['classification'] == (classification or '')
    assert (source, proposition) == before


def test_report_handoff_minimizes_supporting_notes_without_rewriting_payload(monkeypatch):
    monkeypatch.setattr(main, 'maybe_untrusted_completer', _forbidden)
    notes = 'Question [with limits]\nAnalyst rationale stays literal.\nSelected Research Desk source IDs: ev-original-reference\n'
    page = TestClient(main.app).post('/reports/new', data={
        'step': 'preview', 'report_type': 'competitor_comparison',
        'company_ids': 'company-planasa,company-fall-creek-farm-and-nursery',
        'date_window_days': '90', 'focus_notes': notes,
    })
    assert page.status_code == 200
    assert '<h2 class="report-question">Question [with limits]</h2>' in page.text
    assert '<details class="report-preparation-notes"><summary>Supporting preparation notes</summary>' in page.text
    assert notes in unescape(page.text)
    assert 'name="focus_notes"' in page.text
