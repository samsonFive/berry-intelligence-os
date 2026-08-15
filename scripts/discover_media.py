"""Run spoken-word media discovery for one registered Source.

Discovers episodes/videos from a Source's configured feed, normalizes their
metadata, deduplicates against previously-staged items, and writes staging
records under `inbox/discovered_media/` (untrusted, disposable, never read
by scripts/validate_records.py or scripts/build_static.py -- see
app/services/media_discovery.py's module docstring for the full trust-
boundary rationale).

This script never creates Evidence, Facts, Assessments, or Recommendations.
It never writes to `data/`. It never writes to `inbox/evidence/` (the
existing draft-Evidence intake). Running it repeatedly against an unchanged
feed is a no-op at the logical-item level (idempotent by design).

Usage:
    python scripts/discover_media.py --source source-lucentlands-podcast
    python scripts/discover_media.py --source source-lucentlands-podcast --fetch-transcripts
    python scripts/discover_media.py --source source-lucentlands-podcast --data-dir path/to/data --inbox-dir path/to/inbox

No scheduling, no daemon: run it by hand (or from an external scheduler
that isn't part of this project) whenever you want a fresh check.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR  # noqa: E402
from app.services.media_discovery import (  # noqa: E402
    DiscoveryError,
    TRANSCRIPT_PUBLISHER,
    acquire_raw_transcript_artifact,
    discover_source,
)

DEFAULT_INBOX_DIR = ROOT / "inbox"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="Source id from data/configuration/sources.json, e.g. source-lucentlands-podcast")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Override data/ directory (default: the project's data/)")
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR, help="Override schemas/ directory")
    parser.add_argument("--inbox-dir", type=Path, default=DEFAULT_INBOX_DIR, help="Override inbox/ directory (default: the project's inbox/)")
    parser.add_argument(
        "--fetch-transcripts",
        action="store_true",
        help="For items where a publisher-declared transcript URL was detected, also fetch and stage the raw transcript text "
        "(inbox/discovered_media/_transcripts/). Off by default -- discovery alone never fetches transcript bodies.",
    )
    args = parser.parse_args(argv)

    try:
        result = discover_source(
            args.source,
            inbox_dir=args.inbox_dir,
            data_dir=args.data_dir,
            schemas_dir=args.schemas_dir,
        )
    except DiscoveryError as exc:
        print(f"error: {exc}")
        return 2

    if result.status == "error":
        print(f"source: {result.source_id}")
        print(f"status: error -- {result.error}")
        return 1

    print(f"source: {result.source_id}")
    print(f"status: ok")
    print(f"items found in feed: {result.found}")
    print(f"newly discovered: {result.new}")
    print(f"already known: {result.already_known}")
    if result.item_failures:
        print(f"item-level failures: {len(result.item_failures)}")
        for failure in result.item_failures:
            print(f"  - index {failure.index} ({failure.identifier or 'no identifier'}): {failure.error}")
    else:
        print("item-level failures: 0")

    transcripts_fetched = 0
    if args.fetch_transcripts:
        for item in result.items:
            availability = item.get("transcript_availability") or {}
            if availability.get("status") != TRANSCRIPT_PUBLISHER:
                continue
            artifact = acquire_raw_transcript_artifact(args.inbox_dir, item)
            if artifact is not None:
                transcripts_fetched += 1
        print(f"raw transcripts fetched: {transcripts_fetched}")

    matched = [item for item in result.items if item.get("possible_evidence_matches")]
    if matched:
        print(f"possible matches to already-known Evidence: {len(matched)}")
        for item in matched:
            reasons = ", ".join(sorted({r for m in item["possible_evidence_matches"] for r in m["reasons"]}))
            evidence_ids = ", ".join(m["evidence_id"] for m in item["possible_evidence_matches"])
            print(f"  - {item['id']} ({item['title'][:60]!r}) -> {evidence_ids} [{reasons}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
