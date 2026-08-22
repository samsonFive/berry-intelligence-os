from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

import pytest

from app.services.runtime_backup import RuntimeBackupError, create_backup, restore_backup, verify_backup


def test_backup_restore_covers_mutable_state_excludes_secrets_and_preserves_mode(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    evidence = runtime / "inbox" / "evidence" / "draft.json"
    state = runtime / "inbox" / "operations" / "state.json"
    trusted = runtime / "data" / "evidence" / "trusted.json"
    secret = runtime / "inbox" / ".env"
    for path, payload in ((evidence, {"review_state": "in_review"}), (state, {"last_success": "now"}), (trusted, {"status": "published"})):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    secret.write_text("TOKEN=do-not-copy", encoding="utf-8")
    state.chmod(0o640)
    archive = create_backup(runtime, tmp_path / "backups", now=datetime(2026, 8, 21, tzinfo=timezone.utc))
    manifest = verify_backup(archive)
    paths = {entry["path"] for entry in manifest["files"]}
    assert paths == {"data/evidence/trusted.json", "inbox/evidence/draft.json", "inbox/operations/state.json"}
    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert (restored / "inbox/evidence/draft.json").read_bytes() == evidence.read_bytes()
    assert (restored / "data/evidence/trusted.json").read_bytes() == trusted.read_bytes()
    assert not (restored / "inbox/.env").exists()
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
