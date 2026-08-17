"""Non-trusted publication-draft enrichment.

Order:
1. Preserve original publisher description.
2. Deterministic geography/entity/berry tagging from known records.
3. Optional cheap AI suggestions for unresolved CI fields.
4. Human review remains mandatory. Suggestions are never trusted.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from app.services.deterministic_tagging import (
    apply_known_name_matches,
    infer_berry_ids_from_text,
    matchers_from_entities,
)

NBSP_RE = re.compile(r"&nbsp;|&#160;|\xa0", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

ENRICHMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "concise_summary",
        "why_it_matters",
        "suggested_berry_ids",
        "suggested_geography_ids",
        "suggested_entity_ids",
        "suggested_tags",
        "topical_relevance",
        "confidence",
        "caveats",
    ],
    "properties": {
        "concise_summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "suggested_berry_ids": {"type": "array", "items": {"type": "string"}},
        "suggested_geography_ids": {"type": "array", "items": {"type": "string"}},
        "suggested_entity_ids": {"type": "array", "items": {"type": "string"}},
        "suggested_tags": {"type": "array", "items": {"type": "string"}},
        "topical_relevance": {"type": "string"},
        "confidence": {"type": "number"},
        "caveats": {"type": "string"},
    },
}


def clean_publisher_text(value: str | None) -> str:
    text = NBSP_RE.sub(" ", str(value or ""))
    text = TAG_RE.sub(" ", text)
    return WS_RE.sub(" ", text).strip()


def publisher_description(item: dict[str, Any], draft: dict[str, Any] | None = None) -> str:
    for candidate in (
        item.get("publisher_description"),
        item.get("description"),
        item.get("summary"),
        (draft or {}).get("publisher_description"),
    ):
        cleaned = clean_publisher_text(candidate if isinstance(candidate, str) else None)
        if cleaned:
            return cleaned
    return ""


def apply_deterministic_tags(
    draft: dict[str, Any],
    *,
    geographies: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    extra_text: str = "",
) -> dict[str, Any]:
    tagged = dict(draft)
    haystack = " ".join(
        [
            str(tagged.get("title") or ""),
            publisher_description({}, tagged),
            str(tagged.get("summary") or ""),
            extra_text,
        ]
    )
    apply_known_name_matches(
        tagged,
        haystack,
        geo_matchers=matchers_from_entities(geographies, "geography"),
        company_matchers=matchers_from_entities(entities, "company"),
    )
    berry_ids = list(tagged.get("berry_ids") or [])
    for berry_id in infer_berry_ids_from_text(haystack):
        if berry_id not in berry_ids:
            berry_ids.append(berry_id)
    tagged["berry_ids"] = berry_ids
    tagged["tagging_provenance"] = {
        "method": "deterministic-known-match",
        "trust_state": "untrusted_suggestion",
    }
    return tagged


def empty_ai_enrichment(*, reason: str, model: str | None = None) -> dict[str, Any]:
    return {
        "concise_summary": "",
        "why_it_matters": "",
        "suggested_berry_ids": [],
        "suggested_geography_ids": [],
        "suggested_entity_ids": [],
        "suggested_tags": [],
        "topical_relevance": "",
        "confidence": 0.0,
        "caveats": reason,
        "model_provenance": {
            "status": "skipped" if model is None else "failed",
            "reason": reason,
            "model": model,
            "trust_state": "untrusted_suggestion",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }


def _known_id_list(records: list[dict[str, Any]], limit: int = 80) -> list[str]:
    out: list[str] = []
    for record in records[:limit]:
        rec_id = str(record.get("id") or "").strip()
        name = str(record.get("name") or record.get("title") or "").strip()
        if rec_id:
            out.append(f"{rec_id} ({name})" if name else rec_id)
    return out


def build_enrichment_prompt(
    *,
    title: str,
    publisher_text: str,
    source_name: str,
    berry_catalog: list[str],
    geography_catalog: list[str],
    entity_catalog: list[str],
    deterministic: dict[str, Any],
) -> str:
    return (
        "You are assisting a competitive-intelligence reviewer for berry crops "
        "(blueberry, strawberry, raspberry, blackberry and related production).\n"
        "Return JSON only. Do not invent facts that are not supported by the source text.\n"
        "Keep concise_summary to 2-4 CI-oriented sentences. Keep why_it_matters to 1-2 sentences.\n"
        "Prefer the provided catalog ids. If unsure, leave arrays empty and explain in caveats.\n"
        "This output is an untrusted suggestion. A human must review before publication.\n\n"
        f"Title: {title}\n"
        f"Source: {source_name}\n"
        f"Publisher description:\n{publisher_text[:4000]}\n\n"
        f"Deterministic berry_ids: {json.dumps(deterministic.get('berry_ids') or [])}\n"
        f"Deterministic geography_ids: {json.dumps(deterministic.get('geography_ids') or [])}\n"
        f"Deterministic entity_ids: {json.dumps(deterministic.get('entity_ids') or [])}\n\n"
        f"Known berry ids: {', '.join(berry_catalog[:60])}\n"
        f"Known geography ids: {', '.join(geography_catalog[:60])}\n"
        f"Known entity ids: {', '.join(entity_catalog[:60])}\n"
    )


def _merge_unique(*groups: list[str]) -> list[str]:
    out: list[str] = []
    for group in groups:
        for value in group:
            text = str(value or "").strip()
            if text and text not in out:
                out.append(text)
    return out


def apply_ai_payload(
    draft: dict[str, Any],
    payload: dict[str, Any],
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(draft)
    suggested_berries = [str(v) for v in payload.get("suggested_berry_ids") or [] if str(v).strip()]
    suggested_geos = [str(v) for v in payload.get("suggested_geography_ids") or [] if str(v).strip()]
    suggested_entities = [str(v) for v in payload.get("suggested_entity_ids") or [] if str(v).strip()]
    updated["berry_ids"] = _merge_unique(list(updated.get("berry_ids") or []), suggested_berries)
    updated["geography_ids"] = _merge_unique(list(updated.get("geography_ids") or []), suggested_geos)
    updated["entity_ids"] = _merge_unique(list(updated.get("entity_ids") or []), suggested_entities)
    concise = clean_publisher_text(payload.get("concise_summary"))
    why = clean_publisher_text(payload.get("why_it_matters"))
    if concise:
        updated["summary"] = concise
    if why and not str(updated.get("why_it_matters") or "").strip():
        updated["why_it_matters"] = why
    updated["ai_enrichment"] = {
        "concise_summary": concise,
        "why_it_matters": why,
        "suggested_berry_ids": suggested_berries,
        "suggested_geography_ids": suggested_geos,
        "suggested_entity_ids": suggested_entities,
        "suggested_tags": [str(v) for v in payload.get("suggested_tags") or [] if str(v).strip()],
        "topical_relevance": str(payload.get("topical_relevance") or "").strip(),
        "confidence": payload.get("confidence") if isinstance(payload.get("confidence"), (int, float)) else 0.0,
        "caveats": str(payload.get("caveats") or "").strip(),
        "model_provenance": {
            **provenance,
            "trust_state": "untrusted_suggestion",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
    return updated


def enrich_publication_draft(
    draft: dict[str, Any],
    item: dict[str, Any],
    *,
    berries: list[dict[str, Any]],
    geographies: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    complete_json: Any | None = None,
) -> dict[str, Any]:
    updated = dict(draft)
    original = publisher_description(item, draft)
    updated["publisher_description"] = original
    updated = apply_deterministic_tags(
        updated,
        geographies=geographies,
        entities=entities,
        extra_text=original,
    )
    if original and (
        not clean_publisher_text(updated.get("summary"))
        or updated.get("summary") == original
    ):
        # Keep the raw publisher text in publisher_description; leave summary as
        # a placeholder until AI (or a human) replaces it.
        updated["summary"] = original[:1200]

    model = os.environ.get("BERRY_ENRICHMENT_MODEL", "anthropic/claude-haiku-4-5").strip()
    provider = os.environ.get("BERRY_ENRICHMENT_PROVIDER", "perplexity-agent").strip()
    if complete_json is None or not original:
        updated["ai_enrichment"] = empty_ai_enrichment(
            reason="ai enrichment skipped: no completer or empty publisher text",
            model=None,
        )
        return updated

    prompt = build_enrichment_prompt(
        title=str(updated.get("title") or item.get("title") or ""),
        publisher_text=original,
        source_name=str(item.get("source_name") or updated.get("source_id") or ""),
        berry_catalog=_known_id_list(berries),
        geography_catalog=_known_id_list(geographies),
        entity_catalog=_known_id_list(entities),
        deterministic={
            "berry_ids": updated.get("berry_ids") or [],
            "geography_ids": updated.get("geography_ids") or [],
            "entity_ids": updated.get("entity_ids") or [],
        },
    )
    try:
        result = complete_json(
            prompt,
            schema=ENRICHMENT_SCHEMA,
            model=model,
            provider=provider,
            max_output_tokens=800,
        )
        payload = result.parsed if hasattr(result, "parsed") else result
        if not isinstance(payload, dict):
            raise RuntimeError("enrichment completer returned non-object")
        updated = apply_ai_payload(
            updated,
            payload,
            provenance={
                "status": "ok",
                "provider": provider,
                "model": getattr(result, "model", None) or model,
                "reason": "non-trusted publication enrichment",
            },
        )
    except Exception as exc:
        updated["ai_enrichment"] = empty_ai_enrichment(
            reason=f"ai enrichment failed: {type(exc).__name__}",
            model=model,
        )
    return updated
