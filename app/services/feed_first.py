"""Feed-first read model and analyst-decision store for Gate 1.

Maps existing published Evidence onto Feed Item + Analyst Decision +
Evidence Statement contracts without writing trusted ``data/`` records.
Thumbs-up does not enter Publication Review. Extraction is a labeled
local deterministic preview until a qualified model exists.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from app.services.berries.landscape import SEED_FIXTURE_EVIDENCE_IDS
from app.services.html_text import decode_html_text
from app.services.source_body import classify_source_body, reader_content

STATE_FILENAME = "feed_first_state.json"
EXTRACTION_MODEL = "local-deterministic-preview"
EXTRACTION_VERSION = "gate1-v1"
EXTRACTION_DISCLOSURE = (
    "Local deterministic preview from captured passages only. "
    "The production atomic extractor remains unqualified and was not run."
)

TIERS = ("tier1", "tier2", "tier3", "watch", "muted")
TIER_LABELS = {
    "tier1": "Tier 1 · Priority",
    "tier2": "Tier 2 · Core",
    "tier3": "Tier 3 · Peripheral",
    "watch": "Watch · Exploratory",
    "muted": "Muted",
}
DEFAULT_TIER = "tier2"

CROPS = {
    "berry-strawberry": "strawberry",
    "berry-blueberry": "blueberry",
    "berry-raspberry": "raspberry",
    "berry-blackberry": "blackberry",
    "strawberry": "strawberry",
    "blueberry": "blueberry",
    "raspberry": "raspberry",
    "blackberry": "blackberry",
}
CROP_LABELS = {
    "strawberry": "Strawberry",
    "blueberry": "Blueberry",
    "raspberry": "Raspberry",
    "blackberry": "Blackberry",
}

WINDOWS = {
    "today": 1,
    "7d": 7,
    "30d": 30,
}

SOURCE_KIND = {
    "company_website": "official",
    "company_press_release": "official",
    "company_catalog": "official",
    "industry_podcast": "social",
    "discovered_media": "social",
    "patent_record": "registry",
    "plant_breeders_rights_record": "registry",
    "government_registry": "registry",
    "court_record": "registry",
    "news_search": "article",
    "trade_press": "article",
    "academic": "article",
}

BODY_TO_AVAILABILITY = {
    "body_available": "full",
    "body_partial": "partial",
    "description_only": "excerpt_only",
    "transcript_available": "partial",
    "body_unavailable": "metadata_only",
    "access_limited": "blocked",
    "interstitial": "blocked",
}

NAV = (
    ("Today", "/today"),
    ("Following", "/following"),
    ("Saved", "/saved"),
    ("Entities", "/entities/company"),
    ("People", "/people"),
    ("Statements", "/today?state=judged"),
    ("Landscapes", "/landscapes"),
    ("Research Ops", "/review"),
    ("Settings", "/guide"),
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,200}$")


def state_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / STATE_FILENAME


def empty_state() -> dict[str, Any]:
    return {
        "decisions": {},
        "entity_tiers": {},
        "statements": {},
        "people": [],
        "updated_at": None,
    }


def load_state(inbox_dir: Path) -> dict[str, Any]:
    path = state_path(inbox_dir)
    if not path.exists():
        return empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_state()
    if not isinstance(payload, dict):
        return empty_state()
    base = empty_state()
    base.update({key: payload.get(key, base[key]) for key in base})
    return base


def save_state(inbox_dir: Path, state: dict[str, Any]) -> None:
    path = state_path(inbox_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def parse_filters(params: dict[str, Any]) -> dict[str, str]:
    def _one(name: str, allowed: set[str] | None = None) -> str:
        raw = str(params.get(name) or "").strip()
        if allowed is not None:
            return raw if raw in allowed else ""
        return raw[:120]

    return {
        "window": _one("window", set(WINDOWS)),
        "tier": _one("tier", set(TIERS)),
        "entity": _one("entity"),
        "crop": _one("crop", set(CROP_LABELS)),
        "source": _one("source", {"article", "official", "social", "registry", "fallback"}),
        "state": _one("state", {"unread", "read", "saved", "judged"}),
        "q": _one("q"),
        "item": _one("item"),
        "sort": _one("sort", {"rank", "chrono"}) or "rank",
    }


def filters_query(filters: dict[str, str], **extra: str) -> str:
    merged = {key: value for key, value in filters.items() if value}
    merged.update({key: value for key, value in extra.items() if value})
    return urlencode(merged)


def crop_keys(record: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for raw in record.get("berry_ids") or []:
        key = CROPS.get(str(raw), "")
        if key and key not in found:
            found.append(key)
    return found


def source_kind(record: dict[str, Any]) -> str:
    return SOURCE_KIND.get(str(record.get("source_type") or ""), "article")


def body_availability(record: dict[str, Any]) -> str:
    body = classify_source_body(record)
    return BODY_TO_AVAILABILITY.get(body.get("state") or "", "metadata_only")


def captured_passages(record: dict[str, Any]) -> list[str]:
    content = reader_content(record)
    if content.get("contaminated"):
        return []
    passages: list[str] = []
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    for row in article.get("paragraphs") or []:
        if isinstance(row, dict):
            text = decode_html_text(row.get("text") or "").strip()
            if text:
                passages.append(text)
    full = decode_html_text(article.get("full_text") or "").strip()
    if full and full not in passages:
        passages.append(full)
    summary = decode_html_text(content.get("summary") or record.get("summary") or "").strip()
    if summary and summary not in passages:
        passages.append(summary)
    return passages


def safe_image_url(record: dict[str, Any]) -> str:
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    raw = str(article.get("image_url") or record.get("image_url") or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        return ""
    host = parsed.hostname.lower()
    if any(token in host for token in ("logo", "favicon", "linkedin", "facebook", "instagram")):
        return ""
    return raw


def entity_tier(entity_id: str, state: dict[str, Any]) -> str:
    value = str((state.get("entity_tiers") or {}).get(entity_id) or DEFAULT_TIER)
    return value if value in TIERS else DEFAULT_TIER


def decision_for(item_id: str, state: dict[str, Any]) -> dict[str, Any]:
    raw = (state.get("decisions") or {}).get(item_id) or {}
    reaction = raw.get("reaction")
    if reaction not in {"up", "down", None}:
        reaction = None
    return {
        "reaction": reaction,
        "saved": bool(raw.get("saved")),
        "read": bool(raw.get("read")),
    }


def present_entities(
    record: dict[str, Any],
    entities_by_id: dict[str, dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in record.get("entity_ids") or []:
        entity = entities_by_id.get(str(entity_id)) or {}
        name = entity.get("name") or str(entity_id)
        entity_type = entity.get("entity_type") or "company"
        rows.append(
            {
                "id": str(entity_id),
                "name": name,
                "entity_type": entity_type,
                "tier": entity_tier(str(entity_id), state),
                "verification_status": entity.get("status") or "unknown",
                "profile_url": f"/entities/{entity_type}/{entity_id}",
                "monogram": _monogram(name),
            }
        )
    return rows


def card_family(record: dict[str, Any], *, lead: bool, rank: int) -> str:
    kind = source_kind(record)
    if kind == "registry":
        return "registry"
    if kind == "social" or str(record.get("source_type") or "") == "company_catalog":
        return "social"
    if lead:
        return "lead"
    if rank > 8:
        return "dense"
    return "standard"


def present_item(
    record: dict[str, Any],
    *,
    entities_by_id: dict[str, dict[str, Any]],
    state: dict[str, Any],
    filters: dict[str, str],
    lead: bool = False,
    rank: int = 0,
) -> dict[str, Any]:
    item_id = str(record.get("id") or "")
    entities = present_entities(record, entities_by_id, state)
    crops = crop_keys(record)
    availability = body_availability(record)
    kind = source_kind(record)
    if availability in {"blocked", "metadata_only", "excerpt_only"} and kind == "article":
        display_kind = "fallback" if availability != "excerpt_only" else "article"
    else:
        display_kind = kind
    decision = decision_for(item_id, state)
    statements = [
        row
        for row in (state.get("statements") or {}).get(item_id) or []
        if row.get("statement_state") != "removed"
    ]
    published = str(record.get("published_date") or "")
    query = filters_query(filters, item=item_id)
    return {
        "id": item_id,
        "headline": decode_html_text(record.get("title") or item_id),
        "deck": decode_html_text(record.get("summary") or "")[:280],
        "source_name": record.get("source_name") or "Unknown source",
        "source_type": record.get("source_type") or "",
        "source_kind": kind,
        "display_kind": display_kind,
        "source_url": record.get("source_url") or "",
        "published_at": published,
        "captured_at": record.get("captured_date") or "",
        "crops": crops,
        "crop_labels": [CROP_LABELS[c] for c in crops if c in CROP_LABELS],
        "geographies": [str(g) for g in (record.get("geography_ids") or [])],
        "entities": entities,
        "highest_tier": _highest_tier([row["tier"] for row in entities]),
        "body_availability": availability,
        "availability_label": _availability_label(availability),
        "image_url": safe_image_url(record),
        "family": card_family(record, lead=lead, rank=rank),
        "decision": decision,
        "statement_count": len(statements),
        "statements": statements,
        "extraction_pending": bool(decision["reaction"] == "up" and not statements),
        "reader_href": f"/today?{query}" if query else f"/today?item={item_id}",
        "profile_href": entities[0]["profile_url"] if entities else "",
        "content_type": kind,
        "passages": captured_passages(record),
        "record": record,
    }


def _highest_tier(tiers: list[str]) -> str:
    order = {name: index for index, name in enumerate(TIERS)}
    present = [tier for tier in tiers if tier in order]
    return min(present, key=lambda tier: order[tier]) if present else DEFAULT_TIER


def _availability_label(value: str) -> str:
    return {
        "full": "Full captured body",
        "partial": "Partial capture",
        "excerpt_only": "Excerpt / synopsis only",
        "metadata_only": "Metadata only",
        "blocked": "Blocked / not readable in-app",
        "error": "Capture error",
    }.get(value, value)


def _monogram(name: str) -> str:
    parts = [part for part in re.split(r"\s+", name.strip()) if part]
    if len(parts) >= 2:
        return (parts[0][:1] + parts[1][:1]).upper()
    return (name[:2] or "BI").upper()


def _in_window(published: str, window: str, today: date) -> bool:
    if not window:
        return True
    days = WINDOWS.get(window)
    if not days:
        return True
    if not published:
        return False
    try:
        when = date.fromisoformat(published[:10])
    except ValueError:
        return False
    return (today - when).days <= days and when <= today


def _matches(item: dict[str, Any], filters: dict[str, str]) -> bool:
    if filters["tier"] and item["highest_tier"] != filters["tier"]:
        return False
    if filters["entity"] and filters["entity"] not in {row["id"] for row in item["entities"]}:
        return False
    if filters["crop"] and filters["crop"] not in item["crops"]:
        return False
    if filters["source"]:
        if filters["source"] == "fallback":
            if item["body_availability"] not in {"blocked", "metadata_only", "excerpt_only"}:
                return False
        elif item["source_kind"] != filters["source"]:
            return False
    decision = item["decision"]
    if filters["state"] == "unread" and decision["read"]:
        return False
    if filters["state"] == "read" and not decision["read"]:
        return False
    if filters["state"] == "saved" and not decision["saved"]:
        return False
    if filters["state"] == "judged" and decision["reaction"] not in {"up", "down"}:
        return False
    if not filters["state"] and decision["reaction"] == "down":
        return False
    needle = filters["q"].casefold()
    if needle:
        hay = " ".join(
            [
                item["headline"],
                item["deck"],
                item["source_name"],
                " ".join(row["name"] for row in item["entities"]),
            ]
        ).casefold()
        if needle not in hay:
            return False
    return True


def build_feed(
    *,
    evidence: list[dict[str, Any]],
    entities: list[dict[str, Any]] | dict[str, dict[str, Any]],
    state: dict[str, Any],
    filters: dict[str, str],
    today: date | None = None,
    limit: int = 48,
) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()
    entities_by_id = (
        entities
        if isinstance(entities, dict)
        else {str(row.get("id")): row for row in entities if row.get("id")}
    )
    ranked: list[dict[str, Any]] = []
    for record in evidence:
        if record.get("status") and record.get("status") != "published":
            continue
        if record.get("id") in SEED_FIXTURE_EVIDENCE_IDS:
            continue
        if "structural" in (record.get("tags") or []):
            continue
        published = str(record.get("published_date") or "")
        if not _in_window(published, filters["window"], today):
            continue
        item = present_item(
            record,
            entities_by_id=entities_by_id,
            state=state,
            filters=filters,
        )
        if not _matches(item, filters):
            continue
        ranked.append(item)

    order = {name: index for index, name in enumerate(TIERS)}
    ranked.sort(key=lambda item: (item["published_at"] or "", item["id"]), reverse=True)
    if filters["sort"] != "chrono":
        ranked.sort(
            key=lambda item: (
                item["decision"]["reaction"] == "down",
                order.get(item["highest_tier"], 9),
                item["body_availability"] not in {"full", "partial", "excerpt_only"},
            )
        )

    visible = ranked[:limit]
    if visible:
        visible[0] = present_item(
            visible[0]["record"],
            entities_by_id=entities_by_id,
            state=state,
            filters=filters,
            lead=True,
            rank=0,
        )
        for index, item in enumerate(visible[1:], start=1):
            visible[index] = present_item(
                item["record"],
                entities_by_id=entities_by_id,
                state=state,
                filters=filters,
                lead=False,
                rank=index,
            )

    selected = None
    if filters["item"]:
        selected = next((item for item in visible if item["id"] == filters["item"]), None)
        if selected is None:
            raw = next((row for row in evidence if str(row.get("id")) == filters["item"]), None)
            if raw is not None:
                selected = present_item(
                    raw,
                    entities_by_id=entities_by_id,
                    state=state,
                    filters=filters,
                )
    if selected is None and visible:
        selected = visible[0]

    ids = [item["id"] for item in visible]
    prev_id = next_id = ""
    if selected and selected["id"] in ids:
        index = ids.index(selected["id"])
        prev_id = ids[index - 1] if index > 0 else ""
        next_id = ids[index + 1] if index + 1 < len(ids) else ""
    query = filters_query(filters)
    def _href(item_id: str = "", **extra: str) -> str:
        suffix = filters_query(filters, item=item_id, **extra)
        return f"/today?{suffix}" if suffix else "/today"

    families = {item["family"] for item in visible}
    kinds = {item["source_kind"] for item in visible}
    return {
        "cards": [{key: value for key, value in item.items() if key != "record"} for item in visible],
        "selected": None
        if selected is None
        else {key: value for key, value in selected.items() if key != "record"},
        "prev_id": prev_id,
        "next_id": next_id,
        "prev_href": _href(prev_id) if prev_id else "",
        "next_href": _href(next_id) if next_id else "",
        "close_href": _href(),
        "filters": filters,
        "filter_query": query,
        "tier_hrefs": {key: _href(tier=key) for key in TIERS},
        "count": len(visible),
        "total_matched": len(ranked),
        "nav": NAV,
        "tier_labels": TIER_LABELS,
        "crop_labels": CROP_LABELS,
        "disclosure": (
            "Stored published evidence — not a live multi-lane poll. "
            "Optional discovery keys are unused on this page. "
            "Social platforms are not actively collected."
        ),
        "has_article": "article" in kinds,
        "has_official": "official" in kinds,
        "has_social_style": "social" in families or "social" in kinds,
        "has_fallback": any(
            item["body_availability"] in {"blocked", "metadata_only", "excerpt_only"}
            for item in visible
        ),
        "extraction_disclosure": EXTRACTION_DISCLOSURE,
    }


def apply_decision(
    inbox_dir: Path,
    *,
    item_id: str,
    action: str,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not SAFE_ID_RE.match(item_id):
        raise ValueError("invalid item id")
    state = load_state(inbox_dir)
    decisions = dict(state.get("decisions") or {})
    current = dict(decisions.get(item_id) or {"reaction": None, "saved": False, "read": False})
    if action == "thumbs_up":
        current["reaction"] = "up"
        current["read"] = True
    elif action == "thumbs_down":
        current["reaction"] = "down"
        current["read"] = True
    elif action == "clear_reaction":
        current["reaction"] = None
    elif action == "save":
        current["saved"] = not bool(current.get("saved"))
    elif action == "read":
        current["read"] = True
    elif action == "unread":
        current["read"] = False
    else:
        raise ValueError("unknown action")
    decisions[item_id] = current
    state["decisions"] = decisions

    statements = dict(state.get("statements") or {})
    if current.get("reaction") == "up":
        if item_id not in statements:
            record = next((row for row in (evidence or []) if str(row.get("id")) == item_id), None)
            statements[item_id] = extract_statements(record or {"id": item_id})
    elif current.get("reaction") != "up":
        # Undo removes the working set but never writes trusted data.
        statements.pop(item_id, None)
    state["statements"] = statements
    save_state(inbox_dir, state)
    return {
        "decision": current,
        "statements": [
            row for row in statements.get(item_id) or [] if row.get("statement_state") != "removed"
        ],
        "extraction_disclosure": EXTRACTION_DISCLOSURE,
        "muted_world": False,
    }


def extract_statements(record: dict[str, Any]) -> list[dict[str, Any]]:
    availability = body_availability(record)
    if availability in {"blocked", "error"}:
        return []
    passages = captured_passages(record)
    if not passages:
        return []
    sentences: list[str] = []
    for passage in passages:
        bits = [part.strip() for part in _SENTENCE_RE.split(passage) if part.strip()]
        sentences.extend(bits if bits else [passage])
    picked: list[str] = []
    for sentence in sentences:
        if len(sentence) < 40:
            continue
        if sentence in picked:
            continue
        picked.append(sentence)
        if len(picked) >= 6:
            break
    if not picked:
        picked = passages[:3]
    now = datetime.now(UTC).isoformat(timespec="seconds")
    item_id = str(record.get("id") or "item")
    crops = crop_keys(record)
    entity_ids = [str(eid) for eid in (record.get("entity_ids") or [])]
    rows: list[dict[str, Any]] = []
    for index, sentence in enumerate(picked, start=1):
        rows.append(
            {
                "id": f"{item_id}::stmt-{index}",
                "feed_item_id": item_id,
                "statement_text": sentence,
                "original_extraction_text": sentence,
                "supporting_passages": [sentence],
                "entity_ids": entity_ids,
                "person_ids": [],
                "crops": crops,
                "geographies": [str(g) for g in (record.get("geography_ids") or [])],
                "topics": list(record.get("tags") or []),
                "statement_type": "captured_assertion",
                "importance_state": "normal",
                "statement_state": "trusted_editable",
                "confidence": "excerpt_supported" if availability != "full" else "body_supported",
                "uncertainty_note": EXTRACTION_DISCLOSURE,
                "extraction_model": EXTRACTION_MODEL,
                "extraction_version": EXTRACTION_VERSION,
                "created_at": now,
                "updated_at": now,
                "analyst_edit_history": [],
            }
        )
    return rows


def mutate_statement(
    inbox_dir: Path,
    *,
    statement_id: str,
    action: str,
    text: str | None = None,
) -> dict[str, Any] | None:
    state = load_state(inbox_dir)
    statements = dict(state.get("statements") or {})
    found = None
    parent = None
    for item_id, rows in statements.items():
        for row in rows:
            if row.get("id") == statement_id:
                found = dict(row)
                parent = item_id
                break
        if found is not None:
            break
    if found is None or parent is None:
        return None
    now = datetime.now(UTC).isoformat(timespec="seconds")
    history = list(found.get("analyst_edit_history") or [])
    if action == "edit":
        next_text = (text or "").strip()
        if not next_text:
            raise ValueError("empty statement")
        history.append(
            {
                "at": now,
                "from": found.get("statement_text"),
                "to": next_text,
            }
        )
        found["statement_text"] = next_text
        found["updated_at"] = now
        found["analyst_edit_history"] = history
    elif action == "important":
        found["importance_state"] = "important"
        found["updated_at"] = now
    elif action == "demote":
        found["importance_state"] = "demoted"
        found["updated_at"] = now
    elif action == "remove":
        found["statement_state"] = "removed"
        found["updated_at"] = now
    elif action == "restore":
        found["statement_state"] = "trusted_editable"
        found["updated_at"] = now
    else:
        raise ValueError("unknown statement action")
    updated = []
    for row in statements[parent]:
        updated.append(found if row.get("id") == statement_id else row)
    statements[parent] = updated
    state["statements"] = statements
    save_state(inbox_dir, state)
    return found


def set_entity_tier(inbox_dir: Path, *, entity_id: str, tier: str) -> str:
    if tier not in TIERS:
        raise ValueError("invalid tier")
    if not SAFE_ID_RE.match(entity_id):
        raise ValueError("invalid entity id")
    state = load_state(inbox_dir)
    tiers = dict(state.get("entity_tiers") or {})
    tiers[entity_id] = tier
    state["entity_tiers"] = tiers
    save_state(inbox_dir, state)
    return tier


def statements_for_entity(state: dict[str, Any], entity_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in (state.get("statements") or {}).values():
        for row in group:
            if entity_id in (row.get("entity_ids") or []) and row.get("statement_state") != "removed":
                rows.append(row)
    return rows


def playground_fixtures() -> list[dict[str, Any]]:
    """Visibly isolated design-system fixtures. Never mixed into /today."""
    return [
        {
            "id": "fixture-lead-article",
            "status": "published",
            "title": "Fall Creek Spain reaches 14 million blueberry plants after 10 years",
            "summary": "The nursery marks a decade in Spain and reports 14 million plants from a two-hectare start in 2016.",
            "source_name": "FreshPlaza",
            "source_type": "trade_press",
            "source_url": "https://example.test/fall-creek-spain",
            "published_date": "2026-05-26",
            "berry_ids": ["berry-blueberry"],
            "entity_ids": ["company-fall-creek-farm-and-nursery"],
            "geography_ids": ["geography-spain"],
            "article": {
                "paragraphs": [
                    {
                        "text": (
                            "Fall Creek Farm & Nursery marked 10 years of operations in Spain. "
                            "Established in 2016 with a two-hectare harvest using plug material from the U.S., "
                            "the operation has expanded to 14 million blueberry plants."
                        )
                    }
                ]
            },
        },
        {
            "id": "fixture-official",
            "status": "published",
            "title": "Our history — Fall Creek",
            "summary": "Company history page describing breeding and nursery operations.",
            "source_name": "Fall Creek",
            "source_type": "company_website",
            "published_date": "2026-03-01",
            "berry_ids": ["berry-blueberry"],
            "entity_ids": ["company-fall-creek-farm-and-nursery"],
        },
        {
            "id": "fixture-social-style",
            "status": "published",
            "title": "Sekoya Fiesta catalog drop",
            "summary": "Official catalog page for a blueberry variety platform.",
            "source_name": "Fall Creek catalog",
            "source_type": "company_catalog",
            "published_date": "2026-04-12",
            "berry_ids": ["berry-blueberry"],
            "entity_ids": ["company-fall-creek-farm-and-nursery"],
        },
        {
            "id": "fixture-registry",
            "status": "published",
            "title": "USPP032267 — DrisBlueTwentyOne",
            "summary": "Plant patent record (registry). Excluded from competitor counts.",
            "source_name": "USPTO",
            "source_type": "patent_record",
            "published_date": "2025-11-02",
            "berry_ids": ["berry-blueberry"],
            "entity_ids": ["company-driscolls"],
        },
        {
            "id": "fixture-blocked",
            "status": "published",
            "title": "Paywalled trade note",
            "summary": "Please log in to continue. Subscribe to continue reading.",
            "source_name": "Trade desk",
            "source_type": "trade_press",
            "published_date": "2026-06-02",
            "berry_ids": ["berry-strawberry"],
            "article": {"paragraphs": [{"text": "Please log in to continue. Subscribe to continue reading."}]},
        },
    ]
