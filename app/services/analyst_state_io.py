"""Atomic private JSON writes and per-runtime serialization in the local worker."""
from functools import wraps
import json
import os
from pathlib import Path
import tempfile
from time import sleep
from threading import Lock, RLock

_guard = Lock()
_locks: dict[str, RLock] = {}


def serialized_write(function):
    @wraps(function)
    def write(inbox_dir, *args, **kwargs):
        key = str(Path(inbox_dir).resolve())
        with _guard:
            lock = _locks.setdefault(key, RLock())
        with lock:
            return function(inbox_dir, *args, **kwargs)
    return write


def atomic_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Windows may briefly deny replacement while a concurrent reader or
        # scanner holds the destination. Keep the old file intact until success.
        for attempt in range(4):
            try:
                temporary.replace(path)
                break
            except PermissionError as exc:
                if getattr(exc, 'winerror', None) not in {5, 32} or attempt == 3:
                    raise
                sleep(0.025 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)
