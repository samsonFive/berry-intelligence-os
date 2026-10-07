"""University source depth must preserve dates, identities and old observations."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from scripts.audit_variety_portfolios import audit

ROOT = Path(__file__).resolve().parents[1]


def university_sources():
    return json.loads((ROOT / 'data/imports/variety-portfolio-observations-2026-10-07-universities/observations.json').read_text(encoding='utf-8'))['sources']


def test_refresh_accounts_for_existing_arkansas_scope_once_without_losing_names():
    before = json.loads((ROOT / 'data/imports/variety-portfolio-observations-2026-10-07/observations.json').read_text(encoding='utf-8'))['sources']
    old = next(s for s in before if s['id'] == 'portfolio-arkansas-blackberry')
    sources = load_portfolio_observations(ROOT / 'data')
    matching = [s for s in sources if s['id'] == old['id']]
    assert len(matching) == 1
    assert [n['candidate_name'] for n in matching[0]['names']] == [n['candidate_name'] for n in old['names']]
    assert all('product_url' in n for n in matching[0]['names'][:15])
    assert all('Historical' in n['portfolio_context'] for n in matching[0]['names'][15:])
    current = next(s for s in sources if s['id'] == 'portfolio-arkansas-current-blackberry')
    assert len(current['names']) == current['accounting']['observed_items'] == 9
    assert '43 varieties developed' in current['enumerated_scope']
    assert not current['accounting'].get('reported_items')  # 43 is a program total, not page cards.


def test_code_name_source_pair_is_not_an_automatic_alias_or_catalog_write():
    source = next(s for s in university_sources() if s['id'] == 'portfolio-arkansas-current-blackberry')
    before = deepcopy(source)
    varieties = [{'id': 'v-ponca', 'name': 'Sweet-Ark Ponca', 'entity_type': 'variety', 'berry_ids': ['berry-blackberry']}]
    old_varieties = deepcopy(varieties)
    rows, candidates = reconcile_portfolios(sources=[source], varieties=varieties, entities=[], candidates=[])
    code = next(c for c in candidates if c['candidate_name'] == 'A-2538T')
    assert code['trade_name'] == 'Sweet-Ark Ponca' and code['candidate_canonical_match'] == 'v-ponca'
    assert not code['human_gated'] and not code['auto_confirmed']
    assert code['aliases'] == [] and code['proposed_relationships'] == []
    assert rows[0]['matched'] == 0  # Trade-name overlap is a suggestion, not exact code identity.
    assert candidate_queue(candidates, {'q': 'Ponca'})['candidates'] == [code]
    assert source == before and varieties == old_varieties


def test_cornell_provenance_retains_historical_dates_for_unknown_fixture_identities():
    report = audit(ROOT / 'data')
    historical = next(s for s in report['sources'] if s['id'] == 'portfolio-cornell-historical-release-2012')
    assert historical['published_date'] == '2012-04-30' and historical['checked_on'] == '2026-10-07'
    rows, candidates = reconcile_portfolios(sources=university_sources(), varieties=[], entities=[], candidates=[])
    matches = candidate_queue(candidates, {'q': 'Double Gold', 'source': historical['id'], 'berry': 'berry-raspberry'})['candidates']
    assert len(matches) == 1
    references = matches[0]['portfolio_sources']
    assert {r['id'] for r in references} == {'portfolio-cornell-current-licensing', 'portfolio-cornell-raspberry-chart-2018', historical['id']}
    old = next(r for r in references if r['id'] == historical['id'])
    assert old['published_date'] == '2012-04-30' and old['url'] == historical['url']
    chart = next(r for r in references if r['id'] == 'portfolio-cornell-raspberry-chart-2018')
    assert chart['breeder_code'] == 'D-4778' and 'published_date' not in chart
    assert not matches[0]['human_gated'] and matches[0]['proposed_relationships'] == []


def test_review_get_shows_dates_and_program_profile_without_private_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/coverage?q=Cornell')
    assert page.status_code == 200
    assert 'href="/entities/breeding_program/breeding_program-cornell-berry"' in page.text
    assert 'datetime="2012-04-30"' in page.text and 'source checked 2026-10-07' in page.text
    assert 'href="/entities/company/breeding_program-cornell-berry"' not in page.text
    assert 'href="/entities/variety/variety-double-gold"' in page.text
    candidate = client.get('/varieties/candidates?q=Crimson+Giant&berry=berry-raspberry')
    assert candidate.status_code == 200 and 'datetime="2012-04-30"' in candidate.text
    assert 'D-4330' in candidate.text
    assert not list(tmp_path.rglob('*'))


def test_invalid_publication_date_is_not_silently_replaced_by_check_date(tmp_path):
    source = deepcopy(university_sources()[0])
    source['published_date'] = '2026-14-32'
    folder = tmp_path / 'imports/variety-portfolio-observations-invalid-date'
    folder.mkdir(parents=True)
    path = folder / 'observations.json'
    path.write_text(json.dumps({'kind': 'unreviewed_portfolio_name_observations', 'sources': [source]}), encoding='utf-8')
    before = path.read_bytes()
    with pytest.raises(ValueError, match='failed validation'):
        load_portfolio_observations(tmp_path)
    assert path.read_bytes() == before
