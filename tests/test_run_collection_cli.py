"""scripts/run_collection.py's CLI default resolution for --data-dir/
--inbox-dir.

Real bug found deploying the Continuous Intelligence Refresh scheduler: the
CLI's --data-dir/--inbox-dir defaulted to plain repo-relative paths
(app/repositories/paths.DEFAULT_DATA_DIR, ROOT / "inbox"), ignoring
BIOS_RUNTIME_DIR entirely -- unlike every other entry point in this project
(app/main.py's DATA_DIR/INBOX_DIR both go through app/runtime_config.py's
resolve_data_dir()/resolve_inbox_dir()). A scheduled run inside the
deployed container (BIOS_RUNTIME_DIR=/app/runtime, per the Dockerfile,
bind-mounted to the host's persistent demo-runtime/ directory) would have
silently written every discovery to a container-local, non-persisted path
the running app never reads from and that is lost on container restart --
"succeeding" every four hours while never actually feeding the app or
surviving a rebuild.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import run_collection


def test_data_and_inbox_dir_default_to_none_before_resolution() -> None:
    """The argparse default itself must not be a concrete repo-relative
    path -- that was the bug. main() resolves the real default afterward."""
    args = run_collection._parser().parse_args(["--all"])
    assert args.data_dir is None
    assert args.inbox_dir is None


def test_main_honors_runtime_dir_env_var_for_data_and_inbox(monkeypatch, tmp_path: Path, capsys) -> None:
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv("BIOS_DATA_DIR", raising=False)
    monkeypatch.delenv("BIOS_INBOX_DIR", raising=False)

    # No sources configured -- --all completes with zero sources/items,
    # no network calls, but still exercises get_repositories(args.data_dir)
    # and OperationalStateStore(args.inbox_dir / "operations").save_run(),
    # which is enough to prove where main() actually resolved to.
    exit_code = run_collection.main(["--all", "--json"])
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["sources_checked"] == 0

    run_files = list((runtime / "inbox" / "operations" / "runs").glob("*.json"))
    assert len(run_files) == 1, "run summary must be written under BIOS_RUNTIME_DIR, not a repo-relative default"


def test_explicit_flags_still_override_runtime_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(tmp_path / "runtime"))
    explicit_data = tmp_path / "explicit-data"
    explicit_inbox = tmp_path / "explicit-inbox"
    args = run_collection._parser().parse_args(
        ["--all", "--data-dir", str(explicit_data), "--inbox-dir", str(explicit_inbox)]
    )
    assert args.data_dir == explicit_data
    assert args.inbox_dir == explicit_inbox


def test_main_does_not_require_the_benchmark_file_when_extraction_is_disabled(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    """Real failure caught deploying to the VPS: main() unconditionally
    hashed benchmarks/atomic-ci-v1.json to build the extraction gate, even
    though resolve_extraction_gate() returns immediately when extraction
    is disabled without ever looking at that hash -- and the deployed
    container image never included benchmarks/ at all, since nothing had
    ever run this exact code path there before. The recurring scheduler
    always runs with extraction off (Continuous Intelligence Refresh's own
    resource-boundary rule), so this must never require that file."""
    monkeypatch.setattr(run_collection, "ROOT", tmp_path)
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(tmp_path / "runtime"))
    assert not (tmp_path / "benchmarks").exists()

    exit_code = run_collection.main(["--all", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["extraction_gate"]["enabled"] is False
