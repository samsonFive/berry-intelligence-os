"""Private, attributed variety research profiles; never trusted catalog records.

The persisted import is immutable and separate from Facts, relationships and
publication decisions. Existing entity pages read it only in authoring mode.
Missing identities remain application leads, not invented cultivar entities.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

ROOT = "variety_research"
SAFE_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,180}\Z")
SAFE_CAPTURE = re.compile(r"[a-zA-Z0-9_-]+\.png\Z")


@lru_cache(maxsize=16)
def _read_index(path, modified, size):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("kind") != "private_variety_research_import" or payload.get("version") != 1:
        raise ValueError("Unsupported variety research import")
    return payload


def imports(inbox_dir):
    result = []
    for path in sorted((Path(inbox_dir) / ROOT / "imports").glob("*/manifest.json")):
        stat = path.stat()
        result.append(_read_index(str(path), stat.st_mtime_ns, stat.st_size))
    return sorted(result, key=lambda batch: (batch.get("imported_at") or batch["checked_on"], batch["id"]))


def index(inbox_dir, *, q="", berry="", state=""):
    profiles = {}
    unresolved = {}
    batches = imports(inbox_dir)
    for batch in batches:
        for entity_id in batch.get("superseded_entity_ids", []):
            profiles.pop(entity_id, None)
        for row in batch["profiles"]:
            profiles[row["entity_id"]] = row
        for key in batch.get("resolved_keys", []):
            unresolved.pop(key, None)
        unresolved.update({row["key"]: row for row in batch.get("unresolved", [])})
    unresolved = list(unresolved.values())
    rows = list(profiles.values())
    total = len(rows)
    if q:
        words = q.casefold().split()
        rows = [row for row in rows if all(word in row["search_text"].casefold() for word in words)]
        unresolved = [row for row in unresolved if all(word in str(row).casefold() for word in words)]
    if berry:
        rows = [row for row in rows if berry in row.get("berries", [])]
        unresolved = [row for row in unresolved if berry == row.get("berry")]
    if state:
        rows = [row for row in rows if row["profile_kind"] == state]
    return {"rows": sorted(rows, key=lambda row: (row["name"].casefold(), row["entity_id"])),
            "unresolved": unresolved, "total": total, "batches": batches,
            "filters": {"q": q, "berry": berry, "state": state}}


def private_entity(inbox_dir, entity_type, entity_id):
    if not SAFE_ID.fullmatch(entity_id):
        return None
    if any(entity_id in batch.get("superseded_entity_ids", []) for batch in imports(inbox_dir)):
        return None
    for batch in reversed(imports(inbox_dir)):
        for row in batch["profiles"]:
            entity = row.get("private_entity")
            if entity and entity["id"] == entity_id and entity["entity_type"] == entity_type:
                return entity
        for entity in batch.get("commercial_entities", []):
            if entity["id"] == entity_id and entity["entity_type"] == entity_type:
                return entity
    return None


def profile(inbox_dir, entity_id):
    if not SAFE_ID.fullmatch(entity_id):
        return None
    if any(entity_id in batch.get("superseded_entity_ids", []) for batch in imports(inbox_dir)):
        return None
    dossiers = {}
    for batch in imports(inbox_dir):
        if not SAFE_ID.fullmatch(batch["id"]):
            raise ValueError("Invalid research import identifier")
        for row in batch["profiles"]:
            if row["entity_id"] != entity_id:
                continue
            payload = json.loads((Path(inbox_dir) / ROOT / "imports" / batch["id"] / "profiles" / (entity_id + ".json")).read_text(encoding="utf-8"))
            sheet_path = Path(inbox_dir) / ROOT / "imports" / batch["id"] / "source_sheet_rows.json"
            sheet = json.loads(sheet_path.read_text(encoding="utf-8")) if sheet_path.exists() else {}
            for dossier in payload["dossiers"]:
                dossiers[dossier["key"]] = {**dossier, "source_sheet_records": sheet.get("groups", {}).get(dossier["key"], [])}
    return {"dossiers": list(dossiers.values())} if dossiers else None


def company_research(inbox_dir, entity_id):
    rows = [row for row in index(inbox_dir)["rows"] if entity_id in row.get("commercial_entity_ids", [])]
    return {"rows": rows} if rows else None


def capture_file(inbox_dir, batch_id, filename):
    if not SAFE_ID.fullmatch(batch_id) or not SAFE_CAPTURE.fullmatch(filename):
        return None
    batch = next((b for b in imports(inbox_dir) if b["id"] == batch_id), None)
    if not batch or filename not in batch.get("capture_files", []):
        return None
    base = (Path(inbox_dir) / ROOT / "imports" / batch_id / "captures").resolve()
    path = (base / filename).resolve()
    return path if path.parent == base and path.is_file() else None
