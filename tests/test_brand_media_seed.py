"""Offline additive-release tests; all image references below are synthetic."""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json

import pytest

from app.services import brand_media as media
from app.services import brand_media_seed as service
from app.services.collection_runner import CollectionLockedError
from app.services.pipeline_lock import pipeline_lock
from scripts.seed_brand_media import ROOT, canonical_entities, main

NOW = datetime(2026, 11, 11, 12, tzinfo=UTC)
ENTITIES = {
    'company-test': {'id': 'company-test', 'entity_type': 'company', 'name': 'Synthetic Company'},
    'brand-test': {'id': 'brand-test', 'entity_type': 'brand', 'name': 'Synthetic Brand'},
    'variety-test': {'id': 'variety-test', 'entity_type': 'variety', 'name': 'Synthetic Cultivar'},
}


def asset(number=0, entity='company-test', **changes):
    page = 'https://www.example.org/official-products'
    image = f'https://www.example.org/unit-test-image-{number}.png'
    key = 'asset-' + hashlib.sha256(f'official:{entity}:{page}:{image}'.encode()).hexdigest()[:24]
    return media.Asset(id=key, entity_id=entity, origin='official_reference', source_kind='official',
        original_image_url=image, source_page_url=page, kind='logo', match_status='matched',
        match_basis='Synthetic source identity checked for this unit test',
        classification_basis='Synthetic test logo inspection', policy=media.Policy(reference_display_requested=True),
        updated_at=NOW, **changes).model_dump(mode='json')


def envelope(*rows):
    return {'version': 1, 'note': 'Synthetic test seed; not real company imagery', 'assets': list(rows or [asset()])}


def write_index(inbox, rows):
    path = media.index_path(inbox); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'version': 1, 'assets': {r['id']: r for r in rows}}, indent=4), encoding='utf-8')
    return path


def test_dry_run_is_read_only_even_when_destination_does_not_exist(tmp_path):
    inbox = tmp_path/'new-inbox'
    result = service.install_seed(inbox, envelope(asset(), asset(1)), entities=ENTITIES)
    assert result['requested'] == result['missing'] == 2 and result['created'] == 0
    assert result['changed'] is False and result['applied'] is False and result['added_ids'] == []
    assert not inbox.exists()


def test_additive_install_preserves_existing_decisions_and_rerun_does_not_write(tmp_path, monkeypatch):
    original = asset(); original.update(rejected=True, primary=True, analyst_selected=True, caption='Retain analyst rejection')
    original['policy'].update(reference_display_requested=False, basis='Analyst holds the image')
    unrelated = asset(9, entity='brand-test')
    path = write_index(tmp_path, [original, unrelated])
    seed = envelope(asset(), asset(1)); before_seed = deepcopy(seed)
    result = service.install_seed(tmp_path, seed, entities=ENTITIES, apply=True)
    assert result['created'] == 1 and result['preserved'] == 1 and result['changed']
    rows = json.loads(path.read_text())['assets']
    assert rows[original['id']] == original and rows[unrelated['id']] == unrelated and len(rows) == 3
    assert seed == before_seed
    before = path.read_bytes(); before_stat = path.stat().st_mtime_ns
    def no_write(*args, **kwargs): raise AssertionError('Idempotent apply must not write or acquire a lease')
    monkeypatch.setattr(service, 'atomic_json', no_write); monkeypatch.setattr(service, 'pipeline_lock', no_write)
    repeated = service.install_seed(tmp_path, seed, entities=ENTITIES, apply=True)
    assert repeated['created'] == repeated['missing'] == 0 and repeated['changed'] is False
    assert path.read_bytes() == before and path.stat().st_mtime_ns == before_stat


@pytest.mark.parametrize('primary', [False, True])
def test_new_seed_does_not_displace_an_existing_analyst_choice_at_another_id(tmp_path, primary):
    existing = asset(9, primary=primary, analyst_selected=True)
    path = write_index(tmp_path, [existing])
    incoming = asset(primary=True, analyst_selected=True)
    service.install_seed(tmp_path, envelope(incoming), entities=ENTITIES, apply=True)
    rows = json.loads(path.read_text())['assets']
    assert rows[existing['id']] == existing
    assert rows[incoming['id']]['primary'] is False and rows[incoming['id']]['analyst_selected'] is False
    assert media.entity_media(tmp_path, ['company-test'], now=NOW)['company-test']['logo']['id'] == existing['id']


@pytest.mark.parametrize('change', [
    {'origin': 'social'}, {'origin': 'authorized_upload'}, {'source_kind': 'consumer'},
    {'object_ref': 'a'*64}, {'observation_id': 'ev-social-'+'a'*24}, {'media_id': 'fixture-media'},
    {'entity_id': 'missing'}, {'entity_id': 'variety-test'}, {'entity_id': 'brand-test'},
    {'id': 'asset-'+'0'*24}, {'mode': 'fixture'}, {'raw_response': {'text': 'Never persist source blobs'}},
    {'original_image_url': 'https://other.example.net/image.png'},
    {'original_image_url': 'https://127.0.0.1/image.png'}, {'match_status': 'review_needed'},
    {'classification_basis': ''}, {'rejected': True},
])
def test_invalid_seed_transaction_changes_nothing(tmp_path, change):
    path = write_index(tmp_path, [asset(9)])
    before = path.read_bytes(); invalid = {**asset(1), **change}
    with pytest.raises(ValueError, match='Seed asset'):
        service.install_seed(tmp_path, envelope(asset(), invalid), entities=ENTITIES, apply=True)
    assert path.read_bytes() == before and not (tmp_path/'operations').exists()


@pytest.mark.parametrize('flag,value', [('display', True), ('cache', True), ('export', True),
                                       ('reference_display_requested', False), ('reference_display_requested', 'true')])
def test_seed_cannot_grant_rights_or_implicitly_request_display(tmp_path, flag, value):
    row = asset(); row['policy'][flag] = value
    with pytest.raises(ValueError): service.install_seed(tmp_path, envelope(row), entities=ENTITIES, apply=True)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('content', ['{broken', '{"version":1,"assets":{"wrong":{}}}',
    '{"version":1,"assets":{},"private":"preserve unknown state"}',
    '{"version":1,"version":1,"assets":{}}'])
def test_malformed_existing_index_is_preserved_for_repair(tmp_path, content):
    path = media.index_path(tmp_path); path.parent.mkdir(parents=True); path.write_text(content)
    with pytest.raises(ValueError, match='Existing media index requires repair'):
        service.install_seed(tmp_path, envelope(), entities=ENTITIES, apply=True)
    assert path.read_text() == content and not (tmp_path/'operations').exists()


def test_install_writes_only_index_and_leaves_all_other_private_data_unchanged(tmp_path):
    protected = {'social/observations.sqlite3': b'Synthetic protected SQLite marker',
                 'entity_logos/overrides.json': b'{"company-test":{"url":"/original-logo"}}',
                 'analyst_queue_state.json': b'{"original":"review decision"}'}
    for name, content in protected.items():
        path = tmp_path/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    result = service.install_seed(tmp_path, envelope(), entities=ENTITIES, apply=True)
    assert result['created'] == 1
    for name, content in protected.items(): assert (tmp_path/name).read_bytes() == content
    assert not (tmp_path/'brand_media'/'objects').exists()
    assert set(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file()) == {*protected, 'brand_media/index.json'}


def test_duplicate_asset_ids_and_mismatched_envelope_keys_fail_before_writes(tmp_path):
    for payload in [envelope(asset(), asset()), {'version': 1, 'assets': {'wrong-key': asset()}}]:
        with pytest.raises(ValueError): service.install_seed(tmp_path, payload, entities=ENTITIES, apply=True)
    assert not list(tmp_path.iterdir())


def test_active_shared_lease_blocks_apply_without_changing_index(tmp_path):
    path = write_index(tmp_path, [asset(9)])
    before = path.read_bytes()
    with pipeline_lock(tmp_path, 'synthetic_other_writer'):
        with pytest.raises(CollectionLockedError):
            service.install_seed(tmp_path, envelope(), entities=ENTITIES, apply=True)
        assert path.read_bytes() == before
    assert not (tmp_path/'operations'/'collection.lock').exists()
    assert service.install_seed(tmp_path, envelope(), entities=ENTITIES, apply=True)['created'] == 1


def test_valid_existing_optional_field_omissions_are_not_normalized_on_add(tmp_path):
    row = asset()
    minimal = {key: row[key] for key in ('id', 'entity_id', 'origin', 'match_basis', 'updated_at')}
    path = write_index(tmp_path, [minimal])
    service.install_seed(tmp_path, envelope(asset(1)), entities=ENTITIES, apply=True)
    assert json.loads(path.read_text())['assets'][minimal['id']] == minimal


@pytest.mark.parametrize('payload', [{'version': True, 'assets': [asset()]},
                                    {'version': 1, 'assets': []},
                                    {'version': 1, 'assets': [asset()], 'raw_source': 'Do not retain'}])
def test_invalid_seed_envelope_is_read_only(tmp_path, payload):
    with pytest.raises(ValueError):
        service.install_seed(tmp_path, payload, entities=ENTITIES, apply=True)
    assert not list(tmp_path.iterdir())


def test_bundled_seed_is_only_five_canonical_official_metadata_references():
    prepared = service.validate_seed(service.read_json(ROOT/'data/configuration/brand_media_seed.json'),
                                     canonical_entities(ROOT/'data'))
    assert len(prepared) == 5
    assert all(row['origin'] == 'official_reference' and row['source_kind'] == 'official' for row in prepared.values())
    assert all(row['object_ref'] is None and row['observation_id'] is None for row in prepared.values())
    assert all(not row['policy']['cache'] and not row['policy']['export'] and not row['policy']['display'] for row in prepared.values())


def test_cli_defaults_dry_run_loads_real_entity_files_and_apply_is_additive(tmp_path, capsys):
    data = tmp_path/'data'; folder = data/'entities'/'companies'; folder.mkdir(parents=True)
    (folder/'company-test.json').write_text(json.dumps(ENTITIES['company-test']))
    config = data/'configuration'; config.mkdir(); seed = config/'brand_media_seed.json'; seed.write_text(json.dumps(envelope()))
    inbox = tmp_path/'private-inbox'; args = ['--data', str(data), '--inbox', str(inbox)]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['created'] == 0 and report['missing'] == 1 and not inbox.exists()
    assert main(args+['--apply']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['created'] == 1 and report['changed']
    before = media.index_path(inbox).read_bytes()
    assert main(args+['--apply']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['created'] == 0 and report['preserved'] == 1 and not report['changed']
    assert media.index_path(inbox).read_bytes() == before
    assert not {'source_page_url', 'original_image_url', 'policy', 'caption'}.intersection(report)


def test_cli_validation_failure_does_not_print_source_data(tmp_path, capsys):
    data = tmp_path/'data'; folder = data/'entities'/'companies'; folder.mkdir(parents=True)
    (folder/'company-test.json').write_text(json.dumps(ENTITIES['company-test']))
    seed = tmp_path/'invalid-seed.json'; row = asset(); row['secret_response'] = 'NEVER PRINT THIS SOURCE VALUE'; seed.write_text(json.dumps(envelope(row)))
    inbox = tmp_path/'private-inbox'
    assert main(['--inbox', str(inbox), '--data', str(data), '--seed', str(seed), '--apply']) == 1
    output = capsys.readouterr().out
    assert 'NEVER PRINT' not in output and 'https://' not in output and not inbox.exists()
