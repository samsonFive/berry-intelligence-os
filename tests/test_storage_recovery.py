from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import pytest
from test_storage_retention import environment as accepted_environment

from app.services.storage_recovery import (
    StorageRecoveryError, _previous, _read, _safe,
    build_protection_manifest, collect_recovery_manifest,
    validate_accepted_recovery_proofs,
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
           }}, 'HostConfig': {}, 'Mounts': mounts, 'State': {'Running': True, 'Health': {'Status': 'healthy'}},
           '_storage_recovery_sidecar': {'container_id': 'd' * 64, 'image': image('d'), 'healthy': True,
                                          'network_mode': 'container:' + 'a' * 64, 'config_fingerprint': 'd' * 64}}
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
            'Config': {'Env': ['TOKEN=fictional-secret']}, 'Mounts': [],
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
    changed = copy.deepcopy(node); changed['HostConfig']['LogConfig'] = {'Type': 'local', 'Config': {'max-size': '10m'}}
    assert recovery_live_binding(app, changed)['copilot']['config_fingerprint'] != original['copilot']['config_fingerprint']
    changed_app = copy.deepcopy(app); changed_app['Config']['Env'] = ['TOKEN=changed-fictional-secret']
    assert recovery_live_binding(changed_app, node)['config_fingerprint'] != original['config_fingerprint']
    assert 'fictional-secret' not in json.dumps(original)


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
def test_unsigned_historical_baselines_and_archives_never_authorize_retention(tmp_path, monkeypatch):
    from app.services.runtime_backup import create_backup, verify_backup
    from app.services import runtime_backup
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
    bounded_calls = []
    def bounded_verify(path, **limits):
        assert limits == {'maximum_manifest_bytes': 16 * 1024**2, 'maximum_members': 100001}
        bounded_calls.append(path)
        return verify_backup(path, **limits)
    monkeypatch.setattr(runtime_backup, 'verify_backup', bounded_verify)
    with pytest.raises(StorageRecoveryError, match='accepted_recovery_proof_missing'):
        collect_recovery_manifest(ledger_path, tmp_path / 'backups', arguments['app_inspection'])
    assert not bounded_calls


@pytest.fixture
def authenticated_memory(accepted_environment):
    """Real producer fixture bytes, then pure injected reads for adversarial races."""
    return _memory_state(accepted_environment)


def _memory_state(env):
    from types import SimpleNamespace
    manifest = copy.deepcopy(env['value'])
    bodies = {pin['path']: Path(pin['path']).read_bytes() for pin in manifest['accepted_content_pins']}
    modes = {pin['path']: pin['mode'] for pin in manifest['accepted_content_pins']}

    def read_file(path, maximum):
        name = str(path)
        if name not in bodies:
            raise FileNotFoundError
        assert len(bodies[name]) <= maximum
        return bodies[name]

    def stat_file(path):
        name = str(path)
        if name not in bodies:
            raise FileNotFoundError
        return SimpleNamespace(st_mode=0o100000 | modes.get(name, 0o600), st_uid=0, st_nlink=1,
            st_dev=1, st_ino=1, st_size=len(bodies[name]), st_mtime_ns=1)

    return {'env': env, 'manifest': manifest, 'bodies': bodies, 'read': read_file, 'stat': stat_file}


@pytest.fixture
def authenticated_configuration_memory(accepted_environment):
    from storage_logging_fixtures import configuration_only_environment
    env = configuration_only_environment(accepted_environment, now=datetime(2026, 11, 16, 12, tzinfo=timezone.utc))
    return _memory_state(env)


def test_authenticated_full_producer_closure_passes_without_exposing_private_config(authenticated_memory):
    state = authenticated_memory
    validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    assert 'accepted-private-value' not in json.dumps(state['manifest'])


@pytest.mark.parametrize('change', ['baseline', 'compose', 'environment', 'store_marker', 'plan', 'raw_manifest', 'rollback_module'])
def test_accepted_exact_bytes_cannot_be_replaced_at_the_same_path(authenticated_memory, change):
    state = authenticated_memory
    wrapper = state['env']['wrapper']; recovery = wrapper['recovery_files']
    refs = {'baseline': wrapper['snapshots']['pre'], 'compose': wrapper['configuration']['post']['app']['compose_files'][0],
        'environment': wrapper['configuration']['post']['app']['environment_files'][0],
        'store_marker': next(pin for pin in wrapper['configuration']['post']['app']['dependency_files'] if pin['path'].endswith('store.json')),
        'plan': wrapper['plan'], 'raw_manifest': recovery['raw_manifest'], 'rollback_module': recovery['rollback_modules'][0]}
    state['bodies'][refs[change]['path']] += b'changed-private-value'
    with pytest.raises(StorageRecoveryError, match='accepted_file_digest_mismatch') as caught:
        validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])
    assert 'changed-private-value' not in str(caught.value)


@pytest.mark.parametrize('change', ['app_config', 'copilot_config', 'proof_pointer', 'missing_raw_directory'])
def test_matching_images_cannot_bypass_accepted_configuration_or_protection(authenticated_memory, change):
    state = authenticated_memory; manifest = state['manifest']
    if change == 'app_config':
        manifest['live_binding']['config_fingerprint'] = '0' * 64
    elif change == 'copilot_config':
        manifest['live_binding']['copilot']['config_fingerprint'] = '0' * 64
    elif change == 'proof_pointer':
        manifest['accepted_recovery_proofs'][0]['sha256'] = '0' * 64
    else:
        raw = str(Path(state['env']['wrapper']['recovery_files']['raw_plan']['path']).parent)
        manifest['protected_paths'] = [row for row in manifest['protected_paths'] if row['path'] != raw]
        manifest['protected_paths'].append({'path': raw, 'kind': 'file'})
    with pytest.raises(StorageRecoveryError, match='accepted_(live_configuration|content_manifest|directory_protection)'):
        validate_accepted_recovery_proofs(manifest, read_file=state['read'], stat_file=state['stat'])


def test_accepted_content_is_reread_after_other_dependencies(authenticated_memory):
    state = authenticated_memory; target = state['env']['wrapper']['snapshots']['pre']['path']; calls = 0
    def racing_read(path, maximum):
        nonlocal calls
        if str(path) == target:
            calls += 1
            if calls == 2:
                state['bodies'][target] += b'late-change'
        return state['read'](path, maximum)
    with pytest.raises(StorageRecoveryError, match='accepted_file_(changed|digest_mismatch)'):
        validate_accepted_recovery_proofs(state['manifest'], read_file=racing_read, stat_file=state['stat'])
    assert calls == 2


def test_transition_created_during_collection_is_rechecked(authenticated_memory):
    state = authenticated_memory
    transition = str(state['env']['runtime'] / 'data/.information-store-transition.json'); probes = 0
    def racing_stat(path):
        nonlocal probes
        if str(path) == transition:
            probes += 1
            if probes == 2:
                state['bodies'][transition] = b'{}'
        return state['stat'](path)
    with pytest.raises(StorageRecoveryError, match='accepted_store_transition_present'):
        validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=racing_stat)


def test_full_caddy_identity_and_logging_are_bound_without_changing_binding_shape():
    from app.services.storage_recovery import recovery_live_binding
    app = evidence()['app_inspection']
    caddy = {'Id': 'e' * 64, 'Image': image('e'), 'Config': {'Env': ['TOKEN=private-caddy-value']},
        'HostConfig': {'LogConfig': {'Type': 'json-file', 'Config': {'max-size': '10m'}}}, 'Mounts': [], 'State': {'Running': True}}
    original = recovery_live_binding(app, caddy_inspection=caddy)
    assert len(original) == 8 and original['healthy']
    for field in ('Id', 'HostConfig'):
        changed = copy.deepcopy(caddy)
        if field == 'Id': changed['Id'] = 'f' * 64
        else: changed['HostConfig']['LogConfig']['Config']['max-size'] = '999m'
        assert recovery_live_binding(app, caddy_inspection=changed)['config_fingerprint'] != original['config_fingerprint']
    changed = copy.deepcopy(caddy); changed['State']['Running'] = False
    assert recovery_live_binding(app, caddy_inspection=changed)['healthy'] is False
    assert 'private-caddy-value' not in json.dumps(original)


def test_opaque_recovery_inventory_streams_beyond_the_parsed_metadata_budget(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services import storage_recovery
    import stat
    inventory = tmp_path / 'opaque-inventory.json'
    block = b'x' * 1024**2
    expected = hashlib.sha256()
    with inventory.open('wb') as handle:
        for _ in range(5):
            handle.write(block); expected.update(block)
    if os.name == 'nt':
        monkeypatch.setattr(storage_recovery, '_host_path', lambda value: str(Path(value)))
    def file_stat(path):
        info = path.stat()
        return SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_size=info.st_size,
            st_dev=info.st_dev, st_ino=info.st_ino, st_mtime_ns=info.st_mtime_ns, st_uid=0, st_nlink=1)
    original = storage_recovery.os.fdopen
    reads = []
    class BoundedRead:
        def __init__(self, handle): self.handle = handle
        def __enter__(self): return self
        def __exit__(self, *args): self.handle.close()
        def fileno(self): return self.handle.fileno()
        def read(self, size=-1):
            assert 0 < size <= 1024**2
            reads.append(size)
            return self.handle.read(size)
    monkeypatch.setattr(storage_recovery.os, 'fdopen', lambda *args, **kwargs: BoundedRead(original(*args, **kwargs)))
    reader = storage_recovery._AcceptedFiles(stat_file=file_stat)
    reader.file({'path': str(inventory), 'sha256': expected.hexdigest()})
    reader.reread()
    assert len(reads) == 12
    assert reader.pins[str(inventory)]['size'] == 5 * 1024**2


def _reseal_memory_wrapper(state, wrapper):
    """Model a newly accepted outer pointer; native evidence stays immutable."""
    ledger_path = state['manifest']['ledger_path']
    ledger = json.loads(state['bodies'][ledger_path])
    wrapper_path = ledger['recovery_proof']['path']
    state['bodies'][wrapper_path] = encoded(wrapper)
    ledger['recovery_proof']['sha256'] = hashlib.sha256(state['bodies'][wrapper_path]).hexdigest()
    state['bodies'][ledger_path] = encoded(ledger)
    receipt = json.loads(state['bodies'][ledger['receipt']])
    receipt['new_ledger_sha256'] = hashlib.sha256(state['bodies'][ledger_path]).hexdigest()
    state['bodies'][ledger['receipt']] = encoded(receipt)


def test_even_valid_stale_pre_snapshot_cannot_replace_accepted_post_snapshot(authenticated_memory):
    state = authenticated_memory
    wrapper = copy.deepcopy(state['env']['wrapper'])
    wrapper['snapshots']['post'] = wrapper['snapshots']['pre']
    _reseal_memory_wrapper(state, wrapper)
    with pytest.raises(StorageRecoveryError, match='accepted_snapshot_identity_mismatch'):
        validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])


def test_bare_replay_step_claims_cannot_replace_the_reviewed_protocol(authenticated_memory):
    state = authenticated_memory
    archive = state['env']['wrapper']['archives']['current']
    recipe = json.loads(state['bodies'][archive['recovery_recipe']['path']])
    recipe.pop('replay_protocol')
    state['bodies'][archive['recovery_recipe']['path']] = encoded(recipe)
    wrapper = copy.deepcopy(state['env']['wrapper'])
    wrapper['archives']['current']['recovery_recipe']['sha256'] = hashlib.sha256(encoded(recipe)).hexdigest()
    _reseal_memory_wrapper(state, wrapper)
    with pytest.raises(StorageRecoveryError, match='accepted_file_reference_invalid'):
        validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])


@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'geteuid') or os.geteuid() != 0,
                    reason='Root Linux fixture verifies actual UID1000 application marker ownership')
def test_default_reader_accepts_pinned_uid1000_marker_but_never_private_proof(tmp_path):
    from app.services.storage_recovery import _AcceptedFiles
    marker = tmp_path / 'store.json'
    marker.write_bytes(b'{"version":1,"state":"active"}')
    marker.chmod(0o600)
    os.chown(marker, 1000, 1000)
    ref = {'path': str(marker), 'sha256': hashlib.sha256(marker.read_bytes()).hexdigest(), 'mode': 0o600}
    assert _AcceptedFiles().json(ref, private=False)['state'] == 'active'
    with pytest.raises(StorageRecoveryError, match='accepted_private_file_invalid'):
        _AcceptedFiles().json(ref, private=True)


def test_configuration_only_accepts_current_store_and_binds_all_three_containers(authenticated_configuration_memory):
    from app.services.storage_recovery import recovery_live_binding
    state = authenticated_configuration_memory; manifest = state['manifest']; env = state['env']
    validate_accepted_recovery_proofs(manifest, read_file=state['read'], stat_file=state['stat'])
    assert manifest['operation_kind'] == 'configuration-only' and manifest['accepted_caddy_id'] == env['post_caddy']['Id']
    baseline = copy.deepcopy(manifest['live_binding'])
    for service, field in [('app', 'Config'), ('copilot', 'HostConfig'), ('caddy', 'HostConfig'), ('caddy', 'Id')]:
        pair, caddy = copy.deepcopy(env['post_pair']), copy.deepcopy(env['post_caddy'])
        target = caddy if service == 'caddy' else pair[service]
        if field == 'Id': target['Id'] = '0' * 64
        elif field == 'Config': target['Config']['Env'].append('UNACCEPTED=fictional-private-value')
        else: target['HostConfig']['LogConfig']['Config']['max-size'] = '999m'
        manifest['live_binding'] = recovery_live_binding(pair['app'], pair['copilot'], caddy_inspection=caddy)
        with pytest.raises(StorageRecoveryError, match='accepted_live_configuration_mismatch'):
            validate_accepted_recovery_proofs(manifest, read_file=state['read'], stat_file=state['stat'])
    manifest['live_binding'] = baseline
    assert 'accepted-private-value' not in json.dumps(manifest)


def test_configuration_only_cannot_smuggle_physical_storage_rollback(authenticated_configuration_memory):
    state = authenticated_configuration_memory
    wrapper = copy.deepcopy(state['env']['wrapper'])
    proof_ref = wrapper['recovery_files']['final_proof']; phase_ref = wrapper['recovery_files']['phase_receipt']
    proof = json.loads(state['bodies'][proof_ref['path']])
    proof['rollback_recipe']['steps'].insert(2, 'strict-storage-rollback')
    state['bodies'][proof_ref['path']] = encoded(proof)
    proof_ref['sha256'] = hashlib.sha256(encoded(proof)).hexdigest()
    phase = json.loads(state['bodies'][phase_ref['path']])
    phase['final_verification']['recovery_proof_sha256'] = proof_ref['sha256']
    state['bodies'][phase_ref['path']] = encoded(phase)
    phase_ref['sha256'] = hashlib.sha256(encoded(phase)).hexdigest()
    _reseal_memory_wrapper(state, wrapper)
    with pytest.raises(StorageRecoveryError, match='accepted_rollback_recipe_invalid'):
        validate_accepted_recovery_proofs(state['manifest'], read_file=state['read'], stat_file=state['stat'])


@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'geteuid') or os.geteuid() != 0,
                    reason='Default production collector is root/POSIX; all writes stay inside this fixture')
def test_default_collector_verifies_local_archives_and_rechecks_accepted_content(accepted_environment, monkeypatch):
    from app.services import storage_recovery, runtime_backup
    env = accepted_environment
    original_verify = runtime_backup.verify_backup; calls = []
    def verified(path, **limits):
        assert limits == {'maximum_manifest_bytes': 16 * 1024**2, 'maximum_members': 100001}
        calls.append(path)
        return original_verify(path, **limits)
    monkeypatch.setattr(runtime_backup, 'verify_backup', verified)
    monkeypatch.setattr(storage_recovery, '_verify_image_set', lambda expected: [
        {'image': image, 'source_sha': source, 'exists': True, 'provenance_verified': True}
        for image, source in sorted(expected.items())])
    app = storage_recovery._pair_app(env['post_pair'])
    result = collect_recovery_manifest(env['ledger'], env['backups'], app_inspection=app)
    assert len(calls) == 2 and all(row['backup']['verified'] for row in result['recovery_sets'])
    validate_accepted_recovery_proofs(result)
    assert 'accepted-private-value' not in json.dumps(result)
    def changed_during_image_verification(expected):
        env['accepted_dependency'].write_bytes(b'UNACCEPTED=late-private-value\n')
        return [{'image': image, 'source_sha': source, 'exists': True, 'provenance_verified': True}
                for image, source in sorted(expected.items())]
    monkeypatch.setattr(storage_recovery, '_verify_image_set', changed_during_image_verification)
    with pytest.raises(StorageRecoveryError, match='accepted_file_digest_mismatch'):
        collect_recovery_manifest(env['ledger'], env['backups'], app_inspection=app)


def test_later_configuration_release_keeps_previous_unified_backup_honestly_direct():
    from app.services.storage_recovery import _archive_role
    pin = {'path': '/srv/backups/previous/berry-runtime-20261116T000000Z.tar.gz', 'sha256': 'a' * 64, 'size': 1,
        'capture_phase': 'pre-configuration', 'store_schema': 'unified-v1', 'recovery_role': 'direct',
        'recovery_recipe': None, 'transformation_proof': None}
    _archive_role(pin, 'previous', 'configuration-only', {}, {}, {}, {}, {}, None)
    pin['store_schema'] = 'legacy'
    with pytest.raises(StorageRecoveryError, match='accepted_archive_role_mismatch'):
        _archive_role(pin, 'previous', 'configuration-only', {}, {}, {}, {}, {}, None)
