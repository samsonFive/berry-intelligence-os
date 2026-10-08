"""Brand families, failed catalogs and photo conflicts stay reviewable source context."""
from pathlib import Path
from fastapi.testclient import TestClient
from app import main
from app.services import variety_photos as photos
from app.services.variety_portfolio_coverage import load_portfolio_observations, reconcile_portfolios

DATA = Path(__file__).resolve().parents[1] / 'data'

def sources():
    # This fixture is the original nine-section batch, not all future checks
    # of these publishers (which legitimately add more sources).
    import json
    path = DATA / 'imports/variety-portfolio-observations-2026-10-07-psg-ozblu/observations.json'
    ids = {s['id'] for s in json.loads(path.read_text(encoding='utf-8'))['sources']}
    return [s for s in load_portfolio_observations(DATA) if s['id'] in ids]

def test_catalog_failure_is_a_gap_and_consumer_grades_are_not_cultivars():
    rows, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    assert len(rows) == 9 and sum(len(s['names']) for s in rows) == 9
    gaps = [s for s in rows if s['capture_status'] == 'unreadable']
    assert len(gaps) == 3 and all(not s['names'] and 'accounting' not in s for s in gaps)
    assert all('not a zero-variety' in s['limitations'] for s in gaps)
    consumer = next(s for s in rows if s['id'].endswith('consumer-product-panels'))
    assert not consumer['names'] and consumer['accounting_view']['accounted_items'] == 8
    magica = next(s for s in rows if s['id'].endswith('magica-2023-release'))
    assert magica['accounting_view']['accounted_items'] == 3
    assert {e['label'] for e in magica['accounting_view']['exclusions']} == {'Arana','Sekoya Pop'}
    assert all(not s['accounting_view']['issues'] for s in rows if s['capture_status'] == 'names_enumerated')
    assert not {c['candidate_name'] for c in candidates} & {'Rejoice','Jumbo','Standard','Arana','Sekoya Pop','BK6-13'}

def test_literal_codes_and_historical_brand_prefixes_do_not_silently_merge():
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    assert len(candidates) == 9
    named = {c['candidate_name']:c for c in candidates}
    assert named['PS-BK3-17.006-13']['id'] != named['BK3-17.006-13']['id']
    assert named['OZ Magica']['id'] != named['OZblu Magica']['id']
    assert all(not c['aliases'] and not c['auto_confirmed'] and not c['human_gated'] for c in candidates)
    assert all(not c['proposed_relationships'] and not c['deployment'] and not c['breeder_owner'] for c in candidates)
    assert all(not c['registration']['official_registry_source'] and not c['registration']['grant_number'] for c in candidates)
    assert named['OZ Magnifica']['source_tier'] == 'weak_noncanonical_lead'
    rejoice = next(s for s in sources() if s['id'].endswith('varietal-faq'))
    assert not rejoice['capture_reference']['sell_sheet_bodies_checked']
    assert 'BK6-13 in filenames is not a new code' in rejoice['limitations']

def test_conflicted_package_photo_is_withheld_and_named_photos_keep_unknown_reuse():
    _, candidates = reconcile_portfolios(sources=sources(), varieties=[], entities=[], candidates=[])
    coded = next(s for s in sources() if s['id'].endswith('eb12-19-caption'))
    assert coded['capture_reference']['photo_mismatch']['package_label'] == 'VARIETY: MAGNIFICA'
    eb = next(c for c in candidates if c['candidate_name'] == 'EB 12-19')
    assert not photos.source_photos(eb, candidate=True)
    held = [p for c in candidates for p in photos.source_photos(c, candidate=True)]
    assert len(held) == 2 and {p['named_variety'] for p in held} == {'BK3-17.006-13','OZblu Magica'}
    assert all(p['reuse'] == 'unknown' and not p['license_url'] for p in held)
    assert '%C2%AE' in next(p for p in held if p['named_variety'] == 'OZblu Magica')['image_url']
    for c in candidates:
        sourced = photos.source_photos(c,candidate=True)
        assert all(not p['display_image'] for p in photos.gallery(c,sourced=sourced,authoring=True))
        assert not photos.gallery(c,sourced=sourced,authoring=False)

def test_magica_profile_get_never_persists_decisions_or_loads_held_photo(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'INBOX_DIR',tmp_path)
    monkeypatch.setattr(main,'AUTHORING_MODE',True)
    client=TestClient(main.app)
    # OZblu Magica is an already-reviewed catalog alias; it belongs on that
    # profile rather than being recreated in the unresolved-candidate list.
    page=client.get('/entities/variety/variety-magica')
    image='https://www.ozblu.com/wp-content/uploads/2023/06/OZblu%C2%AE-Continues-its-Winning-Streak-with-Magica-1024x683.jpg'
    assert page.status_code == 200 and 'Ignore permission' in page.text
    assert f'data-image-url="{image}"' in page.text and f'src="{image}"' not in page.text
    assert 'OZblu article' in page.text and 'Permission unconfirmed' in page.text
    assert not list(tmp_path.rglob('*.json'))
    monkeypatch.setattr(main,'AUTHORING_MODE',False)
    public=client.get('/entities/variety/variety-magica')
    assert image not in public.text and 'Ignore permission' not in public.text
