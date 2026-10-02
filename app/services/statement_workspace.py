"""Read-only statement presentation. Triage never implies Fact confirmation."""
from __future__ import annotations

from urllib.parse import quote, urlencode

from app.services.map_regions import public_source_url


STATE_LABELS = {
    "pending_confirmation": "Awaiting confirmation",
    "proposed": "Awaiting confirmation",
    "trusted_analyst": "Confirmed statement",
    "conflicting": "Conflicting statement",
    "superseded": "Superseded statement",
    "rejected": "Rejected statement",
    "removed": "Removed statement",
}
IMPORTANCE_LABELS = {"normal": "Normal priority", "important": "Important", "demoted": "Lower priority"}


def present_statements(rows, records, entities, *, return_to):
    """Enrich copies only; retain exact text, all passages and review history."""
    entities_by_id = {str(entity.get("id")): entity for entity in entities}
    result = []
    for raw in rows:
        row = dict(raw)
        item_id = str(row.get("feed_item_id") or "")
        record = records.get(item_id) or row.get("source_context") or {}
        state = str(row.get("statement_state") or "")
        row.update(
            state_label=STATE_LABELS.get(state, "Status unavailable"),
            importance_label=IMPORTANCE_LABELS.get(row.get("importance_state"), "Priority unavailable"),
            article_title=str(record.get("title") or "Article title unavailable"),
            article_source=str(record.get("source_name") or "Source unavailable"),
            article_date=str(record.get("published_date") or ""),
            source_url=public_source_url(record.get("source_url")),
            reader_url=("/intelligence/" + quote(item_id, safe="") + "?" + urlencode({"personal": "1", "return_to": return_to})) if item_id and item_id in records else "",
            subjects=[],
        )
        for entity_id in row.get("entity_ids") or []:
            entity = entities_by_id.get(str(entity_id)) or {}
            kind = entity.get("entity_type")
            if entity.get("name"):
                row["subjects"].append({
                    "name": entity["name"],
                    "href": ("/geographies/" if kind == "geography" else "/entities/" + str(kind) + "/") + quote(str(entity_id), safe="") if kind in {"company", "variety", "geography", "retailer"} else "",
                })
        result.append(row)
    return result
