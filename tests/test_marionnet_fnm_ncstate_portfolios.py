"""Source conflicts, mixed crop labels and recommendation scope stay untrusted."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'
PREFIXES = ('portfolio-marionnet-', 'portfolio-fnm-', 'portfolio-ncstate-')


def sources():
    return [row for row in load_portfolio_observations(DATA) if row['id'].startswith(PREFIXES)]


def test_unresolved_marvella_codes_and_image_labels_are_not_silently_selected():
    observed = sources()
    strawberry = next(row for row in observed if row['id'] == 'portfolio-marionnet-strawberry-cards')
    assert strawberry['capture_status'] == 'partial'
    marvella = next(row for row in strawberry['names'] if row['candidate_name'] == 'Marvella')
    assert not marvella.get('breeder_code') and not marvella.get('denomination') and not marvella.get('photos')
    assert 'MAR118' in marvella['portfolio_context'] and 'MAR109' in marvella['portfolio_context']
    marly = next(row for row in strawberry['names'] if row.get('trade_name') == 'Marly')
    assert marly['breeder_code'] == 'MAR 109' and not marly.get('photos')
    rows, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    projected = next(row for row in rows if row['id'] == strawberry['id'])
    assert projected['needs_follow_up'] and not projected['accounting_view']['issues']
    assert {'Marvella', 'MAR 109'} <= {row['candidate_name'] for row in candidates}
    assert all(not row['aliases'] for row in candidates)


def test_repeated_cards_and_shared_pink_star_family_do_not_create_extra_varieties():
    observed = sources()
    rows, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    rasp = next(row for row in rows if row['id'] == 'portfolio-marionnet-raspberry-cards')
    assert len(rasp['names']) == 10 and rasp['accounting_view']['accounted_items'] == 10
    coded = {row['candidate_name']: row for row in candidates if row['candidate_name'] in {'MAR502', 'MAR506'}}
    assert len(coded) == 2 and coded['MAR502']['id'] != coded['MAR506']['id']
    assert coded['MAR502']['trade_name'] == 'Gaïa' and coded['MAR506']['trade_name'] == 'Pandora'
    assert not any(row['candidate_name'] == 'Pink Star' for row in candidates)
    for code, candidate in coded.items():
        held = photos.source_photos(candidate, candidate=True)
        assert len(held) == 1 and held[0]['named_variety'] == code


def test_fnm_index_body_includes_menu_omissions_and_keeps_raspberry_scope_and_redirect():
    observed = sources()
    index = next(row for row in observed if row['id'] == 'portfolio-fnm-current-variety-index')
    names = {row['candidate_name']: row for row in index['names']}
    assert {'Divine', 'Duna', 'Ondina'} <= names.keys()
    assert len(names) == 9 and names['Noelia']['berry_id'] == 'berry-raspberry'
    assert all(row['berry_id'] == 'berry-strawberry' for label, row in names.items() if label != 'Noelia')
    assert names['Marisma FNM']['product_url'] == 'https://www.fresasnm.com/marisma/'
    assert names['Noelia']['product_url'] == 'https://www.fresasnm.com/noelia'
    assert index['capture_reference']['redirects'][0]['resolved_url'] == 'https://www.fresasnm.com/marisma-fnm/'
    rows, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    projected = next(row for row in rows if row['id'] == index['id'])
    assert projected['accounting_view']['accounted_items'] == 10 and not projected['accounting_view']['issues']
    assert projected['accounting_view']['exclusions'][0]['label'] == 'Otras variedades'
    assert not any(row['candidate_name'] == 'Otras variedades' for row in candidates)
    candy = next(row for row in candidates if row['candidate_name'] == 'Candy')
    divine = next(row for row in candidates if row['candidate_name'] == 'Divine')
    assert 'shareholder' in candy['portfolio_sources'][0]['portfolio_context']
    assert any('licensed' in row['portfolio_context'] for row in divine['portfolio_sources'])
    assert not divine['breeder_owner'] and not divine['proposed_relationships']


def test_ncstate_recommendations_are_not_breeding_records_or_current_footprints():
    observed = sources()
    home = next(row for row in observed if row['id'] == 'portfolio-ncstate-home-garden-table')
    assert home['published_date'] == '2024-03-21' and home['source_type'] == 'extension_recommendation'
    assert len(home['names']) == 8 and all('recommendation' in row['portfolio_context'] for row in home['names'])
    assert {'Sweet-Ark™ Caddo', 'Sweet-Ark™ Ponca'} <= {row['candidate_name'] for row in home['names']}
    ervin = next(row for row in observed if row['id'] == 'portfolio-ncstate-ervin-coded-release')
    assert ervin['published_date'] == '2026-02-08' and ervin['capture_reference']['article_updated_date'] == '2026-04-05'
    coded = next(row for row in ervin['names'] if row.get('trade_name') == 'Ervin')
    assert coded['candidate_name'] == coded['breeder_code'] == 'NC 740'
    rows, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    natchez = next(row for row in candidates if row['candidate_name'] == 'Natchez')
    assert natchez['source_tier'] == 'weak_noncanonical_lead' and not natchez['breeder_owner']
    assert sum(len(row['names']) for row in rows) == 45 and len(candidates) == 34
    assert all(not row['deployment'] and not row['proposed_relationships'] for row in candidates)
    assert all(not row['human_gated'] and not row['auto_confirmed'] for row in candidates)
    assert all(not row['registration']['official_registry_source'] and not row['registration']['grant_number'] for row in candidates)


def test_replay_preserves_analyst_rejection_notes_and_user_photo_edits():
    human = {'id': 'human-mar502', 'candidate_name': 'MAR502', 'berry_id': 'berry-raspberry',
             'status': 'rejected', 'identity_state': 'rejected', 'human_gated': True,
             'reviewer': 'Analyst', 'review_notes': 'Keep separate; do not reapprove',
             'knowledge': {'notes': 'User edit'}, 'photos': [{'user_edit': 'retained'}]}
    original = deepcopy(human)
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[human])
    saved = next(row for row in candidates if row['id'] == human['id'])
    for key in ('status', 'identity_state', 'human_gated', 'reviewer', 'review_notes', 'knowledge', 'photos'):
        assert saved[key] == original[key]
    assert human == original and saved['portfolio_sources']


def test_new_photos_are_held_per_asset_and_readonly_get_never_writes(monkeypatch, tmp_path):
    observed = sources()
    _, candidates = reconcile_portfolios(sources=observed, varieties=[], entities=[], candidates=[])
    held = [photo for candidate in candidates for photo in photos.source_photos(candidate, candidate=True)]
    assert len(held) == 6 and all(row['reuse'] == 'unknown' and not row['license_url'] for row in held)
    assert {row['named_variety'] for row in held} == {'Mariguette', 'MAR502', 'MAR506', 'Marisma FNM', 'Von', 'NC 740'}
    assert all('Photographer not credited' in row['credit'] for row in held)
    for candidate in candidates:
        assert not photos.gallery(candidate, sourced=photos.source_photos(candidate, candidate=True), authoring=False)
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    page = client.get('/varieties/candidates', params={'source': 'portfolio-marionnet-raspberry-cards', 'berry': 'berry-raspberry', 'q': 'MAR502'})
    assert page.status_code == 200 and 'Ignore permission' in page.text and 'Permission unconfirmed' in page.text
    image = next(row['image_url'] for row in held if row['named_variety'] == 'MAR502')
    assert 'data-image-url="' + image + '"' in page.text and 'src="' + image + '"' not in page.text
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    public = client.get('/varieties/candidates', params={'q': 'MAR502'})
    assert image not in public.text and 'Ignore permission' not in public.text
    assert not list(tmp_path.rglob('*.json'))
