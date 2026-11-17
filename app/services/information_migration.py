"""Offline, resumable consolidation of source-state persistence.

The plan is read-only. Apply requires a stopped web service, takes both the
collector lease and the storage lease, verifies exact backups, stages a full
store, activates it atomically, then retires legacy record payloads. Raw input
variants remain in the verified backup and private store history. Rollback
refuses post-cutover record/asset changes rather than discarding new work.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable

from app.services import information_storage as storage
from app.services.information_catalog import INACTIVE_STATES
from app.services.pipeline_lock import pipeline_lock


class InformationMigrationError(storage.InformationStorageError):
    pass


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if resolved == root.resolve() or root.resolve() not in resolved.parents:
        raise InformationMigrationError(f"Migration path escapes its named root: {path}")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
        raise InformationMigrationError(f"Migration does not follow symbolic links: {path}")
    return resolved


def _files(folder: Path):
    if folder.is_symlink():
        raise InformationMigrationError(f"Legacy directory is a symbolic link: {folder}")
    if folder.exists():
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise InformationMigrationError(f"Legacy source is a symbolic link: {path}")
            if path.is_file():
                yield path


def _identity(row: dict[str, Any]) -> str:
    from app.services.article_dedup import normalize_canonical_url
    value = row.get("source_url") or row.get("url") or ""
    return normalize_canonical_url(str(value)) or str(value)


def _summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: plan[key] for key in ("version", "migration_id", "data_dir", "inbox_dir", "source_fingerprint", "counts", "conflicts")}


def plan_migration(data_dir: Path, inbox_dir: Path) -> dict[str, Any]:
    """Read all legacy variants and build a deterministic, private apply plan."""
    data, inbox = Path(data_dir).resolve(), Path(inbox_dir).resolve()
    if data == inbox:
        raise InformationMigrationError("Data and inbox directories must be distinct")
    if not data.is_dir() or not inbox.is_dir():
        raise InformationMigrationError("Both named runtime roots must already exist")
    if (data / storage.STORE_NAME).exists():
        raise InformationMigrationError("Target information directory already exists; verify/resume its migration")
    if ((inbox / storage.BINDING_NAME).exists() or (data / storage.TRANSITION_NAME).exists()
            or (data / storage.STORE_NAME / storage.MARKER_NAME).exists()):
        raise InformationMigrationError("An information-store binding already exists; verify/resume that migration")
    sources, candidates, replacements, assets, conflicts = [], {}, {}, {}, []

    def add_file(path, root, label, kind, *, retire=False):
        _inside(path, root)
        spec = {"root": label, "relative": path.relative_to(root).as_posix(), "sha256": file_hash(path),
                "size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns,
                "kind": kind, "retire": retire}
        sources.append(spec)
        return spec

    def candidate(row, spec, origin, position=0):
        if not isinstance(row, dict):
            raise InformationMigrationError(f"Malformed source record in {spec['relative']}")
        key = storage.safe_id(row.get("id") or "")
        saved = deepcopy(row)
        candidates.setdefault(key, []).append({"origin": origin, "source": f"{spec['root']}/{spec['relative']}",
            "source_sha256": spec["sha256"], "position": position, "mtime_ns": spec["mtime_ns"],
            "sha256": record_hash(saved), "record": saved})

    for root, label, origin in ((data, "data", "canonical"), (inbox, "inbox", "intake")):
        for path in _files(root / "evidence"):
            if path.suffix.lower() != ".json":
                raise InformationMigrationError(f"Unexpected file in legacy records directory: {path}")
            spec = add_file(path, root, label, "record", retire=True)
            row = storage.read_json(path)
            if row.get("id") != path.stem:
                raise InformationMigrationError(f"Record filename/identity mismatch: {path}")
            candidate(row, spec, origin)
        for path in _files(root / "attachments"):
            spec = add_file(path, root, label, "asset", retire=True)
            relative = path.relative_to(root / "attachments").as_posix()
            if len(Path(relative).parts) < 2:
                raise InformationMigrationError(f"Attachment has no record directory: {path}")
            storage.safe_id(Path(relative).parts[0])
            if relative in assets and assets[relative]["sha256"] != spec["sha256"]:
                conflicts.append({"kind": "asset_identity", "path": relative,
                                  "sources": [assets[relative]["source"], f"{label}/{spec['relative']}"]})
            else:
                assets[relative] = {"source": f"{label}/{spec['relative']}", "sha256": spec["sha256"]}

    caches = list((inbox / "feed_first_live").glob("????-??-??.json"))
    caches += list((inbox / "news_packets" / "captures").glob("packet-*.json"))
    for path in sorted(caches):
        spec = add_file(path, inbox, "inbox", "cache")
        envelope = storage.read_json(path)
        rewritten = deepcopy(envelope)
        for field in ("records", "rotating_records"):
            if field not in envelope:
                continue
            rows = envelope[field]
            if not isinstance(rows, list):
                raise InformationMigrationError(f"Malformed cache record list: {path}")
            ids = []
            for position, row in enumerate(rows):
                candidate(row, spec, "retained", position)
                ids.append(str(row["id"]))
            rewritten.pop(field, None)
            rewritten[field + "_ids"] = ids
        rewritten["information_storage_version"] = storage.VERSION
        replacements[f"inbox/{spec['relative']}"] = rewritten

    # Decision stores are snapshotted for audit and verified unchanged. They
    # stay in place; consolidation never rewrites user reading/review history.
    state_names = ("analyst_queue_state.json", "feed_first_state.json", "analyst_feed_state.json")
    state_paths = [inbox / name for name in state_names if (inbox / name).is_file()]
    for folder in (inbox / "review_events", inbox / "review_state"):
        state_paths.extend(_files(folder))
    seen = {f"{entry['root']}/{entry['relative']}" for entry in sources}
    for path in state_paths:
        if f"inbox/{path.relative_to(inbox).as_posix()}" not in seen:
            add_file(path, inbox, "inbox", "decision")

    reviewed_events = {}
    for spec in sources:
        if spec["kind"] != "decision" or not spec["relative"].startswith("review_events/"):
            continue
        event = storage.read_json(_source({"data_dir": str(data), "inbox_dir": str(inbox)}, spec))
        if (event.get("record_type") != "review_event" or event.get("workflow") not in {"publication_review", "atomic_evidence_review"}
                or not event.get("object_id") or not str(event.get("actor") or "").strip()):
            continue
        try:
            when = datetime.fromisoformat(str(event.get("occurred_at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        when = when.replace(tzinfo=when.tzinfo or UTC).astimezone(UTC)
        prior = reviewed_events.get(event["object_id"])
        if prior is None or (when, str(event.get("id") or "")) > prior[0]:
            reviewed_events[event["object_id"]] = ((when, str(event.get("id") or "")), event)
    selected, history = {}, {}
    rank = {"retained": 0, "intake": 1, "canonical": 2}
    for key, variants in candidates.items():
        identities = {_identity(entry["record"]) for entry in variants if _identity(entry["record"])}
        kinds = {str(entry["record"].get("record_type") or "evidence") for entry in variants}
        roles = {entry["record"]["evidence_role"] for entry in variants if entry["record"].get("evidence_role")}
        if len(identities) > 1 or len(kinds) > 1 or len(roles) > 1:
            conflicts.append({"kind": "record_identity", "id": key,
                              "sources": sorted({entry["source"] for entry in variants})})
        chosen = max(variants, key=lambda entry: (rank[entry["origin"]], entry["mtime_ns"], entry["source"], entry["position"]))
        row = deepcopy(chosen["record"])
        origin = chosen["origin"]
        if origin == "retained":
            if row.get("status") not in INACTIVE_STATES:
                row["status"] = "unreviewed"
            flags = row.get("information") if isinstance(row.get("information"), dict) else {}
            row["information"] = {**flags, "review_status": "unreviewed"}
        elif origin == "intake":
            event = (reviewed_events.get(key) or (None, {}))[1]
            terminal = any(str(row.get(field) or "") in {"rejected", "archived", "withdrawn", "deleted"}
                           for field in ("status", "review_state"))
            reviewed = not terminal and event.get("action") == "publish" and event.get("new_state") == "published"
            if not reviewed and not terminal and (row.get("status") == "published" or row.get("review_state") == "published"):
                row["status"] = "unreviewed"
            flags = row.get("information") if isinstance(row.get("information"), dict) else {}
            row["information"] = {**flags, "review_status": "reviewed" if reviewed else "unreviewed"}
            if reviewed:
                row["status"] = row["review_state"] = "published"
                row["reviewed_by"], row["reviewed_at"] = event["actor"], event["occurred_at"]
        row["publication_scope"] = ("public" if origin == "canonical" and row.get("status") == "published"
                                    and row.get("publication_scope") != "private" else "private")
        selected[key] = storage.prepare_record(row, origin=origin)
        history[key] = variants

    # Attachment routes authorize the owning record. An inbox-only attachment
    # must not gain public access just because a same-ID canonical source is
    # public. Identical path/bytes already present in data retain their existing
    # public authorization; differing same-path bytes are asset_identity conflicts.
    canonical_assets = {spec["relative"].removeprefix("attachments/"): spec["sha256"]
                        for spec in sources if spec["kind"] == "asset" and spec["root"] == "data"}
    for spec in sources:
        if spec["kind"] != "asset" or spec["root"] != "inbox":
            continue
        relative = spec["relative"].removeprefix("attachments/")
        key = Path(relative).parts[0]
        if selected.get(key, {}).get("publication_scope") == "public" and relative not in canonical_assets:
            conflicts.append({"kind": "asset_publication_scope", "id": key, "path": relative,
                              "sources": [f"inbox/{spec['relative']}"]})

    fingerprint = hashlib.sha256(json.dumps({"data": str(data), "inbox": str(inbox), "sources": sources},
                                           sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    migration_id = "information-" + fingerprint[:20]
    for key, row in selected.items():
        row["information_migration"] = {"id": migration_id, "variants": len(history[key])}
    return {"version": storage.VERSION, "migration_id": migration_id, "data_dir": str(data), "inbox_dir": str(inbox),
            "source_fingerprint": fingerprint, "sources": sources, "records": selected, "variants": history,
            "assets": assets, "cache_replacements": replacements, "conflicts": conflicts,
            "counts": {"records": len(selected), "variants": sum(map(len, history.values())),
                       "source_files": len(sources), "assets": len(assets), "cache_envelopes": len(replacements),
                       "public": sum(row["publication_scope"] == "public" for row in selected.values()),
                       "private": sum(row["publication_scope"] == "private" for row in selected.values())}}


def dry_run(data_dir: Path, inbox_dir: Path) -> dict[str, Any]:
    return {"state": "dry_run", **_summary(plan_migration(data_dir, inbox_dir))}


def _source(plan, spec):
    return _inside(Path(plan[spec["root"] + "_dir"]) / spec["relative"], Path(plan[spec["root"] + "_dir"]))


def _backup_location(backup, spec):
    return _inside(backup / "sources" / spec["root"] / spec["relative"], backup)


def _copy_verified(source: Path, target: Path, digest: str) -> None:
    if target.exists():
        if file_hash(target) != digest:
            raise InformationMigrationError(f"Existing backup/staged file differs: {target}")
        return
    if not source.is_file() or file_hash(source) != digest:
        raise InformationMigrationError(f"Source changed or is unavailable: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = __import__("tempfile").mkstemp(prefix=".migration-", dir=target.parent)
    os.close(descriptor)
    try:
        shutil.copy2(source, temporary)
        if file_hash(Path(temporary)) != digest or file_hash(source) != digest:
            raise InformationMigrationError(f"Source changed during backup: {source}")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _journal(backup, plan, state, **extra):
    path = backup / "MANIFEST.json"
    value = storage.read_json(path) if path.exists() else {**_summary(plan), "created_at": datetime.now(UTC).isoformat()}
    value.update(state=state, **extra)
    storage.atomic_json(path, value)
    return value


def _check_backup(plan, backup):
    for spec in plan["sources"]:
        path = _backup_location(backup, spec)
        if not path.is_file() or file_hash(path) != spec["sha256"]:
            raise InformationMigrationError(f"Backup verification failed: {path}")


@contextmanager
def _maintenance(data, inbox, migration_id, operation):
    # Acquire the OS lease first. A crashed process releases it automatically,
    # allowing only this exact migration's stale collector lease to be resumed.
    with storage.storage_lock(data_dir=data, maintenance=True):
        lease = inbox / "operations/collection.lock"
        if lease.exists():
            payload = storage.read_json(lease)
            prefixes = tuple(f"information-{action}-{migration_id}-" for action in ("migration", "rollback"))
            if str(payload.get("run_id") or "").startswith(prefixes):
                lease.unlink()
        with pipeline_lock(inbox, f"information-{operation}-{migration_id}"):
            yield


def _verify_store(plan, root):
    paths = {path.stem: path for path in (root / "records").glob("*.json")}
    if set(paths) != set(plan["records"]):
        raise InformationMigrationError("Information-store ID coverage differs from the migration plan")
    for key, record in plan["records"].items():
        if storage.read_json(paths[key]) != record:
            raise InformationMigrationError(f"Information-store content differs from the plan: {key}")
        for variant in plan["variants"][key]:
            prior = root / "history" / key / (variant["sha256"] + ".json")
            if not prior.is_file() or record_hash(storage.read_json(prior)) != variant["sha256"]:
                raise InformationMigrationError(f"Information-store variant coverage differs: {key}")
    asset_paths = {path.relative_to(root / "assets").as_posix() for path in (root / "assets").rglob("*") if path.is_file()}
    if asset_paths != set(plan["assets"]):
        raise InformationMigrationError("Information-store asset coverage differs from the migration plan")
    for relative, asset in plan["assets"].items():
        path = _inside(root / "assets" / relative, root)
        if not path.is_file() or file_hash(path) != asset["sha256"]:
            raise InformationMigrationError(f"Information-store asset differs from the plan: {relative}")


def apply_migration(data_dir: Path, inbox_dir: Path, backup_dir: Path, *, quiesced: bool = False,
                    resume_id: str | None = None, _fault: Callable[[str], None] | None = None) -> dict[str, Any]:
    if not quiesced:
        raise InformationMigrationError("Stop the web service and acquisition jobs, then pass quiesced=True")
    data, inbox, backups = Path(data_dir).resolve(), Path(inbox_dir).resolve(), Path(backup_dir).resolve()
    if any(backups == root or root in backups.parents for root in (data, inbox)):
        raise InformationMigrationError("Migration backups must be outside both source roots")
    marker = data / storage.STORE_NAME / storage.MARKER_NAME
    transition = data / storage.TRANSITION_NAME
    if resume_id is None and marker.is_file():
        resume_id = storage.read_json(marker).get("migration_id")
    if resume_id is None and transition.is_file():
        resume_id = storage.read_json(transition).get("migration_id")
    if resume_id is not None:
        storage.safe_id(resume_id)
        backup = _inside(backups / resume_id, backups)
        plan = storage.read_json(backup / "PLAN.private.json")
        if plan["data_dir"] != str(data) or plan["inbox_dir"] != str(inbox) or plan["migration_id"] != resume_id:
            raise InformationMigrationError("Resume plan belongs to a different runtime")
    else:
        plan = plan_migration(data, inbox)
        backup = _inside(backups / plan["migration_id"], backups)
    if plan["conflicts"]:
        raise InformationMigrationError("Migration has incompatible record/attachment identities; inspect dry-run conflicts")
    root = data / storage.STORE_NAME
    stage = data / (".information-stage-" + plan["migration_id"])
    _inside(stage, data)
    with _maintenance(data, inbox, plan["migration_id"], "migration"):
        backup.mkdir(parents=True, exist_ok=True)
        saved_plan = backup / "PLAN.private.json"
        if saved_plan.exists():
            if storage.read_json(saved_plan) != plan:
                raise InformationMigrationError("Migration resume plan differs from the saved plan")
        else:
            storage.atomic_json(saved_plan, plan)
        _journal(backup, plan, "backing_up")
        binding = {"version": storage.VERSION, "inbox_dir": str(inbox), "store_root": str(root)}
        storage.atomic_json(inbox / storage.BINDING_NAME, binding)
        storage.atomic_json(transition, {"version": storage.VERSION, "migration_id": plan["migration_id"],
                                       "store_root": str(root), "backup_dir": str(backup)})
        for spec in plan["sources"]:
            _copy_verified(_source(plan, spec), _backup_location(backup, spec), spec["sha256"])
        _check_backup(plan, backup)
        if _fault:
            _fault("backed_up")
        if not root.exists():
            for spec in plan["sources"]:
                source = _source(plan, spec)
                if not source.is_file() or file_hash(source) != spec["sha256"]:
                    raise InformationMigrationError(f"Source changed after the migration plan: {source}")
            (stage / "records").mkdir(parents=True, exist_ok=True)
            for key, record in plan["records"].items():
                storage.atomic_json(stage / "records" / (storage.safe_id(key) + ".json"), record)
                for variant in plan["variants"][key]:
                    storage.atomic_json(stage / "history" / key / (variant["sha256"] + ".json"), variant["record"])
            for relative, asset in plan["assets"].items():
                origin, source_relative = asset["source"].split("/", 1)
                _copy_verified(Path(plan[origin + "_dir"]) / source_relative,
                               _inside(stage / "assets" / relative, stage), asset["sha256"])
            _verify_store(plan, stage)
            _journal(backup, plan, "staged")
            if _fault:
                _fault("staged")
            for spec in plan["sources"]:
                source = _source(plan, spec)
                if not source.is_file() or file_hash(source) != spec["sha256"]:
                    raise InformationMigrationError(f"Source changed before activation: {source}")
            store_marker = {"version": storage.VERSION, "state": "active", "data_dir": str(data),
                            "inbox_dir": str(inbox), "store_root": str(root), "migration_id": plan["migration_id"],
                            "backup_dir": str(backup), "source_fingerprint": plan["source_fingerprint"]}
            storage.atomic_json(stage / storage.MARKER_NAME, store_marker)
            os.replace(stage, root)
        elif not marker.is_file() or storage.read_json(marker).get("migration_id") != plan["migration_id"]:
            raise InformationMigrationError("Target store already exists and is not this migration")
        _verify_store(plan, root)
        _journal(backup, plan, "activated")
        if _fault:
            _fault("activated")
        for spec in plan["sources"]:
            source = _source(plan, spec)
            if spec["retire"]:
                if source.exists():
                    if file_hash(source) != spec["sha256"]:
                        raise InformationMigrationError(f"Legacy writer changed a source during cutover: {source}")
                    source.unlink()
            elif spec["kind"] == "cache":
                replacement = plan["cache_replacements"][f"{spec['root']}/{spec['relative']}"]
                if not source.is_file():
                    raise InformationMigrationError(f"Cache receipt disappeared during cutover: {source}")
                if file_hash(source) != spec["sha256"] and storage.read_json(source) != replacement:
                    raise InformationMigrationError(f"Cache changed during cutover: {source}")
                storage.atomic_json(source, replacement)
            elif spec["kind"] == "decision" and file_hash(source) != spec["sha256"]:
                raise InformationMigrationError(f"Decision state changed while migration was offline: {source}")
        _verify_store(plan, root)
        _check_backup(plan, backup)
        result = _journal(backup, plan, "complete", completed_at=datetime.now(UTC).isoformat())
        transition.unlink(missing_ok=True)
        return result


def rollback_migration(data_dir: Path, inbox_dir: Path, backup: Path, *, quiesced: bool = False) -> dict[str, Any]:
    if not quiesced:
        raise InformationMigrationError("Stop the web service and acquisition jobs before rollback")
    data, inbox, backup = Path(data_dir).resolve(), Path(inbox_dir).resolve(), Path(backup).resolve()
    plan = storage.read_json(backup / "PLAN.private.json")
    if plan["data_dir"] != str(data) or plan["inbox_dir"] != str(inbox):
        raise InformationMigrationError("Rollback backup belongs to a different runtime")
    root = data / storage.STORE_NAME
    stage = data / (".information-stage-" + storage.safe_id(plan["migration_id"]))
    transition = data / storage.TRANSITION_NAME
    archived = data / (".information-rolled-back-" + storage.safe_id(plan["migration_id"]))
    _inside(archived, data)
    with _maintenance(data, inbox, plan["migration_id"], "rollback"):
        _check_backup(plan, backup)
        source_store = None
        if root.exists():
            # No silent loss of new records, edits, removals or replaced assets.
            _verify_store(plan, root)
            source_store = root
        elif stage.is_dir():
            _verify_store(plan, stage)
            source_store = stage
        elif not archived.is_dir() and storage.read_json(backup / "MANIFEST.json").get("state") not in {"backing_up", "staged"}:
            raise InformationMigrationError("No matching information store exists for rollback")
        if transition.exists() and storage.read_json(transition).get("migration_id") != plan["migration_id"]:
            raise InformationMigrationError("Rollback would clear another migration's maintenance guard")
        if source_store is not None and archived.exists():
            raise InformationMigrationError("Rollback archive already exists")
        for spec in plan["sources"]:
            if spec["kind"] == "decision":
                continue  # Preserve newer reading/review decisions in place.
            source = _source(plan, spec)
            if source.exists():
                allowed = file_hash(source) == spec["sha256"]
                if spec["kind"] == "cache":
                    allowed = allowed or storage.read_json(source) == plan["cache_replacements"][f"{spec['root']}/{spec['relative']}"]
                if not allowed:
                    raise InformationMigrationError(f"Rollback would overwrite later legacy work: {source}")
            temporary = source.with_name(".restore-" + source.name)
            _copy_verified(_backup_location(backup, spec), temporary, spec["sha256"])
            os.replace(temporary, source)
        binding = inbox / storage.BINDING_NAME
        if binding.exists():
            value = storage.read_json(binding)
            if value.get("store_root") != str(root):
                raise InformationMigrationError("Rollback would remove another store binding")
            binding.unlink()
        if source_store is not None:
            os.replace(source_store, archived)
        transition.unlink(missing_ok=True)
        return _journal(backup, plan, "rolled_back", rollback_at=datetime.now(UTC).isoformat(), store_archive=str(archived))
