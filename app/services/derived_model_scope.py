"""Opt-in private calculation reuse; ordinary pages have no writer capability."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, UTC
from functools import lru_cache, wraps
from io import BytesIO
import hashlib
import hmac
import os
from pathlib import Path
import pickle
import sys
from types import CodeType, FunctionType

from app.services.derived_model_store import DerivedModelStore, ModelKey

NOT_HANDLED = object()
_active: ContextVar["DerivedModelScope | None"] = ContextVar("private_derived_model_scope", default=None)
_MAX_INPUT = 32_000_000
_MODELS = {
    "app.services.variety_universe.corpus_discovery.build_discovered_candidates": dict,
    "app.services.variety_portfolio_coverage.reconcile_portfolios": tuple,
}


def current_scope():
    return _active.get()


def utc_day():
    return datetime.now(UTC).date().isoformat()


def local_day():
    # Portfolio freshness uses date.today(). Bind that day as well as UTC so
    # a configured non-UTC runtime cannot reuse yesterday's freshness labels.
    return datetime.now().date().isoformat()


class _BoundedBuffer(BytesIO):
    def write(self, value):
        if self.tell() + len(value) > _MAX_INPUT:
            raise ValueError("Derived-model input exceeds its budget")
        return super().write(value)


def _input_bytes(value):
    from app.services.presentation_memo import _BuiltinPickler
    buffer = _BoundedBuffer()
    pickler = _BuiltinPickler(buffer, protocol=5)
    # Source models are value calculations. Disable object-reference memoing
    # in this key only: equal strings/containers parsed in another worker must
    # not change the key merely because their sharing differs. Types and order
    # remain exact. Cycles, opaque values and unsupported implementations fall
    # back to the original calculation; result snapshots retain normal memos.
    pickler.fast = True
    pickler.dump(value)
    return buffer.getvalue()


def _code_value(code):
    def constant(value):
        if type(value) is CodeType:
            return ("code", _code_value(value))
        if type(value) is tuple:
            return ("tuple", tuple(constant(row) for row in value))
        if type(value) is frozenset:
            return ("frozenset", tuple(sorted(_input_bytes(constant(row)) for row in value)))
        if type(value) is complex:
            return ("complex", value.real, value.imag)
        if value is Ellipsis:
            return ("ellipsis",)
        return (type(value).__name__, value)
    return (code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount,
            code.co_nlocals, code.co_stacksize, code.co_flags, code.co_code,
            code.co_exceptiontable, tuple(constant(value) for value in code.co_consts),
            code.co_names, code.co_varnames, code.co_freevars, code.co_cellvars)


@lru_cache(maxsize=64)
def executing_code_digest(code):
    # marshal's reference flags can change with ordinary object refcounts.
    # Encode immutable semantic fields by value instead, including sorted
    # frozenset constants and nested code; hash seeds and retained results do
    # not change this identity. The full image fingerprint also binds source.
    return hashlib.sha256(_input_bytes(_code_value(code))).digest()


@lru_cache(maxsize=4)
def code_version(repo_root: Path):
    """Immutable application image plus schemas; never source/runtime files."""
    runtime = (sys.version, sys.implementation.cache_tag, sys.flags.optimize)
    digest = hashlib.sha256(b"berry-private-derived-models-v1\0" + repr(runtime).encode())
    for folder in (repo_root / "app", repo_root / "schemas"):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".json"}:
                digest.update(str(path.relative_to(repo_root)).replace("\\", "/").encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
    return digest.hexdigest()


@dataclass
class DerivedModelScope:
    store: DerivedModelStore
    code_digest: str
    writer: bool = False
    counts: dict = field(default_factory=lambda: dict(memory_hits=0, artifact_hits=0,
        calculations=0, writes=0, invalid_results=0, unsupported=0))

    def execute(self, function, args, kwargs, memo):
        from app.services.presentation_memo import _BuiltinUnpickler, _BuiltinSnapshot
        if type(function) is not FunctionType:
            return NOT_HANDLED
        identity = function.__module__ + "." + function.__qualname__
        expected_type = _MODELS.get(identity)
        if expected_type is None or function.__closure__:
            return NOT_HANDLED
        try:
            input_digest = hashlib.sha256(_input_bytes((local_day(), args, kwargs))).hexdigest()
            executing_code = hashlib.sha256(self.code_digest.encode() + b"\0"
                + executing_code_digest(function.__code__)
                + _input_bytes((function.__defaults__, function.__kwdefaults__))).hexdigest()
            key = ModelKey(hashlib.sha256(identity.encode()).hexdigest(), input_digest,
                           executing_code, utc_day())
        except (AttributeError, TypeError, ValueError, pickle.PickleError, RecursionError):
            self.counts["unsupported"] += 1
            return NOT_HANDLED
        # Separate the ordinary memo and every runtime/code/day context.
        memory_key = "derived:" + self.store.context_digest + ":" + hashlib.sha256(self.store._header(key)).hexdigest()
        value = memo.get(memory_key)
        if value is not None:
            self.counts["memory_hits"] += 1
            if self.writer:
                self._write_admitted(memo, memory_key, key, _BuiltinSnapshot)
            return value
        payload = self.store.load(key)
        if payload is not None:
            try:
                stream = BytesIO(payload)
                value = _BuiltinUnpickler(stream).load()
                if type(value) is not expected_type or stream.read(1):
                    raise ValueError("Unexpected derived-model representation")
                if expected_type is tuple and (len(value) != 2 or any(type(row) is not list for row in value)):
                    raise ValueError("Unexpected portfolio representation")
            except (pickle.UnpicklingError, EOFError, ValueError, TypeError, RecursionError, OverflowError):
                self.counts["invalid_results"] += 1
            else:
                memo.put(memory_key, value)
                self.counts["artifact_hits"] += 1
                return value
        self.counts["calculations"] += 1
        value = function(*args, **kwargs)
        memo.put(memory_key, value)
        if self.writer and type(value) is expected_type:
            self._write_admitted(memo, memory_key, key, _BuiltinSnapshot)
        return value

    def _write_admitted(self, memo, memory_key, key, snapshot_type):
        with memo.lock:
            row = memo.rows.get(memory_key)
            snapshot = row[0] if row else None
            payload = snapshot.payload if type(snapshot) is snapshot_type else None
        if payload is not None and self.store.write(key, payload):
            self.counts["writes"] += 1


@contextmanager
def model_scope(scope: DerivedModelScope):
    token = _active.set(scope)
    try:
        yield scope
    finally:
        _active.reset(token)


def configured_scope(*, repo_root, data_dir, schemas_dir, inbox_dir, preparation=False):
    """No work when disabled; production signing uses purpose-separated material."""
    from app.runtime_config import env_flag, session_secret
    if (os.name != "posix" or os.environ.get("BIOS_MODE", "authoring") != "authoring"
            or (not preparation and not env_flag("BIOS_PRIVATE_READ_MODELS"))):
        return None
    secret = session_secret()
    if len(secret) < 32:
        return None
    try:
        artifact_parent = Path(os.environ.get("BIOS_PRIVATE_MODEL_ROOT") or inbox_dir).expanduser().absolute()
        resolved_parent = artifact_parent.resolve()
        public_or_canonical = (Path(data_dir).resolve(), Path(schemas_dir).resolve(),
            (Path(repo_root) / "generated").resolve(), (Path(repo_root) / "app" / "static").resolve())
        if any(resolved_parent.is_relative_to(folder) for folder in public_or_canonical):
            return None
        context = hashlib.sha256(("private-authoring-v1\0" + "\0".join(
            str(Path(path).resolve()) for path in (data_dir, schemas_dir, inbox_dir))).encode()).hexdigest()
        signing_key = hmac.digest(secret.encode(), b"berry-derived-model-integrity-v1\0" + context.encode(), "sha256")
        return DerivedModelScope(DerivedModelStore(artifact_parent, context, signing_key),
                                 code_version(Path(repo_root)), writer=preparation)
    except (OSError, ValueError):
        return None


def private_catalog_models(function):
    """Only an actual private authoring request opts in; static/CLI stays off."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        if current_scope() is not None:
            return function(*args, **kwargs)
        from app.runtime_config import env_flag
        if not env_flag("BIOS_PRIVATE_READ_MODELS") or not function.__globals__.get("AUTHORING_MODE"):
            return function(*args, **kwargs)
        from app.services.request_corpus import get_request_corpus
        if get_request_corpus() is None:
            return function(*args, **kwargs)
        values = function.__globals__
        scope = configured_scope(repo_root=values["BASE_DIR"], data_dir=values["DATA_DIR"],
            schemas_dir=values["SCHEMAS_DIR"], inbox_dir=values["INBOX_DIR"])
        if scope is None:
            return function(*args, **kwargs)
        with model_scope(scope):
            return function(*args, **kwargs)
    return wrapped
