"""Bounded private memoization of deterministic presentation calculations.

Keys contain exact inputs, never record IDs alone. No rendered/authenticated
responses are cached. Every mutable result is copied before returning.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from io import BytesIO
import json
import hashlib
import pickle
from threading import RLock


_SNAPSHOT_MIN_BYTES = 64_000


@dataclass(frozen=True, slots=True)
class _BuiltinSnapshot:
    # Created locally from an allowlisted graph, never from files or requests.
    payload: bytes


class _BuiltinUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # Builtin container opcodes need no global/class lookup. Even an
        # accidentally corrupted internal entry cannot import/execute classes.
        raise pickle.UnpicklingError('Presentation snapshots cannot load classes')


class _BuiltinPickler(pickle.Pickler):
    def reducer_override(self, value):
        # The C pickler handles exact builtin atoms/containers without this
        # callback. Every object needing a class/reducer uses legacy deepcopy.
        raise pickle.PicklingError('Presentation snapshots cannot save classes')


def _owned_cache_value(value, size, encoded):
    # deepcopy retains NaN objects by identity. Conservatively retain its path
    # for any nonfinite token, including harmless occurrences inside strings.
    if (size >= _SNAPSHOT_MIN_BYTES and type(value) in {dict, list, tuple, set, frozenset}
            and 'NaN' not in encoded and 'Infinity' not in encoded):
        try:
            buffer = BytesIO()
            _BuiltinPickler(buffer, protocol=5).dump(value)
            payload = buffer.getvalue()
            if len(payload) <= size:
                return _BuiltinSnapshot(payload)
        except pickle.PicklingError:
            pass
    return deepcopy(value)


class ByteMemo:
    def __init__(self, max_bytes=64_000_000, max_entries=8192, max_item=256_000):
        self.rows = OrderedDict()
        self.bytes = 0
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.max_item = max_item
        self.lock = RLock()

    def get(self, key):
        with self.lock:
            row = self.rows.get(key)
            if row is None:
                return None
            self.rows.move_to_end(key)
            if type(row[0]) is _BuiltinSnapshot:
                try:
                    return _BuiltinUnpickler(BytesIO(row[0].payload)).load()
                except (pickle.UnpicklingError, EOFError, ValueError, TypeError):
                    # A private cache entry is disposable; recompute from the
                    # original current inputs rather than serving corrupt data.
                    self.rows.pop(key)
                    self.bytes -= row[1]
                    return None
            return deepcopy(row[0])

    def put(self, key, value):
        try:
            encoded = json.dumps(value, ensure_ascii=False,
                default=lambda row: sorted(row) if isinstance(row, set) else row.isoformat())
            value_size = len(encoded.encode('utf-8'))
            size = len(key.encode('utf-8')) + value_size
        except (TypeError, ValueError, AttributeError):
            return
        if size > min(self.max_bytes, self.max_item):
            return
        owned = _owned_cache_value(value, value_size, encoded)
        with self.lock:
            prior = self.rows.pop(key, None)
            if prior:
                self.bytes -= prior[1]
            self.rows[key] = (owned, size)
            self.bytes += size
            while self.bytes > self.max_bytes or len(self.rows) > self.max_entries:
                _, removed = self.rows.popitem(last=False)
                self.bytes -= removed[1]


def record_memo(fields):
    def decorate(function):
        memo = ByteMemo()
        @wraps(function)
        def wrapped(record):
            try:
                key = json.dumps({k: record[k] for k in fields if k in record}, sort_keys=True, ensure_ascii=False)
            except (TypeError, ValueError):
                return function(record)
            if len(key) > 128_000:
                return function(record)
            cached = memo.get(key)
            if cached is not None:
                return cached
            result = function(record)
            memo.put(key, result)
            return result
        return wrapped
    return decorate


def json_call_memo(function):
    """Pure JSON read model, invalidated by every input and the UTC day."""
    from datetime import datetime, UTC
    memo = ByteMemo(max_bytes=32_000_000, max_entries=4, max_item=16_000_000)
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            raw = json.dumps([datetime.now(UTC).date().isoformat(), args, kwargs], sort_keys=True,
                             ensure_ascii=False, default=lambda x: x.isoformat()).encode('utf-8')
        except (TypeError, ValueError, AttributeError):
            return function(*args, **kwargs)
        if len(raw) > 32_000_000:
            return function(*args, **kwargs)
        key = hashlib.sha256(raw).hexdigest()
        cached = memo.get(key)
        if cached is not None:
            return cached
        value = function(*args, **kwargs)
        memo.put(key, value)
        return value
    return wrapped


def flat_json_signature(folder):
    """Exact inventory including replacements, deletions and permission changes."""
    rows = []
    for path in sorted(folder.glob('*.json')):
        try:
            stat = path.stat()
            rows.append((path.name, stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
        except OSError:
            rows.append((path.name, None))
    return json.dumps([str(folder.resolve()), rows])
