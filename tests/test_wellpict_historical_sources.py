"""Historical trial evidence cannot establish a current portfolio or rights."""
from copy import deepcopy
from html import escape
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-wellpict-original-'
WELL = 'company-well-pict'
PSI = 'company-plant-sciences-genetics'


def all_sources():
    return load_portfolio_observations(DATA)


def reconcile(rows, candidates=()):
    return reconcile_portfolios(sources=rows, varieties=[],
        entities=[dict(id=WELL, name='Well-Pict', entity_type='company'),
                  dict(id=PSI, name='Plant Sciences, Inc.', entity_type='company')], candidates=list(candidates))


def test_original_subject_names_claim_pages_and_comparators_are_fully_accounted():
    rows, candidates = reconcile([s for s in all_sources() if s['id'].startswith(PREFIX)])
    assert len(rows) == len(candidates) == 2
    assert all(not r['accounting_view']['issues'] for r in rows)
    for row, date, pages, claim in [(rows[0], '1993-04-20', 8, 4), (rows[1], '1993-01-05', 7, 3)]:
        assert row['published_date'] == date
        assert row['company_ids'] == [WELL, PSI]
        assert row['capture_reference']['visually_checked_pages'] == list(range(1, pages+1))
        assert row['capture_reference']['all_pages_read']
        assert row['names'][0]['product_url'].endswith(f'.pdf#page={claim}')
        assert 'trial-site connection' in row['names'][0]['portfolio_context']
        assert 'current legal status' in row['limitations']
        assert {'Selva', 'Muir', 'Irvine', 'Chandler', 'Pajaro', 'Douglas'} <= {
            x['label'] for x in row['accounting_view']['exclusions']}
    assert {c['candidate_name'] for c in candidates} == {'PSI-.118', 'PSI-130'}
    assert 'January 5, 1992' in rows[1]['limitations']
    assert {'Fern', 'PSI-118'} <= {x['label'] for x in rows[1]['accounting_view']['exclusions']}
    assert all(not c['aliases'] and not c['proposed_relationships'] and not c['deployment']
               and not c['breeder_owner'] and not c['auto_confirmed'] and not c['human_gated'] for c in candidates)
    assert all(not c['registration']['official_registry_source'] and not c['registration']['status'] for c in candidates)


def test_six_original_photographs_have_unknown_reuse_and_diagrams_are_excluded():
    _, candidates = reconcile([s for s in all_sources() if s['id'].startswith(PREFIX)])
    refs = [p for c in candidates for p in photos.source_photos(c, candidate=True)]
    assert len(refs) == len({p['image_url'] for p in refs}) == 6
    assert sum(p['kind'] == 'fruit' for p in refs) == 2
    assert all(p['kind'] != 'drawing' and 'photographer not identified' in p['credit'] for p in refs)
    assert not any('page-8.png' in p['image_url'] for p in refs)
    for c in candidates:
        private = photos.gallery(c, sourced=photos.source_photos(c, candidate=True), authoring=True)
        assert len(private) == 3
        assert all(p['reuse'] == 'unknown' and not p['display_image'] and not p['license_url'] for p in private)
        assert not photos.gallery(c, sourced=private, authoring=False)


def test_perfection_unnamed_product_ranges_and_partnership_do_not_map_patent_subjects():
    rows = [s for s in all_sources() if s['id'].startswith('portfolio-perfection-original-')]
    assert len(rows) == 6 and all(s['capture_status'] == 'partial' and not s['names'] for s in rows)
    assert all(s['company_ids'] == ['company-perfection-fresh'] for s in rows)
    assert all(s['capture_reference']['page_read'] for s in rows)
    announcement = next(s for s in rows if s['id'].endswith('psi-announcement'))
    assert announcement['published_date'] == '2020-07-23'
    assert all(not s.get('published_date') for s in rows if s != announcement)
    assert all('does not establish' in s['limitations'] for s in rows)
    _, candidates = reconcile(rows)
    assert not candidates
    gap = next(s for s in all_sources() if s['id'] == 'portfolio-gap-wellpict-dns')
    assert gap['capture_status'] == 'unreadable' and not gap['names']


def test_replay_preserves_existing_anchors_operator_photos_and_rejected_identity():
    sources = all_sources()
    _, old = reconcile([s for s in sources if not s['id'].startswith(PREFIX)])
    _, new = reconcile(sources)
    old_keys = {(c['berry_id'], c['candidate_name'], c['id']) for c in old}
    new_keys = {(c['berry_id'], c['candidate_name'], c['id']) for c in new}
    assert old_keys <= new_keys
    assert {name for _, name, _ in new_keys-old_keys} == {'PSI-.118', 'PSI-130'}
    human = dict(id='operator-psi130', candidate_name='PSI-130', berry_id='berry-strawberry',
                 status='rejected', identity_state='rejected', human_gated=True,
                 review_notes='User decision', aliases=['User alias'], photos=[{'operator': 'Private'}],
                 registration={'status': 'User rights note'})
    before = deepcopy(human)
    rows, candidates = reconcile([s for s in sources if s['id'].startswith(PREFIX)], [human])
    saved = next(c for c in candidates if c['id'] == human['id'])
    assert human == before and all(saved[k] == v for k,v in before.items())
    assert next(r for r in rows if r['id'].endswith('psi-130'))['names'][0]['status'] == 'previously_rejected'


def test_private_company_scoped_review_links_claims_without_auto_loading_or_writing(monkeypatch, tmp_path):
    _, candidates = reconcile([s for s in all_sources() if s['id'].startswith(PREFIX)])
    before = deepcopy(candidates)
    assert [c['candidate_name'] for c in candidate_queue(candidates, {'company': WELL, 'q': 'PSI-130'})['candidates']] == ['PSI-130']
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([], candidates, {}))
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'company': WELL, 'q': 'PSI-130'})
    assert page.status_code == 200 and '1 of 2' in page.text
    assert 'Original claim' in page.text and 'USPP8086.pdf#page=3' in page.text
    assert 'trial-site connection' in page.text and '1993-01-05' in page.text
    assert 'Ignore permission' in page.text and 'Permission unconfirmed' in page.text
    for photo in photos.source_photos(next(c for c in candidates if c['candidate_name'] == 'PSI-130'), candidate=True):
        url = escape(photo['image_url'], quote=True)
        assert 'data-image-url="'+url+'"' in page.text and 'src="'+url+'"' not in page.text
    assert candidates == before and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
