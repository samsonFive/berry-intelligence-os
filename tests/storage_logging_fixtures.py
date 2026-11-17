"""A synthetic logging release over an authenticated unified-store fixture."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from storage_recovery_fixtures import encoded


def configuration_only_environment(environment, *, now):
    import app.services.storage_recovery as recovery
    from app.services.runtime_backup import create_backup

    env = dict(environment)
    old = copy.deepcopy(environment["wrapper"])
    digest = lambda body: hashlib.sha256(body).hexdigest()
    ledger = environment["ledger"]
    old_raw = ledger.read_bytes()
    old_row = json.loads(old_raw)
    stage = env["releases"] / "logging-current"
    private = stage / "operator-private"
    private.mkdir(parents=True, mode=0o700)

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else encoded(value))
        path.chmod(0o600)
        return {"path": str(path), "sha256": digest(path.read_bytes())}

    def pin(ref):
        return {**ref, "mode": 0o600}

    previous = write(private / "ledger-before.bytes", old_raw)
    older = write(Path(old_row["stage"]) / "operator-private" / "old-ledger.bytes",
                  Path(environment["value"]["previous_ledger_path"]).read_bytes())
    current_backup = create_backup(env["runtime"], env["backups"] / "logging-current-recovery", now=now)
    current_archive = {"path": str(current_backup), "sha256": digest(current_backup.read_bytes()),
        "size": current_backup.stat().st_size, "capture_phase": "pre-configuration", "store_schema": "unified-v1",
        "recovery_role": "direct", "recovery_recipe": None, "transformation_proof": None}
    candidate = write(private / "candidate-override.json", {"services": {
        name: {"logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}}
        for name in ("app", "copilot", "caddy")}})
    rollback = write(private / "rollback-override.json", {"fixture": "restore exact prior logging and pair"})
    pre = copy.deepcopy(environment["post_pair"])
    post = copy.deepcopy(pre)
    target_logging = {"Type": "json-file", "Config": {"max-size": "10m", "max-file": "3"}}
    configuration = {"pre": copy.deepcopy(old["configuration"]["post"]),
                     "post": copy.deepcopy(old["configuration"]["post"])}
    for name, identifier in [("app", "1" * 64), ("copilot", "2" * 64)]:
        post[name]["Id"] = identifier
        post[name]["HostConfig"]["LogConfig"] = copy.deepcopy(target_logging)
        configuration["post"][name]["compose_files"].append(pin(candidate))
        post[name]["Config"]["Labels"]["com.docker.compose.project.config_files"] += "," + candidate["path"]
    post["copilot"]["HostConfig"]["NetworkMode"] = "container:" + post["app"]["Id"]
    snapshots = {phase: write(private / (phase + "-pair.json"), pair) for phase, pair in [("pre", pre), ("post", post)]}
    pre_files = configuration["pre"]["app"]["compose_files"]
    native_environment = copy.deepcopy(json.loads(Path(old["recovery_files"]["baseline"]["path"]).read_bytes())["protected_environment_files"])
    baseline = write(private / "producer-baseline.json", {"production_binding": recovery._native_pair_binding(pre),
        "protected_environment_files": native_environment,
        "compose": {name: {"files": copy.deepcopy(pre_files)} for name in ("app", "copilot")}})
    nonce = "6" * 32
    program = write(private / "logging-operator.py", b"# fictional native logging-release operator\n")
    plan_value = {"operation_kind": "configuration-only", "nonce": nonce, "candidate_image": old_row["image"],
        "source_sha": old_row["source_sha"], "canonical_sha": "7" * 40, "modules": {"logging": program},
        "proofs": {"baseline": baseline}, "operational_allowlist": []}
    plan = write(private / "final-plan.json", plan_value)
    caddy_file = write(env["tmp"] / "deploy" / "Caddyfile", b"# fictional unchanged proxy configuration\n")
    caddy_pre = {"Id": "8" * 64, "Image": "sha256:" + "e" * 64,
        "Config": {"Env": ["FIXTURE_CADDY_TOKEN=unchanged-private-value"], "Labels": {
            key: value for key, value in pre["app"]["Config"]["Labels"].items() if key.startswith("com.docker.compose.")}},
        "HostConfig": {"NetworkMode": "bridge", "LogConfig": {"Type": "json-file", "Config": {}}},
        "Mounts": [{"Type": "bind", "Source": caddy_file["path"], "Destination": "/etc/caddy/Caddyfile", "RW": False}],
        "State": {"Running": True, "Health": {"Status": "healthy"}}}
    caddy_post = copy.deepcopy(caddy_pre)
    caddy_post["Id"] = "3" * 64
    caddy_post["HostConfig"]["LogConfig"] = copy.deepcopy(target_logging)
    caddy_post["Config"]["Labels"]["com.docker.compose.project.config_files"] += "," + candidate["path"]
    caddy_configs = {phase: {**copy.deepcopy(configuration[phase]["app"]), "dependency_files": [pin(caddy_file)]}
                     for phase in ("pre", "post")}
    caddy_pre_config = write(private / "caddy-pre-config.json", {"fixture": "unchanged original proxy config"})
    caddy_post_config = write(private / "caddy-post-config.json", {"fixture": "unchanged original proxy config"})
    caddy = {"pre_snapshot": write(private / "caddy-pre.json", caddy_pre),
        "post_snapshot": write(private / "caddy-post.json", caddy_post),
        "pre_configuration": caddy_pre_config, "post_configuration": caddy_post_config,
        "configuration": caddy_configs, "original_config_sha256": caddy_pre_config["sha256"],
        "barrier_handoff": write(private / "caddy-handoff.json", {"old_container_id": caddy_pre["Id"],
            "new_container_id": caddy_post["Id"], "backend_stopped_during_handoff": True,
            "original_config_sha256": caddy_pre_config["sha256"], "new_contract": {"fixture": "new Caddy contract"},
            "new_barrier_proof": {"fixture": "write barrier verified"}})}
    before = write(private / "runtime-before.json", {"fixture": "preserved runtime inventory"})
    after = write(private / "runtime-after.json", {"fixture": "preserved runtime inventory"})
    logical_before = write(private / "logical-before.json", {"workspaces": 2, "reports": 3})
    logical_after = write(private / "logical-after.json", {"workspaces": 2, "reports": 3})
    audit = write(private / "startup-audit.json", {"operation_kind": "configuration-only", "nonce": nonce,
        "workspace_before": {"fixture": "preserved"}, "workspace_after": {"fixture": "preserved"},
        "binary_invariant_before": {"fixture": "preserved"}, "binary_invariant_after": {"fixture": "preserved"}, "mutations": {}})
    markers = [copy.deepcopy(row) for row in configuration["post"]["app"]["dependency_files"]
               if row["path"] in {str(env["active_store_marker"]), str(env["inbox_store_binding"])}]
    physical_roots = [str(env["runtime"] / name) for name in ("data", "inbox")]
    recovery_files = {"baseline": baseline, "source_receipt": write(private / "source-receipt.json", {
        "fixture": "verified local unified backup", "archive_sha256": current_archive["sha256"],
        "source_inventory_sha256": "5" * 64, "source_inventory_after_sha256": "5" * 64, "source_stable": True}),
        "post_apply_manifest": before, "post_startup_manifest": after,
        **{name: copy.deepcopy(old["recovery_files"][name]) for name in ("raw_plan", "raw_manifest", "legacy_promotion_manifest")},
        "rollback_modules": [program, *copy.deepcopy(old["recovery_files"]["rollback_modules"])]}
    origin = json.loads(Path(old["recovery_files"]["final_proof"]["path"]).read_bytes())
    proof_value = {"state": "recovery-prepared", **{key: plan_value[key] for key in
        ("operation_kind", "nonce", "candidate_image", "source_sha", "canonical_sha")},
        "baseline_path": baseline["path"], "baseline_sha256": baseline["sha256"],
        "old_binding": recovery._native_pair_binding(pre), "candidate_binding": recovery._native_pair_binding(post),
        "compose_files": copy.deepcopy(pre_files), "protected_files": native_environment,
        "candidate_override": candidate, "rollback_override": rollback,
        **{name: recovery_files[name] for name in ("source_receipt", "post_apply_manifest", "post_startup_manifest")},
        "local_archive": {"path": current_archive["path"], "archive_sha256": current_archive["sha256"],
            "archive_bytes": current_archive["size"], **{key: current_archive[key] for key in ("capture_phase", "store_schema", "recovery_role")},
            "source_receipt": recovery_files["source_receipt"]},
        "inherited_storage_recovery": {"kind": "inherited-active-unified-store", "origin_proof": old["recovery_files"]["final_proof"],
            "migration": origin["migration"], **{name: old["recovery_files"][name] for name in ("raw_plan", "raw_manifest", "legacy_promotion_manifest")},
            "rollback_modules": old["recovery_files"]["rollback_modules"], "protected_dirs": old["protected_dirs"], "active_markers": markers},
        "configuration_delta": {"kind": "logging-only", "services": ["app", "copilot", "caddy"], "log_config": target_logging},
        "configuration_preservation": {"before_manifest": before, "after_manifest": after,
            "before_logical": logical_before, "after_logical": logical_after, "startup_audit": audit,
            "active_markers": markers, "physical_roots": physical_roots},
        "caddy": caddy, "pair_snapshots": snapshots,
        "configuration_post": {**configuration["post"], "caddy": caddy_configs["post"]},
        "rollback_recipe": {"operator_modules": plan_value["modules"], "plan_sha256": plan["sha256"],
            "on_guard_refusal": "preserve-new-work-and-hold-maintenance",
            "steps": ["pause-reviewed-writers", "stop-known-pair", "restore-old-caddy-configuration", "verify-new-caddy-write-barrier",
                "restore-old-compose-pair-on-current-store", "verify-current-store-preservation", "verify-old-pair",
                "restore-original-timer", "restore-write-barrier"]}}
    if environment["value"].get("accepted_native_origin") is not None:
        proof_value["inherited_storage_recovery"]["native_origin"] = copy.deepcopy(environment["value"]["accepted_native_origin"])
    final_proof = write(private / "recovery-proof-1.json", proof_value)
    recovery_files["final_proof"] = final_proof
    recovery_files["phase_receipt"] = write(private / "completed-phase.json", {"phase": "completed", "writers_resumed": True,
        "maintenance_held": False, "bindings": {**{key: plan_value[key] for key in
            ("operation_kind", "nonce", "candidate_image", "source_sha", "canonical_sha")},
            "archive_sha256": current_archive["sha256"], "source_inventory_sha256": "5" * 64,
            "source_receipt_sha256": recovery_files["source_receipt"]["sha256"]},
        "final_verification": {"recovery_proof_path": final_proof["path"], "recovery_proof_sha256": final_proof["sha256"],
            "candidate_binding_sha256": digest(recovery._canonical(recovery._native_pair_binding(post)))}})
    wrapper = {"schema": recovery.RECOVERY_PROOF_SCHEMA, "operation_kind": "configuration-only", "operation_nonce": nonce,
        "current": {"source_sha": old_row["source_sha"], "image": old_row["image"], "stage": str(stage)},
        "previous_ledger": previous, "plan": plan, "snapshots": snapshots, "configuration": configuration,
        "recovery_files": recovery_files, "protected_dirs": sorted(set(old["protected_dirs"] + [str(stage)])),
        "archives": {"current": current_archive, "previous": copy.deepcopy(old["archives"]["current"])}, "images": old["images"]}
    pointer = {"schema": recovery.RECOVERY_PROOF_SCHEMA, **write(private / "accepted-recovery.json", wrapper)}
    new_row = {**old_row, "stage": str(stage), "backup": str(current_backup), "previous_image": old_row["image"],
               "receipt": str(stage / "promotion.json"), "compose_override": candidate["path"], "rollback_override": rollback["path"],
               "recovery_proof": pointer}
    write(ledger, new_row)
    write(Path(new_row["receipt"]), {"status": "PASS", "image": new_row["image"],
        "old_ledger_sha256": previous["sha256"], "new_ledger_sha256": digest(ledger.read_bytes()),
        "backup_sha256": current_archive["sha256"]})
    context = recovery._load_accepted_closure(ledger, env["backups"], older_path=Path(older["path"]),
        read_file=env["accepted_read_file"], stat_file=env["accepted_stat_file"])
    value = copy.deepcopy(environment["value"])
    value.update(operation_kind="configuration-only", accepted_caddy_id=context["caddy_id"],
        accepted_native_origin=context["native_origin"], adoption_origin_ledger_sha256=context["adoption_origin_sha256"],
        previous_adoption_origin_ledger_sha256=context["previous_adoption_origin_sha256"],
        ledger_sha256=digest(ledger.read_bytes()), previous_ledger_path=previous["path"], previous_ledger_sha256=previous["sha256"],
        previous_before_ledger_path=older["path"], previous_before_ledger_sha256=older["sha256"],
        live_binding=recovery.recovery_live_binding(context["post_app"]), accepted_promotion_receipts=context["accepted"],
        accepted_recovery_proofs=context["accepted_recovery_proofs"],
        accepted_content_pins=sorted(context["files"].pins.values(), key=lambda row: row["path"]),
        recovery_sets=[{"role": role, "source_sha": old_row["source_sha"], "image": old_row["image"], "stage": target_stage,
            "backup": {**wrapper["archives"][role], "verified": True}} for role, target_stage in [("current", str(stage)), ("previous", old_row["stage"])]])
    value["protected_paths"].extend({"path": name, "kind": "directory"} for name in context["required_directories"])
    value["protected_paths"].extend({"path": row["path"], "kind": "file"} for row in value["accepted_content_pins"])
    write(env["protection"], value)
    env.update(value=value, wrapper=wrapper, proof_pointer=pointer, current=current_backup,
        previous=environment["current"], post_pair=post, post_caddy=caddy_post,
        binding_provider=lambda: copy.deepcopy(value["live_binding"]))
    return env
