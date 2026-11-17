"""Resolve the accepted current/previous recovery sets without changing them.

The collector is intended to run inside the caller's three release locks. It
never reads environment values into its output and never removes anything.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any

LEDGER_PATH = Path('/opt/berry-platform-releases/current.json')
BACKUP_ROOT = Path('/var/backups/berry-intelligence-os')
SHARED_RELEASE_LOCKS = (
    Path('/run/lock/berry-review.lock'),
    Path('/opt/berry-platform-releases/brand-media-release.lock'),
    Path('/opt/berry-platform-releases/watchlist524-release.lock'),
)
_HEX = re.compile(r'[a-f0-9]{64}\Z')
_SOURCE = re.compile(r'[a-f0-9]{40}\Z')
_IMAGE = re.compile(r'sha256:[a-f0-9]{64}\Z')
RECOVERY_PROOF_SCHEMA = 'berry.recovery-proof.v1'
ADOPTION_SCHEMA = 'berry.recovery-adoption.v1'
ADOPTION_PROFILE = 'frozen-590-extended-snapshot.v1'
ADOPTION_LOGO_PROFILE = 'frozen-590-extended-logos.v1'
REPLAY_V2_CHECKS = frozenset({
    'restore-bytes-and-modes', 'source-hashes-before-mtime', 'source-mtime-ns-rehydration',
    'fresh-plan-at-new-paths', 'new-empty-backup-base', 'winner-and-variants-preserved',
    'analyst-decisions-preserved', 'current-store-verification', 'fresh-prepared-plan',
    'this-plan-id', 'no-old-plan-reuse', 'no-replan', 'no-aggregate-plan-rewrite',
    'ascii-plan-full-roundtrip', 'prepared-raw-and-canonical-sha', 'source-fingerprint-validated',
    'buffers-released-before-plan', 'all-protected-runtime-state',
})
_BEFORE_NAMES = frozenset({
    'old-ledger.bytes', 'ledger-before.bytes', 'report-library-ledger-before.bytes',
    'ledger-before.json', 'current-before.json',
})
_RECEIPT_NAMES = ('fresh-backup-safe.json', 'backup-safe.json', 'activation-safe.json', 'reports-activation-safe.json')


class StorageRecoveryError(ValueError):
    """Fixed reason codes only; exception text must not contain configuration."""


def _need(value: Any, reason: str) -> None:
    if not value:
        raise StorageRecoveryError(reason)


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _host_path(value: Any) -> str:
    _need(isinstance(value, str) and value and not value.startswith('//') and '\x00' not in value
          and '\\' not in value and '\n' not in value and '\r' not in value, 'invalid_host_path')
    path = PurePosixPath(value)
    _need(path.is_absolute() and '..' not in path.parts and str(path) == value and value != '/', 'invalid_host_path')
    return value


def _identity(value: dict) -> dict:
    _need(isinstance(value, dict), 'ledger_shape_invalid')
    source, image = value.get('source_sha'), value.get('image')
    _need(isinstance(source, str) and _SOURCE.fullmatch(source), 'ledger_source_missing')
    _need(isinstance(image, str) and _IMAGE.fullmatch(image), 'ledger_image_missing')
    return {'source_sha': source, 'image': image, 'stage': _host_path(value.get('stage')), 'backup': _host_path(value.get('backup'))}


def _parsed(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise StorageRecoveryError('metadata_json_invalid') from None
    _need(isinstance(value, dict), 'metadata_shape_invalid')
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def _configuration_fingerprint(container: dict) -> str:
    _need(isinstance(container.get('Config'), dict) and isinstance(container.get('HostConfig'), dict)
          and isinstance(container.get('Mounts'), list), 'full_container_configuration_missing')
    return _sha(_canonical({'Config': container['Config'], 'HostConfig': container['HostConfig'],
        'Mounts': sorted(container['Mounts'], key=lambda row: _canonical(row))}))


def _sidecar_snapshot(sidecar: dict) -> dict:
    state = sidecar.get('State') or {}
    return {'container_id': sidecar.get('Id'), 'image': sidecar.get('Image'),
            'healthy': state.get('Running') is True and state.get('Health', {}).get('Status') == 'healthy',
            'network_mode': sidecar.get('HostConfig', {}).get('NetworkMode'),
            'config_fingerprint': _configuration_fingerprint(sidecar)}


def _caddy_snapshot(container: dict) -> dict:
    _need(isinstance(container, dict) and isinstance(container.get('Id'), str) and _HEX.fullmatch(container['Id'])
          and isinstance(container.get('Image'), str) and _IMAGE.fullmatch(container['Image']), 'live_caddy_metadata_missing')
    return {'id': container['Id'], 'image': container['Image'], 'config_fingerprint': _configuration_fingerprint(container),
            'running': container.get('State', {}).get('Running') is True}


def recovery_live_binding(app_inspection: dict, sidecar_inspection: dict | None = None,
                          caddy_inspection: dict | None = None) -> dict:
    """Stable live identity/config-path evidence, without environment values."""
    _need(isinstance(app_inspection, dict), 'live_app_inspection_failed')
    identity = app_inspection.get('Id')
    image = app_inspection.get('Image')
    labels = app_inspection.get('Config', {}).get('Labels') or {}
    source = labels.get('org.opencontainers.image.revision')
    _need(isinstance(identity, str) and _HEX.fullmatch(identity), 'live_app_id_missing')
    _need(isinstance(image, str) and _IMAGE.fullmatch(image), 'live_image_binding_failed')
    _need(isinstance(source, str) and _SOURCE.fullmatch(source), 'live_source_binding_failed')
    mounts = app_inspection.get('Mounts')
    _need(isinstance(mounts, list) and mounts and all(isinstance(row, dict) for row in mounts), 'live_mounts_missing')
    files = labels.get('com.docker.compose.project.config_files', '').split(',')
    _need(files and all(files) and len(files) == len(set(files)), 'live_compose_chain_missing')
    for path in files:
        _host_path(path)
    serialize = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    ordered_mounts = sorted(mounts, key=lambda row: serialize(row))
    state = app_inspection.get('State') or {}
    node = _sidecar_snapshot(sidecar_inspection) if sidecar_inspection is not None else app_inspection.get('_storage_recovery_sidecar')
    _need(isinstance(node, dict) and isinstance(node.get('container_id'), str) and _HEX.fullmatch(node['container_id'])
          and isinstance(node.get('image'), str) and _IMAGE.fullmatch(node['image'])
          and isinstance(node.get('config_fingerprint'), str) and _HEX.fullmatch(node['config_fingerprint'])
          and type(node.get('healthy')) is bool and isinstance(node.get('network_mode'), str), 'live_copilot_metadata_missing')
    node = {name: node[name] for name in ['container_id', 'image', 'healthy', 'network_mode', 'config_fingerprint']}
    caddy = _caddy_snapshot(caddy_inspection) if caddy_inspection is not None else app_inspection.get('_storage_recovery_caddy')
    config_fingerprint = _configuration_fingerprint(app_inspection)
    if caddy is not None:
        _need(isinstance(caddy, dict) and set(caddy) == {'id', 'image', 'config_fingerprint', 'running'}
              and isinstance(caddy['id'], str) and _HEX.fullmatch(caddy['id'])
              and isinstance(caddy['image'], str) and _IMAGE.fullmatch(caddy['image'])
              and isinstance(caddy['config_fingerprint'], str) and _HEX.fullmatch(caddy['config_fingerprint'])
              and type(caddy['running']) is bool, 'live_caddy_metadata_missing')
        config_fingerprint = _sha(_canonical({'app': config_fingerprint, 'caddy': caddy}))
    return {'app_id': identity, 'image': image, 'source_sha': source,
            'mount_fingerprint': _sha(serialize(ordered_mounts)),
            'compose_fingerprint': _sha(serialize(files)),
            'config_fingerprint': config_fingerprint,
            'healthy': state.get('Running') is True and state.get('Health', {}).get('Status') == 'healthy'
                       and node['healthy'] and node['network_mode'] == 'container:' + identity
                       and (caddy is None or caddy['running']),
            'copilot': node}


def build_protection_manifest(*, ledger_bytes: bytes, previous_ledger_bytes: bytes,
                              ledger_path: str, previous_ledger_path: str,
                              app_inspection: dict, current_baseline: dict,
                              previous_baseline: dict, backup_proofs: dict[str, dict],
                              backup_root: str, generated_at: datetime | None = None,
                              metadata_paths: tuple[str, ...] = ()) -> dict:
    """Pure assembly from explicitly supplied evidence; no filesystem access."""
    ledger, previous = _parsed(ledger_bytes), _parsed(previous_ledger_bytes)
    current_id, previous_id = _identity(ledger), _identity(previous)
    _need(ledger.get('previous_image') == previous_id['image'], 'previous_image_binding_failed')
    _need(app_inspection.get('Image') == current_id['image'], 'live_image_binding_failed')
    labels = app_inspection.get('Config', {}).get('Labels') or {}
    _need(labels.get('org.opencontainers.image.revision') == current_id['source_sha'], 'live_source_binding_failed')
    binding = recovery_live_binding(app_inspection)
    _need(binding['healthy'], 'live_app_not_healthy')
    backup_root = _host_path(backup_root)
    paths: dict[str, str] = {}
    images = {current_id['image'], previous_id['image']}
    images.add(binding['copilot']['image'])

    def protect(value: str, kind='file') -> None:
        value = _host_path(value)
        _need(value != backup_root, 'whole_backup_root_must_not_be_pinned')
        _need(value not in paths or paths[value] == kind, 'protected_path_kind_conflict')
        paths[value] = kind

    def mounts(rows: Any) -> None:
        _need(isinstance(rows, list) and rows, 'recovery_mounts_missing')
        runtime_destinations = set()
        for mount in rows:
            _need(isinstance(mount, dict), 'recovery_mount_shape_invalid')
            if mount.get('Type') != 'bind':
                continue
            source = _host_path(mount.get('Source'))
            destination = mount.get('Destination')
            if destination == '/app/backups':
                _need(source == backup_root, 'backup_mount_binding_failed')
                continue
            # The collector replaces this conservative kind using actual lstat.
            protect(source, 'directory' if destination in {'/app/runtime/data', '/app/runtime/inbox', '/app/gene-delivery-source'} else 'file')
            runtime_destinations.add(destination)
        _need({'/app/runtime/data', '/app/runtime/inbox'}.issubset(runtime_destinations), 'runtime_mounts_missing')

    protect(ledger_path)
    protect(previous_ledger_path)
    for name in metadata_paths:
        protect(name)
    sets = []
    for role, value, identity, baseline in [
        ('current', ledger, current_id, current_baseline),
        ('previous', previous, previous_id, previous_baseline),
    ]:
        _need(isinstance(baseline, dict), 'recovery_baseline_missing')
        protect(identity['stage'], 'directory')
        files = baseline.get('ordered_compose_files')
        _need(isinstance(files, list) and files and len(files) == len(set(files)), 'baseline_compose_files_missing')
        for name in files:
            protect(name)
        argv = baseline.get('compose_argv')
        _need(isinstance(argv, list) and argv.count('--env-file') == 1, 'baseline_environment_path_missing')
        at = argv.index('--env-file')
        _need(at + 1 < len(argv), 'baseline_environment_path_missing')
        protect(argv[at + 1])
        for field in ('compose_override', 'rollback_override', 'receipt'):
            protect(value.get(field))
        mounts(baseline.get('mounts'))
        for field in ('node_image', 'web_image', 'rollback_image'):
            image = baseline.get(field)
            if image is not None:
                _need(isinstance(image, str) and _IMAGE.fullmatch(image), 'recovery_image_reference_invalid')
                images.add(image)
        proof = backup_proofs.get(role)
        _need(isinstance(proof, dict) and proof.get('verified') is True, 'recovery_archive_not_verified')
        _need(proof.get('path') == identity['backup'], 'recovery_archive_path_binding_failed')
        _need(PurePosixPath(identity['backup']).is_relative_to(PurePosixPath(backup_root)), 'recovery_archive_outside_root')
        _need(PurePosixPath(identity['backup']).parent != PurePosixPath(backup_root), 'recovery_archive_must_use_release_child')
        _need(type(proof.get('size')) is int and proof['size'] > 0, 'recovery_archive_size_invalid')
        _need(isinstance(proof.get('sha256'), str) and _HEX.fullmatch(proof['sha256']), 'recovery_archive_digest_invalid')
        protect(identity['backup'])
        sets.append({'role': role, 'source_sha': identity['source_sha'], 'image': identity['image'],
                     'stage': identity['stage'], 'backup': dict(proof)})
    _need(sets[0]['backup']['path'] != sets[1]['backup']['path'], 'distinct_recovery_archives_required')
    live_files = labels.get('com.docker.compose.project.config_files', '').split(',')
    _need(live_files and all(live_files) and len(live_files) == len(set(live_files)), 'live_compose_chain_missing')
    for name in live_files:
        protect(name)
    environment_file = labels.get('com.docker.compose.project.environment_file')
    if environment_file:
        protect(environment_file)
    mounts(app_inspection.get('Mounts'))
    instant = generated_at or datetime.now(timezone.utc)
    _need(instant.tzinfo is not None, 'aware_timestamp_required')
    return {
        'version': 1, 'generated_at': instant.astimezone(timezone.utc).isoformat(),
        'ledger_path': _host_path(ledger_path), 'ledger_sha256': _sha(ledger_bytes), 'backup_root': backup_root,
        'previous_ledger_path': _host_path(previous_ledger_path), 'previous_ledger_sha256': _sha(previous_ledger_bytes),
        'recovery_sets': sets, 'protected_paths': [{'path': name, 'kind': kind} for name, kind in sorted(paths.items())],
        'protected_images': sorted(images),
        'live_binding': binding,
        'policy': 'Protect both complete recovery sets, exact configuration files and active runtime/mount subtrees. The generic backup-root bind does not pin every historical archive.',
    }


def _safe(path: Path, *, directory=False) -> os.stat_result:
    _need(path.is_absolute() and '..' not in path.parts, 'absolute_metadata_path_required')
    for ancestor in reversed([path, *path.parents]):
        info = ancestor.lstat()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(ancestor, 'is_junction', lambda: False)(), 'filesystem_indirection_refused')
        _need(stat.S_ISDIR(info.st_mode) if ancestor != path or directory else stat.S_ISREG(info.st_mode), 'metadata_path_type_invalid')
    return path.lstat()


def _read(path: Path, maximum=2 * 1024**2) -> bytes:
    before = _safe(path)
    _need(before.st_size <= maximum and not stat.S_IMODE(before.st_mode) & 0o022, 'metadata_permissions_or_bound_invalid')
    if hasattr(os, 'getuid'):
        _need(before.st_uid in {0, os.getuid()}, 'metadata_owner_invalid')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        body = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    _need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
          (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) and len(body) == before.st_size,
          'metadata_changed_during_read')
    return body


def _metadata_folders(stage: Path) -> list[Path]:
    _safe(stage, directory=True)
    children = list(stage.iterdir())
    _need(len(children) <= 256, 'release_stage_scan_bound_exceeded')
    folders = [stage]
    for child in children:
        if child.is_dir() and not child.is_symlink() and child.name.startswith(('cutover-', 'promotion-', 'operator-private')):
            _safe(child, directory=True)
            folders.append(child)
    _need(len(folders) <= 64, 'release_stage_scan_bound_exceeded')
    return folders


def _accepted_promotion(ledger: dict, ledger_bytes: bytes) -> dict:
    path = Path(_host_path(ledger.get('receipt')))
    stage = Path(_host_path(ledger.get('stage')))
    _need(path.is_relative_to(stage), 'accepted_promotion_receipt_outside_stage')
    body = _read(path)
    value = _parsed(body)
    _need(value.get('status') == 'PASS', 'accepted_promotion_status_unknown')
    old = value.get('old_ledger_sha256')
    _need(isinstance(old, str) and _HEX.fullmatch(old), 'accepted_previous_ledger_hash_missing')
    new = value.get('new_ledger_sha256')
    if new is not None:
        _need(isinstance(new, str) and _HEX.fullmatch(new) and new == _sha(ledger_bytes), 'accepted_promotion_new_ledger_mismatch')
    image = value.get('candidate_image', value.get('image'))
    _need(image == ledger.get('image'), 'accepted_promotion_image_mismatch')
    if 'approved_head' in value:
        _need(value['approved_head'] == ledger.get('source_sha'), 'accepted_promotion_source_mismatch')
    return {'path': str(path), 'sha256': _sha(body), 'status': 'PASS', 'image': image,
            'old_ledger_sha256': old, 'new_ledger_sha256': new}


def _previous(ledger: dict, ledger_bytes: bytes) -> tuple[Path, bytes]:
    stage = Path(_host_path(ledger.get('stage')))
    accepted = _accepted_promotion(ledger, ledger_bytes)
    candidates = []
    for folder in _metadata_folders(stage):
        for name in sorted(_BEFORE_NAMES):
            path = folder / name
            if not path.exists() and not path.is_symlink():
                continue
            body = _read(path)
            value = _parsed(body)
            if _sha(body) == accepted['old_ledger_sha256']:
                _need(value.get('image') == ledger.get('previous_image'), 'accepted_previous_image_mismatch')
                _identity(value)
                candidates.append((path, body))
    _need(candidates and len(candidates) <= 32, 'previous_ledger_not_found')
    _need(len({_sha(body) for _, body in candidates}) == 1, 'previous_ledger_ambiguous')
    return candidates[0]


def _backup_receipt(stage: Path, archive: Path, backup_root: Path) -> tuple[Path, dict]:
    candidates = []
    for folder in _metadata_folders(stage):
        for name in _RECEIPT_NAMES:
            path = folder / name
            if not path.exists() and not path.is_symlink():
                continue
            value = _parsed(_read(path))
            evidence = value.get('backup') if isinstance(value.get('backup'), dict) else value
            referenced = evidence.get('archive')
            if not isinstance(referenced, str):
                continue
            if referenced.startswith('/app/backups/'):
                referenced = str(backup_root / referenced.removeprefix('/app/backups/'))
            if referenced == str(archive):
                digest, size = evidence.get('archive_sha256'), evidence.get('archive_bytes')
                _need(isinstance(digest, str) and _HEX.fullmatch(digest) and type(size) is int and size > 0,
                      'backup_receipt_identity_missing')
                candidates.append((path, {'sha256': digest, 'size': size}))
    _need(candidates, 'backup_verification_receipt_missing')
    _need(len({(v['sha256'], v['size']) for _, v in candidates}) == 1, 'backup_verification_receipt_ambiguous')
    return candidates[0]


def _archive_proof(path: Path, receipt: dict, receipt_path: Path, *, active_markers=None) -> dict:
    from app.services.runtime_backup import verify_backup

    before = _safe(path)
    _need(before.st_nlink == 1 and before.st_size == receipt['size'], 'protected_archive_stat_mismatch')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    _need(h.hexdigest() == receipt['sha256'], 'protected_archive_digest_mismatch')
    try:
        manifest = verify_backup(path, maximum_manifest_bytes=16 * 1024**2, maximum_members=100001)
        members = {row['path']: row for row in manifest.get('files', [])}
        _need('data/.information-store-transition.json' not in members, 'protected_archive_transition_present')
        if receipt.get('store_schema') == 'legacy':
            _need(not any(name in members for name in ('data/information/store.json', 'inbox/.information-store.json')),
                  'protected_archive_store_schema_mismatch')
        elif receipt.get('store_schema') == 'unified-v1':
            _need(isinstance(active_markers, dict) and all(name in members and members[name].get('sha256') == pin['sha256']
                  for name, pin in active_markers.items()) and len(active_markers) == 2, 'protected_archive_store_schema_mismatch')
        else:
            raise StorageRecoveryError('protected_archive_store_schema_unsupported')
        with gzip.open(path, 'rb') as stream:
            for _block in iter(lambda: stream.read(4 * 1024**2), b''):
                pass
    except Exception:
        raise StorageRecoveryError('protected_archive_integrity_failed') from None
    _need(manifest.get('files') and manifest.get('scope') == ['data', 'inbox'], 'protected_archive_scope_invalid')
    after = _safe(path)
    before_key = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    _need(before_key == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'protected_archive_changed')
    return {**receipt, 'path': str(path), 'size': after.st_size, 'sha256': h.hexdigest(), 'verified': True,
            'device': after.st_dev, 'inode': after.st_ino, 'mtime_ns': after.st_mtime_ns,
            'uid': after.st_uid, 'gid': after.st_gid, 'mode': stat.S_IMODE(after.st_mode),
            'receipt_path': str(receipt_path), 'manifest_file_count': len(manifest['files'])}


def _inspect_app(caddy_id: str | None = None) -> dict:
    names = ['deploy-app-1', 'deploy-copilot-1']
    if caddy_id is not None:
        _need(isinstance(caddy_id, str) and _HEX.fullmatch(caddy_id), 'live_caddy_metadata_missing')
        names.append(caddy_id)
    run = subprocess.run(['docker', 'inspect', *names], input=b'', capture_output=True, timeout=30)
    _need(run.returncode == 0, 'live_app_inspection_failed')
    try:
        rows = json.loads(run.stdout)
    except ValueError:
        raise StorageRecoveryError('live_app_inspection_failed') from None
    _need(isinstance(rows, list) and len(rows) == len(names) and all(isinstance(row, dict) for row in rows), 'live_app_inspection_failed')
    app, node = rows[:2]
    app['_storage_recovery_sidecar'] = _sidecar_snapshot(node)
    if caddy_id is not None:
        _need(rows[2].get('Id') == caddy_id, 'live_caddy_metadata_missing')
        app['_storage_recovery_caddy'] = _caddy_snapshot(rows[2])
    return app


def _verify_images(current: dict, previous: dict) -> None:
    """Compatibility helper for the two application image bindings."""
    _verify_image_set({row['image']: row['source_sha'] for row in [current, previous]})


def _verify_image_set(expected: dict[str, str]) -> list[dict]:
    result = []
    for image, expected_source in sorted(expected.items()):
        _need(isinstance(image, str) and _IMAGE.fullmatch(image) and isinstance(expected_source, str)
              and _SOURCE.fullmatch(expected_source), 'recovery_image_metadata_invalid')
        run = subprocess.run(['docker', 'image', 'inspect', '--format',
            '{{json .Id}} {{json (index .Config.Labels "org.opencontainers.image.revision")}}', image],
            input='', capture_output=True, text=True, timeout=30)
        _need(run.returncode == 0, 'recovery_image_missing')
        try:
            actual_image, source = [json.loads(part) for part in run.stdout.strip().split(' ', 1)]
        except ValueError:
            raise StorageRecoveryError('recovery_image_metadata_invalid') from None
        _need(actual_image == image and source == expected_source, 'recovery_image_provenance_failed')
        result.append({'image': image, 'source_sha': source, 'exists': True, 'provenance_verified': True})
    return result


def verify_protected_image_provenance(provenance: list[dict]) -> list[dict]:
    """Recheck every immutable image/source pin without exposing image config."""
    _need(isinstance(provenance, list) and provenance, 'protected_image_provenance_missing')
    expected = {}
    for row in provenance:
        _need(isinstance(row, dict) and row.get('exists') is True and row.get('provenance_verified') is True,
              'protected_image_provenance_invalid')
        image, source = row.get('image'), row.get('source_sha')
        _need(isinstance(image, str) and _IMAGE.fullmatch(image) and isinstance(source, str)
              and _SOURCE.fullmatch(source) and image not in expected, 'protected_image_provenance_invalid')
        expected[image] = source
    return _verify_image_set(expected)


class _AcceptedFiles:
    """Track authenticated small metadata and stream opaque recovery inventories."""
    def __init__(self, read_file=None, stat_file=None):
        self.read_file, self.stat_file, self.pins, self.private_paths = read_file, stat_file or _safe, {}, set()
        self.absent_paths = set()

    def file(self, ref: dict, *, private=False, parse=False, maximum_bytes=None) -> bytes | None:
        _need(isinstance(ref, dict) and set(ref) in ({'path', 'sha256'}, {'path', 'sha256', 'mode'}), 'accepted_file_reference_invalid')
        name = _host_path(ref['path']); path = Path(name)
        _need(isinstance(ref['sha256'], str) and _HEX.fullmatch(ref['sha256']), 'accepted_file_reference_invalid')
        before = self.stat_file(path)
        mode = stat.S_IMODE(before.st_mode)
        maximum = 4 * 1024**2 if parse else 256 * 1024**2
        if maximum_bytes is not None:
            _need(type(maximum_bytes) is int and 0 < maximum_bytes <= 32 * 1024**2 and parse,
                  'accepted_parse_budget_invalid')
            maximum = maximum_bytes
        _need(stat.S_ISREG(before.st_mode) and getattr(before, 'st_nlink', 1) == 1
              and before.st_size <= maximum and not mode & 0o022,
              'accepted_file_permissions_or_bound_invalid')
        if private:
            _need(mode == 0o600 and getattr(before, 'st_uid', 0) == 0, 'accepted_private_file_invalid')
            self.private_paths.add(name)
        if 'mode' in ref:
            _need(type(ref['mode']) is int and 0 <= ref['mode'] <= 0o777 and mode == ref['mode'], 'accepted_file_mode_changed')
        read_file = self.read_file
        if read_file is not None and hasattr(read_file, 'handles'):
            _need(callable(read_file.handles), 'accepted_reader_selector_invalid')
            handled = read_file.handles(path)
            _need(type(handled) is bool, 'accepted_reader_selector_invalid')
            if not handled:
                read_file = None
        if read_file is not None or parse:
            if read_file is not None:
                body = read_file(path, maximum)
            else:
                fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                with os.fdopen(fd, 'rb') as handle:
                    opened = os.fstat(handle.fileno())
                    _need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'accepted_file_changed')
                    body = handle.read(maximum + 1)
            _need(isinstance(body, bytes) and len(body) == before.st_size, 'accepted_file_changed')
            digest = _sha(body)
        else:
            digest = hashlib.sha256(); count = 0
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(fd, 'rb') as handle:
                opened = os.fstat(handle.fileno())
                _need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), 'accepted_file_changed')
                for block in iter(lambda: handle.read(1024**2), b''):
                    count += len(block); _need(count <= maximum, 'accepted_file_permissions_or_bound_invalid'); digest.update(block)
            _need(count == before.st_size, 'accepted_file_changed')
            digest, body = digest.hexdigest(), None
        _need(digest == ref['sha256'], 'accepted_file_digest_mismatch')
        after = self.stat_file(path)
        key = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, stat.S_IMODE(info.st_mode),
                            getattr(info, 'st_uid', None), getattr(info, 'st_gid', None), getattr(info, 'st_nlink', 1))
        _need(key(before) == key(after), 'accepted_file_changed')
        pin = {'path': name, 'sha256': digest, 'mode': mode, 'size': before.st_size}
        _need(name not in self.pins or self.pins[name] == pin, 'accepted_file_reference_conflict')
        _need(len(self.pins) < 256 or name in self.pins, 'accepted_file_count_exceeded')
        self.pins[name] = pin
        return body

    def json(self, ref: dict, *, private=True, maximum_bytes=None) -> dict:
        return _parsed(self.file(ref, private=private, parse=True, maximum_bytes=maximum_bytes))

    def reread(self):
        expected = list(self.pins.values())
        for pin in expected:
            self.file({key: pin[key] for key in ('path', 'sha256', 'mode')}, private=pin['path'] in self.private_paths)
        for name in self.absent_paths:
            self.absent(Path(name))

    def absent(self, path):
        try:
            self.stat_file(path)
        except FileNotFoundError:
            self.absent_paths.add(str(path))
        else:
            raise StorageRecoveryError('accepted_store_transition_present')


def _pair_app(pair: dict) -> dict:
    _need(isinstance(pair, dict) and set(pair) == {'app', 'copilot'}
          and all(isinstance(row, dict) for row in pair.values()), 'accepted_pair_snapshot_invalid')
    app = dict(pair['app']); app['_storage_recovery_sidecar'] = _sidecar_snapshot(pair['copilot'])
    _need(recovery_live_binding(app)['healthy'], 'accepted_pair_snapshot_unhealthy')
    return app


def _native_pair_binding(pair: dict) -> dict:
    """The actual producer's documented partial projection; full hashes are separate."""
    result = {}
    keys = ('Type', 'Source', 'Destination', 'RW', 'Mode', 'Propagation')
    for name, row in pair.items():
        config, host = row['Config'], row['HostConfig']
        environment = config.get('Env') or []
        _need(isinstance(environment, list) and all(isinstance(value, str) and '=' in value for value in environment),
              'accepted_pair_environment_invalid')
        _need(len({value.split('=', 1)[0] for value in environment}) == len(environment), 'accepted_pair_environment_invalid')
        mounts = sorted(({key: mount.get(key) for key in keys} for mount in row['Mounts']), key=lambda mount: mount['Destination'])
        labels = {key: value for key, value in (config.get('Labels') or {}).items()
                  if key.startswith(('com.docker.compose.', 'berry.', 'org.opencontainers.image.'))}
        stable = {'Env': sorted(environment), 'Entrypoint': config.get('Entrypoint'), 'Cmd': config.get('Cmd'),
            'User': config.get('User'), 'Mounts': mounts, 'NetworkMode': host.get('NetworkMode'), 'Labels': labels,
            'Memory': host.get('Memory'), 'NanoCpus': host.get('NanoCpus'), 'RestartPolicy': host.get('RestartPolicy')}
        result[name] = {'id': row['Id'], 'image': row['Image'], 'config_sha256': _sha(_canonical(stable)),
            'environment_sha256': _sha(_canonical(stable['Env'])), 'mounts': mounts, 'network_mode': host.get('NetworkMode')}
    return result


def _accepted_configuration(value: dict, pair: dict, files: _AcceptedFiles) -> dict:
    _need(isinstance(value, dict) and set(value) == {'app', 'copilot'}, 'accepted_configuration_invalid')
    for name in ('app', 'copilot'):
        config = value[name]
        _need(isinstance(config, dict) and set(config) == {'compose_files', 'environment_files', 'dependency_files', 'project', 'working_dir'},
              'accepted_configuration_invalid')
        labels = pair[name]['Config'].get('Labels') or {}
        for field in ('compose_files', 'environment_files', 'dependency_files'):
            pins = config[field]
            _need(isinstance(pins, list) and (pins or field == 'dependency_files'), 'accepted_configuration_invalid')
            for pin in pins:
                _need(isinstance(pin, dict) and set(pin) == {'path', 'sha256', 'mode'}, 'accepted_configuration_pin_invalid')
                files.file(pin)
            _need(len({pin['path'] for pin in pins}) == len(pins), 'accepted_configuration_invalid')
        names = [pin['path'] for pin in config['compose_files']]
        _need(labels.get('com.docker.compose.project.config_files') == ','.join(names), 'accepted_compose_chain_mismatch')
        environment = labels.get('com.docker.compose.project.environment_file')
        if environment:
            selected = environment.split(',')
            _need([pin['path'] for pin in config['environment_files'] if pin['path'] in selected] == selected,
                  'accepted_environment_chain_mismatch')
        _need(isinstance(config['project'], str) and config['project']
              and labels.get('com.docker.compose.project') == config['project']
              and labels.get('com.docker.compose.project.working_dir') == _host_path(config['working_dir']),
              'accepted_compose_project_mismatch')
    return value


def _logging_pair(before: dict, after: dict, log_config: dict) -> None:
    """A configuration release may change logging and generated pair metadata."""
    from copy import deepcopy
    for name in before:
        old, new = before[name], after[name]
        _need(isinstance(old.get('Id'), str) and _HEX.fullmatch(old['Id'])
              and isinstance(new.get('Id'), str) and _HEX.fullmatch(new['Id']), 'configuration_only_container_identity_invalid')
        _need(old['Id'] != new['Id'], 'configuration_only_container_not_recreated')
        _need(old['Image'] == new['Image'] and sorted(old['Config'].get('Env') or []) == sorted(new['Config'].get('Env') or [])
              and sorted(old['Mounts'], key=_canonical) == sorted(new['Mounts'], key=_canonical), 'configuration_only_runtime_changed')
        a, b = deepcopy(old['Config']), deepcopy(new['Config'])
        a['Env'] = b['Env'] = sorted(old['Config'].get('Env') or [])
        a['Image'] = b['Image'] = new['Image']
        if a.get('Hostname') == old['Id'][:12]:
            _need(b.get('Hostname') == new['Id'][:12], 'configuration_only_runtime_changed')
            a['Hostname'] = b['Hostname'] = 'generated'
        if 'com.docker.compose.replace' in (b.get('Labels') or {}):
            _need(b['Labels']['com.docker.compose.replace'] == old['Id'], 'configuration_only_runtime_changed')
            for value in (a, b):
                value.setdefault('Labels', {}).pop('com.docker.compose.replace', None)
        for value in (a, b):
            labels = value.get('Labels') or {}
            value['Labels'] = {key: item for key, item in labels.items() if key not in {
                'com.docker.compose.config-hash', 'com.docker.compose.project.config_files', 'com.docker.compose.image'}}
        _need(a == b, 'configuration_only_runtime_changed')
        a, b = deepcopy(old['HostConfig']), deepcopy(new['HostConfig'])
        _need(b.get('LogConfig') == log_config, 'configuration_only_logging_unproven')
        a.pop('LogConfig', None); b.pop('LogConfig', None)
        if name == 'copilot':
            _need(b.get('NetworkMode') == 'container:' + after['app']['Id'], 'configuration_only_runtime_changed')
            a['NetworkMode'] = b['NetworkMode'] = 'paired'
        _need(a == b, 'configuration_only_runtime_changed')


def _configuration_only_proof(proof, plan, recovery, snapshots, wrapper, files, backup_root):
    from copy import deepcopy
    _need(proof.get('pair_snapshots') == wrapper['snapshots']
          and all(proof.get('configuration_post', {}).get(name) == wrapper['configuration']['post'][name]
                  for name in ('app', 'copilot')), 'configuration_only_snapshot_unproven')
    inherited = proof.get('inherited_storage_recovery') or {}
    _need(inherited.get('kind') == 'inherited-active-unified-store', 'configuration_only_storage_unproven')
    origin = files.json(inherited.get('origin_proof'))
    context = None
    if inherited.get('native_origin') is not None:
        context = _load_accepted_closure_checked(None, backup_root, read_file=files.read_file,
            stat_file=files.stat_file, native_wrapper_ref=inherited['native_origin'], shared_files=files)
        _need(context['wrapper']['recovery_files']['final_proof'] == inherited.get('origin_proof')
              and context['native_proof'] == origin, 'configuration_only_origin_unproven')
    else:
        _need(origin.get('state') == 'recovery-prepared' and origin.get('operation_kind') == 'unified-migration',
              'configuration_only_origin_unproven')
    for source, target in [('raw_plan', 'raw_plan'), ('raw_manifest', 'raw_manifest')]:
        _need(inherited.get(source) == recovery[target], 'configuration_only_storage_unproven')
    legacy = inherited.get('legacy_promotion_manifest') or {}
    _need(all(legacy.get(key) == recovery['legacy_promotion_manifest'][key] for key in ('path', 'sha256')),
          'configuration_only_storage_unproven')
    _need(inherited.get('migration') == origin.get('migration') and inherited.get('migration', {}).get('activated') is True,
          'configuration_only_storage_unproven')
    delta = proof.get('configuration_delta') or {}
    _need(delta.get('kind') == 'logging-only' and delta.get('services') == ['app', 'copilot', 'caddy']
          and delta.get('log_config') == {'Type': 'json-file', 'Config': {'max-size': '10m', 'max-file': '3'}},
          'configuration_only_logging_unproven')
    _logging_pair(snapshots['pre'], snapshots['post'], delta['log_config'])
    caddy = proof.get('caddy') or {}
    for name in ('pre_snapshot', 'post_snapshot', 'pre_configuration', 'post_configuration', 'barrier_handoff'):
        files.file(caddy.get(name), private=True)
    old_caddy, new_caddy = files.json(caddy['pre_snapshot']), files.json(caddy['post_snapshot'])
    _logging_pair({'caddy': old_caddy}, {'caddy': new_caddy}, delta['log_config'])
    configs = caddy.get('configuration') or {}
    _need(set(configs) == {'pre', 'post'}, 'configuration_only_caddy_unproven')
    _need(proof.get('configuration_post', {}).get('caddy') == configs['post'], 'configuration_only_caddy_unproven')
    for phase, row in [('pre', old_caddy), ('post', new_caddy)]:
        _accepted_configuration({'app': configs[phase], 'copilot': configs[phase]}, {'app': row, 'copilot': row}, files)
        for mount in row['Mounts']:
            source = _host_path(mount.get('Source'))
            _need(source in files.pins or source in wrapper['protected_dirs'], 'configuration_only_caddy_mount_unprotected')
    _need(caddy.get('original_config_sha256') == caddy['pre_configuration']['sha256'], 'configuration_only_caddy_unproven')
    handoff = files.json(caddy['barrier_handoff'])
    _need(handoff.get('old_container_id') == old_caddy['Id'] and handoff.get('new_container_id') == new_caddy['Id']
          and handoff.get('backend_stopped_during_handoff') is True
          and handoff.get('original_config_sha256') == caddy['original_config_sha256']
          and isinstance(handoff.get('new_contract'), dict) and isinstance(handoff.get('new_barrier_proof'), dict),
          'configuration_only_caddy_handoff_unproven')
    evidence = proof.get('configuration_preservation') or {}
    required = {'before_manifest', 'after_manifest', 'before_logical', 'after_logical', 'startup_audit', 'active_markers', 'physical_roots'}
    _need(set(evidence) == required, 'configuration_only_preservation_unproven')
    for name in ('before_manifest', 'after_manifest', 'before_logical', 'after_logical', 'startup_audit'):
        files.file(evidence[name])
    _need(evidence['before_manifest'] == proof.get('post_apply_manifest')
          and evidence['after_manifest'] == proof.get('post_startup_manifest')
          and evidence['before_logical']['sha256'] == evidence['after_logical']['sha256'], 'configuration_only_preservation_unproven')
    audit = files.json(evidence['startup_audit'])
    _need(audit.get('operation_kind') == 'configuration-only' and audit.get('nonce') == plan['nonce']
          and isinstance(audit.get('workspace_before'), dict) and audit['workspace_before'] == audit.get('workspace_after')
          and isinstance(audit.get('binary_invariant_before'), dict) and audit['binary_invariant_before'] == audit.get('binary_invariant_after')
          and isinstance(audit.get('mutations'), dict), 'configuration_only_preservation_unproven')
    allowed = plan.get('operational_allowlist', [])
    _need(isinstance(allowed, list) and all(isinstance(name, str) for name in allowed), 'configuration_only_preservation_unproven')
    for name, change in audit['mutations'].items():
        relative = PurePosixPath(name)
        _need(not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == name, 'configuration_only_mutation_unapproved')
        header = name == 'inbox/living_workspaces/workspace.sqlite3' and change.get('mechanism') == 'sqlite-header-counters-only'
        sensitive = any(part in relative.parts for part in ('evidence', 'attachments', 'information', 'reports', 'report_library', 'living_workspaces', 'workspaces'))
        _need(header or name in allowed and not sensitive and change.get('mechanism') == 'exact-operational-allowlist',
              'configuration_only_mutation_unapproved')
    markers = inherited.get('active_markers')
    _need(isinstance(markers, list) and markers and markers == evidence['active_markers'], 'configuration_only_store_changed')
    for pin in markers:
        files.file(pin)
        for phase in ('pre', 'post'):
            _need(pin in wrapper['configuration'][phase]['app']['dependency_files'], 'configuration_only_store_changed')
    roots = {row['Source'] for row in snapshots['post']['app']['Mounts']
             if row['Destination'] in {'/app/runtime/data', '/app/runtime/inbox', '/app/gene-delivery-source'}}
    _need(set(evidence['physical_roots']) == roots and set(inherited.get('protected_dirs', [])) <= set(wrapper['protected_dirs']),
          'configuration_only_store_changed')
    normalized = deepcopy(proof)
    normalized['migration'] = inherited['migration']
    normalized['raw_backup_seals'] = {'PLAN.private.json': inherited['raw_plan']['sha256'], 'MANIFEST.json': inherited['raw_manifest']['sha256']}
    normalized['legacy_promotion_manifest'] = legacy
    normalized['_accepted_caddy'] = new_caddy
    if context is not None:
        normalized['_accepted_native_directories'] = context['required_directories']
        normalized['_accepted_native_images'] = context['images']
    return normalized, inherited.get('rollback_modules'), origin


def _v2_closed(value, keys, reason):
    _need(isinstance(value, dict) and set(value) == set(keys), reason)


def _v2_int(value, minimum=0):
    return type(value) is int and value >= minimum


def _v2_preparation(value):
    _v2_closed(value, {'schema', 'state', 'encoding', 'path', 'sha256', 'canonical_sha256', 'source_fingerprint',
        'migration_id', 'bytes', 'largest_source_codepoint', 'counts', 'budget'}, 'replay_v2_preparation_invalid')
    _need(value['schema'] == 'berry.prepared-migration-plan.v1' and value['state'] == 'prepared' and value['encoding'] == 'ascii-json'
          and all(isinstance(value[key], str) and _HEX.fullmatch(value[key])
                  for key in ('sha256', 'canonical_sha256', 'source_fingerprint'))
          and value['migration_id'] == 'information-' + value['source_fingerprint'][:20]
          and _v2_int(value['bytes'], 1) and _v2_int(value['largest_source_codepoint'])
          and value['largest_source_codepoint'] <= 0x10ffff, 'replay_v2_preparation_invalid')
    _host_path(value['path'])
    _v2_closed(value['counts'], {'records', 'variants', 'source_files', 'assets', 'cache_envelopes', 'public', 'private'},
        'replay_v2_preparation_invalid')
    _need(all(_v2_int(count) for count in value['counts'].values())
          and value['counts']['records'] == value['counts']['public'] + value['counts']['private']
          and isinstance(value['budget'], dict) and value['budget'].get('schema') == 'berry.prepared-migration-budget.v1'
          and value['budget'].get('fits') is True, 'replay_v2_preparation_invalid')
    budget = value['budget']
    _need(type(budget.get('disk_floor_bytes')) is int and budget['disk_floor_bytes'] == 10 * 1024**3
          and _v2_int(budget.get('future_upper_bound')) and _v2_int(budget.get('total_phase_upper_bound'))
          and budget['total_phase_upper_bound'] >= budget['future_upper_bound']
          and _v2_int(budget.get('free_bytes')) and budget['free_bytes'] >= budget['disk_floor_bytes'] + budget['future_upper_bound']
          and (budget.get('phase_budget_bytes') is None or _v2_int(budget['phase_budget_bytes'], 1)
               and budget['total_phase_upper_bound'] <= budget['phase_budget_bytes']), 'replay_v2_preparation_invalid')
    return value


def _v2_metadata(protocol, source, archive, files):
    metadata = protocol['source_metadata']
    _v2_closed(metadata, {'from', 'source_receipt', 'timestamp_sidecar', 'program', 'verify_archive_member_coverage',
        'verify_size_sha256_mode_before_metadata', 'restore_mtime_ns', 'reject_unknown_roots_and_unsafe_paths',
        'release_buffers_before_plan'}, 'replay_v2_metadata_invalid')
    _need(metadata['from'] == 'source-receipt.source_manifest+timestamp-sidecar.source_mtime_ns'
          and all(metadata[key] is True for key in ('verify_archive_member_coverage', 'verify_size_sha256_mode_before_metadata',
              'restore_mtime_ns', 'reject_unknown_roots_and_unsafe_paths', 'release_buffers_before_plan'))
          and metadata['source_receipt'] == source.get('source_receipt')
          and metadata['timestamp_sidecar'].get('sha256') == source.get('offhost_archive', {}).get('timestamps', {}).get('sha256'),
          'replay_v2_metadata_invalid')
    files.file(metadata['program'])
    receipt = files.json(metadata['source_receipt'], maximum_bytes=16 * 1024**2)
    times = files.json(metadata['timestamp_sidecar'], maximum_bytes=16 * 1024**2)
    rows, stamps = receipt.get('source_manifest'), times.get('source_mtime_ns')
    _need(isinstance(rows, dict) and rows and isinstance(stamps, dict) and set(rows) == set(stamps), 'replay_v2_metadata_invalid')
    total, largest = 0, 0
    for name, row in rows.items():
        path = PurePosixPath(name)
        _need(isinstance(name, str) and path.as_posix() == name and not path.is_absolute() and len(path.parts) >= 2
              and path.parts[0] in {'data', 'inbox'} and '..' not in path.parts and '\\' not in name and '\x00' not in name,
              'replay_v2_metadata_invalid')
        _v2_closed(row, {'sha256', 'size', 'mode'}, 'replay_v2_metadata_invalid')
        _need(isinstance(row['sha256'], str) and _HEX.fullmatch(row['sha256']) and _v2_int(row['size'])
              and _v2_int(row['mode']) and row['mode'] <= 0o777 and type(stamps[name]) is int
              and -(2**63) <= stamps[name] < 2**63, 'replay_v2_metadata_invalid')
        total += row['size']; largest = max(largest, max(map(ord, name)))
    inventory, timestamp = _sha(_canonical(rows)), _sha(_canonical(stamps))
    _need(receipt.get('source_stable') is times.get('source_stable') is times.get('source_mtime_stable') is True
          and receipt.get('nonce') == source.get('nonce') and receipt.get('candidate_image') == protocol['image']
          and receipt.get('archive', {}).get('archive_sha256') == archive['sha256']
          and all(value == inventory for value in (receipt.get('source_inventory_sha256'), receipt.get('source_inventory_after_sha256'),
              times.get('source_inventory_sha256'), times.get('source_inventory_after_sha256')))
          and times.get('source_mtime_ns_sha256') == times.get('source_mtime_ns_after_sha256') == timestamp
          and receipt.get('archive', {}).get('timestamps', {}).get('digest') == timestamp
          and _canonical(times.get('archive')) == _canonical({key: value for key, value in receipt['archive'].items() if key != 'timestamps'}),
          'replay_v2_metadata_invalid')
    return {'source_inventory_sha256': inventory, 'timestamp_digest': timestamp, 'files': len(rows), 'bytes': total,
        'source_receipt_bytes': files.pins[metadata['source_receipt']['path']]['size'],
        'timestamp_sidecar_bytes': files.pins[metadata['timestamp_sidecar']['path']]['size'],
        'largest_relative_path_codepoint': largest}


def _v2_apply(value, prepared):
    _v2_closed(value, {'resume_id', 'migration_id', 'plan_calls', 'aggregate_plan_writes', 'before_plan_sha256',
        'after_plan_sha256', 'before_plan_bytes', 'after_plan_bytes'}, 'replay_v2_apply_invalid')
    _need(value['resume_id'] == value['migration_id'] == prepared['migration_id']
          and type(value['plan_calls']) is int and value['plan_calls'] == 1
          and type(value['aggregate_plan_writes']) is int and value['aggregate_plan_writes'] == 0
          and value['before_plan_sha256'] == value['after_plan_sha256'] == prepared['sha256']
          and type(value['before_plan_bytes']) is int and type(value['after_plan_bytes']) is int
          and value['before_plan_bytes'] == value['after_plan_bytes'] == prepared['bytes'], 'replay_v2_apply_invalid')


def _v2_command(config, inspection, protocol, protocol_ref, recipe, files, mode, *, resource_config=None, workspace=None):
    """Bind direct isolated Python to the actual read-only code/input mounts."""
    _v2_closed(config, {'schema', 'source_mode', 'image', 'source_sha', 'program', 'protocol', 'recipe_input',
        'preparer', 'metadata', 'output_dir', 'work_dir'}, 'replay_v2_execution_invalid')
    _need(config['schema'] == 'berry.migration-replay-functional-config.v2' and config['source_mode'] == 'app'
          and config['image'] == protocol['image'] and config['source_sha'] == protocol['source_sha']
          and config['program'] == protocol['program'] and config['protocol'] == protocol_ref
          and config['preparer'] == protocol['plan']['program'] and config['metadata'] == protocol['source_metadata']['program'],
          'replay_v2_execution_invalid')
    supplied = files.json(config['recipe_input'])
    _v2_closed(supplied, {'schema', 'candidate_image', 'source_sha', 'replay_protocol', 'operator_modules', 'raw_plan'},
        'replay_v2_execution_invalid')
    _need(supplied['schema'] == 'berry.migration-replay-input.v2'
          and all(_canonical(supplied[key]) == _canonical(recipe[key])
                  for key in ('candidate_image', 'source_sha', 'replay_protocol', 'operator_modules', 'raw_plan')),
          'replay_v2_execution_invalid')
    output, work = _host_path(config['output_dir']), _host_path(config['work_dir'])
    arguments = ['-I', '-B', config['program']['path'], mode, '--protocol', protocol_ref['path'], '--protocol-sha256', protocol_ref['sha256'],
        '--recipe', config['recipe_input']['path'], '--recipe-sha256', config['recipe_input']['sha256'],
        '--output-dir', output, '--work-dir', work]
    if mode == '--prepare-apply-only':
        _need(resource_config is not None and workspace is not None, 'replay_v2_execution_invalid')
        _host_path(resource_config['backup_dir'])
        _need(PurePosixPath(resource_config['backup_dir']).is_relative_to(work)
              and PurePosixPath(resource_config['backup_dir']) != PurePosixPath(work), 'replay_v2_execution_invalid')
        arguments += ['--runtime-dir', str(PurePosixPath(resource_config['data_dir']).parent),
            '--backup-base', str(PurePosixPath(resource_config['backup_dir']) / 'migration-backups'),
            '--scratch-dir', str(PurePosixPath(resource_config['backup_dir']) / 'scratch')]
    raw_config = inspection.get('Config') or {}
    _need(raw_config.get('Entrypoint') in (None, []) and raw_config.get('Cmd') == ['python3', *arguments]
          and inspection.get('Path') == 'python3' and inspection.get('Args') == arguments
          and not inspection.get('HostConfig', {}).get('Tmpfs') and not raw_config.get('Volumes'), 'replay_v2_execution_invalid')
    required = [config[key] for key in ('program', 'protocol', 'recipe_input', 'preparer', 'metadata')]
    required += [protocol['plan']['original_preparation_receipt'], protocol['source_metadata']['source_receipt'],
                 protocol['source_metadata']['timestamp_sidecar']]
    rows = inspection.get('Mounts')
    _need(isinstance(rows, list) and all(isinstance(row, dict) and row.get('Type') == 'bind' for row in rows),
          'replay_v2_execution_invalid')
    mounts = {_host_path(row.get('Destination')): row for row in rows}
    _need(len(mounts) == len(rows), 'replay_v2_execution_invalid')
    allowed = {ref['path'] for ref in required} | {output, work}
    if workspace is not None: allowed.add('/app/runtime')
    _need(set(mounts) == allowed, 'replay_v2_execution_invalid')
    for ref in required:
        row = mounts[ref['path']]
        _need(_host_path(row.get('Source')) == ref['path'] and row.get('RW') is False, 'replay_v2_execution_invalid')
        files.file(ref)
    for name, row in mounts.items():
        path = PurePosixPath(name)
        overlaps_app = path.is_relative_to('/app') or PurePosixPath('/app').is_relative_to(path)
        _need(not overlaps_app or workspace is not None and name == '/app/runtime'
              and Path(_host_path(row.get('Source'))) == workspace and row.get('RW') is True, 'replay_v2_execution_invalid')
    _need(mounts[output].get('RW') is True and mounts[work].get('RW') is True, 'replay_v2_execution_invalid')
    output_host, work_host = Path(_host_path(mounts[output].get('Source'))), Path(_host_path(mounts[work].get('Source')))
    _need(not output_host.is_relative_to(work_host) and not work_host.is_relative_to(output_host)
          and all(not Path(ref['path']).is_relative_to(output_host) and not Path(ref['path']).is_relative_to(work_host) for ref in required),
          'replay_v2_execution_invalid')
    if workspace is not None:
        _need(not output_host.is_relative_to(workspace) and not workspace.is_relative_to(output_host)
              and not work_host.is_relative_to(workspace) and not workspace.is_relative_to(work_host), 'replay_v2_execution_invalid')
    return output_host, work_host, mounts


def _v2_functional_execution(ref, protocol, recipe, verified, native, files):
    execution = files.json(ref)
    _v2_closed(execution, {'schema', 'state', 'completion', 'inspection', 'config', 'result'}, 'replay_v2_execution_invalid')
    _need(execution['schema'] == 'berry.migration-replay-functional-execution.v2' and execution['state'] == 'passed'
          and execution['result'] == verified['native_receipt'], 'replay_v2_execution_invalid')
    completion = files.json(execution['completion']); inspection = files.json(execution['inspection']); config = files.json(execution['config'])
    _v2_closed(completion, {'schema', 'state', 'container_id', 'image', 'source_sha', 'program_sha256', 'config_sha256',
        'result_sha256', 'inspection_sha256', 'helper_exit', 'oom_killed'}, 'replay_v2_execution_invalid')
    state = inspection.get('State') or {}
    _need(completion['schema'] == 'berry.migration-replay-functional-complete.v2' and completion['state'] == 'passed'
          and isinstance(completion['container_id'], str) and _HEX.fullmatch(completion['container_id'])
          and completion['container_id'] == inspection.get('Id') and completion['image'] == inspection.get('Image') == protocol['image']
          and completion['source_sha'] == protocol['source_sha'] and completion['program_sha256'] == protocol['program']['sha256']
          and completion['config_sha256'] == execution['config']['sha256']
          and completion['result_sha256'] == execution['result']['sha256']
          and completion['inspection_sha256'] == execution['inspection']['sha256']
          and type(completion['helper_exit']) is int and completion['helper_exit'] == 0 and completion['oom_killed'] is False
          and state.get('Running') is False and state.get('Status') == 'exited' and type(state.get('ExitCode')) is int
          and state['ExitCode'] == 0 and state.get('OOMKilled') is False, 'replay_v2_execution_invalid')
    output, work, mounts = _v2_command(config, inspection, protocol, recipe['replay_protocol'], recipe, files, '--fixture-only')
    _need(Path(verified['native_receipt']['path']).is_relative_to(output)
          and Path(verified['preparation_receipt']['path']).is_relative_to(output)
          and native['roots']['proof_dir'] == config['output_dir'], 'replay_v2_execution_invalid')
    observed = PurePosixPath(_host_path(native['prepared_plan']['receipt_path']))
    _need(observed.is_relative_to(config['output_dir'])
          and output.joinpath(*observed.relative_to(config['output_dir']).parts) == Path(verified['preparation_receipt']['path']),
          'replay_v2_execution_invalid')


def _v2_kernel(execution, completion, program_sha, protocol, files):
    inspection, config, phase, result = [files.json(execution[key]) for key in ('inspection', 'config', 'phase', 'result')]
    kernel = files.json(execution['kernel'])
    _v2_closed(kernel, {'schema', 'state', 'container_id', 'initial_inspection', 'observer', 'init_pid', 'proc_cgroup_path',
        'cgroup_path', 'memory_max_bytes', 'swap_max_bytes', 'memory_peak_bytes', 'events_before', 'events_after',
        'populated_after', 'result_sha256'}, 'replay_v2_kernel_invalid')
    initial = files.json(kernel['initial_inspection']); files.file(kernel['observer'])
    identifier = completion.get('container_id'); state = inspection.get('State') or {}; start = initial.get('State') or {}
    limit = kernel['memory_max_bytes']; swap = kernel['swap_max_bytes']
    _need(kernel['schema'] == 'berry.migration-replay-kernel.v2' and kernel['state'] == 'verified'
          and isinstance(identifier, str) and _HEX.fullmatch(identifier)
          and identifier == inspection.get('Id') == initial.get('Id') == kernel['container_id'] == phase.get('ephemeral', {}).get('id')
          and inspection.get('Image') == initial.get('Image') == completion.get('image') == phase.get('ephemeral', {}).get('image') == protocol['image']
          and completion.get('state') == 'passed' and completion.get('program_sha256') == program_sha
          and completion.get('config_sha256') == execution['config']['sha256']
          and completion.get('phase_sha256') == execution['phase']['sha256']
          and config.get('policy', {}).get('program_sha256') == program_sha
          and config.get('policy', {}).get('source_sha') == protocol['source_sha']
          and all(type(completion.get(key)) is int and completion[key] == 0 for key in ('helper_exit', 'watcher_exit'))
          and completion.get('oom_killed') is False and state.get('Running') is False and state.get('Status') == 'exited'
          and type(state.get('ExitCode')) is int and state['ExitCode'] == 0 and state.get('OOMKilled') is False
          and start.get('Running') is True and _v2_int(kernel['init_pid'], 1)
          and type(start.get('Pid')) is int and start['Pid'] == kernel['init_pid']
          and isinstance(start.get('StartedAt'), str) and bool(start['StartedAt']) and not start['StartedAt'].startswith('0001-')
          and start['StartedAt'] == state.get('StartedAt') and isinstance(state.get('FinishedAt'), str)
          and bool(state['FinishedAt']) and not state['FinishedAt'].startswith('0001-')
          and _v2_int(limit, 1) and limit <= 448 * 1024**2 and type(swap) is int and swap == 0
          and type(completion.get('memory_cap_mib')) is int and completion['memory_cap_mib'] * 1024**2 == limit
          and _v2_int(kernel['memory_peak_bytes'], 1) and kernel['memory_peak_bytes'] <= limit
          and kernel['populated_after'] is False and kernel['result_sha256'] == execution['result']['sha256'], 'replay_v2_kernel_invalid')
    for row in (initial, inspection):
        host = row.get('HostConfig') or {}
        _need(type(host.get('Memory')) is int and host['Memory'] == limit
              and type(host.get('MemorySwap')) is int and host['MemorySwap'] == limit + swap, 'replay_v2_kernel_invalid')
    group = _host_path(kernel['proc_cgroup_path'])
    _need(kernel['cgroup_path'] == '/sys/fs/cgroup' + group and identifier in PurePosixPath(group).name, 'replay_v2_kernel_invalid')
    for key in ('events_before', 'events_after'):
        _v2_closed(kernel[key], {'oom', 'oom_kill'}, 'replay_v2_kernel_invalid')
        _need(all(type(value) is int and value == 0 for value in kernel[key].values()), 'replay_v2_kernel_invalid')
    _need(kernel['events_before'] == kernel['events_after'], 'replay_v2_kernel_invalid')
    return inspection, config, phase, result


def _v2_resources(ref, protocol, verified, native_plan, original, stats, source, recipe, files):
    initial_pins = set(files.pins)
    evidence = files.json(ref)
    _v2_closed(evidence, {'schema', 'mode', 'metadata_execution', 'prepare_apply_execution'}, 'replay_v2_resource_invalid')
    _need(evidence['schema'] == 'berry.migration-replay-resource.v2'
          and evidence['mode'] in {'composed-native', 'owned-qualification'}, 'replay_v2_resource_invalid')
    roles = {}
    for role in ('metadata_execution', 'prepare_apply_execution'):
        execution = evidence[role]
        _v2_closed(execution, {'completion', 'inspection', 'kernel', 'config', 'phase', 'result'}, 'replay_v2_resource_invalid')
        completion = files.json(execution['completion'])
        if role == 'prepare_apply_execution' and evidence['mode'] == 'owned-qualification':
            _v2_closed(completion, {'schema', 'state', 'nonce', 'image', 'source_sha', 'protocol_sha256', 'program_sha256',
                'original_preparation_receipt', 'source_receipt', 'timestamp_sidecar', 'native_completion', 'inspection',
                'kernel', 'config', 'phase', 'result', 'workspace_root', 'backup_base_before'}, 'replay_v2_qualification_invalid')
            _need(completion['schema'] == 'berry.migration-replay-qualification-complete.v2' and completion['state'] == 'passed'
                  and isinstance(completion['nonce'], str) and re.fullmatch('[a-f0-9]{32,64}', completion['nonce'])
                  and completion['image'] == protocol['image'] and completion['source_sha'] == protocol['source_sha']
                  and completion['protocol_sha256'] == verified['protocol_sha256']
                  and completion['program_sha256'] == protocol['program']['sha256']
                  and completion['original_preparation_receipt'] == protocol['plan']['original_preparation_receipt']
                  and all(completion[key] == protocol['source_metadata'][key] for key in ('source_receipt', 'timestamp_sidecar'))
                  and all(completion[key] == execution[key] for key in ('inspection', 'kernel', 'config', 'phase', 'result')),
                  'replay_v2_qualification_invalid')
            qualification = completion
            completion = files.json(qualification['native_completion'])
        else:
            qualification = None
        program_sha = protocol['program']['sha256'] if role == 'metadata_execution' or qualification is not None else protocol['plan']['program']['sha256']
        inspection, config, phase, result = _v2_kernel(execution, completion, program_sha, protocol, files)
        if role == 'metadata_execution' or qualification is not None:
            policy = config.get('policy') or {}
            _need(policy.get('metadata_program_sha256') == protocol['source_metadata']['program']['sha256']
                  and policy.get('preparer_sha256') == protocol['plan']['program']['sha256'], 'replay_v2_execution_invalid')
            output, work, _ = _v2_command(policy.get('replay_execution'), inspection, protocol, recipe['replay_protocol'], recipe,
                files, '--metadata-allocation' if role == 'metadata_execution' else '--prepare-apply-only',
                resource_config=config if qualification is not None else None,
                workspace=Path(_host_path(qualification['workspace_root'])) if qualification is not None else None)
            _need(Path(execution['result']['path']).is_relative_to(output), 'replay_v2_execution_invalid')
        _need(_canonical(completion.get('counts')) == _canonical(result.get('counts'))
              and isinstance(completion.get('counts'), dict) and isinstance(completion.get('hashes'), dict)
              and result.get('state') == 'passed'
              and _canonical(completion.get('hashes')) == _canonical(result.get('hashes')), 'replay_v2_resource_result_invalid')
        roles[role] = execution, completion, inspection, config, phase, result, qualification
    execution, completion, inspection, config, phase, result, _ = roles['metadata_execution']
    _v2_closed(result, {'state', 'counts', 'hashes', 'artifacts'}, 'replay_v2_metadata_resource_invalid')
    _v2_closed(result['counts'], {'files', 'bytes'}, 'replay_v2_metadata_resource_invalid')
    _v2_closed(result['hashes'], {'inventory', 'timestamp'}, 'replay_v2_metadata_resource_invalid')
    _v2_closed(result['artifacts'], {'metadata_allocation'}, 'replay_v2_metadata_resource_invalid')
    metadata = result.get('artifacts', {}).get('metadata_allocation')
    _v2_closed(metadata, {'schema', 'state', 'source_receipt', 'timestamp_sidecar', *stats, 'validated_entries',
        'maps_released_before_plan', 'stream_buffer_bytes'}, 'replay_v2_metadata_resource_invalid')
    _need(metadata['schema'] == 'berry.migration-replay-metadata-allocation.v2' and metadata['state'] == 'passed'
          and all(metadata[key] == protocol['source_metadata'][key] for key in ('source_receipt', 'timestamp_sidecar'))
          and all(type(metadata[key]) is type(value) and metadata[key] == value for key, value in stats.items())
          and type(metadata['validated_entries']) is int and metadata['validated_entries'] == stats['files']
          and metadata['maps_released_before_plan'] is True and type(metadata['stream_buffer_bytes']) is int
          and metadata['stream_buffer_bytes'] == 2 * 1024**2
          and all(type(result['counts'][key]) is int and result['counts'][key] == stats[key] for key in ('files', 'bytes'))
          and result['hashes'] == {'inventory': stats['source_inventory_sha256'], 'timestamp': stats['timestamp_digest']}
          and completion.get('result_sha256') == execution['result']['sha256'], 'replay_v2_metadata_resource_invalid')
    execution, completion, inspection, config, phase, result, qualification = roles['prepare_apply_execution']
    observed = _v2_preparation(result.get('artifacts', {}).get('prepared_migration_plan'))
    if qualification is None:
        _v2_closed(result.get('artifacts'), {'full_file_manifests', 'snapshot_spills', 'prepared_migration_plan'},
            'replay_v2_resource_result_invalid')
        rehearsal = files.json(native_plan.get('proofs', {}).get('rehearsal'))
        native = rehearsal.get('native_evidence') or {}
        _need(native.get('rehearsal', {}).get('sha256') == execution['completion']['sha256']
              and native.get('rehearsal_helper_stdout', {}).get('sha256') == execution['result']['sha256']
              and _canonical(rehearsal.get('http_coverage', {}).get('evidence', {}).get('rehearsal_helper_stdout')) ==
                  _canonical(native.get('rehearsal_helper_stdout'))
              and native.get('rehearsal_config', {}).get('sha256') == execution['config']['sha256']
              and native.get('rehearsal_phase', {}).get('sha256') == execution['phase']['sha256'], 'replay_v2_native_reuse_unanchored')
        _need(result.get('state') == 'passed' and all(_v2_int(observed['counts'][key])
              and observed['counts'][key] >= value for key, value in original['counts'].items())
              and observed['bytes'] >= original['bytes'] and observed['largest_source_codepoint'] >= original['largest_source_codepoint']
              and _v2_int(result.get('counts', {}).get('original_files')) and result['counts']['original_files'] >= stats['files']
              and all(type(result.get('counts', {}).get(key)) is int and type(config.get('policy', {}).get(expected)) is int
                      and result['counts'][key] == config['policy'][expected]
                      for key, expected in [('reports', 'expected_report_count'), ('workspaces', 'expected_workspace_count')])
              and all(type(result.get('counts', {}).get(key)) is int and result['counts'][key] == observed['counts'][key]
                      for key in ('records', 'variants', 'assets')),
              'replay_v2_workload_not_covered')
    else:
        _v2_closed(result, {'schema', 'state', 'image', 'source_sha', 'program_sha256', 'preparer_sha256', 'counts',
            'hashes', 'artifacts', 'apply'}, 'replay_v2_qualification_invalid')
        _need(result['schema'] == 'berry.migration-replay-prepare-apply.v2' and result['state'] == 'passed'
              and result['image'] == protocol['image'] and result['source_sha'] == protocol['source_sha']
              and result['program_sha256'] == protocol['program']['sha256']
              and result['preparer_sha256'] == config.get('policy', {}).get('preparer_sha256') == protocol['plan']['program']['sha256']
              and all(_canonical(observed[key]) == _canonical(original[key]) for key in
                  ('sha256', 'canonical_sha256', 'source_fingerprint', 'migration_id', 'bytes', 'counts', 'largest_source_codepoint'))
              and result['hashes'].get('source_inventory_sha256') == stats['source_inventory_sha256']
              and result['hashes'].get('timestamp_digest') == stats['timestamp_digest'], 'replay_v2_workload_not_covered')
        _v2_closed(result['artifacts'], {'prepared_migration_plan'}, 'replay_v2_qualification_invalid')
        _v2_closed(result['hashes'], {'source_inventory_sha256', 'timestamp_digest', 'before_plan_sha256', 'after_plan_sha256'},
            'replay_v2_qualification_invalid')
        _need(_canonical(result['counts']) == _canonical(observed['counts'])
              and result['hashes']['before_plan_sha256'] == result['hashes']['after_plan_sha256'] == observed['sha256'],
              'replay_v2_qualification_invalid')
        _v2_apply(result['apply'], observed)
        workspace = Path(_host_path(qualification['workspace_root']))
        before = qualification['backup_base_before']
        _v2_closed(before, {'path', 'device', 'inode', 'entries', 'observed_before_prepare'}, 'replay_v2_qualification_invalid')
        _need(_v2_int(before['device']) and _v2_int(before['inode'], 1) and before['entries'] == []
              and before['observed_before_prepare'] is True, 'replay_v2_qualification_invalid')
        def mapped(container_path):
            path = PurePosixPath(_host_path(container_path))
            choices = [row for row in inspection.get('Mounts', []) if row.get('Type') == 'bind'
                       and path.is_relative_to(PurePosixPath(row.get('Destination', '')))]
            _need(choices, 'replay_v2_qualification_invalid')
            row = max(choices, key=lambda item: len(PurePosixPath(item['Destination']).parts))
            return Path(_host_path(row['Source'])).joinpath(*path.relative_to(row['Destination']).parts)
        _need(mapped(config['data_dir']) == workspace / 'data' and mapped(config['inbox_dir']) == workspace / 'inbox'
              and observed['path'] == str(PurePosixPath(config['backup_dir']) / 'migration-backups' /
                  observed['migration_id'] / 'PLAN.private.json')
              and mapped(str(PurePosixPath(config['backup_dir']) / 'migration-backups')) == Path(_host_path(before['path'])),
              'replay_v2_qualification_invalid')
        for mount in source.get('old_binding', {}).get('app', {}).get('mounts', []):
            if mount.get('Destination') in {'/app/runtime/data', '/app/runtime/inbox'}:
                active = Path(_host_path(mount['Source']))
                _need(not workspace.is_relative_to(active) and not active.is_relative_to(workspace), 'replay_v2_qualification_invalid')
        # Durable receipts survive retirement; observed PLAN/workspace paths do
        # not become generic file pins or permanent runtime-copy dependencies.
        for role in roles.values():
            for pin in role[0].values():
                _need(not Path(_host_path(pin['path'])).is_relative_to(workspace), 'replay_v2_qualification_invalid')
        _need(all(not Path(path).is_relative_to(workspace) for path in set(files.pins) - initial_pins),
              'replay_v2_qualification_invalid')


def _replay_protocol_v2(protocol, verified, recipe, archive, recovery, source, proof, plan, files):
    _v2_closed(protocol, {'schema', 'image', 'source_sha', 'restore', 'source_metadata', 'plan', 'apply', 'verification',
        'original_migration_id_is_provenance_only', 'program'}, 'replay_v2_protocol_invalid')
    _need(protocol['image'] == recipe['candidate_image'] and protocol['source_sha'] == recipe['source_sha']
          and _canonical(protocol['restore']) == _canonical({'module': 'app.services.runtime_backup', 'function': 'restore_backup', 'require_empty': True})
          and _canonical(protocol['apply']) == _canonical({'module': 'app.services.information_migration', 'function': 'apply_migration', 'quiesced': True,
              'resume_id': 'this-prepared-plan.migration_id', 'no_replan': True, 'no_aggregate_plan_rewrite': True})
          and protocol['verification'] == ['current-store', 'winner-and-variants', 'analyst-decisions', 'all-protected-runtime-state']
          and protocol['original_migration_id_is_provenance_only'] is True, 'replay_v2_protocol_invalid')
    preparing = protocol['plan']
    _v2_closed(preparing, {'module', 'function', 'program', 'original_preparation_receipt', 'fresh_runtime_paths',
        'new_empty_backup_base', 'encoding', 'exclusive_prepared_plan'}, 'replay_v2_protocol_invalid')
    _need(preparing['module'] == 'accepted-preservation-helper' and preparing['function'] == 'prepare_migration_plan'
          and preparing['program'] == recipe['operator_modules'].get('preservation')
          and preparing['fresh_runtime_paths'] is preparing['new_empty_backup_base'] is preparing['exclusive_prepared_plan'] is True
          and preparing['encoding'] == 'ascii-json', 'replay_v2_protocol_invalid')
    files.file(preparing['program']); files.file(protocol['program'])
    _need(preparing['original_preparation_receipt']['path'] == str(Path(recovery['raw_plan']['path']).with_name('PLAN-preparation.private.json')),
          'replay_v2_original_preparation_invalid')
    original = _v2_preparation(files.json(preparing['original_preparation_receipt'], private=False))
    _need(original['sha256'] == recovery['raw_plan']['sha256']
          and original['path'] == str(PurePosixPath(source['migration']['backup_path']) / 'PLAN.private.json')
          and original['migration_id'] == source['migration']['migration_id'], 'replay_v2_original_preparation_invalid')
    stats = _v2_metadata(protocol, source, archive, files)
    _v2_closed(verified, {'schema', 'state', 'image', 'source_sha', 'protocol_sha256', 'program_sha256', 'checks',
        'test_program', 'native_receipt', 'native_execution', 'preparation_receipt', 'resource_evidence'}, 'replay_v2_verification_invalid')
    _need(verified['schema'] == 'berry.migration-replay-verification.v2' and verified['state'] == 'passed'
          and verified['image'] == recipe['candidate_image'] and verified['source_sha'] == recipe['source_sha']
          and verified['protocol_sha256'] == recipe['replay_protocol']['sha256']
          and verified['program_sha256'] == protocol['program']['sha256']
          and isinstance(verified['checks'], dict) and set(verified['checks']) == REPLAY_V2_CHECKS
          and all(value is True for value in verified['checks'].values()), 'replay_v2_verification_invalid')
    files.file(verified['test_program'])
    native = files.json(verified['native_receipt'])
    _v2_closed(native, {'schema', 'state', 'fixture_only', 'execution_context', 'image', 'source_sha', 'protocol_sha256',
        'program_sha256', 'preparer_sha256', 'module_sha256', 'roots', 'source_metadata', 'prepared_plan', 'apply', 'checks'},
        'replay_v2_native_invalid')
    _need(native['schema'] == 'berry.migration-replay-native.v2' and native['state'] == 'passed'
          and native['fixture_only'] is True and native['execution_context'] == 'app-modules-fixture'
          and all(_canonical(native[key]) == _canonical(verified[key]) for key in ('image', 'source_sha', 'protocol_sha256', 'program_sha256', 'checks'))
          and native['preparer_sha256'] == preparing['program']['sha256'], 'replay_v2_native_invalid')
    _v2_closed(native['module_sha256'], {'runtime_backup', 'information_migration', 'information_storage', 'metadata'}, 'replay_v2_native_invalid')
    _need(all(isinstance(value, str) and _HEX.fullmatch(value) for value in native['module_sha256'].values())
          and native['module_sha256']['metadata'] == protocol['source_metadata']['program']['sha256'], 'replay_v2_native_invalid')
    roots = native['roots']
    _v2_closed(roots, {'runtime', 'data', 'inbox', 'backup_base', 'proof_dir', 'fresh_runtime', 'new_empty_backup_base'}, 'replay_v2_native_invalid')
    for key in ('runtime', 'data', 'inbox', 'backup_base', 'proof_dir'):
        _host_path(roots[key])
    _need(roots['fresh_runtime'] is roots['new_empty_backup_base'] is True
          and Path(roots['data']) == Path(roots['runtime']) / 'data' and Path(roots['inbox']) == Path(roots['runtime']) / 'inbox'
          and all(not Path(roots['backup_base']).is_relative_to(Path(roots[key])) for key in ('data', 'inbox')),
          'replay_v2_native_invalid')
    prepared = _v2_preparation(files.json(verified['preparation_receipt']))
    observed = native['prepared_plan']
    _v2_closed(observed, {'path', 'receipt_path', 'receipt_sha256', 'sha256', 'canonical_sha256', 'source_fingerprint',
        'migration_id', 'bytes', 'counts', 'largest_source_codepoint'}, 'replay_v2_native_invalid')
    _need(all(_canonical(observed[key]) == _canonical(prepared[key]) for key in observed if key not in {'receipt_path', 'receipt_sha256'})
          and observed['receipt_sha256'] == verified['preparation_receipt']['sha256']
          and prepared['path'] == str(PurePosixPath(roots['backup_base']) / prepared['migration_id'] / 'PLAN.private.json')
          and Path(_host_path(observed['receipt_path'])).is_relative_to(Path(roots['proof_dir']))
          and not Path(roots['proof_dir']).is_relative_to(Path(roots['runtime']))
          and not Path(roots['proof_dir']).is_relative_to(Path(roots['backup_base']))
          and prepared['largest_source_codepoint'] > 0xffff, 'replay_v2_native_invalid')
    _v2_apply(native['apply'], prepared)
    # Functional fixture metadata is intentionally synthetic; representative
    # original input/resource coverage is independently checked below.
    metadata = native['source_metadata']
    _v2_closed(metadata, {'archive_sha256', 'source_receipt_sha256', 'timestamp_sidecar_sha256', 'inventory_sha256',
        'timestamp_sha256', 'files', 'verified_before_mtime', 'released_before_plan'}, 'replay_v2_native_invalid')
    _need(all(isinstance(metadata[key], str) and _HEX.fullmatch(metadata[key]) for key in
          ('archive_sha256', 'source_receipt_sha256', 'timestamp_sidecar_sha256', 'inventory_sha256', 'timestamp_sha256'))
          and _v2_int(metadata['files'], 1) and metadata['verified_before_mtime'] is metadata['released_before_plan'] is True,
          'replay_v2_native_invalid')
    _v2_functional_execution(verified['native_execution'], protocol, recipe, verified, native, files)
    native_plan = plan
    inherited = proof.get('inherited_storage_recovery') or {}
    if inherited.get('native_origin') is not None:
        wrapper = files.json(inherited['native_origin']); native_plan = files.json(wrapper['plan'])
    _v2_resources(verified['resource_evidence'], protocol, verified, native_plan, original, stats, source, recipe, files)


def _archive_role(pin, role, kind, current, recovery, proof, phase, plan, files, origin=None):
    fields = {'path', 'sha256', 'size', 'capture_phase', 'store_schema', 'recovery_role', 'recovery_recipe', 'transformation_proof'}
    _need(isinstance(pin, dict) and set(pin) == fields, 'accepted_archive_role_missing')
    if kind == 'unified-migration' and role == 'current':
        expected = ('pre-migration', 'legacy', 'migration-replay')
    elif kind == 'unified-migration':
        expected = ('pre-release', 'legacy', 'direct')
    elif kind == 'configuration-only' and role == 'current':
        expected = ('pre-configuration', 'unified-v1', 'direct')
    elif pin['recovery_role'] == 'migration-replay':
        expected = ('pre-migration', 'legacy', 'migration-replay')
    else:
        expected = ('pre-configuration', 'unified-v1', 'direct')
    _need(tuple(pin[key] for key in ('capture_phase', 'store_schema', 'recovery_role')) == expected, 'accepted_archive_role_mismatch')
    if expected[2] == 'direct':
        _need(pin['recovery_recipe'] is None and pin['transformation_proof'] is None, 'accepted_archive_role_mismatch')
        return
    recipe, transformed = files.json(pin['recovery_recipe']), files.json(pin['transformation_proof'])
    source = origin if role == 'previous' and origin is not None else proof
    _need(recipe.get('schema') == 'berry.migration-replay.v1' and recipe.get('archive_sha256') == pin['sha256']
          and recipe.get('candidate_image') == source.get('candidate_image') and recipe.get('source_sha') == source.get('source_sha')
          and recipe.get('migration_id') == source.get('migration', {}).get('migration_id')
          and recipe.get('raw_plan') == recovery['raw_plan']
          and recipe.get('operator_modules') == source.get('rollback_recipe', {}).get('operator_modules')
          and recipe.get('steps') == ['restore-legacy-runtime', 'run-exact-migration', 'verify-unified-store-and-preservation']
          and recipe.get('transformation_proof') == pin['transformation_proof'], 'accepted_migration_replay_unproven')
    protocol = files.json(recipe.get('replay_protocol'))
    verified = files.json(recipe.get('protocol_verification'))
    if protocol.get('schema') == 'berry.migration-replay-protocol.v2':
        _replay_protocol_v2(protocol, verified, recipe, pin, recovery, source, proof, plan, files)
    else:
        _need(protocol.get('schema') == 'berry.migration-replay-protocol.v1'
          and protocol.get('image') == recipe['candidate_image'] and protocol.get('source_sha') == recipe['source_sha']
          and protocol.get('restore') == {'module': 'app.services.runtime_backup', 'function': 'restore_backup', 'require_empty': True}
          and protocol.get('source_metadata') == {'from': 'raw-plan.sources', 'verify_size_and_sha256_before_metadata': True,
              'restore_mtime_ns': True, 'reject_unknown_roots_and_unsafe_paths': True}
          and protocol.get('plan') == {'module': 'app.services.information_migration', 'function': 'plan_migration', 'fresh_runtime_paths': True}
          and protocol.get('apply') == {'module': 'app.services.information_migration', 'function': 'apply_migration',
              'quiesced': True, 'resume_id': None, 'new_empty_backup_base': True}
          and protocol.get('verification') == ['current-store', 'winner-and-variants', 'analyst-decisions', 'all-protected-runtime-state']
          and protocol.get('original_migration_id_is_provenance_only') is True, 'accepted_migration_replay_protocol_unsupported')
        files.file(protocol.get('program'))
        checks = {'restore-bytes-and-modes', 'source-hashes-before-mtime', 'source-mtime-ns-rehydration',
              'fresh-plan-at-new-paths', 'new-empty-backup-base', 'no-resume-id', 'winner-and-variants-preserved',
              'analyst-decisions-preserved', 'current-store-verification'}
        _need(verified.get('schema') == 'berry.migration-replay-verification.v1' and verified.get('state') == 'passed'
          and verified.get('image') == recipe['candidate_image'] and verified.get('source_sha') == recipe['source_sha']
          and verified.get('protocol_sha256') == recipe['replay_protocol']['sha256']
          and verified.get('program_sha256') == protocol['program']['sha256']
          and isinstance(verified.get('checks'), dict) and set(verified['checks']) == checks
          and all(value is True for value in verified['checks'].values()), 'accepted_migration_replay_verification_missing')
    files.file(verified.get('test_program')); files.file(verified.get('native_receipt'))
    _need(transformed.get('schema') == 'berry.migration-transformation.v1' and transformed.get('state') == 'verified'
          and transformed.get('archive_sha256') == pin['sha256'] and transformed.get('migration_id') == recipe['migration_id']
          and transformed.get('raw_plan') == recovery['raw_plan']
          and isinstance(transformed.get('source_inventory_sha256'), str) and _HEX.fullmatch(transformed['source_inventory_sha256']),
          'accepted_migration_transformation_unproven')
    for name in ('source_receipt', 'post_apply_manifest', 'post_startup_manifest'):
        _need(transformed.get(name) == source.get(name), 'accepted_migration_transformation_unproven')
        files.file(transformed[name])
    expected_proof = proof.get('inherited_storage_recovery', {}).get('origin_proof') if source is origin else recovery['final_proof']
    _need(transformed.get('final_proof') == expected_proof, 'accepted_migration_transformation_unproven')
    if kind == 'unified-migration' and role == 'current':
        _need(transformed['source_inventory_sha256'] == phase.get('bindings', {}).get('source_inventory_sha256')
              and phase.get('bindings', {}).get('archive_sha256') == pin['sha256']
              and phase.get('bindings', {}).get('source_receipt_sha256') == recovery['source_receipt']['sha256'],
              'accepted_migration_transformation_unproven')


def _load_accepted_closure(ledger_path: Path, backup_root: Path, *, older_path=None, read_file=None, stat_file=None) -> dict:
    try:
        return _load_accepted_closure_checked(ledger_path, backup_root, older_path=older_path, read_file=read_file, stat_file=stat_file)
    except StorageRecoveryError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise StorageRecoveryError('accepted_recovery_proof_invalid') from None


def _pin_references(value, files):
    """Authenticate producer-declared reference trees without parsing inventories."""
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            files.file({key: value[key] for key in ('path', 'sha256')})
        else:
            for item in value.values():
                _pin_references(item, files)
    elif isinstance(value, list):
        for item in value:
            _pin_references(item, files)


def _accepted_before(ledger, expected_sha, files):
    """Resolve bounded historical metadata with the same injected reader."""
    matches = []
    for folder in _metadata_folders(Path(_host_path(ledger['stage']))):
        for name in sorted(_BEFORE_NAMES):
            path = folder / name
            if not path.exists() and not path.is_symlink():
                continue
            try:
                reader = files.read_file
                if reader is not None and hasattr(reader, 'handles') and not reader.handles(path):
                    reader = None
                body = (reader or _read)(path, 4 * 1024**2)
            except FileNotFoundError:
                continue
            if _sha(body) == expected_sha:
                files.file({'path': str(path), 'sha256': expected_sha}, private=True, parse=True)
                _need(_identity(_parsed(body))['image'] == ledger.get('previous_image'), 'accepted_previous_image_mismatch')
                matches.append(path)
    _need(matches and len(matches) <= 32, 'previous_ledger_not_found')
    return matches[0]


def _logo_constants(ref, files):
    """Read literal protocol constants from authenticated code without executing it."""
    body = files.file(ref, parse=True, maximum_bytes=1024**2)
    names = {'SOURCE', 'SEED_SHA', 'INDEX', 'EXPECTED', 'CHOICES'}
    values = {}
    try:
        for node in ast.parse(body).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in names:
                    _need(name not in values, 'accepted_logo_protocol_unsupported')
                    values[name] = ast.literal_eval(node.value)
    except (SyntaxError, ValueError, TypeError, RecursionError):
        raise StorageRecoveryError('accepted_logo_protocol_unsupported') from None
    _need(set(values) == names and values['INDEX'] == 'inbox/brand_media/index.json'
          and isinstance(values['EXPECTED'], dict) and len(values['EXPECTED']) == 5
          and all(isinstance(key, str) and isinstance(value, str) and _HEX.fullmatch(value)
                  for key, value in values['EXPECTED'].items())
          and values['CHOICES'] == ('primary', 'analyst_selected', 'rejected', 'match_status', 'policy', 'object_ref')
          and isinstance(values['SEED_SHA'], str) and _HEX.fullmatch(values['SEED_SHA']), 'accepted_logo_protocol_unsupported')
    return values


def _logo_audit(ref, before_ref, constants, source, files):
    audit = files.json(ref, maximum_bytes=32 * 1024**2)
    before = files.json(before_ref, maximum_bytes=32 * 1024**2)
    expected = constants['EXPECTED']; missing = audit.get('missing_ids')
    _need(audit.get('schema') == 'berry.logo-supplement-47ad.v1' and audit.get('state') == 'verified'
          and audit.get('source_sha') == constants['SOURCE'] and audit.get('seed_sha256') == constants['SEED_SHA']
          and audit.get('index_path') == constants['INDEX'] and audit.get('expected_normalized_hashes') == expected
          and isinstance(missing, list) and all(isinstance(item, str) for item in missing)
          and missing == sorted(set(missing)) and set(missing) <= set(expected), 'accepted_logo_audit_invalid')
    for name, apply, ids in [('dry', False, missing), ('apply', True, missing), ('replay', True, [])]:
        result = {'requested': 5, 'missing': len(ids), 'preserved': 5 - len(ids), 'created': len(ids) if apply else 0,
            'missing_ids': ids, 'added_ids': ids if apply else [], 'preserved_ids': sorted(set(expected) - set(ids)),
            'applied': apply, 'changed': bool(apply and ids)}
        _need(_canonical(audit.get(name)) == _canonical(result), 'accepted_logo_audit_invalid')
    rows = before.get('assets')
    _need(type(before.get('version')) is int and before['version'] == 1 and set(before) == {'version', 'assets'}
          and isinstance(rows, dict) and all(isinstance(row, dict) for row in rows.values()), 'accepted_logo_preseed_invalid')
    old = {key: _sha(_canonical(value)) for key, value in rows.items()}
    choices = {key: {field: row[field] for field in constants['CHOICES'] if field in row} for key, row in rows.items()}
    after = audit.get('after_raw_row_hashes')
    _need(audit.get('before_raw_row_hashes') == old and sorted(set(expected) - set(old)) == missing
          and isinstance(after, dict) and set(after) == set(old) | set(missing)
          and all(after[key] == value for key, value in old.items())
          and all(after[key] == expected[key] for key in missing)
          and audit.get('old_choices_before_sha256') == audit.get('old_choices_after_sha256') == _sha(_canonical(choices))
          and audit.get('mutations') == ([constants['INDEX']] if missing else [])
          and all(audit.get(key) is True for key in ('raw_rows_preserved', 'no_binary_downloads', 'new_grants_false', 'replay_exact_noop'))
          and audit.get('forced_selections') is False
          and audit.get('preseed_index', {}).get('sha256') == before_ref['sha256'] == audit.get('before_index', {}).get('sha256'),
          'accepted_logo_preservation_invalid')
    if source is not None:
        _need(source.get(constants['INDEX']) == {key: audit.get('after_index', {}).get(key) for key in ('sha256', 'size', 'mode')},
              'accepted_logo_snapshot_invalid')
    return audit


def _adoption_logo_evidence(adoption, recovery, plan, proof, phase, files):
    """Validate the actual timestamp/logo extension's declared native joins."""
    completion = adoption['receiver']
    _need(recovery['timestamp_completion'] == adoption['descriptor']['local_archive']['source']['verification'],
          'accepted_timestamp_completion_invalid')
    dependencies = recovery['timestamp_dependencies']
    _need(isinstance(dependencies, dict) and set(dependencies) == {'native_verified_receipt', 'timestamp_proof', 'sidecar'},
          'accepted_timestamp_dependencies_invalid')
    for name, ref in dependencies.items():
        _need(completion.get(name, {}).get('sha256') == ref['sha256'], 'accepted_timestamp_copy_invalid')
    native = files.json(dependencies['native_verified_receipt'])
    checked = files.json(dependencies['timestamp_proof'])
    sidecar = files.json(dependencies['sidecar'], maximum_bytes=16 * 1024**2)
    source = files.json(recovery['source_receipt'], maximum_bytes=16 * 1024**2)
    inventory, times = source.get('source_manifest'), sidecar.get('source_mtime_ns')
    _need(isinstance(inventory, dict) and inventory and isinstance(times, dict) and set(times) == set(inventory)
          and all(type(value) is int and -(2**63) <= value < 2**63 for value in times.values()), 'accepted_timestamp_inventory_invalid')
    for name, row in inventory.items():
        path = PurePosixPath(name)
        _need(not path.is_absolute() and path.as_posix() == name and '..' not in path.parts and len(path.parts) >= 2
              and path.parts[0] in {'data', 'inbox'} and '\\' not in name and '\x00' not in name
              and isinstance(row, dict) and set(row) == {'sha256', 'size', 'mode'}
              and isinstance(row['sha256'], str) and _HEX.fullmatch(row['sha256'])
              and type(row['size']) is int and row['size'] >= 0 and type(row['mode']) is int and 0 <= row['mode'] <= 0o777,
              'accepted_timestamp_inventory_invalid')
    inventory_sha, timestamp_sha = _sha(_canonical(inventory)), _sha(_canonical(times))
    bindings = phase['bindings']; archive = source.get('archive') or {}; remote = archive.get('timestamps') or {}
    _need(set(remote) == {'path', 'sha256', 'digest', 'count'} and _host_path(remote.get('path')),
          'accepted_timestamp_source_invalid')
    _need(native.get('state') == 'completed' and native.get('writers_resumed') is True
          and all(native.get(key) == completion.get(key) == plan.get(key) for key in ('nonce', 'source_sha', 'canonical_sha', 'candidate_image'))
          and native.get('final_receipt_sha256') == completion['final_receipt_sha256']
          and native.get('candidate_binding_sha256') == completion['candidate_binding_sha256']
          and native.get('proof_seals') == bindings.get('proof_seals'), 'accepted_timestamp_completion_invalid')
    _need(checked.get('state') == 'verified' and sidecar.get('state') == 'captured'
          and type(sidecar.get('version')) is int and sidecar['version'] == 1
          and type(sidecar.get('source_timestamp_version')) is int and sidecar['source_timestamp_version'] == 1
          and type(checked.get('source_timestamp_version')) is int and checked['source_timestamp_version'] == 1
          and source.get('source_stable') is sidecar.get('source_stable') is sidecar.get('source_mtime_stable') is True
          and all(value == inventory_sha for value in (source.get('source_inventory_sha256'), source.get('source_inventory_after_sha256'),
              sidecar.get('source_inventory_sha256'), sidecar.get('source_inventory_after_sha256'), checked.get('source_inventory_sha256'),
              native.get('source_inventory_sha256'), bindings.get('source_inventory_sha256')))
          and all(value == timestamp_sha for value in (sidecar.get('source_mtime_ns_sha256'), sidecar.get('source_mtime_ns_after_sha256'),
              remote.get('digest'), checked.get('timestamp_digest'), completion.get('timestamp_digest')))
          and checked.get('source_receipt_sha256') == native.get('source_receipt_sha256') == recovery['source_receipt']['sha256']
          and checked.get('nonce') == source.get('nonce') == plan['nonce']
          and checked.get('candidate_image') == source.get('candidate_image') == plan['candidate_image']
          and all(type(value) is int and value == len(times) for value in (remote.get('count'), checked.get('files'), completion.get('files')))
          and remote.get('sha256') == dependencies['sidecar']['sha256']
          and checked.get('remote_sidecar') == remote and checked.get('local_sidecar') == completion['sidecar']
          and checked.get('archive_sha256') == archive.get('archive_sha256') == completion['archive_sha256']
          and _canonical({key: value for key, value in proof.get('offhost_archive', {}).items() if key != 'path'}) == _canonical(archive)
          and sidecar.get('archive') == {key: value for key, value in archive.items() if key != 'timestamps'}
          and sidecar.get('base_producer_sha256') == recovery['live_base_dependency']['sha256'], 'accepted_timestamp_source_invalid')
    files.file(recovery['live_base_dependency'])
    refs = recovery['logo_supplement']
    _need(isinstance(refs, dict) and set(refs) == {'audit', 'preseed_index', 'helper', 'copy_proof'}
          and refs == proof.get('logo_supplement') == source.get('logo_supplement')
          and refs['helper'] == plan.get('modules', {}).get('logo_seed')
          and refs['copy_proof'] == plan.get('logo_supplement', {}).get('copy_proof')
          and completion.get('logo_supplement', {}).get('remote') == refs,
          'accepted_logo_native_context_invalid')
    constants = _logo_constants(refs['helper'], files)
    _need(constants['SOURCE'] == plan['source_sha'], 'accepted_logo_protocol_unsupported')
    audit = _logo_audit(refs['audit'], refs['preseed_index'], constants, inventory, files)
    _need(phase.get('seed', {}).get('logo_supplement') == audit and audit.get('preseed_index') == refs['preseed_index'],
          'accepted_logo_seed_invalid')
    retained = completion['logo_supplement']
    _need(all(retained.get(name, {}).get('sha256') == refs[name]['sha256'] for name in ('audit', 'preseed_index')),
          'accepted_logo_receiver_invalid')
    copied = files.json(refs['copy_proof'])
    _need(copied.get('schema') == 'berry.copy-logo-supplement-complete.v1' and copied.get('state') == 'verified'
          and copied.get('source_sha') == plan['source_sha'] and copied.get('candidate_image') == plan['candidate_image']
          and copied.get('logo_helper_sha256') == refs['helper']['sha256'] and copied.get('seed_sha256') == constants['SEED_SHA']
          and type(copied.get('helper_exit')) is int and copied['helper_exit'] == 0
          and type(copied.get('watcher_exit')) is int and copied['watcher_exit'] == 0
          and copied.get('oom_killed') is False and copied.get('isolated_copy_preserved') is True,
          'accepted_logo_copy_invalid')
    _pin_references(copied, files)
    _logo_audit(copied.get('logo_audit'), copied.get('preseed_index'), constants, None, files)
    preservation = files.json(copied.get('preservation_completion'))
    rehearsal = files.json(plan.get('proofs', {}).get('rehearsal'))
    _need(copied['preservation_completion']['sha256'] == rehearsal.get('native_evidence', {}).get('rehearsal', {}).get('sha256')
          and preservation.get('state') == 'passed' and preservation.get('image') == plan['candidate_image']
          and preservation.get('program_sha256') == plan.get('modules', {}).get('preservation', {}).get('sha256'),
          'accepted_logo_preservation_chain_invalid')


def _candidate_image_inventory(plan, files):
    """Retain the known optional image-inventory producer extension."""
    reference = plan['candidate_image_manifest']
    _v2_closed(reference, {'path', 'sha256'}, 'accepted_candidate_image_manifest_invalid')
    admission = files.json(plan.get('proofs', {}).get('image'))
    _need(admission.get('state') == 'verified' and admission.get('image', admission.get('image_id')) == plan['candidate_image']
          and admission.get('source_sha') == plan['source_sha']
          and admission.get('image_verification_sha256') == reference['sha256'], 'accepted_candidate_image_manifest_invalid')
    manifest = files.json(reference, private=False)
    inventory = manifest.get('exact_image_files')
    _need(manifest.get('source_sha') == plan['source_sha'] and isinstance(inventory, dict) and inventory,
          'accepted_candidate_image_manifest_invalid')
    reports = 0
    for name, checksum in inventory.items():
        path = PurePosixPath(_host_path(name))
        _need(path.is_relative_to('/app') and path != PurePosixPath('/app')
              and isinstance(checksum, str) and _HEX.fullmatch(checksum), 'accepted_candidate_image_manifest_invalid')
        if name.startswith('/app/reports/'):
            relative = path.relative_to('/app/reports')
            _need(relative.parts and '..' not in relative.parts, 'accepted_candidate_image_manifest_invalid')
            reports += 1
    # The accepted native producer enforces its own release-specific count.
    _need(reports > 0, 'accepted_candidate_image_manifest_invalid')


def _adoption_context(wrapper, files):
    """Join the immutable offhost/HOLD acceptance to an explicit local copy.

    This derives migration semantics from the frozen producer's actual shape.
    It never inserts an operation kind into that producer's bytes.
    """
    descriptor = files.json(wrapper.get('adoption'))
    _need(set(descriptor) == {'schema', 'profile', 'origin_ledger', 'origin_receipt', 'origin_wrapper', 'local_archive'}
          and descriptor['schema'] == ADOPTION_SCHEMA and descriptor['profile'] in {ADOPTION_PROFILE, ADOPTION_LOGO_PROFILE},
          'accepted_adoption_profile_unsupported')
    body = files.file(descriptor['origin_ledger'], private=True, parse=True)
    origin = _parsed(body); historical = files.json(descriptor['origin_wrapper'])
    receipt = files.json(descriptor['origin_receipt'])
    _need(origin.get('pr') == 590 and origin.get('receipt') == descriptor['origin_receipt']['path']
          and origin.get('recovery_proof') == {'schema': 'berry.unified-release-recovery.v1', **descriptor['origin_wrapper']}
          and receipt.get('state') == 'accepted' and receipt.get('status') == 'PASS'
          and receipt.get('candidate_image') == origin.get('image')
          and receipt.get('source_sha') == origin.get('source_sha')
          and receipt.get('new_ledger_sha256') == descriptor['origin_ledger']['sha256']
          and receipt.get('old_ledger_sha256') == wrapper['previous_ledger']['sha256']
          and receipt.get('recovery_proof') == origin['recovery_proof']
          and receipt.get('retention_readiness') == 'HOLD', 'accepted_adoption_origin_unproven')
    fields = {'schema', 'operation_kind', 'operation_nonce', 'current', 'previous_ledger', 'previous_accepted', 'plan',
              'snapshots', 'configuration', 'recovery_files', 'protected_dirs', 'archives', 'images', 'retention_readiness'}
    _need(set(historical) == fields and historical['schema'] == 'berry.unified-release-recovery.v1'
          and historical['operation_kind'] == 'unified-migration' and historical['retention_readiness'] == 'HOLD',
          'accepted_adoption_origin_unproven')
    compared = fields - {'schema', 'operation_kind', 'previous_accepted', 'archives', 'retention_readiness'}
    if descriptor['profile'] == ADOPTION_LOGO_PROFILE:
        compared.remove('protected_dirs')
        previous = historical.get('previous_accepted') or {}
        known_files = {previous.get('backup')}
        def gather(value):
            if isinstance(value, dict):
                if 'path' in value and 'sha256' in value:
                    known_files.add(value['path'])
                else:
                    for item in value.values(): gather(item)
            elif isinstance(value, list):
                for item in value: gather(item)
        gather(previous.get('historical_acceptance'))
        gather(previous.get('historical_proof_dependencies'))
        _need(isinstance(historical.get('protected_dirs'), list)
              and _canonical(wrapper['protected_dirs']) == _canonical([
                  path for path in historical['protected_dirs'] if path not in known_files]),
              'accepted_adoption_protected_path_classification_invalid')
        # The producer's known archive FILE is deliberately not inspected in a
        # flat historical lookup. Every remaining declared subtree must really
        # be a directory; an unfamiliar existing file is never reclassified.
        for directory in wrapper['protected_dirs']:
            _safe(Path(_host_path(directory)), directory=True)
    for key in compared:
        _need(_canonical(historical[key]) == _canonical(wrapper[key]), 'accepted_adoption_native_context_changed')
    mapping = descriptor['local_archive']
    _need(isinstance(mapping, dict) and set(mapping) == {'source', 'destination'}
          and set(historical['archives']) == {'current'}
          and _canonical(mapping['source']) == _canonical(historical['archives']['current']),
          'accepted_adoption_archive_mapping_invalid')
    source, destination = mapping['source'], mapping['destination']
    _need(set(source) == {'location', 'path', 'sha256', 'size', 'verification'} and source['location'] == 'offhost-verified'
          and isinstance(source['path'], str) and source['path'] == origin.get('backup')
          and set(destination) == {'path', 'sha256', 'size'}
          and source['path'] != destination['path']
          and all(destination[key] == source[key] == wrapper['archives']['current'][key] for key in ('sha256', 'size'))
          and destination['path'] == wrapper['archives']['current']['path'], 'accepted_adoption_archive_mapping_invalid')
    verification = files.json(source['verification'])
    phase_ref = wrapper['recovery_files']['phase_receipt']
    _need(verification.get('state') == 'completed' and verification.get('writers_resumed') is True
          and verification.get('archive_sha256') == source['sha256']
          and verification.get('final_receipt_sha256') == phase_ref['sha256']
          and verification.get('source_receipt_sha256') == wrapper['recovery_files']['source_receipt']['sha256']
          and all(verification.get(key) == origin.get(key) for key in ('source_sha', 'image') if key in verification)
          and verification.get('candidate_image') == origin.get('image')
          and verification.get('nonce') == wrapper['operation_nonce'], 'accepted_adoption_receiver_unproven')
    metadata = origin.get('unified_information_release') or {}
    _need(metadata.get('source_sha') == origin.get('source_sha') and metadata.get('retention_readiness') == 'HOLD'
          and metadata.get('native_final_proof') == wrapper['recovery_files']['final_proof']
          and isinstance(metadata.get('proofs'), dict), 'accepted_adoption_origin_unproven')
    proofs = metadata['proofs']
    for key, expected in {'plan': wrapper['plan'], 'snapshot_pre': wrapper['snapshots']['pre'],
                          'snapshot_post': wrapper['snapshots']['post'], 'phase_receipt': phase_ref,
                          'final_proof': wrapper['recovery_files']['final_proof'], 'archive_verification': source['verification']}.items():
        _need(proofs.get(key) == expected, 'accepted_adoption_origin_unproven')
    _pin_references(proofs, files)
    preserved = historical['previous_accepted']
    _need(isinstance(preserved, dict) and preserved.get('ledger') == wrapper['previous_ledger'], 'accepted_adoption_previous_unproven')
    _pin_references(preserved.get('historical_acceptance'), files)
    _pin_references(preserved.get('historical_proof_dependencies'), files)
    return {'descriptor': descriptor, 'ledger': origin, 'raw': body, 'historical': historical, 'receiver': verification}


def _load_accepted_closure_checked(ledger_path: Path, backup_root: Path, *, older_path=None, read_file=None, stat_file=None,
                                 native_wrapper_ref=None, shared_files=None) -> dict:
    files = shared_files if shared_files is not None else _AcceptedFiles(read_file, stat_file)
    native_only = native_wrapper_ref is not None
    if native_only:
        wrapper_ref = native_wrapper_ref
        wrapper = files.json(wrapper_ref)
        _need(wrapper.get('operation_kind') == 'recovery-adoption', 'configuration_only_origin_unproven')
        adoption = _adoption_context(wrapper, files)
        raw = adoption['raw']; ledger = {**adoption['ledger'], 'backup': adoption['descriptor']['local_archive']['destination']['path']}
        ledger_path = Path(adoption['descriptor']['origin_ledger']['path'])
    else:
        raw = (read_file or _read)(ledger_path, 4 * 1024**2)
        ledger = _parsed(raw)
        files.file({'path': str(ledger_path), 'sha256': _sha(raw)}, private=True)
        pointer = ledger.get('recovery_proof')
        _need(isinstance(pointer, dict) and set(pointer) == {'schema', 'path', 'sha256'}
              and pointer['schema'] == RECOVERY_PROOF_SCHEMA, 'accepted_recovery_proof_missing')
        wrapper_ref = {key: pointer[key] for key in ('path', 'sha256')}
        wrapper = files.json(wrapper_ref)
        adoption = _adoption_context(wrapper, files) if wrapper.get('operation_kind') == 'recovery-adoption' else None
    current = _identity(ledger)
    _need(Path(_host_path(wrapper_ref['path'])).is_relative_to(Path(current['stage'])), 'accepted_recovery_proof_outside_stage')
    fields = {'schema', 'operation_kind', 'operation_nonce', 'current', 'previous_ledger', 'plan', 'snapshots',
              'configuration', 'recovery_files', 'protected_dirs', 'archives', 'images'}
    _need(set(wrapper) == fields | ({'adoption'} if adoption is not None else set())
          and wrapper['schema'] == RECOVERY_PROOF_SCHEMA, 'accepted_recovery_proof_schema_invalid')
    nonce = wrapper['operation_nonce']
    operation_kind = wrapper['operation_kind']
    _need(operation_kind in {'unified-migration', 'configuration-only', 'recovery-adoption'}, 'accepted_operation_kind_unsupported')
    kind = 'unified-migration' if adoption is not None else operation_kind
    if adoption is not None and not native_only:
        _need(_canonical({key: value for key, value in ledger.items() if key not in {'backup', 'receipt', 'recovery_proof'}}) ==
              _canonical({key: value for key, value in adoption['ledger'].items() if key not in {'backup', 'receipt', 'recovery_proof'}})
              and ledger['backup'] == adoption['descriptor']['local_archive']['destination']['path'],
              'accepted_adoption_runtime_changed')
    _need(isinstance(nonce, str) and re.fullmatch('[a-f0-9]{32,64}', nonce), 'accepted_operation_nonce_invalid')
    _need(wrapper['current'] == {key: current[key] for key in ('source_sha', 'image', 'stage')}, 'accepted_current_identity_mismatch')
    previous_raw = files.file(wrapper['previous_ledger'], private=True, parse=True)
    previous_ledger = _parsed(previous_raw); previous = _identity(previous_ledger)
    _need(ledger.get('previous_image') == previous['image'], 'accepted_previous_identity_mismatch')
    if adoption is not None:
        preserved = adoption['historical']['previous_accepted']
        pin = wrapper['archives']['previous']
        _need(preserved.get('backup') == previous['backup'] == pin['path']
              and preserved.get('stage') == previous['stage']
              and type(preserved.get('original_backup_size')) is int and preserved['original_backup_size'] == pin['size']
              and preserved.get('original_archive_sha256') == pin['sha256']
              and preserved.get('historical_acceptance', {}).get('decision', {}).get('path') == previous_ledger.get('receipt')
              and isinstance(preserved.get('historical_proof_dependencies'), list) and preserved['historical_proof_dependencies'],
              'accepted_adoption_previous_unproven')
    previous_adoption = None
    previous_pointer = previous_ledger.get('recovery_proof') or {}
    if kind == 'configuration-only' and previous_pointer.get('schema') == RECOVERY_PROOF_SCHEMA:
        previous_wrapper_ref = {key: previous_pointer[key] for key in ('path', 'sha256')}
        previous_wrapper = files.json(previous_wrapper_ref)
        if previous_wrapper.get('operation_kind') == 'recovery-adoption':
            previous_adoption = _load_accepted_closure_checked(None, backup_root, read_file=read_file, stat_file=stat_file,
                native_wrapper_ref=previous_wrapper_ref, shared_files=files)
            original = previous_adoption['adoption']['ledger']
            _need(_canonical({key: value for key, value in previous_ledger.items() if key not in {'backup', 'receipt', 'recovery_proof'}}) ==
                  _canonical({key: value for key, value in original.items() if key not in {'backup', 'receipt', 'recovery_proof'}})
                  and previous['backup'] == previous_adoption['current']['backup'], 'accepted_adoption_runtime_changed')
    accepted = []
    for role, document, body in [('current', ledger, raw), ('previous', previous_ledger, previous_raw)]:
        receipt_ref = {'path': _host_path(document.get('receipt')), 'sha256': ''}
        receipt_body = (read_file or _read)(Path(receipt_ref['path']), 4 * 1024**2)
        receipt_ref['sha256'] = _sha(receipt_body); value = files.json(receipt_ref)
        _need(Path(receipt_ref['path']).is_relative_to(Path(document['stage'])) and value.get('status') == 'PASS'
              and value.get('new_ledger_sha256') == _sha(body)
              and value.get('candidate_image', value.get('image')) == document['image']
              and isinstance(value.get('old_ledger_sha256'), str) and _HEX.fullmatch(value['old_ledger_sha256']),
              'accepted_promotion_binding_invalid')
        if 'approved_head' in value:
            _need(value['approved_head'] == document['source_sha'], 'accepted_promotion_source_mismatch')
        accepted.append({'role': role, **receipt_ref, 'status': 'PASS', 'image': document['image'],
                         'old_ledger_sha256': value['old_ledger_sha256'], 'new_ledger_sha256': value['new_ledger_sha256']})
    expected_before = adoption['descriptor']['origin_ledger']['sha256'] if adoption is not None and not native_only else wrapper['previous_ledger']['sha256']
    _need(accepted[0]['old_ledger_sha256'] == expected_before, 'accepted_previous_ledger_mismatch')
    if previous_adoption is not None:
        logical_before = previous_adoption['wrapper']['previous_ledger']
        older_path = Path(logical_before['path']) if older_path is None else older_path
        older_sha = logical_before['sha256']
        _need(accepted[1]['old_ledger_sha256'] == previous_adoption['adoption']['descriptor']['origin_ledger']['sha256'],
              'accepted_previous_ledger_mismatch')
    elif adoption is not None:
        discovered = _accepted_before(previous_ledger, accepted[1]['old_ledger_sha256'], files)
        older_path = discovered if older_path is None else older_path
        older_sha = accepted[1]['old_ledger_sha256']
    elif older_path is None:
        older_path = _accepted_before(previous_ledger, accepted[1]['old_ledger_sha256'], files)
        older_sha = accepted[1]['old_ledger_sha256']
    else:
        older_sha = accepted[1]['old_ledger_sha256']
    older_ref = {'path': str(older_path), 'sha256': older_sha}
    older_raw = files.file(older_ref, private=True, parse=True); older = _identity(_parsed(older_raw))
    _need(previous_ledger.get('previous_image') == older['image'], 'accepted_previous_before_mismatch')
    snapshots, baselines = {}, {}
    _need(isinstance(wrapper['snapshots'], dict) and set(wrapper['snapshots']) == {'pre', 'post'}
          and isinstance(wrapper['configuration'], dict) and set(wrapper['configuration']) == {'pre', 'post'},
          'accepted_snapshots_missing')
    for phase, identity in [('pre', previous), ('post', current)]:
        pair = files.json(wrapper['snapshots'][phase]); app = _pair_app(pair)
        _need(app['Image'] == identity['image'] and app['Config'].get('Labels', {}).get('org.opencontainers.image.revision') == identity['source_sha'],
              'accepted_snapshot_identity_mismatch')
        config = _accepted_configuration(wrapper['configuration'][phase], pair, files)
        snapshots[phase] = pair
        baselines['previous' if phase == 'pre' else 'current'] = {
            'ordered_compose_files': [pin['path'] for pin in config['app']['compose_files']],
            'compose_argv': ['docker', 'compose', '--env-file', config['app']['environment_files'][0]['path']],
            'mounts': app['Mounts'], 'node_image': pair['copilot']['Image'],
            'node_component_source': pair['copilot']['Config'].get('Labels', {}).get('org.opencontainers.image.revision'),
            'web_image': identity['image'], 'rollback_image': previous['image'] if phase == 'post' else older['image']}
    recovery = wrapper['recovery_files']
    required = {'baseline', 'phase_receipt', 'final_proof', 'source_receipt', 'post_apply_manifest', 'post_startup_manifest',
                'legacy_promotion_manifest', 'raw_plan', 'raw_manifest', 'rollback_modules'}
    logos = adoption is not None and adoption['descriptor']['profile'] == ADOPTION_LOGO_PROFILE
    extra = {'timestamp_completion', 'timestamp_dependencies', 'live_base_dependency', 'logo_supplement'} if logos else set()
    _need(isinstance(recovery, dict) and set(recovery) == required | extra, 'accepted_recovery_dependencies_missing')
    native = files.json(recovery['baseline']); plan = files.json(wrapper['plan'])
    phase = files.json(recovery['phase_receipt']); proof = files.json(recovery['final_proof'])
    if adoption is not None:
        _need('operation_kind' not in plan and 'operation_kind' not in proof
              and 'operation_kind' not in phase.get('bindings', {}), 'accepted_adoption_native_kind_manufactured')
        _pin_references(plan.get('proofs'), files)
        _need(adoption['receiver'].get('candidate_binding_sha256') == phase.get('final_verification', {}).get('candidate_binding_sha256'),
              'accepted_adoption_receiver_unproven')
        _need(adoption['receiver'].get('canonical_sha') == plan.get('canonical_sha')
              and adoption['ledger']['unified_information_release'].get('canonical_sha') == plan.get('canonical_sha')
              and proof.get('offhost_archive', {}).get('path') == adoption['descriptor']['local_archive']['source']['path'],
              'accepted_adoption_native_context_changed')
        if logos:
            _adoption_logo_evidence(adoption, recovery, plan, proof, phase, files)
            if 'candidate_image_manifest' in plan:
                _candidate_image_inventory(plan, files)
    else:
        _need(plan.get('operation_kind') == kind and proof.get('operation_kind') == kind
              and phase.get('bindings', {}).get('operation_kind') == kind, 'accepted_operation_kind_mismatch')
    inherited_modules, origin = [], None
    if kind == 'configuration-only':
        _need(current['image'] == previous['image'] and current['source_sha'] == previous['source_sha'], 'configuration_only_runtime_changed')
        proof, inherited_modules, origin = _configuration_only_proof(proof, plan, recovery, snapshots, wrapper, files, backup_root)
        if previous_adoption is not None:
            _need(proof.get('inherited_storage_recovery', {}).get('native_origin') == previous_wrapper_ref,
                  'configuration_only_origin_unproven')
    for name in required - {'baseline', 'phase_receipt', 'final_proof', 'rollback_modules'}:
        files.file(recovery[name])
    modules = recovery['rollback_modules']
    _need(isinstance(modules, list) and modules and isinstance(plan.get('modules'), dict), 'accepted_rollback_modules_missing')
    _need(isinstance(inherited_modules, list), 'accepted_rollback_modules_missing')
    expected_modules = {pin['path']: pin for pin in [*plan['modules'].values(), *inherited_modules]}
    _need(sorted(modules, key=lambda pin: pin['path']) == sorted(expected_modules.values(), key=lambda pin: pin['path']),
          'accepted_rollback_modules_mismatch')
    for ref in modules:
        files.file(ref)
    _need(plan.get('nonce') == nonce and plan.get('candidate_image') == current['image'] and plan.get('source_sha') == current['source_sha']
          and isinstance(plan.get('canonical_sha'), str) and _SOURCE.fullmatch(plan['canonical_sha']),
          'accepted_release_plan_mismatch')
    final = phase.get('final_verification') or {}
    _need(phase.get('phase') == 'completed' and phase.get('writers_resumed') is True and phase.get('maintenance_held') is False
          and final.get('recovery_proof_path') == recovery['final_proof']['path']
          and final.get('recovery_proof_sha256') == recovery['final_proof']['sha256']
          and Path(recovery['final_proof']['path']).name == 'recovery-proof-1.json', 'accepted_final_verification_mismatch')
    bindings = phase.get('bindings') or {}
    _need(all(bindings.get(key) == plan.get(key) for key in ('nonce', 'candidate_image', 'source_sha', 'canonical_sha')),
          'accepted_phase_bindings_mismatch')
    if 'baseline_sha256' in bindings:
        _need(bindings['baseline_sha256'] == recovery['baseline']['sha256'], 'accepted_phase_bindings_mismatch')
    _need(proof.get('state') == 'recovery-prepared' and proof.get('nonce') == nonce
          and proof.get('candidate_image') == current['image'] and proof.get('source_sha') == current['source_sha']
          and proof.get('canonical_sha') == plan.get('canonical_sha'), 'accepted_native_proof_mismatch')
    _need(proof.get('baseline_path') == recovery['baseline']['path'] and proof.get('baseline_sha256') == recovery['baseline']['sha256']
          and plan.get('proofs', {}).get('baseline') == recovery['baseline'], 'accepted_native_baseline_mismatch')
    for native_name, outer_name in [('source_receipt', 'source_receipt'), ('post_apply_manifest', 'post_apply_manifest'),
                                    ('post_startup_manifest', 'post_startup_manifest')]:
        _need(proof.get(native_name) == recovery[outer_name], 'accepted_native_dependency_mismatch')
    legacy = proof.get('legacy_promotion_manifest') or {}
    _need(all(legacy.get(key) == recovery['legacy_promotion_manifest'][key] for key in ('path', 'sha256')),
          'accepted_legacy_promotion_mismatch')
    for name, expected in _native_pair_binding(snapshots['pre']).items():
        _need(all(proof.get('old_binding', {}).get(name, {}).get(key) == value for key, value in expected.items())
              and all(native.get('production_binding', {}).get(name, {}).get(key) == value for key, value in expected.items()),
              'accepted_pre_snapshot_mismatch')
    candidate = _native_pair_binding(snapshots['post'])
    _need(proof.get('candidate_binding') == candidate and final.get('candidate_binding_sha256') == _sha(_canonical(candidate)),
          'accepted_post_snapshot_mismatch')
    for name in ('app', 'copilot'):
        before = wrapper['configuration']['pre'][name]['compose_files']
        _need([{key: pin[key] for key in ('path', 'sha256')} for pin in before] ==
              [{key: pin[key] for key in ('path', 'sha256')} for pin in native.get('compose', {}).get(name, {}).get('files', [])],
              'accepted_native_compose_mismatch')
        override = proof.get('candidate_override')
        files.file(override, private=True)
        _need([pin['path'] for pin in wrapper['configuration']['post'][name]['compose_files']] ==
              [pin['path'] for pin in before] + [override['path']], 'accepted_candidate_override_mismatch')
    _need(proof.get('compose_files') == native.get('compose', {}).get('app', {}).get('files')
          and proof.get('protected_files') == native.get('protected_environment_files', []), 'accepted_native_configuration_mismatch')
    for native_pin in native.get('protected_environment_files', []):
        for name in ('app', 'copilot'):
            declared = wrapper['configuration']['pre'][name]
            _need(any(all(pin.get(key) == native_pin.get(key) for key in ('path', 'sha256'))
                      for pin in declared['environment_files'] + declared['dependency_files']), 'accepted_native_environment_mismatch')
    files.file(proof.get('rollback_override'), private=True)
    recipe = proof.get('rollback_recipe') or {}
    steps = ['pause-reviewed-writers', 'stop-known-pair', 'strict-storage-rollback', 'verify-legacy-source-hashes',
             'restore-exact-legacy-promotion-manifest', 'restore-old-compose-pair', 'verify-old-pair',
             'restore-original-timer', 'restore-write-barrier'] if kind == 'unified-migration' else [
             'pause-reviewed-writers', 'stop-known-pair', 'restore-old-caddy-configuration', 'verify-new-caddy-write-barrier',
             'restore-old-compose-pair-on-current-store', 'verify-current-store-preservation', 'verify-old-pair',
             'restore-original-timer', 'restore-write-barrier']
    _need(recipe.get('plan_sha256') == wrapper['plan']['sha256'] and recipe.get('operator_modules') == plan['modules']
          and recipe.get('on_guard_refusal') == 'preserve-new-work-and-hold-maintenance'
          and recipe.get('steps') == steps, 'accepted_rollback_recipe_invalid')
    directories = wrapper['protected_dirs']
    _need(isinstance(directories, list) and directories and len(directories) == len(set(directories)), 'accepted_directories_invalid')
    for directory in directories:
        directory = _host_path(directory)
        _need(directory != str(backup_root) and not backup_root.is_relative_to(Path(directory)), 'whole_backup_root_must_not_be_pinned')
    migration = proof.get('migration') or {}; container_backup = PurePosixPath(migration.get('backup_path', ''))
    _need(migration.get('activated') is True and isinstance(migration.get('migration_id'), str)
          and container_backup.is_relative_to('/app/backups') and container_backup != PurePosixPath('/app/backups')
          and '..' not in container_backup.parts and container_backup.as_posix() == migration.get('backup_path')
          and container_backup.name == migration['migration_id'], 'accepted_migration_binding_invalid')
    raw_backup = backup_root.joinpath(*container_backup.relative_to('/app/backups').parts)
    _need(str(raw_backup) in directories and recovery['raw_plan']['path'] == str(raw_backup / 'PLAN.private.json')
          and recovery['raw_manifest']['path'] == str(raw_backup / 'MANIFEST.json')
          and proof.get('raw_backup_seals') == {'PLAN.private.json': recovery['raw_plan']['sha256'], 'MANIFEST.json': recovery['raw_manifest']['sha256']},
          'accepted_raw_backup_mismatch')
    post_mounts = {row['Destination']: row['Source'] for row in snapshots['post']['app']['Mounts']}
    _need({'/app/runtime/data', '/app/runtime/inbox'}.issubset(post_mounts), 'accepted_store_mounts_missing')
    data, inbox = Path(post_mounts['/app/runtime/data']), Path(post_mounts['/app/runtime/inbox'])
    marker_names = [str(data / 'information/store.json'), str(inbox / '.information-store.json')]
    marker_pins = {pin['path']: pin for pin in wrapper['configuration']['post']['app']['dependency_files']}
    _need(all(name in marker_pins for name in marker_names), 'accepted_active_store_proof_missing')
    marker, binding = [files.json(marker_pins[name], private=False) for name in marker_names]
    _need(marker.get('version') == 1 and marker.get('state') == 'active'
          and marker.get('data_dir') == '/app/runtime/data' and marker.get('inbox_dir') == '/app/runtime/inbox'
          and marker.get('store_root') == '/app/runtime/data/information'
          and marker.get('migration_id') == migration['migration_id'] and marker.get('backup_dir') == migration['backup_path']
          and binding.get('version') == 1 and binding.get('inbox_dir') == '/app/runtime/inbox'
          and binding.get('store_root') == marker['store_root'] and str(data / 'information') in directories,
          'accepted_active_store_binding_mismatch')
    files.absent(data / '.information-store-transition.json')
    mount_directories = set(directories) | {current['stage'], previous['stage']}
    mount_directories.update(proof.get('_accepted_native_directories', set()))
    for pair in snapshots.values():
        for container in pair.values():
            for mount in container['Mounts']:
                _need(isinstance(mount, dict) and mount.get('Type') == 'bind', 'accepted_mount_type_unsupported')
                source = _host_path(mount.get('Source')); destination = mount.get('Destination')
                if destination == '/app/backups':
                    _need(source == str(backup_root), 'accepted_backup_mount_mismatch')
                elif destination in {'/app/runtime/data', '/app/runtime/inbox', '/app/gene-delivery-source'}:
                    _need(source in directories, 'accepted_mount_directory_unprotected')
                    mount_directories.add(source)
                else:
                    _need(source in files.pins, 'accepted_mount_file_unpinned')
    archives = wrapper['archives']
    _need(isinstance(archives, dict) and set(archives) == {'current', 'previous'}, 'accepted_local_archives_missing')
    for role, identity in [('current', current), ('previous', previous)]:
        pin = archives[role]
        _archive_role(pin, role, kind, current, recovery, proof, phase, plan, files, origin)
        _need(pin['path'] == identity['backup'], 'accepted_archive_binding_invalid')
        archive = Path(_host_path(pin['path']))
        _need(archive.is_relative_to(backup_root) and archive.parent != backup_root and isinstance(pin['sha256'], str)
              and _HEX.fullmatch(pin['sha256']) and type(pin['size']) is int and pin['size'] > 0, 'accepted_local_archives_missing')
    _need(archives['current']['path'] != archives['previous']['path'], 'distinct_recovery_archives_required')
    captured = proof.get('offhost_archive' if kind == 'unified-migration' else 'local_archive') or {}
    _need(captured.get('archive_sha256') == archives['current']['sha256'] and captured.get('archive_bytes') == archives['current']['size'],
          'accepted_local_archive_copy_unproven')
    if kind == 'configuration-only':
        _need(captured.get('path') == archives['current']['path']
              and all(captured.get(key) == archives['current'][key] for key in ('capture_phase', 'store_schema', 'recovery_role'))
              and captured.get('source_receipt') == recovery['source_receipt']
              and phase.get('bindings', {}).get('archive_sha256') == archives['current']['sha256']
              and phase.get('bindings', {}).get('source_receipt_sha256') == recovery['source_receipt']['sha256']
              and isinstance(phase.get('bindings', {}).get('source_inventory_sha256'), str)
              and _HEX.fullmatch(phase['bindings']['source_inventory_sha256']), 'accepted_local_archive_copy_unproven')
    expected_images = {}
    _need(isinstance(wrapper['images'], list) and wrapper['images'], 'accepted_images_invalid')
    for row in wrapper['images']:
        _need(isinstance(row, dict) and set(row) == {'image', 'source_sha'} and isinstance(row['image'], str)
              and _IMAGE.fullmatch(row['image']) and isinstance(row['source_sha'], str) and _SOURCE.fullmatch(row['source_sha'])
              and row['image'] not in expected_images, 'accepted_images_invalid')
        expected_images[row['image']] = row['source_sha']
    for identity in (current, previous, older):
        _need(expected_images.get(identity['image']) == identity['source_sha'], 'accepted_image_closure_incomplete')
    for image, source in proof.get('_accepted_native_images', {}).items():
        _need(expected_images.get(image) == source, 'accepted_image_closure_incomplete')
    for pair in snapshots.values():
        for row in pair.values():
            _need(expected_images.get(row['Image']) == row['Config'].get('Labels', {}).get('org.opencontainers.image.revision'),
                  'accepted_image_closure_incomplete')
    files.reread()
    post_app = _pair_app(snapshots['post'])
    caddy_id = None
    if kind == 'configuration-only':
        caddy_id = proof['_accepted_caddy']['Id']
        post_app['_storage_recovery_caddy'] = _caddy_snapshot(proof['_accepted_caddy'])
    native_origin = wrapper_ref if adoption is not None else proof.get('inherited_storage_recovery', {}).get('native_origin')
    return {'files': files, 'ledger': ledger, 'raw': raw, 'current': current, 'previous': previous,
        'previous_raw': previous_raw, 'previous_path': Path(wrapper['previous_ledger']['path']), 'older_path': Path(older_path),
        'older_raw': older_raw, 'baselines': baselines, 'wrapper': wrapper, 'proofs': archives, 'accepted': accepted,
        'post_app': post_app, 'images': expected_images, 'caddy_id': caddy_id, 'native_proof': proof, 'adoption': adoption,
        'native_origin': native_origin,
        'adoption_origin_sha256': adoption['descriptor']['origin_ledger']['sha256'] if adoption is not None and not native_only else None,
        'previous_adoption_origin_sha256': previous_adoption['adoption']['descriptor']['origin_ledger']['sha256'] if previous_adoption else None,
        'active_markers': {'data/information/store.json': marker_pins[marker_names[0]],
                           'inbox/.information-store.json': marker_pins[marker_names[1]]},
        'required_directories': mount_directories,
        'accepted_recovery_proofs': [{'schema': RECOVERY_PROOF_SCHEMA, **wrapper_ref, 'ledger_path': str(ledger_path),
            'ledger_sha256': _sha(raw), 'previous_ledger_path': wrapper['previous_ledger']['path'],
            'previous_ledger_sha256': wrapper['previous_ledger']['sha256']}]}


def validate_accepted_recovery_proofs(manifest: dict, *, read_file=None, stat_file=None) -> None:
    """Independently reopen the accepted closure before planning or each unlink.

    Large inventories are streamed by default. Reader/stat injection is for
    isolated fixtures only. This function neither inspects Docker nor rehashes
    the large runtime archives; callers independently enforce both live binding
    and archive identity/integrity checks. No private snapshot data is returned.
    """
    context = _load_accepted_closure(Path(_host_path(manifest.get('ledger_path'))), Path(_host_path(manifest.get('backup_root'))),
        older_path=Path(_host_path(manifest.get('previous_before_ledger_path'))), read_file=read_file, stat_file=stat_file)
    pins = sorted(context['files'].pins.values(), key=lambda row: row['path'])
    _need(manifest.get('accepted_recovery_proofs') == context['accepted_recovery_proofs']
          and manifest.get('accepted_content_pins') == pins, 'accepted_content_manifest_mismatch')
    _need(manifest.get('accepted_promotion_receipts') == context['accepted'], 'accepted_promotion_manifest_mismatch')
    _need(manifest.get('ledger_sha256') == _sha(context['raw'])
          and manifest.get('previous_ledger_path') == str(context['previous_path'])
          and manifest.get('previous_ledger_sha256') == _sha(context['previous_raw'])
          and manifest.get('previous_before_ledger_sha256') == _sha(context['older_raw']), 'accepted_ledger_manifest_mismatch')
    _need(manifest.get('live_binding') == recovery_live_binding(context['post_app']), 'accepted_live_configuration_mismatch')
    _need(manifest.get('operation_kind') == context['wrapper']['operation_kind']
          and manifest.get('accepted_caddy_id') == context['caddy_id']
          and manifest.get('accepted_native_origin') == context['native_origin']
          and manifest.get('adoption_origin_ledger_sha256') == context['adoption_origin_sha256']
          and manifest.get('previous_adoption_origin_ledger_sha256') == context['previous_adoption_origin_sha256'],
          'accepted_operation_manifest_mismatch')
    for role, identity in [('current', context['current']), ('previous', context['previous'])]:
        rows = [row for row in manifest.get('recovery_sets', []) if row.get('role') == role]
        _need(len(rows) == 1 and all(rows[0].get(key) == identity[key] for key in ('image', 'source_sha', 'stage'))
              and all(rows[0].get('backup', {}).get(key) == value for key, value in context['proofs'][role].items()),
              'accepted_recovery_set_mismatch')
    expected = {pin['path'] for pin in pins}
    expected.update(context['wrapper']['protected_dirs'])
    protected = manifest.get('protected_paths', [])
    _need(all(any(row.get('path') == name or row.get('kind') == 'directory' and Path(name).is_relative_to(Path(row['path']))
                  for row in protected) for name in expected), 'accepted_protection_closure_incomplete')
    _need(all(any(row.get('kind') == 'directory' and Path(name).is_relative_to(Path(row['path']))
                  for row in protected) for name in context['required_directories']), 'accepted_directory_protection_incomplete')
    _need(set(manifest.get('protected_images', [])) == set(context['images'])
          and {row.get('image'): row.get('source_sha') for row in manifest.get('protected_image_provenance', [])} == context['images'],
          'accepted_image_manifest_mismatch')


def accepted_native_origin(manifest: dict, *, read_file=None, stat_file=None) -> dict | None:
    """Return authenticated flat storage provenance for a later configuration.

    No environment values or full container snapshots leave this API. Runtime
    archives are verified separately by the caller's full collection.
    """
    validate_accepted_recovery_proofs(manifest, read_file=read_file, stat_file=stat_file)
    ref = manifest.get('accepted_native_origin')
    if ref is None:
        return None
    try:
        context = _load_accepted_closure_checked(None, Path(_host_path(manifest['backup_root'])),
            read_file=read_file, stat_file=stat_file, native_wrapper_ref=ref)
    except StorageRecoveryError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise StorageRecoveryError('accepted_recovery_proof_invalid') from None
    proof = context['native_proof']; recovery = context['wrapper']['recovery_files']
    return {'native_origin': ref, 'origin_proof': recovery['final_proof'], 'migration': proof['migration'],
        'raw_plan': recovery['raw_plan'], 'raw_manifest': recovery['raw_manifest'],
        'legacy_promotion_manifest': proof['legacy_promotion_manifest'], 'rollback_modules': recovery['rollback_modules'],
        'protected_dirs': [directory for directory in context['wrapper']['protected_dirs']
            if Path(directory).is_relative_to(Path(manifest['backup_root'])) and Path(directory) != Path(manifest['backup_root'])],
        'active_markers': list(context['active_markers'].values())}


def collect_recovery_manifest(ledger_path: Path = LEDGER_PATH, backup_root: Path = BACKUP_ROOT,
                              app_inspection: dict | None = None,
                              generated_at: datetime | None = None) -> dict:
    """Collect fresh evidence inside caller-held release locks; return JSON data.

    Missing accepted configuration proof holds retention. Private full Docker
    snapshots are hashed in memory; environment values never enter the result.
    """
    ledger_path, backup_root = Path(ledger_path), Path(backup_root)
    context = _load_accepted_closure(ledger_path, backup_root)
    raw, ledger = context['raw'], context['ledger']
    previous_path, previous_raw = context['previous_path'], context['previous_raw']
    older_path, older_raw = context['older_path'], context['older_raw']
    app = app_inspection if app_inspection is not None else _inspect_app(context['caddy_id'])
    _need(recovery_live_binding(app) == recovery_live_binding(context['post_app']), 'live_configuration_not_accepted')
    proofs = {}
    for role, pin in context['proofs'].items():
        proofs[role] = _archive_proof(Path(pin['path']), pin, Path(ledger['recovery_proof']['path']), active_markers=context['active_markers'])
    result = build_protection_manifest(ledger_bytes=raw, previous_ledger_bytes=previous_raw,
        ledger_path=str(ledger_path), previous_ledger_path=str(previous_path), app_inspection=app,
        current_baseline=context['baselines']['current'], previous_baseline=context['baselines']['previous'],
        backup_proofs=proofs, backup_root=str(backup_root), generated_at=generated_at,
        metadata_paths=tuple(context['files'].pins))
    paths = {row['path']: row['kind'] for row in result['protected_paths']}
    for directory in context['required_directories']:
        _need(directory not in paths or paths[directory] == 'directory', 'protected_path_kind_conflict')
        paths[directory] = 'directory'
    result['protected_paths'] = [{'path': name, 'kind': kind} for name, kind in sorted(paths.items())]
    result['protected_images'] = sorted(context['images'])
    result['protected_image_provenance'] = _verify_image_set(context['images'])
    result['accepted_promotion_receipts'] = context['accepted']
    result['accepted_recovery_proofs'] = context['accepted_recovery_proofs']
    result['accepted_content_pins'] = sorted(context['files'].pins.values(), key=lambda row: row['path'])
    result['operation_kind'] = context['wrapper']['operation_kind']
    result['accepted_caddy_id'] = context['caddy_id']
    result['accepted_native_origin'] = context['native_origin']
    result['adoption_origin_ledger_sha256'] = context['adoption_origin_sha256']
    result['previous_adoption_origin_ledger_sha256'] = context['previous_adoption_origin_sha256']
    result['previous_before_ledger_path'] = str(older_path)
    result['previous_before_ledger_sha256'] = _sha(older_raw)
    for row in result['protected_paths']:
        path = Path(row['path'])
        info = _safe(path, directory=row['kind'] == 'directory')
        _need(stat.S_ISDIR(info.st_mode) if row['kind'] == 'directory' else stat.S_ISREG(info.st_mode), 'protected_dependency_missing')
    context['files'].reread()
    if app_inspection is None:
        after = _inspect_app(context['caddy_id'])
        _need(recovery_live_binding(after) == result['live_binding'], 'live_app_changed_during_collection')
    return result
