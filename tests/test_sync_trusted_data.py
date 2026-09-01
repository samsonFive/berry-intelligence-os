"""scripts/sync_trusted_data.py -- additive-only, file-level sync of the
whole deployed-runtime data/ tree.

Real gap this exists to fix: sync_source_config.py (scripts/sync_source_config.py)
only ever resynced data/configuration/sources.json. Comparing canonical data/
to a real VPS runtime's demo-runtime/data/ found the runtime missing exactly
the two entity records added in canonical's most recent commit
(company-sanlucar.json, company-ushbc.json) -- the same seed-runs-once
staleness bug, just for the rest of data/ too, and it directly blocked
testing company coverage for those two entities. These tests prove the
sync is additive-only at the file level: a file already present at the
runtime path (an operator's own live-published record) is never touched,
and configuration/sources.json keeps using the existing entry-level merge
rather than being overwritten wholesale.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.runtime_backup import create_backup
from scripts.sync_trusted_data import (
    MANIFEST_FILENAME,
    TRANSACTION_FILENAME,
    apply_safe_canonical_updates,
    plan_trusted_data_sync,
    startup_sync_trusted_data,
    sync_trusted_data,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_copies_a_new_file_missing_from_the_runtime(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "entities" / "companies" / "company-a.json", {"id": "company-a"})

    result = sync_trusted_data(seed, runtime)

    assert result["files_added"] == ["entities/companies/company-a.json"]
    copied = json.loads((runtime / "entities" / "companies" / "company-a.json").read_text(encoding="utf-8"))
    assert copied == {"id": "company-a"}


def test_never_overwrites_a_file_already_present_at_runtime(tmp_path: Path) -> None:
    """An operator's own live-published record at this path must survive
    every future deploy, even if the seed bundle's copy of that same
    relative path differs (e.g. a since-superseded canonical draft)."""
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "evidence" / "ev-1.json", {"id": "ev-1", "status": "seed-version"})
    _write_json(runtime / "evidence" / "ev-1.json", {"id": "ev-1", "status": "operator-published"})

    result = sync_trusted_data(seed, runtime)

    assert result["files_added"] == []
    saved = json.loads((runtime / "evidence" / "ev-1.json").read_text(encoding="utf-8"))
    assert saved == {"id": "ev-1", "status": "operator-published"}


def test_sources_json_uses_entry_level_merge_not_whole_file_copy(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "configuration" / "sources.json", [{"id": "source-a"}, {"id": "source-b"}])
    _write_json(runtime / "configuration" / "sources.json", [{"id": "source-a", "label": "operator-edited"}])

    result = sync_trusted_data(seed, runtime)

    assert result["sources"]["added"] == ["source-b"]
    assert "configuration/sources.json" not in result["files_added"]
    saved = {s["id"]: s for s in json.loads((runtime / "configuration" / "sources.json").read_text(encoding="utf-8"))}
    assert saved["source-a"] == {"id": "source-a", "label": "operator-edited"}
    assert "source-b" in saved


def test_missing_seed_dir_is_a_safe_no_op(tmp_path: Path) -> None:
    seed = tmp_path / "does-not-exist"
    runtime = tmp_path / "runtime"
    _write_json(runtime / "evidence" / "ev-1.json", {"id": "ev-1"})

    result = sync_trusted_data(seed, runtime)

    assert result == {"skipped_missing_seed": True, "sources": None, "files_added": [], "files_updated": []}
    assert json.loads((runtime / "evidence" / "ev-1.json").read_text(encoding="utf-8")) == {"id": "ev-1"}


def test_running_twice_is_idempotent(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "entities" / "companies" / "company-a.json", {"id": "company-a"})

    first = sync_trusted_data(seed, runtime)
    manifest_after_first = (runtime / MANIFEST_FILENAME).read_bytes()
    second = sync_trusted_data(seed, runtime)

    assert first["files_added"] == ["entities/companies/company-a.json"]
    assert second["files_added"] == []
    assert second["baseline_initialized"] == []
    assert (runtime / MANIFEST_FILENAME).read_bytes() == manifest_after_first


def test_scheduler_configuration_is_authoritative_without_overwriting_trusted_records(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "configuration/collection_pipelines.json", {"schema_version": 2})
    _write_json(runtime / "configuration/collection_pipelines.json", {"schema_version": 1})
    _write_json(seed / "configuration/source_collection_cadence.json", {"schema_version": 2})
    _write_json(runtime / "configuration/source_collection_cadence.json", {"schema_version": 1})
    _write_json(seed / "configuration/source_universe.json", {"schema_version": 2, "entries": []})
    _write_json(runtime / "configuration/source_universe.json", {"schema_version": 1, "entries": []})
    _write_json(seed / "evidence/ev-1.json", {"id": "ev-1", "status": "seed"})
    _write_json(runtime / "evidence/ev-1.json", {"id": "ev-1", "status": "operator"})

    result = sync_trusted_data(seed, runtime)

    assert result["files_updated"] == [
        "configuration/collection_pipelines.json",
        "configuration/source_collection_cadence.json",
        "configuration/source_universe.json",
    ]
    assert json.loads((runtime / "configuration/collection_pipelines.json").read_text())["schema_version"] == 2
    assert json.loads((runtime / "configuration/source_collection_cadence.json").read_text())["schema_version"] == 2
    assert json.loads((runtime / "configuration/source_universe.json").read_text())["schema_version"] == 2
    assert json.loads((runtime / "evidence/ev-1.json").read_text())["status"] == "operator"


def test_a_freshly_synced_runtime_gains_the_real_missing_entities(tmp_path: Path) -> None:
    """Prove against the *real* canonical data/ tree that a runtime with
    an empty data/ directory ends up with every trusted record after one
    sync -- this is the actual regression test for the deployment bug."""
    seed = REPO_ROOT / "data"
    assert seed.is_dir(), "canonical data/ must exist for this test to be meaningful"

    runtime = tmp_path / "runtime-data"
    runtime.mkdir()

    result = sync_trusted_data(seed, runtime)

    assert (runtime / "entities" / "companies" / "company-sanlucar.json").is_file()
    assert (runtime / "entities" / "companies" / "company-ushbc.json").is_file()
    assert "entities/companies/company-sanlucar.json" in result["files_added"]
    assert "entities/companies/company-ushbc.json" in result["files_added"]
    assert result["sources"]["added"], "sources.json should also populate from an empty runtime"


def test_cli_invocation_via_module_flag_does_not_raise_module_not_found(tmp_path: Path) -> None:
    """Real deploy bug: docker-entrypoint.sh originally ran this as a bare
    file path (`python3 /app/scripts/sync_trusted_data.py`), which fails
    with ModuleNotFoundError on `from scripts.sync_source_config import
    ...` because that invocation style puts the script's own directory
    (not the repo root) on sys.path[0] -- `scripts` never resolves as a
    package. The entrypoint's `|| echo warning ...` fallback swallowed the
    crash silently, so the sync ran as a total no-op on every deploy and
    the real VPS runtime stayed missing company-sanlucar/company-ushbc
    even after this fix merged. This test runs the exact `-m` invocation
    docker-entrypoint.sh now uses (`python -m scripts.sync_trusted_data`
    from the repo root) so any regression back to file-path invocation
    fails pytest instead of only failing silently in production."""
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    (seed / "entities" / "companies").mkdir(parents=True)
    (seed / "entities" / "companies" / "company-a.json").write_text('{"id": "company-a"}', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.sync_trusted_data",
            "--seed",
            str(seed),
            "--runtime",
            str(runtime),
            "--startup-sync",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "ModuleNotFoundError" not in result.stderr
    assert (runtime / "entities" / "companies" / "company-a.json").is_file()


def test_dry_run_classifies_new_records_without_writing(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "facts/fact-new.json", {"id": "fact-new"})

    plan = plan_trusted_data_sync(seed, runtime, canonical_sha="abc123")

    assert plan["counts"]["NEW"] == 1
    assert plan["records"][0]["state"] == "NEW"
    assert not runtime.exists()


def test_semantic_json_hash_ignores_key_order_whitespace_and_line_endings(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    canonical = seed / "evidence/ev-1.json"
    deployed = runtime / "evidence/ev-1.json"
    canonical.parent.mkdir(parents=True)
    deployed.parent.mkdir(parents=True)
    canonical.write_bytes(b'{\n  "id": "ev-1",\n  "score": 1\n}\n')
    deployed.write_bytes(b'{\r\n  "score": 1,\r\n  "id": "ev-1"\r\n}\r\n')

    plan = plan_trusted_data_sync(seed, runtime)

    assert plan["records"][0]["state"] == "UNCHANGED"
    assert plan["records"][0]["canonical_raw_sha256"] != plan["records"][0]["runtime_raw_sha256"]
    assert plan["records"][0]["canonical_semantic_sha256"] == plan["records"][0]["runtime_semantic_sha256"]


def test_safe_canonical_update_requires_baseline_and_verified_matching_backup(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime_root = tmp_path / "runtime-root"
    runtime = runtime_root / "data"
    path = Path("evidence/ev-1.json")
    _write_json(seed / path, {"id": "ev-1", "value": "v1"})
    startup_sync_trusted_data(seed, runtime, canonical_sha="oldsha")
    _write_json(seed / path, {"id": "ev-1", "value": "v2"})

    plan = plan_trusted_data_sync(seed, runtime, canonical_sha="newsha")
    assert plan["records"][0]["state"] == "SAFE_CANONICAL_UPDATE"
    archive = create_backup(runtime_root, tmp_path / "backups")

    result = apply_safe_canonical_updates(
        seed,
        runtime,
        verified_backup=archive,
        canonical_sha="newsha",
    )

    assert result["files_updated"] == [path.as_posix()]
    assert json.loads((runtime / path).read_text(encoding="utf-8"))["value"] == "v2"
    assert Path(result["report_path"]).is_file()
    assert not (runtime / TRANSACTION_FILENAME).exists()
    assert plan_trusted_data_sync(seed, runtime)["records"][0]["state"] == "UNCHANGED"


def test_runtime_divergence_and_two_sided_conflict_are_never_applied(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime_root = tmp_path / "runtime-root"
    runtime = runtime_root / "data"
    diverged = Path("evidence/runtime-edit.json")
    conflict = Path("evidence/both-edit.json")
    for path in (diverged, conflict):
        _write_json(seed / path, {"id": path.stem, "value": "base"})
    startup_sync_trusted_data(seed, runtime, canonical_sha="base")
    _write_json(runtime / diverged, {"id": diverged.stem, "value": "operator"})
    _write_json(runtime / conflict, {"id": conflict.stem, "value": "operator"})
    _write_json(seed / conflict, {"id": conflict.stem, "value": "canonical"})

    plan = plan_trusted_data_sync(seed, runtime, canonical_sha="next")
    states = {row["path"]: row["state"] for row in plan["records"]}
    assert states[diverged.as_posix()] == "RUNTIME_DIVERGED"
    assert states[conflict.as_posix()] == "CONFLICT"
    archive = create_backup(runtime_root, tmp_path / "backups")
    result = apply_safe_canonical_updates(
        seed, runtime, verified_backup=archive, canonical_sha="next"
    )

    assert result["updated_count"] == 0
    assert json.loads((runtime / diverged).read_text())["value"] == "operator"
    assert json.loads((runtime / conflict).read_text())["value"] == "operator"


def test_existing_difference_without_baseline_is_a_conflict(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "facts/fact-1.json", {"id": "fact-1", "value": "canonical"})
    _write_json(runtime / "facts/fact-1.json", {"id": "fact-1", "value": "runtime"})

    row = plan_trusted_data_sync(seed, runtime)["records"][0]

    assert row["state"] == "CONFLICT"
    assert row["last_promoted_semantic_sha256"] is None


def test_stale_backup_fails_closed_before_mutation(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime_root = tmp_path / "runtime-root"
    runtime = runtime_root / "data"
    path = Path("evidence/ev-1.json")
    _write_json(seed / path, {"id": "ev-1", "value": "v1"})
    startup_sync_trusted_data(seed, runtime, canonical_sha="old")
    archive = create_backup(runtime_root, tmp_path / "backups")
    # Semantically equal, but raw bytes no longer match the verified backup.
    (runtime / path).write_bytes(b'{"value":"v1","id":"ev-1"}\r\n')
    _write_json(seed / path, {"id": "ev-1", "value": "v2"})

    with pytest.raises(ValueError, match="does not match current runtime bytes"):
        apply_safe_canonical_updates(
            seed, runtime, verified_backup=archive, canonical_sha="new"
        )

    assert json.loads((runtime / path).read_text())["value"] == "v1"
    assert not (runtime / TRANSACTION_FILENAME).exists()


def test_incomplete_transaction_fails_closed(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime-root/data"
    _write_json(seed / "evidence/ev-1.json", {"id": "ev-1"})
    startup_sync_trusted_data(seed, runtime, canonical_sha="old")
    _write_json(runtime / TRANSACTION_FILENAME, {"state": "applying"})

    with pytest.raises(RuntimeError, match="incomplete prior promotion"):
        apply_safe_canonical_updates(
            seed,
            runtime,
            verified_backup=tmp_path / "unused.tar.gz",
            canonical_sha="new",
        )
