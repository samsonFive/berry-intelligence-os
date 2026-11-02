"""Fictional seed scenarios belong in explicit test fixtures, never live data."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

SEED_IDS = {
    'variety-example-blue', 'variety-example-red', 'company-example-genetics',
    'company-example-nursery', 'retailer-example-market', 'ev-sample-variety-launch',
    'ev-sample-patent-published', 'ev-sample-retail-placement',
}


def test_live_catalog_has_no_seed_records_or_dangling_seed_links():
    for path in Path('data').rglob('*.json'):
        if 'imports' in path.parts:
            continue
        text = path.read_text(encoding='utf-8')
        assert not any(key in text for key in SEED_IDS), path
    notes = json.loads(Path('data/imports/variety-profile-source-details-2026-10-27/observations.json').read_text(encoding='utf-8'))
    assert len(notes['profiles']) == 31
    assert not any(n['variety_id'] in SEED_IDS for n in notes['profiles'])


def test_scrubbed_profiles_are_absent_and_real_profile_still_works(monkeypatch):
    from app import main
    monkeypatch.setattr(main, 'DATA_DIR', Path('data').resolve())
    client = TestClient(main.app)
    for key in ('variety-example-blue', 'variety-example-red'):
        assert client.get('/entities/variety/' + key).status_code == 404
    results = client.get('/api/search', params={'q': 'example blue'}).json()
    assert not any(e['id'] in SEED_IDS for e in results['entities'])
    assert client.get('/entities/variety/variety-melissa').status_code == 200
