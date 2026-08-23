"""Plan selective historic source reacquisition; network execution is explicit."""

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
from app.services.article_acquisition import ArticleAcquisitionError, fetch_article
from app.services.extraction_backlog import inventory as readiness_inventory
from app.services.source_fidelity_recovery import write_recovery_artifact
from app.services.source_reacquisition import (
    build_inventory, build_reacquired_artifact, classify_acquisition_failure,
    pilot_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--priority", choices=("high", "medium", "low"))
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--manifest", action="store_true", help="Write private body-free pilot-10 and pilot-25 manifests")
    parser.add_argument("--execute", action="store_true", help="Explicitly allow bounded network acquisition")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    repos = get_repositories(data_dir, SCHEMAS_DIR)
    trusted = repos.evidence.list(status="published")
    readiness = readiness_inventory(trusted)
    thin_ids = {row["id"] for row in readiness["items"] if row["readiness"] == "THIN_DESCRIPTION_ONLY"}
    thin = [row for row in trusted if row.get("id") in thin_ids]
    report = build_inventory(
        thin, entities=repos.entities.list(), signals=repos.signals.list(),
        assessments=repos.assessments.list(),
    )
    if args.manifest:
        folder = inbox_dir / "operations" / "source-reacquisition"
        folder.mkdir(parents=True, exist_ok=True)
        for size in (10, 25):
            payload = pilot_manifest(report["items"], size)
            (folder / f"REACQUISITION-PILOT-{size}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
            )

    selected = report["items"]
    if args.priority:
        selected = [row for row in selected if row["priority"] == args.priority.upper()]
    if args.ids:
        wanted = set(args.ids)
        selected = [row for row in selected if row["evidence_id"] in wanted]
        missing = wanted - {row["evidence_id"] for row in selected}
        if missing:
            raise SystemExit("unknown, non-thin, or priority-filtered Evidence ids: " + ", ".join(sorted(missing)))
    if args.limit is not None:
        if args.limit < 1 or args.limit > 25:
            raise SystemExit("--limit must be between 1 and 25")
        selected = selected[:args.limit]

    if args.execute:
        if args.limit is None or not (args.ids or args.priority):
            raise SystemExit("--execute requires --limit and either explicit --ids or --priority")
        trusted_by_id = {row["id"]: row for row in thin}
        outcomes = []
        for row in selected:
            try:
                body = fetch_article(row["source_url"])
            except ArticleAcquisitionError as exc:
                outcomes.append({
                    "evidence_id": row["evidence_id"],
                    "outcome": classify_acquisition_failure(exc.category, str(exc)),
                    "failure_category": exc.category,
                    "error": str(exc),
                })
                continue
            artifact = build_reacquired_artifact(trusted_by_id[row["evidence_id"]], body)
            path = inbox_dir / "source_fidelity" / "artifacts" / f"{row['evidence_id']}.json"
            outcomes.append({
                "evidence_id": row["evidence_id"],
                "classification": artifact["reacquisition_classification"]["outcome"],
                "outcome": write_recovery_artifact(path, artifact),
                "review": "pending SOURCE_FIDELITY_REVIEW",
            })
        print(json.dumps(outcomes, indent=2, ensure_ascii=False))
        return 0

    output = {**{key: value for key, value in report.items() if key != "items"}, "selected": selected}
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("SELECTIVE SOURCE REACQUISITION — DRY RUN")
        print(f"Thin trusted Evidence: {len(thin)}")
        print(f"Priority counts: {report['counts']}")
        print(f"Realistic high-priority (HIGH + publisher URL likely available): {report['realistic_high_priority']}")
        print(f"Realistic by berry: {report['realistic_high_priority_by_berry']}")
        print(f"Selected: {len(selected)}")
        print("No network acquisition, trusted Evidence, review decision, or extraction state changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
