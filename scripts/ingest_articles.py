"""Real, bounded article ingestion: discover -> screen -> acquire -> enrich
-> publication draft, for a single article_rss Source.

    python scripts/ingest_articles.py --source <source_id> [--max-items 20]

A thin CLI wrapper around app/services/article_refresh.py's
process_discovered_article() -- the same per-item pipeline (two-stage,
body-aware relevance screening, real HTML acquisition, enrichment) that
scripts/refresh_current_intelligence.py now also uses for the normal
recurring refresh path, so this script and the recurring runner never
diverge on how an article item gets triaged.

Two-stage relevance, per app/services/relevance_screen.py's design:
Stage A (title+description) confidently accepts a direct berry mention
and confidently rejects zero-signal items without ever acquiring
anything. A Stage A "borderline" result (generic agriculture/pricing
language, no berry mention -- e.g. an onion or apple-crop story) is
neither accepted nor rejected yet: the real body is acquired and Stage B
decides on berry identity alone, never on aggregate score. A confidently
relevant Stage A result still gets the body acquired (needed for the
`article` field and enrichment either way), just without needing Stage B
to decide relevance first.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator, FormatChecker

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.ai_gateway.untrusted_complete import maybe_untrusted_completer
from app.services.article_refresh import process_discovered_article
from app.services.deterministic_tagging import matchers_from_entities
from app.services.relevance_screen import geography_corroboration_matchers
from app.services.media_discovery import discover_source, list_discovered_items
from app.services.media_orchestration import JsonStagedTranscriptAdapter, MediaOrchestrationService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="A Source ID configured with an article_rss discovery adapter")
    parser.add_argument("--max-items", type=int, default=20, help="Most-recent-first cap on items processed this run")
    parser.add_argument("--relevance-threshold", type=int, default=None, help="Override the default relevance score threshold")
    parser.add_argument("--enrichment-model", help="Overrides BIOS_ENRICHMENT_MODEL for this run")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable report")
    return parser


def _human(report: dict) -> str:
    counts = report["counts"]
    lines = [
        f"Source: {report['source_id']}",
        f"  discovered: {counts['discovered']}",
        f"  selected (most recent, capped): {counts['selected']}",
        f"  relevant (final, stage A + confirmed borderline): {counts['relevant']}",
        f"  skipped (irrelevant): {counts['skipped_irrelevant']}",
        f"  borderline checked against real body: {counts['borderline_checked']}"
        f" (confirmed relevant {counts['borderline_confirmed_relevant']},"
        f" confirmed irrelevant {counts['borderline_confirmed_irrelevant']})",
        f"  acquired (real article body): {counts['acquired']}",
        f"  blocked/failed acquisition: {counts['acquisition_failed']}",
        f"  duplicate (already had a draft/trusted parent): {counts['duplicate']}",
        f"  enriched (real AI suggestion): {counts['enriched']}",
        f"  enrichment unavailable: {counts['enrichment_unavailable']}",
        f"  review-ready: {counts['review_ready']}",
    ]
    if report["items"]:
        lines.append("")
        lines.append("Items:")
        for item in report["items"]:
            lines.append(f"  {item['outcome']:>18}  {item.get('title', '')[:70]}  ({item['item_id']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    schema = json.loads((args.schemas_dir / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    evidence_errors = lambda record: [error.message for error in validator.iter_errors(record)]
    repositories = get_repositories(args.data_dir, args.schemas_dir)

    try:
        discovery_result = discover_source(
            args.source, inbox_dir=args.inbox_dir, data_dir=args.data_dir, schemas_dir=args.schemas_dir
        )
    except Exception as exc:  # noqa: BLE001 -- a caller-mistake or transport failure is a reportable run result, not a crash
        print(json.dumps({"state": "error", "error": str(exc)}, indent=2))
        return 2

    if discovery_result.status == "error":
        print(json.dumps({"state": "error", "error": discovery_result.error}, indent=2))
        return 2

    all_items = list_discovered_items(args.inbox_dir, args.source)
    all_items.sort(key=lambda item: item.get("published_date") or "", reverse=True)
    selected = all_items[: args.max_items]

    all_entities = repositories.entities.list()
    berries = [record for record in all_entities if record.get("entity_type") == "berry"]
    geographies = [record for record in all_entities if record.get("entity_type") == "geography"]
    companies = [record for record in all_entities if record.get("entity_type") == "company"]
    geo_matchers = geography_corroboration_matchers(all_entities)
    company_matchers = matchers_from_entities(all_entities, "company")

    orchestrator = MediaOrchestrationService(
        repositories=repositories,
        inbox_dir=args.inbox_dir,
        evidence_errors=evidence_errors,
        transcript_adapter=JsonStagedTranscriptAdapter(args.inbox_dir),
    )

    threshold_kwargs = {"threshold": args.relevance_threshold} if args.relevance_threshold is not None else {}
    if args.enrichment_model:
        os.environ["BERRY_ENRICHMENT_MODEL"] = args.enrichment_model
    # Shared with the rest of the Scanner pipeline (app/services/ai_gateway/
    # untrusted_complete.py, also used by scripts/run_recent_batch.py) --
    # None when PERPLEXITY_API_KEY is not set, never raises.
    completer = maybe_untrusted_completer()

    counts = {
        "discovered": discovery_result.found,
        "selected": len(selected),
        "relevant": 0,
        "skipped_irrelevant": 0,
        "borderline_checked": 0,
        "borderline_confirmed_relevant": 0,
        "borderline_confirmed_irrelevant": 0,
        "acquired": 0,
        "acquisition_failed": 0,
        "duplicate": 0,
        "enriched": 0,
        "enrichment_unavailable": 0,
        "review_ready": 0,
    }
    report_items: list[dict] = []

    for item in selected:
        item_id = item["id"]
        entry: dict = {"item_id": item_id, "title": item.get("title")}

        result, extra = process_discovered_article(
            item,
            orchestrator=orchestrator,
            inbox_dir=args.inbox_dir,
            completer=completer,
            berries=berries,
            geographies=geographies,
            companies=companies,
            relevance_threshold=args.relevance_threshold,
            geo_matchers=geo_matchers,
            company_matchers=company_matchers,
        )
        entry.update(extra)
        if result.errors:
            entry["error"] = "; ".join(result.errors)

        if extra.get("acquired"):
            counts["acquired"] += 1
        if "relevance_screen_stage_b" in extra:
            counts["borderline_checked"] += 1

        if result.state == "article_acquisition_failed":
            entry["outcome"] = "acquisition_failed"
            counts["acquisition_failed"] += 1
        elif result.state == "skipped_irrelevant":
            entry["outcome"] = "skipped_irrelevant"
            counts["skipped_irrelevant"] += 1
            if "relevance_screen_stage_b" in extra:
                counts["borderline_confirmed_irrelevant"] += 1
        elif result.state == "orchestration_error":
            entry["outcome"] = "orchestration_error"
        elif result.publication_draft_id is not None and result.state == "awaiting_publication_review" and (
            (result.parent_resolution.message or "") == "Publication draft created for review."
        ):
            # A brand-new draft this run -- process_discovered_article()
            # already attached article body + enrichment to the file.
            if "relevance_screen_stage_b" in extra:
                counts["borderline_confirmed_relevant"] += 1
            counts["relevant"] += 1
            entry["draft_id"] = result.publication_draft_id
            if extra.get("enrichment_status") == "ok":
                counts["enriched"] += 1
                entry["enriched"] = True
            else:
                counts["enrichment_unavailable"] += 1
                entry["enrichment_error"] = extra.get("enrichment_caveats") or extra.get("enrichment_status") or "PERPLEXITY_API_KEY not configured"
            entry["outcome"] = "review_ready"
            counts["review_ready"] += 1
        else:
            # Any other resolution (existing draft/trusted/rejected parent)
            # is a duplicate discovery of something already represented.
            entry["outcome"] = "duplicate"
            entry["parent_resolution_status"] = result.parent_resolution.status
            counts["duplicate"] += 1

        report_items.append(entry)

    report = {"state": "ok", "source_id": args.source, "counts": counts, "items": report_items}
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else _human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
