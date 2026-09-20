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
from app.services.clock import utc_today
from app.services.html_text import decode_html_text
from app.services.source_body import classify_source_body, reader_content

STATE_FILENAME = "feed_first_state.json"
BACKUP_SUBDIR = "feed_first_backups"
BACKUP_KEEP = 8
EXTRACTION_MODEL = "local-deterministic-preview"
EXTRACTION_VERSION = "gate3-v2"
EXTRACTION_DISCLOSURE = (
    "Local deterministic preview from captured passages only. "
    "The production atomic extractor remains unqualified and was not run."
)
PENDING_CONFIRMATION = "pending_confirmation"
TRUSTED_ANALYST = "trusted_analyst"
DOSSIER_ELIGIBLE_STATES = {TRUSTED_ANALYST, "conflicting", "superseded"}
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uac00-\ud7af]")
_TOPIC_WORDS = {
    "berry",
    "berries",
    "strawberry",
    "blueberry",
    "raspberry",
    "blackberry",
    "grower",
    "nursery",
    "hectare",
    "hectares",
    "variety",
    "varieties",
    "harvest",
    "breeding",
    "fruit",
}

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
    "90d": 90,
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
    ("Entities", "/entities"),
    ("People", "/people"),
    ("Statements", "/statements"),
    ("Landscapes", "/landscapes"),
    ("This week", "/week"),
    ("Learn", "/learn"),
    ("War Room", "/war-room"),
    ("Watchtower", "/watchtower"),
    ("Research Ops", "/research-ops"),
    ("Settings", "/settings"),
)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_STOP = {
    "the",
    "a",
    "an",
    "of",
    "in",
    "for",
    "and",
    "to",
    "on",
    "with",
    "from",
    "after",
    "this",
    "that",
}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,200}$")


def state_path(inbox_dir: Path) -> Path:
    return Path(inbox_dir) / STATE_FILENAME


def empty_state() -> dict[str, Any]:
    return {
        "decisions": {},
        "reaction_events": [],
        "entity_tiers": {},
        "statements": {},
        "research_runs": {},
        "research_proposals": {},
        "dossier_assessments": {},
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


def snapshot_state(inbox_dir: Path) -> Path:
    """Copy analyst state so a rollback rehearsal can restore it."""
    state = load_state(inbox_dir)
    folder = Path(inbox_dir) / BACKUP_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = folder / f"feed_first_state-{stamp}.json"
    payload = dict(state)
    payload["snapshot_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    snapshots = sorted(folder.glob("feed_first_state-*.json"))
    for stale in snapshots[:-BACKUP_KEEP]:
        stale.unlink(missing_ok=True)
    return path


def latest_snapshot(inbox_dir: Path) -> Path | None:
    folder = Path(inbox_dir) / BACKUP_SUBDIR
    snapshots = sorted(folder.glob("feed_first_state-*.json"))
    return snapshots[-1] if snapshots else None


def restore_state(inbox_dir: Path, snapshot: Path | None = None) -> dict[str, Any]:
    """Replace working state from a snapshot. Does not touch data/evidence."""
    path = snapshot or latest_snapshot(inbox_dir)
    if path is None or not path.exists():
        raise ValueError("no snapshot")
    backup_root = (Path(inbox_dir) / BACKUP_SUBDIR).resolve()
    resolved = path.resolve()
    if backup_root not in resolved.parents and resolved.parent != backup_root:
        raise ValueError("snapshot must live under feed_first_backups")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("unreadable snapshot") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid snapshot")
    state = empty_state()
    state.update({key: payload.get(key, state[key]) for key in state})
    save_state(inbox_dir, state)
    return state


def is_analyst_english(text: str) -> bool:
    """True when the copy is already English enough for the analyst feed."""
    sample = str(text or "")
    if not sample.strip():
        return True
    cjk = len(_CJK_RE.findall(sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    if cjk >= 8 and cjk > latin:
        return False
    if cjk >= 4 and latin == 0:
        return False
    return True


def analyst_lede(
    *,
    window: str,
    today: date,
    count: int,
    held_non_english: int = 0,
    translation_pending: int = 0,
) -> str:
    day = today.isoformat()
    if window == "today":
        line = f"{count} stor{'y' if count == 1 else 'ies'} published {day}."
    elif window == "7d":
        line = f"{count} stor{'y' if count == 1 else 'ies'} from the last 7 days, ending {day}."
    elif window == "30d":
        line = f"{count} stor{'y' if count == 1 else 'ies'} from the last 30 days, ending {day}."
    else:
        line = f"{count} stor{'y' if count == 1 else 'ies'} for the companies you watch."
    if held_non_english:
        line += f" {held_non_english} translated into English."
    if translation_pending:
        line += f" {translation_pending} awaiting English translation."
    return line


def empty_feed_copy(window: str, today: date) -> dict[str, str]:
    day = today.isoformat()
    if window == "7d":
        return {
            "title": "No stories in the last 7 days",
            "body": f"Nothing published for watched companies between {(today - timedelta(days=7)).isoformat()} and {day}.",
        }
    if window == "30d":
        return {
            "title": "No stories in the last 30 days",
            "body": f"Nothing published for watched companies between {(today - timedelta(days=30)).isoformat()} and {day}.",
        }
    return {
        "title": "No stories published today",
        "body": f"Nothing published for watched companies on {day}. Widen the window to 7 or 30 days.",
    }


def parse_filters(params: dict[str, Any]) -> dict[str, str]:
    def _one(name: str, allowed: set[str] | None = None) -> str:
        raw = str(params.get(name) or "").strip()
        if allowed is not None:
            return raw if raw in allowed else ""
        return raw[:120]

    if "window" in params:
        raw_window = str(params.get("window") or "").strip()
        window = raw_window if raw_window in WINDOWS else ""
    else:
        window = "today"
    return {
        "window": window,
        "tier": _one("tier", set(TIERS)),
        "entity": _one("entity"),
        "crop": _one("crop", set(CROP_LABELS)),
        "source": _one("source", {"article", "official", "social", "registry", "fallback"}),
        "state": _one("state", {"unread", "read", "saved", "judged"}),
        "q": _one("q"),
        "item": _one("item"),
        "person": _one("person"),
        "geography": _one("geography"),
        "sort": _one("sort", {"rank", "chrono"}) or "rank",
    }


def filters_query(filters: dict[str, str], **extra: str) -> str:
    merged = {key: value for key, value in filters.items() if value}
    merged.update({key: value for key, value in extra.items() if value})
    return urlencode(merged)


def active_filter_chips(filters: dict[str, str]) -> list[dict[str, str]]:
    """Removable chips for non-default filters. Clearing one leaves the rest."""
    labels = {
        "window": f"Window {filters.get('window') or 'all'}",
        "tier": TIER_LABELS.get(filters.get("tier") or "", filters.get("tier") or ""),
        "crop": CROP_LABELS.get(filters.get("crop") or "", filters.get("crop") or ""),
        "source": (filters.get("source") or "").replace("_", " "),
        "state": filters.get("state") or "",
        "entity": filters.get("entity") or "",
        "person": filters.get("person") or "",
        "geography": filters.get("geography") or "",
        "q": f"Search {filters.get('q')}" if filters.get("q") else "",
        "sort": "Newest first" if filters.get("sort") == "chrono" else "",
    }
    chips: list[dict[str, str]] = []
    for key, label in labels.items():
        value = str(filters.get(key) or "")
        if not value or not label:
            continue
        if key == "window" and value == "today":
            continue
        if key == "sort" and value == "rank":
            continue
        cleared = dict(filters)
        cleared[key] = ""
        suffix = filters_query(cleared)
        chips.append(
            {
                "key": key,
                "value": value,
                "label": label,
                "href": f"/today?{suffix}" if suffix else "/today",
            }
        )
    return chips


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


def topic_tokens(title: str, summary: str = "") -> set[str]:
    words = {
        word
        for word in re.findall(r"[a-z0-9]+", f"{title} {summary}".casefold())
        if len(word) >= 4 and word not in _STOP
    }
    return words | _TOPIC_WORDS


def passages_on_topic(passages: list[str], *, title: str, summary: str = "") -> list[str]:
    tokens = topic_tokens(title, summary)
    kept: list[str] = []
    for passage in passages:
        hay = passage.casefold()
        if any(re.search(rf"\b{re.escape(token)}\b", hay) for token in tokens):
            kept.append(passage)
    return kept


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
    title = str(record.get("title") or "")
    on_topic = passages_on_topic(passages, title=title, summary=summary)
    if on_topic:
        return on_topic
    if summary and passages_on_topic([summary], title=title, summary=summary):
        return [summary]
    return []


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


def _is_dossier_eligible(row: dict[str, Any]) -> bool:
    return str(row.get("statement_state") or "") in DOSSIER_ELIGIBLE_STATES


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
                "verification_status": entity.get("verification_status")
                or entity.get("status")
                or "unknown",
                "candidate": bool(entity.get("candidate"))
                or str(entity.get("verification_status") or "") == "candidate-review"
                or str(entity.get("status") or "") == "unverified",
                "is_registry": bool(entity.get("is_registry")),
                "profile_url": f"/entities/{entity_type}/{entity_id}?view=feed",
                "monogram": _monogram(name),
            }
        )
    return rows


def card_family(record: dict[str, Any], *, lead: bool, rank: int) -> str:
    kind = source_kind(record)
    if int(record.get("cluster_size") or 1) > 1 and not lead:
        return "cluster"
    if kind == "registry":
        return "registry"
    if kind == "social" or str(record.get("source_type") or "") == "company_catalog":
        return "social"
    if lead:
        return "lead"
    if rank > 8:
        return "dense"
    return "standard"


def present_people(record: dict[str, Any], people_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pid in record.get("person_ids") or []:
        person = people_by_id.get(str(pid))
        if not person:
            continue
        rows.append(
            {
                "id": person["id"],
                "canonical_name": person.get("canonical_name") or person["id"],
                "profile_url": person.get("profile_url") or f"/people/{person['id']}",
                "monitoring_coverage": person.get("monitoring_coverage") or "discovery-only",
                "social_coverage": person.get("social_coverage") or "provider-unavailable",
            }
        )
    return rows


def present_item(
    record: dict[str, Any],
    *,
    entities_by_id: dict[str, dict[str, Any]],
    state: dict[str, Any],
    filters: dict[str, str],
    lead: bool = False,
    rank: int = 0,
    people_by_id: dict[str, dict[str, Any]] | None = None,
    capture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.services.feed_first_reader import merge_capture

    record = merge_capture(record, capture)
    item_id = str(record.get("id") or "")
    entities = present_entities(record, entities_by_id, state)
    people = present_people(record, people_by_id or {})
    crops = crop_keys(record)
    availability = body_availability(record)
    if capture and capture.get("availability"):
        availability = str(capture.get("availability") or availability)
    kind = source_kind(record)
    if availability in {"blocked", "metadata_only", "excerpt_only"} and kind == "article":
        display_kind = "fallback" if availability != "excerpt_only" else "article"
    else:
        display_kind = kind
    decision = decision_for(item_id, state)
    statements = list((state.get("statements") or {}).get(item_id) or [])
    published, date_uncertain = published_date_state(record.get("published_date") or "")
    query = filters_query(filters, item=item_id)
    geography_chips = []
    for geo_id in record.get("geography_ids") or []:
        geo = entities_by_id.get(str(geo_id)) or {}
        if str(geo.get("entity_type") or "") not in {"", "geography"} and geo:
            continue
        name = str(geo.get("name") or geo_id)
        geography_chips.append(
            {
                "id": str(geo_id),
                "name": name,
                "href": f"/geographies/{geo_id}",
            }
        )
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
        "date_uncertain": date_uncertain,
        "captured_at": record.get("captured_date") or "",
        "crops": crops,
        "crop_labels": [CROP_LABELS[c] for c in crops if c in CROP_LABELS],
        "geographies": [str(g) for g in (record.get("geography_ids") or [])],
        "geography_chips": geography_chips,
        "entities": entities,
        "people": people,
        "highest_tier": _highest_tier([row["tier"] for row in entities]),
        "body_availability": availability,
        "availability_label": _availability_label(availability),
        "reader_modes": list((record.get("reader_capture") or {}).get("reader_modes") or ["structured_fallback"]),
        "frame_allowed": bool((record.get("reader_capture") or {}).get("frame_allowed")),
        "capture_method": (record.get("reader_capture") or {}).get("method") or "",
        "trust_state": record.get("trust_state") or "",
        "review_state": record.get("review_state") or "",
        "acquisition_lane": record.get("acquisition_lane") or "",
        "image_url": safe_image_url(record),
        "images": list(record.get("images") or (capture or {}).get("images") or []),
        "family": card_family(record, lead=lead, rank=rank),
        "decision": decision,
        "statement_count": sum(1 for row in statements if _is_dossier_eligible(row)),
        "statements": statements,
        "extraction_pending": bool(decision["reaction"] == "up" and not statements),
        "reader_href": f"/today?{query}" if query else f"/today?item={item_id}",
        "profile_href": entities[0]["profile_url"] if entities else "",
        "content_type": kind,
        "content_kind": str(
            (record.get("content_kind") or (record.get("reader_capture") or {}).get("content_kind") or kind)
        ),
        "passages": captured_passages(record),
        "story_cluster_id": record.get("story_cluster_id") or "",
        "cluster_size": int(record.get("cluster_size") or 1),
        "cluster_sources": list(record.get("cluster_sources") or []),
        "corroborating_sources": corroborating_sources(record),
        "muted": item_is_muted({"entities": entities}),
        "translated": bool(record.get("translated")),
        "translation_pending": bool(record.get("translation_pending")),
        "source_language": str(record.get("source_language") or ""),
        "original_title": str(record.get("original_title") or ""),
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
        "pdf": "PDF · metadata / text route",
    }.get(value, value)


def muted_entity_ids(state: dict[str, Any]) -> set[str]:
    return {
        str(entity_id)
        for entity_id, tier in (state.get("entity_tiers") or {}).items()
        if str(tier) == "muted"
    }


def item_is_muted(item: dict[str, Any]) -> bool:
    entities = [row for row in (item.get("entities") or []) if row.get("id")]
    if not entities:
        return False
    return all(str(row.get("tier") or "") == "muted" for row in entities)


def corroborating_sources(record: dict[str, Any]) -> list[dict[str, str]]:
    """Related cluster sources stay independent. They do not replace support."""
    lead_url = str(record.get("source_url") or "").strip()
    rows: list[dict[str, str]] = []
    seen: set[str] = {lead_url}
    for raw in record.get("cluster_sources") or []:
        if isinstance(raw, dict):
            name = str(raw.get("name") or raw.get("source") or "").strip()
            url = str(raw.get("url") or "").strip()
            lane = str(raw.get("lane") or raw.get("provider") or "").strip()
        else:
            name = str(raw).strip()
            url = ""
            lane = ""
        key = url or name
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({"name": name or key, "url": url, "lane": lane, "independent": "true"})
    return rows[:8]


def _monogram(name: str) -> str:
    parts = [part for part in re.split(r"\s+", name.strip()) if part]
    if len(parts) >= 2:
        return (parts[0][:1] + parts[1][:1]).upper()
    return (name[:2] or "BI").upper()


def published_date_state(published: Any) -> tuple[str, bool]:
    raw = str(published or "").strip()
    if not raw:
        return "", True
    try:
        when = date.fromisoformat(raw[:10])
    except ValueError:
        return raw, True
    return when.isoformat(), False


def _in_window(published: str, window: str, today: date) -> bool:
    if not window:
        return True
    stamp, uncertain = published_date_state(published)
    if uncertain or not stamp:
        return False
    when = date.fromisoformat(stamp)
    if when > today:
        return False
    if window == "today":
        return when == today
    days = WINDOWS.get(window)
    if not days:
        return True
    return (today - when).days <= days


def _facet_counts(items: list[dict[str, Any]]) -> dict[str, Any]:
    tiers: dict[str, int] = {}
    crops: dict[str, int] = {}
    states = {"unread": 0, "read": 0, "saved": 0, "judged": 0}
    for item in items:
        tier = str(item.get("highest_tier") or "")
        if tier:
            tiers[tier] = tiers.get(tier, 0) + 1
        for crop in item.get("crops") or []:
            crops[str(crop)] = crops.get(str(crop), 0) + 1
        decision = item.get("decision") or {}
        if decision.get("read"):
            states["read"] += 1
        else:
            states["unread"] += 1
        if decision.get("saved"):
            states["saved"] += 1
        if decision.get("reaction") in {"up", "down"}:
            states["judged"] += 1
    return {"tier": tiers, "crop": crops, "state": states, "total": len(items)}


def _matches(item: dict[str, Any], filters: dict[str, str]) -> bool:
    if item_is_muted(item):
        searching = bool(filters.get("q"))
        explicit_muted = filters.get("tier") == "muted"
        entity_lookup = bool(filters.get("entity")) and filters["entity"] in {
            row["id"] for row in item.get("entities") or []
        }
        if not (searching or explicit_muted or entity_lookup):
            return False
    if filters["tier"] and item["highest_tier"] != filters["tier"]:
        return False
    if filters["entity"] and filters["entity"] not in {row["id"] for row in item["entities"]}:
        return False
    if filters.get("person") and filters["person"] not in {row["id"] for row in item.get("people") or []}:
        return False
    if filters.get("geography") and filters["geography"] not in {
        row["id"] for row in item.get("geography_chips") or []
    } and filters["geography"] not in set(item.get("geographies") or []):
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
    disclosure: str | None = None,
    people: list[dict[str, Any]] | None = None,
    captures: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    today = today or utc_today()
    entities_by_id = (
        entities
        if isinstance(entities, dict)
        else {str(row.get("id")): row for row in entities if row.get("id")}
    )
    people_by_id = {str(row.get("id")): row for row in (people or []) if row.get("id")}
    captures = captures or {}

    def _present(record: dict[str, Any], *, lead: bool = False, rank: int = 0) -> dict[str, Any]:
        item_id = str(record.get("id") or "")
        return present_item(
            record,
            entities_by_id=entities_by_id,
            state=state,
            filters=filters,
            lead=lead,
            rank=rank,
            people_by_id=people_by_id,
            capture=captures.get(item_id),
        )

    windowed: list[dict[str, Any]] = []
    held_non_english = 0
    translation_pending = 0
    for record in evidence:
        if record.get("status") and record.get("status") != "published":
            continue
        if record.get("id") in SEED_FIXTURE_EVIDENCE_IDS:
            continue
        if "structural" in (record.get("tags") or []):
            continue
        if record.get("translated"):
            held_non_english += 1
        elif record.get("translation_pending"):
            translation_pending += 1
        published = str(record.get("published_date") or "")
        if not _in_window(published, filters["window"], today):
            continue
        windowed.append(_present(record))
    facets = _facet_counts(windowed)
    ranked = [item for item in windowed if _matches(item, filters)]

    order = {name: index for index, name in enumerate(TIERS)}
    ranked.sort(key=lambda item: (item["published_at"] or "", item["id"]), reverse=True)
    if filters["sort"] != "chrono":
        ranked.sort(
            key=lambda item: (
                item["decision"]["reaction"] == "down",
                0 if item.get("entities") else 1,
                0 if item.get("source_kind") == "official" else 1,
                order.get(item["highest_tier"], 9),
                item["body_availability"] not in {"full", "partial", "excerpt_only"},
                -(len(item.get("deck") or "")),
            )
        )

    visible = ranked[:limit]
    if visible:
        visible[0] = _present(visible[0]["record"], lead=True, rank=0)
        for index, item in enumerate(visible[1:], start=1):
            visible[index] = _present(item["record"], lead=False, rank=index)

    selected = None
    if filters["item"]:
        selected = next((item for item in visible if item["id"] == filters["item"]), None)
        if selected is None:
            raw = next((row for row in evidence if str(row.get("id")) == filters["item"]), None)
            if raw is not None:
                selected = _present(raw)
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
    geo_options: dict[str, str] = {}
    for item in windowed:
        for chip in item.get("geography_chips") or []:
            geo_options[str(chip["id"])] = str(chip.get("name") or chip["id"])
    geography_options = [
        {"id": geo_id, "name": name}
        for geo_id, name in sorted(geo_options.items(), key=lambda row: row[1].casefold())
    ]
    chips = active_filter_chips(filters)
    geo_filter = str(filters.get("geography") or "")
    if geo_filter:
        for chip in chips:
            if chip["key"] == "geography":
                chip["label"] = geo_options.get(geo_filter, geo_filter)
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
        "facet_counts": facets,
        "filter_chips": chips,
        "geography_options": geography_options,
        "nav": NAV,
        "tier_labels": TIER_LABELS,
        "crop_labels": CROP_LABELS,
        "disclosure": disclosure
        or analyst_lede(
            window=filters.get("window") or "today",
            today=today,
            count=len(visible),
            held_non_english=held_non_english,
            translation_pending=translation_pending,
        ),
        "held_non_english": held_non_english,
        "translation_pending": translation_pending,
        "empty_copy": empty_feed_copy(filters.get("window") or "today", today),
        "today": today.isoformat(),
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
    people: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not SAFE_ID_RE.match(item_id):
        raise ValueError("invalid item id")
    state = load_state(inbox_dir)
    decisions = dict(state.get("decisions") or {})
    current = dict(decisions.get(item_id) or {"reaction": None, "saved": False, "read": False})
    previous_reaction = current.get("reaction")
    if action == "thumbs_up":
        snapshot_state(inbox_dir)
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
    if action in {"thumbs_up", "thumbs_down", "clear_reaction"} and previous_reaction != current.get("reaction"):
        events = list(state.get("reaction_events") or [])
        events.append(
            {
                "id": f"reaction-{item_id}-{len(events) + 1}",
                "item_id": item_id,
                "action": action,
                "prior_reaction": previous_reaction,
                "reaction": current.get("reaction"),
                "occurred_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "purpose": "ranking_feedback",
            }
        )
        state["reaction_events"] = events[-500:]

    statements = dict(state.get("statements") or {})
    if current.get("reaction") == "up":
        if item_id not in statements:
            from app.services.feed_first_reader import load_capture, merge_capture

            record = next((row for row in (evidence or []) if str(row.get("id")) == item_id), None)
            record = merge_capture(record or {"id": item_id}, load_capture(inbox_dir, item_id))
            statements[item_id] = extract_statements(record, people=people)
    elif current.get("reaction") != "up":
        # Undo archives only unconfirmed working candidates. Confirmed
        # statements require an explicit retraction so lineage is preserved.
        rows = list(statements.get(item_id) or [])
        confirmed = [row for row in rows if _is_dossier_eligible(row)]
        if confirmed:
            statements[item_id] = confirmed
        else:
            statements.pop(item_id, None)
    state["statements"] = statements
    save_state(inbox_dir, state)
    return {
        "decision": current,
        "statements": list(statements.get(item_id) or []),
        "extraction_disclosure": EXTRACTION_DISCLOSURE,
        "muted_world": False,
    }


_LOGIN_WALL = re.compile(
    r"please log in|subscribe to continue|sign in to read|create a free account",
    re.IGNORECASE,
)
_QUESTION = re.compile(r"^\s*(who|what|when|where|why|how)\b", re.IGNORECASE)
_QUANTITY = re.compile(
    r"\b(\d[\d,\.]*\s*(million|billion|percent|%|hectare|hectares|acre|acres|plants?|growers?))\b",
    re.IGNORECASE,
)
_DATEISH = re.compile(r"\b(20\d{2}|january|february|march|april|may|june|july|august|september|october|november|december)\b", re.IGNORECASE)
_LAUNCH = re.compile(r"\b(launch|launched|unveiled|released|opened|expanded|expansion)\b", re.IGNORECASE)
_PARTNER = re.compile(r"\b(partner|partnership|license|licensing|acquired|acquisition|joint venture)\b", re.IGNORECASE)


def _statement_type(sentence: str) -> str:
    if _QUANTITY.search(sentence):
        return "quantity"
    if _PARTNER.search(sentence):
        return "partnership"
    if _LAUNCH.search(sentence):
        return "launch"
    if _DATEISH.search(sentence):
        return "dated_event"
    return "captured_assertion"


def _title_tokens(title: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", (title or "").casefold())
        if len(word) >= 4 and word not in _STOP
    }


def _sentence_mentions_item(sentence: str, title: str) -> bool:
    tokens = _title_tokens(title)
    if not tokens:
        return True
    hay = sentence.casefold()
    return any(re.search(rf"\b{re.escape(token)}\b", hay) for token in tokens)


def _mentioned_entity_ids(sentence: str, record: dict[str, Any]) -> list[str]:
    hay = sentence.casefold()
    mentioned: list[str] = []
    for raw in record.get("entity_ids") or []:
        entity_id = str(raw)
        slug = re.sub(r"^(company|geography|berry|variety)-", "", entity_id).replace("-", " ")
        if len(slug) >= 4 and slug in hay:
            mentioned.append(entity_id)
    return mentioned or [str(eid) for eid in (record.get("entity_ids") or [])]


def _atomic_sentences(passages: list[str], *, title: str = "") -> list[str]:
    sentences: list[str] = []
    for passage in passages:
        bits = [part.strip() for part in _SENTENCE_RE.split(passage) if part.strip()]
        sentences.extend(bits if bits else [passage])
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for sentence in sentences:
        if len(sentence) < 40 or len(sentence) > 320:
            continue
        if _LOGIN_WALL.search(sentence) or _QUESTION.search(sentence):
            continue
        if "http://" in sentence or "https://" in sentence:
            continue
        if not _sentence_mentions_item(sentence, title):
            continue
        if sentence in seen:
            continue
        seen.add(sentence)
        score = 0
        if _QUANTITY.search(sentence):
            score += 3
        if _DATEISH.search(sentence):
            score += 2
        if _LAUNCH.search(sentence) or _PARTNER.search(sentence):
            score += 2
        if any(crop in sentence.casefold() for crop in CROP_LABELS):
            score += 1
        scored.append((score, sentence))
    scored.sort(key=lambda row: (-row[0], sentences.index(row[1]) if row[1] in sentences else 99))
    picked = [sentence for _score, sentence in scored[:6]]
    return picked


def _structured_details(sentence: str) -> dict[str, list[str]]:
    return {
        "quantities": [match.group(0) for match in _QUANTITY.finditer(sentence)],
        "dates": [match.group(0) for match in _DATEISH.finditer(sentence)],
    }


def extract_statements(
    record: dict[str, Any],
    *,
    people: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    availability = body_availability(record)
    if availability in {"blocked", "error"}:
        return []
    passages = captured_passages(record)
    if not passages:
        return []
    if all(_LOGIN_WALL.search(passage or "") for passage in passages):
        return []
    picked = _atomic_sentences(passages, title=str(record.get("title") or ""))
    if not picked:
        return []
    now = datetime.now(UTC).isoformat(timespec="seconds")
    item_id = str(record.get("id") or "item")
    crops = crop_keys(record)
    from app.services.people_watchlist import match_people

    rows: list[dict[str, Any]] = []
    for index, sentence in enumerate(picked, start=1):
        matched_people = match_people(sentence, people or [])
        locators = _support_locators(record, sentence)
        rows.append(
            {
                "id": f"{item_id}::stmt-{index}",
                "feed_item_id": item_id,
                "statement_text": sentence,
                "original_extraction_text": sentence,
                "supporting_passages": [sentence],
                "support_locators": locators,
                "entity_ids": _mentioned_entity_ids(sentence, record),
                "person_ids": [row["id"] for row in matched_people],
                "crops": crops,
                "geographies": _mentioned_entity_ids(
                    sentence, {"entity_ids": record.get("geography_ids") or []}
                ),
                "topics": list(record.get("tags") or []),
                "statement_type": _statement_type(sentence),
                "structured_details": _structured_details(sentence),
                "importance_state": "normal",
                "statement_state": PENDING_CONFIRMATION,
                "selected": False,
                "origin": "feed_thumbsup_extraction",
                "confidence": "excerpt_supported" if availability != "full" else "body_supported",
                "uncertainty_note": EXTRACTION_DISCLOSURE,
                "extraction_model": EXTRACTION_MODEL,
                "extraction_version": EXTRACTION_VERSION,
                "created_at": now,
                "updated_at": now,
                "analyst_edit_history": [],
                "decision_history": [],
                "corroborating_sources": corroborating_sources(record),
            }
        )
    return rows


def _support_locators(record: dict[str, Any], excerpt: str) -> list[dict[str, Any]]:
    """Locate exact support in captured paragraphs without fragile display text."""
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    paragraphs = article.get("paragraphs") if isinstance(article.get("paragraphs"), list) else []
    for position, raw in enumerate(paragraphs):
        if isinstance(raw, dict):
            text = decode_html_text(raw.get("text") or "")
            paragraph_index = int(
                raw.get("index") if raw.get("index") is not None else position
            )
        else:
            text = decode_html_text(raw)
            paragraph_index = position
        start = text.find(excerpt)
        if start >= 0:
            return [
                {
                    "medium": "article_paragraph",
                    "paragraph_index": paragraph_index,
                    "start_offset": start,
                    "end_offset": start + len(excerpt),
                    "exact": excerpt,
                }
            ]
    summary = decode_html_text(record.get("summary") or "")
    start = summary.find(excerpt)
    if start >= 0:
        return [
            {
                "medium": "summary",
                "paragraph_index": -1,
                "start_offset": start,
                "end_offset": start + len(excerpt),
                "exact": excerpt,
            }
        ]
    return []


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
    decision_history = list(found.get("decision_history") or [])
    if action == "approve":
        found["updated_at"] = now
    elif action == "edit":
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
    elif action == "select":
        found["selected"] = True
        found["updated_at"] = now
    elif action == "deselect":
        found["selected"] = False
        found["updated_at"] = now
    elif action == "confirm":
        if found.get("statement_state") not in {PENDING_CONFIRMATION, "proposed"}:
            raise ValueError("statement is not awaiting confirmation")
        decision_history.append(
            {
                "at": now,
                "action": "confirmed",
                "from": found.get("statement_state"),
                "to": TRUSTED_ANALYST,
                "surface": "reader_evidence_lens",
            }
        )
        found["statement_state"] = TRUSTED_ANALYST
        found["selected"] = False
        found["confirmed_at"] = now
        found["decision_history"] = decision_history
        found["updated_at"] = now
    elif action == "reject":
        decision_history.append(
            {
                "at": now,
                "action": "rejected",
                "from": found.get("statement_state"),
                "to": "rejected",
                "surface": "reader_evidence_lens",
            }
        )
        found["statement_state"] = "rejected"
        found["selected"] = False
        found["decision_history"] = decision_history
        found["updated_at"] = now
    elif action == "retract":
        if not _is_dossier_eligible(found):
            raise ValueError("only confirmed statements can be retracted")
        decision_history.append(
            {
                "at": now,
                "action": "retracted",
                "from": found.get("statement_state"),
                "to": "removed",
                "surface": "reader_evidence_lens",
            }
        )
        found["statement_state"] = "removed"
        found["decision_history"] = decision_history
        found["updated_at"] = now
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
        found["statement_state"] = (
            TRUSTED_ANALYST if found.get("confirmed_at") else PENDING_CONFIRMATION
        )
        found["updated_at"] = now
    else:
        raise ValueError("unknown statement action")
    found["review_state"] = "reviewed"
    found["reviewed_at"] = now
    updated = []
    for row in statements[parent]:
        updated.append(found if row.get("id") == statement_id else row)
    statements[parent] = updated
    state["statements"] = statements
    save_state(inbox_dir, state)
    return found


def mutate_statements(
    inbox_dir: Path,
    *,
    statement_ids: list[str],
    action: str,
) -> list[dict[str, Any]]:
    if action not in {"confirm", "reject"}:
        raise ValueError("invalid batch action")
    results: list[dict[str, Any]] = []
    for statement_id in dict.fromkeys(str(value) for value in statement_ids if value):
        updated = mutate_statement(
            inbox_dir,
            statement_id=statement_id,
            action=action,
        )
        if updated is not None:
            results.append(updated)
    return results


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
            if entity_id in (row.get("entity_ids") or []) and _is_dossier_eligible(row):
                rows.append(row)
    return rows


def statements_for_person(state: dict[str, Any], person_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in (state.get("statements") or {}).values():
        for row in group:
            if person_id in (row.get("person_ids") or []) and _is_dossier_eligible(row):
                rows.append(row)
    return rows


def trusted_statements(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in (state.get("statements") or {}).values():
        for row in group:
            if _is_dossier_eligible(row):
                rows.append(row)
    return rows


def statements_index(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = trusted_statements(state)

    def _stamp(row: dict[str, Any]) -> str:
        return str(row.get("updated_at") or row.get("created_at") or "")

    important = [row for row in rows if row.get("importance_state") == "important"]
    rest = [row for row in rows if row.get("importance_state") != "important"]
    important.sort(key=_stamp, reverse=True)
    rest.sort(key=_stamp, reverse=True)
    return [*important, *rest]


def statement_is_reviewed(row: dict[str, Any]) -> bool:
    return bool(
        row.get("review_state") == "reviewed"
        or row.get("analyst_edit_history")
        or row.get("statement_state") == "removed"
        or row.get("importance_state") in {"important", "demoted"}
    )


def statements_review_index(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in (state.get("statements") or {}).values():
        for raw in group:
            row = dict(raw)
            row["human_reviewed"] = statement_is_reviewed(row)
            rows.append(row)
    rows.sort(
        key=lambda row: (
            bool(row.get("human_reviewed")),
            str(row.get("updated_at") or row.get("created_at") or ""),
        )
    )
    return rows


def week_statements(state: dict[str, Any], *, today: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in statements_index(state):
        stamp = str(row.get("created_at") or row.get("updated_at") or "")[:10]
        try:
            when = date.fromisoformat(stamp)
        except ValueError:
            continue
        if 0 <= (today - when).days <= 7:
            rows.append(row)
    return rows


def live_story_briefs(
    records: list[dict[str, Any]] | None,
    *,
    today: date | None = None,
    window_days: int | None = None,
) -> list[dict[str, Any]]:
    """Reuse one-story-once live clusters as briefs. LIVE / UNREVIEWED, not trusted."""
    rows: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        published = str(record.get("published_date") or "")[:10]
        if today is not None and window_days is not None:
            try:
                when = date.fromisoformat(published)
            except ValueError:
                continue
            if not (0 <= (today - when).days <= window_days):
                continue
        rows.append(
            {
                "id": str(record.get("id") or ""),
                "title": record.get("title") or "",
                "summary": record.get("summary") or "",
                "source_name": record.get("source_name") or "",
                "source_type": record.get("source_type") or "",
                "published_date": published,
                "entity_ids": [str(eid) for eid in (record.get("entity_ids") or []) if eid],
                "cluster_size": int(record.get("cluster_size") or 1),
                "cluster_sources": list(record.get("cluster_sources") or []),
                "acquisition_lane": record.get("acquisition_lane") or "",
                "trust_state": record.get("trust_state") or "LIVE",
                "kind": "live_story",
            }
        )
    rows.sort(key=lambda row: (row["published_date"], int(row["cluster_size"])), reverse=True)
    return rows


def week_crop_rows(stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {crop: [] for crop in CROP_LABELS}
    for story in stories:
        hay = f"{story.get('title') or ''} {story.get('summary') or ''}".casefold()
        for crop, label in CROP_LABELS.items():
            if crop in hay or label.casefold() in hay:
                buckets[crop].append(story)
    return [
        {
            "id": crop,
            "name": CROP_LABELS[crop],
            "count": len(rows),
            "stories": rows[:6],
            "href": f"/today?window=7d&crop={crop}",
        }
        for crop, rows in buckets.items()
    ]


def week_variety_rows(
    stories: list[dict[str, Any]],
    *,
    entities: list[dict[str, Any]] | None,
    statements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(row.get("id")): row for row in (entities or []) if row.get("id")}
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for group in (stories, statements):
        for item in group:
            for raw in item.get("entity_ids") or []:
                entity_id = str(raw)
                if entity_id in seen:
                    continue
                entity = by_id.get(entity_id) or {}
                if not entity_id.startswith("variety-") and entity.get("entity_type") != "variety":
                    continue
                seen.add(entity_id)
                name = str(entity.get("name") or entity_id.removeprefix("variety-").replace("-", " "))
                rows.append(
                    {
                        "id": entity_id,
                        "name": name,
                        "href": f"/entities/variety/{entity_id}",
                    }
                )
    return rows[:24]


def week_model(
    state: dict[str, Any],
    *,
    today: date,
    live_records: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    statements = week_statements(state, today=today)
    stories = live_story_briefs(live_records, today=today, window_days=7)
    return {
        "statements": statements,
        "stories": stories,
        "statement_count": len(statements),
        "story_count": len(stories),
        "disclosure": (
            f"{len(statements)} trusted statement(s) and {len(stories)} live stor"
            f"{'y' if len(stories) == 1 else 'ies'} from the last 7 days."
        ),
        "varieties": week_variety_rows(stories, entities=entities, statements=statements),
        "by_crop": week_crop_rows(stories),
        "ask_href": "/research?q=What+changed+this+week+across+watched+berry+companies+and+varieties%3F",
    }


def saved_items(
    *,
    evidence: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    state: dict[str, Any],
    people: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    filters = parse_filters({"window": "", "state": "saved"})
    feed = build_feed(
        evidence=evidence,
        entities=entities,
        state=state,
        filters=filters,
        people=people,
    )
    return feed["cards"]


def landscape_profile_url(entity_id: str, entity: dict[str, Any] | None = None) -> str:
    """Company profiles stay on Berry OS. Crops and geographies filter Today."""
    eid = str(entity_id or "")
    etype = str((entity or {}).get("entity_type") or "")
    if eid.startswith("berry-") or etype in {"berry", "crop"}:
        crop = eid.removeprefix("berry-") or str((entity or {}).get("id") or "").removeprefix("berry-")
        return f"/today?crop={crop}" if crop else "/today"
    if eid.startswith("geography-") or etype == "geography":
        return f"/today?geography={eid}" if eid else "/today"
    if eid in {"", "unmatched"}:
        return "/today"
    if eid.startswith("company-") or etype in {"company", "brand", "breeding_program", ""}:
        return f"/entities/company/{eid}"
    return f"/entities/{etype}/{eid}"


def landscapes_model(
    *,
    state: dict[str, Any],
    entities: list[dict[str, Any]],
    counts: dict[str, Any],
    live_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    by_id = {str(row.get("id")): row for row in entities if row.get("id")}
    statements = trusted_statements(state)
    stories = live_story_briefs(live_records)
    grouped: dict[str, dict[str, Any]] = {}

    def _bucket(entity_id: str) -> dict[str, Any]:
        if entity_id not in grouped:
            entity = by_id.get(entity_id) or {}
            grouped[entity_id] = {
                "id": entity_id,
                "name": entity.get("name") or entity_id,
                "profile_url": landscape_profile_url(entity_id, entity),
                "statement_count": 0,
                "story_count": 0,
                "statements": [],
                "stories": [],
            }
        return grouped[entity_id]

    for row in statements:
        for entity_id in row.get("entity_ids") or ["unmatched"]:
            bucket = _bucket(str(entity_id))
            bucket["statement_count"] += 1
            if len(bucket["statements"]) < 6:
                bucket["statements"].append(row)
    for story in stories:
        for entity_id in story.get("entity_ids") or ["unmatched"]:
            bucket = _bucket(str(entity_id))
            bucket["story_count"] += 1
            if len(bucket["stories"]) < 6:
                bucket["stories"].append(story)
    companies = list(grouped.values())
    companies.sort(
        key=lambda row: (-row["statement_count"], -row["story_count"], row["name"].casefold())
    )
    return {
        "companies": companies,
        "statement_count": len(statements),
        "story_count": len(stories),
        "tracked_companies": counts.get("tracked_companies") or 0,
        "disclosure": (
            "Landscapes reuse trusted Today thumbs-up statements and live one-story-once clusters as briefs. "
            "Live stories stay LIVE / UNREVIEWED until thumbs-up. Save is not trust. "
            "Legacy landscape remains at /landscapes?view=legacy."
        ),
    }


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
