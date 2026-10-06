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

ENGINE_VERSION = "landscape-1"
GENETIC_TYPES = {"variety", "breeding_program"}
ACTOR_TYPES = {"company", "breeding_program", "variety"}
ROLE_LABELS = {"develops": "Breeder / developer", "owns": "Owner / rights holder",
               "licenses": "Licensee", "grows": "Grower", "markets": "Marketer",
               "distributes": "Distributor", "trials": "Trial participant",
               "sells": "Seller", "partners_with": "Partner", "operates_in": "Location relationship"}
QUESTIONS = {"markets": "What connects these selected markets?",
             "genetics": "Where is this program or variety documented?",
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


def selection(params, entities, *, today=None):
    today = today or date.today()
    countries = _values(params, "countries") if "countries" in params else ["geography-chile", "geography-china", "geography-peru"]
    # Generic service accepts any known berry; the milestone route gates rollout.
    berry = str(params.get("berry") or "berry-blueberry")
    if berry not in entities or entities[berry].get("entity_type") != "berry":
        raise ValueError("Choose a registered berry.")
    if any(key not in entities or entities[key].get("entity_type") != "geography" for key in countries):
        raise ValueError("Choose registered countries or regions.")
    focus = str(params.get("focus") or "")
    if focus and (focus not in entities or entities[focus].get("entity_type") not in ACTOR_TYPES):
        raise ValueError("The selected company, program or variety is unavailable.")
    enums = {"predicate": ("", *ROLE_LABELS), "evidence": ("reviewed", "all"),
             "status": ("all", "active", "historical", "disputed"),
             "view": ("portrait", "changes", "explain", "relationships"),
             "window": ("all", "7d", "30d", "ytd", "custom"),
             "time": ("documented", "published", "event"),
             "question": tuple(QUESTIONS), "theme": ("light", "dark")}
    defaults = {key: values[0] for key, values in enums.items()}
    result = {key: str(params.get(key, defaults[key])) for key in enums}
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
    return {**result, "berry": berry, "countries": countries, "focus": focus,
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


def build_bundle(entities, relationships, evidence, params, *, today=None):
    """Complete selected scope; visibility limits apply only to the web portrait.

    Fingerprinting includes deletions and source edits, not a TTL. Cached values
    are copied so a caller cannot poison later UI/export responses.
    """
    today = today or date.today()
    filters = selection(params, entities, today=today)
    fingerprint = hashlib.sha256(json.dumps([ENGINE_VERSION, entities, sorted(relationships, key=lambda r: r["id"]),
                                            sorted(evidence, key=lambda r: r["id"])], sort_keys=True, default=str).encode()).hexdigest()
    cache_key = fingerprint + json.dumps(filters, sort_keys=True) + today.isoformat()
    with _CACHE_LOCK:
        if cache_key in _CACHE:
            _CACHE.move_to_end(cache_key)
            return deepcopy(_CACHE[cache_key])
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
        if any(berry not in tagset for tagset in explicit_tags) or berry not in tags | source_tags:
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
                           "predicate": row["predicate"], "role": ROLE_LABELS[row["predicate"]],
                           "status": row["status"], "status_label": {"active": "Documented relationship", "historical": "Historical relationship", "disputed": "Disputed / review required"}[row["status"]],
                           "review": "Includes unreviewed source" if any(r.get("status") != "published" for r in source_rows) else "Reviewed sources",
                           "evidence_ids": source_ids, "unavailable_evidence_count": len(row.get("evidence_ids", [])) - len(source_ids),
                           "notes": row.get("notes") or "No relationship notes recorded.", "caveat": _caveat(row),
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
    used = {key for edge in edges for key in (edge["subject_id"], edge["object_id"])}
    node_rows = [{"id": key, "label": entities[key].get("name") or key, "type": entities[key]["entity_type"],
                  "aliases": entities[key].get("aliases") or [], "berry_ids": entities[key].get("berry_ids") or [],
                  "identity_status": entities[key].get("status") or "Not recorded",
                  "identity_note": "Provisional identity · review needed" if entities[key].get("status") == "unverified" else "",
                  "evidence_ids": sorted({sid for edge in edges if key in {edge["subject_id"], edge["object_id"]} for sid in edge["evidence_ids"]})}
                 for key in sorted(used, key=lambda key: (entities[key].get("name", key).casefold(), key))]
    nodes = {row["id"]: row for row in node_rows}
    sources = [_source(records[key]) for key in sorted({sid for edge in edges for sid in edge["evidence_ids"]})]
    for number, source in enumerate(sources, 1):
        source["number"] = number
    # Independence is an origin count, never a confidence score or fact approval.
    independence = independence_report([records[row["id"]] for row in sources])
    for edge in edges:
        edge["label"] = f"{nodes[edge['subject_id']]['label']} → {edge['predicate'].replace('_', ' ')} → {nodes[edge['object_id']]['label']}"
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
              "filters": filters, "title": f"{entities[berry].get('name', berry)} landscape", "nodes": nodes,
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
    bundle["explanation"] = explain(bundle)
    with _CACHE_LOCK:
        _CACHE[cache_key] = deepcopy(bundle)
        while len(_CACHE) > 12:
            _CACHE.popitem(last=False)
    return bundle


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
            "implications": ["Analyst interpretation: use these sourced connections to choose the next dossier or evidence record to review. Connection counts describe coverage, not commercial scale."],
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
