from __future__ import annotations

from pathlib import Path

from app.runtime_config import resolve_data_dir, resolve_inbox_dir


def test_default_paths_are_repo_data_and_inbox() -> None:
    root = Path("/tmp/berry-repo")
    assert resolve_data_dir(root) == root / "data"
    assert resolve_inbox_dir(root) == root / "inbox"


def test_runtime_dir_override(monkeypatch, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv("BIOS_DATA_DIR", raising=False)
    monkeypatch.delenv("BIOS_INBOX_DIR", raising=False)
    assert resolve_data_dir() == (runtime / "data").resolve()
    assert resolve_inbox_dir() == (runtime / "inbox").resolve()


def test_explicit_data_and_inbox_override_runtime_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("BIOS_DATA_DIR", str(tmp_path / "custom-data"))
    monkeypatch.setenv("BIOS_INBOX_DIR", str(tmp_path / "custom-inbox"))
    assert resolve_data_dir() == (tmp_path / "custom-data").resolve()
    assert resolve_inbox_dir() == (tmp_path / "custom-inbox").resolve()
