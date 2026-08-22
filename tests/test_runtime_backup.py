from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import pytest

from app.services.runtime_backup import RuntimeBackupError, backup_health, create_backup, restore_backup, rotate_backups, verify_backup


def test_backup_restore_covers_mutable_state_excludes_secrets_and_preserves_mode(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    evidence = runtime / "inbox" / "evidence" / "draft.json"
    state = runtime / "inbox" / "operations" / "state.json"
    trusted = runtime / "data" / "evidence" / "trusted.json"
    trusted_with_secret_word = runtime / "data" / "evidence" / "ev-the-secret-of-berries-success.json"
    secret = runtime / "inbox" / ".env"
    token = runtime / "inbox" / "token.json"
    for path, payload in (
        (evidence, {"review_state": "in_review"}),
        (state, {"last_success": "now"}),
        (trusted, {"status": "published"}),
        (trusted_with_secret_word, {"status": "published", "title": "The Secret of Berries Success"}),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    secret.write_text("TOKEN=do-not-copy", encoding="utf-8")
    token.write_text('{"token": "do-not-copy"}', encoding="utf-8")
    state.chmod(0o640)
    archive = create_backup(runtime, tmp_path / "backups", now=datetime(2026, 8, 21, tzinfo=timezone.utc))
    manifest = verify_backup(archive)
    paths = {entry["path"] for entry in manifest["files"]}
    assert paths == {
        "data/evidence/ev-the-secret-of-berries-success.json",
        "data/evidence/trusted.json",
        "inbox/evidence/draft.json",
        "inbox/operations/state.json",
    }
    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert (restored / "inbox/evidence/draft.json").read_bytes() == evidence.read_bytes()
    assert (restored / "data/evidence/trusted.json").read_bytes() == trusted.read_bytes()
    assert (restored / "data/evidence/ev-the-secret-of-berries-success.json").read_bytes() == trusted_with_secret_word.read_bytes()
    assert not (restored / "inbox/.env").exists()
    assert not (restored / "inbox/token.json").exists()
    if os.name != "nt":
        assert (restored / "inbox/operations/state.json").stat().st_mode & 0o777 == 0o640


def test_restore_refuses_nonempty_target(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    (runtime / "inbox").mkdir(parents=True)
    archive = create_backup(runtime, tmp_path / "backups")
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("keep")
    with pytest.raises(RuntimeBackupError, match="not empty"):
        restore_backup(archive, target)


def test_rotation_keeps_bounded_verified_backups_outside_runtime(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    marker = runtime / "inbox" / "state.json"
    marker.parent.mkdir(parents=True)
    marker.write_text('{"state": "safe"}', encoding="utf-8")
    backups = tmp_path / "backups"
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for offset in range(3):
        rotate_backups(runtime, backups, keep=2, now=start + timedelta(days=offset))
    archives = sorted(backups.glob("berry-runtime-*.tar.gz"))
    assert len(archives) == 2
    assert all(verify_backup(path)["files"] for path in archives)
    health = backup_health(backups, now=start + timedelta(days=2, hours=1))
    assert health["state"] == "HEALTHY" and health["verified"] is True
    assert health["latest_sha256"]


def test_rotation_refuses_backup_inside_runtime(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    (runtime / "inbox").mkdir(parents=True)
    with pytest.raises(RuntimeBackupError, match="outside"):
        rotate_backups(runtime, runtime / "backups")
