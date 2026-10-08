"""Original CBC trial entries, claims and photos remain bounded review leads."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIX = 'portfolio-cbc-original-'
COMPANY = 'company-california-berry-cultivars'
PDF = 'https://www.cbcberry.com/docs/resources/2026/wt-may/wtfldday26_EN.pdf'


def sources():
    return [s for s in load_portfolio_observations(DATA) if s['id'].startswith(PREFIX)]


def reconcile(candidates=()):
    return reconcile_portfolios(sources=sources(), varieties=[],
        entities=[dict(id=COMPANY, name='California Berry Cultivars', entity_type='company')],
        candidates=list(candidates))


def test_all_profiles_and_full_handout_account_for_named_and_excluded_entries():
    rows, candidates = reconcile()
    assert len(rows) == 14 and sum(len(s['names']) for s in rows) == 27
    assert len(candidates) == 15
    assert all(not s['accounting_view']['issues'] for s in rows)
    assert all(s['company_ids'] == [COMPANY] and s['berry_ids'] == ['berry-strawberry'] for s in rows)
    handout = next(s for s in rows if s['url'] == PDF)
    assert len(handout['names']) == 14 and handout['capture_reference']['pages'] == 15
    assert handout['capture_reference']['visually_checked_pages'] == list(range(1, 16))
    assert handout['capture_reference']['image_only_pages'] == [5, 7, 9, 11, 14]
    names = {n['candidate_name']: n for n in handout['names']}
    assert 'Sweet Carolina' not in names
    assert {name: names[name]['breeder_code'] for name in ('CBC033', 'CBC030', 'CBC045', 'CBC043')} == {
        'CBC033': '119.056-102', 'CBC030': '118.066-601', 'CBC045': '121.008-601', 'CBC043': '121.257-605'}
    assert {'Monterey', 'Fronteras', 'UC Victor', 'Victor', 'Bounty'} <= {x['label'] for x in handout['accounting']['exclusions']}
    assert not any(n['candidate_name'].startswith('Competitor Variety') for n in handout['names'])
    old_index = next(s for s in load_portfolio_observations(DATA) if s['id'] == 'portfolio-cbc-visible-cultivars')
    assert old_index['capture_status'] == 'partial' and old_index['accounting']['reported_items'] == 12
    assert all(not s.get('published_date') for s in rows if s['source_type'] != 'plant_patent')


def test_near_identical_secondary_codes_are_searchable_without_identity_merging():
    rows, candidates = reconcile()
    original = deepcopy(candidates)
    for query, expected in [('118.060-601', 'Dunsmuir'), ('118.066-601', 'CBC030'),
                            ('117.074-601', 'Elcano'), ('121.257-605', 'CBC043')]:
        queue = candidate_queue(candidates, {'q': query, 'company': COMPANY})
        assert [c['candidate_name'] for c in queue['candidates']] == [expected]
        table = company_variety_discoveries(entity_id=COMPANY, sources=rows)
        assert [c['name'] for c in table['rows'] if query in c['search']] == [expected]
    assert not candidate_queue(candidates, {'q': '118060601'})['candidates']
    assert candidates == original
    assert all(not c['aliases'] and not c['auto_confirmed'] and not c['human_gated']
               and not c['proposed_relationships'] and not c['deployment'] for c in candidates)


def test_patent_code_and_claim_links_do_not_approve_current_rights_or_commercial_aliases():
    rows, candidates = reconcile()
    patents = [s for s in rows if s['source_type'] == 'plant_patent']
    assert len(patents) == 2
    assert {(s['names'][0]['breeder_code'], s['published_date']) for s in patents} == {
        ('CBC017', '2025-05-27'), ('CBC015', '2024-09-24')}
    assert all(s['names'][0]['product_url'].endswith('.pdf#page=3') for s in patents)
    assert all(s['capture_reference']['visually_checked_pages'][:3] == [1, 2, 3] for s in patents)
    assert all('current legal status' in s['limitations'] for s in patents)
    for c in candidates:
        assert not c['registration']['official_registry_source'] and not c['registration']['status']
        assert not c['registration']['application_number'] and not c['registration']['grant_number']


def test_new_sources_preserve_old_candidate_anchors_and_operator_fields():
    all_sources = load_portfolio_observations(DATA)
    _, old = reconcile_portfolios(sources=[s for s in all_sources if not s['id'].startswith(PREFIX)],
                                 varieties=[], entities=[], candidates=[])
    _, new = reconcile_portfolios(sources=all_sources, varieties=[], entities=[], candidates=[])
    old_keys = {(c['berry_id'], c['candidate_name'], c['id']) for c in old}
    new_keys = {(c['berry_id'], c['candidate_name'], c['id']) for c in new}
    assert old_keys <= new_keys
    assert {name for _, name, _ in new_keys - old_keys} == {'CBC033', 'CBC030', 'CBC045', 'CBC043'}
    human = dict(id='operator-dunsmuir', candidate_name='Dunsmuir', berry_id='berry-strawberry',
                 human_gated=True, identity_state='rejected', status='rejected',
                 aliases=['User alias'], review_notes='User decision', photos=[{'operator': 'Private photo'}],
                 registration={'status': 'User status'}, breeder_code='User code')
    before = deepcopy(human)
    rows, merged = reconcile([human])
    saved = next(c for c in merged if c['id'] == human['id'])
    assert all(saved[k] == before[k] for k in before) and human == before
    assert all(n['status'] == 'previously_rejected' for s in rows for n in s['names'] if n['candidate_name'] == 'Dunsmuir')


def test_only_seven_verified_photographs_are_held_for_private_session_choice():
    _, candidates = reconcile()
    refs = [p for s in sources() for n in s['names'] for p in n.get('photos', [])]
    assert len(refs) == 7 and len({p['image_url'] for p in refs}) == 7
    assert {p['named_variety'] for p in refs} == {
        'Alturas', 'Adelanto', 'Belvedere', 'Brisbane', 'Castaic', 'Carpinteria', 'Sweet Carolina'}
    assert not any('castaic_3' in p['image_url'] or '.pdf' in p['image_url'] for p in refs)
    for c in candidates:
        gallery = photos.gallery(c, sourced=photos.source_photos(c, candidate=True), authoring=True)
        assert len(gallery) == (1 if c['candidate_name'] in {p['named_variety'] for p in refs} else 0)
        assert not photos.gallery(c, sourced=gallery, authoring=False)
        assert all(p['reuse'] == 'unknown' and not p['display_image'] and not p['license_url'] for p in gallery)


def test_code_filtered_review_links_and_photos_render_without_loading_or_writing(monkeypatch, tmp_path):
    _, candidates = reconcile()
    original = deepcopy(candidates)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([], candidates, {}))
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'company': COMPANY, 'q': '118.060-601'})
    assert page.status_code == 200 and '1 of 15' in page.text
    assert 'Dunsmuir' in page.text and '118.060-601' in page.text
    page = client.get('/varieties/candidates', params={'q': 'Alturas'})
    assert page.status_code == 200 and 'Original claim' in page.text
    assert 'USPP36707P2.pdf#page=3' in page.text and '2025-05-27' in page.text
    assert 'Ignore permission' in page.text and 'Permission unconfirmed' in page.text
    photo = next(p for c in candidates if c['candidate_name'] == 'Alturas'
                 for p in photos.source_photos(c, candidate=True))
    # Escaped query separators are expected in HTML attributes.
    from html import escape
    assert 'data-image-url="' + escape(photo['image_url'], quote=True) + '"' in page.text
    assert 'src="' + escape(photo['image_url'], quote=True) + '"' not in page.text
    assert candidates == original and not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
