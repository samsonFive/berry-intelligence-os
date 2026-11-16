from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tarfile
import hashlib
import io

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


def test_locked_backup_does_not_restore_the_backups_own_collection_lease(tmp_path: Path) -> None:
    from app.services.collection_runner import CollectionLockedError
    from app.services.pipeline_lock import pipeline_lock

    runtime = tmp_path / "runtime"
    inbox = runtime / "inbox"
    draft = inbox / "evidence" / "draft.json"
    draft.parent.mkdir(parents=True)
    draft.write_bytes(b'{"review_state":"pending"}\n')
    # A same-named history file is data, not the live runtime lease.
    history = inbox / "operations" / "runs" / "collection.lock"
    history.parent.mkdir(parents=True)
    history.write_bytes(b"historical run data\n")
    with pipeline_lock(inbox, "runtime-backup"):
        lease = inbox / "operations" / "collection.lock"
        lease_bytes = lease.read_bytes()
        archive = create_backup(runtime, tmp_path / "backups")
        assert lease.read_bytes() == lease_bytes
        with pytest.raises(CollectionLockedError):
            with pipeline_lock(inbox, "concurrent-writer"):
                pass
        manifest = verify_backup(archive)
        paths = {entry["path"] for entry in manifest["files"]}
        assert "inbox/operations/collection.lock" not in paths
        assert "inbox/operations/runs/collection.lock" in paths
    assert not lease.exists()
    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert (restored / "inbox/evidence/draft.json").read_bytes() == draft.read_bytes()
    assert (restored / "inbox/operations/runs/collection.lock").read_bytes() == history.read_bytes()
    with pipeline_lock(restored / "inbox", "after-recovery"):
        assert (restored / "inbox/operations/collection.lock").exists()


def legacy_locked_archive(tmp_path: Path, *, corrupt_lease: bool = False) -> Path:
    # Explicitly fictional format-v1 archive from the old locked-backup path.
    entries = {
        "inbox/operations/collection.lock": json.dumps({
            "run_id": "old-runtime-backup", "pid": 123,
            "started_at": datetime.now(timezone.utc).isoformat()}).encode(),
        "inbox/analyst_queue_state.json": b'{"saved_ids":["fictional-story"]}\n',
    }
    manifest = {"format_version": 1, "scope": ["data", "inbox"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files": [{"path": name, "size": len(body), "mode": 0o600,
                           "sha256": "0" * 64 if corrupt_lease and name.endswith("collection.lock")
                           else hashlib.sha256(body).hexdigest()}
                          for name, body in entries.items()]}
    archive = tmp_path / "legacy.tar.gz"
    with tarfile.open(archive, "x:gz") as tar:
        for name, body in {**entries, "MANIFEST.json": json.dumps(manifest).encode()}.items():
            member = tarfile.TarInfo(name)
            member.size = len(body)
            tar.addfile(member, io.BytesIO(body))
    return archive


def test_legacy_backup_lease_is_verified_but_not_recreated_in_empty_recovery(tmp_path: Path) -> None:
    from app.services.pipeline_lock import pipeline_lock

    archive = legacy_locked_archive(tmp_path)
    assert len(verify_backup(archive)["files"]) == 2
    target = tmp_path / "restored"
    result = restore_backup(archive, target)
    assert result["restore"] == {"verified_files": 1,
                                  "skipped_ephemeral_paths": ["inbox/operations/collection.lock"]}
    assert (target / "inbox/analyst_queue_state.json").read_bytes() == b'{"saved_ids":["fictional-story"]}\n'
    assert not (target / "inbox/operations/collection.lock").exists()
    with pipeline_lock(target / "inbox", "after-legacy-recovery"):
        assert (target / "inbox/operations/collection.lock").exists()


def test_legacy_lease_integrity_still_fails_before_any_restore_write(tmp_path: Path) -> None:
    archive = legacy_locked_archive(tmp_path, corrupt_lease=True)
    target = tmp_path / "restored"
    with pytest.raises(RuntimeBackupError, match="checksum mismatch"):
        restore_backup(archive, target)
    assert not target.exists()


def test_legacy_recovery_never_removes_an_existing_destination_lease(tmp_path: Path) -> None:
    from app.services.collection_runner import CollectionLockedError
    from app.services.pipeline_lock import pipeline_lock

    archive = legacy_locked_archive(tmp_path)
    target = tmp_path / "restored"
    with pipeline_lock(target / "inbox", "destination-owner"):
        lease = target / "inbox/operations/collection.lock"
        before = lease.read_bytes()
        # Explicit nonempty restore is an existing low-level option; neither
        # the archive lease nor this repair may overwrite the target owner.
        restore_backup(archive, target, require_empty=False)
        assert lease.read_bytes() == before
        with pytest.raises(CollectionLockedError):
            with pipeline_lock(target / "inbox", "concurrent-writer"):
                pass


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


@pytest.mark.parametrize("bounded_metadata", [False, True])
def test_verification_streams_body_checksums_and_returns_identical_manifest(tmp_path: Path, monkeypatch, bounded_metadata) -> None:
    runtime = tmp_path / "runtime"
    body = b"multi-chunk-body\n" * (140 * 1024)
    source = runtime / "data" / "large.db"
    source.parent.mkdir(parents=True)
    source.write_bytes(body)
    archive = create_backup(runtime, tmp_path / "backups")
    expected = verify_backup(archive)
    with tarfile.open(archive, "r:gz") as tar:
        manifest_size = tar.getmember("MANIFEST.json").size
    original_extract = tarfile.TarFile.extractfile
    reads = []

    class GuardedRead:
        def __init__(self, handle, name):
            self.handle, self.name = handle, name

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def read(self, size=-1):
            reads.append((self.name, size))
            if self.name != "MANIFEST.json":
                assert 0 < size <= 1024 * 1024, "body must not be read without a bounded chunk size"
            elif bounded_metadata:
                assert 0 < size <= manifest_size + 1, "manifest must use its configured read budget"
            return self.handle.read(size)

    def extract(tar, member):
        return GuardedRead(original_extract(tar, member), member.name)

    monkeypatch.setattr(tarfile.TarFile, "extractfile", extract)
    limits = {"maximum_manifest_bytes": manifest_size, "maximum_members": 2} if bounded_metadata else {}
    assert verify_backup(archive, **limits) == expected
    assert expected["files"][0]["sha256"] == hashlib.sha256(body).hexdigest()
    assert len([name for name, _ in reads if name == "data/large.db"]) >= 4


def test_manifest_budget_rejects_oversized_metadata_before_reading(tmp_path: Path, monkeypatch) -> None:
    archive = legacy_locked_archive(tmp_path)
    with tarfile.open(archive, "r:gz") as tar:
        manifest_size = tar.getmember("MANIFEST.json").size

    def unexpected_read(*args):
        pytest.fail("oversized manifest must be rejected before extraction")

    monkeypatch.setattr(tarfile.TarFile, "extractfile", unexpected_read)
    with pytest.raises(RuntimeBackupError, match="manifest exceeds maximum bytes"):
        verify_backup(archive, maximum_manifest_bytes=manifest_size - 1)


def test_member_budget_stops_iteration_without_full_inventory_or_body_reads(tmp_path: Path, monkeypatch) -> None:
    archive = legacy_locked_archive(tmp_path)

    def unexpected_inventory(*args):
        pytest.fail("bounded verification must not allocate tar.getmembers()")

    monkeypatch.setattr(tarfile.TarFile, "getmembers", unexpected_inventory)
    assert len(verify_backup(archive, maximum_members=3)["files"]) == 2

    def unexpected_extract(*args):
        pytest.fail("member limit must be checked before extraction")

    monkeypatch.setattr(tarfile.TarFile, "extractfile", unexpected_extract)
    with pytest.raises(RuntimeBackupError, match="maximum member count"):
        verify_backup(archive, maximum_members=2)


@pytest.mark.parametrize("name", ["maximum_manifest_bytes", "maximum_members"])
@pytest.mark.parametrize("invalid", [0, -1, True, 1.0])
def test_verification_rejects_invalid_optional_budgets(tmp_path: Path, name, invalid) -> None:
    archive = legacy_locked_archive(tmp_path)
    with pytest.raises(RuntimeBackupError, match="positive integer"):
        verify_backup(archive, **{name: invalid})
