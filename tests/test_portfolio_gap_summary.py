"""Named sources must not conceal the same company's open source gaps."""
from copy import deepcopy
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage

DATA = Path(__file__).resolve().parents[1] / 'data'


def report(company=''):
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((DATA/'entities').rglob('*.json'))]
    return portfolio_coverage(data_dir=DATA, sources=load_portfolio_observations(DATA),
        varieties=[e for e in entities if e.get('entity_type') == 'variety'], entities=entities,
        candidates=[], filters={'company': company})


def progress(html):
    return re.search(r'<div class="portfolio-source-progress"[^>]*>(.*?)</div>', html, re.S).group(1)


def test_named_company_keeps_open_gap_badge_without_changing_partial_only_metric():
    portfolios = report('company-perfection-fresh')
    before = deepcopy(portfolios)
    assert portfolios['summary']['registry_entries_checked'] == 1
    assert portfolios['summary']['registry_entries_partial_checks'] == 0
    assert portfolios['summary']['follow_up_sections'] == 8
    rendered = main.templates.env.get_template('_variety_portfolio_coverage.html').render(
        coverage={'portfolios': portfolios})
    assert '<b>1</b> entry with source gaps' in progress(rendered)
    assert 'Companies with names found can still have source gaps.' in rendered
    assert '8 source checks still have gaps' in rendered
    assert 'checked, list incomplete' not in rendered
    assert portfolios == before


def test_gap_badge_counts_filtered_subjects_not_source_rows_or_global_totals():
    portfolios = report('company-perfection-fresh')
    portfolios['subjects'].append({**portfolios['subjects'][0], 'name': 'Fixture second entry'})
    rendered = main.templates.env.get_template('_variety_portfolio_coverage.html').render(
        coverage={'portfolios': portfolios})
    assert '<b>2</b> entries with source gaps' in progress(rendered)
    portfolios['subjects'][0]['has_source_gaps'] = False
    rendered = main.templates.env.get_template('_variety_portfolio_coverage.html').render(
        coverage={'portfolios': portfolios})
    assert '<b>1</b> entry with source gaps' in progress(rendered)


def test_live_company_scope_renders_named_and_incomplete_without_private_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    response = TestClient(main.app).get('/varieties/coverage', params={'company': 'company-perfection-fresh'})
    assert response.status_code == 200
    assert '<b>1</b> entry with source gaps' in progress(response.text)
    assert '8 source checks still have gaps' in response.text
    assert 'Arabella in the Autumn 2022 grower interview' in response.text
    assert 'Company: Perfection Fresh' in response.text
    assert not list(tmp_path.rglob('*.json'))
