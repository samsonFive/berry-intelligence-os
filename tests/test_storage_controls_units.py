"""Configuration boundaries of the actual host entrypoint, without host writes."""
import json
import os
from pathlib import Path

import pytest

from app.services.storage_monitor import DEFAULT_RELEASE_LOCKS, parse_config
from scripts import storage_monitor as command


ROOT = Path(__file__).resolve().parents[1]


def test_monitor_cli_cannot_replace_shared_release_locks(tmp_path, monkeypatch, capsys):
    # Core sampling accepts injected locks for isolated fixtures, while the real
    # operator entrypoint must always use the release owners' exact three locks.
    cfg = parse_config({"paths": [{"id": "fixture", "path": str(tmp_path)}],
                        "state_dir": str(tmp_path / "private"),
                        "status_file": str(tmp_path / "storage/status.json"),
                        "release_locks": [str(tmp_path / "unrelated.lock")]})
    monkeypatch.setattr(command, "load_config", lambda _path: cfg)
    monkeypatch.setattr(command, "run_monitor", lambda *_args, **_kwargs: pytest.fail("uncoordinated entrypoint"))
    assert command.main(["--config", str(tmp_path / "policy.json")]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "shared_release_lock_set_changed"
    assert not cfg.state_dir.exists() and not cfg.status_file.exists()


@pytest.mark.skipif(os.name != "posix", reason="Actual host policy uses POSIX absolute paths")
def test_committed_combined_policy_parses_with_shared_monitor_lock_contract():
    # Catches incompatible operator policy/schema changes before installation.
    value = json.loads((ROOT / "deploy/storage-controls/policy.example.json").read_text())
    cfg = parse_config(value)
    assert cfg.release_locks == tuple(Path(p) for p in DEFAULT_RELEASE_LOCKS)
    assert cfg.notification["kind"] == "none"
    assert cfg.reserve_free_bytes >= 8 * 1024**3


@pytest.mark.skipif(os.name != "posix", reason="Actual host policy uses POSIX absolute paths")
def test_standalone_policy_parses_without_enabling_external_delivery():
    value = json.loads((ROOT / "deploy/logging/storage-monitor-policy.example.json").read_text())
    cfg = parse_config(value)
    assert cfg.release_locks == tuple(Path(p) for p in DEFAULT_RELEASE_LOCKS)
    assert cfg.notification == {"kind": "none"}
