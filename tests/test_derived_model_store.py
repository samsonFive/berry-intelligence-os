"""Explicit writer/read-only miss, integrity, ownership and filesystem boundaries."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from io import BytesIO
import hashlib
import os
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

from app.services.derived_model_store import DerivedModelStore, ModelKey, MAX_PAYLOAD


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def key(value="source-a"):
    return ModelKey(digest("test-model"), digest(value), digest("code-v1"), "2026-11-03")


class IdentityTests(unittest.TestCase):
    def test_unsupported_platform_is_a_read_only_miss(self):
        store = DerivedModelStore(Path(tempfile.gettempdir()), digest("fixture"),
                                  b"private-fixture-signing-key-32bytes")
        with patch("app.services.derived_model_store.os.name", "unsupported"):
            self.assertIsNone(store.load(key()))
            self.assertFalse(store.write(key(), b"derived output"))

    def test_invalid_identity_and_day_are_rejected(self):
        for values in [dict(namespace="../source"), dict(input_digest="A" * 64),
                       dict(code_digest=""), dict(day="2026-2-3"),
                       dict(day="2026-02-30"), dict(day=None)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(key(), **values)

    def test_store_configuration_is_bounded_and_secret_is_not_in_repr(self):
        base = dict(inbox_dir=Path(tempfile.gettempdir()), context_digest=digest("fixture"),
                    signing_key=b"private-fixture-signing-key-32bytes")
        for values in [dict(max_bytes=0), dict(max_bytes=128_000_001),
                       dict(max_entries=33), dict(max_entries=True),
                       dict(signing_key=b"short"), dict(context_digest="../"),
                       dict(inbox_dir=Path("relative-inbox"))]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                DerivedModelStore(**{**base, **values})
        self.assertNotIn(base["signing_key"].decode(), repr(DerivedModelStore(**base)))


@unittest.skipUnless(os.name == "posix", "Descriptor-relative private store is POSIX-only; other platforms miss")
class PrivateStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="derived-model-store-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.store = DerivedModelStore(self.base, digest("runtime-a"), b"fixture-signing-key-never-production-123")
        self.folder = self.base / "derived-read-models-v1"

    def artifact(self, identity=None):
        return self.folder / self.store._name(self.store._header(identity or key()))

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.folder.iterdir() if p.is_file()}

    def test_miss_does_not_create_any_file_or_directory(self):
        self.assertIsNone(self.store.load(key()))
        self.assertEqual(list(self.base.iterdir()), [])

    def test_explicit_writer_authenticates_payload_and_read_is_unchanged(self):
        self.assertTrue(self.store.write(key(), b"literal derived output"))
        before = self.snapshot()
        self.assertEqual(self.store.load(key()), b"literal derived output")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.artifact().stat().st_mode & 0o777, 0o600)

    def test_every_current_input_code_day_namespace_and_context_is_bound(self):
        self.assertTrue(self.store.write(key(), b"earlier model"))
        before = self.snapshot()
        for changed in [replace(key(), input_digest=digest("edited human decision")),
                        replace(key(), code_digest=digest("code-v2")),
                        replace(key(), namespace=digest("different model")),
                        replace(key(), day="2026-11-04")]:
            self.assertIsNone(self.store.load(changed))
        self.assertIsNone(replace(self.store, context_digest=digest("runtime-b")).load(key()))
        self.assertIsNone(replace(self.store, signing_key=b"different-private-fixture-key-32bytes").load(key()))
        self.assertEqual(self.snapshot(), before)

    def test_tamper_truncation_extra_bytes_and_corrupt_header_are_read_only_misses(self):
        self.assertTrue(self.store.write(key(), b"source output"))
        original = self.artifact().read_bytes()
        for damaged in [original[:-1], original + b"extra", b"wrong" + original[5:],
                        original[:20] + bytes([original[20] ^ 1]) + original[21:]]:
            self.artifact().write_bytes(damaged)
            before = self.snapshot()
            self.assertIsNone(self.store.load(key()))
            self.assertEqual(self.snapshot(), before)

    def test_oversized_payload_is_not_written(self):
        self.assertFalse(self.store.write(key(), b"x" * (MAX_PAYLOAD + 1)))
        self.assertFalse(self.folder.exists())

    def test_artifact_cannot_be_moved_to_another_input_name(self):
        self.assertTrue(self.store.write(key(), b"original input model"))
        self.artifact().rename(self.artifact(key("different-input")))
        self.assertIsNone(self.store.load(key("different-input")))

    def test_unsafe_leaf_or_file_permissions_are_not_repaired(self):
        self.assertTrue(self.store.write(key(), b"original"))
        self.artifact().chmod(0o644)
        self.assertIsNone(self.store.load(key()))
        self.assertFalse(self.store.write(key(), b"replacement"))
        self.assertEqual(self.artifact().stat().st_mode & 0o777, 0o644)
        self.artifact().chmod(0o600)
        self.folder.chmod(0o755)
        self.assertIsNone(self.store.load(key()))
        self.assertFalse(self.store.write(key("new"), b"new"))
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o755)

    def test_leaf_and_ancestor_symlinks_never_redirect_operations(self):
        target = self.base / "outside"; target.mkdir()
        marker = target / "operator-record.json"; marker.write_bytes(b"preserve")
        self.folder.symlink_to(target, target_is_directory=True)
        self.assertIsNone(self.store.load(key()))
        self.assertFalse(self.store.write(key(), b"not allowed"))
        self.assertEqual([p.name for p in target.iterdir()], [marker.name])
        (self.base / "linked-parent").symlink_to(target, target_is_directory=True)
        (target / "inbox").mkdir()
        alternate = replace(self.store, inbox_dir=self.base / "linked-parent" / "inbox")
        self.assertFalse(alternate.write(key(), b"not allowed"))
        self.assertIsNone(alternate.load(key()))
        self.assertEqual(marker.read_bytes(), b"preserve")

    def test_reserved_destination_symlink_cannot_replace_outside_file(self):
        self.folder.mkdir(mode=0o700)
        target = self.base / "source.json"; target.write_bytes(b"operator source")
        self.artifact().symlink_to(target)
        self.assertFalse(self.store.write(key(), b"replacement"))
        self.assertTrue(self.artifact().is_symlink())
        self.assertEqual(target.read_bytes(), b"operator source")

    def test_fifo_is_a_bounded_read_only_miss(self):
        self.folder.mkdir(mode=0o700)
        os.mkfifo(self.artifact(), mode=0o600)
        self.assertIsNone(self.store.load(key()))
        self.assertFalse(self.store.write(key(), b"replacement"))

    def test_unknown_files_are_not_evicted_to_make_space(self):
        store = replace(self.store, max_entries=1)
        self.folder.mkdir(mode=0o700)
        unknown = self.folder / "operator-notes.json"; unknown.write_bytes(b"keep this")
        self.assertFalse(store.write(key(), b"new model"))
        self.assertEqual(unknown.read_bytes(), b"keep this")
        self.assertFalse(self.artifact().exists())

    def test_budget_expires_only_authenticated_old_artifacts(self):
        store = replace(self.store, max_entries=2)
        self.assertTrue(store.write(key("old"), b"old"))
        os.utime(self.artifact(key("old")), ns=(1, 1))
        self.assertTrue(store.write(key("current"), b"current"))
        self.assertTrue(store.write(key("newest"), b"newest"))
        self.assertIsNone(store.load(key("old")))
        self.assertEqual(store.load(key("current")), b"current")
        self.assertEqual(store.load(key("newest")), b"newest")

    def test_failed_atomic_replace_keeps_prior_result_and_removes_own_temp(self):
        self.assertTrue(self.store.write(key(), b"earlier"))
        before = self.snapshot()
        with patch("app.services.derived_model_store.os.replace", side_effect=OSError("fixture failure")):
            self.assertFalse(self.store.write(key(), b"later"))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.store.load(key()), b"earlier")

    def test_nonblocking_lock_does_not_change_existing_files(self):
        import fcntl
        self.assertTrue(self.store.write(key(), b"earlier"))
        before = self.snapshot()
        with (self.folder / ".writer.lock").open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertFalse(self.store.write(key("new"), b"later"))
        self.assertEqual(self.snapshot(), before)

    def test_concurrent_publication_never_returns_torn_or_unsigned_bytes(self):
        first = b"a" * 50_000; second = b"b" * 50_000
        self.assertTrue(self.store.write(key(), first))
        def publish(i):
            self.store.write(key(), first if i % 2 else second)
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(publish, i) for i in range(20)]
            values = [self.store.load(key()) for _ in range(50)]
            for future in futures:
                future.result()
        self.assertTrue(all(value in (first, second) for value in values))
        self.assertFalse(any(p.name.endswith(".tmp") for p in self.folder.iterdir()))

    def test_authenticated_bytes_still_require_class_denying_decoder(self):
        from app.services.presentation_memo import _BuiltinUnpickler
        payload = pickle.dumps(date(2026, 11, 3), protocol=5)
        self.assertTrue(self.store.write(key(), payload))
        authenticated = self.store.load(key())
        with self.assertRaises(pickle.UnpicklingError):
            _BuiltinUnpickler(BytesIO(authenticated)).load()


if __name__ == "__main__":
    unittest.main()
