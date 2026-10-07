"""Score curated variety-name recall fixtures through existing discovery, offline.

This is a diagnostic, not extraction qualification or a global coverage estimate.
It never reads operator inboxes, acquires pages, or changes catalog/review state.
Unsupported formats stay in the denominator rather than being silently skipped.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.variety_universe.corpus_discovery import discover_corpus_variety_mentions
from app.services.variety_universe.identity import fold_identity

DEFAULT_FIXTURE = ROOT / "benchmarks" / "variety-name-recall-v1.json"


def score_case(case: dict, *, discover=discover_corpus_variety_mentions) -> dict:
    """Score names separately from species, codes, resolution and provenance."""
    inputs = deepcopy(case["inputs"])
    report = discover(
        varieties=inputs.get("varieties", []), entities=inputs.get("entities", []),
        published_evidence=inputs.get("evidence", []), facts=inputs.get("facts", []),
        existing_candidates=inputs.get("candidates", []),
    )
    observed = report["mentions"]
    by_name: dict[str, list[dict]] = {}
    for row in observed:
        by_name.setdefault(fold_identity(row["candidate_name"]), []).append(row)
    expected = case["expected"]
    expected_names = {fold_identity(row["name"]) for row in expected}
    checks = []
    extra_berry_assignments = []
    for row in expected:
        matches = by_name.get(fold_identity(row["name"]), [])
        compatible = [m for m in matches if m.get("berry_id", "") == row["berry_id"]]
        if compatible:
            extra_berry_assignments.extend(m for m in matches if m.get("berry_id", "") != row["berry_id"])
        found = compatible[0] if compatible else matches[0] if matches else None
        errors = []
        if found is None:
            errors.append("name_missing")
        else:
            if not compatible:
                errors.append("wrong_berry")
            if "breeder_code" in row and fold_identity(found.get("breeder_code")) != fold_identity(row["breeder_code"]):
                errors.append("wrong_or_missing_code")
            if "disposition" in row and found.get("disposition") != row["disposition"]:
                errors.append("wrong_disposition")
            if "canonical_variety_id" in row and found.get("canonical_variety_id") != row["canonical_variety_id"]:
                errors.append("wrong_catalog_link")
            if not set(row.get("evidence_ids", [])).issubset(found.get("evidence_ids", [])):
                errors.append("missing_source_reference")
            if "source_url" in row and found.get("source_url") != row["source_url"]:
                errors.append("changed_or_missing_source_url")
        checks.append({"expected": row, "observed": found, "errors": errors})
    unexpected = [row for row in observed if fold_identity(row["candidate_name"]) not in expected_names]
    required_exclusions = set(case.get("required_exclusion_reasons", []))
    missing_exclusions = sorted(required_exclusions - {row["reason"] for row in report["exclusions"]})
    errors = Counter(error for check in checks for error in check["errors"])
    errors["unexpected_name"] += len(unexpected)
    errors["missing_exclusion"] += len(missing_exclusions)
    errors["unexpected_berry_assignment"] += len(extra_berry_assignments)
    return {
        "id": case["id"], "format": case["format"], "language": case["language"],
        "fixture_kind": case["fixture_kind"], "reference_urls": case.get("reference_urls", []),
        "expected_names": len(expected), "detected_names": sum("name_missing" not in c["errors"] for c in checks),
        "fully_correct_names": sum(not c["errors"] for c in checks),
        "returned_names": len(observed), "unexpected_names": len(unexpected),
        "unresolved_names": sum(m.get("disposition") in {"unresolved", "possible_alias", "berry_mismatch"} for m in observed),
        "errors": dict(sorted((key, value) for key, value in errors.items() if value)),
        "passed": not any(errors.values()), "checks": checks, "unexpected": unexpected,
        "unexpected_berry_assignments": extra_berry_assignments,
        "exclusions": report["exclusions"], "missing_exclusion_reasons": missing_exclusions,
    }


def aggregate(rows: list[dict]) -> dict:
    expected = sum(row["expected_names"] for row in rows)
    detected = sum(row["detected_names"] for row in rows)
    returned = sum(row["returned_names"] for row in rows)
    unexpected = sum(row["unexpected_names"] for row in rows)
    return {
        "cases": len(rows), "cases_passed": sum(row["passed"] for row in rows),
        "expected_name_occurrences": expected, "detected_name_occurrences": detected,
        "missed_name_occurrences": expected - detected,
        "fully_correct_name_occurrences": sum(row["fully_correct_names"] for row in rows),
        "returned_name_occurrences": returned, "unexpected_name_occurrences": unexpected,
        "unresolved_name_occurrences": sum(row["unresolved_names"] for row in rows),
        "name_recall": round(detected / expected, 4) if expected else None,
        # Wrong berry/code/identity is reported separately; this is name precision only.
        "name_precision": round((returned - unexpected) / returned, 4) if returned else None,
        "errors": dict(sorted(sum((Counter(row["errors"]) for row in rows), Counter()).items())),
    }


def audit(fixture_path: Path = DEFAULT_FIXTURE) -> dict:
    raw = fixture_path.read_bytes()
    fixture = json.loads(raw)
    if fixture.get("schema_version") != "variety-name-recall-v1":
        raise ValueError("Unsupported recall fixture version")
    ids = [case["id"] for case in fixture["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Recall case IDs must be unique")
    for case in fixture["cases"]:
        names = [fold_identity(row["name"]) for row in case["expected"]]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate expected names in {case['id']}; split ambiguous-species cases")
    cases = [score_case(case) for case in fixture["cases"]]
    berries = sorted({check["expected"]["berry_id"] for case in cases for check in case["checks"]})
    by_berry = {}
    for berry in berries:
        checks = [check for case in cases for check in case["checks"] if check["expected"]["berry_id"] == berry]
        by_berry[berry] = {
            "expected_name_occurrences": len(checks),
            "detected_name_occurrences": sum("name_missing" not in check["errors"] for check in checks),
            "detected_with_correct_berry": sum(check["observed"] is not None and "wrong_berry" not in check["errors"] for check in checks),
            "fully_correct_name_occurrences": sum(not check["errors"] for check in checks),
        }
    return {
        "schema_version": fixture["schema_version"], "fixture_sha256": hashlib.sha256(raw).hexdigest(),
        "scope": fixture["scope"], "review_status": fixture["review_status"],
        "method": "Existing deterministic corpus discovery only; independent expected lists; offline; no qualification or catalog writes",
        "summary": aggregate(cases),
        "by_format": {value: aggregate([row for row in cases if row["format"] == value]) for value in sorted({row["format"] for row in cases})},
        "by_language": {value: aggregate([row for row in cases if row["language"] == value]) for value in sorted({row["language"] for row in cases})},
        "by_berry": by_berry,
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.fixture)
    output = args.output.resolve()
    # Prevent an explicit output argument from replacing canonical records or gold fixtures.
    if any(output.is_relative_to(ROOT / folder) for folder in ("data", "benchmarks")) or output == args.fixture.resolve():
        parser.error("Write diagnostics under artifacts/ or a separate report directory, never data/ or benchmarks/")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"]))
