"""Read-only navigation over existing Variety and company tracking records."""
from urllib.parse import urlencode

from app.services import company_directory, map_regions, personal_digest

ROLE_PREDICATES = {"owns", "develops", "licenses", "grows", "trials", "markets", "distributes"}


def company_actors(variety_id, relationships, entities):
    return {
        row["subject_id"] for row in relationships
        if row.get("object_id") == variety_id and row.get("status") == "active"
        and row.get("predicate") in ROLE_PREDICATES
        and entities.get(row.get("subject_id"), {}).get("entity_type") in {"company", "brand", "breeding_program"}
    }


def region_rows(entities, relationships, records, inbox_dir, authoring):
    private = map_regions.load(inbox_dir) if authoring else None
    return map_regions.catalog(entities, relationships, records, private)


def directory(cards, *, params, state, entities, relationships, regions):
    filters = {key: str(params.get(key) or "").strip() for key in ("letter", "favorites", "tier", "list", "growing_country")}
    filters["letter"] = filters["letter"].upper()
    if filters["letter"] not in {"", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ#"}:
        raise ValueError("Choose an alphabetical group")
    if filters["tier"] not in {"", *company_directory.TIERS} or filters["favorites"] not in {"", "1"}:
        raise ValueError("Choose supported company filters")
    groups = personal_digest.company_lists(state)
    if filters["list"] and not any(row["id"] == filters["list"] for row in groups):
        raise ValueError("Company list is unavailable")
    growing = {}
    for row in regions:
        if row["kind"] == "variety":
            growing.setdefault(row["entity_id"], []).append(row)
    rows = []
    for card in cards:
        actors = company_actors(card["id"], relationships, entities)
        if not company_directory.matches_marks(actors, state, favorites=filters["favorites"], tier=filters["tier"], list_id=filters["list"]):
            continue
        locations = growing.get(card["id"], [])
        if filters["growing_country"] and not any(row["geography_id"] == filters["growing_country"] for row in locations):
            continue
        additional_roles = {}
        for rel in relationships:
            party = entities.get(rel.get("subject_id"), {})
            predicate = rel.get("predicate")
            if rel.get("object_id") == card["id"] and rel.get("status") == "active" and party.get("id") in actors and predicate in {"licenses", "grows", "trials", "distributes"}:
                additional_roles[(predicate, party["id"])] = {"name": party["name"], "href": f"/entities/{party['entity_type']}/{party['id']}",
                    "label": {"licenses": "Licensee", "grows": "Grower", "trials": "Trial operator", "distributes": "Distributor"}[predicate]}
        rows.append({**card, "growing_regions": locations, "company_actors": sorted(actors), "additional_roles": list(additional_roles.values())})
    letters = {company_directory.initial(row["name"]) for row in rows}
    if filters["letter"]:
        rows = [row for row in rows if company_directory.initial(row["name"]) == filters["letter"]]
    rows.sort(key=lambda row: (row["name"].casefold(), row["id"]))
    query = {**dict(params), **filters, "view": "index"}
    query.pop("berry_choice", None)
    return {"variety_rows": rows, "letters": letters, "directory_filters": filters, "tiers": company_directory.TIERS,
            "lists": groups, "letter_urls": {letter: "/entities/variety?" + urlencode({**query, "letter": letter}) + "#variety-directory-results" for letter in ["", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ#"]}}


def candidate_queue(candidates, params):
    filters = {key: str(params.get(key) or "").strip() for key in ("q", "berry", "company", "status", "letter", "source")}
    filters["letter"] = filters["letter"].upper()
    if filters["letter"] not in {"", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ#"}:
        raise ValueError("Choose an alphabetical group")
    statuses = {row.get("identity_state", "unknown") for row in candidates}
    if filters["status"] and filters["status"] not in statuses:
        raise ValueError("Choose an available identity status")
    rows = []
    for row in candidates:
        knowledge = row.get("knowledge") or {}
        portfolios = row.get("portfolio_sources") or []
        companies = (knowledge.get("company_associations") or []) + (knowledge.get("source_companies") or []) + [c for source in portfolios for c in source.get("companies", [])]
        if filters["source"] and filters["source"] not in ((knowledge.get("evidence_ids") or []) + (row.get("corpus_evidence_ids") or []) + [source["id"] for source in portfolios]) and filters["source"] != row.get("source_id"):
            continue
        if row.get("status") == "rejected" and filters["status"] != "rejected":
            continue
        haystack = " ".join(str(row.get(key) or "") for key in ("candidate_name", "denomination", "breeder_code", "breeder_owner", "applicant"))
        haystack += " " + " ".join(item.get("name", "") for item in companies)
        haystack += " " + " ".join(str(source.get(key) or "") for source in portfolios for key in ("breeder_code", "trade_name", "candidate_name"))
        if filters["q"] and filters["q"].casefold() not in haystack.casefold():
            continue
        if filters["berry"] and filters["berry"] != row.get("berry_id"):
            continue
        if filters["company"] and not any(item.get("entity_id") == filters["company"] for item in companies):
            continue
        if filters["status"] and filters["status"] != row.get("identity_state"):
            continue
        rows.append(row)
    letters = {company_directory.initial(row["candidate_name"]) for row in rows}
    if filters["letter"]:
        rows = [row for row in rows if company_directory.initial(row["candidate_name"]) == filters["letter"]]
    companies = {item["entity_id"]: item["name"] for row in candidates for item in
                 ((row.get("knowledge") or {}).get("company_associations") or []) +
                 ((row.get("knowledge") or {}).get("source_companies") or []) +
                 [c for source in row.get("portfolio_sources") or [] for c in source.get("companies", [])]}
    return {"candidates": sorted(rows, key=lambda row: (row["candidate_name"].casefold(), row["id"])), "candidate_total": len(candidates),
            "filters": filters, "letters": letters, "candidate_companies": sorted(companies.items(), key=lambda row: row[1].casefold()),
            "candidate_statuses": sorted({row.get("identity_state", "unknown") for row in candidates}),
            "letter_urls": {letter: "/varieties/candidates?" + urlencode({**filters, "letter": letter}) + "#candidate-results" for letter in ["", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ#"]}}
