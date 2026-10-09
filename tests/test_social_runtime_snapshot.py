import json
import sqlite3
import pytest
from app.services.social_intelligence.runtime_snapshot import export_snapshot, verify_snapshot
from app.services.social_intelligence.store import Store
from tests.test_social_intelligence import sample, ENTITIES


def test_snapshot_preserves_modes_removal_and_translation_tables_without_secrets(tmp_path):
    source = tmp_path / "source"
    store = Store(source)
    key = store.ingest([sample("live"), sample("fixture")], ENTITIES)[0]
    store.remove(key)
    (source / "keyz.txt").write_text("secret-never-export")
    destination = tmp_path / "snapshot"
    manifest = export_snapshot(source, destination)
    assert manifest["observations"] == 2
    assert not (destination / "inbox/keyz.txt").exists()
    assert verify_snapshot(destination)["collection_enabled"] is False
    restored = Store(destination / "inbox")
    assert {r["mode"] for r in restored.records()} == {"fixture"}
    with restored.connect() as db:
        assert db.execute("SELECT removed FROM observations WHERE id=?", (key,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM source_deletions").fetchone()[0] > 0
    with pytest.raises(ValueError): export_snapshot(source, destination)


def test_verification_detects_modified_database_and_rejects_source_destination(tmp_path):
    source = tmp_path / "source"
    Store(source)
    with pytest.raises(ValueError): export_snapshot(source, source / "snapshot")
    destination = tmp_path / "snapshot"
    export_snapshot(source, destination)
    with (destination / "inbox/social/observations.sqlite3").open("ab") as f: f.write(b"changed")
    with pytest.raises(ValueError): verify_snapshot(destination)
