"""Daily Intelligence Briefing V2 — production read model (Slice 1).

Derives briefing cards from canonical published evidence, entity repositories,
competitor landscape coverage, and existing body-quality classifiers.

Hard rules:
- Never load prototypes/daily-intelligence-briefing-v2 fixtures.
- Never invent article bodies, implications, or competitive claims.
- Capture date never substitutes for publication date when assigning recency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse

from app.services.berries.landscape import SEED_FIXTURE_EVIDENCE_IDS
from app.services.competitor_landscape import (
    DEFAULT_REGION_CODE_LABELS,
    LandscapeFilters,
    filters_to_query,
)
from app.services.source_body import classify_source_body, reader_content

RECENCY_CURRENT_BANDS = ("0-30", "31-60", "61-90")
RECENCY_LABELS = {
    "0-30": "0–30 days",
    "31-60": "31–60 days",
    "61-90": "61–90 days",
    "older": "Older historical context",
    "unknown_publication_date": "Unknown publication date",
}

ATTENTION_REASONS = {
    "body_unavailable": "Body unavailable",
    "cookie_consent_page": "Cookie / consent page",
    "bot_wall": "Bot wall",
    "interstitial": "Consent / interstitial / bot wall",
    "access_limited": "Access limited",
    "description_only": "Description only — not full body",
    "pending_review": "Pending review",
    "missing_entity_linkage": "Missing entity linkage",
    "unknown_publication_date": "Unknown publication date",
    "aging_classification": "Aging classification",
    "manual_acquisition_required": "Manual acquisition required",
    "retryable_acquisition": "Retryable acquisition failure",
    "source_configured_never_run": "Source configured but never run",
    "source_strategy_pending": "Source strategy pending",
}

READABLE_BODY_STATES = frozenset({"body_available", "body_partial", "transcript_available"})
INTERSTITIAL_STATES = frozenset({"interstitial"})
SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,200}$")

ENTITY_TYPE_PREFIXES = (
    ("company-", "company"),
    ("brand-", "brand"),
    ("variety-", "variety"),
    ("breeding_program-", "breeding_program"),
    ("breeding-program-", "breeding_program"),
    ("university-", "university"),
    ("public_entity-", "public_entity"),
    ("public-entity-", "public_entity"),
    ("retailer-", "retailer"),
    ("geography-", "geography"),
    ("patent-", "patent"),
    ("trait-", "trait"),
    ("berry-", "berry"),
)


def _parse_date(raw: Any) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def publication_date_of(record: dict[str, Any]) -> date | None:
    return _parse_date(record.get("published_date") or record.get("publication_date"))


def capture_date_of(record: dict[str, Any]) -> date | None:
    return _parse_date(record.get("captured_date") or record.get("capture_date"))


def recency_band_for(published: date | None, *, today: date) -> str:
    if published is None:
        return "unknown_publication_date"
    days = (today - published).days
    if days < 0:
        days = 0
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "older"


def is_safe_record_id(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text or ".." in text or "/" in text or "\\" in text:
        return False
    return bool(SAFE_RECORD_ID_RE.match(text))


def safe_external_url(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return text


def _infer_entity_type(entity_id: str, entity: dict[str, Any]) -> str:
    explicit = str(entity.get("entity_type") or entity.get("type") or "").strip()
    if explicit:
        return explicit
    for prefix, entity_type in ENTITY_TYPE_PREFIXES:
        if entity_id.startswith(prefix):
            return entity_type
    return "entity"


def _berry_labels(record: dict[str, Any]) -> list[str]:
    berries: list[str] = []
    for key in record.get("berry_ids") or []:
        text = str(key).replace("berry-", "").replace("_", " ").strip()
        if text and text not in berries:
            berries.append(text)
    for tag in record.get("tags") or []:
        token = str(tag).casefold()
        if token in {"blueberry", "strawberry", "raspberry", "blackberry"} and token not in berries:
            berries.append(token)
    return berries


def _topic_labels(record: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for tag in record.get("tags") or []:
        text = str(tag).strip()
        if text and text.casefold() not in {"blueberry", "strawberry", "raspberry", "blackberry"}:
            out.append(text)
    return out[:8]


def _region_labels(record: dict[str, Any], entities_by_id: dict[str, dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    geo_ids = [str(x) for x in (record.get("geography_ids") or [])]
    for entity_id in record.get("entity_ids") or []:
        eid = str(entity_id)
        if eid.startswith("geography-"):
            geo_ids.append(eid)
    for geo_id in geo_ids:
        if geo_id in seen:
            continue
        seen.add(geo_id)
        entity = entities_by_id.get(geo_id) or {}
        name = str(entity.get("name") or geo_id.replace("geography-", "").replace("-", " ")).strip()
        if name and name not in labels:
            labels.append(name)
    for region in record.get("regions") or []:
        text = str(region).strip()
        if text and text not in labels:
            labels.append(text)
    return labels[:8]


def _entity_refs(record: dict[str, Any], entities_by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for entity_id in record.get("entity_ids") or []:
        eid = str(entity_id)
        if eid.startswith("geography-"):
            continue
        entity = entities_by_id.get(eid) or {}
        entity_type = _infer_entity_type(eid, entity)
        name = str(entity.get("name") or eid)
        refs.append(
            {
                "id": eid,
                "name": name,
                "entity_type": entity_type,
                "profile_url": f"/entities/{entity_type}/{eid}",
            }
        )
    return refs


def landscape_handoff_url(
    *,
    berry: str | None = None,
    regions: Iterable[str] | None = None,
    tier: str | None = None,
    entity_id: str | None = None,
    from_briefing: bool = True,
) -> str:
    company = ""
    if entity_id and str(entity_id).startswith("company-"):
        company = str(entity_id)
    filters = LandscapeFilters(
        berry=(berry or "blueberry"),
        regions=tuple(regions or ()),
        tier=tier or "",
        company=company,
    )
    query = filters_to_query(filters, include_company=True)
    if from_briefing:
        query = f"{query}&from=today" if query else "from=today"
    return f"/competitors?{query}"


def _is_trusted_published(record: dict[str, Any]) -> bool:
    if str(record.get("status") or "").casefold() != "published":
        return False
    if record.get("auto_captured") and record.get("validated") is False:
        return False
    return True


@dataclass
class BriefingFilters:
    berry: str = ""
    region: str = ""
    entity_id: str = ""
    topic: str = ""
    source: str = ""
    attention: str = ""
    reader: str = ""
    recency: str = ""

    def to_query(self, *, include_reader: bool = True) -> str:
        pairs: list[tuple[str, str]] = []
        if self.berry:
            pairs.append(("berry", self.berry))
        if self.region:
            pairs.append(("region", self.region))
        if self.entity_id:
            pairs.append(("entity", self.entity_id))
        if self.topic:
            pairs.append(("topic", self.topic))
        if self.source:
            pairs.append(("source", self.source))
        if self.attention:
            pairs.append(("attention", self.attention))
        if self.recency:
            pairs.append(("recency", self.recency))
        if include_reader and self.reader:
            pairs.append(("reader", self.reader))
        return urlencode(pairs)


def parse_briefing_filters(params: dict[str, Any] | None) -> BriefingFilters:
    raw = params or {}

    def first(*keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                if not value:
                    continue
                text = str(value[0]).strip()
            else:
                text = str(value).strip()
            if text:
                return text
        return ""

    reader = first("reader")
    if reader and not is_safe_record_id(reader):
        reader = ""

    return BriefingFilters(
        berry=first("berry").casefold().removeprefix("berry-"),
        region=first("region", "regions"),
        entity_id=first("entity", "company", "focus"),
        topic=first("topic"),
        source=first("source"),
        attention=first("attention"),
        reader=reader,
        recency=first("recency", "band"),
    )


def _matches_filters(item: dict[str, Any], filters: BriefingFilters) -> bool:
    if filters.berry:
        berries = {b.casefold() for b in item.get("berries") or []}
        berry_ids = {str(b).casefold() for b in item.get("berry_ids") or []}
        if (
            filters.berry not in berries
            and f"berry-{filters.berry}" not in berry_ids
            and filters.berry not in berry_ids
        ):
            return False
    if filters.region:
        regions = {str(r).casefold() for r in item.get("regions") or []}
        if filters.region.casefold() not in regions:
            return False
    if filters.entity_id:
        ids = {str(e.get("id") if isinstance(e, dict) else e) for e in item.get("entities") or []}
        ids |= {str(x) for x in item.get("entity_ids") or []}
        if filters.entity_id not in ids:
            return False
    if filters.topic:
        topics = {str(t).casefold() for t in item.get("topics") or []}
        if filters.topic.casefold() not in topics:
            return False
    if filters.source:
        blob = f"{item.get('source_id') or ''} {item.get('source_name') or ''}".casefold()
        if filters.source.casefold() not in blob:
            return False
    if filters.recency and item.get("recency_band") != filters.recency:
        return False
    return True


def present_briefing_item(
    record: dict[str, Any],
    *,
    entities_by_id: dict[str, dict[str, Any]],
    today: date,
) -> dict[str, Any]:
    body = classify_source_body(record)
    published = publication_date_of(record)
    captured = capture_date_of(record)
    band = recency_band_for(published, today=today)
    entities = _entity_refs(record, entities_by_id)
    berries = _berry_labels(record)
    regions = _region_labels(record, entities_by_id)
    primary_berry = berries[0] if berries else "blueberry"
    company_id = next((e["id"] for e in entities if e["id"].startswith("company-")), "")
    observed = (record.get("summary") or "").strip() or None
    implication = (record.get("why_it_matters") or record.get("why_it_matters") or "").strip() or None
    usable = bool(body.get("usable_in_app")) and body.get("state") in READABLE_BODY_STATES
    if body.get("state") in INTERSTITIAL_STATES:
        observed = None
        usable = False
        implication = None
    record_id = str(record.get("id") or "")
    return {
        "id": record_id,
        "kind": "evidence",
        "headline": str(record.get("title") or record.get("headline") or "Untitled"),
        "canonical_url": safe_external_url(record.get("source_url") or record.get("canonical_url")),
        "source_id": str(record.get("source_id") or ""),
        "source_name": str(record.get("source_name") or "Source"),
        "publication_date": published.isoformat() if published else None,
        "capture_date": captured.isoformat() if captured else None,
        "recency_band": band,
        "recency_label": RECENCY_LABELS[band],
        "berries": berries,
        "berry_ids": list(record.get("berry_ids") or []),
        "regions": regions,
        "topics": _topic_labels(record),
        "entities": entities,
        "entity_ids": [e["id"] for e in entities],
        "readable_body_state": body["state"],
        "readable_body_label": body["label"],
        "usable_in_app": usable,
        "content_quality_result": body["state"],
        "acquisition_outcome": body["state"],
        "review_trust_state": (
            "trusted_published" if _is_trusted_published(record) else str(record.get("status") or "unknown")
        ),
        "observed_change": observed if usable else None,
        "analyst_implication": implication if implication else None,
        "implication_available": bool(implication) and body.get("state") not in INTERSTITIAL_STATES,
        "supporting_evidence_ids": [record_id] if record_id else [],
        "profile_url": entities[0]["profile_url"] if entities else None,
        "landscape_url": landscape_handoff_url(berry=primary_berry, entity_id=company_id or None),
        "attention_reason": None,
        "attention_label": None,
        "current_or_historical": (
            "current"
            if band in RECENCY_CURRENT_BANDS
            else ("unknown" if band == "unknown_publication_date" else "historical")
        ),
        "body_warning": body.get("warning") or "",
        "reader_href": f"/today?reader={record_id}",
        "intelligence_href": f"/intelligence/{record_id}",
        "image_url": "",
        "prototype_synthetic": False,
        "fixture_dependency": None,
    }


def classify_briefing_bucket(item: dict[str, Any]) -> str:
    if item["recency_band"] == "unknown_publication_date":
        return "unknown_date"
    if item["recency_band"] == "older":
        return "historical"
    trusted = item["review_trust_state"] == "trusted_published"
    usable = item["usable_in_app"]
    if trusted and usable and item["recency_band"] in RECENCY_CURRENT_BANDS:
        return "what_changed"
    return "needs_attention"


def attach_attention_metadata(item: dict[str, Any]) -> dict[str, Any]:
    row = dict(item)
    reason = None
    state = row.get("readable_body_state")
    label = str(row.get("readable_body_label") or "").casefold()
    if state in INTERSTITIAL_STATES:
        blob = " ".join(
            [
                label,
                str(row.get("reader_summary") or ""),
                str(row.get("body_warning") or ""),
                str(row.get("headline") or ""),
            ]
        ).casefold()
        if "bot" in blob or "security service" in blob or "verify you are" in blob:
            reason = "bot_wall"
        elif "cookie" in blob or "consent" in blob:
            reason = "cookie_consent_page"
        else:
            reason = "interstitial"
    elif state == "body_unavailable":
        reason = "body_unavailable"
    elif state == "access_limited":
        reason = "access_limited"
    elif state == "description_only":
        reason = "description_only"
    elif not row.get("entity_ids") and row.get("kind") != "source":
        reason = "missing_entity_linkage"
    elif row.get("recency_band") == "unknown_publication_date":
        reason = "unknown_publication_date"
    elif row.get("recency_band") in {"61-90", "older"} and not row.get("usable_in_app"):
        reason = "aging_classification"
    row["attention_reason"] = reason
    row["attention_label"] = ATTENTION_REASONS.get(reason or "", reason or "Needs attention")
    if reason in {
        "body_unavailable",
        "cookie_consent_page",
        "bot_wall",
        "interstitial",
        "access_limited",
    }:
        row["observed_change"] = None
        row["analyst_implication"] = None
        row["implication_available"] = False
    return row


def attach_reader_payload(item: dict[str, Any], record: dict[str, Any] | None) -> dict[str, Any]:
    """Attach sanitized reader fields. Never returns raw publisher HTML."""
    row = dict(item)
    if record is None:
        row["reader_mode"] = "missing"
        row["reader_notice"] = "This record could not be loaded."
        row["reader_paragraphs"] = []
        row["reader_transcript"] = ""
        row["reader_summary"] = ""
        return row

    content = reader_content(record)
    body = classify_source_body(record)
    paragraphs: list[str] = []
    transcript = ""

    if content.get("contaminated") or body.get("state") in INTERSTITIAL_STATES:
        mode = "interstitial"
    elif body.get("state") == "body_available":
        mode = "readable"
        text = body.get("body") or ""
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    elif body.get("state") == "body_partial":
        mode = "partial"
        text = body.get("body") or ""
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    elif body.get("state") == "transcript_available":
        mode = "transcript"
        transcript = str(body.get("transcript_text") or body.get("excerpt") or "").strip()
    elif body.get("state") == "description_only":
        mode = "description_only"
    elif body.get("state") == "access_limited":
        mode = "access_limited"
    else:
        mode = "body_unavailable"

    row["reader_mode"] = mode
    row["reader_notice"] = content.get("notice") or body.get("warning") or ""
    row["reader_paragraphs"] = paragraphs
    row["reader_transcript"] = transcript
    row["reader_summary"] = content.get("summary") or ""
    if mode in {"interstitial", "body_unavailable", "access_limited", "description_only", "missing"}:
        row["observed_change"] = None
        if mode == "interstitial":
            row["analyst_implication"] = None
            row["implication_available"] = False
    return row


def build_source_attention_items(sources: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in sources or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        if row.get("enabled") is False:
            continue
        last_checked = row.get("last_checked_at") or row.get("last_run_at")
        last_status = str(row.get("last_status") or "").casefold()
        name = str(row.get("label") or row.get("name") or row.get("id"))
        if not last_checked:
            reason = "source_configured_never_run"
        elif last_status in {"pending", "strategy_pending", "planned"}:
            reason = "source_strategy_pending"
        else:
            continue
        items.append(
            {
                "id": f"source-attention-{row.get('id')}",
                "kind": "source",
                "headline": name,
                "canonical_url": safe_external_url(row.get("url")),
                "source_id": str(row.get("id")),
                "source_name": name,
                "publication_date": None,
                "capture_date": None,
                "recency_band": "unknown_publication_date",
                "recency_label": RECENCY_LABELS["unknown_publication_date"],
                "berries": [],
                "berry_ids": [],
                "regions": [],
                "topics": [],
                "entities": [],
                "entity_ids": [],
                "readable_body_state": "body_unavailable",
                "readable_body_label": "SOURCE ATTENTION",
                "usable_in_app": False,
                "content_quality_result": "source_attention",
                "acquisition_outcome": "source_attention",
                "review_trust_state": "source_ops",
                "observed_change": None,
                "analyst_implication": None,
                "implication_available": False,
                "supporting_evidence_ids": [],
                "profile_url": None,
                "landscape_url": "/competitors",
                "attention_reason": reason,
                "attention_label": ATTENTION_REASONS[reason],
                "current_or_historical": "unknown",
                "body_warning": "",
                "reader_href": "/sources",
                "intelligence_href": "/sources",
                "image_url": "",
                "prototype_synthetic": False,
                "fixture_dependency": None,
                "diagnostic_url": "/sources",
            }
        )
    return items


def build_coverage_pulse(
    *,
    landscape_completeness: dict[str, Any] | None,
    universe_count: int,
    sources: Iterable[dict[str, Any]] | None,
    briefing_items: list[dict[str, Any]],
) -> dict[str, Any]:
    source_rows = list(sources or [])
    configured = sum(1 for row in source_rows if row.get("id"))
    operational = sum(
        1
        for row in source_rows
        if row.get("id")
        and row.get("enabled") is not False
        and str(row.get("last_status") or row.get("discovery_status") or row.get("health") or "").casefold()
        not in {"blocked", "manual", "not_configured", "disabled"}
    )
    readable_acquired = sum(1 for item in briefing_items if item.get("usable_in_app"))
    current_usable = sum(
        1
        for item in briefing_items
        if item.get("usable_in_app")
        and item.get("recency_band") in RECENCY_CURRENT_BANDS
        and item.get("review_trust_state") == "trusted_published"
    )
    completeness = landscape_completeness or {}
    represented = int(
        completeness.get("represented")
        or completeness.get("competitors_represented")
        or universe_count
        or 0
    )
    return {
        "competitors_represented": represented,
        "discovery_configured": configured,
        "discovery_operational": operational,
        "readable_content_acquired": readable_acquired,
        "current_usable_coverage": current_usable,
        "notes": [
            "Represented means the competitor appears in the roster — not that it is actively monitored.",
            "Operational discovery does not imply readable article bodies were acquired.",
            "Current usable coverage counts trusted, readable items published within 90 days.",
        ],
        "landscape_url": "/competitors",
        "source_health_url": "/sources",
        "review_url": "/pending",
    }


def build_daily_intelligence_briefing(
    *,
    evidence: Iterable[dict[str, Any]],
    entities: Iterable[dict[str, Any]],
    sources: Iterable[dict[str, Any]] | None = None,
    landscape_completeness: dict[str, Any] | None = None,
    landscape_universe_count: int = 0,
    filters: BriefingFilters | None = None,
    today: date | None = None,
    records_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    filters = filters or BriefingFilters()
    today = today or date.today()
    entities_by_id = {
        str(entity.get("id")): entity
        for entity in entities
        if isinstance(entity, dict) and entity.get("id")
    }

    evidence_rows = [
        row
        for row in evidence
        if isinstance(row, dict)
        and row.get("id")
        and row.get("id") not in SEED_FIXTURE_EVIDENCE_IDS
    ]
    index = records_by_id or {str(row.get("id")): row for row in evidence_rows}

    presented: list[dict[str, Any]] = []
    for record in evidence_rows:
        if str(record.get("status") or "").casefold() != "published":
            continue
        presented.append(present_briefing_item(record, entities_by_id=entities_by_id, today=today))

    what_changed: list[dict[str, Any]] = []
    needs_attention: list[dict[str, Any]] = []
    historical: list[dict[str, Any]] = []
    unknown_date: list[dict[str, Any]] = []

    for item in presented:
        bucket = classify_briefing_bucket(item)
        if bucket == "what_changed":
            if not item.get("implication_available"):
                item = {**item, "implication_placeholder": "Analyst implication not yet added."}
            what_changed.append(item)
        elif bucket == "historical":
            historical.append(attach_attention_metadata(item))
        elif bucket == "unknown_date":
            unknown_date.append(attach_attention_metadata(item))
        else:
            needs_attention.append(attach_attention_metadata(item))

    needs_attention.extend(build_source_attention_items(sources))

    def sort_key(item: dict[str, Any]) -> tuple:
        return (
            item.get("publication_date") or "",
            item.get("capture_date") or "",
            item.get("headline") or "",
        )

    what_changed.sort(key=sort_key, reverse=True)
    needs_attention.sort(key=sort_key, reverse=True)
    historical.sort(key=sort_key, reverse=True)
    unknown_date.sort(key=sort_key, reverse=True)

    active = any([filters.berry, filters.region, filters.entity_id, filters.topic, filters.source, filters.recency])
    if active:
        what_changed = [i for i in what_changed if _matches_filters(i, filters)]
        historical = [i for i in historical if _matches_filters(i, filters)]
        unknown_date = [i for i in unknown_date if _matches_filters(i, filters)]
        needs_attention = [
            i for i in needs_attention if i.get("kind") == "source" or _matches_filters(i, filters)
        ]
    if filters.attention:
        needs_attention = [i for i in needs_attention if i.get("attention_reason") == filters.attention]

    bands = []
    for key in RECENCY_CURRENT_BANDS:
        rows = [item for item in what_changed if item["recency_band"] == key]
        bands.append({"id": key, "label": RECENCY_LABELS[key], "count": len(rows), "entries": rows})

    selected_reader = None
    if filters.reader and is_safe_record_id(filters.reader):
        for pool in (what_changed, needs_attention, historical, unknown_date):
            hit = next((item for item in pool if item.get("id") == filters.reader), None)
            if hit:
                selected_reader = hit
                break
        if selected_reader is None:
            raw = next((row for row in presented if row.get("id") == filters.reader), None)
            if raw is not None:
                selected_reader = (
                    raw if classify_briefing_bucket(raw) == "what_changed" else attach_attention_metadata(raw)
                )
        if selected_reader is not None:
            selected_reader = attach_reader_payload(selected_reader, index.get(filters.reader))

    pulse = build_coverage_pulse(
        landscape_completeness=landscape_completeness,
        universe_count=landscape_universe_count,
        sources=sources,
        briefing_items=presented,
    )

    entity_options = sorted(
        {
            (e["id"], e["name"])
            for item in presented
            for e in item.get("entities") or []
            if isinstance(e, dict)
        },
        key=lambda pair: pair[1].casefold(),
    )[:80]

    return {
        "title": "Daily Intelligence Briefing",
        "subtitle": "What changed, why it matters, and what needs attention today.",
        "as_of": today.isoformat(),
        "filters": filters,
        "filter_options": {
            "berries": sorted({b for item in presented for b in item.get("berries") or []}),
            "regions": sorted({r for item in presented for r in item.get("regions") or []}),
            "topics": sorted({t for item in presented for t in item.get("topics") or []})[:40],
            "sources": sorted({item.get("source_name") or "" for item in presented if item.get("source_name")}),
            "entities": entity_options,
        },
        "query_string": filters.to_query(include_reader=False),
        "selected_query_string": filters.to_query(include_reader=True),
        "clear_href": "/today",
        "what_changed_bands": bands,
        "what_changed_count": len(what_changed),
        "what_changed_empty": len(what_changed) == 0,
        "needs_attention": needs_attention[:75],
        "needs_attention_count": len(needs_attention),
        "historical_context": historical[:40],
        "historical_count": len(historical),
        "unknown_publication_dates": unknown_date[:40],
        "unknown_publication_date_count": len(unknown_date),
        "coverage_pulse": pulse,
        "selected_reader": selected_reader,
        "region_labels": DEFAULT_REGION_CODE_LABELS,
        "attention_reason_labels": ATTENTION_REASONS,
        "recency_labels": RECENCY_LABELS,
        "fixture_dependency": None,
        "prototype_fixture_used": False,
        "archive_edition_href": "/news",
        "thumbs_mutations_implemented": 0,
    }
