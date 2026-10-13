"""Read-only candidate → existing source-review preparation. Never authors entities."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlencode

from app.services.entity_identity import match_named_entity
from app.services.map_regions import public_source_url


def decision_digest(candidate: dict) -> str:
    fields = ("id", "candidate_name", "berry_id", "identity_state", "status", "human_gated",
              "reviewer", "reviewed_at", "review_notes", "candidate_canonical_match")
    payload = {key: candidate.get(key) for key in fields}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def catalog_handoff(candidate: dict, varieties: list[dict]) -> dict:
    name = str(candidate.get("candidate_name") or "").strip()
    matched, ambiguous = match_named_entity(name, "variety", varieties, berry_id=candidate.get("berry_id") or "")
    reason = ""
    if not name:
        reason = "Record the variety name before preparing catalog review."
    elif ambiguous:
        reason = "This name matches multiple catalog records. Resolve the identity first."
    elif matched:
        reason = "This name is already represented in the catalog. Review its source and profile there."
    elif candidate.get("status") != "reviewed" or candidate.get("identity_state") != "distinct" or candidate.get("human_gated") is not True or not str(candidate.get("reviewer") or "").strip() or not candidate.get("reviewed_at"):
        reason = "Check the identity and mark it distinct before preparing a new catalog record."
    elif candidate.get("berry_id") not in {"berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"}:
        reason = "The berry must be established before preparing catalog review."
    choices = []
    for source in candidate.get("portfolio_sources") or []:
        url = public_source_url(source.get("product_url") or source.get("url"))
        if url and not any(item["url"] == url for item in choices):
            choices.append({"url": url, "label": source.get("title") or "Primary source", "checked_on": source.get("checked_on")})
    url = public_source_url(candidate.get("source_url"))
    if url and not any(item["url"] == url for item in choices):
        choices.append({"url": url, "label": candidate.get("source_label") or "Recorded source", "checked_on": None})
    return {"ready": not reason, "reason": reason, "catalog_entity": matched,
            "href": "/intake?" + urlencode({"type": "article_or_url", "catalog_candidate": candidate["id"]}),
            "decision_digest": decision_digest(candidate), "source_choices": choices}


def validate_handoff(candidate: dict, varieties: list[dict], digest: str) -> dict:
    plan = catalog_handoff(candidate, varieties)
    if digest != plan["decision_digest"]:
        raise ValueError("The identity decision changed. Reopen the candidate and prepare review again.")
    if not plan["ready"]:
        raise ValueError(plan["reason"])
    return plan
