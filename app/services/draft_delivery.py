"""Additive, conflict-aware delivery of untrusted drafts between runtimes.

This module never publishes, rejects, or mutates review_state. An existing
destination draft is never overwritten. Trusted records are never reverted
to drafts. Operators must name source and destination identities explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

NEW_DRAFT = "NEW_DRAFT"
ALREADY_PRESENT_IDENTICAL = "ALREADY_PRESENT_IDENTICAL"
CONFLICT_DIFFERENT_CONTENT = "CONFLICT_DIFFERENT_CONTENT"
SKIP_ALREADY_TRUSTED = "SKIP_ALREADY_TRUSTED"
SKIP_TEST_ARTIFACT = "SKIP_TEST_ARTIFACT"
SKIP_NOT_OPERATIONAL = "SKIP_NOT_OPERATIONAL"
SKIP_FILTERED = "SKIP_FILTERED"
SKIP_INVALID = "SKIP_INVALID"

ANALYST_OWNED_KEYS = frozenset(
    {
        "review_state",
        "status",
        "reviewed_by",
        "reviewed_at",
        "reviewer",
        "rejection_reason",
        "rejection_category",
        "review_notes",
        "analyst_notes",
        "triage_bucket",
        "reading_state",
        "priority",
    }
)

TEST_SUBMITTERS = frozenset({"pytest", "fixture", "test-harness", "local-test"})
TEST_ID_PREFIXES = ("ev-test-", "draft-test-", "fixture-")
SENSITIVE_LOG_KEYS = frozenset(
    {
        "article",
        "paragraphs",
        "summary",
        "publisher_description",
        "why_it_matters",
        "transcript",
        "transcript_excerpt",
        "ai_enrichment",
    }
)


class DraftDeliveryError(ValueError):
    """Operator or identity error that must fail closed."""


@dataclass
class DraftDecision:
    draft_id: str
    outcome: str
    source_hash: str = ""
    destination_hash: str = ""
    reason: str = ""
    written: bool = False


@dataclass
class DeliveryReport:
    source_identity: str
    destination_identity: str
    source_inbox: str
    destination_inbox: str
    dry_run: bool
    generated_at: str
    decisions: list[DraftDecision] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        tallies: dict[str, int] = {}
        for row in self.decisions:
            tallies[row.outcome] = tallies.get(row.outcome, 0) + 1
        tallies["TOTAL"] = len(self.decisions)
        return tallies

    def added_ids(self) -> list[str]:
        return [row.draft_id for row in self.decisions if row.outcome == NEW_DRAFT and row.written]

    def conflict_ids(self) -> list[str]:
        return [row.draft_id for row in self.decisions if row.outcome == CONFLICT_DIFFERENT_CONTENT]

    def skipped_ids(self) -> list[str]:
        skip = {
            SKIP_ALREADY_TRUSTED,
            SKIP_TEST_ARTIFACT,
            SKIP_NOT_OPERATIONAL,
            SKIP_FILTERED,
            SKIP_INVALID,
        }
        return [row.draft_id for row in self.decisions if row.outcome in skip]

    def public_dict(self) -> dict[str, Any]:
        return {
            "source_identity": self.source_identity,
            "destination_identity": self.destination_identity,
            "source_inbox": self.source_inbox,
            "destination_inbox": self.destination_inbox,
            "dry_run": self.dry_run,
            "generated_at": self.generated_at,
            "counts": self.counts(),
            "added_ids": self.added_ids(),
            "skipped_ids": self.skipped_ids(),
            "conflict_ids": self.conflict_ids(),
            "decisions": [
                {
                    "draft_id": row.draft_id,
                    "outcome": row.outcome,
                    "source_hash": row.source_hash,
                    "destination_hash": row.destination_hash,
                    "reason": row.reason,
                    "written": row.written,
                }
                for row in self.decisions
            ],
        }


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payload_hash(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items() if key not in ANALYST_OWNED_KEYS}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_dir(inbox: Path) -> Path:
    return inbox / "evidence"


def trusted_evidence_paths(data_dir: Path | None) -> dict[str, Path]:
    if data_dir is None or not data_dir.is_dir():
        return {}
    found: dict[str, Path] = {}
    for path in data_dir.joinpath("evidence").glob("*.json"):
        found[path.stem] = path
    return found


def trusted_source_urls(data_dir: Path | None) -> set[str]:
    urls: set[str] = set()
    for path in trusted_evidence_paths(data_dir).values():
        try:
            record = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        url = str(record.get("source_url") or "").strip()
        if url:
            urls.add(url)
    return urls


def is_test_artifact(record: dict[str, Any]) -> bool:
    draft_id = str(record.get("id") or "")
    if draft_id.startswith(TEST_ID_PREFIXES):
        return True
    submitter = str(record.get("submitted_by") or "").strip().casefold()
    if submitter in TEST_SUBMITTERS:
        return True
    return bool(record.get("draft_delivery_exclude"))


def assert_identities_match(destination_identity: str, expected_identity: str) -> None:
    dest = destination_identity.strip()
    expected = expected_identity.strip()
    if not dest or not expected:
        raise DraftDeliveryError("destination identity and expected identity are required")
    if dest != expected:
        raise DraftDeliveryError(
            f"destination identity {dest!r} does not match expected {expected!r}"
        )


def assert_production_allowed(destination_identity: str) -> None:
    allowed = os.environ.get("BIOS_DRAFT_DELIVERY_ALLOWED_DESTINATIONS", "").strip()
    if destination_identity == "local-test":
        return
    if destination_identity.startswith("production") or destination_identity.endswith("-vps"):
        if not allowed:
            raise DraftDeliveryError(
                "production destinations require BIOS_DRAFT_DELIVERY_ALLOWED_DESTINATIONS "
                "to contain the destination identity"
            )
        permitted = {item.strip() for item in allowed.split(",") if item.strip()}
        if destination_identity not in permitted:
            raise DraftDeliveryError(
                f"destination {destination_identity!r} is not in BIOS_DRAFT_DELIVERY_ALLOWED_DESTINATIONS"
            )


def referenced_artifacts(record: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("transcript_path", "normalized_transcript_path", "artifact_path"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())
    locator = record.get("artifact_locator")
    if isinstance(locator, dict):
        for key in ("transcript_path", "path"):
            value = locator.get(key)
            if isinstance(value, str) and value.strip():
                refs.append(value.strip())
    transcript = record.get("transcript")
    if isinstance(transcript, dict):
        value = transcript.get("path")
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())
    return refs


def _safe_relative(path_text: str) -> Path | None:
    cleaned = path_text.replace("\\", "/").lstrip("/")
    if cleaned.startswith("inbox/"):
        cleaned = cleaned[len("inbox/") :]
    candidate = Path(cleaned)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate


def copy_referenced_artifacts(record: dict[str, Any], source_inbox: Path, dest_inbox: Path, *, dry_run: bool) -> None:
    for ref in referenced_artifacts(record):
        relative = _safe_relative(ref)
        if relative is None:
            continue
        source_path = source_inbox / relative
        dest_path = dest_inbox / relative
        if not source_path.is_file():
            continue
        if dest_path.exists():
            continue
        if dry_run:
            continue
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(source_path.read_bytes())


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        os.write(fd, encoded.encode("utf-8"))
        os.close(fd)
        tmp_path.replace(path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def classify_draft(
    record: dict[str, Any],
    *,
    source_path: Path,
    dest_path: Path,
    trusted_ids: set[str],
    trusted_urls: set[str],
    exclude_tests: bool,
    selected_ids: set[str] | None,
) -> DraftDecision:
    draft_id = str(record.get("id") or source_path.stem)
    source_hash = file_sha256(source_path)
    if selected_ids is not None and draft_id not in selected_ids:
        return DraftDecision(draft_id, SKIP_FILTERED, source_hash=source_hash, reason="not in --ids")
    if exclude_tests and is_test_artifact(record):
        return DraftDecision(draft_id, SKIP_TEST_ARTIFACT, source_hash=source_hash, reason="test/pilot artifact")
    source_url = str(record.get("source_url") or "").strip()
    if draft_id in trusted_ids or (source_url and source_url in trusted_urls):
        return DraftDecision(
            draft_id,
            SKIP_ALREADY_TRUSTED,
            source_hash=source_hash,
            reason="matching trusted evidence already exists at destination",
        )
    status = str(record.get("status") or "draft")
    review_state = str(record.get("review_state") or "")
    if status == "published" or review_state == "published":
        return DraftDecision(
            draft_id,
            SKIP_NOT_OPERATIONAL,
            source_hash=source_hash,
            reason="source record is already published; delivery moves untrusted drafts only",
        )
    if dest_path.exists():
        dest_hash = file_sha256(dest_path)
        dest_record = load_json(dest_path)
        if dest_hash == source_hash or payload_hash(dest_record) == payload_hash(record):
            return DraftDecision(
                draft_id,
                ALREADY_PRESENT_IDENTICAL,
                source_hash=source_hash,
                destination_hash=dest_hash,
                reason="destination already has identical payload",
            )
        return DraftDecision(
            draft_id,
            CONFLICT_DIFFERENT_CONTENT,
            source_hash=source_hash,
            destination_hash=dest_hash,
            reason="destination draft exists with different content; production wins",
        )
    return DraftDecision(draft_id, NEW_DRAFT, source_hash=source_hash, reason="missing at destination")


def deliver_drafts(
    *,
    source_inbox: Path,
    destination_inbox: Path,
    source_identity: str,
    destination_identity: str,
    expected_identity: str,
    destination_data: Path | None = None,
    dry_run: bool = True,
    apply: bool = False,
    exclude_tests: bool = True,
    selected_ids: set[str] | None = None,
    write_audit: bool = True,
) -> DeliveryReport:
    if apply and dry_run:
        raise DraftDeliveryError("apply and dry-run cannot both be true")
    if not apply:
        dry_run = True
    assert_identities_match(destination_identity, expected_identity)
    assert_production_allowed(destination_identity)
    source_evidence = evidence_dir(source_inbox)
    dest_evidence = evidence_dir(destination_inbox)
    if not source_evidence.is_dir():
        raise DraftDeliveryError(f"source evidence directory missing: {source_evidence}")
    trusted_map = trusted_evidence_paths(destination_data)
    trusted_urls = trusted_source_urls(destination_data)
    decisions: list[DraftDecision] = []
    for source_path in sorted(source_evidence.glob("*.json")):
        try:
            record = load_json(source_path)
        except (OSError, json.JSONDecodeError) as exc:
            decisions.append(
                DraftDecision(source_path.stem, SKIP_INVALID, reason=f"unreadable source: {exc}")
            )
            continue
        dest_path = dest_evidence / source_path.name
        decision = classify_draft(
            record,
            source_path=source_path,
            dest_path=dest_path,
            trusted_ids=set(trusted_map),
            trusted_urls=trusted_urls,
            exclude_tests=exclude_tests,
            selected_ids=selected_ids,
        )
        if decision.outcome == NEW_DRAFT and apply and not dry_run:
            dest_evidence.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(source_path.read_bytes())
            copy_referenced_artifacts(record, source_inbox, destination_inbox, dry_run=False)
            decision.written = True
            decision.destination_hash = file_sha256(dest_path)
        elif decision.outcome == NEW_DRAFT:
            copy_referenced_artifacts(record, source_inbox, destination_inbox, dry_run=True)
        decisions.append(decision)
    report = DeliveryReport(
        source_identity=source_identity,
        destination_identity=destination_identity,
        source_inbox=str(source_inbox),
        destination_inbox=str(destination_inbox),
        dry_run=dry_run,
        generated_at=utc_now(),
        decisions=decisions,
    )
    if write_audit and apply and not dry_run:
        write_audit_report(destination_inbox, report)
    return report


def write_audit_report(destination_inbox: Path, report: DeliveryReport) -> Path:
    stamp = re.sub(r"[^0-9T]", "", report.generated_at)[:15]
    directory = destination_inbox / "operations" / "draft-deliveries"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"delivery-{stamp}.json"
    payload = report.public_dict()
    text = json.dumps(payload, indent=2, sort_keys=True)
    for banned in SENSITIVE_LOG_KEYS:
        if f'"{banned}"' in text and banned in {
            "article",
            "paragraphs",
            "summary",
            "publisher_description",
            "transcript",
        }:
            raise DraftDeliveryError("audit payload leaked a source-body field")
    path.write_text(text + "\n", encoding="utf-8")
    latest = directory / "latest.json"
    latest.write_text(text + "\n", encoding="utf-8")
    return path


def inventory(inbox: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    folder = evidence_dir(inbox)
    if not folder.is_dir():
        return rows
    for path in folder.glob("*.json"):
        rows[path.stem] = file_sha256(path)
    return rows


def compare_inventories(local: dict[str, str], production: dict[str, str]) -> dict[str, Any]:
    local_ids = set(local)
    prod_ids = set(production)
    both = local_ids & prod_ids
    identical = sorted(draft_id for draft_id in both if local[draft_id] == production[draft_id])
    conflicting = sorted(draft_id for draft_id in both if local[draft_id] != production[draft_id])
    return {
        "local_total": len(local_ids),
        "production_total": len(prod_ids),
        "both": len(both),
        "only_local": sorted(local_ids - prod_ids),
        "only_production": sorted(prod_ids - local_ids),
        "identical": identical,
        "conflicts": conflicting,
    }


def format_summary(report: DeliveryReport) -> str:
    counts = report.counts()
    skipped = sum(
        counts.get(key, 0)
        for key in (
            SKIP_ALREADY_TRUSTED,
            SKIP_TEST_ARTIFACT,
            SKIP_NOT_OPERATIONAL,
            SKIP_FILTERED,
            SKIP_INVALID,
        )
    )
    lines = [
        f"SOURCE {report.source_identity}",
        f"DESTINATION {report.destination_identity}",
        f"DRY RUN {str(report.dry_run).lower()}",
        f"NEW {counts.get(NEW_DRAFT, 0)}",
        f"IDENTICAL {counts.get(ALREADY_PRESENT_IDENTICAL, 0)}",
        f"CONFLICT {counts.get(CONFLICT_DIFFERENT_CONTENT, 0)}",
        f"SKIPPED {skipped}",
        f"TOTAL {counts.get('TOTAL', 0)}",
    ]
    return "\n".join(lines)
