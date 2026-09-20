"""Gate 3 evaluation set: support, atomicity, blocked-body honesty."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.feed_first import extract_statements

EVAL_PATH = Path(__file__).parent / "fixtures" / "feed_first_eval_set.json"


def _cases() -> list[dict]:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))


def test_eval_set_covers_required_kinds():
    kinds = {row["kind"] for row in _cases()}
    assert {"press_release", "blocked", "metadata_only"} <= kinds


def test_eval_set_scores_support_and_atomicity():
    failures: list[str] = []
    for case in _cases():
        statements = extract_statements(case["record"])
        expect = case["expect"]
        if not (expect["min_statements"] <= len(statements) <= expect["max_statements"]):
            failures.append(f"{case['id']}: count {len(statements)}")
            continue
        if expect.get("all_have_support"):
            for row in statements:
                if not row.get("supporting_passages") or not row["supporting_passages"][0]:
                    failures.append(f"{case['id']}: missing support")
                if row["statement_text"] not in row["supporting_passages"][0] and row["supporting_passages"][0] not in row["statement_text"]:
                    failures.append(f"{case['id']}: support mismatch")
                if row["original_extraction_text"] != row["supporting_passages"][0] and not row.get("analyst_edit_history"):
                    # original must stay tied to the extracted sentence
                    if row["original_extraction_text"] != row["statement_text"]:
                        failures.append(f"{case['id']}: original drifted")
        if expect.get("require_quantity"):
            if not any((row.get("structured_details") or {}).get("quantities") for row in statements):
                failures.append(f"{case['id']}: missing quantity structure")
    assert failures == []
