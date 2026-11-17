"""Physical cutover, crash resume and rollback without source or decision loss."""
from copy import deepcopy
import json
from datetime import UTC, date, datetime
from pathlib import Path
import subprocess
import sys

import pytest

from app.services import information_migration as migration, information_storage as store


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=3, ensure_ascii=False) + "\n", encoding="utf-8")


def record(key, **changes):
    return {"id": key, "record_type": "evidence", "status": "draft", "title": "Blueberry source " + key,
            "summary": "Source statement", "source_url": "https://example.com/" + key,
            "source_type": "trade_press", "published_date": "2026-11-12", "captured_date": "2026-11-13",
            **changes}


@pytest.fixture
def runtime(tmp_path):
    data, inbox, backups = tmp_path / "data", tmp_path / "separate-private-runtime" / "inbox", tmp_path / "backups"
    inbox.mkdir(parents=True)
    reviewed = record("ev-reviewed", status="published", reviewed_by="Analyst", information_confidence="high")
    write(data / "evidence/ev-reviewed.json", reviewed)
    write(data / "evidence/ev-internal.json", record("ev-internal", status="in_review"))
    write(inbox / "evidence/ev-reviewed.json", record("ev-reviewed", summary="Original unedited draft"))
    write(inbox / "evidence/ev-draft.json", record("ev-draft", article={"paragraphs": [{"text": "PRIVATE FULL SOURCE BODY"}]}))
    write(inbox / "evidence/ev-rejected.json", record("ev-rejected", status="rejected", rejection_reason="Wrong event"))
    write(inbox / "feed_first_live/2026-11-13.json", {"today": "2026-11-13", "telemetry": {"provider": "fixture"},
        "records": [record("ev-reviewed", status="published"), record("live-web", status="published", human_reviewed=True,
            information={"review_status": "reviewed"}), record("ev-rejected", status="published")],
        "rotating_records": [record("live-rotating")]})
    write(inbox / "news_packets/captures/packet-fixture.json", {"captured_at": "2026-11-13", "records": [record("live-packet"), record("ev-draft")]})
    write(inbox / "analyst_queue_state.json", {"reading": {"ev-draft": {"state": "read", "reviewer": "Analyst"}}})
    write(inbox / "review_events/review-one.json", {"object_id": "ev-reviewed", "actor": "Analyst", "action": "publish"})
    for path in (data / "attachments/ev-reviewed/proof.txt", inbox / "attachments/ev-reviewed/proof.txt"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"same attachment bytes")
    (inbox / "attachments/ev-draft").mkdir(parents=True)
    (inbox / "attachments/ev-draft/private.bin").write_bytes(b"private\0attachment")
    return data, inbox, backups


def snapshots(data, inbox):
    return {str(path): path.read_bytes() for root in (data, inbox) for path in root.rglob("*") if path.is_file()}


def test_plan_is_read_only_and_has_complete_variant_and_privacy_coverage(runtime):
    data, inbox, _ = runtime
    before = snapshots(data, inbox)
    plan = migration.plan_migration(data, inbox)
    report = migration.dry_run(data, inbox)
    assert snapshots(data, inbox) == before
    assert report["migration_id"] == plan["migration_id"]
    assert report["counts"]["records"] == 7
    assert report["counts"]["variants"] == 11
    assert report["counts"]["public"] == 1
    assert report["counts"]["private"] == 6
    assert "PRIVATE FULL SOURCE BODY" not in json.dumps(report)
    assert not plan["conflicts"]


def test_cutover_one_store_retires_payloads_keeps_assets_decisions_and_cache_refs(runtime):
    data, inbox, backups = runtime
    originals = snapshots(data, inbox)
    plan = migration.plan_migration(data, inbox)
    result = migration.apply_migration(data, inbox, backups, quiesced=True)
    assert result["state"] == "complete"
    assert store.enabled(data_dir=data) and store.enabled(inbox_dir=inbox)
    assert store.information_directory(data_dir=data) == store.information_directory(inbox_dir=inbox)
    assert not list((data / "evidence").glob("*.json"))
    assert not list((inbox / "evidence").glob("*.json"))
    rows = {row["id"]: row for row in store.list_records(inbox_dir=inbox)}
    assert set(rows) == set(plan["records"])
    assert rows["ev-reviewed"]["reviewed_by"] == "Analyst"
    assert rows["ev-reviewed"]["publication_scope"] == "public"
    assert rows["ev-internal"]["publication_scope"] == "private"
    assert rows["ev-draft"]["article"]["paragraphs"][0]["text"] == "PRIVATE FULL SOURCE BODY"
    assert rows["live-web"]["status"] == "unreviewed"
    assert rows["live-web"]["information"]["review_status"] == "unreviewed"
    assert rows["live-web"]["publication_scope"] == "private"
    assert rows["ev-rejected"]["status"] == "rejected"
    envelope = store.read_json(inbox / "feed_first_live/2026-11-13.json")
    assert "records" not in envelope and "rotating_records" not in envelope
    assert envelope["records_ids"] == ["ev-reviewed", "live-web", "ev-rejected"]
    assert envelope["telemetry"] == {"provider": "fixture"}
    from app.services.feed_first_live import load_cached_bundle
    from app.services.personal_digest import retained_news
    loaded = load_cached_bundle(inbox, today=date(2026, 11, 13))
    assert [row["id"] for row in loaded["records"]] == envelope["records_ids"]
    assert [row["id"] for row in loaded["rotating_records"]] == ["live-rotating"]
    assert loaded["records"][0]["reviewed_by"] == "Analyst"
    assert loaded["records"][0]["publication_scope"] == "public"
    retained = {row["id"]: row for row in retained_news(inbox)}
    assert {"ev-draft", "live-packet"} <= set(retained)
    assert retained["ev-draft"]["publication_scope"] == "private"
    assert retained["ev-rejected"]["status"] == "rejected"
    assert "article" not in retained["ev-draft"]
    assert "PRIVATE FULL SOURCE BODY" not in json.dumps(retained)
    assert (store.assets_dir(inbox_dir=inbox) / "ev-draft/private.bin").read_bytes() == b"private\0attachment"
    assert (inbox / "analyst_queue_state.json").read_bytes() == originals[str(inbox / "analyst_queue_state.json")]
    for spec in plan["sources"]:
        backup = backups / plan["migration_id"] / "sources" / spec["root"] / spec["relative"]
        assert migration.file_hash(backup) == spec["sha256"]
    again = migration.apply_migration(data, inbox, backups, quiesced=True)
    assert again["migration_id"] == result["migration_id"]
    assert {row["id"]: row for row in store.list_records(data_dir=data)} == rows


@pytest.mark.parametrize("phase", ["backed_up", "staged", "activated"])
def test_crash_resume_is_hash_verified_and_idempotent(runtime, phase):
    data, inbox, backups = runtime
    plan = migration.plan_migration(data, inbox)
    def crash(current):
        if current == phase:
            raise RuntimeError("simulated process interruption")
    with pytest.raises(RuntimeError, match="interruption"):
        migration.apply_migration(data, inbox, backups, quiesced=True, _fault=crash)
    for roots in ({"data_dir": data}, {"inbox_dir": inbox}):
        with pytest.raises(store.InformationStorageError, match="incomplete|in progress"):
            store.enabled(**roots)
    result = migration.apply_migration(data, inbox, backups, quiesced=True, resume_id=plan["migration_id"])
    assert result["state"] == "complete"
    assert len(store.list_records(data_dir=data)) == 7


@pytest.mark.parametrize("phase", ["backed_up", "staged"])
def test_preactivation_rollback_clears_partial_bindings_without_losing_records(runtime, phase):
    data, inbox, backups = runtime
    before = snapshots(data, inbox)
    plan = migration.plan_migration(data, inbox)
    def crash(current):
        if current == phase:
            raise RuntimeError("stop before activation")
    with pytest.raises(RuntimeError):
        migration.apply_migration(data, inbox, backups, quiesced=True, _fault=crash)
    migration.rollback_migration(data, inbox, backups / plan["migration_id"], quiesced=True)
    assert not store.enabled(data_dir=data) and not store.enabled(inbox_dir=inbox)
    for path, value in before.items():
        assert Path(path).read_bytes() == value


def test_rollback_restores_exact_source_bytes_and_preserves_later_reading_decisions(runtime):
    data, inbox, backups = runtime
    before = snapshots(data, inbox)
    result = migration.apply_migration(data, inbox, backups, quiesced=True)
    state = inbox / "analyst_queue_state.json"
    write(state, {"reading": {"ev-draft": {"state": "in_progress", "position": 234}}})
    later = state.read_bytes()
    rolled = migration.rollback_migration(data, inbox, backups / result["migration_id"], quiesced=True)
    assert rolled["state"] == "rolled_back"
    assert not store.enabled(data_dir=data) and not store.enabled(inbox_dir=inbox)
    for path, value in before.items():
        assert Path(path).read_bytes() == (later if path == str(state) else value)
    assert migration.rollback_migration(data, inbox, backups / result["migration_id"], quiesced=True)["state"] == "rolled_back"


def test_rollback_refuses_post_cutover_record_work(runtime):
    data, inbox, backups = runtime
    result = migration.apply_migration(data, inbox, backups, quiesced=True)
    store.upsert_record(record("ev-new-work"), inbox_dir=inbox)
    with pytest.raises(migration.InformationMigrationError, match="coverage differs"):
        migration.rollback_migration(data, inbox, backups / result["migration_id"], quiesced=True)
    assert store.enabled(inbox_dir=inbox)
    assert store.get_record("ev-new-work", inbox_dir=inbox) is not None
    assert not (data / "evidence/ev-reviewed.json").exists()


def test_identity_and_asset_conflicts_stop_before_any_mutation(runtime):
    data, inbox, backups = runtime
    write(inbox / "evidence/ev-reviewed.json", record("ev-reviewed", source_url="https://different.example/other-event"))
    (inbox / "attachments/ev-reviewed/proof.txt").write_bytes(b"different attachment")
    before = snapshots(data, inbox)
    report = migration.dry_run(data, inbox)
    assert {row["kind"] for row in report["conflicts"]} == {"record_identity", "asset_identity"}
    with pytest.raises(migration.InformationMigrationError, match="incompatible"):
        migration.apply_migration(data, inbox, backups, quiesced=True)
    assert snapshots(data, inbox) == before and not backups.exists()


def test_source_and_atomic_statement_cannot_share_one_identity(runtime):
    data, inbox, _ = runtime
    canonical = store.read_json(data / "evidence/ev-reviewed.json")
    write(data / "evidence/ev-reviewed.json", {**canonical, "evidence_role": "publication_artifact"})
    write(inbox / "evidence/ev-reviewed.json", record("ev-reviewed", evidence_role="atomic_evidence"))
    assert {row["kind"] for row in migration.dry_run(data, inbox)["conflicts"]} == {"record_identity"}


def test_inbox_only_attachment_cannot_become_public_under_same_id_canonical_source(runtime):
    data, inbox, backups = runtime
    private_asset = inbox / "attachments/ev-reviewed/private-only.txt"
    private_asset.write_bytes(b"PRIVATE ATTACHMENT CONTENT")
    before = snapshots(data, inbox)
    report = migration.dry_run(data, inbox)
    assert report["conflicts"] == [{
        "kind": "asset_publication_scope", "id": "ev-reviewed", "path": "ev-reviewed/private-only.txt",
        "sources": ["inbox/attachments/ev-reviewed/private-only.txt"],
    }]
    assert "PRIVATE ATTACHMENT CONTENT" not in json.dumps(report)
    with pytest.raises(migration.InformationMigrationError, match="incompatible"):
        migration.apply_migration(data, inbox, backups, quiesced=True)
    assert snapshots(data, inbox) == before
    assert not backups.exists() and not (data / "information").exists()


def test_identical_public_attachment_in_both_origins_keeps_existing_authorization(runtime):
    data, inbox, backups = runtime
    report = migration.dry_run(data, inbox)
    assert not report["conflicts"]
    assert report["counts"]["assets"] == 2
    migration.apply_migration(data, inbox, backups, quiesced=True)
    assert store.get_record("ev-reviewed", inbox_dir=inbox)["publication_scope"] == "public"
    assert (store.assets_dir(inbox_dir=inbox) / "ev-reviewed/proof.txt").read_bytes() == b"same attachment bytes"


def test_retained_flags_keep_confidence_verification_and_caveats_without_granting_review(runtime):
    data, inbox, backups = runtime
    flags = {"review_status": "reviewed", "confidence": {"level": "medium"},
             "verification_status": "source_check_pending", "caveats": ["Thin retained excerpt."]}
    cache_path = inbox / "feed_first_live/2026-11-13.json"
    cache = store.read_json(cache_path)
    cache["records"].append(record("flagged-migration", status="published", information=flags))
    write(cache_path, cache)
    migration.apply_migration(data, inbox, backups, quiesced=True)
    from app.services.feed_first_live import load_cached_bundle, save_bundle
    migrated = next(row for row in load_cached_bundle(inbox, today=date(2026, 11, 13))["records"]
                    if row["id"] == "flagged-migration")
    save_bundle(inbox, {"today": "2026-11-14", "records": [record("flagged-retention", status="published", information=flags)]})
    retained = load_cached_bundle(inbox, today=date(2026, 11, 14))["records"][0]
    for row in (migrated, retained):
        assert row["status"] == "unreviewed" and row["publication_scope"] == "private"
        assert row["information"]["review_status"] == "unreviewed"
        assert row["information"]["confidence"] == flags["confidence"]
        assert row["information"]["verification_status"] == flags["verification_status"]
        assert row["information"]["caveats"] == flags["caveats"]


def test_retained_only_terminal_decisions_survive_migration_and_new_cache_retention(runtime):
    data, inbox, backups = runtime
    from app.services.information_catalog import INACTIVE_STATES, load_information
    terminal_rows = [record(f"terminal-{field}-{state}", **{field: state})
                     for field in ("status", "review_state") for state in sorted(INACTIVE_STATES)]
    write(inbox / "news_packets/captures/packet-terminals.json", {"records": terminal_rows})
    migration.apply_migration(data, inbox, backups, quiesced=True)
    new_rows = [{**row, "id": "new-" + row["id"], "source_url": row["source_url"] + "-new"} for row in terminal_rows]
    store.retain_records(inbox, new_rows)
    rows = store.list_records(inbox_dir=inbox)
    visible = {row["id"] for row in load_information(rows, inbox)}
    for original in terminal_rows + new_rows:
        current = store.get_record(original["id"], inbox_dir=inbox)
        assert current["id"] not in visible
        assert current["information"]["review_status"] == "rejected"
        for field in ("status", "review_state"):
            if original.get(field) in INACTIVE_STATES:
                assert current[field] == original[field]


def test_resume_refuses_changed_source_and_corrupted_backup(runtime):
    data, inbox, backups = runtime
    plan = migration.plan_migration(data, inbox)
    def crash(phase):
        if phase == "backed_up":
            raise RuntimeError("stop")
    with pytest.raises(RuntimeError):
        migration.apply_migration(data, inbox, backups, quiesced=True, _fault=crash)
    write(inbox / "evidence/ev-draft.json", record("ev-draft", summary="New work after interrupted plan"))
    with pytest.raises(migration.InformationMigrationError, match="Source changed"):
        migration.apply_migration(data, inbox, backups, quiesced=True, resume_id=plan["migration_id"])
    assert not (data / "information/store.json").exists()
    backup = backups / plan["migration_id"] / "sources/data/evidence/ev-reviewed.json"
    backup.write_text("corrupted", encoding="utf-8")
    with pytest.raises(migration.InformationMigrationError, match="differs|verification"):
        migration.apply_migration(data, inbox, backups, quiesced=True, resume_id=plan["migration_id"])


def test_active_retention_never_overwrites_review_or_richer_source_and_replacement_is_exact(runtime):
    data, inbox, backups = runtime
    migration.apply_migration(data, inbox, backups, quiesced=True)
    original = store.get_record("ev-reviewed", inbox_dir=inbox)
    store.retain_records(inbox, [record("ev-reviewed", title="Cached different headline", confidence="low", live=True,
                                       article={"full_text": "Unreviewed cached body must not enter a public record"})])
    assert store.get_record("ev-reviewed", inbox_dir=inbox) == original
    store.upsert_record({"id": "ev-draft", "summary": "Edited summary"}, inbox_dir=inbox)
    assert store.get_record("ev-draft", inbox_dir=inbox)["article"]["paragraphs"]
    saved = deepcopy(store.get_record("ev-draft", inbox_dir=inbox))
    store.write_record({**saved, "temporary_field": "added"}, inbox_dir=inbox)
    store.write_record(saved, inbox_dir=inbox)
    assert store.get_record("ev-draft", inbox_dir=inbox) == saved
    assert "temporary_field" not in store.get_record("ev-draft", inbox_dir=inbox)
    assert saved["publication_scope"] == "private"
    store.upsert_record(record("ev-acquired", publication_scope="public"), inbox_dir=inbox)
    assert store.get_record("ev-acquired", inbox_dir=inbox)["publication_scope"] == "private"


def test_inactive_helpers_preserve_legacy_format_and_cli_plan_is_read_only(runtime):
    data, inbox, _ = runtime
    raw = record("ev-new-legacy")
    store.upsert_record(raw, inbox_dir=inbox)
    assert store.get_record(raw["id"], inbox_dir=inbox) == raw
    assert "publication_scope" not in store.read_json(inbox / "evidence/ev-new-legacy.json")
    before = snapshots(data, inbox)
    script = Path(__file__).resolve().parents[1] / "scripts/migrate_information_storage.py"
    result = subprocess.run([sys.executable, str(script), "plan", "--data-dir", str(data), "--inbox-dir", str(inbox)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0 and json.loads(result.stdout)["state"] == "dry_run"
    assert "PRIVATE FULL SOURCE BODY" not in result.stdout
    assert snapshots(data, inbox) == before
    with pytest.raises(migration.InformationMigrationError, match="Stop the web service"):
        migration.apply_migration(data, inbox, data.parent / "backups")


def test_writer_and_existing_collector_locks_prevent_cutover(runtime):
    from app.services.collection_runner import CollectionLockedError
    data, inbox, backups = runtime
    with store.storage_lock(data_dir=data):
        with pytest.raises(store.InformationStorageError, match="locked"):
            with store.storage_lock(data_dir=data, timeout=0.05):
                raise AssertionError("The second writer must not acquire this lease")
    write(inbox / "operations/collection.lock", {"run_id": "busy-collector", "started_at": datetime.now(UTC).isoformat(), "pid": 123})
    with pytest.raises(CollectionLockedError):
        migration.apply_migration(data, inbox, backups, quiesced=True)
    assert not backups.exists() and not (data / "information/store.json").exists()


def test_cache_metadata_reads_never_hydrate_private_body(runtime):
    data, inbox, backups = runtime
    migration.apply_migration(data, inbox, backups, quiesced=True)
    rows = store.load_records_by_id(inbox, ["ev-draft"], metadata_only=True)
    assert rows[0]["id"] == "ev-draft" and rows[0]["publication_scope"] == "private"
    assert "article" not in rows[0] and "PRIVATE FULL SOURCE BODY" not in json.dumps(rows)


def test_same_migration_collector_lease_can_resume_but_markerless_store_cannot_fallback(runtime):
    data, inbox, backups = runtime
    plan = migration.plan_migration(data, inbox)
    def crash(phase):
        if phase == "backed_up":
            raise RuntimeError("stop")
    with pytest.raises(RuntimeError):
        migration.apply_migration(data, inbox, backups, quiesced=True, _fault=crash)
    write(inbox / "operations/collection.lock", {"run_id": f"information-migration-{plan['migration_id']}-interrupted", "started_at": datetime.now(UTC).isoformat(), "pid": 123})
    assert migration.apply_migration(data, inbox, backups, quiesced=True)["state"] == "complete"
    marker = data / "information/store.json"
    marker.unlink()
    with pytest.raises(store.InformationStorageError, match="incomplete"):
        store.information_directory(data_dir=data)


def test_stale_acquisition_cannot_downgrade_review_or_resurrect_rejected_source(runtime):
    data, inbox, backups = runtime
    migration.apply_migration(data, inbox, backups, quiesced=True)
    reviewed = store.get_record("ev-reviewed", inbox_dir=inbox)
    stale = record("ev-reviewed", title="Outdated unreviewed title", information_confidence="low",
                   information={"review_status": "unreviewed", "confidence": "low"},
                   article={"full_text": "Captured source body"})
    store.upsert_record(stale, inbox_dir=inbox)
    current = store.get_record("ev-reviewed", inbox_dir=inbox)
    assert current["status"] == "published" and current["title"] == reviewed["title"]
    assert current["information"] == reviewed["information"]
    assert current["reviewed_by"] == "Analyst" and current["publication_scope"] == "public"
    assert current["article"]["full_text"] == "Captured source body"
    store.upsert_record({**stale, "article": {"full_text": "A later stale body must not replace this"}}, inbox_dir=inbox)
    assert store.get_record("ev-reviewed", inbox_dir=inbox)["article"] == current["article"]
    rejected = store.get_record("ev-rejected", inbox_dir=inbox)
    store.upsert_record(record("ev-rejected", summary="Old provider result"), inbox_dir=inbox)
    assert store.get_record("ev-rejected", inbox_dir=inbox) == rejected


def test_intake_publication_spoof_cannot_become_reviewed_without_real_review_event(runtime):
    from app.services.review_events import append_review_event
    data, inbox, backups = runtime
    write(inbox / "evidence/ev-spoof.json", record("ev-spoof", status="published", review_state="published",
          human_reviewed=True, information={"review_status": "reviewed"}, reviewed_by="Claimed reviewer"))
    append_review_event(inbox, workflow="publication_review", object_id="ev-draft", object_type="publication_draft",
                        action="publish", prior_state="draft", new_state="published", actor="Recorded reviewer")
    migration.apply_migration(data, inbox, backups, quiesced=True)
    spoof = store.get_record("ev-spoof", inbox_dir=inbox)
    assert spoof["status"] == "unreviewed" and spoof["information"]["review_status"] == "unreviewed"
    assert spoof["publication_scope"] == "private"
    actual = store.get_record("ev-draft", inbox_dir=inbox)
    assert actual["information"]["review_status"] == "reviewed" and actual["reviewed_by"] == "Recorded reviewer"
    assert actual["publication_scope"] == "private"
