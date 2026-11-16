"""Synthetic producer evidence shared by storage recovery/retention tests."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import stat
from types import SimpleNamespace


def encoded(value):
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def fixture_filesystem(monkeypatch):
    """Use real bounded files while modeling root ownership in isolated tests."""
    import app.services.storage_recovery as recovery
    import app.services.storage_retention as retention

    if __import__("os").name == "nt":
        # Windows test paths are native; production and Linux CI retain the
        # unmodified canonical POSIX host-path validator.
        posix_path = recovery._host_path

        def host_path(value):
            recovery._need(isinstance(value, str), "invalid_host_path")
            if value.startswith("/"):
                return posix_path(value)
            path = Path(value)
            recovery._need(path.is_absolute()
                           and ".." not in path.parts, "invalid_host_path")
            return str(path)
        monkeypatch.setattr(recovery, "_host_path", host_path)

    def stat_file(path):
        info = recovery._safe(path)
        mode = stat.S_IMODE(info.st_mode)
        if __import__("os").name == "nt":
            mode = 0o600  # POSIX mode bits do not represent Windows file ACLs.
        return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino,
            st_size=info.st_size, st_mtime_ns=info.st_mtime_ns,
            st_mode=stat.S_IFREG | mode, st_uid=0)

    def read_file(path, maximum):
        return retention.read(path, maximum=maximum)

    validator = recovery.validate_accepted_recovery_proofs
    monkeypatch.setattr(retention, "validate_accepted_recovery_proofs",
                        lambda manifest: validator(manifest, read_file=read_file, stat_file=stat_file))
    return read_file, stat_file


def reseal_wrapper(environment, wrapper):
    """Accept synthetic changed wrapper bytes, including subsequent promotion.

    Negative tests use this to reach semantic contract checks rather than
    stopping at an unsurprising changed-file digest check.
    """
    digest = lambda body: hashlib.sha256(body).hexdigest()
    pointer = environment["proof_pointer"]
    path = Path(pointer["path"])
    path.write_bytes(encoded(wrapper))
    document = json.loads(environment["ledger"].read_bytes())
    document["recovery_proof"]["sha256"] = digest(path.read_bytes())
    environment["ledger"].write_bytes(encoded(document))
    ledger_sha = digest(environment["ledger"].read_bytes())
    value = environment["value"]
    value["ledger_sha256"] = ledger_sha
    proof = next(row for row in value["accepted_promotion_receipts"] if row["role"] == "current")
    receipt_path = Path(proof["path"])
    receipt = json.loads(receipt_path.read_bytes())
    receipt["new_ledger_sha256"] = ledger_sha
    receipt_path.write_bytes(encoded(receipt))
    proof.update(sha256=digest(receipt_path.read_bytes()), new_ledger_sha256=ledger_sha)
    value["accepted_recovery_proofs"][0].update(sha256=document["recovery_proof"]["sha256"], ledger_sha256=ledger_sha)
    environment["protection"].write_bytes(encoded(value))


def producer_evidence(*, root, runtime, backups, current, previous, ledger,
                      previous_ledger, older_ledger):
    """Seal a fictional genuine PRE/POST producer transaction, without cycles.

    The caller seals promotion receipts after this writes the new ledger, then
    invokes the actual closure loader to obtain authenticated manifest pins.
    """
    import app.services.storage_recovery as recovery

    digest = lambda body: hashlib.sha256(body).hexdigest()
    current_row = json.loads(ledger.read_bytes())
    previous_row = json.loads(previous_ledger.read_bytes())
    older_row = json.loads(older_ledger.read_bytes())
    stage = Path(current_row["stage"])
    private = stage / "operator-private"
    private.mkdir(mode=0o700)
    deploy = root / "deploy"
    deploy.mkdir()

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else encoded(value))
        path.chmod(0o600)
        return {"path": str(path), "sha256": digest(path.read_bytes())}

    def pin(ref):
        return {**ref, "mode": 0o600}

    write(Path(previous_row["compose_override"]), {"services": {"app": {"image": previous_row["image"]}}})
    write(Path(previous_row["rollback_override"]), {"services": {"app": {"image": older_row["image"]}}})
    write(Path(previous_row["stage"]) / "cutover-fixture" / "old-ledger.bytes", older_ledger.read_bytes())
    write(stage / "cutover-fixture" / "old-ledger.bytes", previous_ledger.read_bytes())
    base = write(deploy / "compose.json", {"services": {"app": {}, "copilot": {}}})
    environment = write(deploy / "accepted.env", b"FIXTURE_TOKEN=accepted-private-value\n")
    dependency = write(deploy / "settings.json", {"fixture": "accepted configuration"})
    candidate_override = write(private / "candidate-override.json", {"services": {"app": {"image": current_row["image"]}}})
    rollback_override = write(private / "rollback-override.json", {"services": {"app": {"image": previous_row["image"]}}})
    mounts = [{"Type": "bind", "Source": str(runtime / name), "Destination": "/app/runtime/" + name,
               "RW": True, "Mode": "rw", "Propagation": "rprivate"} for name in ("data", "inbox")]
    mounts.append({"Type": "bind", "Source": str(backups), "Destination": "/app/backups",
                   "RW": True, "Mode": "rw", "Propagation": "rprivate"})
    node_image = "sha256:" + "f" * 64
    pairs, configuration = {}, {}
    for phase, document, app_id, node_id in [("pre", previous_row, "d" * 64, "9" * 64),
                                             ("post", current_row, "c" * 64, "f" * 64)]:
        compose = [base] + ([candidate_override] if phase == "post" else [])
        labels = {"com.docker.compose.project.config_files": ",".join(ref["path"] for ref in compose),
                  "com.docker.compose.project.environment_file": environment["path"],
                  "com.docker.compose.project": "fixture", "com.docker.compose.project.working_dir": str(deploy)}
        pair = {}
        for name, image, source, identifier in [("app", document["image"], document["source_sha"], app_id),
                                                ("copilot", node_image, "f" * 40, node_id)]:
            pair[name] = {"Id": identifier, "Image": image,
                "Config": {"Env": ["FIXTURE_TOKEN=accepted-private-value"], "Labels": {**labels,
                    "org.opencontainers.image.revision": source}, "Entrypoint": ["fixture"], "Cmd": [], "User": "1000:1000"},
                "HostConfig": {"NetworkMode": "bridge" if name == "app" else "container:" + app_id,
                    "LogConfig": {"Type": "json-file", "Config": {"max-size": "10m"}},
                    "Memory": 1024**3, "NanoCpus": 0, "RestartPolicy": {"Name": "unless-stopped"}},
                "Mounts": copy.deepcopy(mounts) if name == "app" else [],
                "State": {"Running": True, "Health": {"Status": "healthy"}}}
        pairs[phase] = pair
        configuration[phase] = {name: {"compose_files": [pin(ref) for ref in compose],
            "environment_files": [pin(environment)], "dependency_files": [pin(dependency)],
            "project": "fixture", "working_dir": str(deploy)} for name in ("app", "copilot")}
    snapshots = {phase: write(private / (phase + "-pair.json"), pair) for phase, pair in pairs.items()}
    native_pre = recovery._native_pair_binding(pairs["pre"])
    native_post = recovery._native_pair_binding(pairs["post"])
    native_environment = [pin(environment), pin(dependency)]
    baseline = write(private / "producer-baseline.json", {"production_binding": native_pre,
        "protected_environment_files": native_environment,
        "compose": {name: {"files": [base]} for name in ("app", "copilot")}})
    module = write(private / "rollback-module.py", b"# fictional reviewed rollback module\n")
    nonce = "3" * 32
    plan_value = {"operation_kind": "unified-migration", "nonce": nonce,
                  "candidate_image": current_row["image"], "source_sha": current_row["source_sha"],
                  "canonical_sha": "4" * 40, "modules": {"storage": module}, "proofs": {"baseline": baseline}}
    plan = write(private / "final-plan.json", plan_value)
    raw = backups / "information-migration-backups" / "fixture-migration"
    recovery_files = {"baseline": baseline,
        "source_receipt": write(private / "source-receipt.json", {"fixture": "verified source"}),
        "post_apply_manifest": write(private / "post-apply.json", {"fixture": "post migration"}),
        "post_startup_manifest": write(private / "post-startup.json", {"fixture": "post startup"}),
        "legacy_promotion_manifest": write(private / "legacy-promotion.bin", b"fictional legacy promotion bytes\n"),
        "raw_plan": write(raw / "PLAN.private.json", {"migration_id": "fixture-migration"}),
        "raw_manifest": write(raw / "MANIFEST.json", {"fixture": "raw source inventory"}),
        "rollback_modules": [module]}
    marker = write(runtime / "data" / "information" / "store.json", {"version": 1, "state": "active",
        "data_dir": "/app/runtime/data", "inbox_dir": "/app/runtime/inbox",
        "store_root": "/app/runtime/data/information", "migration_id": "fixture-migration",
        "backup_dir": "/app/backups/information-migration-backups/fixture-migration"})
    inbox_binding = write(runtime / "inbox" / ".information-store.json", {"version": 1,
        "inbox_dir": "/app/runtime/inbox", "store_root": "/app/runtime/data/information"})
    configuration["post"]["app"]["dependency_files"].extend([pin(marker), pin(inbox_binding)])
    archives = {role: {"path": str(path), "sha256": digest(path.read_bytes()), "size": path.stat().st_size}
                for role, path in [("current", current), ("previous", previous)]}
    proof_value = {"state": "recovery-prepared", **{key: plan_value[key] for key in
        ("operation_kind", "nonce", "candidate_image", "source_sha", "canonical_sha")},
        "baseline_path": baseline["path"], "baseline_sha256": baseline["sha256"],
        "old_binding": native_pre, "candidate_binding": native_post,
        "compose_files": [base], "protected_files": native_environment,
        "candidate_override": candidate_override, "rollback_override": rollback_override,
        **{key: recovery_files[key] for key in ("source_receipt", "post_apply_manifest", "post_startup_manifest", "legacy_promotion_manifest")},
        "migration": {"activated": True, "migration_id": "fixture-migration",
                      "backup_path": "/app/backups/information-migration-backups/fixture-migration"},
        "raw_backup_seals": {"PLAN.private.json": recovery_files["raw_plan"]["sha256"],
                             "MANIFEST.json": recovery_files["raw_manifest"]["sha256"]},
        "offhost_archive": {"archive_sha256": archives["current"]["sha256"], "archive_bytes": archives["current"]["size"]},
        "rollback_recipe": {"plan_sha256": plan["sha256"], "operator_modules": plan_value["modules"],
            "on_guard_refusal": "preserve-new-work-and-hold-maintenance",
            "steps": ["pause-reviewed-writers", "stop-known-pair", "strict-storage-rollback", "verify-legacy-source-hashes",
                      "restore-exact-legacy-promotion-manifest", "restore-old-compose-pair", "verify-old-pair",
                      "restore-original-timer", "restore-write-barrier"]}}
    proof = write(private / "recovery-proof-1.json", proof_value)
    recovery_files["final_proof"] = proof
    transformation = write(private / "migration-transformation.json", {
        "schema": "berry.migration-transformation.v1", "state": "verified",
        "archive_sha256": archives["current"]["sha256"], "source_inventory_sha256": "5" * 64,
        "migration_id": "fixture-migration", "raw_plan": recovery_files["raw_plan"],
        **{key: recovery_files[key] for key in
           ("source_receipt", "post_apply_manifest", "post_startup_manifest", "final_proof")}})
    replay_program = write(private / "replay-program.py", b"# fictional reviewed source-metadata replay program\n")
    replay_test = write(private / "replay-test.py", b"# fictional native replay verification program\n")
    replay_native = write(private / "replay-native-receipt.json", {"fixture": "native verified replay"})
    protocol = write(private / "replay-protocol.json", {"schema": "berry.migration-replay-protocol.v1",
        "image": current_row["image"], "source_sha": current_row["source_sha"], "program": replay_program,
        "restore": {"module": "app.services.runtime_backup", "function": "restore_backup", "require_empty": True},
        "source_metadata": {"from": "raw-plan.sources", "verify_size_and_sha256_before_metadata": True,
            "restore_mtime_ns": True, "reject_unknown_roots_and_unsafe_paths": True},
        "plan": {"module": "app.services.information_migration", "function": "plan_migration", "fresh_runtime_paths": True},
        "apply": {"module": "app.services.information_migration", "function": "apply_migration", "quiesced": True,
            "resume_id": None, "new_empty_backup_base": True},
        "verification": ["current-store", "winner-and-variants", "analyst-decisions", "all-protected-runtime-state"],
        "original_migration_id_is_provenance_only": True})
    verification = write(private / "replay-verification.json", {"schema": "berry.migration-replay-verification.v1",
        "state": "passed", "image": current_row["image"], "source_sha": current_row["source_sha"],
        "protocol_sha256": protocol["sha256"], "program_sha256": replay_program["sha256"],
        "test_program": replay_test, "native_receipt": replay_native,
        "checks": {name: True for name in ["restore-bytes-and-modes", "source-hashes-before-mtime",
            "source-mtime-ns-rehydration", "fresh-plan-at-new-paths", "new-empty-backup-base", "no-resume-id",
            "winner-and-variants-preserved", "analyst-decisions-preserved", "current-store-verification"]}})
    replay = write(private / "migration-replay.json", {"schema": "berry.migration-replay.v1",
        "archive_sha256": archives["current"]["sha256"], "candidate_image": current_row["image"],
        "source_sha": current_row["source_sha"], "migration_id": "fixture-migration",
        "raw_plan": recovery_files["raw_plan"], "operator_modules": plan_value["modules"],
        "steps": ["restore-legacy-runtime", "run-exact-migration", "verify-unified-store-and-preservation"],
        "transformation_proof": transformation, "replay_protocol": protocol, "protocol_verification": verification})
    archives["current"].update(capture_phase="pre-migration", store_schema="legacy", recovery_role="migration-replay",
                               recovery_recipe=replay, transformation_proof=transformation)
    archives["previous"].update(capture_phase="pre-release", store_schema="legacy", recovery_role="direct",
                                recovery_recipe=None, transformation_proof=None)
    recovery_files["phase_receipt"] = write(private / "completed-phase.json", {"phase": "completed", "writers_resumed": True,
        "maintenance_held": False, "bindings": {**{key: plan_value[key] for key in
            ("operation_kind", "nonce", "candidate_image", "source_sha", "canonical_sha")},
            "archive_sha256": archives["current"]["sha256"], "source_inventory_sha256": "5" * 64,
            "source_receipt_sha256": recovery_files["source_receipt"]["sha256"]},
        "final_verification": {"recovery_proof_path": proof["path"], "recovery_proof_sha256": proof["sha256"],
            "candidate_binding_sha256": digest(recovery._canonical(native_post))}})
    wrapper = {"schema": recovery.RECOVERY_PROOF_SCHEMA, "operation_kind": "unified-migration", "operation_nonce": nonce,
        "current": {key: current_row[key] for key in ("source_sha", "image", "stage")},
        "previous_ledger": {"path": str(previous_ledger), "sha256": digest(previous_ledger.read_bytes())},
        "plan": plan, "snapshots": snapshots, "configuration": configuration, "recovery_files": recovery_files,
        "protected_dirs": [str(stage), previous_row["stage"], str(runtime / "data"), str(runtime / "inbox"),
                           str(runtime / "data" / "information"), str(raw)],
        "archives": archives, "images": [{"image": row["image"], "source_sha": row["source_sha"]}
            for row in [current_row, previous_row, older_row, {"image": node_image, "source_sha": "f" * 40}]]}
    pointer = write(private / "accepted-recovery.json", wrapper)
    current_row["recovery_proof"] = {"schema": recovery.RECOVERY_PROOF_SCHEMA, **pointer}
    write(ledger, current_row)
    return {"accepted_dependency": Path(environment["path"]), "wrapper": wrapper,
            "active_store_marker": Path(marker["path"]), "inbox_store_binding": Path(inbox_binding["path"]),
            "post_pair": pairs["post"], "proof_pointer": current_row["recovery_proof"]}
