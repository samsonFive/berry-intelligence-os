"""Read existing Fact records and their published sources; never change trust."""
from urllib.parse import quote

from app.services.map_regions import public_source_url
from app.services.company_source_scope import source_reviewed


PUBLIC_STATUSES = {"active", "disputed"}
HISTORY_STATUSES = PUBLIC_STATUSES | {"superseded", "withdrawn"}


def statement_detail(fact, evidence, entities, *, include_history=False):
    """One source-backed statement, keeping claims and history explicit.

    Callers supply the existing output-eligible Fact and Evidence populations.
    Missing, unpublished and unvalidated source details are never exposed by
    following a reference. No private triage/extraction store is consulted.
    """
    if (not fact or fact.get("record_type") != "fact"
            or fact.get("classification") not in {"fact", "claim"}
            or fact.get("status") not in (HISTORY_STATUSES if include_history else PUBLIC_STATUSES)):
        return None
    available = {row["id"]: row for row in evidence
                 if row.get("id") and source_reviewed(row)
                 and (not row.get("auto_captured") or row.get("validated") is True)}
    references = list(dict.fromkeys(fact.get("evidence_ids") or []))
    sources = []
    for identity in references:
        source = available.get(identity)
        if source is None:
            continue
        encoded = quote(identity, safe="")
        sources.append({"id": identity, "title": source.get("title") or "Source title not recorded",
                        "publisher": source.get("source_name") or "Publisher not recorded",
                        "published_date": source.get("published_date"),
                        "original_url": public_source_url(source.get("source_url") or ""),
                        "record_href": "/evidence/" + encoded,
                        "reader_href": "/intelligence/" + encoded})
    return {"statement": fact["statement"], "classification": fact["classification"],
            "status": fact["status"], "confidence": fact.get("confidence"),
            "recorded_date": fact.get("created_at"), "event_date": fact.get("event_date"),
            "reviewer": fact.get("reviewer"), "sources": sources,
            "unavailable_sources": len(references) - len(sources),
            "linked_entities": [entities[identity] for identity in dict.fromkeys(fact.get("entity_ids") or [])
                                if identity in entities],
            "is_history": fact["status"] in {"superseded", "withdrawn"}}
