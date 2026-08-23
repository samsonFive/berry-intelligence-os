"""Report trusted-source extraction readiness and write bounded manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.extraction_backlog import build_manifest, inventory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--manifest", type=int, choices=(10, 25, 100))
    parser.add_argument("--qualification-identity")
    parser.add_argument("--seconds-per-window", type=float, default=121.874)
    parser.add_argument("--json", action="store_true")
    return parser


def _human(report: dict) -> str:
    counts = report["classification_counts"]
    lines = [
        "ATOMIC EXTRACTION BACKLOG READINESS",
        f"Trusted published: {report['trusted_published']}",
        f"Extraction ready: {report['extraction_ready']}",
        f"Full articles: {counts.get('READY_FULL_ARTICLE', 0)}",
        f"Transcripts: {counts.get('READY_TRANSCRIPT', 0)}",
        f"Structured registry: {counts.get('READY_STRUCTURED_REGISTRY', 0)}",
        f"Thin descriptions: {counts.get('THIN_DESCRIPTION_ONLY', 0)}",
        f"Missing content: {counts.get('MISSING_SOURCE_CONTENT', 0)}",
        f"Unsupported: {counts.get('UNSUPPORTED_ARTIFACT', 0)}",
        f"Duplicates/superseded: {report['duplicates_skipped']}",
        f"Repeated thin boilerplate excess (not treated as duplicates): {report['repeated_thin_source_hash_excess']}",
        "",
        "Ready berry distribution: " + json.dumps(report["berry_distribution_ready"], sort_keys=True),
        "Ready source types: " + json.dumps(report["source_type_distribution_ready"], sort_keys=True),
        "Ready languages: " + json.dumps(report["language_distribution_ready"], sort_keys=True),
        "Fidelity failures: " + json.dumps(report["fidelity_failure_causes"], sort_keys=True),
        "",
        "Source length distributions (chars / estimated tokens):",
    ]
    for name, values in report["length_distribution"].items():
        lines.append(f"  {name}: {json.dumps(values, sort_keys=True)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    records = get_repositories(data_dir, SCHEMAS_DIR).evidence.list()
    report = inventory(records)
    if args.manifest:
        manifest = build_manifest(
            report,
            args.manifest,
            qualification_identity=args.qualification_identity,
            seconds_per_window=args.seconds_per_window,
        )
        path = inbox_dir / "operations" / "extraction-backlog" / f"PILOT-{args.manifest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            runtime = manifest["hypothetical_runtime"]
            review = manifest["review_volume"]
            print(f"Manifest: {path}")
            print(f"Selected: {manifest['selected_size']}/{manifest['requested_size']}")
            print(f"Hypothetical runtime: {runtime['estimated_seconds']}s")
            print(f"Estimated review proposals: {review['estimated_proposals']}")
            print("Qualification identity: " + manifest["qualification_identity"])
        return 0
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) if args.json else _human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
