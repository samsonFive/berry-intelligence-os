"""Versioned private analyst inputs for company strategy frameworks."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit

from app.services import living_workspaces as living
from app.services.global_berry_landscape import CROPS, REGIONS

KIND = "berry_strategy_input"
PREFIX = "berry-strategy-input-"
ENTITY_TYPES = {"company", "retailer", "breeding_program"}
CATEGORIES = {"strength": "Strength", "weakness": "Weakness", "capability": "Capability"}
VRIO_FIELDS = {"valuable": "Valuable", "rare": "Rare", "inimitable": "Difficult to imitate", "organized": "Organized to exploit"}
VRIO_VALUES = {"unknown": "Unknown", "yes": "Yes", "no": "No"}


def _text(payload, field, maximum, *, required=False):
    value = payload.get(field, "")
    if not isinstance(value, str) or len(value.strip()) > maximum:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} must be text of at most {maximum} characters.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field.replace('_', ' ').capitalize()} is required.")
    return value


def _content(payload, allowed_entities):
    if not isinstance(payload, dict):
        raise ValueError("Supply an analyst input.")
    entity_id = _text(payload, "entity_id", 160, required=True)
    entity = allowed_entities.get(entity_id) or {}
    if entity.get("entity_type") not in ENTITY_TYPES:
        raise ValueError("Choose an existing company, retailer or breeding program.")
    crop, region = _text(payload, "crop", 40), _text(payload, "region", 40)
    if (crop and crop not in CROPS) or (region and region not in REGIONS):
        raise ValueError("Choose a supported berry and macroregion, or all.")
    category = _text(payload, "category", 40, required=True)
    if category not in CATEGORIES:
        raise ValueError("Choose a strength, weakness or capability.")
    observed = _text(payload, "observed_date", 10, required=True)
    try:
        if date.fromisoformat(observed).isoformat() != observed:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Observed date must use YYYY-MM-DD.") from exc
    url = _text(payload, "source_url", 2000)
    parsed = urlsplit(url)
    if url and (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or any(character.isspace() for character in url)):
        raise ValueError("Public source URL must be an HTTP or HTTPS URL without credentials.")
    judgments = payload.get("vrio", {})
    if not isinstance(judgments, dict) or set(judgments) - VRIO_FIELDS.keys():
        raise ValueError("Choose supported VRIO judgments.")
    vrio = {}
    for field in VRIO_FIELDS:
        judgment = judgments.get(field, {"judgment": "unknown", "rationale": ""})
        if not isinstance(judgment, dict) or set(judgment) - {"judgment", "rationale"}:
            raise ValueError("Each VRIO judgment needs a value and rationale.")
        value = judgment.get("judgment", "unknown")
        if not isinstance(value, str) or value not in VRIO_VALUES:
            raise ValueError("VRIO judgments must be yes, no or unknown.")
        vrio[field] = {"judgment": value, "rationale": _text(judgment, "rationale", 1200, required=value != "unknown")}
    return {"entity_id": entity_id, "crop": crop, "region": region, "category": category,
            "title": _text(payload, "title", 240, required=True), "statement": _text(payload, "statement", 4000, required=True),
            "reference": _text(payload, "reference", 2000, required=True), "observed_date": observed,
            "source_url": url, "vrio": vrio}


def _identity(value):
    if not isinstance(value, str) or not re.fullmatch(PREFIX + r"[a-f0-9]{32}", value):
        raise ValueError("Choose an existing strategy input.")
    return value


def _request(actor, expected, **fields):
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
        raise ValueError("A named analyst is required.")
    if type(expected) is not int or expected < 0:
        raise ValueError("Supply the current input version.")
    return {"kind": KIND, "actor": actor, "expected": expected, **fields}


def save_input(store, payload, actor, allowed_entities, expected=0, token=None):
    content = _content(payload, allowed_entities)
    identity = payload.get("id") or ""
    if identity:
        _identity(identity)
    request = _request(actor, expected, operation="save", id=identity, content=content)
    with store.transaction() as db:
        replay = store.replay(db, token, request)
        if replay:
            return replay
        old = store.get(identity, db) if identity else None
        if identity and (not old or old.get("kind") != KIND):
            raise ValueError("Strategy input not found.")
        if expected != (old["version"] if old else 0):
            raise living.Conflict("The input changed. Reload before saving it.")
        row = {"id": identity or living.ident(PREFIX), "kind": KIND, **content, "state": "draft",
               "created_at": old["created_at"] if old else living.now(), "created_by": old["created_by"] if old else actor}
        saved = store.put(db, KIND, row, actor, expected)
        store.remember(db, token, request, saved)
        return saved


def decide_input(store, input_id, actor, allowed_entities, expected, action, token=None):
    identity = _identity(input_id)
    if action not in {"approve", "withdraw"}:
        raise ValueError("Choose approval or withdrawal.")
    request = _request(actor, expected, operation=action, id=identity)
    with store.transaction() as db:
        replay = store.replay(db, token, request)
        if replay:
            return replay
        current = store.get(identity, db)
        if not current or current.get("kind") != KIND:
            raise ValueError("Strategy input not found.")
        if current["version"] != expected:
            raise living.Conflict("The input changed. Reload before recording a decision.")
        if action == "approve":
            content = _content(current, allowed_entities)
            if current["state"] != "draft":
                raise ValueError("Save a draft before approving this input.")
            updated = {**current, **content, "state": "approved", "approved_at": living.now(), "approved_by": actor}
        else:
            if current["state"] == "withdrawn":
                raise ValueError("This input is already withdrawn.")
            updated = {**current, "state": "withdrawn", "withdrawn_at": living.now(), "withdrawn_by": actor}
        saved = store.put(db, KIND, updated, actor, expected)
        store.remember(db, token, request, saved)
        return saved


def _matches_scope(row, scope):
    # Inputs carry no transaction or value-chain-role assertion.
    if scope.get("event_type") or scope.get("role"):
        return False
    if any(scope.get(field) and row.get(field) and row[field] != scope[field] for field in ("crop", "region")):
        return False
    observed = row.get("observed_date", "")
    if (scope.get("start") and observed < scope["start"]) or (scope.get("end") and observed > scope["end"]):
        return False
    query = str(scope.get("q") or "").casefold()
    return not query or query in (row.get("title", "") + " " + row.get("statement", "")).casefold()


def matching_inputs(rows, scope, entity_ids=None, *, approved_only=True):
    selected = set(entity_ids) if entity_ids is not None else None
    return sorted((row for row in rows if row.get("kind") == KIND
                   and (not approved_only or row.get("state") == "approved")
                   and (selected is None or row.get("entity_id") in selected)
                   and _matches_scope(row, scope)), key=lambda row: row["id"])


def scoped_inputs(store, scope, entity_ids=None, *, approved_only=True, db=None):
    return matching_inputs(store.rows(KIND, db), scope, entity_ids, approved_only=approved_only)
