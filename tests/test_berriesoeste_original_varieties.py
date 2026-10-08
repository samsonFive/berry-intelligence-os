"""Original names and photo attribution must not bypass analyst review."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-berriesoeste-original-'
NAMES = {'Aurea', 'Arwen', 'Jacqueline', 'Mérida', 'Inás', 'Lourdesa', 'Cibeles'}


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]


def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=list(candidates))


def test_current_menu_profiles_and_all_brochure_versions_have_honest_accounting():
    rows, candidates = reconcile()
    assert len(rows) == 13 and sum(len(s['names']) for s in rows) == 19
    assert {c['candidate_name'] for c in candidates} == NAMES
    assert all(s['company_ids'] == ['company-berries-del-oeste'] and s['berry_ids'] == ['berry-strawberry'] for s in rows)
    assert all(not s['accounting_view']['issues'] and not s['needs_follow_up'] and not s.get('published_date') for s in rows)
    menu = next(s for s in rows if s['id'].endswith('current-menu'))
    assert {x['label'] for x in menu['accounting']['exclusions']} == {'Esenzia Savour', 'Iguazú Savour', 'Iguazú'}
    assert menu['accounting']['observed_items'] == 10 and len(menu['names']) == 7
    brochures = [s for s in rows if s['source_type'] == 'technical_sheet']
    assert len(brochures) == 5 and sum(s['capture_reference']['pages'] for s in brochures) == 29
    assert all(s['capture_reference']['visually_checked_pages'] == list(range(1,s['capture_reference']['pages']+1)) for s in brochures)
    aurea = [s for s in brochures if s['names'][0]['candidate_name'] == 'Áurea']
    assert {s['url'] for s in aurea} == {
        'https://www.berriesdeloeste.com/wp-content/uploads/2025/09/aurea-esp.pdf',
        'https://www.berriesdeloeste.com/wp-content/uploads/2026/10/aurea-esp.pdf'}
    assert {s['capture_reference']['pages'] for s in aurea} == {5,6}
    assert len({s['capture_reference']['sha256'] for s in aurea}) == 2
    assert all(not c['auto_confirmed'] and not c['human_gated'] and not c['aliases'] and not c['proposed_relationships'] for c in candidates)
    assert all(not c['registration']['status'] and not c.get('denomination') and not c.get('breeder_code') for c in candidates)
    table = company_variety_discoveries(entity_id='company-berries-del-oeste', sources=rows)
    assert len(table['rows']) == 7 and len(table['berries']) == 1
    assert all('#vcand-' in r['href'] for r in table['rows'])


def test_new_observations_keep_old_anchors_and_human_arwen_fields():
    all_sources = load_portfolio_observations(DATA)
    _, old = reconcile_portfolios(sources=[s for s in all_sources if not s['id'].startswith(PREFIX)], varieties=[], entities=[], candidates=[])
    _, new = reconcile_portfolios(sources=all_sources, varieties=[], entities=[], candidates=[])
    ids = {(c['berry_id'],c['candidate_name']):c['id'] for c in new}
    assert all(ids[(c['berry_id'],c['candidate_name'])] == c['id'] for c in old)
    human = dict(id='operator-arwen', candidate_name='Arwen', berry_id='berry-strawberry',
        status='reviewed',identity_state='distinct',human_gated=True,aliases=['User spelling'],
        registration={'status':'User status'},review_notes='Keep notes',photos=[{'operator':'Keep photo'}])
    original = deepcopy(human)
    _, merged = reconcile([human])
    saved = next(c for c in merged if c['id'] == human['id'])
    assert all(saved[k] == original[k] for k in ('status','identity_state','aliases','registration','review_notes','photos'))
    assert human == original and len(merged) == 7


def test_twenty_one_named_gallery_assets_keep_private_permission_and_crop_boundaries():
    _, candidates = reconcile()
    assert sum(len(n.get('photos',[])) for s in sources() for n in s['names']) == 21
    for c in candidates:
        gallery = photos.gallery(c,sourced=photos.source_photos(c,candidate=True),authoring=True)
        assert len(gallery) == 3
        assert len({p['image_url'] for p in gallery}) == 3
        for p in gallery:
            assert p['named_variety'] == c['candidate_name'] and p['berry_id'] == 'berry-strawberry'
            assert p['source_url'].startswith('https://www.berriesdeloeste.com/')
            assert p['image_url'].startswith('https://www.berriesdeloeste.com/wp-content/uploads/')
            assert 'not individually credited' in p['credit'] and not p['license_url']
            assert p['reuse'] == 'unknown' and not p['display_image']
            assert not photos.compatible(p,dict(candidate_name=c['candidate_name'],berry_id='berry-blueberry'),candidate=True)
        assert not photos.gallery(c,sourced=gallery,authoring=False)


def test_original_versions_and_photos_render_without_loading_images_or_writing_review(monkeypatch,tmp_path):
    # The route's company filter uses real entity associations from reconciliation.
    # Empty entity fixtures intentionally cannot identify a company in a source.
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[],
        entities=[{'id':'company-berries-del-oeste','name':'Berries del Oeste','entity_type':'company'}], candidates=[])
    original = deepcopy(candidates)
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    monkeypatch.setattr(main,'variety_candidate_universe',lambda:([],candidates,{}))
    client = TestClient(main.app)
    response = client.get('/varieties/candidates',params={'company':'company-berries-del-oeste','q':'Aurea'})
    assert response.status_code == 200
    assert '1 of 7' in response.text
    assert 'https://www.berriesdeloeste.com/wp-content/uploads/2025/09/aurea-esp.pdf' in response.text
    assert 'https://www.berriesdeloeste.com/wp-content/uploads/2026/10/aurea-esp.pdf' in response.text
    assert 'Ignore permission' in response.text and 'Permission unconfirmed' in response.text
    urls = [p['image_url'] for c in candidates if c['candidate_name'] == 'Aurea' for p in photos.source_photos(c,candidate=True)]
    assert len(urls) == 3
    assert all('data-image-url="'+url+'"' in response.text and 'src="'+url+'"' not in response.text for url in urls)
    assert candidates == original and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    assert client.get('/varieties/candidates').status_code == 403
