"""Safely synchronize canonical ``data/`` into a persistent runtime.

Startup mode preserves the historical contract: add missing canonical files,
merge missing Source ids, and replace explicitly authoritative operational
configuration. Existing trusted records are never changed at startup.

Explicit promotion adds a three-way comparison for one-record JSON stores:
last promoted canonical content vs current canonical content vs live runtime
content. Only a proven, unchanged runtime base may receive a canonical update.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from app.services.runtime_backup import verify_backup
from scripts.sync_source_config import sync_source_config

SOURCES_RELATIVE_PATH = Path("configuration") / "sources.json"
AUTHORITATIVE_CONFIG_PATHS = {
    Path("configuration") / "collection_pipelines.json",
    Path("configuration") / "source_collection_cadence.json",
    Path("configuration") / "source_universe.json",
}
PROMOTABLE_ROOTS = {
    "assessments",
    "entities",
    "evidence",
    "facts",
    "recommendations",
    "relationships",
    "signals",
    "strategic-questions",
}
MANIFEST_FILENAME = ".canonical-promotion-manifest.json"
TRANSACTION_FILENAME = ".canonical-promotion-transaction.json"
MANIFEST_FORMAT_VERSION = 1
PROMOTION_STATES = ("NEW", "UNCHANGED", "SAFE_CANONICAL_UPDATE", "RUNTIME_DIVERGED", "CONFLICT")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _raw_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def canonical_json_bytes(path: Path) -> bytes:
    """Return semantic JSON bytes; formatting, key order and CRLF/LF vanish."""

    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _semantic_hash(path: Path) -> str:
    content = canonical_json_bytes(path) if path.suffix.casefold() == ".json" else path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def _record_id(path: Path) -> str | None:
    if path.suffix.casefold() != ".json":
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return str(payload.get("id")) if isinstance(payload, dict) and payload.get("id") else None


def _is_promotable(relative: Path) -> bool:
    return relative.suffix.casefold() == ".json" and bool(relative.parts) and relative.parts[0] in PROMOTABLE_ROOTS


def _manifest_path(runtime_data_dir: Path) -> Path:
    return runtime_data_dir / MANIFEST_FILENAME


def _transaction_path(runtime_data_dir: Path) -> Path:
    return runtime_data_dir / TRANSACTION_FILENAME


def _load_manifest(runtime_data_dir: Path) -> dict[str, Any]:
    path = _manifest_path(runtime_data_dir)
    if not path.is_file():
        return {"format_version": MANIFEST_FORMAT_VERSION, "records": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format_version") != MANIFEST_FORMAT_VERSION or not isinstance(payload.get("records"), dict):
        raise ValueError(f"unsupported canonical promotion manifest: {path}")
    return payload


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            Path(temporary).unlink(missing_ok=True)
        finally:
            raise


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write(path, (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))


def _snapshot(seed_file: Path, runtime_file: Path, *, canonical_sha: str, promoted_at: str) -> dict[str, Any]:
    return {
        "canonical_sha": canonical_sha,
        "canonical_raw_sha256": _raw_hash(seed_file),
        "semantic_sha256": _semantic_hash(seed_file),
        "runtime_raw_sha256_at_promotion": _raw_hash(runtime_file),
        "promoted_at": promoted_at,
    }


def _source_plan(seed_path: Path, runtime_path: Path) -> dict[str, Any]:
    if not seed_path.is_file():
        return {"new_ids": [], "runtime_only_ids": [], "existing_ids": 0, "skipped_missing_seed": True}
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.is_file() else []
    if not isinstance(seed, list) or not isinstance(runtime, list):
        raise ValueError("sources.json must be a JSON array")
    seed_ids = {str(row.get("id")) for row in seed if isinstance(row, dict) and row.get("id")}
    runtime_ids = {str(row.get("id")) for row in runtime if isinstance(row, dict) and row.get("id")}
    return {
        "new_ids": sorted(seed_ids - runtime_ids),
        "runtime_only_ids": sorted(runtime_ids - seed_ids),
        "existing_ids": len(seed_ids & runtime_ids),
        "skipped_missing_seed": False,
        "policy": "additive_by_source_id; existing ids are never overwritten",
    }


def plan_trusted_data_sync(
    seed_data_dir: Path,
    runtime_data_dir: Path,
    *,
    canonical_sha: str = "unknown",
) -> dict[str, Any]:
    if not seed_data_dir.is_dir():
        return {"skipped_missing_seed": True, "records": [], "counts": {state: 0 for state in PROMOTION_STATES}}
    manifest = _load_manifest(runtime_data_dir)
    baseline = manifest["records"]
    records: list[dict[str, Any]] = []
    authoritative_updates: list[str] = []
    seed_relatives: set[str] = set()
    for seed_file in sorted(path for path in seed_data_dir.rglob("*") if path.is_file()):
        relative = seed_file.relative_to(seed_data_dir)
        relative_text = relative.as_posix()
        seed_relatives.add(relative_text)
        if relative == SOURCES_RELATIVE_PATH:
            continue
        runtime_file = runtime_data_dir / relative
        if relative in AUTHORITATIVE_CONFIG_PATHS:
            if not runtime_file.is_file() or _raw_hash(seed_file) != _raw_hash(runtime_file):
                authoritative_updates.append(relative_text)
            continue
        canonical_raw = _raw_hash(seed_file)
        canonical_semantic = _semantic_hash(seed_file)
        row: dict[str, Any] = {
            "path": relative_text,
            "record_id": _record_id(seed_file),
            "canonical_raw_sha256": canonical_raw,
            "canonical_semantic_sha256": canonical_semantic,
            "last_promoted_canonical_raw_sha256": (baseline.get(relative_text) or {}).get(
                "canonical_raw_sha256"
            ),
            "last_promoted_semantic_sha256": (baseline.get(relative_text) or {}).get("semantic_sha256"),
            "last_promoted_runtime_raw_sha256": (baseline.get(relative_text) or {}).get(
                "runtime_raw_sha256_at_promotion"
            ),
            "runtime_raw_sha256": None,
            "runtime_semantic_sha256": None,
            "state": "NEW",
            "reason": "canonical file is absent from runtime",
            "promotable": _is_promotable(relative),
        }
        if runtime_file.is_file():
            runtime_raw = _raw_hash(runtime_file)
            runtime_semantic = _semantic_hash(runtime_file)
            prior = row["last_promoted_semantic_sha256"]
            row["runtime_raw_sha256"] = runtime_raw
            row["runtime_semantic_sha256"] = runtime_semantic
            if canonical_semantic == runtime_semantic:
                row["state"] = "UNCHANGED"
                row["reason"] = "canonical and runtime content are semantically equal"
            elif not row["promotable"]:
                row["state"] = "RUNTIME_DIVERGED"
                row["reason"] = "existing non-promotable seed/reference content is never overwritten"
            elif not prior:
                row["state"] = "CONFLICT"
                row["reason"] = "existing differing record has no last-promoted baseline"
            elif runtime_semantic == prior and canonical_semantic != prior:
                row["state"] = "SAFE_CANONICAL_UPDATE"
                row["reason"] = "runtime still matches the last promoted canonical content"
            elif canonical_semantic == prior and runtime_semantic != prior:
                row["state"] = "RUNTIME_DIVERGED"
                row["reason"] = "runtime changed while canonical stayed at the promoted base"
            else:
                row["state"] = "CONFLICT"
                row["reason"] = "canonical and runtime both differ from the promoted base"
        records.append(row)
    runtime_only: list[str] = []
    if runtime_data_dir.is_dir():
        ignored = {MANIFEST_FILENAME, TRANSACTION_FILENAME}
        for runtime_file in sorted(path for path in runtime_data_dir.rglob("*") if path.is_file()):
            relative_text = runtime_file.relative_to(runtime_data_dir).as_posix()
            if relative_text not in seed_relatives and Path(relative_text).name not in ignored:
                runtime_only.append(relative_text)
    counts = {state: sum(row["state"] == state for row in records) for state in PROMOTION_STATES}
    return {
        "skipped_missing_seed": False,
        "mode": "dry-run",
        "canonical_sha": canonical_sha,
        "generated_at": _utc_now(),
        "manifest": str(_manifest_path(runtime_data_dir)),
        "incomplete_transaction": _transaction_path(runtime_data_dir).is_file(),
        "counts": counts,
        "records": records,
        "sources": _source_plan(seed_data_dir / SOURCES_RELATIVE_PATH, runtime_data_dir / SOURCES_RELATIVE_PATH),
        "authoritative_config_updates": sorted(authoritative_updates),
        "runtime_only_count": len(runtime_only),
        "runtime_only_paths": runtime_only,
        "ownership": {
            "promotable_roots": sorted(PROMOTABLE_ROOTS),
            "sources": "additive_by_id",
            "authoritative_configuration": sorted(path.as_posix() for path in AUTHORITATIVE_CONFIG_PATHS),
            "runtime_only": "never copied back to canonical and never overwritten",
        },
    }


def _update_equal_baselines(
    seed_data_dir: Path,
    runtime_data_dir: Path,
    manifest: dict[str, Any],
    *,
    canonical_sha: str,
) -> list[str]:
    initialized: list[str] = []
    now = _utc_now()
    for seed_file in sorted(path for path in seed_data_dir.rglob("*.json") if path.is_file()):
        relative = seed_file.relative_to(seed_data_dir)
        if not _is_promotable(relative):
            continue
        runtime_file = runtime_data_dir / relative
        if runtime_file.is_file() and _semantic_hash(seed_file) == _semantic_hash(runtime_file):
            relative_text = relative.as_posix()
            existing = manifest["records"].get(relative_text)
            snapshot = _snapshot(
                seed_file,
                runtime_file,
                canonical_sha=canonical_sha,
                promoted_at=(existing or {}).get("promoted_at", now),
            )
            if existing != snapshot:
                manifest["records"][relative_text] = snapshot
                initialized.append(relative_text)
    return initialized


def startup_sync_trusted_data(
    seed_data_dir: Path,
    runtime_data_dir: Path,
    *,
    canonical_sha: str = "unknown",
) -> dict[str, Any]:
    """Add new seed files/config only and establish equal-content baselines."""

    if not seed_data_dir.is_dir():
        return {"skipped_missing_seed": True, "sources": None, "files_added": [], "files_updated": []}
    plan = plan_trusted_data_sync(seed_data_dir, runtime_data_dir, canonical_sha=canonical_sha)
    source_result = sync_source_config(
        seed_data_dir / SOURCES_RELATIVE_PATH, runtime_data_dir / SOURCES_RELATIVE_PATH
    )
    files_added: list[str] = []
    files_updated: list[str] = []
    for row in plan["records"]:
        if row["state"] != "NEW":
            continue
        relative = Path(row["path"])
        _atomic_write(runtime_data_dir / relative, (seed_data_dir / relative).read_bytes())
        files_added.append(row["path"])
    for relative_text in plan["authoritative_config_updates"]:
        relative = Path(relative_text)
        _atomic_write(runtime_data_dir / relative, (seed_data_dir / relative).read_bytes())
        files_updated.append(relative_text)
    manifest = _load_manifest(runtime_data_dir)
    initialized = _update_equal_baselines(
        seed_data_dir, runtime_data_dir, manifest, canonical_sha=canonical_sha
    )
    if initialized or not _manifest_path(runtime_data_dir).is_file():
        manifest.update({"updated_at": _utc_now(), "canonical_sha": canonical_sha})
        _write_json_atomic(_manifest_path(runtime_data_dir), manifest)
    return {
        **plan,
        "mode": "startup-sync",
        "sources": source_result,
        "files_added": sorted(files_added),
        "files_updated": sorted(files_updated),
        "baseline_initialized": sorted(initialized),
    }


def _verify_backup_gate(archive: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = verify_backup(archive)
    if "data" not in manifest.get("scope", []):
        raise ValueError("verified backup does not include data scope")
    files = {entry["path"]: entry for entry in manifest.get("files", [])}
    for row in rows:
        backup_path = f"data/{row['path']}"
        entry = files.get(backup_path)
        if entry is None:
            raise ValueError(f"verified backup is missing promotion target: {backup_path}")
        if entry.get("sha256") != row.get("runtime_raw_sha256"):
            raise ValueError(f"verified backup does not match current runtime bytes: {backup_path}")
    return {
        "archive": str(archive),
        "created_at": manifest.get("created_at"),
        "verified_targets": len(rows),
    }


def apply_safe_canonical_updates(
    seed_data_dir: Path,
    runtime_data_dir: Path,
    *,
    verified_backup: Path,
    canonical_sha: str,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    """Atomically apply only SAFE_CANONICAL_UPDATE rows, backup-gated."""

    if not canonical_sha or canonical_sha == "unknown":
        raise ValueError("--canonical-sha is required for promotion")
    transaction = _transaction_path(runtime_data_dir)
    if transaction.exists():
        raise RuntimeError(f"incomplete prior promotion requires reconciliation: {transaction}")
    plan = plan_trusted_data_sync(seed_data_dir, runtime_data_dir, canonical_sha=canonical_sha)
    rows = [row for row in plan["records"] if row["state"] == "SAFE_CANONICAL_UPDATE"]
    backup = _verify_backup_gate(verified_backup, rows)
    manifest = _load_manifest(runtime_data_dir)
    original_manifest = json.loads(json.dumps(manifest))
    now = _utc_now()
    transaction_payload = {
        "state": "applying",
        "started_at": now,
        "canonical_sha": canonical_sha,
        "verified_backup": str(verified_backup),
        "paths": [row["path"] for row in rows],
    }
    _write_json_atomic(transaction, transaction_payload)
    staging = Path(tempfile.mkdtemp(prefix=".canonical-promotion-staging-", dir=runtime_data_dir))
    rollback = Path(tempfile.mkdtemp(prefix=".canonical-promotion-rollback-", dir=runtime_data_dir))
    replaced: list[str] = []
    transaction_complete = False
    report: dict[str, Any] | None = None
    report_path: Path | None = None
    try:
        for row in rows:
            relative = Path(row["path"])
            staged = staging / relative
            previous = rollback / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            previous.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes((seed_data_dir / relative).read_bytes())
            previous.write_bytes((runtime_data_dir / relative).read_bytes())
            canonical_json_bytes(staged)
        for row in rows:
            relative = Path(row["path"])
            os.replace(staging / relative, runtime_data_dir / relative)
            replaced.append(row["path"])
            manifest["records"][row["path"]] = _snapshot(
                seed_data_dir / relative,
                runtime_data_dir / relative,
                canonical_sha=canonical_sha,
                promoted_at=now,
            )
        manifest.update({"updated_at": now, "canonical_sha": canonical_sha})
        _write_json_atomic(_manifest_path(runtime_data_dir), manifest)
        report = {
            **plan,
            "mode": "apply-safe-updates",
            "applied_at": now,
            "backup": backup,
            "files_updated": sorted(replaced),
            "updated_count": len(replaced),
            "conflict_count": plan["counts"]["CONFLICT"],
            "runtime_diverged_count": plan["counts"]["RUNTIME_DIVERGED"],
        }
        destination = report_dir or runtime_data_dir.parent / "inbox" / "operations" / "promotions"
        safe_sha = "".join(ch for ch in canonical_sha if ch.isalnum())[:16] or "unknown"
        report_path = destination / f"promotion-{now.replace(':', '').replace('+00:00', 'Z')}-{safe_sha}.json"
        _write_json_atomic(report_path, report)
        transaction_complete = True
    except Exception:
        rollback_complete = False
        try:
            for relative_text in reversed(replaced):
                relative = Path(relative_text)
                os.replace(rollback / relative, runtime_data_dir / relative)
            if original_manifest["records"] or _manifest_path(runtime_data_dir).is_file():
                _write_json_atomic(_manifest_path(runtime_data_dir), original_manifest)
            rollback_complete = True
        finally:
            if rollback_complete:
                transaction.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(rollback, ignore_errors=True)
        if transaction_complete:
            transaction.unlink(missing_ok=True)
    assert report is not None and report_path is not None
    report["report_path"] = str(report_path)
    return report


def sync_trusted_data(seed_data_dir: Path, runtime_data_dir: Path) -> dict[str, Any]:
    """Backward-compatible startup sync used by existing callers/tests."""

    return startup_sync_trusted_data(seed_data_dir, runtime_data_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=Path, help="Image/canonical seed data/ directory")
    parser.add_argument("--runtime", required=True, type=Path, help="Deployed runtime data/ directory")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Classify only; this is the default")
    modes.add_argument("--startup-sync", action="store_true", help="Add missing seed/config and initialize safe baselines")
    modes.add_argument("--apply-safe-updates", action="store_true", help="Apply only proven safe canonical updates")
    parser.add_argument("--canonical-sha", default=os.environ.get("BIOS_CANONICAL_SHA", "unknown"))
    parser.add_argument("--verified-backup", type=Path)
    parser.add_argument("--report-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.apply_safe_updates:
        if args.verified_backup is None:
            raise SystemExit("--apply-safe-updates requires --verified-backup")
        result = apply_safe_canonical_updates(
            args.seed,
            args.runtime,
            verified_backup=args.verified_backup,
            canonical_sha=args.canonical_sha,
            report_dir=args.report_dir,
        )
    elif args.startup_sync:
        result = startup_sync_trusted_data(
            args.seed, args.runtime, canonical_sha=args.canonical_sha
        )
    else:
        result = plan_trusted_data_sync(
            args.seed, args.runtime, canonical_sha=args.canonical_sha
        )
    if args.startup_sync:
        summary = {
            "mode": result["mode"],
            "canonical_sha": result["canonical_sha"],
            "counts": result["counts"],
            "sources_added": len((result.get("sources") or {}).get("added", [])),
            "files_added": len(result.get("files_added", [])),
            "authoritative_config_updated": result.get("files_updated", []),
            "baselines_initialized": len(result.get("baseline_initialized", [])),
        }
        print(json.dumps(summary, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
