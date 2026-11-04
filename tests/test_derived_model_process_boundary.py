"""The real offline command and a fresh private reader share only derived bytes."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]

# All inputs are the committed public seed. No live account, provider key or
# operator inbox is copied into these children. Freeze only the generated
# candidate clock so complete results from distinct processes can be compared.
CHILD = r'''
import hashlib,json,os,sys
from datetime import date,datetime,timezone
from scripts.prepare_private_read_models import main as prepare,offline_preparation
with offline_preparation():
    from app.services.variety_universe import registry_import
    class MaterializationClock(datetime):
        @classmethod
        def now(cls,tz=None):
            value=datetime(2026,11,3,12,0,0,tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    registry_import.datetime=MaterializationClock
    if sys.argv[1]=='prepare':
        raise SystemExit(prepare(['--prepare']))
    from app import main
    from app.services import derived_model_scope
    from app.services.identity_read_model import identity_read_model_scope
    from app.services.request_corpus import RequestCorpus,bind_request_corpus,reset_request_corpus
    scopes=[]
    original=derived_model_scope.configured_scope
    def observe(**kwargs):
        scope=original(**kwargs)
        scopes.append(scope)
        return scope
    derived_model_scope.configured_scope=observe
    token=bind_request_corpus(RequestCorpus(main.DATA_DIR,main.SCHEMAS_DIR,main.INBOX_DIR))
    try:
        with identity_read_model_scope():
            value=main.variety_candidate_universe()
    finally:
        reset_request_corpus(token)
    def typed(value):
        if value is None or type(value) in {str,bool,int,float}:
            return [type(value).__name__,value]
        if isinstance(value,(date,datetime)):
            return [type(value).__name__,value.isoformat()]
        if type(value) is dict:
            return ['dict',[[typed(k),typed(v)] for k,v in value.items()]]
        if type(value) in {list,tuple}:
            return [type(value).__name__,[typed(v) for v in value]]
        if type(value) in {set,frozenset}:
            return [type(value).__name__,sorted([typed(v) for v in value],key=repr)]
        raise TypeError(type(value))
    digest=hashlib.sha256(json.dumps(typed(value),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    print(json.dumps({'complete_typed_sha256':digest,'counts':[s.counts for s in scopes if s is not None],
        'catalog_rows':len(value[0]),'visible_candidates':len(value[1])}))
'''


def inventory(folder):
    return {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in folder.rglob("*") if path.is_file()}


@contextmanager
def public_seed_runtime():
    with tempfile.TemporaryDirectory(prefix="private-model-process-") as name:
        root = Path(name)
        inbox, artifacts = root / "inbox", root / "artifacts"
        inbox.mkdir(mode=0o700)
        artifacts.mkdir(mode=0o700)
        env = {key: value for key, value in os.environ.items()
               if not key.endswith(("_API_KEY", "_API_TOKEN"))}
        env.update(BIOS_DATA_DIR=str(ROOT / "data"), BIOS_INBOX_DIR=str(inbox),
            BIOS_PRIVATE_MODEL_ROOT=str(artifacts), BIOS_MODE="authoring",
            BIOS_REMOTE_INTERACTIVE="false", BIOS_BASIC_AUTH="",
            BIOS_SESSION_SECRET="public-fixture-only-not-a-production-secret-32",
            PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        yield env, inbox, artifacts


def child(mode, env, *, enabled):
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", CHILD, mode],
        cwd=ROOT, env={**env, "BIOS_PRIVATE_READ_MODELS": "true" if enabled else "false"},
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    if result.returncode:
        raise AssertionError("Offline model subprocess failed: " + result.stderr[-2400:])
    return json.loads(result.stdout.splitlines()[-1])


@unittest.skipUnless(os.name == "posix", "The private filesystem integration is POSIX-only")
class PrivateModelProcessBoundaryTests(unittest.TestCase):
    def test_actual_command_then_fresh_reader_preserve_complete_public_universe(self):
        source_before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in (ROOT / "data", ROOT / "schemas") for path in folder.rglob("*.json")}
        with public_seed_runtime() as (env, inbox, artifacts):
            baseline = child("read", env, enabled=False)
            self.assertEqual(baseline["counts"], [])
            self.assertEqual(inventory(artifacts), {})
            prepared = child("prepare", env, enabled=False)
            self.assertTrue(prepared["prepared"])
            self.assertEqual(prepared["counts"]["writes"], 2)
            self.assertEqual(prepared["provider_requests"], 0)
            self.assertFalse(prepared["source_or_review_writes"])
            written = inventory(artifacts)
            self.assertEqual(sum(name.endswith(".snapshot") for name in written), 2)
            reader = child("read", env, enabled=True)
            self.assertEqual(reader["complete_typed_sha256"], baseline["complete_typed_sha256"])
            self.assertEqual(reader["catalog_rows"], baseline["catalog_rows"])
            self.assertEqual(reader["visible_candidates"], baseline["visible_candidates"])
            self.assertEqual(len(reader["counts"]), 1)
            counts = reader["counts"][0]
            self.assertEqual(counts["artifact_hits"], 2)
            self.assertEqual(counts["memory_hits"], 0)
            self.assertEqual(counts["calculations"], 0)
            self.assertEqual(counts["writes"], 0)
            self.assertEqual(inventory(artifacts), written)
            self.assertEqual(inventory(inbox), {})
        self.assertEqual({str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in (ROOT / "data", ROOT / "schemas") for path in folder.rglob("*.json")}, source_before)


if __name__ == "__main__":
    unittest.main()
