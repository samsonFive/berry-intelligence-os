"""Current named product photos preserve historical identities and permission gates."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios
from app.services.variety_universe.identity import fold_identity

DATA = Path(__file__).resolve().parents[1] / 'data'
IDS = {'portfolio-abz-' + str(i) for i in range(1, 10)}
OLD = DATA / 'imports/variety-portfolio-observations-2026-10-07-programs/observations.json'


def captures():
    old = [s for s in json.loads(OLD.read_text(encoding='utf-8'))['sources'] if s['id'] in IDS]
    current = load_portfolio_observations(DATA)
    return old, current, [s for s in current if s['id'] in IDS]


def test_historical_photo_capture_retains_all_names_and_unrecovered_booklet_without_fake_dates():
    old, current, refreshed = captures()
    # This checks the retained November 1 HTML/photo capture. Later document
    # checks may supersede its current projection without rewriting its proof.
    refreshed = json.loads((DATA / 'imports/variety-portfolio-observations-2026-11-01-abz-current-photos/observations.json').read_text(encoding='utf-8'))['sources']
    assert len(refreshed) == 9 and sum(len(s['names']) for s in refreshed) == 21
    assert {s['id'] for s in refreshed} == {s['id'] for s in old} == IDS
    for prior in old:
        newer = next(s for s in refreshed if s['id'] == prior['id'])
        assert {fold_identity(n['candidate_name']) for n in newer['names']} == {
            fold_identity(n['candidate_name']) for n in prior['names']}
        assert prior['checked_on'] == '2026-10-07' and newer['checked_on'] == '2026-11-01'
        assert not newer.get('published_date') and newer['review_state'] == 'unreviewed'
        assert newer['url'].endswith('?hsLang=en')
        assert newer['capture_reference']['body_language'] == 'English'
        assert newer['capture_reference']['previous_capture']['names'] == [n['candidate_name'] for n in prior['names']]
        assert all(not item['bodies_checked'] for item in newer['capture_reference']['infosheet_destinations'])
    book = next(s for s in current if s['id'] == 'portfolio-abz-booklet')
    assert book['capture_status'] == 'unreadable' and not book['names']
    assert sum(len(s['capture_reference']['infosheet_destinations']) for s in refreshed) == 18


def test_selected_photos_are_specific_attributed_and_held_with_conflicting_milan_photo_excluded():
    _, _, sources = captures()
    rows, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=[])
    assert len(candidates) == 21 and all(not r['accounting_view']['issues'] for r in rows)
    photos = [p for c in candidates for p in variety_photos.source_photos(c, candidate=True)]
    assert len(photos) == 21 and len({p['image_url'] for p in photos}) == 21
    assert all(p['reuse'] == 'unknown' and not p['license_url'] and p['credit'].startswith('ABZ Seeds') for p in photos)
    assert all('Rectangle%201.png' not in p['image_url'] and 'Elan_1_Vrij.png' not in p['image_url'] for p in photos)
    for candidate in candidates:
        sourced = variety_photos.source_photos(candidate, candidate=True)
        assert len(sourced) == 1
        assert not variety_photos.gallery(candidate, sourced=sourced, authoring=True)[0]['display_image']
        assert not variety_photos.gallery(candidate, sourced=sourced, authoring=False)
        assert not candidate['human_gated'] and not candidate['auto_confirmed'] and not candidate['aliases']
        assert not candidate['proposed_relationships'] and not candidate['deployment'] and not candidate['breeder_owner']
    milan = next(c for c in candidates if c['candidate_name'] == 'Milan F1')
    elan = next(c for c in candidates if c['candidate_name'] == 'Elan F1')
    assert any('Elan_1_Vrij.png' in w for w in milan['portfolio_review_warnings'])
    assert not any('Elan_1_Vrij.png' in w for w in elan['portfolio_review_warnings'])
    assert 'ABZ%20Milan%20010%20S.jpg' in variety_photos.source_photos(milan, candidate=True)[0]['image_url']


def test_all_saved_keys_rejections_names_user_notes_and_photo_choices_survive_replay():
    old, sources, _ = captures()
    prior_sources = {s['id']: s for s in old}
    baseline = [prior_sources.get(s['id'], s) for s in sources]
    _, saved = reconcile_portfolios(sources=baseline, varieties=[], entities=[], candidates=[])
    delizz = next(c for c in saved if c['candidate_name'] == 'Delizz F1')
    delizz.update(human_gated=True, status='rejected', identity_state='rejected',
        review_notes='Keep my decision', knowledge={'notes': 'Operator research'},
        aliases=['Operator spelling'], photos=[{'operator': 'Keep my chosen photo'}])
    original = deepcopy((sources, saved))
    rows, after = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=saved)
    assert {c['id'] for c in after} == {c['id'] for c in saved} and len(after) == len(saved)
    indexed = {c['id']: c for c in after}
    for prior in saved:
        for key, value in prior.items():
            if key not in {'portfolio_sources', 'portfolio_review_warnings', 'portfolio_identity_notes'}:
                assert indexed[prior['id']][key] == value
    assert indexed[delizz['id']]['candidate_name'] == 'Delizz F1'
    selected = next(n for s in rows if s['id'] == 'portfolio-abz-4' for n in s['names'] if n['candidate_name'] == 'Delizz® F1')
    assert selected['candidate_id'] == delizz['id'] and selected['status'] == 'previously_rejected'
    again_rows, again = reconcile_portfolios(sources=sources, varieties=[], entities=[], candidates=after)
    assert again_rows == rows and again == after and (sources, saved) == original


def test_private_routes_offer_explicit_session_preview_without_auto_images_or_get_writes(monkeypatch, tmp_path):
    protected = {p: p.read_bytes() for folder in ['entities', 'facts', 'evidence', 'relationships']
                 for p in (DATA / folder).rglob('*.json')}
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    for name, source in [('Soraya F1', 'portfolio-abz-1'), ('Milan F1', 'portfolio-abz-5')]:
        response = client.get('/varieties/candidates', params={'source': source, 'q': name})
        assert response.status_code == 200 and len(response.context['candidates']) == 1
        row = response.context['candidates'][0]
        photo = variety_photos.source_photos(row, candidate=True)[0]
        assert 'Ignore permission' in response.text and 'Permission unconfirmed' in response.text
        assert 'data-image-url="' + photo['image_url'] + '"' in response.text
        assert 'src="' + photo['image_url'] + '"' not in response.text
        assert 'ABZ Seeds' in response.text
    source = client.get('/varieties/coverage/source/portfolio-abz-5')
    assert source.status_code == 200 and 'Elan_1_Vrij.png' in source.text
    company = client.get('/entities/company/company-abz-seeds', params={'tab': 'varieties'})
    assert company.status_code == 200 and 'Milan F1' in company.text and 'Soraya F1' in company.text
    assert not list(tmp_path.rglob('*.json'))
    assert all(path.read_bytes() == value for path, value in protected.items())
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.get('/varieties/candidates').status_code == 403
    assert client.get('/varieties/coverage/source/portfolio-abz-5').status_code == 403
