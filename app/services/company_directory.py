"""Organization presentation and personal marks; no canonical intelligence writes."""
import json
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.services import feed_first, personal_digest, seed_roster
from app.services.analyst_state_io import atomic_json, serialized_write
from app.services.map_regions import public_source_url

TIERS = {"untiered": "Untiered", "tier1": "Tier 1", "tier2": "Tier 2", "tier3": "Tier 3", "watch": "Legacy watch", "muted": "Muted"}
CURRENT_TIERS = {key: TIERS[key] for key in ("untiered", "tier1", "tier2", "tier3")}
PROFILE_FILE = "company_profile_overrides.json"


def assignment_tiers(current):
    """Offer current tiers while retaining this organization's stored legacy value."""
    choices = dict(CURRENT_TIERS)
    if current and current not in choices:
        choices[current] = f"{TIERS[current]} (existing)" if current in TIERS else "Existing tier — choose a current tier to change"
    return choices


def load_profiles(inbox_dir):
    path = Path(inbox_dir) / PROFILE_FILE
    if not path.exists():
        return {"version": 1, "profiles": {}, "history": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("profiles"), dict) or not isinstance(value.get("history"), list):
        raise ValueError("Profile history cannot be read; restore the saved file before editing")
    return value


def catalog(entities, *, logos=None, profiles=None, state=None):
    state, profiles = state or {}, profiles or {}
    rows = {}
    for entity in entities.values():
        if entity.get("entity_type") not in {"company", "brand", "breeding_program"}:
            continue
        attrs = entity.get("attributes") or {}
        rows[entity["id"]] = {**entity, "website": public_source_url(attrs.get("official_website") or attrs.get("website") or entity.get("website")),
                              "linkedin": public_source_url(attrs.get("linkedin") or attrs.get("linkedin_url")), "socials": [],
                              "profile_url": f"/entities/{entity['entity_type']}/{entity['id']}", "logo_url": "", "is_registry": False}
    for seed in seed_roster.build_roster(entities.values()):
        key = seed["id"]
        row = rows.get(key) or {"id": key, "name": seed["canonical_name"], "aliases": seed.get("aliases") or [],
                                "entity_type": "company", "status": "unverified", "berry_ids": ["berry-"+c for c in seed.get("crops") or []], "description": ""}
        rows[key] = {**row, "website": row.get("website") or public_source_url(seed.get("official_website") or seed.get("resolved_website")),
                     "linkedin": row.get("linkedin") or "", "socials": seed_roster.official_social_channels(seed),
                     "profile_url": row.get("profile_url") or seed_roster.profile_url(seed),
                     "logo_url": seed_roster.logo_display_url(seed, logo_overrides=logos), "is_registry": bool(seed.get("is_registry"))}
    lists = personal_digest.company_lists(state)
    for key, row in rows.items():
        if not row.get("linkedin"):
            row["linkedin"] = next((public_source_url(link.get("url")) for link in row.get("socials") or [] if link.get("platform") == "linkedin"), "")
        row["socials"] = [link for link in row.get("socials") or [] if link.get("url") != row.get("linkedin")]
        override = profiles.get(key) or {}
        for field in ("website", "linkedin", "socials"):
            if field in override:
                row[field] = override[field]
        row["logo_url"] = (logos or {}).get(key, {}).get("url") or row.get("logo_url") or ""
        row["canonical"] = key in entities
        row["favorite"] = bool((state.get("entity_favorites") or {}).get(key))
        row["tier"] = (state.get("entity_tiers") or {}).get(key) or "untiered"
        row["tier_label"] = TIERS.get(row["tier"], "Unrecognized legacy tier")
        row["tier_choices"] = assignment_tiers(row["tier"])
        row["lists"] = [group for group in lists if key in group.get("company_ids", [])]
        row["edited"] = any(field in override for field in ("website", "linkedin", "socials"))
        row["website"] = public_source_url(row.get("website"))
        row["linkedin"] = public_source_url(row.get("linkedin"))
        row["socials"] = [{**s, "url": public_source_url(s.get("url"))} for s in row.get("socials") or []]
    return rows


def initial(name):
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()[:1].upper()
    return value if "A" <= value <= "Z" else "#"


def matches_marks(ids, state, *, favorites="", tier="", list_id=""):
    ids = set(ids)
    if favorites == "1" and not any((state.get("entity_favorites") or {}).get(key) for key in ids):
        return False
    if tier and not any(((state.get("entity_tiers") or {}).get(key) or "untiered") == tier for key in ids):
        return False
    if list_id:
        group = next((g for g in personal_digest.company_lists(state) if g["id"] == list_id), None)
        if not group:
            raise ValueError("Company list is unavailable")
        if not ids.intersection(group.get("company_ids") or []):
            return False
    return True


def directory(rows, state, params):
    filters = {key: str(params.get(key) or "") for key in ("q", "letter", "berry", "tier", "list", "favorites", "kind")}
    if filters["tier"] and filters["tier"] not in TIERS or filters["favorites"] not in {"", "1"} or filters["kind"] not in {"", "company", "brand", "breeding_program", "registry"}:
        raise ValueError("Choose supported directory filters")
    if filters["letter"] and (len(filters["letter"]) != 1 or filters["letter"] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ#"):
        raise ValueError("Choose one alphabetical group")
    if filters["list"] and filters["list"] not in {g["id"] for g in personal_digest.company_lists(state)}:
        raise ValueError("Company list is unavailable")
    berries = set(filter(None, filters["berry"].split(",")))
    available = []
    for row in rows.values():
        if not matches_marks([row["id"]], state, favorites=filters["favorites"], tier=filters["tier"], list_id=filters["list"]):
            continue
        if berries and not berries.intersection(row.get("berry_ids") or []):
            continue
        kind = "registry" if row["is_registry"] else row["entity_type"]
        if filters["kind"] and filters["kind"] != kind:
            continue
        if filters["q"].casefold() not in " ".join([row["name"], *(row.get("aliases") or [])]).casefold():
            continue
        available.append(row)
    letters = {initial(row["name"]) for row in available}
    selected = sorted([r for r in available if not filters["letter"] or initial(r["name"]) == filters["letter"]], key=lambda r: r["name"].casefold())
    return {"rows": selected, "letters": letters, "matching": len(selected), "total": len(rows), "filters": filters,
            "tiers": TIERS, "lists": personal_digest.company_lists(state)}


@serialized_write
def mark(inbox_dir, *, entity_id, action, value="", allowed):
    if entity_id not in allowed:
        raise ValueError("Choose an organization from the directory")
    path = feed_first.state_path(inbox_dir)
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or any(key in raw and not isinstance(raw[key], dict) for key in ("entity_favorites", "entity_tiers", "company_lists")) or "entity_mark_history" in raw and not isinstance(raw["entity_mark_history"], list):
            raise ValueError("Personal history cannot be read; restore it before editing")
    state = feed_first.load_state(inbox_dir)
    before = {"favorite": bool(state.get("entity_favorites", {}).get(entity_id)), "tier": state["entity_tiers"].get(entity_id) or "untiered"}
    if action == "favorite":
        if value not in {"0", "1"}:
            raise ValueError("Choose a favorite status")
        state.setdefault("entity_favorites", {})[entity_id] = value == "1"
    elif action == "tier":
        if value not in TIERS:
            raise ValueError("Choose a supported tier")
        if value == "untiered":
            state["entity_tiers"].pop(entity_id, None)
        else:
            state["entity_tiers"][entity_id] = value
    elif action in {"join", "leave"}:
        group = state["company_lists"].get(value)
        if not group or group.get("archived"):
            raise ValueError("Company list is unavailable")
        members = set(group.get("company_ids") or [])
        if action == "join":
            members.add(entity_id)
        else:
            members.discard(entity_id)
        group["company_ids"] = sorted(members)
        group["updated_at"] = datetime.now(UTC).isoformat()
    else:
        raise ValueError("Choose a supported personal action")
    state.setdefault("entity_mark_history", []).append({"entity_id": entity_id, "action": action, "value": value, "before": before, "at": datetime.now(UTC).isoformat()})
    feed_first.save_state(inbox_dir, state)


def links(text):
    result = []
    for line in str(text or "").splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3 or not parts[0] or len(parts[0]) > 50 or len(parts[1]) > 120:
            raise ValueError("Use Platform | handle | URL for each social link; handle or URL may be blank")
        if parts[2] and not public_source_url(parts[2]) or not (parts[1] or parts[2]):
            raise ValueError("Use a public social link or a handle")
        result.append({"platform": parts[0], "handle": parts[1], "url": parts[2]})
    if len(result) > 20:
        raise ValueError("Use at most 20 social links")
    return result


@serialized_write
def edit_profile(inbox_dir, *, entity_id, payload, known_people=(), reviewer=""):
    state = load_profiles(inbox_dir)
    old = state["profiles"].get(entity_id) or {"revision": 0, "people": {}}
    if str(payload.get("revision", "")) != str(old["revision"]):
        raise ValueError("Profile changed in another view; reload before saving")
    row = {**old, "people": dict(old.get("people") or {})}
    action = payload.get("action") or "profile"
    if action == "reset":
        for field in ("website", "linkedin", "socials"):
            row.pop(field, None)
    elif action == "profile":
        for field in ("website", "linkedin"):
            value = str(payload.get(field) or "").strip()
            if value and not public_source_url(value):
                raise ValueError("Use complete public http or https profile links")
            row[field] = value
        row["socials"] = links(payload.get("socials"))
    elif action in {"person", "hide_person", "restore_person"}:
        key = str(payload.get("person_id") or "")
        if key and key not in row["people"] and key not in known_people:
            raise ValueError("Person is not linked to this company")
        key = key or "contact-" + uuid4().hex
        person = dict(row["people"].get(key) or {})
        if action == "person":
            name = str(payload.get("name") or "").strip()
            if not name or len(name) > 150:
                raise ValueError("Choose a person name of 1–150 characters")
            linkedin = str(payload.get("linkedin") or "").strip()
            if linkedin and not public_source_url(linkedin):
                raise ValueError("Use a complete public LinkedIn link")
            person.update(name=name, role=str(payload.get("role") or "").strip()[:150], linkedin=linkedin,
                          socials=links(payload.get("socials")), highlighted=payload.get("highlighted") == "1", hidden=False)
        else:
            person["hidden"] = action == "hide_person"
        row["people"][key] = person
    else:
        raise ValueError("Choose a supported profile action")
    row["revision"] = old["revision"] + 1
    row["updated_at"] = datetime.now(UTC).isoformat()
    state["history"].append({"entity_id": entity_id, "action": action, "before": old, "after": row, "reviewer": reviewer, "at": row["updated_at"]})
    state["profiles"][entity_id] = row
    atomic_json(Path(inbox_dir) / PROFILE_FILE, state)
    return row


def people_for(entity_id, entities, relationships, discovered, overrides):
    rows = {}
    for person in discovered:
        if entity_id in person.get("entity_ids", []):
            rows[person["id"]] = {"id": person["id"], "name": person["canonical_name"], "role": "", "basis": "Named in stored records", "linkedin": "", "socials": [], "highlighted": False, "hidden": False}
    for rel in relationships:
        if rel.get("status") != "active":
            continue
        a, b = rel.get("subject_id"), rel.get("object_id")
        key = b if a == entity_id else a if b == entity_id else None
        person = entities.get(key) or {}
        if person.get("entity_type") == "person":
            rows[key] = {"id": key, "name": person["name"], "role": "", "basis": "Stored relationship: " + rel["predicate"].replace("_", " "), "linkedin": "", "socials": [], "highlighted": False, "hidden": False}
    for key, value in overrides.get("people", {}).items():
        rows[key] = {"id": key, "role": "", "linkedin": "", "socials": [], "highlighted": False, "hidden": False,
                     **rows.get(key, {}), **value, "basis": "User-edited contact · not reviewed"}
        rows[key]["linkedin"] = public_source_url(rows[key].get("linkedin"))
        rows[key]["socials"] = [{**link, "url": public_source_url(link.get("url"))} for link in rows[key].get("socials") or []]
    return sorted(rows.values(), key=lambda row: (not row["highlighted"], row.get("name", "").casefold()))
