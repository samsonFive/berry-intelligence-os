"""Company coverage by publication date, separate from factual-claim approval."""
from datetime import date, timedelta

from app.services.chronology import parse_stamp
from app.services.entity_alias_recall import linked_evidence_for_entity
from app.services.evidence_claim_review import trust_tier_label
from app.services.source_body import reader_content


def company_news_coverage(company, *, published, pending=(), days=90, today=None):
    end = today or date.today()
    start = end - timedelta(days=days - 1)
    records = linked_evidence_for_entity(company, list(published) + list(pending))
    current, undated = [], []
    historical = 0
    seen = set()
    for record in records:
        if not record.get("id") or record["id"] in seen or record.get("status") in {"rejected", "archived"}:
            continue
        seen.add(record["id"])
        stamp = parse_stamp(record.get("published_date"))
        if stamp and not start <= stamp.date() <= end:
            historical += stamp.date() < start
            continue
        content = reader_content(record)
        is_published = record.get("status") == "published"
        row = {
            "id": record["id"], "title": record.get("title") or record["id"],
            "source_name": record.get("source_name") or "Source not recorded",
            "source_url": record.get("source_url") or "",
            "published_date": stamp.date().isoformat() if stamp else "",
            "captured_date": record.get("captured_date") or "",
            "href": "/intelligence/" + record["id"],
            "summary": content["summary"], "notice": content["notice"],
            "content_state": content["label"],
            "excerpt": " ".join(content["body"].split()[:25]) if content["usable_in_app"] else "",
            "trust_label": trust_tier_label(record) if is_published else "PENDING SOURCE REVIEW",
            "pending": not is_published,
            "match_basis": "Named source mention" if record.get("link_mechanism") == "alias_recall" else "Linked company",
        }
        (current if stamp else undated).append(row)
    current.sort(key=lambda r: (r["published_date"], r["id"]), reverse=True)
    return {"items": current, "undated": undated, "historical_count": historical,
            "start": start.isoformat(), "end": end.isoformat(), "days": days,
            "pending_count": sum(r["pending"] for r in current),
            "usable_count": sum(bool(r["excerpt"]) for r in current)}
