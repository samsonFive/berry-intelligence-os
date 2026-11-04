"""Old catalog URLs must not bypass the current confirmation/revision workflow."""
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.repositories.json.entities import EntityRepository
from app.services import variety_catalog as catalog

SCHEMAS = Path(__file__).resolve().parents[1] / 'schemas'
RECORD = {'id': 'variety-removal-example', 'record_type': 'entity', 'entity_type': 'variety',
          'name': 'Example variety', 'status': 'active', 'berry_ids': ['berry-blueberry'],
          'aliases': [], 'description': 'Keep the editor text', 'evidence_ids': [], 'fact_ids': [],
          'relationship_ids': [], 'attributes': {'operator_note': 'Keep this note'}}


@pytest.fixture
def removal_runtime(tmp_path, monkeypatch):
    data, inbox = tmp_path / 'data', tmp_path / 'inbox'
    repository = EntityRepository(data, SCHEMAS)
    repository.create(deepcopy(RECORD))
    monkeypatch.setattr(main, 'DATA_DIR', data)
    monkeypatch.setattr(main, 'INBOX_DIR', inbox)
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    monkeypatch.setattr(main, 'all_relationships', lambda: [])
    monkeypatch.setattr(main, 'review_username', lambda: 'Fixture reviewer')
    return TestClient(main.app), repository, data, inbox


def test_old_remove_submission_opens_confirmation_without_changing_the_record(removal_runtime):
    client, repository, _, inbox = removal_runtime
    before = repository.get(RECORD['id'])
    response = client.post('/varieties/' + RECORD['id'] + '/catalog-status',
                           data={'action': 'remove'}, follow_redirects=False)
    assert response.status_code == 303
    assert repository.get(RECORD['id']) == before
    assert not catalog.history(inbox, RECORD['id'])
    assert response.headers['location'] == '/varieties/catalog/' + RECORD['id'] + '/edit#catalog-removal'


def test_old_restore_submission_cannot_bypass_a_newer_editor_revision(removal_runtime):
    client, repository, data, inbox = removal_runtime
    removed = catalog.remove_or_restore(inbox, data, SCHEMAS, RECORD['id'],
        expected=catalog.revision(RECORD), actor='Fixture reviewer', confirmation=RECORD['name'])
    updated = deepcopy(removed)
    updated['description'] = 'A different editor changed this after the page was opened'
    repository.update(updated['id'], updated)
    response = client.post('/varieties/' + RECORD['id'] + '/catalog-status',
        data={'action': 'restore', 'revision': catalog.revision(removed)}, follow_redirects=False)
    assert response.status_code == 303
    assert repository.get(RECORD['id']) == updated
    assert len(catalog.history(inbox, RECORD['id'])) == 1
    assert response.headers['location'] == '/varieties/catalog/' + RECORD['id'] + '/edit#catalog-restore'


def test_old_removed_bookmark_resolves_to_one_current_removed_list(removal_runtime):
    client, _, _, _ = removal_runtime
    response = client.get('/varieties/removed', follow_redirects=False)
    assert response.status_code in {302, 303, 307, 308}
    assert response.headers['location'] == '/varieties/catalog/removed'
    assert client.get(response.headers['location']).status_code == 200


def test_current_remove_and_restore_still_require_latest_revision_and_confirmation(removal_runtime):
    client, repository, _, _ = removal_runtime
    remove = '/varieties/catalog/' + RECORD['id'] + '/remove'
    revision = catalog.revision(repository.get(RECORD['id']))
    assert client.post(remove, data={'revision': revision}, follow_redirects=False).status_code == 409
    assert repository.get(RECORD['id']) == RECORD
    updated = deepcopy(RECORD)
    updated['description'] = 'Latest editor text'
    repository.update(updated['id'], updated)
    assert client.post(remove, data={'revision': revision, 'confirmation': RECORD['name']},
                       follow_redirects=False).status_code == 409
    assert repository.get(RECORD['id']) == updated
    assert client.post(remove, data={'revision': catalog.revision(updated), 'confirmation': RECORD['name']},
                       follow_redirects=False).status_code == 303
    removed = repository.get(RECORD['id'])
    assert removed['attributes']['catalog_removed']
    assert client.post('/varieties/catalog/' + RECORD['id'] + '/restore',
        data={'revision': catalog.revision(removed)}, follow_redirects=False).status_code == 303
    restored = repository.get(RECORD['id'])
    assert restored['description'] == updated['description'] and restored['attributes']['operator_note'] == 'Keep this note'
    assert not restored['attributes'].get('catalog_removed') and restored['status'] == RECORD['status']


def test_profile_links_to_confirmation_instead_of_the_legacy_write(removal_runtime):
    client, _, _, _ = removal_runtime
    response = client.get('/entities/variety/' + RECORD['id'])
    assert response.status_code == 200
    assert '/varieties/catalog/' + RECORD['id'] + '/edit#catalog-removal' in response.text
    assert 'action="/varieties/' + RECORD['id'] + '/catalog-status"' not in response.text


def test_legacy_links_retain_cross_origin_and_readonly_guards(removal_runtime, monkeypatch):
    client, repository, _, inbox = removal_runtime
    url = '/varieties/' + RECORD['id'] + '/catalog-status'
    assert client.post(url, data={'action': 'remove'}, headers={'Origin': 'https://other.example'}).status_code == 403
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    assert client.post(url, data={'action': 'remove'}, follow_redirects=False).status_code == 403
    assert client.get('/varieties/removed', follow_redirects=False).status_code == 403
    assert repository.get(RECORD['id']) == RECORD and not catalog.history(inbox, RECORD['id'])


def test_legacy_bad_actions_and_unknown_records_still_fail_visibly(removal_runtime):
    client, repository, _, inbox = removal_runtime
    assert client.post('/varieties/' + RECORD['id'] + '/catalog-status',
                       data={'action': 'erase'}, follow_redirects=False).status_code == 422
    assert client.post('/varieties/variety-missing/catalog-status',
                       data={'action': 'remove'}, follow_redirects=False).status_code == 404
    assert repository.get(RECORD['id']) == RECORD and not catalog.history(inbox, RECORD['id'])
