"""Dry-run and stage deterministic trusted-source fidelity recoveries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.runtime_config import resolve_data_dir, resolve_inbox_dir
from app.services.extraction_backlog import inventory
from app.services.source_fidelity_recovery import (
    APPLICABLE_MATCHES, build_recovery_artifact, load_candidate_records,
    match_recoveries, recovery_manifest, write_recovery_artifact,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--artifact-dir", action="append", default=[], metavar="LABEL=PATH")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--id")
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--json", action="store_true")
    return parser


def _locations(args: argparse.Namespace, inbox_dir: Path) -> list[tuple[str, Path]]:
    values = [
        ("current_runtime_evidence", inbox_dir / "evidence"),
        ("current_runtime_normalized_transcripts", inbox_dir / "discovered_media" / "_normalized_transcripts"),
        ("current_runtime_transcripts", inbox_dir / "transcripts"),
        ("current_runtime_source_artifacts", inbox_dir / "source_artifacts"),
        ("current_runtime_article_cache", inbox_dir / "article_cache"),
        ("current_runtime_normalized_media", inbox_dir / "normalized_media"),
    ]
    for raw in args.artifact_dir:
        if "=" not in raw:
            raise SystemExit("--artifact-dir must be LABEL=PATH")
        label, path = raw.split("=", 1)
        values.append((label, Path(path).expanduser().resolve()))
    return values


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    if args.apply and not (args.ids or args.id):
        raise SystemExit("--apply requires explicit --id or --ids; bulk apply is forbidden")
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    total_started = time.perf_counter()
    trusted = get_repositories(data_dir, SCHEMAS_DIR).evidence.list(status="published")
    baseline = inventory(trusted)
    thin_ids = {
        str(row["id"])
        for row in baseline["items"]
        if row["readiness"] == "THIN_DESCRIPTION_ONLY"
    }
    thin = [record for record in trusted if str(record.get("id")) in thin_ids]
    classification_seconds = time.perf_counter() - total_started
    started = time.perf_counter()
    candidates = load_candidate_records(_locations(args, inbox_dir))
    results = match_recoveries(thin, candidates)
    report = recovery_manifest(results)
    report["performance_seconds"] = round(time.perf_counter() - started, 3)
    report["classification_seconds"] = round(classification_seconds, 3)
    report["total_seconds"] = round(time.perf_counter() - total_started, 3)
    selected_ids = set(args.ids or ([] if not args.id else [args.id]))
    if args.id:
        selected_ids.add(args.id)
    if selected_ids:
        results = [row for row in results if row["evidence_id"] in selected_ids]
        missing = selected_ids - {row["evidence_id"] for row in results}
        if missing:
            raise SystemExit("unknown or non-thin Evidence ids: " + ", ".join(sorted(missing)))
    if args.apply:
        trusted_by_id = {row["id"]: row for row in thin}
        outcomes = []
        for result in results:
            if result["match_class"] not in APPLICABLE_MATCHES:
                raise SystemExit(f"refusing non-exact recovery for {result['evidence_id']}: {result['match_class']}")
            artifact = build_recovery_artifact(result, trusted_by_id[result["evidence_id"]])
            path = inbox_dir / "source_fidelity" / "artifacts" / f"{result['evidence_id']}.json"
            outcomes.append({"evidence_id": result["evidence_id"], "outcome": write_recovery_artifact(path, artifact), "path": str(path)})
        print(json.dumps(outcomes, indent=2) if args.json else "\n".join(f"{row['evidence_id']}: {row['outcome']}" for row in outcomes))
        return 0
    if args.manifest:
        path = inbox_dir / "operations" / "source-fidelity-recovery" / "recovery-manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report if not selected_ids else recovery_manifest(results), indent=2, ensure_ascii=False, sort_keys=True))
    else:
        counts = report["counts"]
        print("SOURCE FIDELITY RECOVERY — DRY RUN")
        print(f"Thin trusted Evidence: {len(thin)}")
        print(f"Rich candidates indexed: {len(candidates)}")
        for name in ("EXACT_IDENTITY_MATCH", "EXACT_URL_MATCH", "LINEAGE_MATCH", "AMBIGUOUS", "CONFLICT", "NO_MATCH"):
            print(f"{name}: {counts.get(name, 0)}")
        print(f"Recoverable articles: {report['recoverable_articles']}")
        print(f"Recoverable transcripts: {report['recoverable_transcripts']}")
        print(f"Recovery indexing/matching: {report['performance_seconds']}s")
        print(f"Total including canonical readiness classification: {report['total_seconds']}s")
        print("No trusted Evidence or review decision was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
