"""Publication Review read-only UI Slice 1 — presentation adapter.

Projects durable publication drafts into the contract-aligned queue/detail
read model. Decision mutations are intentionally disconnected
(``decisions_enabled`` is always False for this slice).

Rehearsal fixtures live under ``tests/`` and may be loaded only when
``BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=1`` (browser verification) or when a
caller injects records explicitly in tests. They are never treated as
authoritative production backlog.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

DECISIONS_ENABLED = False
SLICE_ID = "publication-review-readonly-ui-v1"

CONTENT_FILTERS: tuple[dict[str, str], ...] = (
    {"id": "all", "label": "All"},
    {"id": "readable", "label": "Readable body"},
    {"id": "transcript", "label": "Transcript"},
    {"id": "limited", "label": "Limited content"},
    {"id": "problem", "label": "Problem states"},
)

_TRUST_BANDS = {
    "trusted_source_metadata": "Trusted source metadata",
    "acquired_body": "Acquired body content",
    "untrusted_ai": "Untrusted AI enrichment",
    "proposed_entities": "Proposed entity associations",
    "atomic_evidence": "Atomic Evidence (not approved here)",
}


def decisions_enabled() -> bool:
    """Slice 1 capability flag — always false until a later mutation slice."""
    return False


def rehearsal_ui_allowed() -> bool:
    return os.environ.get("BIOS_PUBLICATION_REVIEW_REHEARSAL_UI", "").strip() == "1"


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _warning(code: str, message: str, *, level: str = "warn") -> dict[str, str]:
    return {"code": code, "message": message, "level": level}


def classify_content(draft: dict[str, Any]) -> dict[str, Any]:
    """Normalize content class for filters and badges."""
    if draft.get("fixture_state"):
        # Presentation-layer rehearsal / already-projected records
        quality = str(draft.get("content_quality") or "limited")
        label = str(draft.get("content_quality_label") or quality.replace("_", " ").title())
        return {
            "content_class": quality,
            "content_class_label": label,
            "readable_content": quality == "readable",
            "body_kind": draft.get("body_kind") or quality,
        }

    completeness = draft.get("source_completeness") if isinstance(draft.get("source_completeness"), dict) else {}
    source_class = str(completeness.get("class") or "").upper()
    article = draft.get("article") if isinstance(draft.get("article"), dict) else {}
    transcript = draft.get("transcript") if isinstance(draft.get("transcript"), dict) else {}
    paragraphs = article.get("paragraphs") if isinstance(article.get("paragraphs"), list) else []
    has_body = bool(paragraphs) or bool(article.get("text") or article.get("body"))
    has_transcript = bool(transcript.get("text") or draft.get("transcript_segments"))

    if source_class in {"FULL_ARTICLE"} or (has_body and not has_transcript):
        quality, label, kind = "readable", "Readable body", "readable"
    elif source_class in {"FULL_TRANSCRIPT"} or has_transcript:
        quality, label, kind = "transcript", "Transcript", "transcript"
    elif source_class in {"NO_CONTENT"} or draft.get("acquisition_outcome") in {
        "navigation_shell",
        "bot_wall",
        "empty_shell",
    }:
        quality, label, kind = "problem", "Problem / shell", "problem"
    else:
        quality, label, kind = "limited", "Limited content", "limited"

    return {
        "content_class": quality,
        "content_class_label": label,
        "readable_content": quality == "readable",
        "body_kind": kind,
    }


def _extract_body(draft: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    if draft.get("body_text") is not None or draft.get("limited_explanation") is not None:
        return (
            draft.get("body_text"),
            draft.get("body_kind"),
            draft.get("limited_explanation"),
        )
    article = draft.get("article") if isinstance(draft.get("article"), dict) else {}
    transcript = draft.get("transcript") if isinstance(draft.get("transcript"), dict) else {}
    paragraphs = article.get("paragraphs") if isinstance(article.get("paragraphs"), list) else []
    texts = []
    for row in paragraphs:
        if isinstance(row, dict) and row.get("text"):
            texts.append(str(row["text"]))
        elif isinstance(row, str):
            texts.append(row)
    body = "\n\n".join(texts).strip() or (article.get("text") or article.get("body") or None)
    if body:
        return str(body), "readable", None
    ttext = transcript.get("text") or draft.get("transcript_excerpt")
    if ttext:
        return str(ttext), "transcript", None
    explanation = (
        draft.get("limited_explanation")
        or completeness_note(draft)
        or "No usable acquired body is available for this draft."
    )
    return None, "limited", str(explanation)


def completeness_note(draft: dict[str, Any]) -> str | None:
    completeness = draft.get("source_completeness") if isinstance(draft.get("source_completeness"), dict) else {}
    if completeness.get("class"):
        return f"Acquisition completeness: {completeness.get('class')}"
    outcome = draft.get("acquisition_outcome")
    return f"Acquisition outcome: {outcome}" if outcome else None


def _entity_match(draft: dict[str, Any]) -> dict[str, Any]:
    if isinstance(draft.get("entity_match"), dict):
        return draft["entity_match"]
    entities = []
    for row in _as_list(draft.get("linked_entities") or draft.get("entities")):
        if isinstance(row, dict) and (row.get("id") or row.get("name")):
            entities.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name") or row.get("id"),
                    "type": row.get("type") or row.get("entity_type") or "entity",
                }
            )
    for eid in _as_list(draft.get("entity_ids")):
        entities.append({"id": eid, "name": eid, "type": "entity"})
    if entities:
        return {"status": "matched", "entities": entities}
    return {"status": "missing", "entities": []}


def _duplicate(draft: dict[str, Any]) -> dict[str, Any] | None:
    if draft.get("duplicate") is not None:
        return draft.get("duplicate")
    if draft.get("duplicate_of") or draft.get("probable_duplicate_of"):
        return {
            "status": "probable",
            "candidate_id": draft.get("duplicate_of") or draft.get("probable_duplicate_of"),
            "candidate_title": draft.get("duplicate_title") or "Related draft",
            "similarity": draft.get("duplicate_similarity"),
        }
    return None


def _warnings(draft: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if draft.get("provenance_warnings") is not None or draft.get("blocking_warnings") is not None:
        return list(draft.get("provenance_warnings") or []), list(draft.get("blocking_warnings") or [])

    warnings: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []
    date_conf = str(draft.get("publication_date_confidence") or "").lower()
    if date_conf in {"low", "none", "unknown"}:
        warnings.append(_warning("uncertain_date", "Publication date confidence is low or unknown."))
    if _entity_match(draft)["status"] == "missing":
        warnings.append(_warning("missing_entity", "No canonical entity match proposed."))
    dup = _duplicate(draft)
    if dup and dup.get("status") == "probable":
        warnings.append(_warning("probable_duplicate", "Probable duplicate of another draft (warning only)."))
    outcome = str(draft.get("acquisition_outcome") or "")
    if outcome in {"navigation_shell", "bot_wall", "empty_shell"}:
        blockers.append(_warning("navigation_shell", "Capture looks like a navigation/bot shell.", level="block"))
    if draft.get("validation_failure") or draft.get("status") == "invalid":
        blockers.append(_warning("validation_failure", "Draft failed validation and cannot be approved.", level="block"))
    if not (draft.get("source_url") or draft.get("canonical_url")):
        blockers.append(_warning("missing_source_url", "Draft is missing a required source URL.", level="block"))
    enrichment = draft.get("ai_enrichment") or draft.get("untrusted_suggestions")
    if enrichment:
        warnings.append(_warning("ai_enrichment", "AI enrichment is present and remains untrusted."))
    return warnings, blockers


def _review_state(draft: dict[str, Any]) -> str:
    if draft.get("queue_state"):
        return str(draft["queue_state"])
    status = str(draft.get("status") or "pending").lower()
    if status in {"pending", "draft", "review_ready"}:
        return "pending_review"
    if status in {"approved", "published"}:
        return "approved"
    if status == "rejected":
        return "rejected"
    if status in {"deferred", "defer"}:
        return "deferred"
    if status in {"correction_required", "correction_requested"}:
        return "correction_required"
    return status or "pending_review"


def _attention_rank(draft: dict[str, Any], blockers: list[Any], warnings: list[Any]) -> int:
    if draft.get("needs_attention_rank") is not None:
        try:
            return int(draft["needs_attention_rank"])
        except (TypeError, ValueError):
            pass
    state = _review_state(draft)
    if state not in {"pending_review", "pending"}:
        return 90
    if blockers:
        return 1
    if any(w.get("code") == "probable_duplicate" for w in warnings):
        return 2
    if any(w.get("code") == "missing_entity" for w in warnings):
        return 3
    if any(w.get("code") == "uncertain_date" for w in warnings):
        return 4
    content = classify_content(draft)["content_class"]
    if content == "problem":
        return 1
    if content == "limited":
        return 5
    return 10


def project_queue_item(draft: dict[str, Any]) -> dict[str, Any]:
    """Body-free queue projection (contract UI-DATA-CONTRACT)."""
    content = classify_content(draft)
    warnings, blockers = _warnings(draft)
    entity = _entity_match(draft)
    dup = _duplicate(draft)
    draft_id = str(draft.get("draft_id") or draft.get("id") or "")
    title = str(draft.get("headline") or draft.get("title") or draft_id or "Untitled draft")
    pub_date = draft.get("publication_date") or draft.get("published_date")
    captured = draft.get("captured_at") or draft.get("captured_date")
    version = int(draft.get("version") or draft.get("review_version") or 1)
    state = _review_state(draft)
    item = {
        "draft_id": draft_id,
        "title": title,
        "source_name": draft.get("source_name") or draft.get("source_id") or "Unknown source",
        "source_id": draft.get("source_id"),
        "publication_date": pub_date,
        "publication_date_confidence": draft.get("publication_date_confidence") or "unknown",
        "captured_at": captured,
        "discovered_at": draft.get("discovered_at") or draft.get("discovered_date"),
        "review_state": state,
        "version": version,
        "updated_at": draft.get("updated_at") or captured,
        "content_class": content["content_class"],
        "content_class_label": content["content_class_label"],
        "readable_content": content["readable_content"],
        "acquisition_outcome": draft.get("acquisition_outcome") or "unknown",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blocking_warnings": blockers,
        "provenance_warnings": warnings,
        "duplicate": dup,
        "entity_match": entity,
        "needs_attention_rank": _attention_rank(draft, blockers, warnings),
        "attention_reasons": draft.get("attention_reasons") or [w["code"] for w in blockers + warnings],
        "fixture_state": draft.get("fixture_state"),
        "permitted_commands": [],
        "decisions_enabled": False,
        "href": f"/review-ops/publications/{draft_id}",
    }
    return item


def project_detail(draft: dict[str, Any]) -> dict[str, Any]:
    """Detail projection with hydrated body for the private workspace only."""
    item = project_queue_item(draft)
    body_text, body_kind, limited = _extract_body(draft)
    provenance = draft.get("provenance_chain")
    if not isinstance(provenance, list):
        provenance = []
        for label, at in (
            ("discovered", item.get("discovered_at")),
            ("captured", item.get("captured_at")),
            ("staged_for_review", item.get("updated_at")),
        ):
            if at:
                provenance.append({"step": label, "at": at, "detail": label.replace("_", " ")})

    history = draft.get("review_history")
    if not isinstance(history, list):
        history = []

    content_digest = draft.get("review_content_digest") or _digest(
        {"id": item["draft_id"], "title": item["title"], "version": item["version"]}
    )
    source_url = draft.get("source_url") or draft.get("canonical_url")

    detail = {
        **item,
        "source_url": source_url,
        "source_type": draft.get("source_type"),
        "body_text": body_text,
        "body_kind": body_kind or item["content_class"],
        "limited_explanation": limited,
        "provenance_chain": provenance,
        "review_history": history,
        "review_version": item["version"],
        "review_content_digest": content_digest,
        "content_digest": content_digest,
        "provenance_digest": draft.get("provenance_digest") or _digest(provenance),
        "ai_enrichment": draft.get("ai_enrichment") or draft.get("untrusted_suggestions"),
        "trust_bands": _TRUST_BANDS,
        "atomic_evidence_note": (
            "Atomic Evidence is a separate private proposal gate. "
            "Publication approval is not Atomic Evidence approval."
        ),
        "permitted_commands": [],
        "decisions_enabled": False,
        "decision_controls": {
            "visible": True,
            "enabled": False,
            "reason": (
                "Decision service connection is not part of Publication Review "
                "read-only UI Slice 1. Controls are shown for migration fidelity only."
            ),
            "actions": [
                {"id": "approve_publication", "label": "Approve publication", "requires_confirm": True},
                {"id": "reject", "label": "Reject", "requires_reason": True},
                {"id": "defer", "label": "Defer", "requires_reason": False},
                {"id": "request_correction", "label": "Request correction", "requires_reason": True},
            ],
            "bulk_approval_available": False,
        },
    }
    return detail


def matches_content_filter(item: dict[str, Any], content_filter: str) -> bool:
    if content_filter in {"", "all", None}:
        return True
    if content_filter == "problem":
        return item.get("content_class") == "problem" or bool(item.get("blocking_warnings"))
    return item.get("content_class") == content_filter


def build_publication_review_readonly_view(
    *,
    drafts: list[dict[str, Any]],
    selected_id: str | None = None,
    content_filter: str = "all",
    load_error: str | None = None,
    loading: bool = False,
    source: str = "durable",
) -> dict[str, Any]:
    """Assemble queue + selected workspace for the private operator page."""
    queue = [project_queue_item(d) for d in drafts]
    queue.sort(key=lambda row: (0 if row["review_state"] in {"pending_review", "pending"} else 1, row["needs_attention_rank"], row["title"]))
    pending_count = sum(1 for row in queue if row["review_state"] in {"pending_review", "pending"})
    visible = [row for row in queue if matches_content_filter(row, content_filter)]

    selected = None
    detail = None
    if visible:
        if selected_id and any(row["draft_id"] == selected_id for row in visible):
            chosen_id = selected_id
        else:
            chosen_id = visible[0]["draft_id"]
        raw = next((d for d in drafts if str(d.get("draft_id") or d.get("id")) == chosen_id), None)
        if raw is not None:
            detail = project_detail(raw)
            selected = chosen_id
            for row in visible:
                row["selected"] = row["draft_id"] == chosen_id

    empty = not loading and not load_error and not queue
    return {
        "slice_id": SLICE_ID,
        "decisions_enabled": False,
        "bulk_approval_available": False,
        "source": source,
        "pending_count": pending_count,
        "total_count": len(queue),
        "content_filter": content_filter or "all",
        "filters": list(CONTENT_FILTERS),
        "queue": visible,
        "selected_id": selected,
        "detail": detail,
        "loading": loading,
        "error": load_error,
        "empty": empty,
        "empty_message": (
            "No durable publication-review queue is available in this environment. "
            "This page does not invent backlog from local rehearsal fixtures."
        ),
        "capability_banner": (
            "Read-only Slice 1 — publication review queue and workspace. "
            "Decision mutations are disconnected (decisions_enabled: false). "
            "Approve publication is not Evidence approval and is not available here."
        ),
    }


def load_rehearsal_fixture_records() -> list[dict[str, Any]]:
    """Load presentation-layer rehearsal records from the tests tree.

    Not authoritative production state. Callers must gate with
    ``rehearsal_ui_allowed()`` or use this only from tests.
    """
    path = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "publication_review_readonly_rehearsal.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("drafts") or [])


def select_source_drafts(
    *,
    durable_drafts: list[dict[str, Any]],
    allow_rehearsal: bool | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Prefer durable drafts; optionally fall back to rehearsal for verification."""
    if durable_drafts:
        return durable_drafts, "durable"
    if allow_rehearsal is None:
        allow_rehearsal = rehearsal_ui_allowed()
    if allow_rehearsal:
        return load_rehearsal_fixture_records(), "rehearsal"
    return [], "durable"
