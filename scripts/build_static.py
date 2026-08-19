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
    entity_index,
    entity_regions,
    evidence_regions,
    entity_synthesis_context,
    evidence_for_strategic_question,
    facts_for_evidence,
    landscape_context,
    list_drafts,
    load_strategic_questions,
    published_evidence,
    queue_items,
    relationships_for_evidence,
    sources_page_context,
    templates,
)
from app.services.intelligence_feed import build_intelligence_feed  # noqa: E402
from app.services.review_workbench import build_public_scanner_summary  # noqa: E402

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
    templates.env.globals["queue_counts"] = lambda: queue_summary_once
    templates.env.globals["pending_review_count"] = lambda: 0
    templates.env.globals["nav_work"] = lambda: {
        "reading_action": 0,
        "testing_action": 0,
        "commercial_inventory": queue_summary_once.get("commercial_position", 0),
        "monitoring_inventory": queue_summary_once.get("monitoring", 0),
        "signal_alerts": 0,
    }

    # Static asset.
    static_out = OUTPUT_DIR / "static"
    static_out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "app" / "static" / "app.css", static_out / "app.css")
    shutil.copy2(ROOT / "app" / "static" / "search-core.js", static_out / "search-core.js")

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
        written.append(
            write_page(
                "entity_list.html",
                f"/entities/{entity_type}",
                {"entities": type_entities, "entity_type": entity_type, "authoring_mode": False},
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
                    **entity_synthesis_context(entity, entities, include_pending=False),
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
    written.append(
        write_page(
            "work_queue.html",
            "/work-queue",
            {
                "recent_evidence": evidence[:5],
                "drafts": [],
                "review_cards": [],
                "feed": feed,
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
                },
            )
        )

    # Strategic questions.
    questions = load_strategic_questions()
    counts = {sq["id"]: len(evidence_for_strategic_question(sq["id"])) for sq in questions if sq.get("id")}
    written.append(
        write_page(
            "strategic_question_list.html",
            "/strategic-questions",
            {"questions": questions, "counts": counts, "authoring_mode": False},
        )
    )
    for sq in questions:
        written.append(
            write_page(
                "strategic_question_detail.html",
                f"/strategic-questions/{sq['id']}",
                {
                    "sq": sq,
                    "linked_evidence": evidence_for_strategic_question(sq["id"]),
                    "berry_label": berry_label,
                    "authoring_mode": False,
                },
            )
        )

    # Signals.
    signals = all_signals()
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
                    "authoring_mode": False,
                },
            )
        )

    # Assessments.
    assessments = all_assessments()
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
                    "linked_facts": [f for f in all_facts() if f["id"] in (assessment.get("fact_ids") or [])],
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

    # Blueberry Landscape (V2 Phase 1.5B, BL-026).
    written.append(
        write_page(
            "landscape.html",
            "/landscapes/berries/blueberry",
            {**landscape_context("berry-blueberry"), "authoring_mode": False},
        )
    )

    # Full search-results page. Runs Pagefind's own JS entirely client-side
    # (reads ?q= at load, renders via the site's own card styling) -- no
    # server-side content to pass here, unlike every other page above.
    written.append(write_page("search.html", "/search", {"authoring_mode": False}))

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
