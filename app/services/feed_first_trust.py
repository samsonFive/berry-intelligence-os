"""Bridge in-reader confirmation into the existing Evidence → Fact trust path."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Any

from app.services.review_publish import ApproveClaimRequest, PublishRequest

ORIGIN_FEED_CONFIRMATION = "feed_thumbsup_extraction"


def _canonical_evidence_id(record: dict[str, Any]) -> str:
    item_id = str(record.get("id") or "")
    if item_id.startswith("ev-"):
        return item_id
    identity = str(record.get("source_url") or item_id)
    digest = sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"ev-feed-{digest}"


def confirm_feed_statement(
    *,
    service: Any,
    repositories: Any,
    record: dict[str, Any],
    statement: dict[str, Any],
    reviewer: str,
) -> str:
    """Return the one canonical Fact id created/reused for a confirmation."""
    if not reviewer.strip():
        raise ValueError("reviewer is required for canonical confirmation")
    evidence_id = _canonical_evidence_id(record)
    existing = repositories.evidence.get(evidence_id)
    statement_text = str(statement.get("statement_text") or "").strip()
    proposed = str(statement.get("original_extraction_text") or statement_text).strip()
    if not statement_text:
        raise ValueError("statement text is required")
    if existing is not None:
        result = service.approve_claim(
            ApproveClaimRequest(
                evidence_id=evidence_id,
                statement=statement_text,
                proposed_statement=proposed,
                classification="fact",
                confidence="medium",
                reviewer=reviewer,
                origin=ORIGIN_FEED_CONFIRMATION,
            )
        )
        if not result.ok:
            raise ValueError("; ".join(result.schema_errors))
        return str(result.fact_id)

    known_entities = {
        str(row.get("id")) for row in repositories.entities.list() if row.get("id")
    }
    entity_ids = [
        str(value)
        for value in (statement.get("entity_ids") or record.get("entity_ids") or [])
        if str(value) in known_entities
    ]
    priority = {
        name: {"level": "none", "rationale": ""}
        for name in ("reading", "testing", "commercial_position", "monitoring")
    }
    draft = {
        **record,
        "id": evidence_id,
        "record_type": "evidence",
        "status": "draft",
        "review_state": "draft",
        "submitted_by": reviewer,
        "evidence_role": "publication_artifact",
        "entity_ids": entity_ids,
    }
    result = service.publish(
        PublishRequest(
            draft=draft,
            draft_id=evidence_id,
            title=str(record.get("title") or statement_text)[:300],
            source_type=str(record.get("source_type") or "web_article"),
            source_name=str(record.get("source_name") or ""),
            source_url=str(record.get("source_url") or ""),
            published_date=record.get("published_date"),
            captured_date=str(record.get("captured_date") or date.today().isoformat())[:10],
            summary=str(record.get("summary") or ""),
            why_it_matters="",
            tags=[str(value) for value in (record.get("tags") or [])],
            selected_berries=[str(value) for value in (record.get("berry_ids") or [])],
            all_entity_names_by_type={},
            facts_input=[
                {
                    "statement": statement_text,
                    "classification": "fact",
                    "confidence": "medium",
                }
            ],
            relationships_input=[],
            priority=priority,
            strategic_question_text=[],
            reviewer=reviewer,
            existing_entity_ids=entity_ids,
        )
    )
    if not result.ok:
        detail = [*result.schema_errors, *result.conflicts]
        raise ValueError("; ".join(detail) or "canonical publication failed")
    published = repositories.evidence.get(evidence_id)
    fact_ids = list((published or {}).get("fact_ids") or [])
    if not fact_ids:
        raise ValueError("canonical publication created no Fact")
    return str(fact_ids[-1])
