"""Read-only company scope for older reviewed sources with missing entity links.

Reuse canonical conservative recall; a textual mention is not a reviewed link.
Never resolve provisional identities or write back inferred associations.
"""
from app.services.entity_alias_recall import match_evidence_to_entity


def source_reviewed(record):
    return (record.get("status") == "published" and not record.get("live")
            and record.get("trust_state") != "LIVE"
            and (record.get("submitted_by") != "auto" or record.get("review_state") == "validated"))


def candidates(entities, state, filters, *, subscribed=False):
    wanted = {filters.get("company")} - {None, ""}
    # List keys, rather than optional record IDs, are the persisted identity.
    subscriptions = set(state.get("digest_subscriptions") or [])
    for list_id, group in (state.get("company_lists") or {}).items():
        if not isinstance(group, dict) or group.get("archived"):
            continue
        if list_id == filters.get("list") or (subscribed and list_id in subscriptions):
            wanted.update(group.get("company_ids") or [])
    if filters.get("favorites") == "1":
        wanted.update(key for key, value in (state.get("entity_favorites") or {}).items() if value)
    if filters.get("tier"):
        wanted.update(key for key, row in entities.items()
                      if row.get("entity_type") == "company"
                      and str((state.get("entity_tiers") or {}).get(key) or "untiered") == filters["tier"])
    return [entities[key] for key in sorted(wanted) if key in entities
            and entities[key].get("entity_type") == "company"
            and entities[key].get("canonical") is not False]


def links(record, subjects):
    linked = set(record.get("entity_ids") or []) | set(record.get("company_ids") or [])
    mentions = []
    if source_reviewed(record):
        for entity in subjects:
            if entity["id"] in linked:
                continue
            match = match_evidence_to_entity(entity, record)
            if match:
                linked.add(entity["id"])
                mentions.append({"id": entity["id"], "name": entity.get("name") or entity["id"],
                                 "alias": match.alias, "field": match.field})
    return linked, mentions
