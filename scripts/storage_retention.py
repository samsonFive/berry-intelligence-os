#!/usr/bin/env python3
"""Plan or apply bounded nested-backup retention under the shared release locks."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path("/var/lib/berry-storage-controls")
sys.path.insert(0, str(ROOT))

from app.services.storage_recovery import (  # noqa: E402
    collect_recovery_manifest, SHARED_RELEASE_LOCKS, recovery_live_binding,
    verify_protected_image_provenance, StorageRecoveryError,
)
from app.services.storage_retention import (  # noqa: E402
    RetentionHold, RetentionPolicy, apply_plan, create_plan, encoded, need, read, safe, sha, archive_open_file, load_protection,
)


def _private_file(path: Path) -> bytes:
    body = read(path)
    info = path.stat()
    need(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o600, "root_private_file_required")
    return body


def _private_parent(path: Path) -> None:
    safe(path.parent, directory=True)
    info = path.parent.stat()
    need(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700, "root_private_output_directory_required")
    if path.exists() or path.is_symlink():
        _private_file(path)


def _write(path: Path, value: dict) -> None:
    _private_parent(path)
    body = encoded(value)
    fd, name = tempfile.mkstemp(prefix=".retention-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _live_binding(protection: dict) -> dict:
    kind = protection.get("operation_kind")
    need(kind in {"unified-migration", "configuration-only"}, "accepted_operation_kind_unsupported")
    identifiers = ["deploy-app-1", "deploy-copilot-1"]
    caddy_id = protection.get("accepted_caddy_id")
    if kind == "configuration-only":
        need(isinstance(caddy_id, str) and bool(re.fullmatch(r"[a-f0-9]{64}", caddy_id)),
             "accepted_caddy_identity_missing")
        identifiers.append(caddy_id)
    else:
        need(caddy_id is None, "unexpected_caddy_profile")
    result = subprocess.run(["docker", "inspect", *identifiers], input="", capture_output=True,
                            text=True, timeout=30)
    need(result.returncode == 0, "running_app_unavailable")
    try:
        rows = json.loads(result.stdout)
    except ValueError:
        raise RetentionHold("running_app_unavailable") from None
    need(isinstance(rows, list) and len(rows) == len(identifiers) and all(isinstance(row, dict) for row in rows),
         "running_app_unavailable")
    if kind == "configuration-only":
        need(rows[2].get("Id") == caddy_id, "running_caddy_identity_mismatch")
    try:
        return recovery_live_binding(rows[0], rows[1], caddy_inspection=rows[2] if len(rows) == 3 else None)
    except StorageRecoveryError as error:
        raise RetentionHold(str(error)) from None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--protection", type=Path, required=True)
    parser.add_argument("--refresh-protection", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--status-file", type=Path, default=Path("/var/lib/berry-storage-controls/retention-status.json"))
    parser.add_argument("--plan-output", type=Path, default=Path("/var/lib/berry-storage-controls/retention-plan.json"))
    parser.add_argument("--expected-plan-sha256")
    return parser


def _validate_outputs(args, config: dict, protection: dict) -> None:
    """Reject every output collision before the first metadata replacement."""
    state = STATE_DIR
    need(config.get("state_dir", str(state)) == str(state), "dedicated_state_directory_required")
    required = {args.protection: "recovery.json", args.plan_output: "retention-plan.json",
                args.status_file: "retention-status.json"}
    need(len(required) == 3 and all(path == state / name for path, name in required.items()),
         "retention_output_location_invalid")
    outputs = list(required) + [state / "retention-intents.json", state / "retention-history.jsonl",
                                state / "retention-history.jsonl.1", state / "retention-history.jsonl.2"]
    need(not args.policy.is_relative_to(state), "policy_must_be_outside_state_directory")
    ledger = Path(config["ledger_path"])
    need(not state.is_relative_to(ledger.parent), "state_directory_overlaps_release_tree")
    need(not any(state.is_relative_to(Path(root)) or Path(root).is_relative_to(state)
                 for root in config["archive_roots"]), "state_directory_overlaps_archive_tree")
    dependencies = list(protection.get("protected_paths") or [])
    for recovery in protection.get("recovery_sets") or []:
        dependencies += [{"path": recovery["stage"], "kind": "directory"},
                         {"path": recovery["backup"]["path"], "kind": "file"}]
    for path in outputs:
        need(path not in {args.policy, ledger, Path(protection["previous_ledger_path"])}, "output_overlaps_policy_or_ledger")
        for dependency in dependencies:
            target = Path(dependency["path"])
            need(path != target and not (dependency["kind"] == "directory" and path.is_relative_to(target)),
                 "output_overlaps_protected_recovery")
        _private_parent(path)


def _history(path: Path, event: dict, *, maximum_bytes: int = 1024**2) -> None:
    """Three fixed private log files; no archive or recovery metadata is rotated."""
    _private_parent(path)
    line = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
    need(len(line) <= min(maximum_bytes, 64 * 1024), "history_record_size_limit")
    first, second = path.with_name(path.name + ".1"), path.with_name(path.name + ".2")
    for item in [first, second]:
        if item.exists() or item.is_symlink():
            _private_file(item)
    if path.exists() and path.stat().st_size + len(line) > maximum_bytes:
        if second.exists():
            second.unlink()
        if first.exists():
            os.replace(first, second)
        os.replace(path, first)
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "ab") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _unresolved_intent_count(record: dict) -> int:
    """Match outcomes in order; a state label alone cannot close an intent."""
    events = record.get("events")
    if not isinstance(events, list):
        return 1
    pending = Counter()
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("path"), str) or not isinstance(event.get("sha256"), str):
            return 1
        key = (event["path"], event["sha256"])
        if event.get("event") == "retirement_intent":
            pending[key] += 1
        elif event.get("event") == "archive_retired" and pending[key] > 0:
            pending[key] -= 1
        else:
            return 1
    return sum(pending.values())


def _run_locked(args, config: dict, policy: RetentionPolicy, policy_body: bytes) -> tuple[dict, int]:
    """All metadata/status/history writes happen while the caller holds 3 locks."""
    roots = [Path(value) for value in config["archive_roots"]]
    ledger_path, backup_root = Path(config["ledger_path"]), Path(config["backup_root"])
    # No writes, including HELD status, before outputs are proven outside both
    # recovery sets. A bad destination only yields a sanitized journal message.
    if args.refresh_protection:
        protection = collect_recovery_manifest(ledger_path, backup_root)
    else:
        _private_file(args.protection)
        protection = load_protection(args.protection, verify_archives=False)["value"]
    _validate_outputs(args, config, protection)
    previous = json.loads(_private_file(args.status_file)) if args.status_file.exists() else {}
    intents_path = STATE_DIR / "retention-intents.json"

    def binding_with_images():
        try:
            verify_protected_image_provenance(protection["protected_image_provenance"])
        except StorageRecoveryError:
            raise RetentionHold("protected_image_provenance_unavailable") from None
        return _live_binding(protection)

    try:
        # This admission check precedes protection/plan/history replacement in
        # every mode, including a dry run. Never erase a prior uncertain unlink.
        if intents_path.exists():
            old_intents = json.loads(_private_file(intents_path))
            need(old_intents.get("state") in {"complete", "partial", "held"}
                 and _unresolved_intent_count(old_intents) == 0, "unfinished_retirement_requires_review")
        if args.refresh_protection:
            _write(args.protection, protection)
        if args.apply and not args.refresh_protection:
            need(bool(args.expected_plan_sha256), "explicit_plan_sha256_required")
            plan_bytes = _private_file(args.plan_output)
            plan, digest = json.loads(plan_bytes), args.expected_plan_sha256
        else:
            plan = create_plan(roots, args.protection, policy=policy, binding_provider=binding_with_images)
            plan["policy_file_sha256"] = sha(policy_body)
            _write(args.plan_output, plan)
            plan_bytes = encoded(plan)
            digest = sha(plan_bytes)
        need(plan["archive_roots"] == sorted(str(root) for root in roots)
             and plan["policy"] == json.loads(json.dumps(policy.__dict__))
             and plan["ledger_path"] == str(ledger_path)
             and plan["protection_manifest"] == str(args.protection)
             and plan.get("policy_file_sha256") == sha(policy_body), "plan_policy_binding_changed")
        need(sha(plan_bytes) == digest, "plan_sha256_mismatch")
        history_path = STATE_DIR / "retention-history.jsonl"
        if args.apply:
            intents = {"version": 1, "state": "started", "plan_sha256": digest, "events": []}
            _history(history_path, {"event": "run_started", "plan_sha256": digest, "ledger_sha256": plan["ledger_sha256"],
                                    "at": datetime.now(timezone.utc).isoformat(), "policy": plan["policy"]})
            _write(intents_path, intents)

            def event(value):
                intents["events"].append(value)
                _write(intents_path, intents)
                _history(history_path, {"plan_sha256": digest, **value})

            result = apply_plan(plan_bytes, digest, binding_provider=binding_with_images, event_callback=event,
                                open_file_guard=archive_open_file)
            unresolved = _unresolved_intent_count(intents)
            intents["state"] = "needs_review" if unresolved else result["state"]
            if unresolved:
                _write(intents_path, intents)
                result.update({"state": "held", "reason": "unfinished_retirement_requires_review",
                               "retirement_outcome_uncertain": True, "unresolved_intent_count": unresolved})
            _history(history_path, {"event": "run_finished", **result})
            if not unresolved:
                # Close the marker only after the durable run outcome exists.
                # A history failure leaves the on-disk started marker intact.
                _write(intents_path, intents)
            status = {**result, "mode": "apply", "last_success_at": result["checked_at"] if result["state"] == "complete" else previous.get("last_success_at")}
        else:
            status = {"version": 1, "state": "planned", "mode": "dry_run", "checked_at": datetime.now(timezone.utc).isoformat(),
                      "last_success_at": previous.get("last_success_at"), "recovery_sets_verified": True,
                      "plan_sha256": digest, "candidate_count": len(plan["candidates"]),
                      "candidate_bytes": plan["candidate_bytes"], "held_count": len(plan["held"]),
                      "deferred_count": len(plan["deferred"]), "retired_count": 0, "retired_bytes": 0,
                      "ledger_sha256": plan["ledger_sha256"]}
        status.update({"policy_file_sha256": sha(policy_body), "protection_manifest_sha256": plan["protection_manifest_sha256"],
                       "current_and_previous_recovery_sets_preserved": True, "root_daily_rotation_unchanged": True})
        _write(args.status_file, status)
        return status, 0 if status["state"] in {"planned", "complete"} else 1
    except RetentionHold as error:
        # A pre-mutation guard can fail after the empty run marker is written.
        # Only an empty marker is safe to close automatically; any recorded
        # unlink intent left by an interrupted process still requires review.
        if "intents" in locals() and not intents["events"] and intents.get("state") == "started":
            intents["state"] = "held"
            _write(intents_path, intents)
        status = {"version": 1, "state": "held", "checked_at": datetime.now(timezone.utc).isoformat(),
                  "reason": str(error), "last_success_at": previous.get("last_success_at"), "raw_details_suppressed": True}
        _write(args.status_file, status)
        return status, 1


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    need(os.name == "posix" and os.geteuid() == 0, "linux_host_root_required")
    policy_body = _private_file(args.policy)
    config = json.loads(policy_body)
    need(config.get("version") == 1, "policy_version_invalid")
    policy = RetentionPolicy(**config.get("retention", {}))
    need(Path(config["backup_root"]) in [Path(value) for value in config["archive_roots"]], "backup_root_must_be_an_archive_root")
    locks = [Path(value) for value in config.get("release_locks", SHARED_RELEASE_LOCKS)]
    need(locks == list(SHARED_RELEASE_LOCKS), "shared_release_lock_set_changed")
    import fcntl
    try:
        with ExitStack() as stack:
            for lock in locks:
                safe(lock)
                fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
                stack.callback(os.close, fd)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise RetentionHold("release_window_busy") from None
            need(read(args.policy) == policy_body, "policy_changed_after_lock")
            status, code = _run_locked(args, config, policy, policy_body)
            print(json.dumps(status, sort_keys=True))
            return code
    except RetentionHold as error:
        # No writes occur inside a busy release slot. The unit journal remains
        # the visible signal; do not race its runtime/state files for a status.
        if str(error) == "release_window_busy":
            print(json.dumps({"state": "skipped", "reason": "release_window_busy", "retired_count": 0}))
            return 0
        status = {"version": 1, "state": "held", "checked_at": datetime.now(timezone.utc).isoformat(),
                  "reason": str(error), "raw_details_suppressed": True}
        print(json.dumps(status))
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RetentionHold, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"state": "held", "reason": "retention_command_refused", "raw_details_suppressed": True}))
        raise SystemExit(1)
