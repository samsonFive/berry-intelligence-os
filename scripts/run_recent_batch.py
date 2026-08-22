"""Bounded recent-media batch: discover → screen → cheap transcript → enrich.

One source or item failure never aborts the rest. Whisper (tier 3) is skipped
by default; publisher transcripts and YouTube captions may still be used.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.ai_gateway.untrusted_complete import maybe_untrusted_completer
from app.services.article_refresh import process_discovered_article
from app.services.deterministic_tagging import matchers_from_entities
from app.services.media_discovery import DiscoveryError, discover_source, list_discovered_items
from app.services.media_orchestration import MediaOrchestrationService, MediaTranscriptionAdapter
from app.services.publication_enrichment import enrich_publication_draft
from app.services.relevance_screen import geography_corroboration_matchers
from app.services.relevance_screening import screen_discovered_item

DEFAULT_SOURCES = (
    "source-business-of-blueberries-podcast",
    "source-redagricola-on-the-road",
    "source-blueberries-tv-youtube",
    "source-lucentlands-podcast",
)


def _recency(item: dict) -> str:
    return str(item.get("published_date") or item.get("first_seen_at") or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="*", default=list(DEFAULT_SOURCES))
    parser.add_argument("--max-per-source", type=int, default=5)
    parser.add_argument("--max-total", type=int, default=16)
    parser.add_argument("--max-tier", type=int, default=2, help="1=publisher, 2=captions, 3=Whisper")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=ROOT / "inbox")
    parser.add_argument("--report", type=Path, help="Write JSON report to this path")
    args = parser.parse_args(argv)

    schema = json.loads((SCHEMAS_DIR / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    repositories = get_repositories(args.data_dir, SCHEMAS_DIR)
    completer = maybe_untrusted_completer()
    all_entities = repositories.entities.list()
    berries = [record for record in all_entities if record.get("entity_type") == "berry"]
    geographies = [record for record in all_entities if record.get("entity_type") == "geography"]
    companies = [record for record in all_entities if record.get("entity_type") == "company"]
    # Relevance Screen Boundary V1 (2026-08-23): reused by the web_article
    # branch below for the same query-provenance corroboration + real
    # body-fetch two-stage screen scripts/run_collection.py and
    # scripts/process_discovered_media.py already use -- this was the one
    # real batch tool still routing web_article items through the older,
    # single-stage, no-body-fetch app/services/relevance_screening.py gate.
    geo_matchers = geography_corroboration_matchers(all_entities)
    company_matchers = matchers_from_entities(all_entities, "company")

    report: dict = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {},
        "items": [],
        "totals": {
            "discovered": 0,
            "relevant": 0,
            "skipped": 0,
            "transcript_ready": 0,
            "enriched": 0,
            "review_ready": 0,
            "failed": 0,
        },
    }

    for source_id in args.sources:
        source_report = {"discovered": 0, "new": 0, "error": None, "items": []}
        try:
            result = discover_source(source_id, inbox_dir=args.inbox_dir, data_dir=args.data_dir)
            source_report["discovered"] = result.found
            source_report["new"] = result.new
            if result.status == "error":
                source_report["error"] = result.error
        except (DiscoveryError, OSError, ValueError) as exc:
            source_report["error"] = str(exc)
        report["sources"][source_id] = source_report

    selected: list[dict] = []
    per_source = max(1, min(args.max_per_source, args.max_total // max(1, len(args.sources))))
    for source_id in args.sources:
        items = sorted(list_discovered_items(args.inbox_dir, source_id), key=_recency, reverse=True)
        selected.extend(items[:per_source])
    selected = selected[: max(0, args.max_total)]
    report["totals"]["discovered"] = len(selected)

    service = MediaOrchestrationService(
        repositories=repositories,
        inbox_dir=args.inbox_dir,
        evidence_errors=lambda record: [error.message for error in validator.iter_errors(record)],
        transcript_adapter=MediaTranscriptionAdapter(
            args.inbox_dir,
            transcribe_missing=True,
            max_tier=args.max_tier,
        ),
        complete_json=completer,
    )

    for item in selected:
        row = {
            "item_id": item.get("id"),
            "source_id": item.get("source_id"),
            "title": item.get("title"),
            "published_date": item.get("published_date"),
            "relevance": None,
            "state": None,
            "transcript_status": None,
            "enriched": False,
            "review_ready": False,
            "error": None,
        }
        try:
            if item.get("media_format") == "web_article":
                # Real two-stage, body-aware screen (relevance_screen.py +
                # article_refresh.py) instead of the single-stage,
                # metadata-only, no-body-fetch screen_discovered_item() --
                # see the module-level comment above geo_matchers/
                # company_matchers.
                result, extra = process_discovered_article(
                    item,
                    orchestrator=service,
                    inbox_dir=args.inbox_dir,
                    completer=completer,
                    berries=berries,
                    geographies=geographies,
                    companies=companies,
                    geo_matchers=geo_matchers,
                    company_matchers=company_matchers,
                )
                row["relevance"] = extra.get("relevance_screen_stage_b") or extra.get("relevance_screen_stage_a")
                skipped = result.state == "skipped_irrelevant"
            else:
                screening = screen_discovered_item(item)
                row["relevance"] = screening.to_dict()
                result = service.process(
                    item["id"],
                    relevance_gate=True,
                    enrich=True,
                )
                skipped = screening.decision == "skip" or result.state == "skipped_irrelevant"
            row["state"] = result.state
            row["transcript_status"] = result.transcript_status
            row["error"] = "; ".join(result.errors) if result.errors else None
            if skipped:
                report["totals"]["skipped"] += 1
            else:
                report["totals"]["relevant"] += 1
            if result.transcript_status == "ready":
                report["totals"]["transcript_ready"] += 1
            if result.state == "awaiting_publication_review" and result.publication_draft_id:
                draft_path = args.inbox_dir / "evidence" / f"{result.publication_draft_id}.json"
                if draft_path.exists():
                    draft = json.loads(draft_path.read_text(encoding="utf-8"))
                    if (draft.get("ai_enrichment") or {}).get("model_provenance", {}).get("status") != "ok" and completer:
                        draft = enrich_publication_draft(
                            draft,
                            item,
                            berries=berries,
                            geographies=geographies,
                            entities=companies,
                            complete_json=completer,
                        )
                        draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    if (draft.get("ai_enrichment") or {}).get("model_provenance", {}).get("status") == "ok":
                        row["enriched"] = True
                        report["totals"]["enriched"] += 1
                    row["review_ready"] = True
                    report["totals"]["review_ready"] += 1
            if result.errors and result.state not in {"awaiting_publication_review", "skipped_irrelevant"}:
                report["totals"]["failed"] += 1
        except Exception as exc:  # one item must not abort the batch
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["state"] = "failed"
            report["totals"]["failed"] += 1
        report["items"].append(row)
        report["sources"].setdefault(item.get("source_id") or "unknown", {}).setdefault("items", []).append(row["item_id"])

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0 if report["totals"]["failed"] < report["totals"]["discovered"] or not selected else 1


if __name__ == "__main__":
    raise SystemExit(main())
