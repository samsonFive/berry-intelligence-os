"""Versioned, read-only investigation adapters over the governed presenters.

The URL is selectors, not factual authority. Focus never seeds the landscape;
news publication dates never erase standing relationships. Only selected source
detail hydrates prose. This module performs no acquisition or provider calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlencode

from app.services import landscape_explorer as explorer
from app.services.berries.landscape import SEED_FIXTURE_ENTITY_IDS, SEED_FIXTURE_EVIDENCE_IDS

CONTEXT_FIELDS = (
    "ctx_v", "berry", "countries", "geo_basis", "actor_roles", "relationship_types",
    "news_from", "news_to", "focus", "cohort_companies", "cohort_varieties", "lens",
    "comparison_kind", "detail_path", "demo_specimens", "q", "q_scope", "saved_view_id", "saved_revision",
)
DEFAULT_CONTEXT = {key: "" for key in CONTEXT_FIELDS}
DEFAULT_CONTEXT.update(ctx_v="1", berry="all", geo_basis="company_connections",
                       lens="connections", comparison_kind="company", q_scope="scope")
BERRIES = ("blueberry", "strawberry", "raspberry", "blackberry")
DETAIL_TYPES = {"company", "variety", "geography", "relationship", "source", "observation"}
ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,180}$")


def issue(code, field, message, key=None):
    result = {"code": code, "field": field, "message": message}
    if key is not None:
        result["id"] = key
    return result


def ids(value):
    return list(dict.fromkeys(part.strip() for part in str(value or "").split(",") if part.strip()))


def reference(value, *, kinds=DETAIL_TYPES):
    kind, separator, subject = str(value).partition(":")
    key, section_separator, section = subject.partition("@")
    if not separator or kind not in kinds or not ID_RE.fullmatch(key):
        raise ValueError("Choose a supported typed reference with a canonical identifier.")
    if section_separator and (kind != "source" or section not in {"article", "brief"}):
        raise ValueError("Choose a supported source reading section.")
    return kind, key


def normalize_context(params):
    """Return allowlisted string selectors and non-destructive selection issues.

    No repository scan is needed by save/URL callers. Unknown canonical IDs are
    resolved by the read adapters. Valid overflow IDs stay in saved selectors so
    the user can explicitly resolve them rather than silently lose selections.
    """
    context = dict(DEFAULT_CONTEXT)
    issues = []
    for key in CONTEXT_FIELDS:
        if key not in params:
            continue
        values = params.getlist(key) if hasattr(params, "getlist") else [params.get(key)]
        value = ",".join(str(v or "") for v in values) if key in {
            "countries", "actor_roles", "relationship_types", "cohort_companies", "cohort_varieties", "demo_specimens"
        } else str(values[-1] or "")
        if len(value) > (200 if key == "q" else 4096):
            raise ValueError(f"{key} exceeds the supported input length.")
        context[key] = value.strip()
    if context["berry"] in BERRIES:
        context["berry"] = "berry-" + context["berry"]
    enums = {
        "ctx_v": {"1"}, "berry": {"all", *("berry-" + berry for berry in BERRIES)},
        "geo_basis": {"company_connections", "source_geography", "variety_growing", "rights"},
        "lens": {"connections", "portfolio", "geography", "comparison", "sensory"},
        "comparison_kind": {"company", "variety"}, "q_scope": {"scope", "catalog"},
    }
    for key, allowed in enums.items():
        if context[key] not in allowed:
            raise ValueError(f"Choose a supported {key}.")
    for key in ("countries", "actor_roles", "relationship_types", "cohort_companies", "cohort_varieties", "demo_specimens"):
        entries = ids(context[key])
        if len(entries) > 40 or any(not ID_RE.fullmatch(v) for v in entries):
            raise ValueError(f"{key} contains an invalid or excessive selection.")
        context[key] = ",".join(entries)
    if any(not key.startswith("demo-specimen-") for key in ids(context["demo_specimens"])):
        raise ValueError("Synthetic comparison accepts only the separate demo specimen namespace.")
    unknown_predicates = set(ids(context["relationship_types"])) - set(explorer.ROLE_LABELS)
    if unknown_predicates:
        raise ValueError("Choose supported relationship predicates.")
    for key, maximum in (("cohort_companies", 5), ("cohort_varieties", 4)):
        for extra in ids(context[key])[maximum:]:
            issues.append(issue("overflow", key, f"Only the first {maximum} selections are compared; remove or reorder this selection.", extra))
    for key in ("news_from", "news_to"):
        if context[key]:
            try:
                if date.fromisoformat(context[key]).isoformat() != context[key]:
                    raise ValueError()
            except ValueError:
                raise ValueError(f"{key} must be an ISO publication date.") from None
    if context["news_from"] and context["news_to"] and context["news_from"] > context["news_to"]:
        raise ValueError("The publication start must not follow the end date.")
    if context["focus"]:
        if ":" in context["focus"]:
            _kind, context["focus"] = reference(context["focus"], kinds={"company", "variety"})
        if not ID_RE.fullmatch(context["focus"]):
            raise ValueError("Choose a canonical focus identifier.")
    if context["detail_path"]:
        path = context["detail_path"].split("~")
        if len(path) > 8:
            raise ValueError("The detail path supports at most eight ancestors.")
        canonical_path = []
        for value in path:
            kind, key = reference(value)
            canonical_path.append(f"{kind}:{key}" + ("@brief" if value.endswith("@brief") else ""))
        context["detail_path"] = "~".join(canonical_path)
    if context["saved_view_id"] and not ID_RE.fullmatch(context["saved_view_id"]):
        raise ValueError("The saved investigation identifier is invalid.")
    if context["saved_revision"] and (not context["saved_revision"].isdigit() or len(context["saved_revision"]) > 10):
        raise ValueError("The saved revision must be a non-negative integer.")
    return context, issues


def context_query(context):
    return urlencode({key: str(context.get(key, DEFAULT_CONTEXT[key])) for key in CONTEXT_FIELDS})


def scope_key(context):
    return sha256(json.dumps({key: context[key] for key in CONTEXT_FIELDS}, sort_keys=True).encode()).hexdigest()[:24]


@dataclass
class World:
    main: Any
    entities: dict
    relationships: list
    evidence: list
    state: dict = field(default_factory=dict)
    _news: dict | None = None
    _facts: list | None = None
    _signals: list | None = None
    _assessments: list | None = None
    _published: list | None = None
    _evidence_index: dict | None = None
    _attribution_index: Any = None
    _source_index: dict | None = None

    @property
    def published(self):
        if self._published is None:
            self._published = [row for row in self.evidence if row.get("status") == "published"]
        return self._published

    @property
    def evidence_index(self):
        if self._evidence_index is None:
            self._evidence_index = {row["id"]: row for row in self.published}
        return self._evidence_index

    @property
    def facts(self):
        if self._facts is None:
            self._facts = self.main.all_facts()
        return self._facts

    @property
    def signals(self):
        if self._signals is None:
            self._signals = self.main.all_signals()
        return self._signals

    @property
    def assessments(self):
        if self._assessments is None:
            self._assessments = self.main.all_assessments()
        return self._assessments

    @property
    def berry_labels(self):
        return {key: row.get("name", key) for key, row in self.entities.items() if row.get("entity_type") == "berry"}


    @property
    def attribution_index(self):
        if self._attribution_index is None:
            from app.services.draft_attribution import build_attribution_match_index
            self._attribution_index = build_attribution_match_index(self.entities)
        return self._attribution_index

    @property
    def source_index(self):
        if self._source_index is None:
            loader = getattr(self.main, "load_sources", lambda: [])
            self._source_index = {row["id"]: row for row in loader() if row.get("id")}
        return self._source_index

    @property
    def news(self):
        if self._news is None:
            from app.services.personal_digest import source_records
            from app.services.publication_sources import pending_source_previews
            pending, problems = pending_source_previews(self.main.INBOX_DIR)
            records = source_records(self.published, self.main.INBOX_DIR, include_private=True,
                                     pending=pending, metadata_only=True, index_issues=problems)
            self._news = {key: value for key, value in records.items() if key not in SEED_FIXTURE_EVIDENCE_IDS}
        return self._news


def load_world():
    from app import main
    from app.landscape_explorer_routes import company_state
    entities = {row["id"]: row for row in main.all_entities() if row["id"] not in SEED_FIXTURE_ENTITY_IDS}
    evidence = [row for row in main._social_eligible_outputs(main.all_evidence()) if row["id"] not in SEED_FIXTURE_EVIDENCE_IDS]
    relationships = main._social_eligible_outputs(main.all_relationships())
    return World(main, entities, relationships, evidence, company_state(main.INBOX_DIR))


def load_catalog_world():
    """Selector metadata only: no Evidence/relationship/inbox loading."""
    from app import main
    entities = {row["id"]: row for row in main.all_entities() if row["id"] not in SEED_FIXTURE_ENTITY_IDS}
    return World(main, entities, [], [], {})


def validate_scope(world, context):
    for key in ids(context["countries"]):
        if world.entities.get(key, {}).get("entity_type") != "geography":
            raise ValueError("Choose registered geography identifiers; the scope was not broadened.")
    authored_roles = {role for row in world.entities.values() for role in row.get("roles") or []}
    if set(ids(context["actor_roles"])) - authored_roles:
        raise ValueError("Choose authored actor roles from the available catalog.")
    berry = context["berry"]
    if context["berry"] != "all" and world.entities.get(berry, {}).get("entity_type") != "berry":
        raise ValueError("The selected berry is not registered.")


def selection_issues(world, context, bundle):
    problems = []
    selections = [("cohort_companies", "company", key) for key in ids(context["cohort_companies"])]
    selections += [("cohort_varieties", "variety", key) for key in ids(context["cohort_varieties"])]
    if context["focus"]:
        key = context["focus"]
        kind = world.entities.get(key, {}).get("entity_type") or key.partition("-")[0]
        selections.append(("focus", kind, key))
    for field_name, kind, key in selections:
        if kind not in {"company", "variety"} or world.entities.get(key, {}).get("entity_type") != kind:
            problems.append(issue("invalid_id", field_name, "This selected identity is unavailable; remove or replace it.", key))
        elif key not in bundle["nodes"]:
            problems.append(issue("outside_scope", field_name, "This selection is outside the applied landscape; inspection does not expand scope.", key))
    return problems


def base_bundle(world, context):
    validate_scope(world, context)
    # Crucial: existing Explorer uses focus as an additional graph root. New
    # investigation focus is deliberately NOT passed to that legacy behavior.
    bundle = explorer.build_bundle(world.entities, world.relationships, world.evidence, {
        "berry": context["berry"],
        "countries": context["countries"], "focus": "", "window": "all", "time": "published",
        "view": "portrait", "evidence": "reviewed", "limit": "5000",
    }, state=world.state)
    roles = set(ids(context["actor_roles"]))
    if roles:
        companies = {key for key, row in bundle["nodes"].items() if row["type"] == "company"}
        selected = {key for key in companies if roles.intersection(world.entities[key].get("roles") or [])}
        eligible = [edge for edge in bundle["edges"]
                    if not (companies - selected).intersection({edge["subject_id"], edge["object_id"]})]
        # Traverse explicit actor/genetic edges only. Geography is an endpoint,
        # never a bridge that brings unrelated companies back into this scope.
        reached = set(selected)
        changed = True
        while changed:
            changed = False
            for edge in eligible:
                endpoints = {edge["subject_id"], edge["object_id"]}
                if any(bundle["nodes"][key]["type"] == "geography" for key in endpoints):
                    continue
                if endpoints.intersection(reached) and not endpoints <= reached:
                    reached.update(endpoints)
                    changed = True
        edges = [edge for edge in eligible if {edge["subject_id"], edge["object_id"]}.intersection(reached)]
        bundle = explorer._assemble_bundle(world.entities, world.relationships, world.evidence_index,
            bundle["filters"], edges, bundle["version"], bundle["coverage"]["excluded"], bundle.get("company_scope"))
    return bundle


def source_metadata(row):
    """No article/transcript/excerpts or private raw attributes on list routes."""
    if "review" not in row:
        from app.services.company_source_scope import source_reviewed
        reviewed = source_reviewed(row)
        row = {**explorer._source(row), "review": "Reviewed source · claims retain their own review" if reviewed else "Unreviewed source"}
    allowed = ("id", "title", "url", "source_name", "status", "review", "published", "captured", "number")
    result = {key: row[key] for key in allowed if key in row}
    result["varieties"] = [{key: value for key, value in item.items() if key in
                            {"id", "name", "catalog_id", "href", "status", "berry_id"}}
                           for item in row.get("varieties", [])]
    return result


def module_scope(context, module):
    if module == "options":
        return {"basis": "catalog metadata", "scope_selectors": "not applied", "q": context["q"]}
    applied = {"berry": context["berry"], "countries": ids(context["countries"])}
    if module == "developments":
        applied.update(geo_basis="source_geography", news_from=context["news_from"], news_to=context["news_to"],
                       date_basis="source publication date", actor_roles=ids(context["actor_roles"]), relationship_types="not applied")
    elif module == "comparison":
        applied.update(countries="Context only; comparison contains full selected profiles",
                       berry="Context only; comparison contains full selected profiles",
                       news_from="not applied", news_to="not applied",
                       basis="Existing profile presenters; geography and publication filters do not trim portfolios")
    else:
        applied.update(geo_basis="company_connections", actor_roles=ids(context["actor_roles"]),
                       relationship_types=ids(context["relationship_types"]),
                       news_from="not applied", news_to="not applied", date_basis="standing recorded relationships")
        if context["geo_basis"] != "company_connections":
            applied.update(requested_geo_basis=context["geo_basis"], omitted_scope_keys=["geo_basis"])
    return applied


def catalog_options(world, context, bundle=None):
    query = context["q"].strip().casefold()
    def match(row):
        if not query:
            return {"match_basis": "unfiltered"}
        name = str(row.get("name") or "")
        aliases = [value for value in row.get("aliases") or [] if isinstance(value, str)]
        if query == name.strip().casefold():
            return {"match_basis": "exact_name", "matched_label": name}
        exact = next((value for value in aliases if query == value.strip().casefold()), None)
        if exact is not None:
            return {"match_basis": "exact_alias", "matched_label": exact}
        partial = next((value for value in [name, *aliases] if query in value.casefold()), None)
        return {"match_basis": "substring", "matched_label": partial} if partial is not None else {"match_basis": "unfiltered"}
    matches_by_id = {key: match(row) for key, row in world.entities.items()}
    def option(row):
        return {"id": row["id"], "label": row.get("name", row["id"]),
                "name": row.get("name", row["id"]),
                "type": row.get("entity_type"), "status": row.get("status", "unknown"),
                "in_scope": row["id"] in bundle["nodes"] if bundle is not None else None,
                **matches_by_id[row["id"]]}
    sorted_entities = sorted(world.entities.values(), key=lambda row: (row.get("name", "").casefold(), row["id"]))
    selectable = [row for row in sorted_entities if row.get("entity_type") in {"company", "variety"}
                  and (not query or matches_by_id[row["id"]]["match_basis"] != "unfiltered")
                  and (bundle is None or context["q_scope"] == "catalog" or row["id"] in bundle["nodes"])]
    if query:
        # Authored exact matches must survive the finite metadata cap. This is
        # name resolution, never a commercial relevance or confidence ranking.
        selectable.sort(key=lambda row: matches_by_id[row["id"]]["match_basis"] not in {"exact_name", "exact_alias"})
    return {
        "berries": [{"id": "all", "label": "All berries", "name": "All berries"}] + [
            {"id": "berry-" + key, "label": world.berry_labels.get("berry-" + key, key.title()),
             "name": world.berry_labels.get("berry-" + key, key.title())} for key in BERRIES
            if "berry-" + key in world.entities],
        "countries": [option(row) for row in sorted_entities if row.get("entity_type") == "geography"],
        "companies": [option(row) for row in selectable if row["entity_type"] == "company"][:150],
        "varieties": [option(row) for row in selectable if row["entity_type"] == "variety"][:150],
        "actor_roles": sorted({role for row in world.entities.values() for role in row.get("roles") or []}),
        "relationship_types": [{"id": key, "label": value} for key, value in explorer.ROLE_LABELS.items()],
        "search_basis": context["q_scope"] if bundle is not None else "catalog",
        "scope_evaluated": bundle is not None, "matching_count": len(selectable), "limit_per_type": 150,
    }


def _display_label(node, title=""):
    label = node.get("label") or node.get("name") or node["id"]
    aliases = [alias.strip() for alias in node.get("aliases") or []
               if isinstance(alias, str) and alias.strip() and len(alias.strip()) < len(label)]
    if (node.get("type") or node.get("entity_type")) == "company" and aliases:
        if title:
            from app.services.draft_attribution import _boundary_search
            matched = [alias for alias in aliases if _boundary_search(title.casefold(), alias.casefold())]
            if matched:
                return matched[0]
        return aliases[0]
    return label


def _scope_findings(nodes, edges):
    """Lead with existing activity/role labels, without adding a proposition.

    Inputs contain only the applied graph. Focus, cohort, lens, detail and news
    dates cannot choose or rewrite these standing-context findings.
    """
    def name(key):
        node = nodes[key]
        # An authored alias can shorten a legal identity; never manufacture a
        # familiar company name by stripping words or matching free text.
        display = _display_label(node)
        return display + (" (" + node["identity_note"] + ")" if node.get("identity_note") else "")

    def finding(key, text, selected):
        return {"id": key, "text": text,
                "relationship_ids": [edge["id"] for edge in selected],
                "evidence_ids": sorted({sid for edge in selected for sid in edge["evidence_ids"]})}

    def qualifiers(edge):
        parts = [edge["caveat"]] if edge.get("caveat") else []
        if edge.get("status") != "active":
            parts.append(edge["status_label"])
        return " (" + "; ".join(parts) + ")" if parts else ""

    activities = {}
    for edge in edges:
        subject, target = nodes[edge["subject_id"]], nodes[edge["object_id"]]
        label = edge.get("location_label")
        if (subject["type"] == "company" and target["type"] == "geography"
                and label and label != "Location reported · check source"):
            activities.setdefault(subject["id"], []).append(edge)
    ordered_actors = sorted(activities, key=lambda key: (name(key).casefold(), key))
    phase_labels = {"Variety validation programme", "Planned market entry"}
    licensing_labels = {"Growing & licensing region"}
    operating_labels = {"Company-reported production", "Local operations"}
    labels_by_actor = {key: {edge["location_label"] for edge in values} for key, values in activities.items()}
    phase_actors = sorted((key for key in ordered_actors if labels_by_actor[key] & phase_labels),
                          key=lambda key: (not phase_labels <= labels_by_actor[key], name(key).casefold(), key))
    actor_choices = []
    preferred = {}
    # Show distinct captured activity types before administrative presence. This
    # selects an editorial contrast, never a country-count or strength ranking.
    for candidates, labels in ((phase_actors, phase_labels),
                               ([key for key in ordered_actors if labels_by_actor[key] & licensing_labels], licensing_labels),
                               ([key for key in ordered_actors if labels_by_actor[key] & operating_labels], operating_labels),
                               (ordered_actors, set())):
        candidate = next((key for key in candidates if key not in actor_choices), None)
        if candidate is not None:
            actor_choices.append(candidate)
            preferred[candidate] = labels
        if len(actor_choices) == 2:
            break
    findings = []
    activity_actors = set(actor_choices)
    for actor in actor_choices:
        ordered = sorted(activities[actor], key=lambda edge: (
            edge.get("status") != "active", edge["location_label"] not in preferred[actor],
            name(edge["object_id"]).casefold(), edge["location_label"], edge["id"]))
        selected, places = [], set()
        for edge in ordered:
            if edge["object_id"] not in places:
                selected.append(edge)
                places.add(edge["object_id"])
        selected_ids = {edge["id"] for edge in selected}
        selected = (selected + [edge for edge in ordered if edge["id"] not in selected_ids])[:2]
        text = name(actor) + " — " + "; ".join(
            name(edge["object_id"]) + ": " + edge["location_label"] + qualifiers(edge) for edge in selected) + "."
        findings.append(finding("finding-activity-" + actor, text, selected))

    role_predicates = {"develops", "owns", "licenses", "grows", "markets", "distributes", "trials", "sells"}
    genetics = [edge for edge in edges if edge["predicate"] in role_predicates
                and nodes[edge["subject_id"]]["type"] in {"company", "breeding_program"}
                and nodes[edge["object_id"]]["type"] in explorer.GENETIC_TYPES]
    genetics.sort(key=lambda edge: (
        edge.get("status") != "active", bool(edge.get("caveat")),
        edge["subject_id"] not in activity_actors if activity_actors else False,
        nodes[edge["object_id"]]["type"] != "breeding_program",
        nodes[edge["subject_id"]]["type"] != "company",
        name(edge["subject_id"]).casefold(), name(edge["object_id"]).casefold(), edge["id"]))
    # Prefer distinct actors when there is room, then retain further exact roles
    # if a genuinely sparse selection contains only one actor.
    represented = set()
    chosen = []
    for edge in genetics:
        if edge["subject_id"] not in represented:
            chosen.append(edge)
            represented.add(edge["subject_id"])
    chosen_ids = {edge["id"] for edge in chosen}
    chosen += [edge for edge in genetics if edge["id"] not in chosen_ids]
    for edge in chosen[:3 - len(findings)]:
        text = (name(edge["subject_id"]) + " → " + name(edge["object_id"])
                + ": " + edge["role"] + qualifiers(edge) + ".")
        findings.append(finding("finding-" + edge["id"], text, [edge]))
    return findings


def landscape_data(world, context, bundle=None):
    bundle = bundle if bundle is not None else base_bundle(world, context)
    roles, predicates = set(ids(context["actor_roles"])), set(ids(context["relationship_types"]))
    excluded_companies = {key for key, node in bundle["nodes"].items() if node["type"] == "company"
                          and roles and not roles.intersection(world.entities[key].get("roles") or [])}
    edges = [row for row in bundle["edges"] if not excluded_companies.intersection({row["subject_id"], row["object_id"]})
             and (not predicates or row["predicate"] in predicates)]
    used = {key for edge in edges for key in (edge["subject_id"], edge["object_id"])}
    nodes = {key: row for key, row in bundle["nodes"].items() if key in used}
    edge_ids = {row["id"] for row in edges}
    source_ids = {key for row in edges for key in row["evidence_ids"]}
    findings = _scope_findings(nodes, edges)
    def portrait(row):
        related = [edge for edge in row["edges"] if edge["id"] in edge_ids]
        portfolio = [edge for edge in row["portfolio_edges"] if edge["id"] in edge_ids]
        all_related_ids = {key for edge in related + portfolio for key in (edge["subject_id"], edge["object_id"])}
        return {"actor": row["actor"], "programs": [n for n in row["programs"] if n["id"] in all_related_ids],
                "varieties": [n for n in row["varieties"] if n["id"] in all_related_ids],
                "edges": related, "portfolio_edges": portfolio,
                "markets": [{"country": market["country"], "edges": [e for e in market["edges"] if e["id"] in edge_ids]}
                            for market in row["markets"]]}
    market_rows = [portrait(row) for row in bundle["market_rows"] if row["actor"]["id"] in nodes]
    portfolios = [portrait(row) for row in bundle["portfolios"] if row["actor"]["id"] in nodes]
    return {"selection": context, "nodes": nodes, "edges": edges,
            "sources": [source_metadata(row) for row in bundle["sources"] if row["id"] in source_ids],
            "market_rows": market_rows, "portfolios": portfolios, "findings": findings,
            "scope_notes": list(bundle["warnings"]) + [
                "Connection scope uses recorded company/genetic relationships; source geography, growing and rights are distinct bases.",
                "Search queries affect the labeled selector results, not the standing scope readout."],
            "options": catalog_options(world, context, bundle), "version": bundle["version"],
            "developments": developments_data(world, context, bundle)}


def comparison_data(world, context):
    from app.services.company_workspace import present_company_compare
    from app.services.variety_workspace import present_variety_compare
    kind = context["comparison_kind"]
    selected = ids(context["cohort_companies" if kind == "company" else "cohort_varieties"])
    kwargs = dict(entities=world.entities, relationships=world.relationships,
                  published_evidence=world.published, facts=world.facts,
                  evidence_by_id=world.evidence_index, signals=world.signals,
                  assessments=world.assessments, berry_labels=world.berry_labels)
    presenter = present_company_compare if kind == "company" else present_variety_compare
    result = presenter(selected, **kwargs)
    return {**result, "comparison_kind": kind, "scope_applicability": module_scope(context, "comparison")}


def developments_data(world, context, bundle, *, all_cards=False):
    from app.services import news_workspace, company_source_scope
    kind = context["comparison_kind"]
    raw_cohort = ids(context["cohort_companies" if kind == "company" else "cohort_varieties"])
    cohort = [key for key in raw_cohort[:5 if kind == "company" else 4]
              if world.entities.get(key, {}).get("entity_type") == kind]
    subject_ids, basis = [], "scope"
    if context["lens"] == "comparison" and cohort:
        subject_ids, basis = cohort, "comparison"
    elif context["focus"]:
        focal_id = context["focus"]
        focus_kind = world.entities.get(focal_id, {}).get("entity_type")
        if focal_id in bundle["nodes"] and world.entities.get(focal_id, {}).get("entity_type") == focus_kind:
            subject_ids, basis = [focal_id], "focus"
    labels = [world.entities[key].get("name", key) for key in subject_ids]
    params = {"berry": "" if context["berry"] == "all" else context["berry"],
              "countries": context["countries"], "view": "unreviewed", "tz": "UTC",
              "window": "custom" if context["news_from"] or context["news_to"] else "",
              "start": context["news_from"], "end": context["news_to"]}
    # Subject narrowing precedes pagination, but never removes the module's berry,
    # country or publication constraints. News model still verifies all semantics.
    records = world.news
    subject_mentions, subject_links = {}, {}
    actor_roles = set(ids(context["actor_roles"]))
    if actor_roles:
        actors = [row for row in world.entities.values() if row.get("entity_type") == "company"
                  and actor_roles.intersection(row.get("roles") or [])]
        actor_ids = {row["id"] for row in actors}
        eligible_records = {}
        for key, record in records.items():
            linked, mentions = company_source_scope.links(record, actors)
            if actor_ids.intersection(linked):
                eligible_records[key] = record
                subject_mentions[key] = mentions
        records = eligible_records
    if subject_ids:
        subjects = [world.entities[key] for key in subject_ids if world.entities[key].get("entity_type") == "company"]
        selected = set(subject_ids)
        def matches(record):
            linked, mentions = company_source_scope.links(record, subjects)
            subject_mentions[record["id"]] = [*subject_mentions.get(record["id"], []), *mentions]
            subject_links[record["id"]] = linked & selected
            return bool(selected.intersection(linked))
        records = {key: row for key, row in records.items() if matches(row)}
    model = news_workspace.model(records=records, entities=world.entities, relationships=world.relationships,
                                 facts=world.facts, state=world.state, params=params)
    if all_cards:
        for page in range(2, model.get("pages", 1) + 1):
            following = news_workspace.model(records=records, entities=world.entities, relationships=world.relationships,
                facts=world.facts, state=world.state, params={**params, "page": str(page)})
            model["cards"].extend(following["cards"])
    cards = model["cards"] if all_cards else model["cards"][:6]
    for card in cards:
        # The feed needs personal action state and source review labels, not
        # selected-source passages or the full private statement workspace.
        card.pop("passages", None)
        card.pop("statements", None)
        mentions = {item["id"]: item for item in [*card.get("company_mentions", []), *subject_mentions.get(card["id"], [])]}
        card["company_mentions"] = list(mentions.values())
        if subject_ids and card["id"] in records:
            from app.services.draft_attribution import attribute_draft
            record = records[card["id"]]
            attribution = attribute_draft(record, world.entities, sources=world.source_index,
                match_index=world.attribution_index, include_body=False)
            primary = attribution.get("primary") or {}
            primary_id = str(primary.get("id") or "")
            matched = [key for key in subject_ids if key in subject_links.get(card["id"], set())]
            stored = set(record.get("entity_ids") or []) | set(record.get("company_ids") or [])
            title = str(record.get("original_title") or record.get("title") or "")
            subject_matches = [{"id": key, "label": _display_label(world.entities[key], title),
                                "basis": "recorded_link" if key in stored else "unreviewed_mention"} for key in matched]
            card["scope_match"] = {
                "kind": "primary" if primary_id in matched else "related_context",
                "primary_id": primary_id,
                "primary_label": _display_label(world.entities[primary_id], title) if primary_id in world.entities else "",
                "subject_ids": matched, "subject_labels": [row["label"] for row in subject_matches],
                # A recorded link can establish eligibility independently of an
                # additional alias recall. Each subject retains its own basis.
                "basis": "recorded_link" if any(row["basis"] == "recorded_link" for row in subject_matches) else "unreviewed_mention",
                "subject_matches": subject_matches,
            }
    heading = "Developments across this scope" if basis == "scope" else (
        "Developments for " + ("comparison: " if basis == "comparison" else "") + " · ".join(labels))
    legacy_params = {key: value for key, value in params.items() if value}
    if len(subject_ids) == 1 and world.entities[subject_ids[0]].get("entity_type") == "company":
        legacy_params["company"] = subject_ids[0]
    return {"cards": cards, "basis": basis, "subject_ids": subject_ids,
            "heading": heading, "briefing_href": "/news?" + urlencode(legacy_params),
            "sources": [source_metadata(records[card["id"]]) for card in cards if card["id"] in records],
            "matching_count": model["matching"], "scope_applicability": module_scope(context, "developments"),
            "briefing_scope_note": "Full scoped News; the company cohort remains in this investigation." if len(subject_ids) > 1 else ""}


def _entity_sources(world, entity, bundle):
    linked = set(entity.get("evidence_ids") or [])
    linked.update(row["id"] for row in world.published if entity["id"] in (row.get("entity_ids") or []))
    for edge in bundle["edges"]:
        if entity["id"] in {edge["subject_id"], edge["object_id"]}:
            linked.update(edge["evidence_ids"])
    return [source_metadata(world.evidence_index[key]) for key in sorted(linked) if key in world.evidence_index][:40]


def _edge_item(edge):
    return {**edge, "type": "relationship", "value": edge["role"],
            "summary": edge["notes"], "label": edge["label"]}


def _cited_sources(world, source_ids):
    return [source_metadata(world.evidence_index[key]) for key in dict.fromkeys(source_ids) if key in world.evidence_index]


def detail_data(world, context, bundle, kind, key, request=None):
    if kind not in DETAIL_TYPES or not ID_RE.fullmatch(key):
        raise ValueError("Choose a supported detail type and canonical identifier.")
    if kind == "source":
        from app.personal_digest_routes import personal_source_record, reader_context
        record = personal_source_record(key) if key not in SEED_FIXTURE_EVIDENCE_IDS else None
        if record is None:
            raise LookupError("This source is unavailable.")
        content = reader_context(request, record)
        card = content["card"]
        reading_record = content.get("record", record)
        from app.services.feed_first_reader import is_public_http_url
        media_url = str(reading_record.get("media_url") or "")
        return {"type": kind, "id": key, "title": card.get("headline", record.get("title", key)),
                "kind_label": "Source publication", "status": record.get("status", "unreviewed"),
                "summary": content["summary"], "sections": [], "sources": [source_metadata(record)],
                "expand_href": f"/intelligence/{key}?personal=1", "outside_scope": key not in {s["id"] for s in bundle["sources"]},
                "article_text": content["article_text"], "article_blocks": content["article_blocks"],
                "document_blocks": content["document_blocks"], "card": card,
                "body_availability": {"available": content["article_available"], "auto_acquisition": False},
                "media": {"spoken": content["spoken_media"], "transcript": content["media_transcript"],
                          "format": reading_record.get("media_format") or "",
                          "url": media_url if is_public_http_url(media_url) else "",
                          "source_url": card.get("source_link_url") or card.get("source_url") or "",
                          "transcript_version": reading_record.get("transcript_version") or "",
                          "transcript_read_error": reading_record.get("transcript_read_error") or "",
                          "transcript_provenance": {field: value for field, value in (reading_record.get("transcript_provenance") or {}).items()
                                                    if field in {"method", "created_by", "created_at", "language"}}},
                "trust_note": "Publication review and individual claim approval remain separate."}
    if kind == "relationship":
        edge = next((row for row in bundle["edges"] if row["id"] == key), None)
        if edge is None:
            raise LookupError("This relationship is unavailable in the applied scope. Inspect its actor or explicitly change scope.")
        return {"type": kind, "id": key, "title": edge["label"], "kind_label": "Recorded relationship",
                "status": edge["status_label"], "summary": edge["notes"],
                "sections": [{"title": "Relationship basis", "items": [_edge_item(edge)]}],
                "sources": [source_metadata(row) for row in bundle["sources"] if row["id"] in edge["evidence_ids"]],
                "expand_href": explorer.href(bundle["filters"], edge=key), "outside_scope": False}
    if kind == "observation":
        from app.services.variety_workspace import present_observation
        record = world.evidence_index.get(key)
        if record is None or not record.get("commercial_observation"):
            raise LookupError("This commercial observation is unavailable.")
        model = present_observation(record, entities=world.entities, trust="published")
        return {"type": kind, "id": key, "title": record.get("title", key), "kind_label": "Commercial observation",
                "status": record.get("status"), "summary": record.get("summary", ""),
                "sections": [{"title": "Observed listing", "data": model, "items": [
                    {"id": key, "type": "source", "label": record.get("title", key),
                     "summary": record.get("summary", ""), "status": "Commercial observation, not a Fact",
                     "sources": [source_metadata(record)]}]}], "sources": [source_metadata(record)],
                "expand_href": f"/intelligence/{key}", "outside_scope": key not in {s["id"] for s in bundle["sources"]}}
    entity = world.entities.get(key)
    if not entity or entity.get("entity_type") != kind:
        raise LookupError("This identity is unavailable.")
    sections = []
    kwargs = dict(entities=world.entities, relationships=world.relationships, published_evidence=world.published,
                  facts=world.facts, evidence_by_id=world.evidence_index, signals=world.signals,
                  assessments=world.assessments, berry_labels=world.berry_labels)
    if kind == "company":
        from app.services.company_workspace import present_company_portfolio
        portfolio = present_company_portfolio(key, **kwargs)
        items = []
        for row in (portfolio or {}).get("variety_rows", []):
            relationship_sources = [sid for edge in world.relationships
                                    if {key, row["id"]} == {edge.get("subject_id"), edge.get("object_id")}
                                    for sid in edge.get("evidence_ids") or []]
            items.append({"id": row["id"], "type": "variety", "label": row["name"],
                          "value": " · ".join(row["roles"]),
                          "status": world.entities.get(row["id"], {}).get("status", "unknown"),
                          "summary": "Recorded portfolio roles; source review does not approve each claim.",
                          "sources": _cited_sources(world, relationship_sources)})
        sections.append({"title": "Recorded portfolio roles", "data": portfolio, "items": items})
    elif kind == "variety":
        from app.services.variety_workspace import present_variety_compare
        comparison = present_variety_compare([key], **kwargs)
        items = []
        for card in comparison.get("varieties", []):
            for group in card["variety_intelligence"]["groups"]:
                for row in group["rows"]:
                    items.append({"id": row.get("id"), "label": " · ".join(row["trait_names"]),
                                  "value": row["statement"], "status": row["fact_status"],
                                  "summary": "; ".join(row["does_not_prove"]),
                                  "sources": _cited_sources(world, [row["evidence_id"]])})
        sections.append({"title": "Sourced cultivar observations", "data": comparison, "items": items})
    elif kind == "geography":
        from app.services.geography_workspace import geography_detail
        model = geography_detail(key, entities=world.entities, relationships=world.relationships,
                                 published_evidence=world.published, signals=world.signals,
                                 assessments=world.assessments, berry_labels=world.berry_labels)
        sources = _entity_sources(world, entity, bundle)
        sections.append({"title": "Recorded geographic activity", "data": model, "items": [
            {"id": row["id"], "type": "source", "label": row["title"], "status": row.get("review"),
             "sources": [row]} for row in sources]})
    linked_edges = [edge for edge in bundle["edges"] if key in {edge["subject_id"], edge["object_id"]}]
    if linked_edges:
        sections.insert(0, {"title": "Connections within this investigation", "items": [_edge_item(edge) for edge in linked_edges]})
    return {"type": kind, "id": key, "title": entity.get("name", key),
            "kind_label": {"company": "Company", "variety": "Cultivar", "geography": "Geography"}[kind],
            "status": entity.get("status", "unknown"), "summary": str(entity.get("description") or "")[:6000],
            "sections": sections, "sources": _entity_sources(world, entity, bundle),
            "expand_href": f"/geographies/{key}" if kind == "geography" else f"/entities/{kind}/{key}",
            "outside_scope": key not in bundle["nodes"], "roles": list(entity.get("roles") or []),
            "scope_note": "Profile sections show the full selected identity; the investigation scope remains unchanged."}
