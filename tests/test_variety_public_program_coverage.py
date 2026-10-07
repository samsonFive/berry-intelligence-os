"""Incomplete portfolios and historical co-mentions must retain their limits."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios

ROOT = Path(__file__).resolve().parents[1]


def programs():
    return [s for s in load_portfolio_observations(ROOT / 'data')
            if s['id'].startswith(('portfolio-hutton-', 'portfolio-usda-', 'portfolio-uga-'))]


def test_highlights_do_not_close_the_stated_lifetime_portfolio():
    source = next(s for s in programs() if 'hutton' in s['id'])
    rows, candidates = reconcile_portfolios(sources=[source], varieties=[], entities=[], candidates=[])
    row = rows[0]
    assert len(row['names']) == row['accounting_view']['accounted_items'] == 9
    assert row['accounting_view']['reported_items'] == 23
    assert row['accounting_view']['reported_scope'] == 'lifetime raspberry cultivars'
    assert len(row['accounting_view']['issues']) == 1 and row['needs_follow_up']
    assert len(candidates) == 9 and not any(c['human_gated'] for c in candidates)
    assert source['names'] == [{k: v for k, v in n.items() if k in ('candidate_name', 'berry_id', 'portfolio_context')}
                              for n in row['names']]


def test_genome_taxa_and_wild_selections_are_not_guessed_release_identities():
    sources = programs()
    original = deepcopy(sources)
    rows, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    names = {c['candidate_name'] for c in candidates}
    assert len(names) == 20
    assert {'Chester', 'UCD Royal Royce', 'Finnberry', 'Suziblue'} <= names
    assert not {'FaRR1', 'Rubus idaeus', 'R. coreanus', 'Ruby', 'Black Giant', 'Walker'} & names
    usda = next(r for r in rows if 'usda' in r['id'])
    assert usda['accounting_view']['accounted_items'] == 14 and not usda['needs_follow_up']
    uga = next(r for r in rows if 'program-history' in r['id'])
    assert uga['accounting_view']['accounted_items'] == 12 and len(uga['accounting_view']['exclusions']) == 8
    assert 'reported_items' not in uga['accounting_view']  # NeSmith's 39 is a different population.
    assert sources == original and all('published_date' not in s for s in sources)
    assert all(not c['proposed_relationships'] and not c['deployment'] and not c['human_gated'] for c in candidates)
    # An exclusion from this release-list scope is not a global rejection of a name.
    other = {**sources[0], 'id': 'other-release-source', 'names': [{'candidate_name': 'Ruby', 'berry_id': 'berry-blueberry'}]}
    _, other_candidates = reconcile_portfolios(sources=[*sources, other], varieties=[], entities=[], candidates=[])
    assert any(c['candidate_name'] == 'Ruby' for c in other_candidates)


def test_source_gaps_and_page_checks_remain_distinct_across_berry_filters(tmp_path):
    registry = tmp_path / 'imports/competitor-coverage-registry-2026-09-21/reconciliation-matrix.json'
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({'rows': [{'input_registry_name': 'UGA',
        'canonical_entity_ids': ['breeding_program-university-of-georgia-blueberry'], 'resolution_status': 'matched'}]}))
    sources = programs()
    all_scopes = portfolio_coverage(data_dir=tmp_path, sources=sources, varieties=[], entities=[], candidates=[])
    assert all_scopes['summary']['names'] == 20 and all_scopes['summary']['follow_up_sections'] == 2
    assert all_scopes['subjects'][0]['checked'] and all_scopes['subjects'][0]['has_source_gaps']
    filtered = portfolio_coverage(data_dir=tmp_path, sources=sources, varieties=[], entities=[], candidates=[],
                                  filters={'berry': 'berry-blackberry'})
    assert filtered['summary']['names'] == 5 and filtered['summary']['follow_up_sections'] == 0
    assert filtered['sources'][0]['accounting_view']['accounted_items'] == 14


@pytest.mark.parametrize('accounting', [
    {'observed_items': 0, 'exclusions': [], 'reported_scope': 'Lifetime'},
    {'observed_items': 0, 'exclusions': [], 'reported_items': 1, 'reported_scope': ''},
    {'observed_items': 0, 'exclusions': [], 'reported_items': 1, 'reported_scope': 23},
])
def test_reported_count_scope_requires_a_count_and_plain_label(tmp_path, accounting):
    source = {**programs()[0], 'accounting': accounting}
    path = tmp_path / 'imports/variety-portfolio-observations-bad/observations.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'kind': 'unreviewed_portfolio_name_observations', 'sources': [source]}))
    with pytest.raises(ValueError, match='failed validation'):
        load_portfolio_observations(tmp_path)


def test_live_gap_notice_is_filtered_read_only_and_private(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    response = client.get('/varieties/coverage?q=James+Hutton')
    assert response.status_code == 200
    assert '1 source check still has gaps' in response.text
    assert '9 observed items; 23 lifetime raspberry cultivars reported' in response.text
    assert 'Some names checked · source gaps remain' in response.text
    assert 'Source capture unavailable' not in response.text
    uga = client.get('/varieties/coverage?q=University+of+Georgia')
    assert 'Could not read this source' in uga.text and 'certificate-name mismatch' in uga.text
    assert 'portfolio-uga-blueberry-licensing-list-access-gap' in uga.text
    assert not list(tmp_path.rglob('*'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/coverage')
    assert public.status_code == 200 and 'lifetime raspberry cultivars' not in public.text
    assert 'georgiacultivars.com' not in public.text and 'source checks still have gaps' not in public.text
