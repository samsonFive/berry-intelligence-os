"""Plan selective historic source reacquisition; network execution is explicit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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
from app.services.pipeline_lock import pipeline_lock
from app.services.source_fidelity_recovery import trusted_identity_sha256
from app.services.source_reacquisition import (
    build_inventory, build_reacquired_artifact, classify_acquisition_failure,
    pilot_manifest, preflight_reacquisition_url, stage_reacquired_artifact,
    write_pilot_audit,
)


_EXECUTION_LOCK_HELD = False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--inbox-dir", type=Path)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--priority", choices=("high", "medium", "low"))
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--manifest", action="store_true", help="Write private body-free pilot-10 and pilot-25 manifests")
    parser.add_argument("--pilot-manifest", type=Path, help="Execute the exact existing body-free pilot manifest")
    parser.add_argument("--canonical", help="Canonical commit recorded in the private execution audit")
    parser.add_argument("--execute", action="store_true", help="Explicitly allow bounded network acquisition")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    global _EXECUTION_LOCK_HELD
    args = _parser().parse_args(argv)
    data_dir = args.data_dir or resolve_data_dir(ROOT)
    inbox_dir = args.inbox_dir or resolve_inbox_dir(ROOT)
    if args.execute and not _EXECUTION_LOCK_HELD:
        with pipeline_lock(inbox_dir, "source-reacquisition"):
            _EXECUTION_LOCK_HELD = True
            try:
                return main(argv)
            finally:
                _EXECUTION_LOCK_HELD = False
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
    manifest_sha256 = None
    manifest_name = None
    if args.pilot_manifest:
        raw_manifest = args.pilot_manifest.read_bytes()
        execution_manifest = json.loads(raw_manifest)
        manifest_name = execution_manifest.get("manifest")
        entries = execution_manifest.get("entries")
        if manifest_name != "REACQUISITION-PILOT-10" or not isinstance(entries, list) or not 1 <= len(entries) <= 10:
            raise SystemExit("--pilot-manifest must be the bounded REACQUISITION-PILOT-10 manifest")
        manifest_ids = [str(entry.get("evidence_id") or "") for entry in entries]
        if len(set(manifest_ids)) != len(manifest_ids):
            raise SystemExit("pilot manifest contains duplicate Evidence ids")
        manifest_sha256 = hashlib.sha256(raw_manifest).hexdigest()
        current_by_id = {row["evidence_id"]: row for row in report["items"]}
        selected = []
        for entry in entries:
            evidence_id = str(entry.get("evidence_id") or "")
            current = current_by_id.get(evidence_id)
            if current is None:
                raise SystemExit(f"manifest Evidence is no longer a thin trusted record: {evidence_id}")
            if current.get("source_url") != entry.get("source_url"):
                raise SystemExit(f"manifest source URL changed for {evidence_id}; regenerate and report the difference")
            selected.append(current)
    if args.priority and not args.pilot_manifest:
        selected = [row for row in selected if row["priority"] == args.priority.upper()]
    if args.ids and not args.pilot_manifest:
        wanted = set(args.ids)
        selected = [row for row in selected if row["evidence_id"] in wanted]
        missing = wanted - {row["evidence_id"] for row in selected}
        if missing:
            raise SystemExit("unknown, non-thin, or priority-filtered Evidence ids: " + ", ".join(sorted(missing)))
    if args.limit is not None and not args.pilot_manifest:
        if args.limit < 1 or args.limit > 25:
            raise SystemExit("--limit must be between 1 and 25")
        selected = selected[:args.limit]

    if args.execute:
        if args.pilot_manifest:
            if not args.canonical:
                raise SystemExit("--execute with --pilot-manifest requires --canonical for the audit record")
        elif args.limit is None or not (args.ids or args.priority):
            raise SystemExit("--execute requires --pilot-manifest or --limit and either explicit --ids or --priority")
        trusted_by_id = {row["id"]: row for row in thin}
        started_at = datetime.now(timezone.utc)
        trusted_before = hashlib.sha256(json.dumps(
            [trusted_by_id[row["evidence_id"]] for row in selected],
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        ready_before = {
            row["id"] for row in readiness["items"] if row["readiness"] != "THIN_DESCRIPTION_ONLY"
        }
        outcomes = []
        seen_urls: set[str] = set()
        for row in selected:
            evidence_id = row["evidence_id"]
            artifact_path = inbox_dir / "source_fidelity" / "artifacts" / f"{evidence_id}.json"
            if artifact_path.exists():
                existing = json.loads(artifact_path.read_text(encoding="utf-8"))
                review_status = (existing.get("review") or {}).get("status")
                identity_matches = (
                    existing.get("evidence_id") == evidence_id
                    and existing.get("trusted_identity_sha256") == trusted_identity_sha256(trusted_by_id[evidence_id])
                    and existing.get("source_url") == row["source_url"]
                )
                outcomes.append({
                    "evidence_id": evidence_id,
                    "requested_url": row["source_url"],
                    "final_url": existing.get("final_url"),
                    "outcome": (
                        "AMBIGUOUS" if not identity_matches
                        else "ALREADY_AFFIRMED" if review_status == "affirmed"
                        else "ALREADY_STAGED"
                    ),
                    "staging": "conflict" if not identity_matches else "unchanged",
                    "artifact_id": existing.get("source_artifact_id"),
                    "artifact_path": str(artifact_path),
                    "review": review_status,
                    "body_sha256": existing.get("body_sha256"),
                })
                continue
            normalized_url = str(row["source_url"]).strip().casefold().rstrip("/")
            if normalized_url in seen_urls:
                outcomes.append({
                    "evidence_id": evidence_id,
                    "requested_url": row["source_url"],
                    "final_url": None,
                    "outcome": "KNOWN_DUPLICATE",
                    "failure_category": "preflight",
                    "error": "the selected URL duplicates an earlier pilot candidate",
                })
                continue
            seen_urls.add(normalized_url)
            safe, preflight_outcome = preflight_reacquisition_url(row["source_url"])
            if not safe:
                outcomes.append({
                    "evidence_id": evidence_id,
                    "requested_url": row["source_url"],
                    "final_url": None,
                    "outcome": preflight_outcome,
                    "failure_category": "preflight",
                    "error": "deterministic URL preflight rejected the candidate",
                })
                continue
            try:
                body = fetch_article(row["source_url"])
            except ArticleAcquisitionError as exc:
                outcomes.append({
                    "evidence_id": evidence_id,
                    "requested_url": row["source_url"],
                    "final_url": None,
                    "outcome": classify_acquisition_failure(exc.category, str(exc)),
                    "failure_category": exc.category,
                    "error": str(exc),
                })
                continue
            artifact = build_reacquired_artifact(trusted_by_id[evidence_id], body)
            try:
                staging = stage_reacquired_artifact(artifact_path, artifact)
            except ValueError as exc:
                outcomes.append({
                    "evidence_id": evidence_id,
                    "requested_url": row["source_url"],
                    "final_url": body.final_url or body.source_url,
                    "outcome": "AMBIGUOUS",
                    "failure_category": "artifact_conflict",
                    "error": str(exc),
                })
                continue
            article = artifact["artifact"]["article"]
            outcomes.append({
                "evidence_id": evidence_id,
                "requested_url": row["source_url"],
                "final_url": artifact.get("final_url") or artifact.get("source_url"),
                "outcome": artifact["reacquisition_classification"]["outcome"],
                "identity_comparison": artifact["reacquisition_classification"],
                "staging": staging,
                "artifact_id": artifact["source_artifact_id"],
                "artifact_path": str(artifact_path),
                "review": "pending",
                "paragraph_count": len(article.get("paragraphs") or []),
                "word_count": article.get("word_count"),
                "source_chars": artifact.get("source_chars"),
                "body_sha256": artifact.get("body_sha256"),
                "author_present": bool(artifact.get("author")),
                "publication_date_present": bool(artifact.get("published_date")),
                "language_present": bool(artifact.get("language")),
                "stable_paragraph_indexes": [
                    paragraph.get("index") for paragraph in article.get("paragraphs") or []
                ] == list(range(len(article.get("paragraphs") or []))),
            })
        current_trusted = {row["id"]: row for row in repos.evidence.list(status="published")}
        trusted_after = hashlib.sha256(json.dumps(
            [current_trusted[row["evidence_id"]] for row in selected],
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        ready_after_report = readiness_inventory(list(current_trusted.values()))
        ready_after = {
            row["id"] for row in ready_after_report["items"] if row["readiness"] != "THIN_DESCRIPTION_ONLY"
        }
        ended_at = datetime.now(timezone.utc)
        audit = {
            "contract_version": "bounded-historical-reacquisition-pilot-v1",
            "manifest": manifest_name,
            "manifest_sha256": manifest_sha256,
            "canonical": args.canonical,
            "started_at": started_at.isoformat(timespec="seconds"),
            "ended_at": ended_at.isoformat(timespec="seconds"),
            "attempted_count": len(selected),
            "evidence_ids": [row["evidence_id"] for row in selected],
            "outcomes": outcomes,
            "assertions": {
                "trusted_evidence_mutated": trusted_before != trusted_after,
                "trusted_evidence_sha256_before": trusted_before,
                "trusted_evidence_sha256_after": trusted_after,
                "new_extraction_ready_ids": sorted(ready_after - ready_before),
                "analyst_decisions_created": 0,
                "artifacts_private": True,
            },
        }
        audit_folder = inbox_dir / "operations" / "source-reacquisition" / "runs"
        audit_folder.mkdir(parents=True, exist_ok=True)
        stamp = ended_at.strftime("%Y%m%dT%H%M%S%fZ")
        audit_path = write_pilot_audit(audit_folder, audit, stamp=stamp)
        print(json.dumps({"audit_path": str(audit_path), **audit}, indent=2, ensure_ascii=False))
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
