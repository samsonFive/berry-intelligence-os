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
    python scripts/discover_media.py --all

`--all` iterates every registered Source that has a usable `discovery`
block (i.e. every Source this module actually knows how to poll), running
the exact same per-source `discover_source()` used by `--source` for each
one in turn and printing one report per source. It is not a scheduler --
it does not loop, does not run in the background, and does not run twice.
One source failing (network error, malformed feed, unsupported adapter)
never stops the remaining sources from being checked; each source's
outcome is reported independently.

No scheduling, no daemon: run it by hand (or from an external scheduler
that isn't part of this project) whenever you want a fresh check.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.composition import get_repositories  # noqa: E402
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR  # noqa: E402
from app.services.media_discovery import (  # noqa: E402
    DiscoveryError,
    TRANSCRIPT_PUBLISHER,
    acquire_raw_transcript_artifact,
    discover_source,
)
from app.services.source_lifecycle import is_collection_eligible  # noqa: E402

DEFAULT_INBOX_DIR = ROOT / "inbox"


def _sources_with_discovery_config(data_dir: Path, schemas_dir: Path) -> list[str]:
    """Every registered Source id whose record carries a usable `discovery`
    block -- i.e. every source `--all` can actually do something with.
    Sources without one (still the majority of the registry -- most are
    `reference_manual`, checked by a human, not polled) are silently
    skipped, not reported as failures: not having a `discovery` block is a
    normal, expected state, not an error."""
    repos = get_repositories(data_dir, schemas_dir)
    ids = []
    for source in repos.sources.list():
        if is_collection_eligible(source):
            ids.append(source["id"])
    return ids


def _report_result(result, *, inbox_dir: Path, fetch_transcripts: bool) -> bool:
    """Print one source's discovery report. Returns True if this source's
    run should count as a success for `--all`'s overall exit code."""
    if result.status == "error":
        print(f"source: {result.source_id}")
        print(f"status: error -- {result.error}")
        return False

    print(f"source: {result.source_id}")
    print("status: ok")
    print(f"items found in feed: {result.found}")
    print(f"newly discovered: {result.new}")
    print(f"already known: {result.already_known}")
    if result.feed_failures:
        print(f"feed-level failures: {len(result.feed_failures)} (other configured feed(s) for this source still succeeded)")
        for failure in result.feed_failures:
            print(f"  - {failure['feed_url']}: {failure['error']}")
    if result.item_failures:
        print(f"item-level failures: {len(result.item_failures)}")
        for failure in result.item_failures:
            print(f"  - index {failure.index} ({failure.identifier or 'no identifier'}): {failure.error}")
    else:
        print("item-level failures: 0")

    transcripts_fetched = 0
    if fetch_transcripts:
        for item in result.items:
            availability = item.get("transcript_availability") or {}
            if availability.get("status") != TRANSCRIPT_PUBLISHER:
                continue
            artifact = acquire_raw_transcript_artifact(inbox_dir, item)
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

    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", help="Source id from data/configuration/sources.json, e.g. source-lucentlands-podcast")
    source_group.add_argument("--all", action="store_true", help="Run discovery for every Source that has a usable 'discovery' block, one after another, reporting per-source.")
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

    if args.source:
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
        ok = _report_result(result, inbox_dir=args.inbox_dir, fetch_transcripts=args.fetch_transcripts)
        return 0 if ok else 1

    # --all
    source_ids = _sources_with_discovery_config(args.data_dir, args.schemas_dir)
    if not source_ids:
        print("no sources with a usable 'discovery' block found")
        return 0

    any_failure = False
    for index, source_id in enumerate(source_ids):
        if index > 0:
            print()
        try:
            result = discover_source(
                source_id,
                inbox_dir=args.inbox_dir,
                data_dir=args.data_dir,
                schemas_dir=args.schemas_dir,
            )
        except DiscoveryError as exc:
            # Only a caller-mistake (unsupported adapter, malformed config)
            # reaches here -- network/feed failures are already captured as
            # a per-source DiscoveryRunResult, per discover_source()'s
            # contract. Either way, one source's failure must never stop
            # the remaining sources from being checked.
            print(f"source: {source_id}")
            print(f"status: error -- {exc}")
            any_failure = True
            continue
        ok = _report_result(result, inbox_dir=args.inbox_dir, fetch_transcripts=args.fetch_transcripts)
        any_failure = any_failure or not ok

    return 1 if any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
