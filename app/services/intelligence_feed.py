"""Live intelligence feed and reader presentation.

This module is display composition only. Publication and atomic trust still
go through ReviewPublishService. It does not invent relevance scores or
classifications unsupported by stored fields.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.services.review_workbench import (
    analyst_transcript_label,
    attach_publication_card,
    format_locator,
    timestamp_source_url,
    unknown_transcript_readiness,
)

FEED_FILTERS = (
    ("all", "All"),
    ("articles", "Articles"),
    ("spoken", "Spoken media"),
    ("patents", "Patents"),
    ("companies", "Companies"),
    ("genetics", "Genetics"),
    ("markets", "Markets / supply"),
    ("consumer", "Consumer"),
    ("adjacent", "Adjacent signals"),
)

KIND_LABELS = {
    "article": "Article",
    "spoken": "Spoken media",
    "patent": "Patent",
    "other": "Intelligence",
}

TRUST_LABELS = {
    "pending": "Pending",
    "trusted": "Trusted",
    "attention": "Needs attention",
    "disputed": "Disputed",
}

MARKET_TAGS = {
    "market",
    "supply",
    "export",
    "retail",
    "retail-strategy",
    "seasonal-supply",
    "commercial",
    "omnichannel-marketing",
    "fresh-merchandising",
}
CONSUMER_TAGS = {
    "consumer",
    "shopper",
    "consumption",
    "demand",
}


def classify_kind(record: dict[str, Any]) -> str:
    if (
        record.get("source_type") == "patent_record"
        or record.get("intake_type") == "patent_filing"
        or isinstance(record.get("patent_filing"), dict)
    ):
        return "patent"
    media = str(record.get("media_format") or "")
    if media in {"podcast", "video", "conference_video"}:
        return "spoken"
    if media == "web_article" or isinstance(record.get("article"), dict):
        return "article"
    source = str(record.get("source_type") or "")
    if source in {"article", "trade_press", "news_search", "press_release", "field_observation"}:
        return "article"
    return "other"


def source_action(record: dict[str, Any], kind: str) -> tuple[str, str]:
    url = (record.get("source_url") or "").strip()
    if not url:
        return "", ""
    if kind == "patent":
        return url, "Open filing"
    if kind == "spoken":
        return url, "Open source"
    return url, "Read original"


def trust_state(record: dict[str, Any], *, readiness: dict[str, Any] | None = None) -> str:
    if record.get("status") == "published" or record.get("review_state") == "published":
        verification = str(record.get("verification_state") or "")
        if verification in {"disputed", "contradicted"}:
            return "disputed"
        return "trusted"
    links = record.get("evidence_links") or []
    if any(isinstance(link, dict) and link.get("status") == "contested" for link in links):
        return "disputed"
    state = (readiness or record.get("transcript_readiness") or {}).get("state")
    if state in {"retryable_failure", "intervention_required"}:
        return "attention"
    return "pending"


def _entity_map(entities: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(entities, dict):
        return entities
    return {record["id"]: record for record in entities if record.get("id")}


def entity_chips(record: dict[str, Any], entities: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    enrichment = record.get("ai_enrichment") or {}
    chips: list[dict[str, str]] = []
    seen: set[str] = set()
    ids = list(record.get("entity_ids") or []) + list(enrichment.get("suggested_entity_ids") or [])
    by_name = {
        str(entity.get("name") or "").casefold(): entity
        for entity in entities.values()
        if entity.get("name")
    }
    for entity_id in ids:
        entity = entities.get(entity_id)
        if not entity or entity_id in seen:
            continue
        chips.append(
            {
                "id": entity_id,
                "name": str(entity.get("name") or entity_id),
                "entity_type": str(entity.get("entity_type") or "company"),
            }
        )
        seen.add(entity_id)
    for name in list(record.get("suggested_competitors") or []):
        entity = by_name.get(str(name).casefold())
        if not entity or entity.get("id") in seen:
            continue
        chips.append(
            {
                "id": str(entity["id"]),
                "name": str(entity.get("name") or name),
                "entity_type": str(entity.get("entity_type") or "company"),
            }
        )
        seen.add(str(entity["id"]))
    return chips


def is_berry_direct(record: dict[str, Any]) -> bool:
    enrichment = record.get("ai_enrichment") or {}
    return bool(record.get("berry_ids") or enrichment.get("suggested_berry_ids"))


def matches_filter(item: dict[str, Any], filter_key: str) -> bool:
    if filter_key in {"", "all"}:
        return True
    kind = item.get("kind")
    tags = {str(tag).casefold() for tag in (item.get("tags") or [])}
    if filter_key == "articles":
        return kind == "article"
    if filter_key == "spoken":
        return kind == "spoken"
    if filter_key == "patents":
        return kind == "patent"
    if filter_key == "companies":
        return any(chip.get("entity_type") == "company" for chip in item.get("entities") or [])
    if filter_key == "genetics":
        if kind == "patent":
            return True
        return any(chip.get("entity_type") == "variety" for chip in item.get("entities") or [])
    if filter_key == "markets":
        return bool(tags & MARKET_TAGS)
    if filter_key == "consumer":
        return bool(tags & CONSUMER_TAGS)
    if filter_key == "adjacent":
        return item.get("relevance_tier") == "adjacent"
    return False


def _feed_sort_key(item: dict[str, Any]) -> tuple:
    # relevance_tier ("direct"/"adjacent"/None -- see app/services/
    # relevance_screen.py) is the primary rank: a direct berry story must
    # outrank an adjacent one regardless of relevance_band/berry_direct,
    # which are independent AI-enrichment/tagging signals that don't
    # capture the same "is a berry the real subject, or one incidental
    # mention" distinction. Items with no tier at all (podcasts, videos,
    # trusted Evidence, pre-fix article drafts) are tier-neutral -- ranked
    # with direct, never penalized for predating this field.
    tier_rank = 0 if item.get("relevance_tier") == "adjacent" else 1
    band = {"High": 4, "Relevant": 3, "Moderate": 2, "Low": 1}.get(item.get("relevance_band") or "", 0)
    berry = 1 if item.get("berry_direct") else 0
    pending = 1 if item.get("trust") in {"pending", "attention", "disputed"} else 0
    ready = 1 if item.get("transcript_state") == "ready" else 0
    date = str(item.get("date") or "")
    return (tier_rank, band, berry, pending, ready, date)


def _published_for_feed(published: list[dict[str, Any]], *, limit: int = 48) -> list[dict[str, Any]]:
    """Keep recent trusted items plus spoken media that would otherwise age out."""

    eligible = [record for record in published if record.get("status") == "published"]
    spoken = [record for record in eligible if classify_kind(record) == "spoken"]
    recent = sorted(
        eligible,
        key=lambda record: str(record.get("published_date") or record.get("captured_date") or ""),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in spoken + recent:
        record_id = str(record.get("id") or "")
        if not record_id or record_id in seen:
            continue
        out.append(record)
        seen.add(record_id)
        if len(out) >= limit:
            break
    return out


def _select_visible(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    ranked = sorted(items, key=_feed_sort_key, reverse=True)
    trusted = [item for item in ranked if item["trust"] == "trusted"]
    pending = [item for item in ranked if item["trust"] != "trusted"]
    trusted_slots = min(len(trusted), max(1, min(12, limit // 3))) if trusted else 0
    selected = pending[: limit - trusted_slots] + trusted[:trusted_slots]
    selected.sort(key=_feed_sort_key, reverse=True)
    return selected[:limit]


def present_feed_item(
    record: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]],
    berry_labels: dict[str, str],
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    presentation = deepcopy(record)
    if readiness:
        presentation["transcript_readiness"] = deepcopy(readiness)
    attach_publication_card(presentation, entities=entities, berry_labels=berry_labels)
    card = presentation.get("card") or {}
    kind = classify_kind(record)
    trust = trust_state(record, readiness=presentation.get("transcript_readiness"))
    source_url, source_label = source_action(record, kind)
    chips = entity_chips(record, entities)
    return {
        "id": record.get("id"),
        "title": record.get("title") or "Untitled",
        "kind": kind,
        "kind_label": KIND_LABELS.get(kind, "Intelligence"),
        "trust": trust,
        "trust_label": TRUST_LABELS[trust],
        "source_name": record.get("source_name") or record.get("submitted_by") or "Source not recorded",
        "date": record.get("published_date") or record.get("captured_date") or "",
        "why": card.get("why") or "",
        "summary": card.get("summary") or "",
        "relevance_band": card.get("relevance_band") or "",
        "ai_untrusted": bool(card.get("ai_untrusted") or record.get("ai_enrichment")),
        "entities": chips,
        "tags": card.get("tags") or record.get("tags") or [],
        "source_url": source_url,
        "source_action_label": source_label,
        "media_format": record.get("media_format") or "",
        "berry_direct": is_berry_direct(record),
        "relevance_tier": record.get("relevance_tier"),
        "berry_names": card.get("berries") or [],
        "geo_names": card.get("geographies") or [],
        "transcript_state": card.get("transcript_state"),
        "href": f"/intelligence/{record.get('id')}",
        "trusted_href": f"/evidence/{record.get('id')}",
        "status": record.get("status"),
        "record": record,
        "card": card,
        "pending": (
            trust in {"pending", "attention", "disputed"}
            and record.get("status") != "published"
            and record.get("evidence_role") != "atomic_evidence"
        ),
    }


def build_intelligence_feed(
    *,
    drafts: list[dict[str, Any]],
    published: list[dict[str, Any]],
    entities: dict[str, dict[str, Any]] | list[dict[str, Any]],
    berry_labels: dict[str, str],
    transcript_readiness: dict[str, dict[str, Any]] | None = None,
    filter_key: str = "all",
    limit: int = 48,
) -> dict[str, Any]:
    entity_index = _entity_map(entities)
    readiness = transcript_readiness or {}
    items: list[dict[str, Any]] = []
    pending = [
        draft
        for draft in drafts
        if draft.get("evidence_role") != "atomic_evidence" and draft.get("status", "draft") != "rejected"
    ]
    for draft in pending:
        items.append(
            present_feed_item(
                draft,
                entities=entity_index,
                berry_labels=berry_labels,
                readiness=readiness.get(draft.get("id")),
            )
        )
    trusted_seen = {item["id"] for item in items}
    for record in _published_for_feed(published):
        if record.get("id") in trusted_seen:
            continue
        items.append(
            present_feed_item(
                record,
                entities=entity_index,
                berry_labels=berry_labels,
            )
        )
    available = []
    for key, label in FEED_FILTERS:
        if key == "all" or any(matches_filter(item, key) for item in items):
            available.append({"key": key, "label": label})
    selected = filter_key if any(option["key"] == filter_key for option in available) else "all"
    visible = [item for item in items if matches_filter(item, selected)]
    return {
        "entries": _select_visible(visible, limit=limit),
        "filter": selected,
        "filters": available,
        "counts": {
            "pending": sum(1 for item in items if item["trust"] in {"pending", "attention"}),
            "trusted": sum(1 for item in items if item["trust"] == "trusted"),
            "attention": sum(1 for item in items if item["trust"] == "attention"),
        },
    }


def load_transcript_segments(inbox_dir: Path, record: dict[str, Any]) -> list[dict[str, Any]]:
    discovered_id = record.get("discovered_item_id")
    if not discovered_id:
        return []
    path = inbox_dir / "discovered_media" / "_normalized_transcripts" / f"{discovered_id}.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    segments = payload.get("segments") if isinstance(payload, dict) else None
    if not isinstance(segments, list):
        return []
    out: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        start = segment.get("start_seconds")
        out.append(
            {
                "text": text,
                "start_seconds": start,
                "end_seconds": segment.get("end_seconds"),
                "speaker": segment.get("speaker_label") or "",
                "source_at": timestamp_source_url(record.get("source_url"), start),
            }
        )
    return out


def article_paragraphs(record: dict[str, Any]) -> list[dict[str, Any]]:
    article = record.get("article") if isinstance(record.get("article"), dict) else {}
    paragraphs = article.get("paragraphs") if isinstance(article, dict) else None
    if not isinstance(paragraphs, list):
        return []
    out = []
    for index, paragraph in enumerate(paragraphs, start=1):
        if isinstance(paragraph, dict):
            text = str(paragraph.get("text") or "").strip()
            locator = paragraph.get("locator") or f"p{index}"
        else:
            text = str(paragraph).strip()
            locator = f"p{index}"
        if text:
            out.append({"locator": locator, "text": text})
    return out


def related_evidence(
    record: dict[str, Any],
    published: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    entity_ids = set(record.get("entity_ids") or [])
    berry_ids = set(record.get("berry_ids") or [])
    current_id = record.get("id")
    scored: list[tuple[int, dict[str, Any]]] = []
    for other in published:
        if other.get("id") == current_id or other.get("status") != "published":
            continue
        overlap = len(entity_ids & set(other.get("entity_ids") or [])) + len(
            berry_ids & set(other.get("berry_ids") or [])
        )
        if overlap:
            scored.append((overlap, other))
    scored.sort(key=lambda pair: (pair[0], str(pair[1].get("published_date") or "")), reverse=True)
    return [
        {"id": other.get("id"), "title": other.get("title") or other.get("id")}
        for _, other in scored[:limit]
    ]


def extract_claims_status() -> dict[str, Any]:
    """Reader CTA only. Never implies an unqualified model can run."""

    return {
        "runnable": False,
        "label": "Extract claims",
        "detail": (
            "No qualified extraction model is configured. "
            "The Intelligence OS will not extract claims with an unqualified model."
        ),
    }


def build_reader(
    record: dict[str, Any],
    *,
    entities: dict[str, dict[str, Any]] | list[dict[str, Any]],
    berry_labels: dict[str, str],
    inbox_dir: Path,
    published: list[dict[str, Any]],
    atomic_drafts: list[dict[str, Any]],
    transcript_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entity_index = _entity_map(entities)
    item = present_feed_item(
        record,
        entities=entity_index,
        berry_labels=berry_labels,
        readiness=transcript_readiness,
    )
    kind = item["kind"]
    paragraphs = article_paragraphs(record)
    segments = load_transcript_segments(inbox_dir, record) if kind == "spoken" else []
    patent = record.get("patent_filing") if isinstance(record.get("patent_filing"), dict) else None
    parent_id = record.get("id")
    proposals = []
    for draft in atomic_drafts:
        if draft.get("parent_evidence_id") != parent_id or draft.get("status") == "rejected":
            continue
        locator = draft.get("artifact_locator") or {}
        proposals.append(
            {
                "id": draft.get("id"),
                "statement": draft.get("summary") or draft.get("title") or "",
                "excerpt": draft.get("transcript_excerpt") or "",
                "locator": locator,
                "locator_label": format_locator(locator) if locator else "",
                "source_at": timestamp_source_url(record.get("source_url"), locator.get("start_seconds")),
            }
        )
    enrichment = record.get("ai_enrichment") or {}
    return {
        "item": item,
        "kind": kind,
        "paragraphs": paragraphs,
        "segments": segments,
        "patent": patent,
        "does_not_prove": list(record.get("does_not_prove") or []),
        "source_authority": record.get("source_authority") or "",
        "verification_state": record.get("verification_state") or "",
        "evidence_links": [
            link for link in (record.get("evidence_links") or []) if isinstance(link, dict)
        ],
        "publisher_description": (record.get("publisher_description") or "").strip(),
        "related": related_evidence(record, published),
        "atomic_proposals": proposals,
        "extract_claims": extract_claims_status(),
        "readiness": transcript_readiness or unknown_transcript_readiness(),
        "analyst_transcript_label": analyst_transcript_label(transcript_readiness),
        "ai_caveats": enrichment.get("caveats") or "",
        "pending": (
            item["trust"] in {"pending", "attention", "disputed"}
            and record.get("status") != "published"
            and record.get("evidence_role") != "atomic_evidence"
        ),
    }
