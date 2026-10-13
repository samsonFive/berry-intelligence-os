"""Read-only, berry-neutral landscapes. Every edge remains a registry relationship.

The same complete bundle drives the portrait, chronology, explanations and exports.
Company locations never materialize variety locations. Source review is not claim
verification. No extraction, mutation, external inference or private annotations here.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
from threading import RLock
from urllib.parse import urlencode, urlsplit

from app.services.geography_hierarchy import geography_descendants
from app.services.source_independence import independence_report
from app.services.variety_universe.corpus_discovery import discover_corpus_variety_mentions, source_catalog_coverage
from app.services.variety_universe.coverage import BERRY_ORDER
from app.services.berries.variety import variety_trait_profile
from app.services import company_directory, personal_digest

ENGINE_VERSION = "landscape-5"
GENETIC_TYPES = {"variety", "breeding_program"}
ACTOR_TYPES = {"company", "breeding_program", "variety"}
ROLE_LABELS = {"develops": "Breeder / developer", "owns": "Owner / rights holder",
               "licenses": "Licensee", "grows": "Grower", "markets": "Marketer",
               "distributes": "Distributor", "trials": "Trial participant",
               "sells": "Seller", "partners_with": "Partner", "operates_in": "Location relationship"}
QUESTIONS = {"markets": "What connects these selected markets?",
             "genetics": "Who develops or controls these genetics?",
             "changes": "What changed in this window?"}
_CACHE: OrderedDict = OrderedDict()
_CACHE_LOCK = RLock()


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (ValueError, TypeError):
        return None


def _values(params, key):
    values = params.getlist(key) if hasattr(params, "getlist") else [params.get(key, "")]
    return sorted({part.strip() for value in values for part in str(value).split(",") if part.strip()})


def selection(params, entities, *, today=None, state=None):
    today = today or date.today()
    # Generic service accepts known berries; the route exposes the app's four crop categories.
    berry = str(params.get("berry") or "berry-blueberry")
    available = [key for key in BERRY_ORDER if key in entities and entities[key].get("entity_type") == "berry"]
    if berry != "all" and berry not in available:
        raise ValueError("Choose a registered berry.")
    compare = str(params.get("compare") or next((key for key in available if key != berry), ""))
    if compare and compare not in available:
        raise ValueError("Choose a registered berry to compare.")
    if str(params.get("pair") or "") not in {"", "1"}:
        raise ValueError("Choose a supported comparison scope.")
    comparing = params.get("view") == "compare" or params.get("pair") == "1"
    if comparing and (berry == "all" or not compare or compare == berry):
        raise ValueError("Comparison needs two different berries. Choose a first berry and a second berry.")
    berry_scope = available if berry == "all" else [berry, compare] if comparing else [berry]
    countries = (_values(params, "countries") if "countries" in params else
                 ["geography-chile", "geography-china", "geography-peru"] if berry == "berry-blueberry" and not comparing else [])
    if any(key not in entities or entities[key].get("entity_type") != "geography" for key in countries):
        raise ValueError("Choose registered countries or regions.")
    focus = str(params.get("focus") or "")
    if focus and (focus not in entities or entities[focus].get("entity_type") not in ACTOR_TYPES):
        raise ValueError("The selected company, program or variety is unavailable.")
    if (focus and entities[focus].get("entity_type") in GENETIC_TYPES
            and entities[focus].get("berry_ids") and not set(berry_scope).intersection(entities[focus]["berry_ids"])):
        raise ValueError("This program or variety is outside the selected berry; choose its berry or reset focus.")
    enums = {"predicate": ("", *ROLE_LABELS), "evidence": ("reviewed", "all"),
             "status": ("all", "active", "historical", "disputed"),
             "view": ("portrait", "changes", "explain", "relationships", "compare"),
             "window": ("all", "7d", "30d", "ytd", "custom"),
             "time": ("documented", "published", "event"),
             "question": tuple(QUESTIONS), "theme": ("light", "dark")}
    defaults = {key: values[0] for key, values in enums.items()}
    result = {key: str(params.get(key, defaults[key])) for key in enums}
    result.update({key: str(params.get(key) or "") for key in ("favorites", "tier", "list")})
    if result["favorites"] not in {"", "1"} or result["tier"] not in {"", *company_directory.TIERS}:
        raise ValueError("Choose supported company favorites and tiers.")
    lists = {row["id"]: row for row in personal_digest.company_lists(state or {})}
    if result["list"] and result["list"] not in lists:
        raise ValueError("This company list is unavailable or archived. Choose a current list.")
    if any(result[key] not in values for key, values in enums.items()):
        raise ValueError("A landscape filter is invalid.")
    start, end = "", ""
    if result["window"] == "custom":
        start, end = _day(params.get("start")), _day(params.get("end"))
        if not start or not end or start > end:
            raise ValueError("Enter a valid start and end date, in chronological order.")
    elif result["window"] != "all":
        end = today.isoformat()
        start = (date(today.year, 1, 1) if result["window"] == "ytd" else today - timedelta(days=int(result["window"][:-1]) - 1)).isoformat()
    try:
        limit = min(5000, max(20, int(params.get("limit", 100))))
    except (TypeError, ValueError) as exc:
        raise ValueError("The display limit is invalid.") from exc
    edge = str(params.get("edge") or "")
    return {**result, "berry": berry, "compare": compare, "pair": "1" if comparing else "", "countries": countries, "focus": focus,
            "q": str(params.get("q") or "").strip()[:200], "start": start or "", "end": end or "",
            "limit": limit, "edge": edge}


def href(filters, **changes):
    values = {**filters, **changes}
    values["countries"] = ",".join(values["countries"]) if isinstance(values.get("countries"), list) else values.get("countries", "")
    return "/landscapes/explorer?" + urlencode(values)


def _source(row):
    raw_url = str(row.get("source_url") or "")
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        parsed = urlsplit("")
    safe_url = raw_url if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username else ""
    return {"id": row["id"], "title": row.get("title") or row["id"], "url": safe_url,
            "source_name": row.get("source_name") or "Source name not recorded", "status": row.get("status"),
            "review": "Reviewed source · claims retain their own review" if row.get("status") == "published" else "Unreviewed source",
            "published": _day(row.get("published_date")), "captured": _day(row.get("captured_date")),
            "summary": row.get("summary") or "No source summary recorded.",
            "significance": row.get("why_it_matters") or "",
            "locator": row.get("supporting_excerpt") or row.get("excerpt") or row.get("source_locator") or "No verbatim excerpt recorded; inspect the relationship notes and original source.",
            "origin": row.get("submitted_by") or row.get("source_system") or "Registry record; extraction version not recorded"}


def _caveat(row):
    notes = str(row.get("notes") or "")
    lower = notes.lower()
    if "intention" in lower or "intent signal" in lower or "stated intention" in lower:
        return "Intent only · not an established operation"
    if "rights enforcement" in lower or "rights-enforcement" in lower or "rights-holding and enforcement" in lower:
        return "Rights enforcement · production not established"
    if "incorporation" in lower or "registered office" in lower or "registeredoffice" in lower:
        return "Registered office · growing not established"
    if "test station" in lower or "teststation" in lower or "test-station" in lower:
        return "Test station · variety presence not established"
    if "inferred only" in lower or "breeding origin is not stated" in lower:
        return "Limited support · verify the stated role"
    if "substituted predicate" in lower:
        return "Legacy role mapping · verify the source"
    return ""


def _location_label(row):
    caveat = _caveat(row)
    labels = {"Intent only": "Planned market entry", "Rights enforcement": "IP rights enforcement",
              "Registered office": "Registered office", "Test station": "Breeding test site"}
    for prefix, label in labels.items():
        if caveat.startswith(prefix):
            return label
    notes = str(row.get("notes") or "").lower()
    for phrase, label in [("self-reported production", "Company-reported production"),
                          ("variety validation programme", "Variety validation programme"),
                          ("growing country and licensing", "Growing & licensing region"),
                          ("operations at", "Local operations")]:
        if phrase in notes:
            return label
    return "Location reported · check source"


def build_bundle(entities, relationships, evidence, params, *, today=None, state=None):
    """Complete selected scope; visibility limits apply only to the web portrait.

    Fingerprinting includes deletions and source edits, not a TTL. Cached values
    are copied so a caller cannot poison later UI/export responses.
    """
    today = today or date.today()
    state = state or {}
    filters = selection(params, entities, today=today, state=state)
    fingerprint = hashlib.sha256(json.dumps([ENGINE_VERSION, entities, sorted(relationships, key=lambda r: r["id"]),
                                            sorted(evidence, key=lambda r: r["id"])], sort_keys=True, default=str).encode()).hexdigest()
    mark_signature = {key: state.get(key) or {} for key in ("entity_favorites", "entity_tiers", "company_lists")}
    cache_key = fingerprint + json.dumps([filters, mark_signature], sort_keys=True) + today.isoformat()
    with _CACHE_LOCK:
        if cache_key in _CACHE:
            _CACHE.move_to_end(cache_key)
            return deepcopy(_CACHE[cache_key])
    if filters["berry"] == "all" or filters["pair"]:
        bundle = _combined_bundle(entities, relationships, evidence, filters, fingerprint, today, state)
        _remember(cache_key, bundle)
        return bundle
    records = {row["id"]: row for row in evidence if row.get("status") == "published" or
               (filters["evidence"] == "all" and row.get("status") == "in_review")}
    country_scope = set(filters["countries"])
    for country in filters["countries"]:
        country_scope.update(geography_descendants(country, relationships=relationships))
    berry = filters["berry"]
    candidates, excluded = [], {"missing_endpoints": 0, "unavailable_sources": 0}
    for row in sorted(relationships, key=lambda r: r["id"]):
        left, right = entities.get(row.get("subject_id")), entities.get(row.get("object_id"))
        if not left or not right:
            excluded["missing_endpoints"] += 1
            continue
        types = {left.get("entity_type"), right.get("entity_type")}
        if not types <= ACTOR_TYPES | {"geography"} or types == {"geography"}:
            continue
        genetic = [node for node in (left, right) if node.get("entity_type") in GENETIC_TYPES]
        explicit_tags = [set(node.get("berry_ids") or []) for node in genetic if node.get("berry_ids")]
        tags = set(row.get("berry_ids") or []) | set(left.get("berry_ids") or []) | set(right.get("berry_ids") or [])
        source_tags = {tag for sid in row.get("evidence_ids", []) for tag in records.get(sid, {}).get("berry_ids", [])}
        if (row.get("berry_ids") and berry not in row["berry_ids"] or
                any(berry not in tagset for tagset in explicit_tags) or berry not in tags | source_tags):
            continue
        if row.get("predicate") not in ROLE_LABELS or row.get("status") not in {"active", "historical", "disputed"}:
            continue
        source_ids = [sid for sid in row.get("evidence_ids", []) if sid in records]
        if not source_ids:
            excluded["unavailable_sources"] += 1
            continue
        if "geography" in types and country_scope and not ({left["id"], right["id"]} & country_scope):
            continue
        source_rows = [records[sid] for sid in source_ids]
        publication = sorted({_day(r.get("published_date")) for r in source_rows} - {None})
        captured = sorted({_day(r.get("captured_date")) for r in source_rows} - {None})
        effective = _day(row.get("effective_date"))
        dates = {"event": [effective] if effective else [], "published": publication,
                 "documented": captured[:1]}
        selected_dates = dates[filters["time"]]
        in_window = any((not filters["start"] or d >= filters["start"]) and
                        (not filters["end"] or d <= filters["end"]) for d in selected_dates)
        candidates.append({"id": row["id"], "subject_id": left["id"], "object_id": right["id"],
                           "berry_ids": [berry],
                           "predicate": row["predicate"], "role": ROLE_LABELS[row["predicate"]],
                           "status": row["status"], "status_label": {"active": "Documented relationship", "historical": "Historical relationship", "disputed": "Disputed / review required"}[row["status"]],
                           "review": "Includes unreviewed source" if any(r.get("status") != "published" for r in source_rows) else "Reviewed sources",
                           "evidence_ids": source_ids, "unavailable_evidence_count": len(row.get("evidence_ids", [])) - len(source_ids),
                           "notes": row.get("notes") or "No relationship notes recorded.", "caveat": _caveat(row),
                           "location_label": _location_label(row),
                           "confidence": row.get("confidence") or (match.group(1) if (match := re.search(r"\bconfidence=(low|medium|high)\b", str(row.get("notes") or ""))) else "Not recorded"), "effective": effective,
                           "published": publication, "first_seen": captured[0] if captured else None,
                           "in_window": in_window, "time_dates": selected_dates,
                           "genetic_geography": bool(genetic and "geography" in types),
                           "company_geography": "company" in types and "geography" in types,
                           "scope_kind": "Exact genetic location relationship" if genetic and "geography" in types else "Company location; not variety presence" if "geography" in types else "Genetic / company relationship; location not established"})
    seeds = {edge["subject_id"] for edge in candidates if edge["object_id"] in country_scope} | {edge["object_id"] for edge in candidates if edge["subject_id"] in country_scope}
    if not country_scope:
        seeds = {key for edge in candidates for key in (edge["subject_id"], edge["object_id"])}
    if filters["focus"]:
        seeds.add(filters["focus"])
    # Resolve the exact connected component once, independent of display role
    # filters. Adding a focus already in the bundle cannot change export scope.
    # Follow only typed stored links; never traverse geography to infer genetics.
    reached = set(seeds)
    adjacency = {}
    for edge in candidates:
        if "geography" not in {entities[edge["subject_id"]]["entity_type"], entities[edge["object_id"]]["entity_type"]}:
            adjacency.setdefault(edge["subject_id"], set()).add(edge["object_id"])
            adjacency.setdefault(edge["object_id"], set()).add(edge["subject_id"])
    frontier = list(seeds)
    while frontier:
        node = frontier.pop()
        for neighbor in adjacency.get(node, set()) - reached:
            reached.add(neighbor)
            frontier.append(neighbor)
    edges = [edge for edge in candidates if {edge["subject_id"], edge["object_id"]} <= reached | country_scope]
    edges = [edge for edge in edges if (not filters["predicate"] or edge["predicate"] == filters["predicate"]) and
             (filters["status"] == "all" or edge["status"] == filters["status"])]
    if filters["q"]:
        query = filters["q"].casefold()
        matches = {key for key in reached if query in " ".join([str(entities[key].get("name", "")), *[str(a) for a in entities[key].get("aliases", [])]]).casefold()}
        edges = [edge for edge in edges if {edge["subject_id"], edge["object_id"]} & matches]
    edges, company_scope = _company_scope(edges, candidates, entities, filters, state)
    bundle = _assemble_bundle(entities, relationships, records, filters, edges, fingerprint, excluded, company_scope)
    _remember(cache_key, bundle)
    return bundle


def _remember(cache_key, bundle):
    with _CACHE_LOCK:
        _CACHE[cache_key] = deepcopy(bundle)
        while len(_CACHE) > 12:
            _CACHE.popitem(last=False)


def browser_bundle(bundle):
    """Interactive core; server-rendered tables need not be duplicated in JSON."""
    return {**{key: bundle[key] for key in ("contract", "version", "filters", "nodes", "edges", "sources")},
            "crop_scopes": [{"id": c["id"], "edge_ids": c["edge_ids"]} for c in bundle.get("crop_scopes", [])]}


def _trait_value(value):
    if isinstance(value, dict):
        return "; ".join(str(key).replace("_", " ") + ": " + _trait_value(item) for key, item in value.items())
    if isinstance(value, list):
        return "; ".join(_trait_value(item) for item in value)
    return "Not recorded" if value is None else str(value)


def _company_scope(edges, candidates, entities, filters, state):
    active = bool(filters["favorites"] or filters["tier"] or filters["list"])
    labels = (["Favorites"] if filters["favorites"] else []) + ([company_directory.TIERS[filters["tier"]]] if filters["tier"] else [])
    if filters["list"]:
        labels.append(next(str(row.get("name") or "Unnamed company list") for row in personal_digest.company_lists(state) if row["id"] == filters["list"]))
    context = {"active": active, "labels": labels, "basis": []}
    if not active:
        return edges, context
    matching = {key for key, row in entities.items() if row.get("entity_type") in {"company", "breeding_program"}
                and company_directory.matches_marks([key], state, favorites=filters["favorites"], tier=filters["tier"], list_id=filters["list"])}
    scope, ownership = set(matching), {}
    changed = True
    while changed:
        changed = False
        for edge in candidates:
            if (edge["predicate"] == "owns" and edge["subject_id"] in scope
                    and entities[edge["object_id"]].get("entity_type") == "breeding_program"
                    and (filters["status"] == "all" or edge["status"] == filters["status"])):
                ownership[edge["id"]] = edge
                if edge["object_id"] not in scope:
                    scope.add(edge["object_id"]); changed = True
    selected = [edge for edge in edges if {edge["subject_id"], edge["object_id"]} & scope]
    # Keep complete ownership paths to a selected program, even when a role
    # filter hides those edges. Their sources remain explicit context, not new
    # inferred relationships or transferred breeder/owner roles.
    needed = {key for edge in selected for key in (edge["subject_id"], edge["object_id"])}
    while True:
        parents = {edge["subject_id"] for edge in ownership.values() if edge["object_id"] in needed}
        if parents <= needed:
            break
        needed.update(parents)
    selected_ids = {edge["id"] for edge in selected}
    context["basis"] = [{**deepcopy(edge), "label": entities[edge["subject_id"]].get("name", edge["subject_id"]) + " has a recorded ownership link to " + entities[edge["object_id"]].get("name", edge["object_id"]),
                         "subject_label": entities[edge["subject_id"]].get("name", edge["subject_id"]), "object_label": entities[edge["object_id"]].get("name", edge["object_id"]),
                         "subject_identity_status": entities[edge["subject_id"]].get("status") or "Not recorded", "object_identity_status": entities[edge["object_id"]].get("status") or "Not recorded"}
                        for edge in ownership.values() if edge["object_id"] in needed and edge["id"] not in selected_ids]
    return selected, context


def _assemble_bundle(entities, relationships, records, filters, edges, fingerprint, excluded, company_scope=None):
    """One projection shared by single-crop, union and comparison exports."""
    used = {key for edge in edges for key in (edge["subject_id"], edge["object_id"])}
    node_rows = [{"id": key, "label": entities[key].get("name") or key, "type": entities[key]["entity_type"],
                  "aliases": entities[key].get("aliases") or [], "berry_ids": entities[key].get("berry_ids") or [],
                  "identity_status": entities[key].get("status") or "Not recorded",
                  "identity_note": "Provisional identity · review needed" if entities[key].get("status") == "unverified" else "",
                  "evidence_ids": sorted({sid for edge in edges if key in {edge["subject_id"], edge["object_id"]} for sid in edge["evidence_ids"]})}
                 for key in sorted(used, key=lambda key: (entities[key].get("name", key).casefold(), key))]
    nodes = {row["id"]: row for row in node_rows}
    company_scope = company_scope or {"active": False, "labels": [], "basis": []}
    sources = [_source(records[key]) for key in sorted({sid for edge in [*edges, *company_scope["basis"]] for sid in edge["evidence_ids"]})]
    for number, source in enumerate(sources, 1):
        source["number"] = number
    # Reuse stored variety traits, with every cited source eligible in this
    # exact selection. Never rank incomparable measurements or infer geography.
    available_sources = {source["id"] for source in sources}
    provenance_labels = {"owner_or_marketer_claim": "Owner / marketer claim",
                         "named_trial_measurement": "Reported trial measurement",
                         "regulatory_or_registry_record": "Registry description",
                         "independent_report": "Independent report",
                         "trade_press_report": "Trade press report",
                         "unresolved": "Unresolved report"}
    for node in node_rows:
        if node["type"] != "variety":
            continue
        entity = entities[node["id"]]
        rows = variety_trait_profile(entity, entities)
        node["traits"] = []
        for row, original in zip(rows, (entity.get("attributes") or {}).get("traits") or []):
            citations = list(dict.fromkeys(row["evidence_ids"]))
            if not citations or not set(citations) <= available_sources or row["value"] in (None, ""):
                continue
            node["traits"].append({**deepcopy(row), "evidence_ids": citations, "display_value": _trait_value(row["value"]),
                "units": _trait_value(original["units"]) if original.get("units") else "",
                "trait_name": row["trait_name"] if row["trait_name"] and not str(row["trait_name"]).startswith("trait-") else "Reported characteristic",
                "source_kind": provenance_labels.get(row["provenance"], "Source basis not specified")})
        node["unavailable_trait_count"] = len(rows) - len(node["traits"])
        note_refs = set(entity.get("evidence_ids") or [])
        node["trait_note"] = str((entity.get("attributes") or {}).get("note") or "") if node["traits"] and note_refs and note_refs <= available_sources else ""
        node["trait_note_evidence_ids"] = sorted(note_refs) if node["trait_note"] else []
    # Independence is an origin count, never a confidence score or fact approval.
    independence = independence_report([records[row["id"]] for row in sources])
    for edge in edges:
        verbs = {"partners_with": "partners with", "operates_in": "has a location record in", "develops": "develops",
                 "owns": "owns", "licenses": "licenses", "grows": "grows", "markets": "markets",
                 "distributes": "distributes", "trials": "trials", "sells": "sells"}
        edge["label"] = f"{nodes[edge['subject_id']]['label']} {verbs[edge['predicate']]} {nodes[edge['object_id']]['label']}"
        edge["href"] = href(filters, edge=edge["id"])
    visible = edges[:filters["limit"] * 2]
    visible_ids = set()
    visible_edges = []
    for edge in visible:
        keys = {edge["subject_id"], edge["object_id"]}
        if len(visible_ids | keys) <= filters["limit"]:
            visible_ids |= keys
            visible_edges.append(edge)
    visible_nodes = [row for row in node_rows if row["id"] in visible_ids]
    lanes = []
    geo_ids = filters["countries"] or sorted(key for key in used if nodes[key]["type"] == "geography")
    for geography in geo_ids:
        scoped = {geography} | geography_descendants(geography, relationships=relationships)
        lane_edges = [edge for edge in visible_edges if {edge["subject_id"], edge["object_id"]} & scoped]
        actor_ids = {key for edge in lane_edges for key in (edge["subject_id"], edge["object_id"]) if key not in scoped}
        lanes.append({"id": geography, "label": entities[geography].get("name", geography), "edges": lane_edges,
                      "all_edges": [edge for edge in edges if {edge["subject_id"], edge["object_id"]} & scoped],
                      "actors": [row for row in visible_nodes if row["id"] in actor_ids],
                      "all_actors": [row for row in node_rows if row["id"] not in scoped and any(row["id"] in {edge["subject_id"], edge["object_id"]} and {edge["subject_id"], edge["object_id"]} & scoped for edge in edges)],
                      "iso": (entities[geography].get("attributes") or {}).get("iso_3166_1_alpha_2", "")})
    focus_ids = {filters["focus"]} if filters["focus"] in used else set()
    neighborhood = focus_ids | {key for edge in edges if {edge["subject_id"], edge["object_id"]} & focus_ids for key in (edge["subject_id"], edge["object_id"])}
    changes = [edge for edge in edges if edge["in_window"]]
    warnings = ["Company locations do not establish where their varieties grow.",
                "Source review does not verify every claim. Historical and disputed links remain separately labeled.",
                "First seen uses the earliest captured supporting source, not an audit log of relationship creation.",
                "Date controls highlight documented changes; they do not erase the standing landscape.",
                "Missing coverage is not withdrawal or evidence of no activity."]
    if not any(edge["genetic_geography"] for edge in edges):
        warnings.insert(0, "No direct variety or breeding-program location relationships are recorded in this selected scope.")
    if provisional := sum(bool(row["identity_note"]) for row in node_rows):
        warnings.append(f"{provisional} identities in this scope are provisional and still need identity review. Recorded links do not approve their names.")
    if any(edge["caveat"].startswith(("Limited support", "Legacy role mapping")) for edge in edges):
        warnings.append("Some legacy records contain inferred or substituted roles. Their caveats and original notes remain visible; a stored edge is not independent confirmation.")
    if any(edge["unavailable_evidence_count"] for edge in edges):
        warnings.append("Some relationship references are unavailable under the selected review policy; only visible sources are cited.")
    bundle = {"contract": ENGINE_VERSION, "version": fingerprint[:16], "generated_at": datetime.now(timezone.utc).isoformat(),
              "filters": filters, "title": "All berries landscape" if filters["berry"] == "all" else f"{entities[filters['berry']].get('name', filters['berry'])} landscape", "nodes": nodes,
              "edges": edges, "visible_nodes": visible_nodes, "visible_edges": visible_edges, "lanes": lanes,
              "genetics": [row for row in visible_nodes if row["type"] in GENETIC_TYPES],
              "sources": sources, "independence": independence, "changes": changes,
              "neighborhood": sorted(neighborhood), "warnings": warnings, "url": href(filters),
              "coverage": {"nodes": len(nodes), "relationships": len(edges), "sources": len(sources),
                           "genetic_location_links": sum(edge["genetic_geography"] for edge in edges),
                           "company_location_links": sum(edge["company_geography"] for edge in edges),
                           "event_dated": sum(bool(edge["effective"]) for edge in edges),
                           "undated_for_window": sum(not edge["time_dates"] for edge in edges),
                           "hidden_nodes": len(nodes) - len(visible_nodes), "hidden_relationships": len(edges) - len(visible_edges),
                           "truncated_display": len(edges) != len(visible_edges), "complete_export": True,
                           "excluded": excluded, "partial": True}}
    bundle["company_scope"] = company_scope
    bundle["explanation"] = explain(bundle)
    add_portrait_context(bundle, entities, records)
    return bundle


def _combined_bundle(entities, relationships, evidence, filters, fingerprint, today, state):
    """Union already-scoped crop bundles, never traverse a cross-crop shortcut.

    Stable registry IDs deduplicate shared actors and edges. Crop membership is
    the set of single-crop projections containing the edge, not an inferred
    variety identity, commercial footprint or source claim.
    """
    crops = ([filters["berry"], filters["compare"]] if filters["pair"] else
             [key for key in BERRY_ORDER if key in entities and entities[key].get("entity_type") == "berry"])
    panels, edges = [], {}
    for crop in crops:
        focus = filters["focus"]
        if focus and entities[focus].get("entity_type") in GENETIC_TYPES and entities[focus].get("berry_ids") and crop not in entities[focus]["berry_ids"]:
            focus = ""
        child = build_bundle(entities, relationships, evidence,
                             {**filters, "countries": ",".join(filters["countries"]),
                              "berry": crop, "view": "portrait", "pair": "", "focus": focus, "edge": "",
                              "limit": max(20, filters["limit"] // 2) if filters["view"] == "compare" else filters["limit"]}, today=today, state=state)
        panels.append(child)
        for edge in child["edges"]:
            if edge["id"] not in edges:
                edges[edge["id"]] = deepcopy(edge)
                edges[edge["id"]]["berry_ids"] = []
            edges[edge["id"]]["berry_ids"].append(crop)
    records = {row["id"]: row for row in evidence if row.get("status") == "published" or
               (filters["evidence"] == "all" and row.get("status") == "in_review")}
    # These diagnostics overlap across crops; do not add them as distinct records.
    excluded = {key: max((p["coverage"]["excluded"][key] for p in panels), default=0)
                for key in ("missing_endpoints", "unavailable_sources")}
    basis = {}
    for panel in panels:
        for edge in panel["company_scope"]["basis"]:
            if edge["id"] not in edges:
                if edge["id"] not in basis:
                    basis[edge["id"]] = {**deepcopy(edge), "berry_ids": []}
                basis[edge["id"]]["berry_ids"].extend(key for key in edge["berry_ids"] if key not in basis[edge["id"]]["berry_ids"])
    company_scope = {"active": panels[0]["company_scope"]["active"] if panels else False,
                     "labels": panels[0]["company_scope"]["labels"] if panels else [],
                     "basis": list(basis.values())}
    bundle = _assemble_bundle(entities, relationships, records, filters,
                              [edges[key] for key in sorted(edges)], fingerprint, excluded, company_scope)
    bundle["coverage"]["excluded_count_basis"] = "Largest per-crop diagnostic; crop diagnostics overlap, so these are not distinct excluded-record totals."
    common = set.intersection(*[{key for key, row in p["nodes"].items()
                                if row["type"] in {"company", "breeding_program"}} for p in panels]) if panels else set()
    bundle["common_actor_ids"] = sorted(common) if filters["pair"] else []
    bundle["crop_scopes"] = [{"id": p["filters"]["berry"], "label": entities[p["filters"]["berry"]]["name"],
                               "coverage": p["coverage"], "node_ids": list(p["nodes"]),
                               "edge_ids": [e["id"] for e in p["edges"]],
                               "visible_ids": [n["id"] for n in p["visible_nodes"]],
                               "url": p["url"]} for p in panels]
    # Keep program -> variety paths inside their single-crop projections.
    bundle["portfolios"] = [{**row, "berry_id": p["filters"]["berry"],
                              "berry_label": entities[p["filters"]["berry"]]["name"]}
                             for p in panels for row in p["portfolios"]]
    if filters["pair"]:
        bundle["title"] = " vs ".join(entities[crop]["name"] for crop in crops) + " landscapes"
    if filters["view"] == "compare":
        # The page displays two bounded panels, not the aggregate's edge prefix.
        visible_ids = {node["id"] for p in panels for node in p["visible_nodes"]}
        visible_edges = {edge["id"] for p in panels for edge in p["visible_edges"]}
        bundle["visible_nodes"] = [n for n in bundle["nodes"].values() if n["id"] in visible_ids]
        bundle["visible_edges"] = [e for e in bundle["edges"] if e["id"] in visible_edges]
        bundle["genetics"] = [n for n in bundle["visible_nodes"] if n["type"] in GENETIC_TYPES]
        bundle["coverage"].update(hidden_nodes=len(bundle["nodes"])-len(visible_ids),
                                  hidden_relationships=len(bundle["edges"])-len(visible_edges),
                                  truncated_display=len(bundle["edges"])!=len(visible_edges))
    bundle["warnings"].append("Crop totals overlap where the same registry actor, relationship or source appears in more than one crop. Counts show recorded coverage, not scale or influence.")
    bundle["explanation"] = explain(bundle)
    return bundle


def add_portrait_context(bundle, entities, records):
    """Compact comparisons and cited questions, never inferred deployment."""
    nodes, edges = bundle["nodes"], bundle["edges"]
    company_rows = []
    portfolios = []
    for node in sorted(nodes.values(), key=lambda row: (row["label"].casefold(), row["id"])):
        if node["type"] != "company":
            continue
        linked = [edge for edge in edges if node["id"] in {edge["subject_id"], edge["object_id"]}]
        programs = {key for edge in linked for key in (edge["subject_id"], edge["object_id"])
                    if nodes[key]["type"] == "breeding_program"}
        portfolio_edges = [edge for edge in edges if {edge["subject_id"], edge["object_id"]} & (programs | {node["id"]})
                           and any(nodes[key]["type"] == "variety" for key in (edge["subject_id"], edge["object_id"]))]
        variety_ids = {key for edge in portfolio_edges for key in (edge["subject_id"], edge["object_id"]) if nodes[key]["type"] == "variety"}
        row = {"actor": node, "programs": [nodes[key] for key in sorted(programs)],
               "varieties": sorted([nodes[key] for key in variety_ids], key=lambda row: row["label"].casefold()),
               "edges": [edge for edge in linked if not edge["company_geography"]],
               "portfolio_edges": portfolio_edges,
               "markets": [{"country": lane["label"], "edges": [edge for edge in lane["all_edges"] if node["id"] in {edge["subject_id"], edge["object_id"]}]} for lane in bundle["lanes"]]}
        if any(market["edges"] for market in row["markets"]):
            company_rows.append(row)
        if programs or variety_ids:
            portfolios.append(row)
    report = discover_corpus_variety_mentions(varieties=[e for e in entities.values() if e.get("entity_type") == "variety"],
        entities=list(entities.values()), published_evidence=[records[source["id"]] for source in bundle["sources"]], facts=[])
    source_mentions = source_catalog_coverage(report)
    for source in bundle["sources"]:
        source["varieties"] = source_mentions.get(source["id"], [])
    scope = set(BERRY_ORDER) if bundle["filters"]["berry"] == "all" else {bundle["filters"]["berry"]}
    if bundle["filters"].get("pair"):
        scope.add(bundle["filters"]["compare"])
    gaps = [row for row in report["mentions"] if not row.get("canonical_variety_id") and row.get("berry_id") in scope]
    insights = []
    def insight(title, text, next_step, selected):
        insights.append({"title": title, "text": text, "next_step": next_step,
                         "relationship_ids": [edge["id"] for edge in selected],
                         "evidence_ids": sorted({sid for edge in selected for sid in edge["evidence_ids"]})})
    shared = sorted([row for row in company_rows if sum(bool(m["edges"]) for m in row["markets"]) > 1],
                    key=lambda row: -sum(bool(m["edges"]) for m in row["markets"]))
    if shared:
        row = shared[0]
        markets = [m for m in row["markets"] if m["edges"]]
        insight("Across these markets", row["actor"]["label"] + ": " + "; ".join(m["country"] + " — " + ", ".join(edge["location_label"].lower() for edge in m["edges"]) for m in markets) + ".",
                "Distinguish the R&D network from commercial production before comparing market reach.", [edge for m in markets for edge in m["edges"]])
    elif company_rows:
        insight("Market picture", f"{len(company_rows)} companies have sourced location records in this selection.",
                "Open a country cell to see what presence actually means.", [edge for row in company_rows for m in row["markets"] for edge in m["edges"]])
    disputed = [edge for edge in edges if edge["status"] == "disputed"]
    if disputed:
        owners = [edge for edge in disputed if edge["predicate"] == "owns"]
        objects = {edge["object_id"] for edge in owners}
        if len(objects) == 1 and len({edge["subject_id"] for edge in owners}) > 1:
            text = " and ".join(nodes[key]["label"] for key in sorted({edge["subject_id"] for edge in owners})) + " give conflicting ownership accounts for " + nodes[next(iter(objects))]["label"] + "."
        else:
            text = "Conflicting records: " + "; ".join(edge["label"] for edge in disputed[:2]) + "."
        insight("Control needs checking", text,
                "Check the accounts before assigning sole control.", disputed[:2])
    if gaps:
        names = ", ".join(row["candidate_name"] for row in gaps[:5])
        insights.append({"title": "Portfolio coverage gap", "text": f"{len(gaps)} source-named varieties need catalog review, including {names}.",
            "next_step": "Review source names before assigning company roles or growing regions.",
            "relationship_ids": [], "evidence_ids": sorted({sid for row in gaps for sid in row["evidence_ids"]})})
    if not insights:
        insight("What this selection shows", f"{len(edges)} sourced connections match the selected scope.",
                "Broaden the scope if it is empty. Missing records do not establish inactivity.", [])
    bundle["market_rows"], bundle["portfolios"], bundle["insights"] = company_rows, portfolios, insights
    bundle["catalog_gaps"] = [{"name": row["candidate_name"], "evidence_ids": row["evidence_ids"]} for row in gaps]


def explain(bundle):
    """Bounded, deterministic findings cite exactly their supporting stored edges."""
    filters, edges, nodes = bundle["filters"], bundle["edges"], bundle["nodes"]
    findings = []
    if filters["question"] == "markets":
        candidates = [edge for edge in edges if edge["company_geography"] or edge["genetic_geography"]]
    elif filters["question"] == "genetics":
        focus = filters["focus"]
        candidates = [edge for edge in edges if focus in {edge["subject_id"], edge["object_id"]}] if focus else [edge for edge in edges if nodes[edge["subject_id"]]["type"] in GENETIC_TYPES or nodes[edge["object_id"]]["type"] in GENETIC_TYPES]
    else:
        candidates = bundle["changes"]
    for edge in candidates:
        text = edge["label"] + ". " + edge["status_label"] + "."
        if edge["caveat"]:
            text += " " + edge["caveat"] + "."
        if filters["question"] == "changes":
            label = {"documented": "Newly documented in supporting source capture", "published": "Supporting source published", "event": "Recorded effective date"}[filters["time"]]
            text += " " + label + ": " + ", ".join(edge["time_dates"]) + "."
        findings.append({"id": "finding-" + edge["id"], "text": text, "relationship_ids": [edge["id"]], "evidence_ids": edge["evidence_ids"]})
    return {"question": QUESTIONS[filters["question"]], "findings": findings,
            "changes": f"{len(bundle['changes'])} relationships have supporting dates in this window; {bundle['coverage']['undated_for_window']} have no date for the chosen clock.",
            "implications": [{"markets": "Separate production from R&D sites, offices, planned entry and rights enforcement before comparing market reach. Review variety growing-region evidence before drawing an adoption map.",
                              "genetics": "Check breeder, owner and licensee roles separately. Resolve disputed control and provisional names before treating the connected records as an available commercial portfolio.",
                              "changes": "Use the chosen clock to distinguish an event from a later publication or discovery. Check undated connections before concluding that a company has stopped expanding."}[filters["question"]]],
            "unknowns": bundle["warnings"], "method": "Deterministic registry explanation · no model or research call"}


def validate_phrasing(proposal, bundle):
    """Optional future phrasing gate: closed propositions, not just valid IDs.

    No model is called in milestone A. Untrusted output cannot expand facts:
    only the existing exact supported propositions and citations are accepted.
    """
    if not isinstance(proposal, dict) or set(proposal) != {"findings"} or not isinstance(proposal["findings"], list):
        return bundle["explanation"]
    expected = {row["id"]: row for row in bundle["explanation"]["findings"]}
    if len(proposal["findings"]) != len(expected):
        return bundle["explanation"]
    seen = set()
    for row in proposal["findings"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row != expected.get(row["id"]) or row["id"] in seen:
            return bundle["explanation"]
        seen.add(row["id"])
    return {**bundle["explanation"], "findings": deepcopy(proposal["findings"])}
