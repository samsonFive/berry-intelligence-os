from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import pytest

from app.services.storage_recovery import (
    StorageRecoveryError, _previous, _read, _safe,
    build_protection_manifest, collect_recovery_manifest,
)


def image(letter):
    return 'sha256:' + letter * 64


def encoded(value):
    return (json.dumps(value, sort_keys=True) + '\n').encode()


def evidence(root='/srv/fictional'):
    backup_root = root + '/backups'
    ledgers = {}
    for role, letter, older in [('current', 'a', 'b'), ('previous', 'b', 'c')]:
        stage = root + '/releases/' + role
        ledgers[role] = {'source_sha': letter * 40, 'image': image(letter), 'previous_image': image(older),
                         'stage': stage, 'backup': backup_root + '/' + role + '/berry-runtime-20261101T000000Z.tar.gz',
                         'compose_override': stage + '/candidate.json', 'rollback_override': stage + '/rollback.json',
                         'receipt': stage + '/receipt.json'}
    mounts = [
        {'Type': 'bind', 'Source': root + '/runtime/data', 'Destination': '/app/runtime/data', 'RW': True},
        {'Type': 'bind', 'Source': root + '/runtime/inbox', 'Destination': '/app/runtime/inbox', 'RW': True},
        {'Type': 'bind', 'Source': root + '/gene-source', 'Destination': '/app/gene-delivery-source', 'RW': False},
        {'Type': 'bind', 'Source': backup_root, 'Destination': '/app/backups', 'RW': True},
        {'Type': 'bind', 'Source': root + '/runtime/data/config.json', 'Destination': '/app/seed/config.json', 'RW': False},
    ]
    baseline = {'ordered_compose_files': [root + '/deploy/base.yml'],
                'compose_argv': ['docker', 'compose', '--env-file', root + '/deploy/.env'],
                'mounts': mounts, 'node_image': image('d'), 'node_component_source': 'd' * 40,
                'environment': {'TOKEN': '/do-not-emit-secret'}}
    app = {'Id': 'a' * 64, 'Image': image('a'),
           'Config': {'Env': ['TOKEN=do-not-emit-secret'], 'Labels': {
               'org.opencontainers.image.revision': 'a' * 40,
               'com.docker.compose.project.config_files': root + '/deploy/base.yml,' + root + '/old-release/override.json',
               'com.docker.compose.project.environment_file': root + '/deploy/.env',
           }}, 'Mounts': mounts, 'State': {'Running': True, 'Health': {'Status': 'healthy'}},
           '_storage_recovery_sidecar': {'container_id': 'd' * 64, 'image': image('d'), 'healthy': True,
                                          'network_mode': 'container:' + 'a' * 64}}
    proofs = {role: {'path': row['backup'], 'size': 100, 'sha256': letter * 64, 'verified': True}
              for (role, row), letter in zip(ledgers.items(), ['a', 'b'])}
    return {'ledger_bytes': encoded(ledgers['current']), 'previous_ledger_bytes': encoded(ledgers['previous']),
            'ledger_path': root + '/releases/current.json',
            'previous_ledger_path': root + '/releases/current/cutover-fixture/old-ledger.bytes',
            'app_inspection': app, 'current_baseline': copy.deepcopy(baseline),
            'previous_baseline': copy.deepcopy(baseline), 'backup_proofs': proofs,
            'backup_root': backup_root, 'generated_at': datetime(2026, 11, 16, tzinfo=timezone.utc)}


def test_manifest_protects_both_sets_and_live_dependencies_without_freezing_all_archives():
    arguments = evidence()
    manifest = build_protection_manifest(**arguments)
    paths = {row['path']: row['kind'] for row in manifest['protected_paths']}
    assert {row['role'] for row in manifest['recovery_sets']} == {'current', 'previous'}
    assert paths['/srv/fictional/releases/current'] == 'directory'
    assert paths['/srv/fictional/releases/previous'] == 'directory'
    assert paths['/srv/fictional/old-release/override.json'] == 'file'
    assert '/srv/fictional/old-release' not in paths
    assert paths['/srv/fictional/gene-source'] == 'directory'
    assert paths['/srv/fictional/runtime/inbox'] == 'directory'
    assert paths['/srv/fictional/deploy/.env'] == 'file'
    assert arguments['backup_root'] not in paths
    assert all(row['backup']['path'] in paths for row in manifest['recovery_sets'])
    assert image('d') in manifest['protected_images']
    assert 'do-not-emit-secret' not in json.dumps(manifest)
    assert 'environment' not in json.dumps(manifest)
    assert arguments == evidence()  # Assembly must not mutate its supplied evidence.


@pytest.mark.parametrize('change,reason', [
    ('live_image', 'live_image_binding_failed'),
    ('live_source', 'live_source_binding_failed'),
    ('health', 'live_app_not_healthy'),
    ('previous_image', 'previous_image_binding_failed'),
    ('unverified', 'recovery_archive_not_verified'),
    ('archive_path', 'recovery_archive_path_binding_failed'),
    ('digest', 'recovery_archive_digest_invalid'),
    ('environment_path', 'baseline_environment_path_missing'),
    ('compose', 'baseline_compose_files_missing'),
    ('runtime', 'runtime_mounts_missing'),
])
def test_incomplete_or_mismatched_evidence_holds(change, reason):
    arguments = evidence()
    if change == 'live_image':
        arguments['app_inspection']['Image'] = image('e')
    elif change == 'live_source':
        arguments['app_inspection']['Config']['Labels']['org.opencontainers.image.revision'] = 'e' * 40
    elif change == 'health':
        arguments['app_inspection']['State']['Health']['Status'] = 'starting'
    elif change == 'previous_image':
        previous = json.loads(arguments['previous_ledger_bytes']); previous['image'] = image('e')
        arguments['previous_ledger_bytes'] = encoded(previous)
    elif change == 'unverified':
        arguments['backup_proofs']['previous']['verified'] = False
    elif change == 'archive_path':
        arguments['backup_proofs']['previous']['path'] = '/srv/fictional/backups/other.tar.gz'
    elif change == 'digest':
        arguments['backup_proofs']['current']['sha256'] = 'not-a-digest'
    elif change == 'environment_path':
        arguments['previous_baseline']['compose_argv'] = ['docker', 'compose']
    elif change == 'compose':
        arguments['current_baseline']['ordered_compose_files'] = []
    elif change == 'runtime':
        arguments['current_baseline']['mounts'] = [arguments['current_baseline']['mounts'][-1]]
    with pytest.raises(StorageRecoveryError, match=reason):
        build_protection_manifest(**arguments)


def test_two_roles_cannot_silently_share_one_recovery_archive():
    arguments = evidence()
    previous = json.loads(arguments['previous_ledger_bytes'])
    previous['backup'] = arguments['backup_proofs']['current']['path']
    arguments['previous_ledger_bytes'] = encoded(previous)
    arguments['backup_proofs']['previous'] = copy.deepcopy(arguments['backup_proofs']['current'])
    with pytest.raises(StorageRecoveryError, match='distinct_recovery_archives_required'):
        build_protection_manifest(**arguments)


def test_direct_root_daily_archive_is_not_a_release_recovery_pin():
    arguments = evidence()
    current = json.loads(arguments['ledger_bytes'])
    current['backup'] = arguments['backup_root'] + '/berry-runtime-20261101T000000Z.tar.gz'
    arguments['ledger_bytes'] = encoded(current)
    arguments['backup_proofs']['current']['path'] = current['backup']
    with pytest.raises(StorageRecoveryError, match='recovery_archive_must_use_release_child'):
        build_protection_manifest(**arguments)


def test_configuration_only_recovery_sets_may_share_one_immutable_image():
    arguments = evidence()
    current = json.loads(arguments['ledger_bytes'])
    previous = json.loads(arguments['previous_ledger_bytes'])
    previous['image'], previous['source_sha'] = current['image'], current['source_sha']
    current['previous_image'] = current['image']
    arguments['ledger_bytes'], arguments['previous_ledger_bytes'] = encoded(current), encoded(previous)
    result = build_protection_manifest(**arguments)
    assert result['recovery_sets'][0]['image'] == result['recovery_sets'][1]['image']
    assert result['recovery_sets'][0]['backup']['path'] != result['recovery_sets'][1]['backup']['path']


@pytest.mark.parametrize('bad_path', ['/srv/../etc/data', '/srv//double', '//srv/double-root', '/', '/srv/name\nunsafe', '/srv/name\runsafe'])
def test_noncanonical_host_paths_are_refused(bad_path):
    arguments = evidence()
    arguments['ledger_path'] = bad_path
    with pytest.raises(StorageRecoveryError, match='invalid_host_path'):
        build_protection_manifest(**arguments)


def test_metadata_read_refuses_symlink_and_preserves_target(tmp_path):
    target = tmp_path / 'source.json'; target.write_bytes(b'{}')
    link = tmp_path / 'link.json'
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip('Creating symlinks is not available on this host')
    with pytest.raises(StorageRecoveryError, match='filesystem_indirection_refused'):
        _read(link)
    assert target.read_bytes() == b'{}'


def test_metadata_bounds_hold_before_reading_large_file(tmp_path):
    target = tmp_path / 'metadata.json'; target.write_bytes(b'{}' * 100)
    with pytest.raises(StorageRecoveryError, match='metadata_permissions_or_bound_invalid'):
        _read(target, maximum=100)
    assert target.stat().st_size == 200


def test_same_image_recreate_mount_drift_and_compose_order_have_distinct_live_bindings():
    from app.services.storage_recovery import recovery_live_binding
    app = evidence()['app_inspection']
    original = recovery_live_binding(app)
    changed = copy.deepcopy(app); changed['Id'] = 'e' * 64
    assert recovery_live_binding(changed) != original
    changed = copy.deepcopy(app); changed['Mounts'][0]['Source'] += '-moved'
    assert recovery_live_binding(changed)['mount_fingerprint'] != original['mount_fingerprint']
    changed = copy.deepcopy(app)
    field = 'com.docker.compose.project.config_files'
    changed['Config']['Labels'][field] = ','.join(reversed(changed['Config']['Labels'][field].split(',')))
    assert recovery_live_binding(changed)['compose_fingerprint'] != original['compose_fingerprint']
    changed = copy.deepcopy(app); changed['Mounts'].reverse()
    assert recovery_live_binding(changed) == original
    changed = copy.deepcopy(app); changed['State']['Running'] = False
    assert recovery_live_binding(changed)['healthy'] is False
    assert 'do-not-emit-secret' not in json.dumps(original)


def test_live_copilot_identity_health_image_and_namespace_are_bound():
    from app.services.storage_recovery import recovery_live_binding
    app = evidence()['app_inspection']
    node = {'Id': 'd' * 64, 'Image': image('d'), 'HostConfig': {'NetworkMode': 'container:' + app['Id']},
            'State': {'Running': True, 'Health': {'Status': 'healthy'}}}
    original = recovery_live_binding(app, node)
    assert original['healthy'] and original['copilot']['container_id'] == node['Id']
    changed = copy.deepcopy(node); changed['Id'] = 'e' * 64
    assert recovery_live_binding(app, changed) != original
    changed = copy.deepcopy(node); changed['Image'] = image('e')
    assert recovery_live_binding(app, changed) != original
    changed = copy.deepcopy(node); changed['State']['Health']['Status'] = 'unhealthy'
    assert recovery_live_binding(app, changed)['healthy'] is False
    changed = copy.deepcopy(node); changed['HostConfig']['NetworkMode'] = 'container:' + 'e' * 64
    assert recovery_live_binding(app, changed)['healthy'] is False


def test_image_probe_uses_closed_text_stdin_and_checks_source(monkeypatch):
    from types import SimpleNamespace
    from app.services import storage_recovery
    calls = []

    def run(argv, **kwargs):
        assert kwargs['input'] == '' and kwargs['text'] is True
        identity = argv[-1]; calls.append(identity)
        letter = identity.removeprefix('sha256:')[0]
        return SimpleNamespace(returncode=0, stdout=json.dumps(identity) + ' ' + json.dumps(letter * 40))

    monkeypatch.setattr(storage_recovery.subprocess, 'run', run)
    storage_recovery._verify_images({'image': image('a'), 'source_sha': 'a' * 40},
                                    {'image': image('b'), 'source_sha': 'b' * 40})
    assert calls == [image('a'), image('b')]


def test_all_protected_images_are_probed_and_missing_or_wrong_revision_holds(monkeypatch):
    from types import SimpleNamespace
    from app.services import storage_recovery
    calls = []
    broken = {'image': None, 'source': False}

    def run(argv, **kwargs):
        identity = argv[-1]; calls.append(identity)
        if identity == broken['image']:
            return SimpleNamespace(returncode=1, stdout='')
        letter = identity.removeprefix('sha256:')[0]
        source = 'e' * 40 if broken['source'] else letter * 40
        return SimpleNamespace(returncode=0, stdout=json.dumps(identity) + ' ' + json.dumps(source))

    monkeypatch.setattr(storage_recovery.subprocess, 'run', run)
    proofs = [{'image': image(letter), 'source_sha': letter * 40, 'exists': True, 'provenance_verified': True}
              for letter in ['a', 'b', 'c', 'd']]
    assert storage_recovery.verify_protected_image_provenance(proofs) == proofs
    assert calls == [image(letter) for letter in ['a', 'b', 'c', 'd']]
    broken['image'] = image('c')
    with pytest.raises(StorageRecoveryError, match='recovery_image_missing'):
        storage_recovery.verify_protected_image_provenance(proofs)
    broken.update(image=None, source=True)
    with pytest.raises(StorageRecoveryError, match='recovery_image_provenance_failed'):
        storage_recovery.verify_protected_image_provenance(proofs)


def test_accepted_promotion_receipt_schema_and_identity_are_required(monkeypatch):
    from app.services import storage_recovery
    arguments = evidence(); ledger = json.loads(arguments['ledger_bytes'])
    receipt = {'status': 'PASS', 'image': ledger['image'], 'old_ledger_sha256': 'b' * 64,
               'new_ledger_sha256': hashlib.sha256(arguments['ledger_bytes']).hexdigest()}
    monkeypatch.setattr(storage_recovery, '_read', lambda path: encoded(receipt))
    assert storage_recovery._accepted_promotion(ledger, arguments['ledger_bytes'])['old_ledger_sha256'] == 'b' * 64
    receipt['status'] = 'PREPARED'
    with pytest.raises(StorageRecoveryError, match='accepted_promotion_status_unknown'):
        storage_recovery._accepted_promotion(ledger, arguments['ledger_bytes'])
    receipt['status'] = 'PASS'; receipt['image'] = image('e')
    with pytest.raises(StorageRecoveryError, match='accepted_promotion_image_mismatch'):
        storage_recovery._accepted_promotion(ledger, arguments['ledger_bytes'])
    receipt['image'] = ledger['image']; receipt.pop('old_ledger_sha256')
    with pytest.raises(StorageRecoveryError, match='accepted_previous_ledger_hash_missing'):
        storage_recovery._accepted_promotion(ledger, arguments['ledger_bytes'])


@pytest.mark.skipif(os.name == 'nt', reason='Production collector uses POSIX host paths')
def test_previous_discovery_follows_accepted_receipt_hash_not_image_uniqueness(tmp_path):
    stage = tmp_path / 'current'; stage.mkdir()
    one, two = stage / 'cutover-one', stage / 'promotion-two'
    one.mkdir(); two.mkdir()
    arguments = evidence()
    previous = json.loads(arguments['previous_ledger_bytes'])
    (one / 'old-ledger.bytes').write_bytes(encoded(previous))
    (two / 'ledger-before.bytes').write_bytes(encoded(previous))
    ledger = json.loads(arguments['ledger_bytes']); ledger['stage'] = str(stage); ledger['receipt'] = str(stage / 'accepted.json')
    raw = encoded(ledger)
    receipt = {'status': 'PASS', 'image': ledger['image'], 'old_ledger_sha256': hashlib.sha256(encoded(previous)).hexdigest(),
               'new_ledger_sha256': hashlib.sha256(raw).hexdigest()}
    Path(ledger['receipt']).write_bytes(encoded(receipt))
    _, body = _previous(ledger, raw)
    assert body == encoded(previous)
    previous['note'] = 'different accepted configuration'
    (two / 'ledger-before.bytes').write_bytes(encoded(previous))
    _, body = _previous(ledger, raw)
    assert body == (one / 'old-ledger.bytes').read_bytes()
    receipt['old_ledger_sha256'] = '0' * 64; Path(ledger['receipt']).write_bytes(encoded(receipt))
    with pytest.raises(StorageRecoveryError, match='previous_ledger_not_found'):
        _previous(ledger, raw)
    receipt['new_ledger_sha256'] = '0' * 64; Path(ledger['receipt']).write_bytes(encoded(receipt))
    with pytest.raises(StorageRecoveryError, match='accepted_promotion_new_ledger_mismatch'):
        _previous(ledger, raw)


@pytest.mark.skipif(os.name == 'nt', reason='Production collector uses POSIX host paths')
def test_collector_verifies_real_small_archives_and_refuses_lost_dependency(tmp_path, monkeypatch):
    from app.services.runtime_backup import create_backup
    from app.services import storage_recovery

    monkeypatch.setattr(storage_recovery, '_verify_image_set', lambda expected: [
        {'image': image, 'source_sha': source, 'exists': True, 'provenance_verified': True}
        for image, source in expected.items()])

    arguments = evidence(str(tmp_path))
    current, previous = json.loads(arguments['ledger_bytes']), json.loads(arguments['previous_ledger_bytes'])
    older = copy.deepcopy(previous)
    older.update(source_sha='c' * 40, image=image('c'), previous_image=image('e'),
                 stage=str(tmp_path / 'releases/older'), backup=str(tmp_path / 'backups/older/older.tar.gz'))
    runtime = tmp_path / 'runtime'
    (runtime / 'data').mkdir(parents=True)
    (runtime / 'inbox').mkdir()
    (runtime / 'inbox/draft.json').write_bytes(b'{"status":"pending"}')
    (runtime / 'data/config.json').write_bytes(b'{}')
    (tmp_path / 'gene-source').mkdir()
    for role, ledger in [('current', current), ('previous', previous)]:
        stage = Path(ledger['stage']); (stage / 'operator-private').mkdir(parents=True)
        cutover = stage / 'cutover-fixture'; cutover.mkdir()
        archive = create_backup(runtime, tmp_path / 'backups' / role,
                                now=datetime(2026, 11, 1, tzinfo=timezone.utc))
        assert str(archive) == ledger['backup']
        import hashlib
        receipt = {'archive': str(archive), 'archive_bytes': archive.stat().st_size,
                   'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        (cutover / 'backup-safe.json').write_bytes(encoded(receipt))
        (stage / 'operator-private/baseline-private.json').write_bytes(encoded(arguments[role + '_baseline']))
        for field in ['compose_override', 'rollback_override', 'receipt']:
            Path(ledger[field]).write_bytes(b'{}')
    previous_path = Path(arguments['previous_ledger_path']); previous_path.write_bytes(encoded(previous))
    (Path(previous['stage']) / 'cutover-fixture/old-ledger.bytes').write_bytes(encoded(older))
    ledger_path = Path(arguments['ledger_path']); ledger_path.write_bytes(encoded(current))
    for ledger, before in [(current, previous), (previous, older)]:
        Path(ledger['receipt']).write_bytes(encoded({'status': 'PASS', 'image': ledger['image'],
            'old_ledger_sha256': hashlib.sha256(encoded(before)).hexdigest(),
            'new_ledger_sha256': hashlib.sha256(encoded(ledger)).hexdigest()}))
    for name in ['deploy/base.yml', 'deploy/.env', 'old-release/override.json']:
        path = tmp_path / name; path.parent.mkdir(exist_ok=True); path.write_bytes(b'fixture')
    manifest = collect_recovery_manifest(ledger_path, tmp_path / 'backups', arguments['app_inspection'])
    assert all(row['backup']['verified'] and row['backup']['manifest_file_count'] == 2
               for row in manifest['recovery_sets'])
    assert len(manifest['protected_image_provenance']) == len(manifest['protected_images'])
    assert {r['role'] for r in manifest['accepted_promotion_receipts']} == {'current', 'previous'}
    Path(previous['rollback_override']).unlink()
    with pytest.raises((StorageRecoveryError, OSError)):
        collect_recovery_manifest(ledger_path, tmp_path / 'backups', arguments['app_inspection'])
