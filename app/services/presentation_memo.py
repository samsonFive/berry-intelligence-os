"""Bounded private memoization of deterministic presentation calculations.

Keys contain exact inputs, never record IDs alone. No rendered/authenticated
responses are cached. Every mutable result is copied before returning.
"""
from collections import OrderedDict
from copy import deepcopy
from functools import wraps
import json
import hashlib
from threading import RLock


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
            return deepcopy(row[0])

    def put(self, key, value):
        try:
            size = len(key.encode('utf-8')) + len(json.dumps(value, ensure_ascii=False,
                default=lambda row: sorted(row) if isinstance(row, set) else row.isoformat()).encode('utf-8'))
        except (TypeError, ValueError, AttributeError):
            return
        if size > min(self.max_bytes, self.max_item):
            return
        with self.lock:
            prior = self.rows.pop(key, None)
            if prior:
                self.bytes -= prior[1]
            self.rows[key] = (deepcopy(value), size)
            self.bytes += size
            while self.bytes > self.max_bytes or len(self.rows) > self.max_entries:
                _, removed = self.rows.popitem(last=False)
                self.bytes -= removed[1]


def record_memo(fields):
    def decorate(function):
        memo = ByteMemo()
        @wraps(function)
        def wrapped(record):
            key = json.dumps({k: record[k] for k in fields if k in record}, sort_keys=True, ensure_ascii=False)
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
