"""Reading a profile stays fast; name review retains its current human gates."""
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from app import main


@pytest.fixture
def profile(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    entity = {'id': 'variety-review-fixture', 'record_type': 'entity',
              'entity_type': 'variety', 'name': 'Fixture Fruit',
              'status': 'active', 'berry_ids': ['berry-blueberry'], 'aliases': []}
    main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).entities.create(entity)
    return TestClient(main.app), entity


def candidate(name, state='possible_alias', **overrides):
    return {'id': 'vcand-' + name.lower().replace(' ', '-'), 'candidate_name': name,
            'identity_state': state, 'identity_label': state,
            'candidate_canonical_match': 'variety-review-fixture',
            'status': 'reviewed' if state == 'confirmed_same' else 'proposed',
            'human_gated': state in {'confirmed_same', 'distinct'}, **overrides}


def test_initial_profile_does_not_run_the_global_name_audit(profile, monkeypatch):
    client, entity = profile
    def forbidden():
        raise AssertionError('Collapsed name section blocked the profile on a global audit')
    monkeypatch.setattr(main, 'variety_candidate_universe', forbidden)
    for suffix in ('', '?view=legacy'):
        response = client.get('/entities/variety/' + entity['id'] + suffix)
        assert response.status_code == 200 and 'Fixture Fruit' in response.text
        assert 'Recent intelligence' in response.text or suffix
        if not suffix:
            assert 'data-variety-name-review' in response.text
            assert 'Name matches are checked when you open this section.' in response.text
            assert '?review_names=1#identity-issues' in response.text
            assert 'No matching name entries' not in response.text


def test_requested_names_keep_matching_and_saved_review_states(profile, monkeypatch):
    client, entity = profile
    rows = [candidate('Possible name'), candidate('Uncertain name', 'unknown'),
            candidate('Confirmed name', 'confirmed_same'),
            candidate('Distinct name', 'distinct'), candidate('Rejected name', status='rejected'),
            candidate('Other variety', candidate_canonical_match='variety-other')]
    before = deepcopy(rows)
    calls = []
    def universe():
        calls.append(True)
        return [entity], rows, {}
    monkeypatch.setattr(main, 'variety_candidate_universe', universe)
    response = client.get('/api/varieties/' + entity['id'] + '/name-review')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    assert '3 name entries' in response.text
    assert all(name in response.text for name in ['Possible name', 'Uncertain name', 'Confirmed name'])
    assert all(name not in response.text for name in ['Distinct name', 'Rejected name', 'Other variety'])
    assert calls == [True] and rows == before
    assert not list(main.INBOX_DIR.rglob('*.json'))


def test_full_page_fallback_is_open_and_preserves_the_same_findings(profile, monkeypatch):
    client, entity = profile
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([entity], [candidate('Possible name')], {}))
    response = client.get('/entities/variety/' + entity['id'] + '?review_names=1')
    assert response.status_code == 200 and 'Possible name' in response.text
    assert '<details class="variety-section" open>' in response.text
    assert 'data-variety-name-review' not in response.text


def test_each_requested_refresh_sees_current_review_changes(profile, monkeypatch):
    client, entity = profile
    rows = [candidate('Possible name')]
    monkeypatch.setattr(main, 'variety_candidate_universe', lambda: ([entity], rows, {}))
    path = '/api/varieties/' + entity['id'] + '/name-review'
    assert 'Possible name' in client.get(path).text
    rows[0].update(identity_state='distinct', human_gated=True)
    response = client.get(path)
    assert 'Possible name' not in response.text and 'No matching name entries' in response.text
    rows.append(candidate('<script>name</script>', 'unknown'))
    response = client.get(path)
    assert '&lt;script&gt;name&lt;/script&gt;' in response.text
    assert '<script>name</script>' not in response.text


def test_name_review_never_enters_the_public_profile_or_public_api(profile, monkeypatch):
    client, entity = profile
    monkeypatch.setattr(main, 'AUTHORING_MODE', False)
    def forbidden():
        raise AssertionError('Public request hydrated private candidate names')
    monkeypatch.setattr(main, 'variety_candidate_universe', forbidden)
    response = client.get('/entities/variety/' + entity['id'] + '?review_names=1')
    assert response.status_code == 200 and 'Names needing review' not in response.text
    assert 'data-variety-name-review' not in response.text
    assert client.get('/api/varieties/' + entity['id'] + '/name-review').status_code == 404


def test_missing_entity_does_not_trigger_a_global_audit(profile, monkeypatch):
    client, _ = profile
    def forbidden():
        raise AssertionError('Missing entity started a name audit')
    monkeypatch.setattr(main, 'variety_candidate_universe', forbidden)
    assert client.get('/api/varieties/variety-missing/name-review').status_code == 404


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is unavailable')
def test_browser_loader_contract_without_network():
    result = subprocess.run(
        [shutil.which('node'), 'tests/variety_name_review_checks.js'],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
