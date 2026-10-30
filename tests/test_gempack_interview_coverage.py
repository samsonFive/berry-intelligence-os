"""Interview names keep crop, company, date and existing review boundaries."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import (
    load_portfolio_observations, portfolio_coverage, reconcile_portfolios,
)


DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-gempack-interview-'


def test_interview_scopes_exclude_neighboring_companies_and_unnamed_selections():
    sources = load_portfolio_observations(DATA)
    cohort = [s for s in sources if s['id'].startswith(PREFIX)]
    assert len(cohort) == 3
    pairs = {(n['candidate_name'], n['berry_id']) for s in cohort for n in s['names']}
    assert pairs == {(name, 'berry-strawberry') for name in (
        'Alturas', 'Carpinteria', 'Fronteras', 'Monterey', 'Belvedere', 'Victor', 'Adelanto', 'San Andreas'
    )} | {('Majestic', 'berry-raspberry'), ('Adelita', 'berry-raspberry')}
    april = next(s for s in cohort if '2025-04' in s['id'])
    assert april['published_date'] == '2025-04-07'
    assert april['url'].endswith('.pdf#page=34')
    assert april['capture_reference']['publication_pages'] == '32'
    assert {x['label'] for x in april['accounting']['exclusions']} == {
        'proprietary strawberries', 'BG', 'Short N Sweet'}
    for source in cohort:
        assert source['company_ids'] == ['company-gem-pack-berries']
        assert source['review_state'] == 'unreviewed'
        assert len(source['names']) + len(source['accounting']['exclusions']) == source['accounting']['observed_items']
        for name in source['names']:
            assert name['source_company_ids'] == ['company-gem-pack-berries']
            assert not any(name.get(k) for k in ('photos', 'denomination', 'breeder_code', 'grant_number'))
    assert {s['published_date'] for s in cohort if '2026-07' in s['id']} == {'2026-07-21'}


def test_added_interviews_preserve_saved_rejection_and_replay_without_duplicate_ids():
    sources = load_portfolio_observations(DATA)
    before_sources = [s for s in sources if not s['id'].startswith(PREFIX)]
    _, saved = reconcile_portfolios(sources=before_sources, varieties=[], entities=[], candidates=[])
    target = next(c for c in saved if c['candidate_name'] == 'Alturas' and c['berry_id'] == 'berry-strawberry')
    target.update(status='rejected', identity_state='rejected', human_gated=True,
                  review_notes='Keep the analyst decision', aliases=['My retained label'],
                  photos=[{'operator': 'Keep my photo'}], registration={'status': 'My saved status'})
    frozen = deepcopy((sources, saved))
    rows, after = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=saved)
    by_id = {c['id']: c for c in after}
    for original in saved:
        for key, value in original.items():
            if key not in {'portfolio_sources', 'portfolio_review_warnings', 'portfolio_identity_notes'}:
                assert by_id[original['id']][key] == value
    july = next(s for s in rows if s['id'] == PREFIX+'2026-07-strawberry')
    rejected = next(n for n in july['names'] if n['candidate_name'] == 'Alturas')
    assert rejected['candidate_id'] == target['id'] and rejected['status'] == 'previously_rejected'
    assert rejected['catalog_id'] is None
    _, replay = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=after)
    assert len({c['id'] for c in replay}) == len(replay) == len(after)
    assert {c['id'] for c in replay} == set(by_id)
    assert (sources, saved) == frozen


def test_named_interviews_do_not_clear_existing_gempack_portfolio_gaps():
    sources = load_portfolio_observations(DATA)
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in (DATA/'entities').rglob('*.json')]
    varieties = [e for e in entities if e.get('entity_type') == 'variety']
    report = portfolio_coverage(data_dir=DATA, sources=sources, varieties=varieties,
                                entities=entities, candidates=[], filters={'company': 'company-gem-pack-berries'})
    subject = next(s for s in report['subjects'] if 'company-gem-pack-berries' in s['entity_ids'])
    assert subject['source_status'] == 'names_found' and subject['has_source_gaps']
    names = {n['candidate_name'] for s in report['sources'] if s['id'].startswith(PREFIX) for n in s['names']}
    assert len(names) == 10 and not names.intersection({'BG', 'Short N Sweet'})
    assert all(s['needs_follow_up'] for s in report['sources'] if s['id'] in {
        'portfolio-gap-gempack-current-crops', 'portfolio-gempack-original-history-pdf'})


def test_mixed_company_view_keeps_named_sources_and_gaps_private_without_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    query = {'company': 'company-gem-pack-berries'}
    page = client.get('/varieties/coverage', params=query)
    assert page.status_code == 200
    portfolios = page.context['coverage']['portfolios']
    assert portfolios['summary']['names'] == 10
    assert portfolios['summary']['follow_up_sections'] == 5
    assert 'We haven’t captured variety names in these pages' not in page.text
    assert 'Names found · more sources to check' in page.text
    assert 'Winter Frost' in page.text and '36 packaging/SKU rows' in page.text
    assert 'Published <time datetime="2025-04-07">2025-04-07</time>' in page.text
    assert 'Review these source names' in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/coverage', params=query)
    assert public.status_code == 200
    assert PREFIX not in public.text and 'Winter Frost' not in public.text
    assert not list(tmp_path.rglob('*.json'))
