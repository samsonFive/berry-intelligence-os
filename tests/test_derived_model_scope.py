"""Current-input reuse, explicit writer ownership, fallback and private scope."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import hashlib
from io import BytesIO
import os
from pathlib import Path
import pickle
import tempfile
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services.derived_model_scope import (
    DerivedModelScope, _input_bytes, configured_scope, current_scope,
    model_scope, private_catalog_models, executing_code_digest,
)
from app.services.derived_model_store import DerivedModelStore
from app.services.presentation_memo import json_call_memo

_calls = []
_stamp = "first materialization"
AUTHORING_MODE = True
BASE_DIR = DATA_DIR = SCHEMAS_DIR = INBOX_DIR = Path(tempfile.gettempdir())


def model(*, values, label="original"):
    _calls.append(deepcopy(values))
    return {"candidates": [], "mentions": [], "values": deepcopy(values), "label": label,
            "discovered_at": _stamp,
            "rows": [{"id": str(i), "text": "Literal unreviewed source text " * 50} for i in range(100)]}


model.__module__ = "app.services.variety_universe.corpus_discovery"
model.__qualname__ = "build_discovered_candidates"


class MemoryStore:
    """Scope-only fixture. Real filesystem/HMAC behavior has its own contracts."""
    _header = DerivedModelStore._header
    context_digest = hashlib.sha256(b"fixture-runtime").hexdigest()

    def __init__(self):
        self.values = {}
        self.writes = 0

    def load(self, key):
        return self.values.get(key)

    def write(self, key, value):
        self.writes += 1
        self.values[key] = value
        return True


class ScopeTests(unittest.TestCase):
    def setUp(self):
        _calls.clear()
        self.store = MemoryStore()
        self.version = hashlib.sha256(b"immutable-code-version").hexdigest()
        self.day = patch("app.services.derived_model_scope.utc_day", return_value="2026-11-03")
        self.day.start(); self.addCleanup(self.day.stop)

    def scope(self, *, writer=False):
        return DerivedModelScope(self.store, self.version, writer=writer)

    def prepare(self, values):
        scope = self.scope(writer=True)
        with model_scope(scope):
            value = json_call_memo(model)(values=values)
        self.assertEqual(scope.counts["writes"], 1)
        return value

    def test_fresh_scope_reuses_same_day_materialization_and_owns_results(self):
        values = {"body": "source wording", "decision": "distinct"}
        first = self.prepare(values)
        with patch(__name__ + "._stamp", "later process clock"), model_scope(self.scope()) as scope:
            result = json_call_memo(model)(values=values)
        self.assertEqual(result, first)
        self.assertEqual(len(_calls), 1)
        self.assertEqual(scope.counts["artifact_hits"], 1)
        result["values"]["decision"] = "local mutation"
        with model_scope(self.scope()):
            self.assertEqual(json_call_memo(model)(values=values), first)

    def test_current_body_identity_and_review_edits_calculate_without_writing(self):
        original = {"body": "old body", "url": "https://example.test/original", "review": {"state": "rejected"}}
        self.prepare(original)
        writes = self.store.writes
        for values in [{**original, "body": "new literal body"},
                       {**original, "url": "https://example.test/other"},
                       {**original, "review": {"state": "distinct"}}]:
            with model_scope(self.scope()) as scope:
                result = json_call_memo(model)(values=values)
            self.assertEqual(result["values"], values)
            self.assertEqual(scope.counts["calculations"], 1)
            self.assertEqual(scope.counts["writes"], 0)
        self.assertEqual(self.store.writes, writes)

    def test_next_day_and_changed_code_or_runtime_are_current_misses(self):
        self.prepare(["source"])
        with patch("app.services.derived_model_scope.utc_day", return_value="2026-11-04"), model_scope(self.scope()) as scope:
            json_call_memo(model)(values=["source"])
        self.assertEqual(scope.counts["calculations"], 1)
        for scope in [replace(self.scope(), code_digest=hashlib.sha256(b"new code").hexdigest()),
                      replace(self.scope(), store=SimpleNamespace(context_digest="other", load=lambda key: None, _header=self.store._header))]:
            with model_scope(scope):
                json_call_memo(model)(values=["source"])
            self.assertEqual(scope.counts["calculations"], 1)

    def test_function_defaults_are_bound_to_the_artifact(self):
        self.prepare(["source"])
        with patch.object(model, "__kwdefaults__", {"label": "changed default"}), model_scope(self.scope()) as scope:
            result = json_call_memo(model)(values=["source"])
        self.assertEqual(result["label"], "changed default")
        self.assertEqual(scope.counts["calculations"], 1)

    def test_typed_keys_ignore_sharing_but_preserve_types_order_and_unicode(self):
        text = "A literal Mérita 🌿 source phrase " * 20
        other = ("!" + text)[1:]
        self.assertIsNot(text, other)
        self.assertEqual(_input_bytes([text, text]), _input_bytes([text, other]))
        self.assertNotEqual(_input_bytes([True]), _input_bytes([1]))
        self.assertNotEqual(_input_bytes([1]), _input_bytes([1.0]))
        self.assertNotEqual(_input_bytes([1, 2]), _input_bytes((1, 2)))
        self.assertNotEqual(_input_bytes({"a": 1, "b": 2}), _input_bytes({"b": 2, "a": 1}))
        shared = [{"value": "same source"}]
        self.assertEqual(_input_bytes([shared, shared]), _input_bytes([deepcopy(shared), deepcopy(shared)]))

    def test_executing_code_identity_survives_retained_results_and_refcounts(self):
        executing_code_digest.cache_clear()
        first = executing_code_digest(model.__code__)
        retained = [model(values=["source"]) for _ in range(5)]
        held_constants = [model.__code__.co_consts] * 50
        executing_code_digest.cache_clear()
        self.assertEqual(executing_code_digest(model.__code__), first)
        self.assertTrue(retained and held_constants)

    def test_actual_model_code_identity_is_stable_across_worker_hash_seeds(self):
        code = "from app.services.derived_model_scope import executing_code_digest; from app.services.variety_portfolio_coverage import reconcile_portfolios; from app.services.variety_universe.corpus_discovery import build_discovered_candidates; print([executing_code_digest(f.__wrapped__.__code__).hex() for f in (reconcile_portfolios,build_discovered_candidates)])"
        results = [subprocess.check_output([sys.executable, "-c", code], env={**os.environ, "PYTHONHASHSEED": seed}, text=True)
                   for seed in ("0", "93")]
        self.assertEqual(results[0], results[1])

    def test_corrupt_shape_class_and_trailing_bytes_fall_back_without_repairs(self):
        first = self.prepare(["source"])
        identity, payload = next(iter(self.store.values.items()))
        writes = self.store.writes
        for invalid in [pickle.dumps([]), pickle.dumps(date(2026, 11, 3)), payload + b"trailing", b"not a snapshot"]:
            self.store.values[identity] = invalid
            with model_scope(self.scope()) as scope:
                result = json_call_memo(model)(values=["source"])
            self.assertEqual(result, first)
            self.assertEqual(scope.counts["invalid_results"], 1, repr(invalid[:24]))
            self.assertEqual(scope.counts["calculations"], 1)
            self.assertEqual(self.store.values[identity], invalid)
        self.assertEqual(self.store.writes, writes)

    def test_memory_result_does_not_leak_between_runtime_or_day_contexts(self):
        wrapped = json_call_memo(model)
        with model_scope(self.scope()):
            wrapped(values=["source"])
            wrapped(values=["source"])
        self.assertEqual(len(_calls), 1)
        with patch("app.services.derived_model_scope.utc_day", return_value="2026-11-04"), model_scope(self.scope()):
            wrapped(values=["source"])
        self.assertEqual(len(_calls), 2)
        other = MemoryStore(); other.context_digest = hashlib.sha256(b"other-runtime").hexdigest()
        with model_scope(DerivedModelScope(other, self.version)):
            wrapped(values=["source"])
        self.assertEqual(len(_calls), 3)

    def test_ordinary_and_unsupported_calls_keep_original_behavior(self):
        wrapped = json_call_memo(model)
        outside = wrapped(values=["source"])
        self.assertEqual(self.store.values, {})
        cycle = []; cycle.append(cycle)
        with model_scope(self.scope()) as scope:
            result = wrapped(values=cycle)
        self.assertIs(result["values"][0], result["values"])
        self.assertEqual(scope.counts["unsupported"], 1)
        self.assertEqual(self.store.values, {})
        self.assertEqual(outside["values"], ["source"])

    def test_context_resets_after_nested_scopes_and_errors(self):
        self.assertIsNone(current_scope())
        outer = self.scope()
        with model_scope(outer):
            with self.assertRaises(RuntimeError):
                with model_scope(self.scope(writer=True)):
                    raise RuntimeError("fixture")
            self.assertIs(current_scope(), outer)
        self.assertIsNone(current_scope())

    def test_static_no_request_and_feature_off_do_not_configure_artifacts(self):
        wrapped = private_catalog_models(model)
        with patch.dict(os.environ, {"BIOS_PRIVATE_READ_MODELS": "false"}), patch("app.services.derived_model_scope.configured_scope") as configure:
            wrapped(values=["source"])
            configure.assert_not_called()
        with patch.dict(os.environ, {"BIOS_PRIVATE_READ_MODELS": "true"}), patch("app.services.derived_model_scope.configured_scope") as configure:
            wrapped(values=["source"])
            configure.assert_not_called()

    def test_configuration_off_readonly_or_missing_secret_does_no_hash_work(self):
        values = dict(repo_root=BASE_DIR, data_dir=DATA_DIR, schemas_dir=SCHEMAS_DIR, inbox_dir=INBOX_DIR)
        for env in [{"BIOS_PRIVATE_READ_MODELS": "false"},
                    {"BIOS_PRIVATE_READ_MODELS": "true", "BIOS_MODE": "readonly"},
                    {"BIOS_PRIVATE_READ_MODELS": "true", "BIOS_SESSION_SECRET": ""}]:
            with patch.dict(os.environ, env), patch("app.services.derived_model_scope.code_version") as version:
                self.assertIsNone(configured_scope(**values))
                version.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "Configured artifact filesystem is POSIX-only")
    def test_configuration_separates_signing_purpose_and_refuses_public_roots(self):
        with tempfile.TemporaryDirectory(prefix="derived-model-config-") as folder:
            root = Path(folder)
            for name in ("app", "schemas", "data", "inbox", "artifacts"):
                (root / name).mkdir()
            settings = dict(repo_root=root, data_dir=root / "data", schemas_dir=root / "schemas", inbox_dir=root / "inbox")
            secret = "fixture-private-session-signing-material-32"
            env = {"BIOS_PRIVATE_READ_MODELS": "true", "BIOS_SESSION_SECRET": secret,
                   "BIOS_MODE": "authoring", "BIOS_PRIVATE_MODEL_ROOT": str(root / "artifacts")}
            with patch.dict(os.environ, env):
                scope = configured_scope(**settings)
                self.assertIsNotNone(scope)
                self.assertFalse(scope.writer)
                self.assertNotEqual(scope.store.signing_key, secret.encode())
                self.assertFalse((root / "artifacts" / "derived-read-models-v1").exists())
                self.assertEqual(configured_scope(**settings).store.signing_key, scope.store.signing_key)
                with patch.dict(os.environ, {"BIOS_PRIVATE_MODEL_ROOT": str(root / "data")}):
                    self.assertIsNone(configured_scope(**settings))
                with patch.dict(os.environ, {"BIOS_PRIVATE_READ_MODELS": "false"}):
                    self.assertIsNone(configured_scope(**settings))
                    self.assertTrue(configured_scope(**settings, preparation=True).writer)


if __name__ == "__main__":
    unittest.main()
