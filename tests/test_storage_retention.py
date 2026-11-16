from __future__ import annotations

from dataclasses import replace
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import gzip
import io
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile

import pytest

from app.services.runtime_backup import create_backup, verify_backup
from app.services.storage_retention import (
    RetentionHold, RetentionPolicy, apply_plan, create_plan, encoded, fingerprint, sha, archive_open_file,
)
from storage_recovery_fixtures import fixture_filesystem, producer_evidence, reseal_wrapper
from storage_logging_fixtures import configuration_only_environment

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
CURRENT = "sha256:" + "a" * 64
PREVIOUS = "sha256:" + "b" * 64
OLDER = "sha256:" + "0" * 64


def archive(runtime: Path, folder: Path, when: datetime) -> Path:
    path = create_backup(runtime, folder, now=when)
    os.utime(path, (when.timestamp(), when.timestamp()))
    return path


@pytest.fixture
def environment(tmp_path, monkeypatch):
    import app.services.storage_recovery as recovery
    read_file, stat_file = fixture_filesystem(monkeypatch)
    runtime = tmp_path / "runtime"
    (runtime / "data").mkdir(parents=True)
    (runtime / "data" / "example.json").write_text('{"fixture": "trusted example"}')
    (runtime / "inbox").mkdir()
    (runtime / "inbox" / "decision.json").write_text('{"fixture": "review decision"}')
    backups, releases = tmp_path / "backups", tmp_path / "releases"
    backups.mkdir(); releases.mkdir()
    current_stage, previous_stage = releases / "current", releases / "previous"
    current_stage.mkdir(); previous_stage.mkdir()
    current = archive(runtime, backups / "current-recovery", NOW - timedelta(hours=1))
    previous = archive(runtime, backups / "previous-recovery", NOW - timedelta(days=1, hours=1))
    ledger = releases / "current.json"
    ledger.write_text(json.dumps({"image": CURRENT, "source_sha": "a" * 40, "previous_image": PREVIOUS,
                                  "stage": str(current_stage), "backup": str(current),
                                  "compose_override": str(current_stage / "operator-private" / "candidate-override.json"),
                                  "rollback_override": str(current_stage / "operator-private" / "rollback-override.json"),
                                  "receipt": str(current_stage / "promotion.json")}))
    previous_ledger = releases / "previous-ledger.bytes"
    previous_ledger.write_text(json.dumps({"image": PREVIOUS, "source_sha": "b" * 40,
                                           "stage": str(previous_stage), "backup": str(previous),
                                           "compose_override": str(previous_stage / "legacy-candidate.json"),
                                           "rollback_override": str(previous_stage / "legacy-rollback.json"),
                                           "previous_image": OLDER, "receipt": str(previous_stage / "promotion.json")}))
    older_ledger = releases / "older-ledger.bytes"
    older_ledger.write_text(json.dumps({"image": OLDER, "source_sha": "0" * 40,
                                       "stage": str(releases / "historical-stage"),
                                       "backup": str(backups / "historical-stage" / "historical-backup.tar.gz")}))
    for path in [ledger, previous_ledger, older_ledger]:
        path.chmod(0o600)
    evidence = producer_evidence(root=tmp_path, runtime=runtime, backups=backups, current=current,
        previous=previous, ledger=ledger, previous_ledger=previous_ledger, older_ledger=older_ledger)
    promotion_proofs = []
    for role, stage, image, raw, before, backup in [
            ("current", current_stage, CURRENT, ledger, previous_ledger, current),
            ("previous", previous_stage, PREVIOUS, previous_ledger, older_ledger, previous)]:
        receipt = {"status": "PASS", "image": image, "old_ledger_sha256": sha(before.read_bytes()),
                   "new_ledger_sha256": sha(raw.read_bytes()), "backup_sha256": sha(backup.read_bytes())}
        receipt_path = stage / "promotion.json"
        receipt_path.write_bytes(encoded(receipt))
        receipt_path.chmod(0o600)
        promotion_proofs.append({"role": role, "path": str(receipt_path), "sha256": sha(receipt_path.read_bytes()),
                                 **{key: receipt[key] for key in ["status", "image", "old_ledger_sha256", "new_ledger_sha256"]}})
    protection = tmp_path / "protection.json"
    value = {"version": 1, "generated_at": NOW.isoformat(), "backup_root": str(backups),
             "operation_kind": "unified-migration", "accepted_caddy_id": None,
             "ledger_path": str(ledger), "ledger_sha256": sha(ledger.read_bytes()),
             "previous_ledger_path": str(previous_ledger), "previous_ledger_sha256": sha(previous_ledger.read_bytes()),
             "previous_before_ledger_path": str(older_ledger), "previous_before_ledger_sha256": sha(older_ledger.read_bytes()),
             "recovery_sets": [
                 {"role": role, "source_sha": char * 40, "image": image, "stage": str(stage),
                  "backup": {"path": str(path), "size": path.stat().st_size,
                             "sha256": sha(path.read_bytes()), "verified": True}}
                 for role, char, image, stage, path in [
                     ("current", "a", CURRENT, current_stage, current),
                     ("previous", "b", PREVIOUS, previous_stage, previous)]],
             "protected_paths": [{"path": str(runtime), "kind": "directory"},
                                 {"path": str(ledger), "kind": "file"}],
             "protected_images": [CURRENT, PREVIOUS, OLDER, "sha256:" + "f" * 64],
             "protected_image_provenance": [{"image": image, "source_sha": char * 40, "exists": True, "provenance_verified": True}
                                            for image, char in [(CURRENT, "a"), (PREVIOUS, "b"), (OLDER, "0"), ("sha256:" + "f" * 64, "f")]],
             "accepted_promotion_receipts": promotion_proofs}
    closure = recovery._load_accepted_closure(ledger, backups, older_path=older_ledger,
        read_file=read_file, stat_file=stat_file)
    accepted_binding = recovery.recovery_live_binding(closure["post_app"])
    monkeypatch.setattr(sys.modules[__name__], "binding", lambda: copy.deepcopy(accepted_binding))
    value["live_binding"] = binding()
    for row in value["recovery_sets"]:
        row["backup"].update(evidence["wrapper"]["archives"][row["role"]])
    value["accepted_recovery_proofs"] = closure["accepted_recovery_proofs"]
    value["accepted_content_pins"] = sorted(closure["files"].pins.values(), key=lambda row: row["path"])
    value["protected_paths"].extend({"path": row["path"], "kind": "file"} for row in value["accepted_content_pins"])
    value["protected_paths"].extend({"path": path, "kind": "directory"} for path in evidence["wrapper"]["protected_dirs"])
    protection.write_bytes(encoded(value))
    return {"runtime": runtime, "backups": backups, "releases": releases,
            "current": current, "previous": previous, "ledger": ledger,
            "protection": protection, "value": value,
            "accepted_read_file": read_file, "accepted_stat_file": stat_file,
            **evidence,
            "roots": [backups, releases], "tmp": tmp_path}


def binding():
    return {"app_id": "c" * 64, "image": CURRENT, "source_sha": "a" * 40,
            "mount_fingerprint": "d" * 64, "compose_fingerprint": "e" * 64,
            "config_fingerprint": "1" * 64, "healthy": True,
            "copilot": {"container_id": "f" * 64, "image": "sha256:" + "f" * 64,
                        "healthy": True, "network_mode": "container:" + "c" * 64,
                        "config_fingerprint": "2" * 64}}


def add_old(env, count=6):
    return [archive(env["runtime"], env["backups"] / ("old-" + str(index)),
                    NOW - timedelta(days=40 + index)) for index in range(count)]


def plan(env, **kwargs):
    return create_plan(env["roots"], env["protection"], now=NOW, binding_provider=binding,
                       policy=kwargs.pop("policy", RetentionPolicy(daily=2, weekly=0, monthly=0)), **kwargs)


def apply(env, value, **kwargs):
    body = encoded(value)
    return apply_plan(body, sha(body), now=NOW, binding_provider=kwargs.pop("binding_provider", binding), **kwargs)


def test_exact_global_nested_retirement_preserves_recovery_sets_and_live_state(environment):
    env = environment
    old = add_old(env, 5)
    live_before = {str(p): p.read_bytes() for p in env["runtime"].rglob("*") if p.is_file()}
    protected_before = {p: p.read_bytes() for p in [env["current"], env["previous"], env["ledger"]]}
    value = plan(env)
    assert len(value["candidates"]) == 5
    assert all(p.exists() for p in old)  # Planning is read-only.
    result = apply(env, value)
    assert result["state"] == "complete" and result["retired_count"] == 5
    assert all(not p.exists() and p.parent.is_dir() for p in old)
    assert {p: p.read_bytes() for p in protected_before} == protected_before
    assert {str(p): p.read_bytes() for p in env["runtime"].rglob("*") if p.is_file()} == live_before


def test_configuration_only_acceptance_preserves_caddy_store_and_both_recovery_roles(environment):
    env = configuration_only_environment(environment, now=NOW)
    old = add_old(env, 4)
    before = {str(path): path.read_bytes() for path in env["runtime"].rglob("*") if path.is_file()}
    value = create_plan(env["roots"], env["protection"], now=NOW,
        policy=RetentionPolicy(daily=2, weekly=0, monthly=0), binding_provider=env["binding_provider"])
    assert len(value["candidates"]) == 4
    body = encoded(value)
    result = apply_plan(body, sha(body), now=NOW, binding_provider=env["binding_provider"])
    assert result["state"] == "complete" and result["retired_count"] == 4
    assert env["current"].exists() and env["previous"].exists() and all(not path.exists() for path in old)
    assert {str(path): path.read_bytes() for path in env["runtime"].rglob("*") if path.is_file()} == before


def test_direct_root_daily_archive_never_pruned_or_used_as_global_tier(environment):
    env = environment
    root_archive = archive(env["runtime"], env["backups"], NOW - timedelta(days=100))
    add_old(env, 4)
    value = plan(env)
    assert str(root_archive) not in {row["path"] for row in value["candidates"] + value["retained"]}
    assert {"path": str(root_archive), "reason": "root_daily_rotation_preserved"} in value["held"]
    apply(env, value)
    assert root_archive.exists()


def test_global_tiers_span_attempt_directories_and_keep_valid_calendar_buckets(environment):
    env = environment
    for days in range(2, 100):
        archive(env["runtime"], env["backups"] / f"attempt-{days}", NOW - timedelta(days=days))
    value = plan(env, policy=RetentionPolicy())
    for reason, count in [("daily", 7), ("weekly", 4), ("monthly", 3)]:
        assert sum(reason in row["reasons"] for row in value["retained"]) == count
    assert len(value["candidates"]) == 10
    assert value["deferred"]
    selected = {row["path"] for row in value["retained"]}
    apply(env, value)
    assert all(Path(path).exists() for path in selected)


def test_minimum_age_keeps_all_recent_duplicates_not_only_tier_winner(environment):
    env = environment
    recent = [archive(env["runtime"], env["backups"] / f"recent-{hours}", NOW - timedelta(hours=hours))
              for hours in [4, 8, 30, 50, 71]]
    add_old(env)
    value = plan(env)
    assert all(str(path) in {row["path"] for row in value["retained"]} for path in recent)
    apply(env, value)
    assert all(path.exists() for path in recent)


def test_unknown_corrupt_and_future_archives_are_retained(environment):
    env = environment
    add_old(env, 3)
    folder = env["backups"] / "unknown"
    folder.mkdir()
    unknown = folder / "manual-recovery.tar.gz"
    shutil.copyfile(env["current"], unknown)
    corrupt = folder / "berry-runtime-20260101T000000Z.tar.gz"
    corrupt.write_bytes(b"not a runtime backup")
    when = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(corrupt, (when, when))
    future = archive(env["runtime"], folder, NOW + timedelta(days=2))
    value = plan(env)
    assert {str(unknown), str(corrupt), str(future)}.issubset({row["path"] for row in value["held"]})
    apply(env, value)
    assert all(path.exists() for path in [unknown, corrupt, future])


def test_invalid_newest_archive_does_not_displace_a_valid_daily_representative(environment):
    env = environment
    older = archive(env["runtime"], env["backups"] / "same-day-valid", NOW - timedelta(days=1, hours=2))
    newer_folder = env["backups"] / "same-day-invalid"
    newer_folder.mkdir()
    newer = newer_folder / "berry-runtime-20261115T115900Z.tar.gz"
    newer.write_bytes(b"corrupt")
    value = plan(env)
    # The previous recovery archive is newer than older and remains the daily winner.
    previous_row = next(row for row in value["retained"] if row["path"] == str(env["previous"]))
    assert "daily" in previous_row["reasons"]
    assert any(row["path"] == str(newer) for row in value["held"])
    assert older.exists()


def test_current_and_previous_stage_subtrees_are_never_walked_for_retirement(environment):
    env = environment
    preserved = archive(env["runtime"], env["releases"] / "previous" / "backup", NOW - timedelta(days=180))
    add_old(env)
    value = plan(env)
    assert str(preserved) not in {row["path"] for row in value["candidates"]}
    apply(env, value)
    assert preserved.exists()


@pytest.mark.parametrize("mutation", ["missing_previous", "bad_backup_hash", "root_backup", "same_backup"])
def test_incomplete_or_invalid_recovery_protection_holds_before_retirement(environment, mutation):
    env = environment
    old = add_old(env)
    value = env["value"]
    if mutation == "missing_previous":
        value["recovery_sets"] = value["recovery_sets"][:1]
    elif mutation == "bad_backup_hash":
        value["recovery_sets"][1]["backup"]["sha256"] = "0" * 64
    elif mutation == "same_backup":
        value["recovery_sets"][1]["backup"] = value["recovery_sets"][0]["backup"]
    else:
        root = archive(env["runtime"], env["backups"], NOW - timedelta(days=1))
        value["recovery_sets"][1]["backup"] = {"path": str(root), "size": root.stat().st_size,
                                                     "sha256": sha(root.read_bytes()), "verified": True}
    env["protection"].write_bytes(encoded(value))
    with pytest.raises(RetentionHold):
        plan(env)
    assert all(path.exists() for path in old)


def test_changed_archive_after_plan_is_held_with_no_unlink(environment):
    env = environment
    add_old(env)
    value = plan(env)
    first = Path(value["candidates"][0]["path"])
    first.write_bytes(b"changed after reviewed plan")
    result = apply(env, value)
    assert result["state"] == "held" and result["retired_count"] == 0
    assert first.exists()


@pytest.mark.parametrize("change", ["manifest", "ledger", "app", "app_id", "mount", "compose", "config", "plan_sha"])
def test_stale_manifest_ledger_app_and_plan_digest_refuse_all_mutations(environment, change):
    env = environment
    old = add_old(env)
    value = plan(env)
    if change == "manifest":
        env["protection"].write_bytes(env["protection"].read_bytes() + b" ")
    elif change == "ledger":
        env["ledger"].write_bytes(env["ledger"].read_bytes() + b" ")
    with pytest.raises(RetentionHold):
        if change in {"app", "app_id", "mount", "compose", "config"}:
            changed = binding()
            changed[{"app": "image", "app_id": "app_id", "mount": "mount_fingerprint", "compose": "compose_fingerprint", "config": "config_fingerprint"}[change]] = PREVIOUS if change == "app" else "f" * 64
            apply(env, value, binding_provider=lambda: changed)
        elif change == "plan_sha":
            apply_plan(encoded(value), "0" * 64, now=NOW, binding_provider=binding)
        else:
            apply(env, value)
    assert all(path.exists() for path in old)


def test_recovery_backup_changed_after_plan_is_preserved_and_holds(environment):
    env = environment
    old = add_old(env)
    value = plan(env)
    env["previous"].write_bytes(b"unexpected recovery mutation")
    with pytest.raises(RetentionHold):
        apply(env, value)
    assert all(path.exists() for path in old)


@pytest.mark.parametrize("candidate", ["protected", "outside"])
def test_even_explicitly_rehashed_plan_cannot_target_protected_or_external_file(environment, candidate):
    env = environment
    add_old(env)
    value = plan(env)
    path = env["current"] if candidate == "protected" else archive(env["runtime"], env["tmp"] / "outside", NOW - timedelta(days=200))
    row = {"path": str(path), "created_at": (NOW - timedelta(hours=1) if candidate == "protected" else NOW - timedelta(days=200)).isoformat(),
           "fingerprint": fingerprint(path), "checksum_sidecar": None}
    value["candidates"] = [row]
    with pytest.raises(RetentionHold, match="protected_or_outside"):
        apply(env, value)
    assert path.exists()


def test_count_and_byte_caps_defer_eligible_archives(environment):
    env = environment
    old = add_old(env, 8)
    value = plan(env, policy=RetentionPolicy(daily=2, weekly=0, monthly=0, maximum_archives_per_run=2))
    assert len(value["candidates"]) == 2 and len(value["deferred"]) == 6
    budget = max(path.stat().st_size for path in old) + 1
    value = plan(env, policy=RetentionPolicy(daily=2, weekly=0, monthly=0, maximum_bytes_per_run=budget))
    assert len(value["candidates"]) == 1
    assert value["candidate_bytes"] <= budget
    with pytest.raises(RetentionHold):
        RetentionPolicy(maximum_archives_per_run=11)
    with pytest.raises(RetentionHold):
        RetentionPolicy(maximum_bytes_per_run=5 * 1024**3 + 1)


def test_matching_sidecar_is_removed_but_invalid_sidecar_preserves_its_archive(environment):
    env = environment
    old = add_old(env, 2)
    valid = old[0].with_suffix(old[0].suffix + ".sha256")
    valid.write_text(sha(old[0].read_bytes()) + "  " + old[0].name + "\n")
    invalid = old[1].with_suffix(old[1].suffix + ".sha256")
    invalid.write_text("wrong digest")
    value = plan(env)
    assert {row["path"] for row in value["candidates"]} == {str(old[0])}
    apply(env, value)
    assert not old[0].exists() and not valid.exists()
    assert old[1].exists() and invalid.exists()


def test_midrun_ledger_change_stops_after_recorded_first_retirement(environment):
    env = environment
    add_old(env, 4)
    value = plan(env)
    events = []

    def record(event):
        events.append(event)
        if event["event"] == "archive_retired":
            env["ledger"].write_bytes(env["ledger"].read_bytes() + b" ")

    result = apply(env, value, event_callback=record)
    assert result["state"] == "partial" and result["retired_count"] == 1
    assert [event["event"] for event in events] == ["retirement_intent", "archive_retired"]
    assert sum(Path(row["path"]).exists() for row in value["candidates"]) == 3


def test_expired_plan_and_invalid_short_age_policy_refused(environment):
    env = environment
    add_old(env)
    value = plan(env)
    value["created_at"] = (NOW - timedelta(hours=3)).isoformat()
    with pytest.raises(RetentionHold, match="expired"):
        apply(env, value)
    with pytest.raises(RetentionHold, match="minimum_age"):
        RetentionPolicy(minimum_age_seconds=0)


def test_rehashed_plan_still_cannot_delete_existing_daily_root_archive(environment):
    env = environment
    add_old(env)
    value = plan(env)
    root = archive(env["runtime"], env["backups"], NOW - timedelta(days=100))
    value["candidates"] = [{"path": str(root), "created_at": (NOW - timedelta(days=100)).isoformat(),
                            "fingerprint": fingerprint(root), "checksum_sidecar": None}]
    with pytest.raises(RetentionHold, match="root_daily_archive"):
        apply(env, value)
    assert root.exists()


def test_gzip_footer_corruption_after_tar_end_is_preserved(environment):
    env = environment
    target = add_old(env, 1)[0]
    plain = gzip.decompress(target.read_bytes())
    raw = bytearray(gzip.compress(plain + b"\0" * (1024 * 1024)))
    raw[-8] ^= 1
    target.write_bytes(raw)
    when = (NOW - timedelta(days=40)).timestamp()
    os.utime(target, (when, when))
    # This is why checking only tar members is insufficient: its logical end
    # precedes the corrupted gzip footer and the added padding.
    assert verify_backup(target)["files"]
    value = plan(env)
    assert not value["candidates"]
    assert any(row["path"] == str(target) for row in value["held"])
    apply(env, value)
    assert target.exists()


def test_duplicate_tar_members_are_preserved_even_when_manifest_hashes_match(environment):
    env = environment
    target = add_old(env, 1)[0]
    with tarfile.open(target, "r:gz") as source:
        entries = [(member, source.extractfile(member).read()) for member in source.getmembers()]
    with tarfile.open(target, "w:gz") as output:
        for member, body in entries + entries[:1]:
            output.addfile(member, io.BytesIO(body))
    when = (NOW - timedelta(days=40)).timestamp()
    os.utime(target, (when, when))
    assert verify_backup(target)["files"]
    value = plan(env)
    assert not value["candidates"]
    assert any(row.get("reason") == "duplicate_tar_members_preserved" for row in value["held"])
    assert target.exists()


def test_open_archive_guard_holds_the_archive_without_unlink(environment):
    env = environment
    target = add_old(env, 1)[0]
    value = plan(env)
    result = apply(env, value, open_file_guard=lambda _: True)
    assert result["state"] == "held" and result["retired_count"] == 0
    assert result["held"][0]["reason"] == "archive_in_use_preserved"
    assert target.exists()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux /proc descriptor guard")
def test_proc_guard_observes_a_real_open_archive(environment):
    target = add_old(environment, 1)[0]
    with target.open("rb"):
        assert archive_open_file(target, strict=False)


def test_same_stat_but_changed_content_still_fails_the_pinned_hash(environment):
    env = environment
    target = add_old(env, 1)[0]
    value = plan(env)
    before = target.stat()
    body = bytearray(target.read_bytes())
    body[20] ^= 1
    target.write_bytes(body)
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    result = apply(env, value)
    assert result["state"] == "held" and target.exists()


def test_unchanged_container_but_changed_compose_or_env_dependency_holds(environment):
    env = environment
    old = add_old(env)
    dependency = env["releases"] / "private-compose.json"
    dependency.write_text('{"services":{"app":{"image":"fictional-image"}}}')
    env["value"]["protected_paths"].append({"path": str(dependency), "kind": "file"})
    env["protection"].write_bytes(encoded(env["value"]))
    value = plan(env)
    dependency.write_text('{"services":{"app":{"image":"different-fixture"}}}')
    with pytest.raises(RetentionHold, match="protected_dependency_changed"):
        apply(env, value)
    assert all(path.exists() for path in old)


def test_newly_copied_old_snapshot_gets_filesystem_age_grace(environment):
    env = environment
    target = add_old(env, 1)[0]
    os.utime(target, (NOW.timestamp(), NOW.timestamp()))
    value = plan(env)
    assert not value["candidates"]
    row = next(row for row in value["retained"] if row["path"] == str(target))
    assert "filesystem_minimum_age" in row["reasons"]
    assert target.exists()


def test_apply_independently_refuses_a_new_mtime_even_in_a_rehashed_plan(environment):
    env = environment
    target = add_old(env, 1)[0]
    value = plan(env)
    os.utime(target, (NOW.timestamp(), NOW.timestamp()))
    value["candidates"][0]["fingerprint"] = fingerprint(target)
    with pytest.raises(RetentionHold, match="filesystem_age_too_recent"):
        apply(env, value)
    assert target.exists()


@pytest.mark.parametrize("role,field", [("current", "stage"), ("current", "backup"),
                                        ("previous", "stage"), ("previous", "backup"),
                                        ("previous", "source_sha")])
def test_each_recovery_set_must_match_its_hash_pinned_accepted_ledger(environment, role, field):
    env = environment
    old = add_old(env)
    row = next(row for row in env["value"]["recovery_sets"] if row["role"] == role)
    if field == "stage":
        stage = env["releases"] / "wrong-stage"
        stage.mkdir()
        row["stage"] = str(stage)
    elif field == "backup":
        source = env[role]
        other = env["backups"] / "wrong-backup" / source.name
        other.parent.mkdir()
        shutil.copyfile(source, other)
        row["backup"] = {**row["backup"], "path": str(other), "size": other.stat().st_size,
                         "sha256": sha(other.read_bytes()), "verified": True}
    else:
        row["source_sha"] = "f" * 40
    env["protection"].write_bytes(encoded(env["value"]))
    with pytest.raises(RetentionHold, match="accepted_ledger_mismatch"):
        plan(env)
    assert all(path.exists() for path in old)


def test_changed_previous_ledger_cannot_be_rebound_by_planning_a_new_file_hash(environment):
    env = environment
    old = add_old(env)
    previous = Path(env["value"]["previous_ledger_path"])
    previous.write_bytes(previous.read_bytes() + b" ")
    with pytest.raises(RetentionHold, match="previous_release_ledger_changed"):
        plan(env)
    assert all(path.exists() for path in old)


@pytest.mark.parametrize("field,value", [("healthy", False), ("network_mode", "bridge"),
                                       ("container_id", "0" * 64), ("image", "sha256:" + "0" * 64),
                                       ("config_fingerprint", "0" * 64)])
def test_copilot_health_namespace_identity_and_image_changes_hold(environment, field, value):
    env = environment
    old = add_old(env)
    review = plan(env)
    live = binding()
    live["copilot"][field] = value
    with pytest.raises(RetentionHold, match="running_release_identity_mismatch"):
        apply(env, review, binding_provider=lambda: live)
    assert all(path.exists() for path in old)


def test_accepted_content_changed_before_a_fresh_plan_cannot_be_retrusted(environment):
    env = environment
    old = add_old(env)
    dependency = env["accepted_dependency"]
    dependency.write_bytes(dependency.read_bytes() + b"\nUNACCEPTED_FIXTURE_SECRET=must-not-appear\n")
    with pytest.raises(RetentionHold) as error:
        plan(env)
    assert "must-not-appear" not in str(error.value)
    assert all(path.exists() for path in old)


@pytest.mark.parametrize("change", ["missing_proof", "missing_pins", "substituted_pin"])
def test_missing_or_substituted_acceptance_evidence_holds_archive_retention(environment, change):
    env = environment
    old = add_old(env)
    if change == "missing_proof":
        env["value"].pop("accepted_recovery_proofs")
    elif change == "missing_pins":
        env["value"].pop("accepted_content_pins")
    else:
        env["value"]["accepted_content_pins"][0]["sha256"] = "0" * 64
    env["protection"].write_bytes(encoded(env["value"]))
    with pytest.raises(RetentionHold):
        plan(env)
    assert all(path.exists() for path in old)


def test_unknown_accepted_operation_kind_holds_even_with_fresh_proof_hashes(environment):
    env = environment
    old = add_old(env)
    wrapper = copy.deepcopy(env["wrapper"])
    wrapper["operation_kind"] = "unsupported-operation"
    reseal_wrapper(env, wrapper)
    with pytest.raises(RetentionHold, match="operation_kind"):
        plan(env)
    assert all(path.exists() for path in old)


def test_archive_capture_phase_cannot_be_swapped_between_recovery_roles(environment):
    env = environment
    old = add_old(env)
    wrapper = copy.deepcopy(env["wrapper"])
    wrapper["archives"]["current"]["capture_phase"] = wrapper["archives"]["previous"]["capture_phase"]
    reseal_wrapper(env, wrapper)
    with pytest.raises(RetentionHold, match="archive"):
        plan(env)
    assert all(path.exists() for path in old)


@pytest.mark.parametrize("change,reason", [("bare_steps", "accepted_file_reference_invalid"),
    ("missing_mtime", "accepted_migration_replay_protocol_unsupported"),
    ("missing_verification", "accepted_migration_replay_verification_missing")])
def test_legacy_replay_requires_guarded_source_metadata_and_native_verification(environment, change, reason):
    env = environment
    old = add_old(env)
    wrapper = copy.deepcopy(env["wrapper"])
    recipe_ref = wrapper["archives"]["current"]["recovery_recipe"]
    recipe_path = Path(recipe_ref["path"])
    recipe = json.loads(recipe_path.read_bytes())
    if change == "bare_steps":
        recipe.pop("replay_protocol")
    else:
        ref = recipe["replay_protocol" if change == "missing_mtime" else "protocol_verification"]
        path = Path(ref["path"])
        document = json.loads(path.read_bytes())
        if change == "missing_mtime":
            document["source_metadata"]["restore_mtime_ns"] = False
        else:
            document["checks"].pop("source-mtime-ns-rehydration")
        path.write_bytes(encoded(document))
        ref["sha256"] = sha(path.read_bytes())
    recipe_path.write_bytes(encoded(recipe))
    recipe_ref["sha256"] = sha(recipe_path.read_bytes())
    reseal_wrapper(env, wrapper)
    with pytest.raises(RetentionHold, match=reason):
        plan(env)
    assert all(path.exists() for path in old)


@pytest.mark.parametrize("schema,with_markers,transition", [("unified-v1", False, False),
    ("legacy", True, False), ("unified-v1", True, True)])
def test_recovery_archive_schema_is_checked_against_actual_verified_members(environment, schema, with_markers, transition):
    from app.services.storage_retention import _verified_archive
    env = environment
    if transition:
        (env["runtime"] / "data" / ".information-store-transition.json").write_bytes(b"{}")
    target = archive(env["runtime"], env["backups"] / "schema-probe", NOW) if with_markers else env["current"]
    with pytest.raises(RetentionHold, match="recovery_archive_(store_schema|transition)"):
        _verified_archive(target, recovery_backup={"store_schema": schema},
                          accepted_content_pins=env["value"]["accepted_content_pins"])
    assert target.exists()


def test_unified_recovery_archive_matches_authenticated_active_marker_hashes(environment):
    from app.services.storage_retention import _verified_archive
    env = environment
    target = archive(env["runtime"], env["backups"] / "unified-schema-probe", NOW)
    result = _verified_archive(target, recovery_backup={"store_schema": "unified-v1"},
                               accepted_content_pins=env["value"]["accepted_content_pins"])
    assert result["path"] == str(target) and target.exists()


@pytest.mark.parametrize("change", ["marker_content", "transition", "accepted_wrong_migration"])
def test_active_store_markers_and_migration_relationship_are_rechecked(environment, change):
    env = environment
    old = add_old(env)
    if change == "transition":
        (env["runtime"] / "data" / ".information-store-transition.json").write_bytes(encoded({"migration_id": "fixture-migration"}))
    else:
        marker_path = env["active_store_marker"]
        marker = json.loads(marker_path.read_bytes())
        marker["migration_id"] = "unaccepted-other-migration"
        marker_path.write_bytes(encoded(marker))
        if change == "accepted_wrong_migration":
            wrapper = copy.deepcopy(env["wrapper"])
            for pin in wrapper["configuration"]["post"]["app"]["dependency_files"]:
                if pin["path"] == str(marker_path):
                    pin["sha256"] = sha(marker_path.read_bytes())
            reseal_wrapper(env, wrapper)
    with pytest.raises(RetentionHold) as error:
        plan(env)
    if change != "marker_content":
        assert "store" in str(error.value) or "transition" in str(error.value)
    assert all(path.exists() for path in old)


def test_plan_cannot_substitute_newly_observed_hashes_for_accepted_content(environment):
    env = environment
    old = add_old(env)
    value = plan(env)
    # Even an explicitly rehashed plan must retain the acceptance-time seals.
    value["accepted_content_pins"][0] = {**value["accepted_content_pins"][0], "sha256": "0" * 64}
    with pytest.raises(RetentionHold, match="plan_accepted_content_pins_mismatch"):
        apply(env, value)
    assert all(path.exists() for path in old)


@pytest.mark.parametrize("during", ["plan", "apply"])
def test_accepted_content_race_during_archive_verification_holds_before_unlink(environment, monkeypatch, during):
    import app.services.storage_retention as retention
    env = environment
    old = add_old(env, 3)
    value = plan(env) if during == "apply" else None
    original = retention._verified_archive
    changed = False

    def verify_then_change(path, *args, **kwargs):
        nonlocal changed
        result = original(path, *args, **kwargs)
        if not changed and path in old:
            changed = True
            env["accepted_dependency"].write_bytes(b"UNACCEPTED_FIXTURE_SECRET=must-not-appear\n")
        return result

    monkeypatch.setattr(retention, "_verified_archive", verify_then_change)
    if during == "plan":
        with pytest.raises(RetentionHold) as error:
            plan(env)
        assert "must-not-appear" not in str(error.value)
    else:
        result = apply(env, value)
        assert result["state"] == "held" and result["retired_count"] == 0
        assert "must-not-appear" not in json.dumps(result)
    assert changed and all(path.exists() for path in old)


def test_accepted_proof_is_revalidated_before_sidecar_unlink(environment):
    env = environment
    target = add_old(env, 1)[0]
    sidecar = target.with_suffix(target.suffix + ".sha256")
    sidecar.write_text(sha(target.read_bytes()) + "  " + target.name + "\n", encoding="ascii")
    value = plan(env)

    def after_archive(event):
        if event["event"] == "archive_retired":
            env["accepted_dependency"].write_bytes(b"unaccepted after archive retirement\n")

    result = apply(env, value, event_callback=after_archive)
    assert result["state"] == "partial" and result["retired_count"] == 1
    assert not target.exists() and sidecar.exists()


def retention_cli():
    source = Path(__file__).resolve().parents[1] / "scripts" / "storage_retention.py"
    spec = importlib.util.spec_from_file_location("retention_cli_fixture", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def live_inspection_rows():
    state = {"Running": True, "Health": {"Status": "healthy"}}
    app = {"Id": "c" * 64, "Image": CURRENT,
        "Config": {"Env": ["FIXTURE_TOKEN=private-value"], "Labels": {
            "org.opencontainers.image.revision": "a" * 40,
            "com.docker.compose.project.config_files": "/srv/fixture/base.json"}},
        "HostConfig": {"NetworkMode": "bridge", "LogConfig": {"Type": "json-file", "Config": {}}},
        "Mounts": [{"Type": "bind", "Source": "/srv/fixture/data", "Destination": "/app/runtime/data", "RW": True}],
        "State": copy.deepcopy(state)}
    node = {"Id": "f" * 64, "Image": "sha256:" + "f" * 64,
        "Config": {"Env": [], "Labels": {"org.opencontainers.image.revision": "f" * 40}},
        "HostConfig": {"NetworkMode": "container:" + app["Id"]}, "Mounts": [], "State": copy.deepcopy(state)}
    caddy = {"Id": "8" * 64, "Image": "sha256:" + "e" * 64,
        "Config": {"Env": ["FIXTURE_CADDY_TOKEN=private-value"], "Labels": {}},
        "HostConfig": {"NetworkMode": "bridge", "LogConfig": {"Type": "json-file", "Config": {}}},
        "Mounts": [{"Type": "bind", "Source": "/srv/fixture/Caddyfile", "Destination": "/etc/caddy/Caddyfile", "RW": False}],
        "State": copy.deepcopy(state)}
    return [app, node, caddy]


@pytest.mark.parametrize("change", ["identity", "image", "environment", "logging", "mount", "running"])
def test_configuration_only_provider_binds_accepted_caddy_and_its_full_configuration(monkeypatch, change):
    import app.services.storage_retention as retention
    from types import SimpleNamespace
    cli = retention_cli()
    rows = live_inspection_rows()
    profile = {"operation_kind": "configuration-only", "accepted_caddy_id": rows[2]["Id"]}
    calls = []

    def inspect(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(rows))

    monkeypatch.setattr(cli.subprocess, "run", inspect)
    expected = cli._live_binding(profile)
    caddy = rows[2]
    if change == "identity":
        caddy["Id"] = "7" * 64
    elif change == "image":
        caddy["Image"] = "sha256:" + "7" * 64
    elif change == "environment":
        caddy["Config"]["Env"] = ["FIXTURE_CADDY_TOKEN=unaccepted-value"]
    elif change == "logging":
        caddy["HostConfig"]["LogConfig"]["Config"] = {"max-size": "999m"}
    elif change == "mount":
        caddy["Mounts"][0]["Source"] = "/srv/fixture/other-Caddyfile"
    else:
        caddy["State"]["Running"] = False
    with pytest.raises(RetentionHold) as error:
        retention._binding({"value": {"live_binding": expected}}, lambda: cli._live_binding(profile))
    assert "unaccepted-value" not in str(error.value)
    assert all(call == ["docker", "inspect", "deploy-app-1", "deploy-copilot-1", profile["accepted_caddy_id"]] for call in calls)


@pytest.mark.parametrize("identifier", [None, "deploy-caddy-1", "../arbitrary-container"])
def test_configuration_only_provider_refuses_unaccepted_caddy_reference_before_docker(monkeypatch, identifier):
    cli = retention_cli()
    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(RetentionHold, match="accepted_caddy_identity_missing"):
        cli._live_binding({"operation_kind": "configuration-only", "accepted_caddy_id": identifier})
    assert not calls


def cli_fixture(env, monkeypatch):
    cli = retention_cli()
    state = env["tmp"] / "state"
    state.mkdir(mode=0o700)
    monkeypatch.setattr(cli, "STATE_DIR", state)
    monkeypatch.setattr(cli, "_private_parent", lambda _: None)
    monkeypatch.setattr(cli, "_private_file", lambda path: path.read_bytes())
    config = {"version": 1, "state_dir": str(state), "ledger_path": str(env["ledger"]),
              "backup_root": str(env["backups"]), "archive_roots": [str(path) for path in env["roots"]],
              "retention": {"daily": 2, "weekly": 0, "monthly": 0}}
    policy = env["tmp"] / "policy.json"
    policy.write_bytes(encoded(config))
    args = cli._parser().parse_args(["--policy", str(policy), "--protection", str(state / "recovery.json"),
                                     "--plan-output", str(state / "retention-plan.json"),
                                     "--status-file", str(state / "retention-status.json"), "--refresh-protection"])
    return cli, args, config


@pytest.mark.parametrize("bad_output", ["protection", "plan", "status", "duplicate", "protected_state", "policy_state"])
def test_cli_rejects_output_collisions_before_any_metadata_write(environment, monkeypatch, bad_output):
    cli, args, config = cli_fixture(environment, monkeypatch)
    protection = environment["value"]
    target = environment["releases"] / "previous" / "baseline-private.json"
    target.write_text('{"fixture":"recovery data must survive"}')
    original = target.read_bytes()
    if bad_output == "protection":
        args.protection = target
    elif bad_output == "plan":
        args.plan_output = target
    elif bad_output == "status":
        args.status_file = target
    elif bad_output == "duplicate":
        args.plan_output = args.status_file
    elif bad_output == "policy_state":
        args.policy = cli.STATE_DIR / "policy.json"
    else:
        protection["protected_paths"].append({"path": str(cli.STATE_DIR), "kind": "directory"})
    monkeypatch.setattr(cli, "collect_recovery_manifest", lambda *_: protection)
    writes = []
    monkeypatch.setattr(cli, "_write", lambda *args: writes.append(args))
    with pytest.raises(RetentionHold):
        cli._run_locked(args, config, RetentionPolicy(daily=2, weekly=0, monthly=0), encoded(config))
    assert not writes and target.read_bytes() == original


@pytest.mark.skipif(os.name != "posix", reason="Linux/POSIX flock and rotation")
def test_cli_held_status_is_written_while_all_three_locks_remain_held(environment, monkeypatch):
    import fcntl
    cli, args, config = cli_fixture(environment, monkeypatch)
    locks = tuple(environment["tmp"] / f"release-{index}.lock" for index in range(3))
    for path in locks:
        path.touch()
    monkeypatch.setattr(cli, "SHARED_RELEASE_LOCKS", locks)
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setattr(cli, "collect_recovery_manifest", lambda *_: environment["value"])
    monkeypatch.setattr(cli, "create_plan", lambda *_args, **_kwargs: (_ for _ in ()).throw(RetentionHold("fixture_hold")))
    writes = []

    def write(path, value):
        for lock in locks:
            with lock.open("rb") as handle:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        writes.append((path, value))

    monkeypatch.setattr(cli, "_write", write)
    result = cli.main(["--policy", str(args.policy), "--protection", str(args.protection),
                       "--status-file", str(args.status_file), "--plan-output", str(args.plan_output), "--refresh-protection"])
    assert result == 1
    assert any(value.get("reason") == "fixture_hold" for _, value in writes)


@pytest.mark.skipif(os.name != "posix", reason="Linux/POSIX private history rotation")
def test_retirement_history_is_durable_and_bounded_to_three_fixed_logs(environment, monkeypatch):
    cli, _, _ = cli_fixture(environment, monkeypatch)
    # Keep the path/type guard while making owner policy independent of the CI UID.
    monkeypatch.setattr(cli, "_private_file", lambda path: __import__("app.services.storage_retention", fromlist=["read"]).read(path))
    path = cli.STATE_DIR / "retention-history.jsonl"
    for index in range(12):
        cli._history(path, {"event": "archive_retired", "id": index, "sha256": "a" * 64}, maximum_bytes=256)
    files = [path, path.with_name(path.name + ".1"), path.with_name(path.name + ".2")]
    assert all(file.exists() and file.stat().st_size <= 256 for file in files)
    records = [json.loads(line) for file in reversed(files) for line in file.read_text().splitlines()]
    assert records[-1]["id"] == 11
    assert all(record["event"] == "archive_retired" and record["sha256"] == "a" * 64 for record in records)
    assert len(records) < 12


@pytest.mark.parametrize("failure", ["missing_provenance", "unverified_image", "missing_image", "changed_receipt", "wrong_previous_hash"])
def test_missing_image_provenance_and_unaccepted_receipts_hold_all_retirement(environment, failure):
    env = environment
    old = add_old(env)
    value = env["value"]
    if failure == "missing_provenance":
        value.pop("protected_image_provenance")
    elif failure == "unverified_image":
        value["protected_image_provenance"][0]["provenance_verified"] = False
    elif failure == "missing_image":
        value["protected_image_provenance"] = value["protected_image_provenance"][:-1]
    else:
        proof = value["accepted_promotion_receipts"][0]
        receipt_path = Path(proof["path"])
        receipt = json.loads(receipt_path.read_bytes())
        if failure == "changed_receipt":
            receipt_path.write_bytes(receipt_path.read_bytes() + b" ")
        else:
            receipt["old_ledger_sha256"] = "f" * 64
            receipt_path.write_bytes(encoded(receipt))
            proof["sha256"] = sha(receipt_path.read_bytes())
            proof["old_ledger_sha256"] = "f" * 64
    env["protection"].write_bytes(encoded(value))
    with pytest.raises(RetentionHold):
        plan(env)
    assert all(path.exists() for path in old)


def offline_cli_execution(environment, monkeypatch):
    cli, args, config = cli_fixture(environment, monkeypatch)
    monkeypatch.setattr(cli, "collect_recovery_manifest", lambda *_: environment["value"])
    monkeypatch.setattr(cli, "verify_protected_image_provenance", lambda proofs: proofs)
    monkeypatch.setattr(cli, "_live_binding", lambda _protection: binding())
    monkeypatch.setattr(cli, "archive_open_file", lambda _: False)
    monkeypatch.setattr(cli, "_write", lambda path, value: path.write_bytes(encoded(value)))
    history = []
    monkeypatch.setattr(cli, "_history", lambda _path, event: history.append(event))
    return cli, args, config, history


def test_post_unlink_fsync_error_keeps_uncertain_intent_and_blocks_next_run(environment, monkeypatch):
    import app.services.storage_retention as retention
    env = environment
    old = add_old(env, 3)
    cli, args, config, history = offline_cli_execution(env, monkeypatch)
    args.apply = True
    original_unlink = retention._unlink_pinned

    def unlink_then_fsync_error(path, expected):
        path.unlink()
        raise OSError("synthetic parent fsync failure after unlink")

    monkeypatch.setattr(retention, "_unlink_pinned", unlink_then_fsync_error)
    first, code = cli._run_locked(args, config, RetentionPolicy(daily=2, weekly=0, monthly=0), encoded(config))
    assert code == 1 and first["state"] == "held" and first["retirement_outcome_uncertain"] is True
    assert sum(path.exists() for path in old) == 2
    intents_path = cli.STATE_DIR / "retention-intents.json"
    unresolved = intents_path.read_bytes()
    marker = json.loads(unresolved)
    assert marker["state"] == "needs_review"
    assert [event["event"] for event in marker["events"]] == ["retirement_intent"]
    previous_plan, previous_protection = args.plan_output.read_bytes(), args.protection.read_bytes()
    previous_history = list(history)
    monkeypatch.setattr(retention, "_unlink_pinned", original_unlink)
    second, code = cli._run_locked(args, config, RetentionPolicy(daily=2, weekly=0, monthly=0), encoded(config))
    assert code == 1 and second["reason"] == "unfinished_retirement_requires_review"
    assert intents_path.read_bytes() == unresolved
    assert args.plan_output.read_bytes() == previous_plan and args.protection.read_bytes() == previous_protection
    assert history == previous_history and sum(path.exists() for path in old) == 2


@pytest.mark.parametrize("prior_state", ["held", "partial", "complete"])
def test_unmatched_prior_intent_blocks_even_dryrun_before_plan_protection_history_writes(environment, monkeypatch, prior_state):
    env = environment
    old = add_old(env, 2)
    cli, args, config, history = offline_cli_execution(env, monkeypatch)
    args.apply = False
    intents_path = cli.STATE_DIR / "retention-intents.json"
    marker = {"version": 1, "state": prior_state, "plan_sha256": "d" * 64,
              "events": [{"event": "retirement_intent", "path": str(old[0]), "sha256": sha(old[0].read_bytes())}]}
    intents_path.write_bytes(encoded(marker))
    args.protection.write_bytes(encoded(env["value"]))
    args.plan_output.write_bytes(b"prior plan forensic evidence\n")
    before = {path: path.read_bytes() for path in [intents_path, args.protection, args.plan_output]}
    status, code = cli._run_locked(args, config, RetentionPolicy(daily=2, weekly=0, monthly=0), encoded(config))
    assert code == 1 and status["reason"] == "unfinished_retirement_requires_review"
    assert {path: path.read_bytes() for path in before} == before
    assert not history and all(path.exists() for path in old)


def test_final_history_failure_cannot_close_or_replace_retirement_marker(environment, monkeypatch):
    env = environment
    old = add_old(env, 2)
    cli, args, config, history = offline_cli_execution(env, monkeypatch)
    args.apply = True

    def failing_final_history(_path, event):
        if event["event"] == "run_finished":
            raise OSError("synthetic final history fsync failure")
        history.append(event)

    monkeypatch.setattr(cli, "_history", failing_final_history)
    with pytest.raises(OSError):
        cli._run_locked(args, config, RetentionPolicy(daily=2, weekly=0, monthly=0), encoded(config))
    assert not any(path.exists() for path in old)
    marker_path = cli.STATE_DIR / "retention-intents.json"
    marker_bytes = marker_path.read_bytes()
    marker = json.loads(marker_bytes)
    assert marker["state"] == "started"
    assert cli._unresolved_intent_count(marker) == 0  # matched outcomes still need a durable final record
    previous_plan, previous_protection = args.plan_output.read_bytes(), args.protection.read_bytes()
    monkeypatch.setattr(cli, "_history", lambda _path, event: history.append(event))
    before_history = list(history)
    status, code = cli._run_locked(args, config, RetentionPolicy(daily=2, weekly=0, monthly=0), encoded(config))
    assert code == 1 and status["reason"] == "unfinished_retirement_requires_review"
    assert marker_path.read_bytes() == marker_bytes
    assert args.plan_output.read_bytes() == previous_plan and args.protection.read_bytes() == previous_protection
    assert history == before_history


def test_symlink_and_hardlink_archives_never_deleted(environment):
    env = environment
    old = add_old(env, 3)
    linked = old[0].parent / "berry-runtime-20260101T010101Z.tar.gz"
    try:
        os.link(old[0], linked)
    except OSError:
        pytest.skip("hard links unavailable")
    value = plan(env)
    assert str(old[0]) not in {row["path"] for row in value["candidates"]}
    apply(env, value)
    assert old[0].exists() and linked.exists()


def test_symlink_archive_or_dependency_is_refused(environment):
    env = environment
    outside = archive(env["runtime"], env["tmp"] / "outside", NOW - timedelta(days=90))
    folder = env["backups"] / "symlink-attempt"
    folder.mkdir()
    link = folder / outside.name
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")
    value = plan(env)
    assert any(row["path"] == str(link) for row in value["held"])
    apply(env, value)
    assert outside.exists() and link.is_symlink()
    env["value"]["protected_paths"].append({"path": str(link), "kind": "file"})
    env["protection"].write_bytes(encoded(env["value"]))
    with pytest.raises(RetentionHold, match="symlink"):
        plan(env)
