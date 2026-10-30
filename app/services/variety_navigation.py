"""Read-only navigation over existing Variety and company tracking records."""
from urllib.parse import urlencode
from datetime import date
import unicodedata

from app.services import company_directory, map_regions, personal_digest

ROLE_PREDICATES = {"owns", "develops", "licenses", "grows", "trials", "markets", "distributes"}
ROLE_LABELS = {
    'develops': 'Breeder', 'owns': 'Rights holder', 'licenses': 'Licensee',
    'markets': 'Marketer', 'grows': 'Grower', 'distributes': 'Distributor',
    'trials': 'Trial operator',
}


def _search_text(value):
    """Ignore accents for navigation, retaining letters, spacing and code punctuation."""
    return "".join(char for char in unicodedata.normalize("NFD", value.casefold())
                   if not unicodedata.combining(char))


def company_actors(variety_id, relationships, entities):
    return {
        row["subject_id"] for row in relationships
        if row.get("object_id") == variety_id and row.get("status") == "active"
        and row.get("predicate") in ROLE_PREDICATES
        and entities.get(row.get("subject_id"), {}).get("entity_type") in {"company", "brand", "breeding_program"}
    }


def program_variety_rows(entity_id, entities, relationships):
    """Recorded program/brand links when no company portfolio is available.

    This navigation view does not fabricate a company dossier or locations.
    """
    if entities.get(entity_id, {}).get('entity_type') not in {'brand', 'breeding_program'}:
        return []
    from app.services.variety_universe.coverage import BERRY_LABELS
    rows = []
    for variety in entities.values():
        if variety.get('entity_type') != 'variety' or entity_id not in company_actors(variety['id'], relationships, entities):
            continue
        roles = {ROLE_LABELS[rel['predicate']] for rel in relationships
                 if rel.get('subject_id') == entity_id and rel.get('object_id') == variety['id']
                 and rel.get('status') == 'active' and rel.get('predicate') in ROLE_LABELS}
        rows.append({'id': variety['id'], 'name': variety['name'],
                     'href': '/entities/variety/' + variety['id'], 'roles': sorted(roles),
                     'berries': [BERRY_LABELS.get(b, b) for b in variety.get('berry_ids') or []]})
    return sorted(rows, key=lambda row: (row['name'].casefold(), row['id']))


def region_rows(entities, relationships, records, inbox_dir, authoring):
    private = map_regions.load(inbox_dir) if authoring else None
    return map_regions.catalog(entities, relationships, records, private)


def directory(cards, *, params, state, entities, relationships, regions):
    filters = {key: str(params.get(key) or "").strip() for key in ("letter", "favorites", "tier", "list", "growing_country", "sort")}
    filters['sort'] = filters['sort'] or 'name'
    if filters['sort'] not in {'name', 'recent_desc', 'recent_asc'}:
        raise ValueError('Choose a supported variety sort order')
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
    if filters['sort'] != 'name':
        dated, undated = [], []
        for row in rows:
            try:
                stamp = date.fromisoformat(str((row.get('recent') or {}).get('date') or '')[:10])
            except ValueError:
                undated.append(row)
            else:
                dated.append((stamp, row))
        # Stable date sorting keeps equal dates alphabetical, and missing dates last.
        dated.sort(key=lambda pair: pair[0], reverse=filters['sort'] == 'recent_desc')
        rows = [row for _, row in dated] + undated
    query = {**dict(params), **filters, "view": "index"}
    query.pop("berry_choice", None)
    return {"variety_rows": rows, "letters": letters, "directory_filters": filters, "tiers": company_directory.TIERS,
            "recent_sort_url": '/entities/variety?' + urlencode({**query, 'sort': 'recent_asc' if filters['sort'] == 'recent_desc' else 'recent_desc'}) + '#variety-directory-results',
            "lists": groups, "letter_urls": {letter: "/entities/variety?" + urlencode({**query, "letter": letter}) + "#variety-directory-results" for letter in ["", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ#"]}}


def candidate_queue(candidates, params):
    filters = {key: str(params.get(key) or "").strip() for key in ("q", "berry", "company", "status", "letter", "source")}
    if filters['source'] and params.get('discovery') == 'source-text':
        filters['discovery'] = 'source-text'
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
        scoped_portfolios = [source for source in portfolios if source["id"] == filters["source"]]
        if scoped_portfolios:
            companies = [c for source in scoped_portfolios for c in source.get("companies", [])]
        if filters["source"] and filters["source"] not in ((knowledge.get("evidence_ids") or []) + (row.get("corpus_evidence_ids") or []) + [source["id"] for source in portfolios]) and filters["source"] != row.get("source_id"):
            continue
        if row.get("status") == "rejected" and filters["status"] != "rejected":
            continue
        haystack = " ".join(str(row.get(key) or "") for key in ("candidate_name", "denomination", "breeder_code", "breeder_owner", "applicant"))
        haystack += " " + " ".join(item.get("name", "") for item in companies)
        # Source wording can contain additional trial codes without making them
        # approved aliases. Search that context without changing identity keys.
        haystack += " " + " ".join(str(source.get(key) or "") for source in portfolios for key in ("breeder_code", "trade_name", "candidate_name", "portfolio_context", "source_company_context"))
        if filters["q"] and _search_text(filters["q"]) not in _search_text(haystack):
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
