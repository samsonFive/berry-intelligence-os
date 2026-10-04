"""Statistics use persistent configuration rather than repository-only paths."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.global_explorer import IntelligenceQuery, snapshot_model
from app.services.map_workspace import statistics
from app.services.market_statistics_reference import reference_groups

ENTITIES = {'geography-portugal':{'id':'geography-portugal','name':'Portugal','entity_type':'geography'}}


def store(data_dir):
    baseline = reference_groups(Path(__file__).resolve().parents[1] / 'data')
    group = deepcopy(next(group for group in baseline if group['country_id'] == 'geography-portugal'))
    group['metrics'][0]['value'] = 1.23
    path = data_dir / 'configuration/market_statistics_reference.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'version':1,'groups':[group]}), encoding='utf-8')
    return path


def test_persistent_runtime_override_is_shared_by_map_snapshot_and_review(tmp_path, monkeypatch):
    runtime = tmp_path / 'runtime'
    file = store(runtime / 'data')
    before = file.read_bytes()
    monkeypatch.setenv('BIOS_RUNTIME_DIR', str(runtime))
    monkeypatch.delenv('BIOS_DATA_DIR', raising=False)
    monkeypatch.setattr(main, 'DATA_DIR', runtime / 'data')
    monkeypatch.setattr(main, 'INBOX_DIR', runtime / 'inbox')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    query = IntelligenceQuery(('geography-portugal',), berry_ids=('berry-strawberry',))
    assert statistics(query, ENTITIES, [])['groups'][0]['metrics'][0]['value'] == 1.23
    assert snapshot_model(query, [], ENTITIES, [], {'berry-strawberry':'Strawberry'}, ['statistics'])['statistics']['groups'][0]['metrics'][0]['value'] == 1.23
    response = TestClient(main.app).get('/explorer/statistics')
    assert response.status_code == 200 and not (runtime / 'inbox').exists()
    assert file.read_bytes() == before


def test_explicit_data_dir_wins_over_runtime_without_overwriting_operator_file(tmp_path, monkeypatch):
    explicit = tmp_path / 'explicit-data'
    file = store(explicit)
    before = file.read_bytes()
    monkeypatch.setenv('BIOS_RUNTIME_DIR', str(tmp_path / 'other-runtime'))
    monkeypatch.setenv('BIOS_DATA_DIR', str(explicit))
    assert reference_groups()[0]['metrics'][0]['value'] == 1.23 and file.read_bytes() == before
    assert not (tmp_path / 'other-runtime').exists()


def test_missing_runtime_references_stay_unknown_without_repo_fallback_or_write(tmp_path, monkeypatch):
    monkeypatch.setenv('BIOS_DATA_DIR', str(tmp_path / 'missing'))
    assert reference_groups() == []
    query = IntelligenceQuery(('geography-portugal',), berry_ids=('berry-strawberry',))
    result = statistics(query, ENTITIES, [])
    assert result['groups'] == [] and 'no production reference recorded' in result['gaps'][0]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('content', ['{broken', '[]', '{"version":1,"groups":{}}', '{"version":1,"groups":[17]}'])
def test_damaged_config_is_not_replaced_by_shipped_figures_or_new_review_state(tmp_path, monkeypatch, content):
    file = store(tmp_path / 'data')
    file.write_text(content, encoding='utf-8')
    monkeypatch.setenv('BIOS_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr(main, 'DATA_DIR', tmp_path / 'data')
    monkeypatch.setattr(main, 'INBOX_DIR', tmp_path / 'inbox')
    monkeypatch.setattr(main, 'AUTHORING_MODE', True)
    client = TestClient(main.app)
    with pytest.raises(ValueError, match='Market references cannot'):
        reference_groups()
    assert client.get('/explorer/statistics').status_code == 409
    assert client.post('/explorer/statistics/check', data={'token':'explicit-check-token'}).status_code == 409
    assert not (tmp_path / 'inbox').exists() and file.read_text(encoding='utf-8') == content


@pytest.mark.parametrize('change', ['unsafe_url','blank_unit','nan','bool','negative'])
def test_malformed_reference_cells_remain_preserved_for_repair(tmp_path, change):
    file = store(tmp_path / 'data')
    document = json.loads(file.read_text(encoding='utf-8'))
    group = document['groups'][0]
    if change == 'unsafe_url': group['source_url'] = 'http://localhost./private'
    if change == 'blank_unit': group['metrics'][0]['unit'] = ''
    if change == 'nan': group['metrics'][0]['value'] = float('nan')
    if change == 'bool': group['metrics'][0]['value'] = True
    if change == 'negative': group['metrics'][0]['value'] = -1
    file.write_text(json.dumps(document), encoding='utf-8')
    before = file.read_bytes()
    with pytest.raises(ValueError, match='Market references cannot'):
        reference_groups(tmp_path / 'data')
    assert file.read_bytes() == before
