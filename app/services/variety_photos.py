"""Private, attributed photo presentation over existing source observations.

No acquisition on GET, no identity/trait approval and no canonical writes.
User choices share the existing profile override history and survive refreshes.
"""
from copy import deepcopy
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.services import company_directory
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.map_regions import public_source_url
from app.services.variety_universe.identity import fold_identity, resolve_identity

REUSE = {"unknown": "Reuse not established", "public_domain": "Public domain",
         "cc0": "CC0", "cc_by": "CC BY", "cc_by_sa": "CC BY-SA",
         "permission": "Permission recorded", "owned": "User-owned photo"}
KINDS = {"fruit": "Fruit photo", "plant": "Plant / trial photo", "drawing": "Patent / botanical drawing"}
FIELDS = ("image_url", "source_url", "credit", "caption", "named_variety", "berry_id",
          "reuse", "license_url", "reuse_note", "checked_on", "kind")


def validate_photo(value):
    if not isinstance(value, dict):
        raise ValueError("Photo details must be an object")
    if any(key in value and not isinstance(value[key], str) for key in FIELDS):
        raise ValueError("Photo details must be text")
    row = {key: str(value.get(key) or "").strip() for key in FIELDS}
    for key in ("image_url", "source_url"):
        if not public_source_url(row[key]):
            raise ValueError("Use complete public http or https image and source links")
    if not row["credit"] or not row["caption"] or not row["named_variety"]:
        raise ValueError("Include the photo credit, caption and exact variety name or code")
    if any(len(row[key]) > 2000 for key in FIELDS):
        raise ValueError("Keep each photo detail below 2,000 characters")
    if row["berry_id"] not in {"berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"}:
        raise ValueError("Choose the photo's berry type")
    if row["reuse"] not in REUSE or row["kind"] not in KINDS:
        raise ValueError("Choose the photo type and reuse basis")
    if row["license_url"] and not public_source_url(row["license_url"]):
        raise ValueError("Use a complete public link for reuse terms")
    if row["reuse"] != "unknown" and (not row["license_url"] or not row["reuse_note"]):
        raise ValueError("Record the reuse terms link and why these terms cover this photo")
    try:
        checked = date.fromisoformat(row["checked_on"])
    except ValueError as exc:
        raise ValueError("Record the source check date as YYYY-MM-DD") from exc
    if checked > date.today():
        raise ValueError("The source check date cannot be in the future")
    return row


def compatible(photo, target, *, candidate=False):
    berries = [target.get("berry_id")] if candidate else target.get("berry_ids") or []
    if photo["berry_id"] not in berries:
        return False
    if candidate:
        return fold_identity(photo["named_variety"]) in {
            fold_identity(target.get(key)) for key in ("candidate_name", "denomination", "breeder_code", "trade_name")
            if target.get(key)}
    result = resolve_identity({"candidate_name": photo["named_variety"], "berry_id": photo["berry_id"]}, [target])
    return any(row["reason"] == "exact_identity_string" for row in result["matches"])


def source_photos(target, *, sources=(), candidate=False, varieties=()):
    refs = [(None, ref) for ref in target.get("portfolio_sources", [])] if candidate else [
        (source, name) for source in sources for name in source.get("names", [])]
    rows = {}
    pair_notes = None
    for source, ref in refs:
        if ref.get("identity_notes"):
            continue
        for raw in ref.get("photos", []):
            photo = validate_photo(raw)
            if not compatible(photo, target, candidate=candidate):
                continue
            if not candidate:
                # Honor the portfolio's existing code/label discrepancy gate,
                # including when only one of those identities is in the catalog.
                from app.services.variety_portfolio_coverage import _identity_pair_notes, _key
                if pair_notes is None:
                    pair_notes = _identity_pair_notes(sources)
                if pair_notes.get((source["id"], _key(ref), ref.get("trade_name") or ref["candidate_name"]), []):
                    continue
            if not candidate and varieties:
                result = resolve_identity({"candidate_name": photo["named_variety"], "berry_id": photo["berry_id"]}, list(varieties))
                ids = {row["variety_id"] for row in result["matches"] if row["reason"] == "exact_identity_string"}
                if ids != {target["id"]}:
                    continue
            key = "source-photo-" + sha256((photo["source_url"] + "\n" + photo["image_url"]).encode()).hexdigest()[:20]
            rows[key] = {**photo, "id": key, "origin": "Named by source · not yet reviewed"}
    return list(rows.values())


def gallery(target, *, sourced=(), profile=None, authoring=False):
    # Source captions and private user edits never enter the public snapshot.
    # Public photo publication must use the existing human publication path.
    if not authoring:
        return []
    profile = profile or {}
    rows = {row["id"]: deepcopy(row) for row in sourced}
    for key, value in (profile.get("variety_photo_overrides") or {}).items():
        if value is None:
            rows.pop(key, None)
        else:
            rows[key] = {**validate_photo(value), "id": key, "origin": "Your photo details · not yet reviewed"}
    result = []
    for row in rows.values():
        if not compatible(row, target, candidate=bool(target.get("candidate_name"))):
            continue
        result.append({**row, "display_image": row["reuse"] != "unknown", "reuse_label": REUSE[row["reuse"]],
                       "kind_label": KINDS[row["kind"]]})
    return result


@serialized_write
def edit(inbox_dir, *, target, payload, sourced=(), reviewer=""):
    state = company_directory.load_profiles(inbox_dir)
    key = target["id"]
    old = state["profiles"].get(key) or {"revision": 0}
    if str(payload.get("revision", "")) != str(old["revision"]):
        raise ValueError("Photo details changed in another view; reload before saving")
    row = deepcopy(old)
    overrides = row.setdefault("variety_photo_overrides", {})
    photo_id = str(payload.get("photo_id") or "")
    known = {p["id"] for p in sourced} | set(overrides)
    action = payload.get("action")
    if action not in {"save", "remove", "reset", "restore"} or (photo_id and photo_id not in known):
        raise ValueError("Choose an existing photo or add a new one")
    if action == "save":
        photo = validate_photo(payload)
        if not compatible(photo, target, candidate=bool(target.get("candidate_name"))):
            raise ValueError("The photo name or code and berry must match this variety; keep other identities separate")
        photo_id = photo_id or "user-photo-" + uuid4().hex
        overrides[photo_id] = photo
    elif not photo_id:
        raise ValueError("Choose the photo to change")
    elif action == "remove":
        overrides[photo_id] = None
    elif action == "restore":
        saved = next((change["before"].get("variety_photo_overrides", {}).get(photo_id)
                      for change in reversed(state["history"]) if change.get("entity_id") == key
                      and (change.get("before") or {}).get("variety_photo_overrides", {}).get(photo_id)), None)
        if saved:
            photo = validate_photo(saved)
            if not compatible(photo, target, candidate=bool(target.get("candidate_name"))):
                raise ValueError("Saved photo identity no longer matches this variety")
            overrides[photo_id] = photo
        else:
            overrides.pop(photo_id, None)
    else:
        overrides.pop(photo_id, None)
    row["revision"] = old["revision"] + 1
    state["profiles"][key] = row
    state["history"].append({"entity_id": key, "action": "variety_photo_" + action, "photo_id": photo_id,
                             "reviewer": reviewer, "at": datetime.now(UTC).isoformat(),
                             "before": deepcopy(old), "after": deepcopy(row)})
    atomic_json(Path(inbox_dir) / company_directory.PROFILE_FILE, state)
    return row
