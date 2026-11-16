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


def _sidecar_snapshot(sidecar: dict) -> dict:
    state = sidecar.get('State') or {}
    return {'container_id': sidecar.get('Id'), 'image': sidecar.get('Image'),
            'healthy': state.get('Running') is True and state.get('Health', {}).get('Status') == 'healthy',
            'network_mode': sidecar.get('HostConfig', {}).get('NetworkMode')}


def recovery_live_binding(app_inspection: dict, sidecar_inspection: dict | None = None) -> dict:
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
          and type(node.get('healthy')) is bool and isinstance(node.get('network_mode'), str), 'live_copilot_metadata_missing')
    node = {name: node[name] for name in ['container_id', 'image', 'healthy', 'network_mode']}
    return {'app_id': identity, 'image': image, 'source_sha': source,
            'mount_fingerprint': _sha(serialize(ordered_mounts)),
            'compose_fingerprint': _sha(serialize(files)),
            'healthy': state.get('Running') is True and state.get('Health', {}).get('Status') == 'healthy'
                       and node['healthy'] and node['network_mode'] == 'container:' + identity,
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


def _archive_proof(path: Path, receipt: dict, receipt_path: Path) -> dict:
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
        with gzip.open(path, 'rb') as stream:
            for _block in iter(lambda: stream.read(4 * 1024**2), b''):
                pass
    except Exception:
        raise StorageRecoveryError('protected_archive_integrity_failed') from None
    _need(manifest.get('files') and manifest.get('scope') == ['data', 'inbox'], 'protected_archive_scope_invalid')
    after = _safe(path)
    before_key = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    _need(before_key == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'protected_archive_changed')
    return {'path': str(path), 'size': after.st_size, 'sha256': h.hexdigest(), 'verified': True,
            'device': after.st_dev, 'inode': after.st_ino, 'mtime_ns': after.st_mtime_ns,
            'uid': after.st_uid, 'gid': after.st_gid, 'mode': stat.S_IMODE(after.st_mode),
            'receipt_path': str(receipt_path), 'manifest_file_count': len(manifest['files'])}


def _inspect_app() -> dict:
    run = subprocess.run(['docker', 'inspect', 'deploy-app-1', 'deploy-copilot-1'], input=b'', capture_output=True, timeout=30)
    _need(run.returncode == 0, 'live_app_inspection_failed')
    try:
        rows = json.loads(run.stdout)
    except ValueError:
        raise StorageRecoveryError('live_app_inspection_failed') from None
    _need(isinstance(rows, list) and len(rows) == 2 and all(isinstance(row, dict) for row in rows), 'live_app_inspection_failed')
    app, node = rows
    app['_storage_recovery_sidecar'] = _sidecar_snapshot(node)
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


def collect_recovery_manifest(ledger_path: Path = LEDGER_PATH, backup_root: Path = BACKUP_ROOT,
                              app_inspection: dict | None = None,
                              generated_at: datetime | None = None) -> dict:
    """Collect fresh evidence inside caller-held release locks; return JSON data.

    Callers must not reuse this result after its ledger or live-image binding
    changes. Environment values in Docker/recipe objects are never traversed.
    """
    ledger_path, backup_root = Path(ledger_path), Path(backup_root)
    raw = _read(ledger_path)
    ledger = _parsed(raw)
    current = _identity(ledger)
    previous_path, previous_raw = _previous(ledger, raw)
    previous_ledger = _parsed(previous_raw)
    previous = _identity(previous_ledger)
    older_path, older_raw = _previous(previous_ledger, previous_raw)
    older = _identity(_parsed(older_raw))
    app = app_inspection if app_inspection is not None else _inspect_app()
    baselines, proofs, metadata = {}, {}, [str(previous_path), str(older_path)]
    accepted = []
    for role, document, body in [('current', ledger, raw), ('previous', previous_ledger, previous_raw)]:
        receipt = _accepted_promotion(document, body)
        metadata.append(receipt['path']); accepted.append({'role': role, **receipt})
    for role, identity in [('current', current), ('previous', previous)]:
        stage = Path(identity['stage'])
        baseline = stage / 'operator-private/baseline-private.json'
        baselines[role] = _parsed(_read(baseline))
        metadata.append(str(baseline))
        archive = Path(identity['backup'])
        _need(archive.is_relative_to(backup_root), 'recovery_archive_outside_root')
        receipt_path, receipt = _backup_receipt(stage, archive, backup_root)
        proofs[role] = _archive_proof(archive, receipt, receipt_path)
        metadata.append(str(receipt_path))
    result = build_protection_manifest(ledger_bytes=raw, previous_ledger_bytes=previous_raw,
        ledger_path=str(ledger_path), previous_ledger_path=str(previous_path), app_inspection=app,
        current_baseline=baselines['current'], previous_baseline=baselines['previous'],
        backup_proofs=proofs, backup_root=str(backup_root), generated_at=generated_at,
        metadata_paths=tuple(metadata))
    expected_images = {}

    def image_source(image, source):
        _need(isinstance(image, str) and _IMAGE.fullmatch(image) and isinstance(source, str) and _SOURCE.fullmatch(source),
              'recovery_image_source_unknown')
        _need(image not in expected_images or expected_images[image] == source, 'recovery_image_source_conflict')
        expected_images[image] = source

    for identity in [current, previous, older]:
        image_source(identity['image'], identity['source_sha'])
    for baseline in baselines.values():
        image_source(baseline.get('node_image'), baseline.get('node_component_source'))
    _need(set(result['protected_images']).issubset(expected_images), 'recovery_image_source_unresolved')
    result['protected_image_provenance'] = _verify_image_set({image: expected_images[image] for image in result['protected_images']})
    result['accepted_promotion_receipts'] = accepted
    result['previous_before_ledger_path'] = str(older_path)
    result['previous_before_ledger_sha256'] = _sha(older_raw)
    for row in result['protected_paths']:
        path = Path(row['path'])
        info = _safe(path, directory=row['kind'] == 'directory')
        _need(stat.S_ISDIR(info.st_mode) if row['kind'] == 'directory' else stat.S_ISREG(info.st_mode), 'protected_dependency_missing')
    _need(_read(ledger_path) == raw and _read(previous_path) == previous_raw and _read(older_path) == older_raw,
          'recovery_ledger_changed_during_collection')
    for receipt in accepted:
        _need(_sha(_read(Path(receipt['path']))) == receipt['sha256'], 'accepted_promotion_changed_during_collection')
    if app_inspection is None:
        after = _inspect_app()
        _need(recovery_live_binding(after) == result['live_binding'], 'live_app_changed_during_collection')
    return result
