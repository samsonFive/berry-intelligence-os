"""Acquire a transcript for one discovered spoken-word media item.

Runs the acquisition hierarchy (publisher transcript -> local speech-to-text
-- see app/services/media_transcription.py's module docstring for the full
Tier 1/2/3 rationale and why Tier 2/platform-captions auto-discovery is not
implemented) for exactly one item already staged by
scripts/discover_media.py, and writes a normalized transcript record to
inbox/transcripts/ -- either fully resolved (if --parent-evidence-id is
given) or "staged" (parent_evidence_id: null, promotable later via
--resolve-parent).

This script never extracts CI claims, never creates atomic Evidence
proposals, never publishes trusted Evidence, and never calls
TranscriptEvidenceExtractionService.run() (app/services/transcript_evidence.py,
owned by a different workstream). It never writes to `data/`.

Usage:
    python scripts/transcribe_media.py --item discovered-... --model small
    python scripts/transcribe_media.py --item discovered-... --parent-evidence-id ev-...
    python scripts/transcribe_media.py --item discovered-... --force
    python scripts/transcribe_media.py --resolve-parent discovered-... --parent-evidence-id ev-...

No scheduling, no daemon: one discovered item at a time, run by hand.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR  # noqa: E402
from app.services.media_transcription import (  # noqa: E402
    AVAILABLE_WHISPER_MODELS,
    DEFAULT_WHISPER_MODEL,
    TranscriptionError,
    load_discovered_item,
    resolve_parent_evidence,
    transcribe_discovered_item,
)

DEFAULT_INBOX_DIR = ROOT / "inbox"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--item", help="Discovered media item id, e.g. discovered-lucentlands-podcast-<hash>")
    parser.add_argument("--resolve-parent", metavar="ITEM_ID", help="Promote an already-staged transcript to resolved, without re-running acquisition")
    parser.add_argument("--parent-evidence-id", help="Real Evidence id (ev-...) for the publication artifact this transcript belongs to. If omitted, a staged transcript is produced instead (Phase 12).")
    parser.add_argument("--model", default=DEFAULT_WHISPER_MODEL, choices=AVAILABLE_WHISPER_MODELS, help=f"Local Whisper model size (default: {DEFAULT_WHISPER_MODEL})")
    parser.add_argument("--device", default=None, help="cpu|cuda; auto-detected if omitted")
    parser.add_argument("--language", default=None, help="Force a language code instead of Whisper's own detection")
    parser.add_argument("--created-by", default=None, help="Provenance label; a sensible default is derived per-tier if omitted")
    parser.add_argument("--force", action="store_true", help="Bypass media-download and transcription caches")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--schemas-dir", type=Path, default=SCHEMAS_DIR)
    parser.add_argument("--inbox-dir", type=Path, default=DEFAULT_INBOX_DIR)
    args = parser.parse_args(argv)

    if not args.item and not args.resolve_parent:
        parser.error("one of --item or --resolve-parent is required")

    if args.resolve_parent:
        if not args.parent_evidence_id:
            parser.error("--resolve-parent requires --parent-evidence-id")
        try:
            payload = resolve_parent_evidence(args.inbox_dir, args.resolve_parent, args.parent_evidence_id)
        except (TranscriptionError, ValueError) as exc:
            print(f"error: {exc}")
            return 1
        print(f"resolved: {payload['id']}")
        print(f"parent_evidence_id: {payload['parent_evidence_id']}")
        print(f"segments: {len(payload['segments'])}")
        return 0

    item = load_discovered_item(args.inbox_dir, args.item)
    if item is None:
        print(f"error: no discovered item staged at inbox/discovered_media/{args.item}.json -- run scripts/discover_media.py first")
        return 2

    outcome = transcribe_discovered_item(
        args.inbox_dir,
        item,
        model=args.model,
        device=args.device,
        language=args.language,
        parent_evidence_id=args.parent_evidence_id,
        created_by=args.created_by,
        force=args.force,
    )

    print(f"item: {item['id']}")
    print(f"title: {item.get('title', '')[:80]!r}")
    if outcome.status == "error":
        print(f"status: error")
        print(f"tier attempted: {outcome.tier}")
        print(f"error: {outcome.error}")
        return 1

    print(f"status: ok")
    print(f"tier: {outcome.tier}")
    print(f"cache: {'hit' if outcome.cache_hit else 'miss'}")
    print(f"output: {outcome.output_path}")
    print(f"segments: {outcome.segment_count}")
    print(f"detected language: {outcome.detected_language}")
    print(f"media duration (s): {outcome.media_duration_seconds}")
    print(f"transcript end (s): {outcome.transcript_duration_seconds}")
    print(f"parent_evidence_id: {outcome.parent_evidence_id or '(none -- staged transcript)'}")
    diagnostics = outcome.diagnostics
    print(f"timestamps monotonic: {diagnostics.get('timestamps_monotonic')}")
    print(f"short-duration segments (<0.2s): {diagnostics.get('short_duration_segment_count')}")
    print(f"very-short-text segments (<2 chars): {diagnostics.get('very_short_text_segment_count')}")
    if diagnostics.get("coverage_ratio") is not None:
        print(f"coverage ratio (transcript end / media duration): {diagnostics['coverage_ratio']:.2f}")
    if diagnostics.get("low_coverage_suspected"):
        print("WARNING: suspiciously low transcript coverage relative to media duration")
    print("NOTE: this is an unreviewed, machine-generated transcript; accuracy is not claimed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
