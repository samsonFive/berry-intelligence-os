"""Real, bounded article ingestion: discover -> screen -> acquire -> enrich
-> publication draft, for a single article_rss Source.

    python scripts/ingest_articles.py --source <source_id> [--max-items 20]

Mirrors run_collection.py's contract (never aborts a batch on one item's
failure, never blocks acquisition on a missing AI credential, never
auto-trusts anything) but is a separate, first-class entry point rather
than a change to the recurring collection_runner, since article
acquisition (HTTP + readable-text extraction) is a materially different
operation from audio/video transcription and this is a bounded vertical
slice, not a recurring-runner redesign.

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
from app.main import BERRIES
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.ai_gateway.credentials import MissingCredentialError
from app.services.article_acquisition import ArticleAcquisitionError, fetch_article
from app.services.media_discovery import discover_source, list_discovered_items
from app.services.media_orchestration import (
    JsonStagedTranscriptAdapter,
    MediaOrchestrationError,
    MediaOrchestrationService,
)
from app.services.publication_enrichment import EnrichmentError, enrichment_model_configured, generate_enrichment
from app.services.relevance_screen import screen_relevance


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

    entities = repositories.entities.list()
    allowed_berry_ids = list(BERRIES.keys())
    allowed_geography_ids = [e["id"] for e in entities if e.get("entity_type") == "geography" and e.get("id")]
    allowed_entity_ids = [e["id"] for e in entities if e.get("id")]

    orchestrator = MediaOrchestrationService(
        repositories=repositories,
        inbox_dir=args.inbox_dir,
        evidence_errors=evidence_errors,
        transcript_adapter=JsonStagedTranscriptAdapter(args.inbox_dir),
    )

    threshold_kwargs = {"threshold": args.relevance_threshold} if args.relevance_threshold is not None else {}
    enrichment_available = enrichment_model_configured() and bool(os.environ.get("PERPLEXITY_API_KEY", "").strip())
    if args.enrichment_model:
        os.environ["BIOS_ENRICHMENT_MODEL"] = args.enrichment_model
        enrichment_available = bool(os.environ.get("PERPLEXITY_API_KEY", "").strip())

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

        stage_a = screen_relevance(
            title=item.get("title") or "", description=item.get("description") or "", **threshold_kwargs
        )
        entry["relevance_screen_stage_a"] = stage_a.as_dict()

        if not stage_a.needs_body_check and not stage_a.relevant:
            # Confidently irrelevant on metadata alone -- zero signal at
            # all. Cheapest possible exit: no acquisition, no draft.
            entry["outcome"] = "skipped_irrelevant"
            counts["skipped_irrelevant"] += 1
            report_items.append(entry)
            continue

        # Check existing representation *before* acquiring or creating
        # anything -- orchestrator.process() populates publication_draft_id
        # both when it creates a brand-new draft and when it finds an
        # already-existing pending one (same field, two different
        # meanings), so that field alone can't distinguish "new" from
        # "duplicate." A prior resolution status of anything but "none"
        # means something already represents this item (trusted
        # publication, a pending draft, or a rejected draft) -- exactly the
        # "same article discovered twice -> reuse/skip, idempotent" case.
        try:
            existing = orchestrator.resolve_publication_artifact(item)
        except MediaOrchestrationError as exc:
            entry["outcome"] = "orchestration_error"
            entry["error"] = str(exc)
            report_items.append(entry)
            continue
        if existing.status != "none":
            entry["outcome"] = "duplicate"
            entry["parent_resolution_status"] = existing.status
            counts["duplicate"] += 1
            report_items.append(entry)
            continue

        # Stage A was either confidently relevant (a direct berry mention)
        # or borderline (generic agriculture signal, no berry mention) --
        # either way the real body is needed now: to attach the `article`
        # field for a confident item, or to let Stage B decide a
        # borderline one on berry identity alone, never on score.
        try:
            body = fetch_article(item.get("canonical_url") or "")
        except ArticleAcquisitionError as exc:
            entry["outcome"] = "acquisition_failed"
            entry["acquisition_failure_category"] = exc.category
            entry["error"] = str(exc)
            counts["acquisition_failed"] += 1
            report_items.append(entry)
            continue
        counts["acquired"] += 1

        if stage_a.needs_body_check:
            counts["borderline_checked"] += 1
            stage_b = screen_relevance(
                title=item.get("title") or "",
                description=item.get("description") or "",
                body=body.full_text,
                **threshold_kwargs,
            )
            entry["relevance_screen_stage_b"] = stage_b.as_dict()
            if not stage_b.relevant:
                counts["borderline_confirmed_irrelevant"] += 1
                entry["outcome"] = "skipped_irrelevant"
                report_items.append(entry)
                continue
            counts["borderline_confirmed_relevant"] += 1

        counts["relevant"] += 1

        try:
            result = orchestrator.process(item_id, dry_run=False)
        except MediaOrchestrationError as exc:
            entry["outcome"] = "orchestration_error"
            entry["error"] = str(exc)
            report_items.append(entry)
            continue

        if result.publication_draft_id is None:
            entry["outcome"] = "orchestration_error"
            entry["error"] = "no publication draft id after process() despite a fresh resolution"
            report_items.append(entry)
            continue

        draft_id = result.publication_draft_id
        entry["draft_id"] = draft_id
        draft_path = args.inbox_dir / "evidence" / f"{draft_id}.json"
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        draft["article"] = body.as_dict()

        if enrichment_available:
            try:
                suggestion = generate_enrichment(
                    title=item.get("title") or "",
                    description=item.get("description") or "",
                    content_excerpt=body.full_text,
                    allowed_berry_ids=allowed_berry_ids,
                    allowed_geography_ids=allowed_geography_ids,
                    allowed_entity_ids=allowed_entity_ids,
                )
            except (MissingCredentialError, EnrichmentError) as exc:
                entry["enrichment_error"] = str(exc)
                counts["enrichment_unavailable"] += 1
            else:
                draft["ai_enrichment"] = suggestion.as_dict()
                counts["enriched"] += 1
                entry["enriched"] = True
        else:
            counts["enrichment_unavailable"] += 1
            entry["enrichment_error"] = "PERPLEXITY_API_KEY or BIOS_ENRICHMENT_MODEL not configured"

        draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        entry["outcome"] = "review_ready"
        counts["review_ready"] += 1
        report_items.append(entry)

    report = {"state": "ok", "source_id": args.source, "counts": counts, "items": report_items}
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else _human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
