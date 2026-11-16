"""Resolve the accepted current/previous recovery sets without changing them.

The collector is intended to run inside the caller's three release locks. It
never reads environment values into its output and never removes anything.
"""
from __future__ import annotations

from datetime import datetime, timezone
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

    def file(self, ref: dict, *, private=False, parse=False) -> bytes | None:
        _need(isinstance(ref, dict) and set(ref) in ({'path', 'sha256'}, {'path', 'sha256', 'mode'}), 'accepted_file_reference_invalid')
        name = _host_path(ref['path']); path = Path(name)
        _need(isinstance(ref['sha256'], str) and _HEX.fullmatch(ref['sha256']), 'accepted_file_reference_invalid')
        before = self.stat_file(path)
        mode = stat.S_IMODE(before.st_mode)
        maximum = 4 * 1024**2 if parse else 256 * 1024**2
        _need(stat.S_ISREG(before.st_mode) and getattr(before, 'st_nlink', 1) == 1
              and before.st_size <= maximum and not mode & 0o022,
              'accepted_file_permissions_or_bound_invalid')
        if private:
            _need(mode == 0o600 and getattr(before, 'st_uid', 0) == 0, 'accepted_private_file_invalid')
            self.private_paths.add(name)
        if 'mode' in ref:
            _need(type(ref['mode']) is int and 0 <= ref['mode'] <= 0o777 and mode == ref['mode'], 'accepted_file_mode_changed')
        if self.read_file is not None or parse:
            if self.read_file is not None:
                body = self.read_file(path, maximum)
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

    def json(self, ref: dict, *, private=True) -> dict:
        return _parsed(self.file(ref, private=private, parse=True))

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


def _configuration_only_proof(proof, plan, recovery, snapshots, wrapper, files):
    from copy import deepcopy
    _need(proof.get('pair_snapshots') == wrapper['snapshots']
          and all(proof.get('configuration_post', {}).get(name) == wrapper['configuration']['post'][name]
                  for name in ('app', 'copilot')), 'configuration_only_snapshot_unproven')
    inherited = proof.get('inherited_storage_recovery') or {}
    _need(inherited.get('kind') == 'inherited-active-unified-store', 'configuration_only_storage_unproven')
    origin = files.json(inherited.get('origin_proof'))
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
    return normalized, inherited.get('rollback_modules'), origin


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


def _load_accepted_closure_checked(ledger_path: Path, backup_root: Path, *, older_path=None, read_file=None, stat_file=None) -> dict:
    files = _AcceptedFiles(read_file, stat_file)
    raw = (read_file or _read)(ledger_path, 4 * 1024**2)
    ledger = _parsed(raw); current = _identity(ledger)
    files.file({'path': str(ledger_path), 'sha256': _sha(raw)}, private=True)
    pointer = ledger.get('recovery_proof')
    _need(isinstance(pointer, dict) and set(pointer) == {'schema', 'path', 'sha256'}
          and pointer['schema'] == RECOVERY_PROOF_SCHEMA, 'accepted_recovery_proof_missing')
    wrapper_ref = {key: pointer[key] for key in ('path', 'sha256')}
    _need(Path(_host_path(pointer['path'])).is_relative_to(Path(current['stage'])), 'accepted_recovery_proof_outside_stage')
    wrapper = files.json(wrapper_ref)
    _need(set(wrapper) == {'schema', 'operation_kind', 'operation_nonce', 'current', 'previous_ledger', 'plan', 'snapshots',
                          'configuration', 'recovery_files', 'protected_dirs', 'archives', 'images'}
          and wrapper['schema'] == RECOVERY_PROOF_SCHEMA, 'accepted_recovery_proof_schema_invalid')
    nonce = wrapper['operation_nonce']
    kind = wrapper['operation_kind']
    _need(kind in {'unified-migration', 'configuration-only'}, 'accepted_operation_kind_unsupported')
    _need(isinstance(nonce, str) and re.fullmatch('[a-f0-9]{32,64}', nonce), 'accepted_operation_nonce_invalid')
    _need(wrapper['current'] == {key: current[key] for key in ('source_sha', 'image', 'stage')}, 'accepted_current_identity_mismatch')
    previous_raw = files.file(wrapper['previous_ledger'], private=True, parse=True)
    previous_ledger = _parsed(previous_raw); previous = _identity(previous_ledger)
    _need(ledger.get('previous_image') == previous['image'], 'accepted_previous_identity_mismatch')
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
    _need(accepted[0]['old_ledger_sha256'] == wrapper['previous_ledger']['sha256'], 'accepted_previous_ledger_mismatch')
    if older_path is None:
        older_path, _ = _previous(previous_ledger, previous_raw)
    older_ref = {'path': str(older_path), 'sha256': accepted[1]['old_ledger_sha256']}
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
    _need(isinstance(recovery, dict) and set(recovery) == required, 'accepted_recovery_dependencies_missing')
    native = files.json(recovery['baseline']); plan = files.json(wrapper['plan'])
    phase = files.json(recovery['phase_receipt']); proof = files.json(recovery['final_proof'])
    _need(plan.get('operation_kind') == kind and proof.get('operation_kind') == kind
          and phase.get('bindings', {}).get('operation_kind') == kind, 'accepted_operation_kind_mismatch')
    inherited_modules, origin = [], None
    if kind == 'configuration-only':
        _need(current['image'] == previous['image'] and current['source_sha'] == previous['source_sha'], 'configuration_only_runtime_changed')
        proof, inherited_modules, origin = _configuration_only_proof(proof, plan, recovery, snapshots, wrapper, files)
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
    return {'files': files, 'ledger': ledger, 'raw': raw, 'current': current, 'previous': previous,
        'previous_raw': previous_raw, 'previous_path': Path(wrapper['previous_ledger']['path']), 'older_path': Path(older_path),
        'older_raw': older_raw, 'baselines': baselines, 'wrapper': wrapper, 'proofs': archives, 'accepted': accepted,
        'post_app': post_app, 'images': expected_images, 'caddy_id': caddy_id,
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
          and manifest.get('accepted_caddy_id') == context['caddy_id'], 'accepted_operation_manifest_mismatch')
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
