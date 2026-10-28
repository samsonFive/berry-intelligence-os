"""Candidate-specific cautions stay prominent without losing wider source notes."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios, _source_fingerprint

DATA = Path(__file__).resolve().parents[1] / 'data'
FOLDER = 'variety-portfolio-observations-2026-10-28-warning-scopes'


def fixture_source(scopes):
    return {'id': 'source-scope', 'title': 'Named entries', 'url': 'https://example.test/source',
            'checked_on': '2026-10-09', 'source_type': 'breeder_catalog', 'company_ids': [],
            'berry_ids': ['berry-raspberry'], 'capture_status': 'names_enumerated',
            'review_state': 'unreviewed', 'enumerated_scope': 'Two names', 'limitations': 'Partial source',
            'names': [{'candidate_name': name, 'berry_id': 'berry-raspberry'} for name in ('One', 'Two')],
            'review_warnings': ['Always check', 'One has a disputed code'], 'review_warning_scopes': scopes}


def test_explicit_scope_changes_only_warning_placement_and_preserves_human_fields():
    source = fixture_source([{'message': 'One has a disputed code', 'candidate_names': ['One']}])
    human = {'id': 'retained-two', 'candidate_name': 'Two', 'berry_id': 'berry-raspberry',
             'status': 'rejected', 'identity_state': 'rejected', 'human_gated': True,
             'review_notes': 'Keep operator decision', 'knowledge': {'notes': 'User edit'}}
    original = deepcopy((source, human))
    rows, candidates = reconcile_portfolios(sources=[source], varieties=[], entities=[], candidates=[human])
    one = next(c for c in candidates if c['candidate_name'] == 'One')
    two = next(c for c in candidates if c['candidate_name'] == 'Two')
    assert one['portfolio_review_warnings'] == ['Always check', 'One has a disputed code']
    assert two['portfolio_review_warnings'] == ['Always check']
    assert two['portfolio_sources'][0]['other_entry_warnings'] == ['One has a disputed code']
    assert rows[0]['review_warnings'] == source['review_warnings'] and rows[0]['needs_follow_up']
    assert two['id'] == human['id'] and two['identity_state'] == 'rejected'
    assert two['review_notes'] == human['review_notes'] and two['knowledge'] == human['knowledge']
    assert (source, human) == original
    # Without explicit source metadata, the same warning remains prominent.
    del source['review_warning_scopes']
    _, conservative = reconcile_portfolios(sources=[source], varieties=[], entities=[], candidates=[])
    assert all('One has a disputed code' in c['portfolio_review_warnings'] for c in conservative)


def test_source_only_scope_retains_the_note_without_assigning_it_to_a_candidate():
    source = fixture_source([{'message': 'One has a disputed code', 'candidate_names': []}])
    rows, candidates = reconcile_portfolios(sources=[source], varieties=[], entities=[], candidates=[])
    assert rows[0]['review_warnings'] == source['review_warnings'] and rows[0]['needs_follow_up']
    assert all(c['portfolio_review_warnings'] == ['Always check'] for c in candidates)
    assert all(c['portfolio_sources'][0]['other_entry_warnings'] == ['One has a disputed code']
               for c in candidates)


@pytest.mark.parametrize('scopes', [None, {}, [None], [{'message': 'missing', 'candidate_names': ['One']}],
    [{'message': 'Always check', 'candidate_names': 'One'}],
    [{'message': 'Always check', 'candidate_names': ['Alias not in source']}],
    [{'message': 'Always check', 'candidate_names': ['One', 'One']}],
    [{'message': 'Always check', 'candidate_names': [{}]}],
    [{'message': 'Always check', 'candidate_names': ['One'], 'typo': True}],
    [{'message': 'Always check', 'candidate_names': ['One']},
     {'message': 'Always check', 'candidate_names': ['Two']}],
])
def test_invalid_scope_cannot_silently_suppress_a_warning(tmp_path, scopes):
    folder = tmp_path / 'imports/variety-portfolio-observations-fixture'
    folder.mkdir(parents=True)
    (folder / 'observations.json').write_text(json.dumps({
        'kind': 'unreviewed_portfolio_name_observations', 'sources': [fixture_source(scopes)]}))
    with pytest.raises(ValueError):
        load_portfolio_observations(tmp_path)


@pytest.mark.parametrize('new_snapshot', [False, True])
def test_overlay_never_replaces_operator_edits_or_a_newer_capture(tmp_path, new_snapshot):
    base = fixture_source([])
    original = tmp_path / 'imports/variety-portfolio-observations-2026-10-09/observations.json'
    original.parent.mkdir(parents=True)
    def write(path, source):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'kind': 'unreviewed_portfolio_name_observations',
                                   'sources': [source]}, indent=4))
    write(original, base)
    overlay = tmp_path / 'imports/variety-portfolio-observations-2026-10-28-scope/observations.json'
    overlay.parent.mkdir(parents=True)
    overlay.write_text(json.dumps({'kind': 'unreviewed_portfolio_name_observations', 'sources': [],
        'warning_scope_overlays': [{'source_id': base['id'], 'source_fingerprint': _source_fingerprint(base),
            'review_warning_scopes': [{'message': 'One has a disputed code', 'candidate_names': ['One']}]}]}))
    assert load_portfolio_observations(tmp_path)[0]['review_warning_scopes'][0]['candidate_names'] == ['One']
    edited = deepcopy(base)
    edited['names'][1]['candidate_name'] = 'Operator corrected name'
    edited['limitations'] = 'Preserve newer operator context'
    edited['review_warnings'].append('Operator caution')
    if new_snapshot:
        edited['checked_on'] = '2026-10-20'
        target = tmp_path / 'imports/variety-portfolio-observations-2026-10-29-new-capture/observations.json'
    else:
        target = original
    write(target, edited)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*.json')}
    result = load_portfolio_observations(tmp_path)
    assert result == [edited]  # Neither old names nor old scope replaces the edit.
    rows, candidates = reconcile_portfolios(sources=result, varieties=[], entities=[], candidates=[])
    assert all('One has a disputed code' in c['portfolio_review_warnings']
               and 'Operator caution' in c['portfolio_review_warnings'] for c in candidates)
    assert {p: p.read_bytes() for p in tmp_path.rglob('*.json')} == before


@pytest.mark.parametrize('change', [{'source_id': 'unavailable'}, {'source_fingerprint': 'not-a-fingerprint'},
                                    {'review_warning_scopes': None}])
def test_overlay_requires_a_real_source_valid_fingerprint_and_scopes(tmp_path, change):
    base = fixture_source([])
    folder = tmp_path / 'imports/variety-portfolio-observations-fixture'
    folder.mkdir(parents=True)
    overlay = {'source_id': base['id'], 'source_fingerprint': _source_fingerprint(base),
               'review_warning_scopes': [{'message': 'Always check', 'candidate_names': ['One']}]}
    (folder / 'observations.json').write_text(json.dumps({
        'kind': 'unreviewed_portfolio_name_observations', 'sources': [base],
        'warning_scope_overlays': [{**overlay, **change}]}))
    with pytest.raises(ValueError):
        load_portfolio_observations(tmp_path)


def test_scope_snapshot_preserves_every_original_capture_name_warning_and_date():
    old = {}
    for path in sorted((DATA / 'imports').glob('variety-portfolio-observations-*/observations.json')):
        if path.parent.name != FOLDER:
            old.update({s['id']: s for s in json.loads(path.read_text(encoding='utf-8'))['sources']})
    current = [s for s in load_portfolio_observations(DATA) if 'review_warning_scopes' in s]
    assert len(current) == 4
    for source in current:
        assert {k: v for k, v in source.items() if k != 'review_warning_scopes'} == old[source['id']]
    _, candidates = reconcile_portfolios(sources=current, varieties=[], entities=[], candidates=[])
    baridi = next(c for c in candidates if c.get('trade_name') == 'Baridi' or c['candidate_name'] == 'Baridi')
    assert any('Baridi' in warning for warning in baridi['portfolio_review_warnings'])
    for candidate in candidates:
        if candidate['candidate_name'] in {'Malaika', 'Zawadi'}:
            assert not candidate['portfolio_review_warnings']
            assert any('Baridi' in warning for ref in candidate['portfolio_sources']
                       for warning in ref.get('other_entry_warnings', []))


class Notes(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack = []; self.text = []

    def handle_starttag(self, tag, attrs):
        if tag not in {'br', 'img', 'input', 'link', 'meta', 'hr'}:
            self.stack.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.stack = self.stack[:i]; break

    def handle_data(self, text):
        if text.strip():
            self.text.append((text.strip(), list(self.stack)))

    def locations(self, message):
        return [stack for text, stack in self.text if text == message]


def test_other_name_note_collapses_but_focal_company_and_identity_cautions_stay_visible(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    response = client.get('/varieties/candidates', params={
        'source': 'portfolio-raspberry-original-uspp36008p3'})
    assert response.status_code == 200
    notes = Notes(); notes.feed(response.text)
    lewis = 'Lewis is used for two raspberries. Check Hutton’s Bonnie Lewis and USDA’s older Lewis separately.'
    locations = notes.locations(lewis)
    assert len(locations) == 1
    assert any(tag == 'details' and attrs.get('class') == 'candidate-source-context' and 'open' not in attrs
               for tag, attrs in locations[0])
    company = 'Allberry B.V. and Advanced Berry Breeding are not automatically treated as the same legal organization.'
    assert any(attrs.get('aria-label') == 'Source details to check'
               for stack in notes.locations(company) for _, attrs in stack)
    assert 'Original claim' in response.text and 'Notes about other entries in this source' in response.text
    bonnie = client.get('/varieties/candidates', params={
        'source': 'portfolio-register52-2024-raspberry-main', 'q': 'Bonnie Lewis'})
    assert bonnie.status_code == 200
    notes = Notes(); notes.feed(bonnie.text)
    assert any(attrs.get('aria-label') == 'Source details to check'
               for stack in notes.locations(lewis) for _, attrs in stack)
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
