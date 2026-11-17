"""Bounded retention of verified runtime archives, with recovery-set protection.

This module never removes directories, images, application state or an unknown
archive format. The caller owns the shared release locks; the CLI acquires them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
from typing import Callable, Any

from app.services.runtime_backup import RuntimeBackupError, verify_backup
from app.services.storage_recovery import StorageRecoveryError, validate_accepted_recovery_proofs

UTC = timezone.utc
ARCHIVE_NAME = re.compile(r"berry-runtime-(\d{8}T\d{6}Z)\.tar\.gz\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z")
HARD_MAX_ARCHIVES = 10
HARD_MAX_BYTES = 5 * 1024**3
MINIMUM_AGE_SECONDS = 72 * 3600
MAX_EXPANDED_ARCHIVE_BYTES = 16 * 1024**3


class RetentionHold(RuntimeError):
    """Fixed operational reason codes; never include private contents."""


def need(value: Any, code: str) -> None:
    if not value:
        raise RetentionHold(code)


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class RetentionPolicy:
    daily: int = 7
    weekly: int = 4
    monthly: int = 3
    minimum_age_seconds: int = MINIMUM_AGE_SECONDS
    maximum_archives_per_run: int = HARD_MAX_ARCHIVES
    maximum_bytes_per_run: int = HARD_MAX_BYTES
    maximum_scan_depth: int = 3
    maximum_scan_entries: int = 100_000

    def __post_init__(self) -> None:
        values = asdict(self)
        need(all(type(value) is int for value in values.values()), "policy_integer_required")
        need(2 <= self.daily <= 366 and 0 <= self.weekly <= 104 and 0 <= self.monthly <= 120,
             "policy_retention_counts_invalid")
        need(self.minimum_age_seconds >= MINIMUM_AGE_SECONDS, "minimum_age_cannot_be_reduced")
        need(1 <= self.maximum_archives_per_run <= HARD_MAX_ARCHIVES, "archive_run_cap_invalid")
        need(1 <= self.maximum_bytes_per_run <= HARD_MAX_BYTES, "byte_run_cap_invalid")
        need(1 <= self.maximum_scan_depth <= 4 and 1 <= self.maximum_scan_entries <= 200_000,
             "scan_bounds_invalid")


def instant(value: datetime | None = None) -> datetime:
    value = value or datetime.now(UTC)
    need(value.tzinfo is not None, "timezone_required")
    return value.astimezone(UTC)


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise RetentionHold("archive_timestamp_invalid") from None
    return instant(parsed)


def safe(path: Path, *, directory: bool = False) -> Path:
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts, "absolute_path_required")
    for node in reversed([path, *path.parents]):
        try:
            info = node.lstat()
        except OSError:
            raise RetentionHold("required_path_unavailable") from None
        need(not stat.S_ISLNK(info.st_mode) and not getattr(node, "is_junction", lambda: False)(),
             "symlink_path_refused")
        wanted = stat.S_ISDIR(info.st_mode) if node != path or directory else stat.S_ISREG(info.st_mode)
        need(wanted, "path_type_invalid")
    return path


def read(path: Path, *, maximum: int = 4 * 1024**2) -> bytes:
    safe(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        need(before.st_size <= maximum, "metadata_size_limit")
        body = handle.read(maximum + 1)
        after = os.fstat(handle.fileno())
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) and len(body) == before.st_size,
             "metadata_changed_while_reading")
    return body


def metadata(path: Path) -> dict[str, int]:
    safe(path)
    info = path.lstat()
    return {"device": info.st_dev, "inode": info.st_ino, "size": info.st_size,
            "mtime_ns": info.st_mtime_ns, "mode": stat.S_IMODE(info.st_mode),
            "uid": getattr(info, "st_uid", 0), "gid": getattr(info, "st_gid", 0), "links": info.st_nlink}


def fingerprint(path: Path, *, single_link: bool = True) -> dict[str, Any]:
    before = metadata(path)
    need(not single_link or before["links"] == 1, "multiply_linked_archive_preserved")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        need((opened.st_dev, opened.st_ino) == (before["device"], before["inode"]), "archive_identity_changed")
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    need(metadata(path) == before, "archive_changed_while_reading")
    return {**before, "sha256": digest.hexdigest()}


def _verified_archive(path: Path, expected_time: datetime | None = None, *, single_link: bool = True,
                      recovery_backup: dict | None = None, accepted_content_pins: list | None = None) -> dict[str, Any]:
    before = fingerprint(path, single_link=single_link)
    try:
        # A tar reader can stop before the gzip footer. Scan headers and then
        # drain the same gzip stream fully, so CRC and duplicate checks take one
        # bounded decompression pass rather than two.
        names = set()
        with gzip.open(path, "rb") as stream:
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                for member in archive:
                    need(member.name not in names, "duplicate_tar_members_preserved")
                    need(str(PurePosixPath(member.name)) == member.name, "noncanonical_tar_path_preserved")
                    names.add(member.name)
                    need(len(names) <= 200_000, "archive_member_limit_preserved")
                    need(member.offset_data + member.size <= MAX_EXPANDED_ARCHIVE_BYTES, "expanded_archive_limit_preserved")
            expanded = stream.tell()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                expanded += len(block)
                need(expanded <= MAX_EXPANDED_ARCHIVE_BYTES, "expanded_archive_limit_preserved")
        manifest = verify_backup(path, maximum_manifest_bytes=16 * 1024**2, maximum_members=100_001)
        need(manifest.get("format_version") == 1 and set(manifest.get("scope", [])) == {"data", "inbox"},
             "unknown_archive_format_preserved")
        created = timestamp(manifest["created_at"])
        entries = manifest["files"]
        need(isinstance(entries, list) and bool(entries), "empty_or_invalid_manifest_preserved")
        names = [entry["path"] for entry in entries]
        need(len(names) == len(set(names)), "duplicate_manifest_paths_preserved")
        need(expected_time is None or created == expected_time, "filename_manifest_time_mismatch")
        if recovery_backup is not None:
            members = {entry["path"]: entry for entry in entries}
            marker_names = ("data/information/store.json", "inbox/.information-store.json")
            need("data/.information-store-transition.json" not in members, "recovery_archive_transition_present")
            schema = recovery_backup.get("store_schema")
            if schema == "legacy":
                need(not any(name in members for name in marker_names), "recovery_archive_store_schema_mismatch")
            elif schema == "unified-v1":
                need(isinstance(accepted_content_pins, list), "accepted_active_store_proof_missing")
                for name in marker_names:
                    relative = PurePosixPath(name)
                    pins = [pin for pin in accepted_content_pins if Path(pin["path"]).name == relative.name
                            and (relative.name != "store.json" or Path(pin["path"]).parent.name == "information")]
                    need(len(pins) == 1 and name in members
                         and members[name].get("sha256") == pins[0]["sha256"], "recovery_archive_store_schema_mismatch")
            else:
                raise RetentionHold("recovery_archive_store_schema_unsupported")
    except RetentionHold:
        raise
    except (OSError, ValueError, KeyError, TypeError, EOFError, RuntimeBackupError, tarfile.TarError):
        raise RetentionHold("invalid_archive_preserved") from None
    # tarfile errors need not be RuntimeBackupError on a truncated gzip stream.
    need(metadata(path) == {key: value for key, value in before.items() if key != "sha256"},
         "archive_changed_during_verification")
    return {"path": str(path), "created_at": created.isoformat(), "fingerprint": before}


def load_protection(path: Path, *, verify_archives: bool = True) -> dict[str, Any]:
    body = read(path)
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError):
        raise RetentionHold("protection_manifest_invalid") from None
    need(isinstance(value, dict) and value.get("version") == 1, "protection_version_invalid")
    need(bool(DIGEST.fullmatch(str(value.get("ledger_sha256", "")))), "protection_ledger_pin_invalid")
    sets = value.get("recovery_sets")
    need(isinstance(sets, list) and len(sets) == 2 and {row.get("role") for row in sets} == {"current", "previous"},
         "two_recovery_sets_required")
    protected = list(value.get("protected_paths") or [])
    backup_root = safe(Path(value["backup_root"]), directory=True)
    backup_paths = []
    verified = []
    for row in sets:
        need(isinstance(row.get("source_sha"), str) and bool(re.fullmatch(r"[a-f0-9]{40}", row["source_sha"]))
             and bool(IMAGE.fullmatch(str(row.get("image", "")))), "recovery_identity_invalid")
        stage = safe(Path(row["stage"]), directory=True)
        protected.append({"path": str(stage), "kind": "directory"})
        backup = row.get("backup") or {}
        need(backup.get("verified") is True and type(backup.get("size")) is int and backup["size"] > 0
             and bool(DIGEST.fullmatch(str(backup.get("sha256", "")))), "verified_recovery_backup_required")
        archive = safe(Path(backup["path"]))
        need(archive.is_relative_to(backup_root) and archive.parent != backup_root,
             "root_level_recovery_backup_unsupported")
        if verify_archives:
            checked = _verified_archive(archive, single_link=False, recovery_backup=backup,
                                        accepted_content_pins=value.get("accepted_content_pins"))
            need(checked["fingerprint"]["size"] == backup["size"], "recovery_backup_size_changed")
            need(checked["fingerprint"]["sha256"] == backup["sha256"], "recovery_backup_hash_changed")
            verified.append(checked)
        else:
            need(metadata(archive)["size"] == backup["size"], "recovery_backup_size_changed")
        protected.append({"path": str(archive), "kind": "file"})
        backup_paths.append(str(archive))
    need(len(set(backup_paths)) == 2, "distinct_recovery_backups_required")
    live = value.get("live_binding")
    need(isinstance(live, dict) and set(live) == {"app_id", "image", "source_sha", "mount_fingerprint", "compose_fingerprint", "config_fingerprint", "healthy", "copilot"},
         "live_recovery_binding_required")
    need(bool(DIGEST.fullmatch(str(live.get("app_id", ""))))
         and bool(DIGEST.fullmatch(str(live.get("mount_fingerprint", ""))))
         and bool(DIGEST.fullmatch(str(live.get("compose_fingerprint", ""))))
         and bool(DIGEST.fullmatch(str(live.get("config_fingerprint", ""))))
         and live.get("healthy") is True, "live_recovery_binding_invalid")
    node = live.get("copilot") or {}
    need(set(node) == {"container_id", "image", "healthy", "network_mode", "config_fingerprint"}
         and bool(DIGEST.fullmatch(str(node.get("container_id", ""))))
         and bool(IMAGE.fullmatch(str(node.get("image", "")))) and node.get("healthy") is True
         and bool(DIGEST.fullmatch(str(node.get("config_fingerprint", ""))))
         and node.get("network_mode") == "container:" + live["app_id"], "live_copilot_binding_invalid")
    for item in protected:
        need(isinstance(item, dict) and item.get("kind") in {"file", "directory"}, "protection_path_kind_invalid")
        safe(Path(item["path"]), directory=item["kind"] == "directory")
    current = next(row for row in sets if row["role"] == "current")
    previous = next(row for row in sets if row["role"] == "previous")
    ledger_path = safe(Path(value["ledger_path"]))
    ledger_body = read(ledger_path)
    need(sha(ledger_body) == value["ledger_sha256"], "release_ledger_changed")
    ledger = json.loads(ledger_body)
    previous_ledger_path = safe(Path(value["previous_ledger_path"]))
    need(bool(DIGEST.fullmatch(str(value.get("previous_ledger_sha256", "")))), "previous_ledger_pin_invalid")
    previous_body = read(previous_ledger_path)
    need(sha(previous_body) == value["previous_ledger_sha256"], "previous_release_ledger_changed")
    previous_ledger = json.loads(previous_body)
    older_path = safe(Path(value["previous_before_ledger_path"]))
    older_body = read(older_path)
    need(bool(DIGEST.fullmatch(str(value.get("previous_before_ledger_sha256", ""))))
         and sha(older_body) == value["previous_before_ledger_sha256"], "previous_before_ledger_changed")
    older_ledger = json.loads(older_body)
    need(previous_ledger.get("previous_image") == older_ledger.get("image"), "previous_rollback_image_mismatch")
    for recorded, accepted in [(current, ledger), (previous, previous_ledger)]:
        need((recorded["source_sha"], recorded["image"], recorded["stage"], recorded["backup"]["path"]) ==
             (accepted.get("source_sha"), accepted.get("image"), accepted.get("stage"), accepted.get("backup")),
             "recovery_set_accepted_ledger_mismatch")
    protected.extend([{"path": str(ledger_path), "kind": "file"},
                      {"path": str(previous_ledger_path), "kind": "file"},
                      {"path": str(older_path), "kind": "file"}])
    promotions = value.get("accepted_promotion_receipts")
    need(isinstance(promotions, list) and len(promotions) == 2
         and {row.get("role") for row in promotions} == {"current", "previous"}, "accepted_promotion_proofs_required")
    kind = value.get("operation_kind")
    adoption_origin = value.get("adoption_origin_ledger_sha256")
    previous_adoption_origin = value.get("previous_adoption_origin_ledger_sha256")
    if kind == "recovery-adoption":
        need(isinstance(adoption_origin, str) and bool(DIGEST.fullmatch(adoption_origin)),
             "adoption_origin_ledger_pin_required")
    else:
        need(adoption_origin is None, "unexpected_adoption_origin_ledger_pin")
    if previous_adoption_origin is not None:
        need(kind == "configuration-only" and isinstance(previous_adoption_origin, str)
             and bool(DIGEST.fullmatch(previous_adoption_origin)), "previous_adoption_origin_ledger_pin_invalid")
    # The strict accepted-proof validator below authenticates these two exact
    # metadata-adoption links. Logical previous recovery roles stay unchanged.
    current_before_sha = adoption_origin if kind == "recovery-adoption" else value["previous_ledger_sha256"]
    previous_before_sha = previous_adoption_origin or value["previous_before_ledger_sha256"]
    for proof in promotions:
        role = proof["role"]
        document, recovery, document_sha, before_sha = (
            (ledger, current, value["ledger_sha256"], current_before_sha) if role == "current" else
            (previous_ledger, previous, value["previous_ledger_sha256"], previous_before_sha))
        receipt_path = safe(Path(proof["path"]))
        need(str(receipt_path) == document.get("receipt") and receipt_path.is_relative_to(Path(recovery["stage"])),
             "accepted_promotion_path_mismatch")
        receipt_body = read(receipt_path)
        need(sha(receipt_body) == proof.get("sha256"), "accepted_promotion_receipt_changed")
        receipt = json.loads(receipt_body)
        actual_image = receipt.get("candidate_image", receipt.get("image"))
        need(proof.get("status") == receipt.get("status") == "PASS"
             and proof.get("image") == actual_image == recovery["image"]
             and proof.get("old_ledger_sha256") == receipt.get("old_ledger_sha256") == before_sha,
             "accepted_promotion_binding_mismatch")
        new_sha = receipt.get("new_ledger_sha256")
        need(new_sha == proof.get("new_ledger_sha256") and (new_sha is None or new_sha == document_sha),
             "accepted_promotion_new_ledger_mismatch")
        need("approved_head" not in receipt or receipt["approved_head"] == recovery["source_sha"],
             "accepted_promotion_source_mismatch")
        need("backup_sha256" not in receipt or receipt["backup_sha256"] == recovery["backup"]["sha256"],
             "accepted_promotion_backup_hash_mismatch")
        protected.append({"path": str(receipt_path), "kind": "file"})
    images = value.get("protected_images")
    provenance = value.get("protected_image_provenance")
    need(isinstance(images, list) and isinstance(provenance, list)
         and len(set(images)) == len(images) == len(provenance)
         and {row.get("image") for row in provenance} == set(images), "protected_image_proof_inventory_mismatch")
    sources = {}
    for proof in provenance:
        need(bool(IMAGE.fullmatch(str(proof.get("image", ""))))
             and bool(re.fullmatch(r"[a-f0-9]{40}", str(proof.get("source_sha", ""))))
             and proof.get("exists") is True and proof.get("provenance_verified") is True,
             "protected_image_provenance_invalid")
        sources[proof["image"]] = proof["source_sha"]
    need({current["image"], previous["image"], older_ledger["image"], node["image"]}.issubset(sources)
         and all(sources.get(document["image"]) == document["source_sha"] for document in [current, previous, older_ledger]),
         "protected_recovery_image_source_mismatch")
    need(ledger.get("image") == current["image"] and ledger.get("source_sha") == current["source_sha"]
         and ledger.get("previous_image") == previous["image"]
         and live.get("image") == current["image"] and live.get("source_sha") == current["source_sha"],
         "recovery_ledger_identity_mismatch")
    _accepted_proof(value)
    # These content seals originate in the accepted ledger's immutable proof,
    # rather than a new fingerprint of whatever configuration exists today.
    protected.extend({"path": row["path"], "kind": "file"} for row in value["accepted_content_pins"])
    return {"path": str(path), "sha256": sha(body), "value": value, "protected_paths": protected,
            "current": current, "previous": previous, "verified_backups": verified}


def _accepted_proof(value: dict) -> None:
    try:
        validate_accepted_recovery_proofs(value)
    except StorageRecoveryError as error:
        raise RetentionHold(str(error)) from None


def _binding(protection: dict, provider: Callable[[], dict] | None) -> None:
    if provider is None:
        return
    live = provider()
    need(live == protection["value"]["live_binding"], "running_release_identity_mismatch")


def _protected(path: Path, protection: dict) -> bool:
    return any(path == Path(item["path"]) or
               (item["kind"] == "directory" and path.is_relative_to(Path(item["path"])))
               for item in protection["protected_paths"])


def _roots(roots: list[Path]) -> list[Path]:
    result = sorted({safe(Path(root), directory=True) for root in roots}, key=str)
    need(bool(result), "archive_roots_required")
    need(all(root != Path(root.anchor) for root in result), "filesystem_root_refused")
    need(not any(first != second and first.is_relative_to(second) for first in result for second in result),
         "overlapping_archive_roots_refused")
    return result


def _inventory(roots: list[Path], protection: dict, policy: RetentionPolicy, now: datetime) -> tuple[list[dict], list[dict]]:
    archives, held = [], []
    scanned = 0
    for root in roots:
        for parent, directories, names in os.walk(root, followlinks=False):
            parent = Path(parent)
            depth = len(parent.relative_to(root).parts)
            allowed = []
            for name in sorted(directories):
                folder = parent / name
                scanned += 1
                if folder.is_symlink() or getattr(folder, "is_junction", lambda: False)():
                    held.append({"path": str(folder), "reason": "symlink_directory_preserved"})
                elif depth + 1 < policy.maximum_scan_depth and not _protected(folder, protection):
                    allowed.append(name)
            directories[:] = allowed
            need(scanned <= policy.maximum_scan_entries, "scan_entry_limit_hold")
            for name in sorted(names):
                scanned += 1
                need(scanned <= policy.maximum_scan_entries, "scan_entry_limit_hold")
                if not name.endswith(".tar.gz"):
                    continue
                path = parent / name
                if parent == root:
                    held.append({"path": str(path), "reason": "root_daily_rotation_preserved"})
                    continue
                match = ARCHIVE_NAME.fullmatch(name)
                if not match:
                    held.append({"path": str(path), "reason": "unmanaged_archive_name_preserved"})
                    continue
                try:
                    info = metadata(path)
                    need(info["links"] == 1, "multiply_linked_archive_preserved")
                    created = datetime.strptime(match[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
                    need(created <= now + timedelta(minutes=5), "future_archive_preserved")
                    archives.append({"path": str(path), "created_at": created.isoformat(), "size": info["size"],
                                     "mtime_ns": info["mtime_ns"]})
                except (OSError, ValueError, RetentionHold) as error:
                    held.append({"path": str(path), "reason": str(error) if isinstance(error, RetentionHold) else "archive_inventory_unavailable"})
    return archives, held


def _sidecar(path: Path, archive_sha: str) -> dict | None:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists() and not sidecar.is_symlink():
        return None
    body = read(sidecar, maximum=1024)
    need(body.decode("ascii").strip() == archive_sha + "  " + path.name, "invalid_checksum_sidecar_preserved")
    return {"path": str(sidecar), "fingerprint": fingerprint(sidecar)}


def create_plan(archive_roots: list[Path], protection_manifest: Path, *, policy: RetentionPolicy | None = None,
                now: datetime | None = None, binding_provider: Callable[[], dict] | None = None) -> dict:
    policy = policy or RetentionPolicy()
    current_time = instant(now)
    protection = load_protection(protection_manifest)
    _binding(protection, binding_provider)
    roots = _roots(archive_roots)
    backup_paths = {row["path"] for row in protection["verified_backups"]}
    protected_file_pins = [{"path": name, "fingerprint": fingerprint(Path(name), single_link=False)}
                           for name in sorted({item["path"] for item in protection["protected_paths"]
                                               if item["kind"] == "file" and item["path"] not in backup_paths})]
    archives, held = _inventory(roots, protection, policy, current_time)
    inspected = {row["path"]: row for row in protection["verified_backups"]}
    invalid: set[str] = set()
    keep: dict[str, set[str]] = {}

    def check(row: dict) -> dict | None:
        name = row["path"]
        if name in invalid:
            return None
        if name in inspected:
            return inspected[name]
        try:
            result = _verified_archive(Path(name), timestamp(row["created_at"]))
        except Exception as error:
            # Unknown or corrupt archives are retained, never used as a valid tier representative.
            invalid.add(name)
            held.append({"path": name, "reason": str(error) if isinstance(error, RetentionHold) else "invalid_archive_preserved"})
            return None
        inspected[name] = result
        return result

    ordered = sorted(archives, key=lambda row: (row["created_at"], row["path"]), reverse=True)
    for kind, count in [("daily", policy.daily), ("weekly", policy.weekly), ("monthly", policy.monthly)]:
        selected = set()
        for row in ordered:
            created = timestamp(row["created_at"])
            key = created.date().isoformat() if kind == "daily" else created.strftime("%G-W%V") if kind == "weekly" else created.strftime("%Y-%m")
            if key in selected or len(selected) >= count:
                continue
            if check(row) is not None:
                selected.add(key)
                keep.setdefault(row["path"], set()).add(kind)
    retained = [{**row, "reasons": sorted({"protected_recovery_backup"} | keep.get(row["path"], set()))}
                for row in protection["verified_backups"]]
    candidates, deferred = [], []
    total = 0
    for row in reversed(ordered):
        path = Path(row["path"])
        reasons = keep.get(row["path"], set()).copy()
        if _protected(path, protection):
            reasons.add("protected_dependency")
        if (current_time - timestamp(row["created_at"])).total_seconds() < policy.minimum_age_seconds:
            reasons.add("minimum_age")
        modified = datetime.fromtimestamp(row["mtime_ns"] / 1_000_000_000, UTC)
        if (current_time - modified).total_seconds() < policy.minimum_age_seconds:
            reasons.add("filesystem_minimum_age")
        if reasons:
            if row["path"] not in {r["path"] for r in retained}:
                retained.append({**row, "reasons": sorted(reasons)})
            continue
        if row["path"] in invalid:
            continue
        if len(candidates) >= policy.maximum_archives_per_run or total + row["size"] > policy.maximum_bytes_per_run:
            deferred.append({**row, "reason": "per_run_limit"})
            continue
        checked = check(row)
        if checked is None:
            continue
        try:
            sidecar = _sidecar(path, checked["fingerprint"]["sha256"])
        except Exception:
            held.append({"path": str(path), "reason": "invalid_checksum_sidecar_preserved"})
            continue
        candidates.append({**checked, "checksum_sidecar": sidecar})
        total += checked["fingerprint"]["size"]
    _accepted_proof(protection["value"])
    _binding(protection, binding_provider)
    need(sha(read(Path(protection["value"]["ledger_path"]))) == protection["value"]["ledger_sha256"], "release_ledger_changed")
    return {"version": 1, "state": "planned", "created_at": current_time.isoformat(), "policy": asdict(policy),
            "archive_roots": [str(root) for root in roots], "protection_manifest": str(protection_manifest),
            "protection_manifest_sha256": protection["sha256"], "ledger_path": protection["value"]["ledger_path"],
            "ledger_sha256": protection["value"]["ledger_sha256"], "recovery_sets_verified": True,
            "accepted_content_pins": protection["value"]["accepted_content_pins"],
            "protected_backup_pins": protection["verified_backups"], "protected_file_pins": protected_file_pins, "retained": retained,
            "candidates": candidates, "candidate_bytes": total, "deferred": deferred, "held": held}


def _same_fingerprint(path: Path, expected: dict) -> None:
    need(fingerprint(path) == expected, "planned_archive_changed")


def _unlink_pinned(path: Path, expected: dict) -> None:
    _same_fingerprint(path, expected)
    # Final directory/file identity check immediately before exact unlink.
    before = metadata(path)
    need(before == {key: value for key, value in expected.items() if key != "sha256"}, "planned_archive_changed")
    if os.name == "nt":
        path.unlink()
    else:
        parent_before = path.parent.stat()
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            parent_opened = os.fstat(descriptor)
            need((parent_opened.st_dev, parent_opened.st_ino) == (parent_before.st_dev, parent_before.st_ino),
                 "archive_parent_identity_changed")
            current = os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)
            need(stat.S_ISREG(current.st_mode) and current.st_nlink == 1
                 and (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) ==
                     (expected["device"], expected["inode"], expected["size"], expected["mtime_ns"]),
                 "planned_archive_changed")
            os.unlink(path.name, dir_fd=descriptor)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def archive_open_file(path: Path, *, strict: bool = True) -> bool:
    """Instantaneous Linux guard for transfers/restores not using release locks."""
    if not sys_platform_linux():
        return False
    wanted = metadata(path)
    try:
        processes = list(Path("/proc").iterdir())
    except OSError:
        raise RetentionHold("open_file_scan_unavailable") from None
    count = 0
    for process in processes:
        if not process.name.isdecimal():
            continue
        try:
            descriptors = list((process / "fd").iterdir())
        except FileNotFoundError:
            continue
        except OSError:
            if strict:
                raise RetentionHold("open_file_scan_unavailable") from None
            continue
        for descriptor in descriptors:
            count += 1
            need(count <= 100_000, "open_file_scan_limit")
            try:
                info = descriptor.stat()
            except FileNotFoundError:
                continue
            except OSError:
                if strict:
                    raise RetentionHold("open_file_scan_unavailable") from None
                continue
            if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == (wanted["device"], wanted["inode"]):
                return True
    return False


def sys_platform_linux() -> bool:
    import sys
    return sys.platform.startswith("linux")


def apply_plan(plan_bytes: bytes, expected_sha256: str, *, binding_provider: Callable[[], dict],
               now: datetime | None = None, event_callback: Callable[[dict], None] | None = None,
               open_file_guard: Callable[[Path], bool] | None = None) -> dict:
    need(bool(DIGEST.fullmatch(expected_sha256)) and sha(plan_bytes) == expected_sha256, "plan_sha256_mismatch")
    plan = json.loads(plan_bytes)
    need(plan.get("version") == 1 and plan.get("state") == "planned" and plan.get("recovery_sets_verified") is True,
         "plan_shape_invalid")
    policy = RetentionPolicy(**plan["policy"])
    current_time = instant(now)
    need(timedelta(0) <= current_time - timestamp(plan["created_at"]) <= timedelta(hours=2), "plan_expired")
    protection_path = Path(plan["protection_manifest"])
    need(sha(read(protection_path)) == plan["protection_manifest_sha256"], "protection_manifest_changed")
    protection = load_protection(protection_path)
    need(protection["value"]["ledger_path"] == plan["ledger_path"]
         and protection["value"]["ledger_sha256"] == plan["ledger_sha256"], "plan_recovery_binding_mismatch")
    need(plan.get("accepted_content_pins") == protection["value"]["accepted_content_pins"],
         "plan_accepted_content_pins_mismatch")
    _binding(protection, binding_provider)
    expected_file_names = {item["path"] for item in protection["protected_paths"] if item["kind"] == "file"} - {
        row["path"] for row in protection["verified_backups"]}
    file_pins = plan.get("protected_file_pins")
    need(isinstance(file_pins, list) and {row["path"] for row in file_pins} == expected_file_names,
         "protected_file_pin_inventory_mismatch")
    for row in file_pins:
        need(fingerprint(Path(row["path"]), single_link=False) == row["fingerprint"], "protected_dependency_changed")
    roots = _roots([Path(value) for value in plan["archive_roots"]])
    candidates = plan["candidates"]
    need(isinstance(candidates, list) and len(candidates) <= policy.maximum_archives_per_run
         and len({row["path"] for row in candidates}) == len(candidates), "candidate_count_invalid")
    need(sum(row["fingerprint"]["size"] for row in candidates) <= policy.maximum_bytes_per_run,
         "candidate_bytes_invalid")
    for row in candidates:
        path = Path(row["path"])
        need(any(path.is_relative_to(root) for root in roots) and not _protected(path, protection), "candidate_is_protected_or_outside_root")
        need(all(path.parent != root for root in roots), "root_daily_archive_candidate_refused")
        match = ARCHIVE_NAME.fullmatch(path.name)
        need(match is not None, "unmanaged_candidate_name")
        created = datetime.strptime(match[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        need(created == timestamp(row["created_at"]) and
             (current_time - created).total_seconds() >= policy.minimum_age_seconds, "candidate_too_recent")
        modified = datetime.fromtimestamp(row["fingerprint"]["mtime_ns"] / 1_000_000_000, UTC)
        need((current_time - modified).total_seconds() >= policy.minimum_age_seconds,
             "candidate_filesystem_age_too_recent")
    retired, held = [], []
    for row in candidates:
        path = Path(row["path"])
        try:
            need(sha(read(protection_path)) == plan["protection_manifest_sha256"], "protection_manifest_changed")
            need(sha(read(Path(plan["ledger_path"]))) == plan["ledger_sha256"], "release_ledger_changed")
            _binding(protection, binding_provider)
            for dependency in file_pins:
                need(fingerprint(Path(dependency["path"]), single_link=False) == dependency["fingerprint"],
                     "protected_dependency_changed")
            for backup in protection["verified_backups"]:
                need(metadata(Path(backup["path"])) == {key: value for key, value in backup["fingerprint"].items() if key != "sha256"},
                     "recovery_backup_changed")
            _same_fingerprint(path, row["fingerprint"])
            checked = _verified_archive(path, timestamp(row["created_at"]))
            need(checked["fingerprint"] == row["fingerprint"], "planned_archive_changed")
            sidecar = row.get("checksum_sidecar")
            if sidecar:
                need(Path(sidecar["path"]) == path.with_suffix(path.suffix + ".sha256"), "sidecar_path_invalid")
                _same_fingerprint(Path(sidecar["path"]), sidecar["fingerprint"])
            need(open_file_guard is None or not open_file_guard(path), "archive_in_use_preserved")
            _accepted_proof(protection["value"])
            _binding(protection, binding_provider)
            if event_callback:
                event_callback({"event": "retirement_intent", "path": str(path), "sha256": row["fingerprint"]["sha256"]})
            _unlink_pinned(path, row["fingerprint"])
            result = {"path": str(path), "sha256": row["fingerprint"]["sha256"], "bytes": row["fingerprint"]["size"]}
            retired.append(result)
            if event_callback:
                event_callback({"event": "archive_retired", **result})
            if sidecar:
                _accepted_proof(protection["value"])
                _binding(protection, binding_provider)
                _unlink_pinned(Path(sidecar["path"]), sidecar["fingerprint"])
        except Exception as error:
            held.append({"path": str(path), "reason": str(error) if isinstance(error, RetentionHold) else "retirement_guard_held"})
            break
    return {"version": 1, "state": "partial" if retired and held else "held" if held else "complete",
            "checked_at": instant(now).isoformat(), "plan_sha256": expected_sha256, "ledger_sha256": plan["ledger_sha256"],
            "recovery_sets_verified": True, "retired": retired, "retired_count": len(retired),
            "retired_bytes": sum(row["bytes"] for row in retired), "held": held,
            "planned_held_count": len(plan["held"]), "deferred_count": len(plan["deferred"])}
