"""Reproducible static-site generator.

Reads only trusted, published records from `data/` (never `inbox/`) and
renders the same Jinja templates the live app uses into a self-contained,
relocatable `generated/` directory: every internal link is rewritten to a
path relative to the file that contains it, so the output works when
deployed at any host and any subpath -- no configuration required.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import (  # noqa: E402
    BERRIES,
    DATA_DIR,
    PRIORITY_DIMENSIONS,
    PRIORITY_LEVELS,
    PRIORITY_QUEUE_LABELS,
    all_assessments,
    all_entities,
    all_facts,
    all_recommendations,
    all_relationships,
    all_signals,
    berry_label,
    entity_activity,
    entity_intelligence_timeline,
    entity_index,
    entity_regions,
    evidence_regions,
    entity_synthesis_context,
    facts_for_entity,
    facts_for_evidence,
    get_domain_services,
    get_query_services,
    landscape_context,
    list_drafts,
    load_strategic_questions,
    published_evidence,
    queue_items,
    relationships_for_entity,
    relationships_for_evidence,
    SCHEMAS_DIR,
    sources_page_context,
    templates,
)
from app.services.assessment_scope import assessment_berry_scope, attach_assessment_scope  # noqa: E402
from app.services.berries.landscape import PRIMARY_SOURCE_TYPES  # noqa: E402
from app.services.executive_readout import (  # noqa: E402
    caution as readout_caution,
    top_assessments as readout_top_assessments,
    top_signals as readout_top_signals,
    what_changed as readout_what_changed,
    what_we_know as readout_what_we_know,
)
from app.services.intelligence_feed import annotate_feed_semantics, build_intelligence_feed  # noqa: E402
from app.services.learner import (  # noqa: E402
    all_concepts as learn_all_concepts,
    concepts_by_pillar as learn_concepts_by_pillar,
    related_concepts as learn_related_concepts,
    related_intelligence_for_concept,
)
from app.services.review_workbench import build_public_scanner_summary  # noqa: E402
from app.services.variety_workspace import (  # noqa: E402
    present_variety_detail,
    present_variety_index,
)
from app.services.variety_universe.corpus_discovery import build_discovered_candidates  # noqa: E402
from app.services.variety_universe.coverage import universe_headcounts  # noqa: E402
from app.services.company_workspace import present_company_portfolio  # noqa: E402
from app.services.geography_workspace import geography_detail, geography_index  # noqa: E402
from app.services.strategic_question_workspace import (  # noqa: E402
    strategic_question_detail as present_strategic_question_detail,
    strategic_question_index as present_strategic_question_index,
)

OUTPUT_DIR = ROOT / "generated"


class _FakeURL:
    def __init__(self, path: str) -> None:
        self.path = path


class _FakeRequest:
    """Stand-in for Starlette's Request: templates only read .url.path and
    .query_params.get(...), so a full Request/ASGI app is unnecessary here."""

    def __init__(self, path: str) -> None:
        self.url = _FakeURL(path)
        self.query_params: dict[str, str] = {}


def render(template_name: str, path: str, context: dict[str, Any]) -> str:
    context = {**context, "request": _FakeRequest(path), "static_build": True}
    context.setdefault("nav_work_counts", templates.env.globals["nav_work"]())
    context.setdefault(
        "ui_context",
        {
            "berry": "global",
            "berry_label": "Global",
            "feed_view": "grid",
            "landscape_href": "/entities/berry",
            "options": [{"id": "global", "label": "Global", "slug": ""}],
            "is_global": True,
        },
    )
    context.setdefault("berries", BERRIES)
    return templates.get_template(template_name).render(context)


_HREF_RE = re.compile(r'(href|src)="(/[^"#?]*)(#[^"]*)?"')


def _depth_prefix(output_file: Path) -> str:
    depth = len(output_file.parent.relative_to(OUTPUT_DIR).parts)
    return "../" * depth


def _rewrite_internal_links(html: str, prefix: str) -> str:
    def repl(match: re.Match[str]) -> str:
        attr, path, fragment = match.group(1), match.group(2), match.group(3) or ""
        if path == "/":
            target = "index.html"
        else:
            stripped = path.strip("/")
            last_segment = stripped.rsplit("/", 1)[-1]
            target = stripped if "." in last_segment else f"{stripped}/index.html"
        return f'{attr}="{prefix}{target}{fragment}"'

    return _HREF_RE.sub(repl, html)


def write_page(template_name: str, route_path: str, context: dict[str, Any]) -> Path:
    if route_path == "/":
        output_file = OUTPUT_DIR / "index.html"
    else:
        output_file = OUTPUT_DIR / route_path.strip("/") / "index.html"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    html = render(template_name, route_path, context)
    html = _rewrite_internal_links(html, _depth_prefix(output_file))
    output_file.write_text(html, encoding="utf-8")
    return output_file


def build() -> list[Path]:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    # GitHub Pages must publish generated assets (including Pagefind's
    # underscore-prefixed internals) verbatim rather than invoking Jekyll.
    (OUTPUT_DIR / ".nojekyll").touch()

    written: list[Path] = []
    evidence = published_evidence()
    entities = entity_index()
    questions = load_strategic_questions()
    region_tokens = {
        "Americas": "americas", "Europe": "emea", "Middle East & Africa": "emea",
        "Oceania": "australia-nz", "Asia": "asia",
    }
    static_feed_evidence = [
        {
            **record,
            "filter_regions": sorted({
                region_tokens[region]
                for region in evidence_regions(record, entities)
                if region in region_tokens
            }),
        }
        for record in evidence
    ]

    # base.html calls these as Jinja globals on every single page render (via
    # the sidebar). They're cheap once, but at this record volume calling the
    # live, uncached versions (which each re-read data/ from disk) once per
    # page turns a few hundred pages into minutes of redundant I/O. Nothing
    # in data/ changes mid-build, so compute them once here instead.
    queue_summary_once = {
        dim: sum(1 for r in evidence if (r.get("priority") or {}).get(dim, {}).get("level", "none") != "none")
        for dim in PRIORITY_DIMENSIONS
    }
    previous_globals = {
        "queue_counts": templates.env.globals.get("queue_counts"),
        "pending_review_count": templates.env.globals.get("pending_review_count"),
        "nav_work": templates.env.globals.get("nav_work"),
    }
    templates.env.globals["queue_counts"] = lambda: queue_summary_once
    templates.env.globals["pending_review_count"] = lambda: 0
    templates.env.globals["nav_work"] = lambda: {
        "reading_action": 0,
        "testing_action": 0,
        "commercial_inventory": queue_summary_once.get("commercial_position", 0),
        "monitoring_inventory": queue_summary_once.get("monitoring", 0),
        "signal_alerts": 0,
        "brief_action": 0,
        "review_now": 0,
        "pending_open": 0,
        "emerging_signals": 0,
    }

    # Static asset.
    static_out = OUTPUT_DIR / "static"
    static_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "app" / "static" / "app.css", static_out / "app.css")
    shutil.copy2(ROOT / "app" / "static" / "search-core.js", static_out / "search-core.js")
    shutil.copy2(ROOT / "app" / "static" / "v2.css", static_out / "v2.css")
    shutil.copy2(ROOT / "app" / "static" / "v2.js", static_out / "v2.js")
    vendor_src = ROOT / "app" / "static" / "vendor"
    if vendor_src.is_dir():
        shutil.copytree(vendor_src, static_out / "vendor", dirs_exist_ok=True)

    # Newsfeed.
    written.append(
        write_page(
            "feed.html",
            "/",
            {
                "evidence": static_feed_evidence,
                "total_count": len(evidence),
                "berry_label": berry_label,
                "options": {"berries": [], "sources": [], "competitors": [], "geographies": []},
                "filters": {"q": "", "berry": "", "source": "", "priority": "", "competitor": "", "geography": ""},
                "priority_dimensions": PRIORITY_DIMENSIONS,
                "priority_levels": PRIORITY_LEVELS,
                "authoring_mode": False,
            },
        )
    )

    # Evidence detail + attachments.
    # Pre-index reverse lineage once for the whole Evidence set (avoid
    # O(evidence × signals/assessments) scans per page).
    signals_all = all_signals()
    assessments_all = all_assessments()
    signals_by_evidence: dict[str, list] = {}
    assessments_by_evidence: dict[str, list] = {}
    for signal in signals_all:
        for eid in signal.get("evidence_ids") or []:
            signals_by_evidence.setdefault(eid, []).append(signal)
    for assessment in assessments_all:
        for eid in assessment.get("evidence_ids") or []:
            assessments_by_evidence.setdefault(eid, []).append(assessment)
    for record in evidence:
        record_id = record["id"]
        linked_entities = [entities[e] for e in record.get("entity_ids", []) if e in entities]
        facts = facts_for_evidence(record_id)
        relationships = []
        for rel in relationships_for_evidence(record_id):
            relationships.append(
                {
                    **rel,
                    "subject": entities.get(rel.get("subject_id"), {}).get("name", rel.get("subject_id")),
                    "object": entities.get(rel.get("object_id"), {}).get("name", rel.get("object_id")),
                }
            )
        written.append(
            write_page(
                "evidence.html",
                f"/evidence/{record_id}",
                {
                    "record": record,
                    "linked_entities": linked_entities,
                    "facts": facts,
                    "relationships": relationships,
                    "citing_signals": signals_by_evidence.get(record_id, []),
                    "citing_assessments": assessments_by_evidence.get(record_id, []),
                    "linked_strategic_questions": [
                        sq for sq in questions if sq["id"] in (record.get("strategic_question_ids") or [])
                    ],
                    "berry_label": berry_label,
                    "authoring_mode": False,
                },
            )
        )
        source_dir = ROOT / "data" / "attachments" / record_id
        if source_dir.exists():
            dest_dir = OUTPUT_DIR / "evidence" / record_id / "attachments"
            dest_dir.mkdir(parents=True, exist_ok=True)
            for attachment_file in source_dir.iterdir():
                if attachment_file.is_file():
                    shutil.copy2(attachment_file, dest_dir / attachment_file.name)

    # Entity listings + detail pages.
    entity_types = sorted({e.get("entity_type") for e in all_entities() if e.get("entity_type")})
    for entity_type in entity_types:
        type_entities = sorted(
            (e for e in all_entities() if e.get("entity_type") == entity_type),
            key=lambda e: e.get("name", ""),
        )
        list_context: dict[str, Any] = {
            "entities": type_entities,
            "entity_type": entity_type,
            "authoring_mode": False,
            "berries": BERRIES,
            "regions": [],
            "companies": [],
            "filters": {"q": "", "berry": "", "region": "", "company": "", "has_rights": "", "has_observation": "", "market": "", "ip_and_observation": ""},
            "variety_view": "index",
            "variety_cards": [],
            "berry_inventory": [],
            "unnamed_observation_count": 0,
            "observation_total_count": 0,
            "observation_workspace": {},
            "competition": {},
            "geographies": [],
            "total_count": len(type_entities),
        }
        if entity_type == "variety":
            index_model = present_variety_index(
                varieties=type_entities,
                entities=list(entities.values()),
                relationships=all_relationships(),
                published_evidence=evidence,
                berry_labels=BERRIES,
                inbox_drafts=[],
                signals=all_signals(),
                candidates=[],
                facts=all_facts(),
            )
            report = build_discovered_candidates(
                varieties=type_entities,
                entities=list(entities.values()),
                published_evidence=evidence,
                facts=all_facts(),
                existing_candidates=[],
            )
            list_context.update(
                {
                    "variety_cards": index_model["cards"],
                    "berry_inventory": index_model["berry_inventory"],
                    "unnamed_observation_count": index_model["unnamed_observation_count"],
                    "observation_total_count": index_model["observation_total_count"],
                    "universe": universe_headcounts(
                        varieties=type_entities,
                        candidates=report["candidates"],
                    ),
                }
            )
        written.append(
            write_page(
                "entity_list.html",
                f"/entities/{entity_type}",
                list_context,
            )
        )

    # Loaded once and reused across every entity below -- calling their
    # disk-reading equivalents (facts_for_entity() et al.) inside this loop
    # instead was exactly the queue_counts() mistake documented above,
    # just for a different pair of globals.
    facts_all = all_facts()
    relationships_all = all_relationships()
    evidence_idx = {r["id"]: r for r in evidence}

    for entity in all_entities():
        entity_id = entity["id"]
        linked_evidence = [r for r in evidence if entity_id in (r.get("entity_ids") or [])]
        independent_sources = {r.get("source_name") for r in linked_evidence if r.get("source_name")}
        last_updated = (
            linked_evidence[0].get("published_date") or linked_evidence[0].get("captured_date")
            if linked_evidence
            else None
        )
        entity_facts = [f for f in facts_all if entity_id in (f.get("entity_ids") or [])]
        entity_relationships = [
            r for r in relationships_all if entity_id in (r.get("subject_id"), r.get("object_id"))
        ]
        regions = sorted(entity_regions(entity, entities, linked_evidence))
        activity = entity_activity(linked_evidence, entity_facts, entity_relationships, entities, evidence_idx)
        synthesis = entity_synthesis_context(
            entity,
            entities,
            include_pending=False,
            linked_evidence=linked_evidence,
        )
        if entity.get("entity_type") in ("company", "variety"):
            synthesis["intelligence_timeline"] = entity_intelligence_timeline(
                entity_id=entity_id,
                entities=entities,
                linked_evidence=linked_evidence,
                entity_facts=entity_facts,
                entity_relationships=entity_relationships,
                entity_signals=synthesis["entity_signals"],
                entity_assessments=synthesis["entity_assessments"],
                evidence_idx=evidence_idx,
            )
        if entity.get("entity_type") == "variety":
            synthesis.update(
                present_variety_detail(
                    entity,
                    entities=entities,
                    relationships=relationships_all,
                    published_evidence=evidence,
                    grouped_relationships=synthesis["grouped_relationships"],
                    recent_intelligence=synthesis["recent_intelligence"],
                    berry_labels=BERRIES,
                    inbox_drafts=[],
                    signals=all_signals(),
                    facts=entity_facts,
                    evidence_by_id=evidence_idx,
                )
            )
        written.append(
            write_page(
                "entity.html",
                f"/entities/{entity['entity_type']}/{entity_id}",
                {
                    "entity": entity,
                    "linked_evidence": linked_evidence,
                    "linked_facts": entity_facts,
                    "activity": activity,
                    "evidence_count": len(linked_evidence),
                    "source_count": len(independent_sources),
                    "last_updated": last_updated,
                    "regions": regions,
                    "berry_label": berry_label,
                    "authoring_mode": False,
                    **synthesis,
                },
            )
        )

    # Company Variety Portfolio Intelligence V1 -- a finite, enumerable set
    # (one page per Company, like the entity profile loop just above), not
    # a combinatorial id-selection space like Compare -- so unlike
    # Variety/Company Compare, this is static-safe and gets the same
    # trusted-only treatment as every entity.html page above.
    portfolio_signals = all_signals()
    portfolio_assessments = all_assessments()
    portfolio_strategic_questions = load_strategic_questions()
    for entity in all_entities():
        if entity.get("entity_type") != "company":
            continue
        portfolio = present_company_portfolio(
            entity["id"],
            entities=entities,
            relationships=relationships_all,
            published_evidence=evidence,
            facts=facts_all,
            evidence_by_id=evidence_idx,
            signals=portfolio_signals,
            assessments=portfolio_assessments,
            berry_labels=BERRIES,
            strategic_questions=portfolio_strategic_questions,
        )
        if portfolio is None:
            continue
        written.append(
            write_page(
                "company_portfolio.html",
                f"/entities/company/{entity['id']}/portfolio",
                {"portfolio": portfolio, "authoring_mode": False},
            )
        )

    # Geography / Market Intelligence V1 -- same static-safety story as
    # Company Portfolio just above: a finite, enumerable set of real
    # Geography entities, built entirely from trusted-only data.
    geography_signals = all_signals()
    geography_assessments = all_assessments()
    geography_strategic_questions = load_strategic_questions()
    written.append(
        write_page(
            "geography_index.html",
            "/geographies",
            {
                "geographies": geography_index(
                    entities=entities,
                    published_evidence=evidence,
                    relationships=relationships_all,
                    signals=geography_signals,
                    berry_labels=BERRIES,
                ),
                "authoring_mode": False,
            },
        )
    )
    for entity in all_entities():
        if entity.get("entity_type") != "geography":
            continue
        evidence_idx = {r["id"]: r for r in evidence if r.get("id")}
        geo = geography_detail(
            entity["id"],
            entities=entities,
            relationships=relationships_all,
            published_evidence=evidence,
            signals=geography_signals,
            assessments=geography_assessments,
            berry_labels=BERRIES,
            strategic_questions=geography_strategic_questions,
            entity_facts=facts_for_entity(entity["id"]),
            entity_relationships=relationships_for_entity(entity["id"], relationships_all),
            evidence_idx=evidence_idx,
        )
        if geo is None:
            continue
        written.append(
            write_page(
                "geography_detail.html",
                f"/geographies/{entity['id']}",
                {
                    "geo": geo,
                    "entity": {"id": entity["id"], "name": geo.get("name"), "entity_type": "geography"},
                    "intelligence_timeline": geo.get("intelligence_timeline") or {},
                    "berry_label": berry_label,
                    "berries": BERRIES,
                    "authoring_mode": False,
                },
            )
        )

    # Scanner / work queue — trusted published snapshot only. Never read inbox/.
    high_priority = [r for r in evidence if any(v.get("level") == "high" for v in (r.get("priority") or {}).values())]
    feed = build_intelligence_feed(
        drafts=[],
        published=evidence,
        entities=entities,
        berry_labels=BERRIES,
        filter_key="all",
        limit=48,
    )
    annotate_feed_semantics(feed["entries"], signals=all_signals(), candidates=[])
    written.append(
        write_page(
            "work_queue.html",
            "/work-queue",
            {
                "recent_evidence": evidence[:5],
                "drafts": [],
                "review_cards": [],
                "feed": feed,
                "feed_view": "grid",
                "reviewer": "",
                "return_filter": "",
                "promoted_id": "",
                "promoted_title": "",
                "promoted_date": "",
                "saved": False,
                "scanner": build_public_scanner_summary(evidence),
                "unresolved_entities": [e for e in all_entities() if e.get("status") == "unverified"],
                "high_priority": high_priority[:5],
                "recent_signals": all_signals()[:5],
                "queue_summary": {dim: len(queue_items(dim)) for dim in PRIORITY_DIMENSIONS},
                "authoring_mode": False,
            },
        )
    )

    from app.services.morning_brief import build_morning_brief

    static_brief = build_morning_brief(
        inbox_dir=ROOT / "inbox",
        published=evidence,
        drafts=[],
        unvalidated=[],
        signals=all_signals(),
        entities=entities,
        sources=[],
        berry_labels=BERRIES,
        source_coverage={},
        mark_seen=False,
        include_signal_candidates=False,
    )
    written.append(
        write_page(
            "morning_brief.html",
            "/brief",
            {
                "brief": static_brief,
                "authoring_mode": False,
                "return_to": "/brief",
                "reviewer": "",
            },
        )
    )

    # Read-only Sources registry from trusted configuration.
    written.append(
        write_page(
            "sources.html",
            "/sources",
            {**sources_page_context(None, None, None, None, None, "entity_type", None), "authoring_mode": False},
        )
    )

    # Priority-tagged intelligence views (reading/testing/watches/positions).
    from app.services.analyst_queue import build_dimension_page
    from app.services.commercial_positions import commercial_page_model
    from app.services.testing_workspace import testing_page_model
    from app.services.monitor_workspace import monitor_page_model

    for dimension in PRIORITY_DIMENSIONS:
        page = build_dimension_page(
            dimension=dimension,
            records=queue_items(dimension),
            inbox_dir=ROOT / "inbox",
            entities=entities,
            berry_labels=BERRIES,
            signals=all_signals(),
            show_completed=True,
        )
        monitor = {
            "watch_items": page["items"],
            "monitor_alerts": [],
        }
        if dimension == "monitoring":
            monitor = monitor_page_model(
                watch_items=page["items"],
                entities=entities,
                berry_labels=BERRIES,
                published=evidence,
                drafts=[],
                signals=all_signals(),
                candidates=[],
                inbox_dir=None,
                health_rows=[],
                include_drafts=False,
            )
        testing_extra: dict = {}
        if dimension == "testing":
            testing_extra = testing_page_model(
                records=queue_items(dimension),
                inbox_dir=None,
                entities=entities,
                berry_labels=BERRIES,
                evidence_by_id={str(row.get("id")): row for row in evidence if row.get("id")},
                facts_by_id={},
                show_completed=True,
                static_build=True,
            )
            page = {**page, **testing_extra}
        position_extra: dict = {}
        if dimension == "commercial_position":
            position_extra = commercial_page_model(
                records=queue_items(dimension),
                inbox_dir=None,
                entities=entities,
                berry_labels=BERRIES,
                facts=all_facts(),
                signals=all_signals(),
                assessments=all_assessments(),
                static_build=True,
            )
            page = {**page, **position_extra}
        written.append(
            write_page(
                "queue.html",
                f"/queues/{dimension}",
                {
                    **page,
                    "berry_label": berry_label,
                    "authoring_mode": False,
                    "static_build": True,
                    "filters": {"region": ""},
                    "reviewer": "",
                    "position_proposals": [],
                    "signal_alerts": [],
                    "reading_buckets": [],
                    "reading_bucket_counts": {},
                    "return_to": "",
                    **monitor,
                    **testing_extra,
                    **position_extra,
                },
            )
        )

    # Strategic Question + Decision Workspace V1 -- same static-safety story
    # as Company Portfolio/Geography above: a finite, enumerable set of real
    # Strategic Question records, built entirely from trusted-only data
    # (Evidence/Facts/Signals/Assessments/Recommendations have no draft
    # state reachable from these presenters).
    # `questions` loaded once at build start for Evidence lineage + SQ pages.
    sq_signals = all_signals()
    sq_assessments = all_assessments()
    sq_recommendations = all_recommendations()
    written.append(
        write_page(
            "strategic_question_list.html",
            "/strategic-questions",
            {
                "questions": present_strategic_question_index(
                    questions=questions,
                    published_evidence=evidence,
                    facts=facts_all,
                    signals=sq_signals,
                    assessments=sq_assessments,
                    recommendations=sq_recommendations,
                    berry_labels=BERRIES,
                ),
                "authoring_mode": False,
            },
        )
    )
    for sq in questions:
        detail = present_strategic_question_detail(
            sq["id"],
            questions=questions,
            entities=entities,
            published_evidence=evidence,
            facts=facts_all,
            signals=sq_signals,
            assessments=sq_assessments,
            recommendations=sq_recommendations,
            berry_labels=BERRIES,
        )
        if detail is None:
            continue
        written.append(
            write_page(
                "strategic_question_detail.html",
                f"/strategic-questions/{sq['id']}",
                {"sq": detail, "authoring_mode": False},
            )
        )

    # Signals.
    signals = all_signals()
    assessments_for_signals = all_assessments()
    written.append(
        write_page("signal_list.html", "/signals", {"signals": signals, "authoring_mode": False})
    )
    for signal in signals:
        written.append(
            write_page(
                "signal_detail.html",
                f"/signals/{signal['id']}",
                {
                    "signal": signal,
                    "linked_evidence": [r for r in evidence if r["id"] in (signal.get("evidence_ids") or [])],
                    "linked_facts": [f for f in all_facts() if f["id"] in (signal.get("fact_ids") or [])],
                    "linked_entities": [
                        entities[e] for e in (signal.get("entity_ids") or []) if e in entities
                    ],
                    "linked_strategic_questions": [
                        sq for sq in questions if sq["id"] in (signal.get("strategic_question_ids") or [])
                    ],
                    "citing_assessments": [
                        a for a in assessments_for_signals if signal["id"] in (a.get("signal_ids") or [])
                    ],
                    "authoring_mode": False,
                },
            )
        )

    # Assessments.
    assessments = attach_assessment_scope(all_assessments(), BERRIES)
    fact_idx = {f["id"]: f for f in all_facts()}
    written.append(
        write_page("assessment_list.html", "/assessments", {"assessments": assessments, "authoring_mode": False})
    )
    for assessment in assessments:
        written.append(
            write_page(
                "assessment_detail.html",
                f"/assessments/{assessment['id']}",
                {
                    "assessment": assessment,
                    "berry_scope": assessment.get("berry_scope") or assessment_berry_scope(assessment, BERRIES),
                    "linked_facts": [f for f in all_facts() if f["id"] in (assessment.get("fact_ids") or [])],
                    "linked_signals": [
                        s for s in signals if s["id"] in (assessment.get("signal_ids") or [])
                    ],
                    "linked_evidence": [
                        r for r in evidence if r["id"] in (assessment.get("evidence_ids") or [])
                    ],
                    "linked_entities": [
                        entities[e] for e in (assessment.get("entity_ids") or []) if e in entities
                    ],
                    "linked_strategic_questions": [
                        sq for sq in questions if sq["id"] in (assessment.get("strategic_question_ids") or [])
                    ],
                    "counterevidence": [
                        fact_idx[cid] for cid in (assessment.get("counterevidence_ids") or []) if cid in fact_idx
                    ],
                    "authoring_mode": False,
                },
            )
        )

    # Recommendations.
    recommendations = all_recommendations()
    written.append(
        write_page(
            "recommendation_list.html",
            "/recommendations",
            {"recommendations": recommendations, "authoring_mode": False},
        )
    )
    for recommendation in recommendations:
        written.append(
            write_page(
                "recommendation_detail.html",
                f"/recommendations/{recommendation['id']}",
                {
                    "recommendation": recommendation,
                    "linked_assessments": [
                        a for a in assessments if a["id"] in (recommendation.get("assessment_ids") or [])
                    ],
                    "linked_signals": [
                        s for s in signals if s["id"] in (recommendation.get("signal_ids") or [])
                    ],
                    "linked_facts": [
                        f for f in all_facts() if f["id"] in (recommendation.get("fact_ids") or [])
                    ],
                    "linked_evidence": [
                        r for r in evidence if r["id"] in (recommendation.get("evidence_ids") or [])
                    ],
                    "linked_entities": [
                        entities[e] for e in (recommendation.get("entity_ids") or []) if e in entities
                    ],
                    "linked_strategic_questions": [
                        sq for sq in questions if sq["id"] in (recommendation.get("strategic_question_ids") or [])
                    ],
                    "authoring_mode": False,
                },
            )
        )

    # Berry Landscapes (V2 Phase 1.5B, BL-026; genericized for all four
    # berries in the 2026-08-20 multi-berry portability audit -- this loop
    # previously rendered only "/landscapes/berries/blueberry", the same
    # hardcoding already fixed in the live route (app/main.py) and the nav
    # (base.html); left unfixed here, the static site would have kept
    # serving a 404 for the other three even after those two fixes).
    for berry_id in BERRIES:
        berry_slug = berry_id.removeprefix("berry-")
        written.append(
            write_page(
                "landscape.html",
                f"/landscapes/berries/{berry_slug}",
                {**landscape_context(berry_id), "authoring_mode": False},
            )
        )

    # Landscape V2's cross-berry ALL view -- trusted-only aggregate data,
    # same as every per-berry page above, so it is equally static-safe.
    written.append(
        write_page(
            "landscape_all.html",
            "/landscapes",
            {
                **get_domain_services(DATA_DIR).landscape.landscape_context_all_berries(BERRIES),
                "authoring_mode": False,
            },
        )
    )

    # Executive Intelligence Readout V1 -- trusted-only cross-corpus
    # synthesis, same static-safety story as Landscape above.
    _readout_evidence = published_evidence()
    _readout_signals = all_signals()
    _readout_assessments = all_assessments()
    _readout_recommendations = all_recommendations()
    _readout_coverage_service = get_query_services(DATA_DIR, SCHEMAS_DIR).coverage
    _readout_all_entity_ids = {e["id"] for e in all_entities() if e.get("id")}
    _readout_landscape_all = get_domain_services(DATA_DIR).landscape.landscape_context_all_berries(BERRIES)
    written.append(
        write_page(
            "executive_readout.html",
            "/readout",
            {
                "what_changed": readout_what_changed(
                    published_evidence=_readout_evidence, signals=_readout_signals, assessments=_readout_assessments
                ),
                "who_matters": {
                    "berry_rows": _readout_landscape_all["berry_rows"],
                    "actors_to_watch": _readout_landscape_all["actors_to_watch"],
                },
                "what_we_know": readout_what_we_know(
                    published_evidence=_readout_evidence,
                    facts=facts_all,
                    coverage_service=_readout_coverage_service,
                    primary_source_types=PRIMARY_SOURCE_TYPES,
                ),
                "assessments": readout_top_assessments(_readout_assessments, _readout_recommendations),
                "signals": readout_top_signals(_readout_signals),
                "caution": readout_caution(
                    disputed_relationship_count=len(_readout_coverage_service.disputed_relationships(_readout_all_entity_ids)),
                    unresolved_strategic_question_count=len(_readout_coverage_service.active_strategic_questions()),
                ),
                "header_stats": {
                    "company_count": sum(1 for e in entities.values() if e.get("entity_type") == "company"),
                    "variety_count": sum(1 for e in entities.values() if e.get("entity_type") == "variety"),
                    "evidence_count": len(_readout_evidence),
                    "signal_count": len(_readout_signals),
                    "assessment_count": len(_readout_assessments),
                },
                "presentation_mode": False,
                "authoring_mode": False,
            },
        )
    )

    # Learner Mode V1 -- a small, finite, enumerable concept set (unlike
    # Variety/Company Compare's unbounded id-combination space), so unlike
    # those two it IS wired into the public static build. related_intelligence
    # reuses the same trusted facts_all/evidence_idx already loaded above --
    # no additional corpus scan, and only trusted Fact/Evidence, never
    # inbox/ drafts or Signal Candidates.
    written.append(
        write_page(
            "learn_home.html",
            "/learn",
            {
                "pillars": learn_concepts_by_pillar(),
                "concept_count": len(learn_all_concepts()),
                "search_query": "",
                "search_results": None,
                "authoring_mode": False,
            },
        )
    )
    for concept in learn_all_concepts():
        related_intel = related_intelligence_for_concept(
            concept,
            facts=facts_all,
            entities=entities,
            evidence_by_id=evidence_idx,
        )
        written.append(
            write_page(
                "learn_concept.html",
                f"/learn/{concept['slug']}",
                {
                    "concept": concept,
                    "related": learn_related_concepts(concept),
                    "related_intelligence": related_intel,
                    "authoring_mode": False,
                },
            )
        )

    # Full search-results page. Runs Pagefind's own JS entirely client-side
    # (reads ?q= at load, renders via the site's own card styling) -- no
    # server-side content to pass here, unlike every other page above.
    written.append(write_page("search.html", "/search", {"authoring_mode": False}))

    for key, value in previous_globals.items():
        if value is None:
            templates.env.globals.pop(key, None)
        else:
            templates.env.globals[key] = value
    return written


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def validate_no_drafts_leaked() -> list[str]:
    draft_ids = {d["id"] for d in list_drafts() if d.get("id")}
    draft_titles = {d["title"] for d in list_drafts() if d.get("title")}
    if not draft_ids and not draft_titles:
        return []
    leaked: list[str] = []
    for html_file in OUTPUT_DIR.rglob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        for draft_id in draft_ids:
            if draft_id in content:
                leaked.append(f"{_display_path(html_file)}: contains draft id {draft_id}")
        for draft_title in draft_titles:
            if draft_title and draft_title in content:
                leaked.append(f"{_display_path(html_file)}: contains draft title '{draft_title}'")
    return leaked


def build_search_index() -> bool:
    """Run Pagefind over the generated site, so the whole site -- including
    search -- is reproducible from one command. Client-side search only: no
    server, no external service, consistent with keeping this build free of
    proprietary SaaS dependencies (ADR-0001).

    Optional locally (pip install pagefind pagefind_bin enables it); the
    deploy workflow always installs it, so a failure there is a real build
    failure, not silently skipped like a missing local install is.
    """
    try:
        import pagefind  # noqa: F401
    except ImportError:
        return False
    result = subprocess.run(
        [sys.executable, "-m", "pagefind", "--site", str(OUTPUT_DIR)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"pagefind failed:\n{result.stdout}\n{result.stderr}")
    return True


def main() -> int:
    written = build()
    leaked = validate_no_drafts_leaked()
    if leaked:
        print("Static build produced output that leaks unpublished drafts:")
        for entry in leaked:
            print(f"- {entry}")
        return 1

    if build_search_index():
        print("Search index built (pagefind).")
    else:
        print(
            "Skipped search index: pagefind not installed locally "
            "(pip install pagefind pagefind_bin to enable it here -- "
            "the deployed site always has it via CI)."
        )

    print(f"Static build complete: {len(written)} pages written to {_display_path(OUTPUT_DIR)}/")
    print("Verified: no unpublished draft ids or titles appear in the output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
