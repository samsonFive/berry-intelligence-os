"""Operator-safe backup and restore for mutable Berry Intelligence runtime state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any, Iterable


BACKUP_FORMAT_VERSION = 1
MUTABLE_ROOTS = ("data", "inbox")
EXCLUDED_NAMES = {".env", ".env.local", "secrets", "credentials"}
SECRET_FILE_STEMS = {"secret", "secrets", "credential", "credentials", "api-key", "api_key", "token", "tokens"}


class RuntimeBackupError(RuntimeError):
    pass


def _is_sensitive_component(part: str) -> bool:
    folded = part.casefold()
    return (
        folded in EXCLUDED_NAMES
        or folded.startswith(".env")
        or PurePosixPath(folded).stem in SECRET_FILE_STEMS
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_files(runtime_dir: Path) -> Iterable[tuple[Path, str]]:
    root = runtime_dir.resolve()
    for name in MUTABLE_ROOTS:
        folder = root / name
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            parts = PurePosixPath(relative).parts
            if any(_is_sensitive_component(part) for part in parts):
                continue
            yield path, relative


def create_backup(runtime_dir: Path, output_dir: Path, *, now: datetime | None = None) -> Path:
    runtime_dir = runtime_dir.resolve()
    if not runtime_dir.is_dir():
        raise RuntimeBackupError(f"runtime directory does not exist: {runtime_dir}")
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = instant.strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"berry-runtime-{stamp}.tar.gz"
    if archive.exists():
        raise RuntimeBackupError(f"backup already exists: {archive}")
    files = list(_safe_files(runtime_dir))
    manifest: dict[str, Any] = {
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": instant.isoformat(timespec="seconds"),
        "scope": list(MUTABLE_ROOTS),
        "files": [
            {"path": relative, "size": path.stat().st_size, "sha256": _sha256(path), "mode": path.stat().st_mode & 0o777}
            for path, relative in files
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tarfile.open(archive, "x:gz", format=tarfile.PAX_FORMAT) as tar:
        for path, relative in files:
            tar.add(path, arcname=relative, recursive=False)
        info = tarfile.TarInfo("MANIFEST.json")
        info.size = len(manifest_bytes)
        info.mode = 0o600
        info.mtime = int(instant.timestamp())
        import io
        tar.addfile(info, io.BytesIO(manifest_bytes))
    verify_backup(archive)
    return archive


def backup_health(
    output_dir: Path,
    *,
    now: datetime | None = None,
    maximum_age: timedelta = timedelta(hours=36),
) -> dict[str, Any]:
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    archives = sorted(output_dir.glob("berry-runtime-*.tar.gz")) if output_dir.is_dir() else []
    if not archives:
        return {
            "state": "MISSING",
            "archives": 0,
            "latest": None,
            "latest_sha256": None,
            "age_seconds": None,
            "verified": False,
        }
    latest = archives[-1]
    try:
        manifest = verify_backup(latest)
        created = datetime.fromisoformat(manifest["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = max(0, int((instant - created.astimezone(timezone.utc)).total_seconds()))
        return {
            "state": "HEALTHY" if age <= maximum_age.total_seconds() else "STALE",
            "archives": len(archives),
            "latest": str(latest),
            "latest_sha256": _sha256(latest),
            "age_seconds": age,
            "verified": True,
        }
    except (OSError, ValueError, json.JSONDecodeError, RuntimeBackupError) as exc:
        return {
            "state": "INVALID",
            "archives": len(archives),
            "latest": str(latest),
            "latest_sha256": None,
            "age_seconds": None,
            "verified": False,
            "error": str(exc),
        }


def rotate_backups(
    runtime_dir: Path,
    output_dir: Path,
    *,
    keep: int = 14,
    now: datetime | None = None,
) -> dict[str, Any]:
    if keep < 2:
        raise RuntimeBackupError("backup retention must keep at least two verified archives")
    runtime = runtime_dir.resolve()
    destination = output_dir.resolve()
    if destination == runtime or runtime in destination.parents:
        raise RuntimeBackupError("backup output must be outside the app runtime")
    archive = create_backup(runtime, destination, now=now)
    archive_sha = _sha256(archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{archive_sha}  {archive.name}\n",
        encoding="utf-8",
    )
    valid: list[Path] = []
    invalid: list[str] = []
    for candidate in sorted(destination.glob("berry-runtime-*.tar.gz")):
        try:
            verify_backup(candidate)
        except (OSError, ValueError, json.JSONDecodeError, RuntimeBackupError):
            invalid.append(str(candidate))
        else:
            valid.append(candidate)
    if archive not in valid:
        raise RuntimeBackupError("new backup failed post-creation verification; retention was not changed")
    removed: list[str] = []
    for candidate in valid[:-keep]:
        # A newly verified archive exists and at least two valid archives are
        # retained. Invalid archives are never deleted automatically.
        candidate.unlink()
        sidecar = candidate.with_suffix(candidate.suffix + ".sha256")
        if sidecar.exists():
            sidecar.unlink()
        removed.append(str(candidate))
    retained = valid[-keep:]
    return {
        "state": "created_verified_rotated",
        "archive": str(archive),
        "archive_sha256": archive_sha,
        "archives_valid": len(valid),
        "archives_retained": len(retained),
        "archives_removed": len(removed),
        "removed": removed,
        "invalid_preserved": invalid,
    }


def _validated_members(tar: tarfile.TarFile) -> tuple[dict[str, Any], dict[str, tarfile.TarInfo]]:
    members = {member.name: member for member in tar.getmembers()}
    manifest_member = members.get("MANIFEST.json")
    if manifest_member is None or not manifest_member.isfile():
        raise RuntimeBackupError("backup has no MANIFEST.json")
    handle = tar.extractfile(manifest_member)
    if handle is None:
        raise RuntimeBackupError("backup manifest cannot be read")
    manifest = json.loads(handle.read().decode("utf-8"))
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise RuntimeBackupError("unsupported backup format version")
    expected = {entry["path"]: entry for entry in manifest.get("files", [])}
    for name, member in members.items():
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or member.issym() or member.islnk():
            raise RuntimeBackupError(f"unsafe backup member: {name}")
        if name != "MANIFEST.json" and name not in expected and member.isfile():
            raise RuntimeBackupError(f"unmanifested backup member: {name}")
    return manifest, members


def verify_backup(archive: Path) -> dict[str, Any]:
    with tarfile.open(archive, "r:gz") as tar:
        manifest, members = _validated_members(tar)
        for entry in manifest["files"]:
            member = members.get(entry["path"])
            if member is None or not member.isfile() or member.size != entry["size"]:
                raise RuntimeBackupError(f"missing or size-mismatched member: {entry['path']}")
            handle = tar.extractfile(member)
            if handle is None or hashlib.sha256(handle.read()).hexdigest() != entry["sha256"]:
                raise RuntimeBackupError(f"checksum mismatch: {entry['path']}")
        return manifest


def restore_backup(archive: Path, target_runtime_dir: Path, *, require_empty: bool = True) -> dict[str, Any]:
    manifest = verify_backup(archive)
    target = target_runtime_dir.resolve()
    if require_empty and target.exists() and any(target.iterdir()):
        raise RuntimeBackupError(f"restore target is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        _, members = _validated_members(tar)
        for entry in manifest["files"]:
            member = members[entry["path"]]
            destination = (target / Path(*PurePosixPath(entry["path"]).parts)).resolve()
            if target != destination and target not in destination.parents:
                raise RuntimeBackupError(f"restore path escapes target: {entry['path']}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise RuntimeBackupError(f"cannot extract: {entry['path']}")
            with destination.open("xb") as output:
                output.write(source.read())
            destination.chmod(int(entry["mode"]))
    for entry in manifest["files"]:
        restored = target / Path(*PurePosixPath(entry["path"]).parts)
        if _sha256(restored) != entry["sha256"]:
            raise RuntimeBackupError(f"restore verification failed: {entry['path']}")
    return manifest
