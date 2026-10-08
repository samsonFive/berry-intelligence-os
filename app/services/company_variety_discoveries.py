"""Company context for reconciled source names, without approving relationships."""
from urllib.parse import urlencode

from app.services.company_directory import initial
from app.services.variety_universe.coverage import BERRY_LABELS
from app.services.variety_portfolio_coverage import _public_url


def company_variety_discoveries(*, entity_id, sources, linked_variety_ids=(), error=""):
    selected = [source for source in sources if entity_id in source.get("company_ids", [])]
    grouped, linked, rejected = {}, set(), set()
    for source in selected:
        for name in source["names"]:
            # Reuse reconciliation's code-aware identity key. Shared marketing
            # labels with different breeder codes must remain separate rows.
            key = tuple(name["identity_key"])
            if name["catalog_id"] in linked_variety_ids:
                linked.add(key)
                continue
            if name["status"] == "previously_rejected":
                rejected.add(key)
                continue
            code = name.get("denomination") or name.get("breeder_code") or ""
            label = name.get("display_label") or name.get("trade_name") or name["candidate_name"]
            row = grouped.setdefault(key, {
                "name": label, "code": code, "berry_id": name["berry_id"],
                "berry": BERRY_LABELS.get(name["berry_id"], name["berry_id"]),
                "status": name["status"], "catalog_id": name["catalog_id"],
                "href": name["href"], "sources": [], "notes": [], "search_terms": [],
                "review_label": "Open catalog" if name["catalog_id"] else "Review name",
                "label": {"catalog_match": "Company link needs review",
                          "needs_review": "Name needs review",
                          "distinct_awaiting_catalog": "Catalog entry pending"}[name["status"]],
            })
            if not name["catalog_id"]:
                params = {"company": entity_id, "berry": name["berry_id"],
                          "source": source["id"], "q": name["candidate_name"]}
                row["href"] = "/varieties/candidates?" + urlencode(params)
                if name.get("candidate_id"):
                    row["href"] += "#" + name["candidate_id"]
            row["search_terms"].extend(str(name.get(field) or "") for field in
                ("candidate_name", "denomination", "breeder_code", "trade_name", "display_label"))
            row["notes"].extend(name.get("identity_notes", []))
            if name.get("identity_notes") and row["status"] == "needs_review":
                row["label"] = "Name / code conflict"
            if name.get("portfolio_context"):
                row["notes"].append(name["portfolio_context"])
            href = name.get("product_url") or source["url"]
            row["sources"].append({
                "id": source["id"], "title": source["title"],
                "href": href if _public_url(href) else source["url"],
                "checked_on": source["checked_on"],
                "context": "Recommendation list" if source["source_type"] == "extension_recommendation" else
                    "Trial list" if source["source_type"] in {"trial_report", "university_trial"} else "Source names",
            })
    # A closed human decision takes precedence over another occurrence of a name.
    for key in linked | rejected:
        grouped.pop(key, None)
    rows = sorted(grouped.values(), key=lambda row: (row["name"].casefold(), row["code"], row["berry_id"]))
    for row in rows:
        row["letter"] = initial(row["name"])
        row["search"] = " ".join(row.pop("search_terms")).casefold()
        row["notes"] = sorted(set(row["notes"]))
        row["sources"] = list({(item["id"], item["href"]): item for item in row["sources"]}.values())
    return {
        "rows": rows, "source_count": len(selected), "linked_count": len(linked),
        "rejected_count": len(rejected), "error": bool(error),
        "follow_up_count": sum(bool(source.get("needs_follow_up")) for source in selected),
        "letters": sorted({row["letter"] for row in rows}),
        "berries": sorted({(row["berry_id"], row["berry"]) for row in rows}, key=lambda item: item[1]),
        "coverage_href": "/varieties/coverage?" + urlencode({"company": entity_id}),
        "review_href": "/varieties/candidates?" + urlencode({"company": entity_id}),
    }
