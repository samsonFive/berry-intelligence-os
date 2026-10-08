"""Named launch leads remain distinct from packaging and trusted intelligence."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.variety_portfolio_coverage import (
    load_portfolio_observations, portfolio_coverage, reconcile_portfolios,
)

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-camposol-original-'


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]


def test_names_are_accounted_without_program_factory_or_packaging_identities():
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    assert len(rows) == 2
    assert {c['candidate_name'] for c in candidates} == {'Sol One', 'Maia Blue'}
    assert all(not s['accounting_view']['issues'] for s in rows)
    launch = next(s for s in rows if s['capture_status'] == 'names_enumerated')
    product = next(s for s in rows if s['capture_status'] == 'partial')
    assert launch['published_date'] == '2026-02-04' and not product.get('published_date')
    assert launch['accounting_view']['accounted_items'] == 4
    assert product['accounting_view']['accounted_items'] == 8 and not product['names']
    assert {x['label'] for x in launch['accounting']['exclusions']} == {'ORIGEN', 'Invitrolab'}
    assert all(s['company_ids'] == ['company-camposol'] and s['berry_ids'] == ['berry-blueberry'] for s in rows)
    assert all(len(s['capture_reference']['capture_sha256']) == 64 for s in rows)
    assert product['needs_follow_up'] and 'named-variety coverage' in product['limitations'].lower()
    assert all('crop identity still needs review' in s['limitations'] for s in rows if s == launch)


def test_contextual_crop_and_launch_claims_do_not_create_trusted_relationships():
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    for candidate in candidates:
        assert not candidate['auto_confirmed'] and not candidate['human_gated']
        assert not candidate['aliases'] and not candidate['proposed_relationships']
        assert not candidate['registration']['status'] and not candidate['registration']['application_number']
        assert 'blueberry context requires identity review' in candidate['portfolio_sources'][0]['portfolio_context']
    assert all(not n.get('photos') and not n.get('denomination') and not n.get('breeder_code')
               for s in sources() for n in s['names'])
    report = portfolio_coverage(data_dir=DATA, sources=sources(), varieties=[], entities=[], candidates=[])
    assert report['summary']['catalog_matches'] == 0 and report['summary']['needs_review'] == 2
    assert report['summary']['follow_up_sections'] == 1


def test_added_sources_preserve_all_existing_anchors_and_user_decisions():
    all_sources = load_portfolio_observations(DATA)
    human = dict(id='operator-sol-one', candidate_name='Sol One', berry_id='berry-blueberry',
                 human_gated=True, status='rejected', identity_state='uncertain',
                 aliases=['User spelling'], review_notes='Private decision',
                 registration={'status': 'User status'}, photos=[{'operator': 'User photo'}])
    before = deepcopy(human)
    _, old = reconcile_portfolios(sources=[s for s in all_sources if not s['id'].startswith(PREFIX)],
                                 varieties=[], entities=[], candidates=[human])
    _, new = reconcile_portfolios(sources=all_sources, varieties=[], entities=[], candidates=[human])
    old_keys = {(c['berry_id'], c['candidate_name'], c['id']) for c in old}
    new_keys = {(c['berry_id'], c['candidate_name'], c['id']) for c in new}
    assert old_keys <= new_keys and len(new_keys - old_keys) == 1  # Only Maia Blue is new here.
    saved = next(c for c in new if c['id'] == human['id'])
    assert all(saved[k] == before[k] for k in before) and human == before
    launch = next(s for s in reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[human])[0]
                  if s['capture_status'] == 'names_enumerated')
    assert next(n for n in launch['names'] if n['candidate_name'] == 'Sol One')['status'] == 'previously_rejected'


def test_private_company_source_view_has_exact_review_links_and_no_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    response = client.get('/varieties/coverage', params={'company': 'company-camposol'})
    assert response.status_code == 200
    assert 'Sol One' in response.text and 'Maia Blue' in response.text
    assert 'crop identity still needs review' in response.text
    assert 'Packaging/product format, not a named cultivar.' in response.text
    assert 'href="https://www.camposol.com/product/blueberries/"' in response.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/coverage', params={'company': 'company-camposol'})
    assert public.status_code == 200
    assert PREFIX not in public.text and 'Maia Blue' not in public.text
    assert not list(tmp_path.rglob('*.json'))
