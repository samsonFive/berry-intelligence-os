"""Physical source-record storage, activated only by a verified migration.

Before activation callers retain their existing JSON paths. Afterwards both
data- and inbox-oriented adapters resolve one records directory. Publication
scope is persisted separately from review/status and defaults to private on
new acquisition. Cache envelopes contain references, never a competing record.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Iterable

VERSION = 1
STORE_NAME = "information"
MARKER_NAME = "store.json"
BINDING_NAME = ".information-store.json"
TRANSITION_NAME = ".information-store-transition.json"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$")


class InformationStorageError(RuntimeError):
    pass


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value) or value in {".", ".."}:
        raise InformationStorageError("Invalid information record identifier")
    return value


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InformationStorageError(f"Cannot read information storage file: {path}") from exc
    if not isinstance(value, dict):
        raise InformationStorageError(f"Information storage file must contain an object: {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=".information-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _root(*, data_dir=None, inbox_dir=None) -> tuple[Path | None, dict[str, Any] | None]:
    data = Path(data_dir).resolve() if data_dir is not None else None
    inbox = Path(inbox_dir).resolve() if inbox_dir is not None else None
    root = data / STORE_NAME if data is not None else None
    if inbox is not None and (inbox / BINDING_NAME).exists():
        binding = read_json(inbox / BINDING_NAME)
        if binding.get("version") != VERSION or binding.get("inbox_dir") != str(inbox):
            raise InformationStorageError("Invalid information-store inbox binding")
        named = Path(str(binding.get("store_root") or ""))
        bound = named.resolve()
        if not named.is_absolute() or bound.name != STORE_NAME:
            raise InformationStorageError("Invalid information-store location")
        if root is not None and root != bound:
            raise InformationStorageError("Data and inbox refer to different information stores")
        root = bound
        if not (root / MARKER_NAME).is_file():
            raise InformationStorageError("Information migration is incomplete; legacy fallback is disabled")
    if root is None:
        if inbox is None:
            raise InformationStorageError("Name a data directory or inbox directory")
        return None, None
    if root.is_symlink() or (root / MARKER_NAME).is_symlink() or (root / "records").is_symlink():
        raise InformationStorageError("Information-store directories and markers cannot be symbolic links")
    if (root.parent / TRANSITION_NAME).exists():
        raise InformationStorageError("Information migration is in progress; resume or roll back before serving writes")
    marker_path = root / MARKER_NAME
    if not marker_path.exists():
        if root.is_dir() and any(root.iterdir()):
            raise InformationStorageError("Information store is incomplete; legacy fallback is disabled")
        return root, None
    marker = read_json(marker_path)
    if marker.get("version") != VERSION or marker.get("state") != "active":
        raise InformationStorageError("Information store is not active or has an unsupported version")
    if marker.get("store_root") != str(root):
        raise InformationStorageError("Information store moved; restore/rebind explicitly before using it")
    if data is not None and marker.get("data_dir") != str(data):
        raise InformationStorageError("Information-store data binding does not match this runtime")
    if inbox is not None and marker.get("inbox_dir") != str(inbox):
        raise InformationStorageError("Information-store inbox binding does not match this runtime")
    if not (root / "records").is_dir():
        raise InformationStorageError("Active information store has no records directory")
    return root, marker


def enabled(*, data_dir=None, inbox_dir=None) -> bool:
    return _root(data_dir=data_dir, inbox_dir=inbox_dir)[1] is not None


def is_public_record(record: dict[str, Any]) -> bool:
    from app.services.information_catalog import INACTIVE_STATES
    review = record.get("review_state")
    return (record.get("status") == "published" and record.get("publication_scope", "public") == "public"
            and (review is None or isinstance(review, str) and review not in INACTIVE_STATES))


def information_directory(*, data_dir=None, inbox_dir=None) -> Path:
    root, marker = _root(data_dir=data_dir, inbox_dir=inbox_dir)
    if marker is not None:
        return root / "records"
    legacy = data_dir if data_dir is not None else inbox_dir
    return Path(legacy) / "evidence"


def record_path(record_id: str, *, data_dir=None, inbox_dir=None) -> Path:
    return information_directory(data_dir=data_dir, inbox_dir=inbox_dir) / (safe_id(record_id) + ".json")


def assets_dir(*, data_dir=None, inbox_dir=None) -> Path:
    root, marker = _root(data_dir=data_dir, inbox_dir=inbox_dir)
    if marker is not None:
        if (root / "assets").is_symlink():
            raise InformationStorageError("Information-store assets cannot be a symbolic link")
        return root / "assets"
    return Path(data_dir if data_dir is not None else inbox_dir) / "attachments"


def get_record(record_id: str, *, data_dir=None, inbox_dir=None) -> dict[str, Any] | None:
    path = record_path(record_id, data_dir=data_dir, inbox_dir=inbox_dir)
    if not path.exists():
        return None
    if path.is_symlink():
        raise InformationStorageError("Information records cannot be symbolic links")
    row = read_json(path)
    if row.get("id") != record_id:
        raise InformationStorageError(f"Information record identity does not match its path: {path}")
    return row


def list_records(*, data_dir=None, inbox_dir=None) -> list[dict[str, Any]]:
    folder = information_directory(data_dir=data_dir, inbox_dir=inbox_dir)
    return [row for path in sorted(folder.glob("*.json"))
            if (row := get_record(path.stem, data_dir=data_dir, inbox_dir=inbox_dir)) is not None]


@contextmanager
def storage_lock(*, data_dir=None, inbox_dir=None, timeout: float = 30, maintenance: bool = False):
    """OS-owned exclusive lease; a crashed process cannot strand the lock.

    Migrations also acquire the existing collector lease and require the web
    service to be stopped; legacy code cannot otherwise honor a new lock.
    """
    if maintenance:
        if data_dir is None:
            raise InformationStorageError("Maintenance locking requires an explicit data directory")
        root, marker = Path(data_dir).resolve() / STORE_NAME, None
    else:
        root, marker = _root(data_dir=data_dir, inbox_dir=inbox_dir)
    if root is None:
        location = Path(inbox_dir).resolve() / ".information-store.lock"
    else:
        location = root.parent / ".information-store.lock"
    location.parent.mkdir(parents=True, exist_ok=True)
    handle = location.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while not acquired:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise InformationStorageError("Information store is locked by another writer")
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def prepare_record(record: dict[str, Any], existing: dict[str, Any] | None = None, *,
                   origin: str = "intake", preserve_existing: bool = False,
                   allow_review_update: bool = False) -> dict[str, Any]:
    """Prepare an active-store write; replacement remains exact for UoW undo.

    Replacement drops omitted payload fields. Both modes retain an existing
    publication scope when a caller omits it; canonical creation is public only
    for a stored published record, whereas acquisition/retention is private.
    """
    from app.services.information_catalog import information_flags
    if origin not in {"canonical", "intake", "retained"}:
        raise InformationStorageError("Unknown information storage origin")
    row = {**deepcopy(existing or {}), **deepcopy(record)} if preserve_existing else deepcopy(record)
    if preserve_existing and isinstance((existing or {}).get("information"), dict) and isinstance(record.get("information"), dict):
        row["information"] = {**existing["information"], **record["information"]}
    if origin == "intake" and existing and not allow_review_update:
        from app.services.article_dedup import normalize_canonical_url
        old_url, new_url = existing.get("source_url"), record.get("source_url")
        if old_url and new_url and (normalize_canonical_url(old_url) or old_url) != (normalize_canonical_url(new_url) or new_url):
            raise InformationStorageError("Intake update conflicts with the current source identity")
        if information_flags(existing)["review_status"] in {"reviewed", "rejected"} or existing.get("status") == "published":
            row = deepcopy(existing)
            if information_flags(existing)["review_status"] != "rejected":
                for key in ("article", "article_body", "transcript", "pdf", "source_artifact"):
                    if not row.get(key) and record.get(key):
                        row[key] = deepcopy(record[key])
        for key in ("information", "information_confidence", "confidence", "reviewed_by", "reviewed_at",
                    "human_reviewed", "validated", "review_outcome", "rejection_reason", "rejection_category"):
            if key in existing:
                row[key] = deepcopy(existing[key])
            elif key in row:
                row.pop(key)
    default_scope = "public" if origin == "canonical" and record.get("status") == "published" else "private"
    if origin in {"intake", "retained"}:
        # Acquisition payloads cannot grant publication permission to
        # themselves or change an existing record's publication boundary.
        row["publication_scope"] = (existing or {}).get("publication_scope") or "private"
    else:
        row["publication_scope"] = record.get("publication_scope") or (existing or {}).get("publication_scope") or default_scope
    if row["publication_scope"] not in {"public", "private"}:
        raise InformationStorageError("Publication scope must be public or private")
    row["information"] = information_flags(row)
    if origin == "intake" and existing is None and preserve_existing and not allow_review_update:
        row["information"]["review_status"] = "unreviewed"
    row["storage_origin"] = record.get("storage_origin") or (existing or {}).get("storage_origin") or origin
    row.pop("_catalog_origin", None)
    return row


def _archive_previous(path: Path, previous: dict[str, Any], root: Path) -> None:
    payload = json.dumps(previous, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    history = root / "history" / safe_id(str(previous["id"])) / (digest + ".json")
    if not history.exists():
        atomic_json(history, previous)


def upsert_record(record: dict[str, Any], *, data_dir=None, inbox_dir=None,
                  origin: str = "intake", preserve_existing: bool = True,
                  allow_review_update: bool = False) -> Path:
    key = safe_id(record.get("id") or "")
    path = record_path(key, data_dir=data_dir, inbox_dir=inbox_dir)
    root, marker = _root(data_dir=data_dir, inbox_dir=inbox_dir)
    if marker is None:
        atomic_json(path, record)
        return path
    with storage_lock(data_dir=data_dir, inbox_dir=inbox_dir):
        previous = get_record(key, data_dir=data_dir, inbox_dir=inbox_dir)
        row = prepare_record(record, previous, origin=origin, preserve_existing=preserve_existing,
                             allow_review_update=allow_review_update)
        if previous == row:
            return path
        if previous is not None:
            _archive_previous(path, previous, root)
        atomic_json(path, row)
    return path


def write_record(record: dict[str, Any], *, data_dir=None, inbox_dir=None,
                 origin: str = "canonical", preserve_existing: bool = False) -> Path:
    return upsert_record(record, data_dir=data_dir, inbox_dir=inbox_dir,
                         origin=origin, preserve_existing=preserve_existing)


def retain_records(inbox_dir: Path, rows: Iterable[dict[str, Any]]) -> list[str]:
    """Ingest discovery once, without downgrading an existing record.

    A repeat discovery may fill an absent preview/body field, but never replace
    analyst decisions, confidence, publication scope or already retained prose.
    """
    from app.services.information_catalog import INACTIVE_STATES, information_flags
    if not enabled(inbox_dir=inbox_dir):
        raise InformationStorageError("Cache references require an active information store")
    ids = []
    with storage_lock(inbox_dir=inbox_dir):
        root, _ = _root(inbox_dir=inbox_dir)
        for incoming in rows:
            key = safe_id(incoming.get("id") or "")
            previous = get_record(key, inbox_dir=inbox_dir)
            if previous is None:
                row = deepcopy(incoming)
                row["publication_scope"] = "private"
                if row.get("status") not in INACTIVE_STATES:
                    row["status"] = "unreviewed"
                flags = row.get("information") if isinstance(row.get("information"), dict) else {}
                row["information"] = {**flags, "review_status": "unreviewed"}
                row["information"] = information_flags(row)
                row.pop("_catalog_origin", None)
            else:
                from app.services.article_dedup import normalize_canonical_url
                previous_url, incoming_url = previous.get("source_url"), incoming.get("source_url")
                if (previous_url and incoming_url and
                        (normalize_canonical_url(previous_url) or previous_url) != (normalize_canonical_url(incoming_url) or incoming_url)):
                    raise InformationStorageError(f"Discovery identity conflicts with retained record: {key}")
                row = deepcopy(previous)
                if (information_flags(previous)["review_status"] in {"reviewed", "rejected"}
                        or previous.get("publication_scope") == "public"):
                    ids.append(key)
                    continue
                protected = {"id", "status", "review_state", "reviewed_by", "reviewed_at", "validated",
                             "human_reviewed", "information", "information_confidence", "confidence",
                             "publication_scope", "priority", "fact_ids", "entity_ids", "geography_ids", "berry_ids",
                             "verification_state", "review_outcome", "rejection_reason", "rejection_category"}
                for field, value in incoming.items():
                    if field not in protected and field not in row and value not in (None, "", [], {}):
                        row[field] = deepcopy(value)
                if row != previous:
                    _archive_previous(record_path(key, inbox_dir=inbox_dir), previous, root)
            if previous != row:
                atomic_json(record_path(key, inbox_dir=inbox_dir), row)
            ids.append(key)
    return ids


def load_records_by_id(inbox_dir: Path, ids: Iterable[str], *, metadata_only: bool = False) -> list[dict[str, Any]]:
    if not metadata_only:
        return [row for key in ids if (row := get_record(str(key), inbox_dir=inbox_dir)) is not None]
    from app.services.publication_sources import _current_preview
    rows = []
    for key in ids:
        path = record_path(str(key), inbox_dir=inbox_dir)
        if not path.exists():
            continue
        if path.is_symlink():
            raise InformationStorageError("Information records cannot be symbolic links")
        row = _current_preview(path)
        if row.get("id") != key:
            raise InformationStorageError("Information preview identity does not match the requested record")
        rows.append(row)
    return rows


storage_enabled = store_enabled = enabled
records_dir = record_directory = information_directory
load_record = get_record
