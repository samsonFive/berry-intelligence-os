"""Historical company names must not become current portfolios or alias decisions."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import (
    load_portfolio_observations, portfolio_coverage, reconcile_portfolios,
)

DATA = Path(__file__).resolve().parents[1] / 'data'
SOURCE = 'portfolio-splendor-company-interview-2011-blackberry'


def inputs():
    sources = load_portfolio_observations(DATA)
    return sources, next(s for s in sources if s['id'] == SOURCE)


def test_original_spellings_month_only_date_and_unnamed_crops_remain_distinct():
    _, source = inputs()
    assert [n['candidate_name'] for n in source['names']] == ['Tuppy', 'Brazzo', 'Brasileña']
    assert source['source_type'] == 'company_interview' and source['review_state'] == 'unreviewed'
    assert source['capture_reference']['publication_period'] == 'August 2011'
    assert source['capture_reference']['pdf_pages_read'] == [3, 35]
    assert source['capture_reference']['capture_sha256'] == 'cc6dd98a69af2cdaaa1a22023936ee4577c7233596a7ad84ff084d76083231dd'
    assert not source.get('published_date')
    assert source['url'].endswith('/2024/08/pb-aug-2011.pdf#page=35')
    assert source['accounting']['observed_items'] == 5
    assert [r['label'] for r in source['accounting']['exclusions']] == ['raspberry', 'blueberry']
    assert all(n['berry_id'] == 'berry-blackberry' and not n.get('photos') for n in source['names'])
    # Similar spellings in a catalog do not authorize a new alias or role.
    varieties = [dict(id='v-'+name, name=name, entity_type='variety', berry_ids=['berry-blackberry'])
                 for name in ['Tupy', 'Brazos']]
    rows, candidates = reconcile_portfolios(sources=[source], varieties=varieties, entities=varieties, candidates=[])
    assert all(n['status'] == 'needs_review' and not n['catalog_id'] for n in rows[0]['names'])
    assert len(candidates) == 3 and all(not c['human_gated'] and not c['auto_confirmed'] for c in candidates)
    assert all(not n.get(key) for n in source['names'] for key in ('denomination', 'breeder_code', 'grant_date', 'photos'))


def test_new_source_keeps_all_prior_ids_and_saved_rejection_and_is_idempotent():
    sources, source = inputs()
    baseline = [s for s in sources if s['id'] != SOURCE]
    _, saved = reconcile_portfolios(sources=baseline, varieties=[], entities=[], candidates=[])
    operator = dict(id='operator-tuppy', candidate_name='Tuppy', berry_id='berry-blackberry',
        status='rejected', human_gated=True, identity_state='rejected', reviewer='Fixture analyst',
        review_notes='Keep my rejection', aliases=['My spelling'], photos=[{'operator':'Keep image choice'}],
        registration={'status':'Keep user status'})
    saved.append(operator)
    original = deepcopy((sources, saved))
    rows, visible = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=saved)
    by_id = {c['id']:c for c in visible}
    for old in saved:
        assert old['id'] in by_id
        for key, value in old.items():
            if key not in {'portfolio_sources', 'portfolio_review_warnings', 'portfolio_identity_notes'}:
                assert by_id[old['id']][key] == value
    first = next(s for s in rows if s['id'] == SOURCE)['names'][0]
    assert first['candidate_id'] == operator['id'] and first['status'] == 'previously_rejected'
    assert not first['catalog_id']
    replay_rows, replay = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=visible)
    assert replay_rows == rows and replay == visible
    assert len({c['id'] for c in replay}) == len(replay)
    assert (sources, saved) == original


def test_named_historical_source_does_not_clear_company_coverage_gaps():
    sources, source = inputs()
    entities = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((DATA/'entities').rglob('*.json'))]
    varieties = [r for r in entities if r.get('entity_type') == 'variety']
    report = portfolio_coverage(data_dir=DATA, sources=sources, varieties=varieties, entities=entities, candidates=[])
    subject = next(s for s in report['subjects'] if 'company-splendor-produce' in s['entity_ids'])
    assert subject['source_status'] == 'names_found' and subject['checked']
    assert subject['has_source_gaps'] and subject['named_occurrences'] == 3
    row = next(s for s in report['sources'] if s['id'] == SOURCE)
    assert row['needs_follow_up'] and row['accounting_view']['accounted_items'] == 5
    assert not row['accounting_view']['issues'] and row['review_warnings']


def test_reader_handoff_shows_historical_context_without_a_fake_publication_day(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'source':SOURCE, 'company':'company-splendor-produce'})
    assert page.status_code == 200
    assert all(name in page.text for name in ['Tuppy', 'Brazzo', 'Brasileña'])
    assert 'August 2011 company interview' in page.text
    assert 'not breeding or rights ownership' in page.text
    assert '2011-08-01' not in page.text and 'Published <time' not in page.text
    body = client.get('/varieties/coverage/source/'+SOURCE)
    assert body.status_code == 200 and 'August 2011' in body.text
    assert 'pb-aug-2011.pdf#page=35' in body.text and '2024 upload directory' in body.text
    company = client.get('/entities/company/company-splendor-produce', params={'tab':'varieties'})
    assert company.status_code == 200
    assert all(name in company.text for name in ['Tuppy', 'Brazzo', 'Brasileña'])
    assert 'August 2011' in company.text and 'Name needs review' in company.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/candidates', params={'q':'Brasileña'})
    assert public.status_code == 403
    assert SOURCE not in public.text and 'pb-aug-2011.pdf' not in public.text
