#!/usr/bin/env python3
"""Generate a private current/previous recovery protection manifest."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.storage_recovery import (  # noqa: E402
    BACKUP_ROOT, LEDGER_PATH, SHARED_RELEASE_LOCKS, StorageRecoveryError,
    _read, _safe, collect_recovery_manifest,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger-path', type=Path, default=LEDGER_PATH)
    parser.add_argument('--backup-root', type=Path, default=BACKUP_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if os.name != 'posix' or os.geteuid() != 0:
        raise StorageRecoveryError('host_root_required')
    import fcntl
    with ExitStack() as stack:
        for path in SHARED_RELEASE_LOCKS:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise StorageRecoveryError('release_lock_type_invalid')
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            stack.callback(os.close, fd)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        value = collect_recovery_manifest(args.ledger_path, args.backup_root)
        body = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
        output = args.output.absolute()
        _safe(output.parent, directory=True)
        if not output.parent.is_dir() or output.parent.is_symlink() or output.is_symlink():
            raise StorageRecoveryError('private_output_path_invalid')
        for protected in value['protected_paths']:
            path = Path(protected['path'])
            if output == path or (protected['kind'] == 'directory' and output.is_relative_to(path)):
                raise StorageRecoveryError('output_overlaps_protected_recovery')
        if output.exists():
            existing = json.loads(_read(output))
            if existing.get('version') != 1 or existing.get('ledger_path') != value['ledger_path'] or not isinstance(existing.get('recovery_sets'), list):
                raise StorageRecoveryError('output_is_not_recovery_manifest')
        info = output.parent.stat()
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
            raise StorageRecoveryError('private_output_directory_required')
        fd, name = tempfile.mkstemp(prefix='.recovery-protection-', dir=output.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, output)
            directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({'status': 'RECOVERY_PROTECTION_READY', 'manifest_sha256': hashlib.sha256(body).hexdigest(),
                      'ledger_sha256': value['ledger_sha256'], 'recovery_sets': len(value['recovery_sets']),
                      'protected_paths': len(value['protected_paths']), 'output': str(output)}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (StorageRecoveryError, OSError, ValueError):
        print(json.dumps({'status': 'RECOVERY_PROTECTION_HELD', 'raw_details_suppressed': True}))
        raise SystemExit(1)
