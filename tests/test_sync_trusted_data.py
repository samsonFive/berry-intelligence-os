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

from scripts.sync_trusted_data import sync_trusted_data

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
    second = sync_trusted_data(seed, runtime)

    assert first["files_added"] == ["entities/companies/company-a.json"]
    assert second["files_added"] == []


def test_pipeline_registry_is_authoritative_without_overwriting_trusted_records(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    runtime = tmp_path / "runtime"
    _write_json(seed / "configuration/collection_pipelines.json", {"schema_version": 2})
    _write_json(runtime / "configuration/collection_pipelines.json", {"schema_version": 1})
    _write_json(seed / "evidence/ev-1.json", {"id": "ev-1", "status": "seed"})
    _write_json(runtime / "evidence/ev-1.json", {"id": "ev-1", "status": "operator"})

    result = sync_trusted_data(seed, runtime)

    assert result["files_updated"] == ["configuration/collection_pipelines.json"]
    assert json.loads((runtime / "configuration/collection_pipelines.json").read_text())["schema_version"] == 2
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
        [sys.executable, "-m", "scripts.sync_trusted_data", "--seed", str(seed), "--runtime", str(runtime)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "ModuleNotFoundError" not in result.stderr
    assert (runtime / "entities" / "companies" / "company-a.json").is_file()
