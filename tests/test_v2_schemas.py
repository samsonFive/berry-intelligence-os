"""Schema-level tests for the V2 Phase 1 schema-foundation work
(docs/v2/10-BACKLOG.md BL-010 through BL-015). Pure JSON Schema
validation -- no app.main import, no route/template involvement, no
PostgreSQL. Mirrors scripts/validate_records.py's own approach
(Draft202012Validator + FormatChecker) rather than introducing a new
validation mechanism."""
from __future__ import annotations

import glob
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def _validator(schema_name: str) -> Draft202012Validator:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _is_valid(validator: Draft202012Validator, record: dict) -> bool:
    return not list(validator.iter_errors(record))


# ---------------------------------------------------------------------------
# BL-010: assessment.schema.json
# ---------------------------------------------------------------------------

VALID_ASSESSMENT = {
    "id": "assessment-hortifrut-genetics-consolidation",
    "record_type": "assessment",
    "title": "Hortifrut's blueberry IP is consolidating under Berry Blue, LLC",
    "rationale": (
        "Two independent facts -- the Atlantic Blue acquisition and the Berry "
        "Blue, LLC filings -- point the same direction: Hortifrut is centralizing "
        "genetics ownership under a single subsidiary rather than holding IP "
        "directly."
    ),
    "status": "active",
    "confidence": "medium",
    "fact_ids": ["fact-hortifrut-acquires-atlantic-blue", "fact-berry-blue-llc-holds-ip"],
    "evidence_ids": ["ev-hortifrut-genetic-development"],
    "entity_ids": ["company-hortifrut", "company-berry-blue-llc"],
    "reviewer": "analyst-1",
    "created_at": "2026-08-14",
}


def test_assessment_valid_example_passes() -> None:
    validator = _validator("assessment.schema.json")
    errors = list(validator.iter_errors(VALID_ASSESSMENT))
    assert errors == [], [e.message for e in errors]


def test_assessment_invalid_example_fails_without_supporting_facts() -> None:
    # BL-010: "at least one supporting Fact reference" is structurally
    # required -- an Assessment with zero fact_ids is not a valid Assessment.
    validator = _validator("assessment.schema.json")
    invalid = {**VALID_ASSESSMENT, "fact_ids": []}
    assert not _is_valid(validator, invalid)

    missing_entirely = {k: v for k, v in VALID_ASSESSMENT.items() if k != "fact_ids"}
    assert not _is_valid(validator, missing_entirely)


# ---------------------------------------------------------------------------
# BL-011: recommendation.schema.json
# ---------------------------------------------------------------------------

VALID_RECOMMENDATION = {
    "id": "recommendation-monitor-berry-blue-llc-filings",
    "record_type": "recommendation",
    "title": "Monitor Berry Blue, LLC's future IP filings",
    "rationale": (
        "If genetics consolidation under Berry Blue, LLC is real, future patent "
        "and PBR filings should increasingly list it as assignee rather than "
        "Hortifrut S.A. directly -- worth a standing watch."
    ),
    "action_type": "monitor_for_confirmation",
    "status": "active",
    "priority": "medium",
    "assessment_ids": ["assessment-hortifrut-genetics-consolidation"],
    "entity_ids": ["company-hortifrut", "company-berry-blue-llc"],
    "reviewer": "analyst-1",
    "created_at": "2026-08-14",
}


def test_recommendation_valid_example_passes() -> None:
    validator = _validator("recommendation.schema.json")
    errors = list(validator.iter_errors(VALID_RECOMMENDATION))
    assert errors == [], [e.message for e in errors]


def test_recommendation_invalid_example_fails_without_assessment_or_signal() -> None:
    # BL-011: "at least one Assessment or Signal reference" -- a
    # Recommendation is never a shortcut straight from bare evidence.
    validator = _validator("recommendation.schema.json")
    invalid = {k: v for k, v in VALID_RECOMMENDATION.items() if k != "assessment_ids"}
    assert not _is_valid(validator, invalid)

    empty_lineage = {**invalid, "assessment_ids": [], "signal_ids": []}
    assert not _is_valid(validator, empty_lineage)


def test_recommendation_action_type_is_not_constrained_to_an_enum() -> None:
    # D-007 / core design principle #7: recommendation vocabularies are
    # domain-specific and must not be hard-coded into the core schema.
    validator = _validator("recommendation.schema.json")
    record = {**VALID_RECOMMENDATION, "action_type": "some_future_domain_specific_action"}
    assert _is_valid(validator, record)


def test_recommendation_priority_is_not_evidence_priority_shape() -> None:
    # D-011: Recommendation must not duplicate evidence.priority's
    # four-dimension structure -- it's a single scalar on the recommendation
    # itself, answering a different question.
    schema = json.loads((ROOT / "schemas" / "recommendation.schema.json").read_text(encoding="utf-8"))
    priority_schema = schema["properties"]["priority"]
    # A flat enum, not evidence.priority's nested {reading: {level, rationale}, ...}
    # object structure -- checked structurally, not by searching prose comments.
    assert priority_schema.get("enum") == ["low", "medium", "high"]
    assert priority_schema.get("type") != "object"
    assert "properties" not in priority_schema


# ---------------------------------------------------------------------------
# BL-014: signal.schema.json, validated against the six staged blueberry
# proposed signals (not imported into live data by this task).
# ---------------------------------------------------------------------------

STAGED_SIGNALS_DIR = ROOT / "data" / "imports" / "blueberry-public-pilot-2026-08-03" / "signals"


def test_staged_blueberry_signals_validate_against_refined_schema() -> None:
    validator = _validator("signal.schema.json")
    files = sorted(glob.glob(str(STAGED_SIGNALS_DIR / "*.json")))
    assert len(files) == 6, f"expected 6 staged signals, found {len(files)}"
    failures = {}
    for path in files:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(record))
        if errors:
            failures[record["id"]] = [e.message for e in errors]
    assert failures == {}


def test_signal_evidence_ids_now_requires_at_least_two() -> None:
    validator = _validator("signal.schema.json")
    base = {
        "id": "sig-single-source-pattern",
        "record_type": "signal",
        "title": "A signal built on one data point",
        "status": "proposed",
        "strength": "weak",
        "reviewer": None,
        "evidence_ids": ["ev-only-one"],
    }
    assert not _is_valid(validator, base)
    assert _is_valid(validator, {**base, "evidence_ids": ["ev-one", "ev-two"]})


# ---------------------------------------------------------------------------
# BL-012/BL-013/BL-015: extended fields are optional/additive -- a
# minimal pre-existing-shape record (no new fields set) must still validate.
# ---------------------------------------------------------------------------

def test_evidence_extended_fields_are_optional() -> None:
    validator = _validator("evidence.schema.json")
    minimal_v1_shape = {
        "id": "ev-minimal-v1-shape",
        "record_type": "evidence",
        "status": "published",
        "source_type": "article",
        "title": "A minimal, pre-V2 evidence record",
        "captured_date": "2026-08-14",
        "summary": "Summary.",
        "submitted_by": "analyst-1",
        "priority": {
            "reading": {"level": "none", "rationale": ""},
            "testing": {"level": "none", "rationale": ""},
            "commercial_position": {"level": "none", "rationale": ""},
            "monitoring": {"level": "none", "rationale": ""},
        },
    }
    assert _is_valid(validator, minimal_v1_shape)


def test_relationship_confidence_is_optional_and_notes_still_allowed() -> None:
    validator = _validator("relationship.schema.json")
    without_confidence = {
        "id": "rel-minimal-v1-shape",
        "record_type": "relationship",
        "subject_id": "company-a",
        "predicate": "owns",
        "object_id": "brand-b",
        "status": "active",
        "evidence_ids": ["ev-x"],
        "notes": "confidence=medium; free-text style from before this field existed.",
    }
    assert _is_valid(validator, without_confidence)

    with_confidence = {**without_confidence, "confidence": "medium"}
    assert _is_valid(validator, with_confidence)

    bad_confidence = {**without_confidence, "confidence": "certain"}
    assert not _is_valid(validator, bad_confidence)


def test_strategic_question_status_enum_tightened() -> None:
    validator = _validator("strategic-question.schema.json")
    base = {
        "id": "sq-minimal-v1-shape",
        "record_type": "strategic_question",
        "title": "A minimal strategic question",
    }
    assert _is_valid(validator, {**base, "status": "active"})
    assert _is_valid(validator, {**base, "status": "answered"})
    assert _is_valid(validator, {**base, "status": "retired"})
    # The old V1 enum values are no longer valid.
    assert not _is_valid(validator, {**base, "status": "resolved"})
    assert not _is_valid(validator, {**base, "status": "archived"})


# ---------------------------------------------------------------------------
# D-012 (docs/v2/08-DECISION-LOG.md), V2 Phase 2A: explicit analytical scope
# (domain_ids/market_ids/geography_ids on Assessment/Recommendation,
# domain_ids/geography_ids/berry_ids on Signal) is optional and additive --
# every legacy record without these fields must keep validating unchanged,
# and a record that does set them must validate too.
# ---------------------------------------------------------------------------

def test_assessment_scope_fields_are_optional_not_required() -> None:
    validator = _validator("assessment.schema.json")
    # VALID_ASSESSMENT (above) sets none of domain_ids/market_ids/geography_ids
    # and must still validate -- this is the legacy-record case.
    assert _is_valid(validator, VALID_ASSESSMENT)


def test_assessment_scope_fields_validate_when_present_including_cross_market() -> None:
    validator = _validator("assessment.schema.json")
    scoped = {
        **VALID_ASSESSMENT,
        "domain_ids": ["domain-berries"],
        "market_ids": ["berry-blueberry", "berry-raspberry"],
        "geography_ids": ["geography-south-africa"],
    }
    assert _is_valid(validator, scoped)


def test_recommendation_scope_fields_are_optional_and_validate_when_present() -> None:
    validator = _validator("recommendation.schema.json")
    assert _is_valid(validator, VALID_RECOMMENDATION)
    scoped = {
        **VALID_RECOMMENDATION,
        "domain_ids": ["domain-berries"],
        "market_ids": ["berry-blueberry"],
        "geography_ids": [],
    }
    assert _is_valid(validator, scoped)


def test_signal_scope_fields_are_optional_and_validate_when_present() -> None:
    validator = _validator("signal.schema.json")
    base = {
        "id": "sig-scope-test",
        "record_type": "signal",
        "title": "A signal used only to test scope fields",
        "status": "proposed",
        "strength": "weak",
        "reviewer": None,
        "evidence_ids": ["ev-one", "ev-two"],
    }
    assert _is_valid(validator, base)
    scoped = {**base, "berry_ids": ["berry-blueberry"], "domain_ids": ["domain-berries"], "geography_ids": ["geography-morocco"]}
    assert _is_valid(validator, scoped)


def test_all_six_staged_signals_still_validate_with_scope_fields_declared() -> None:
    # Re-verifies BL-014's own staged-signal fixture (which sets berry_ids,
    # previously an undeclared-but-accepted property) now validates against
    # the field being formally declared, not just tolerated.
    validator = _validator("signal.schema.json")
    files = sorted(glob.glob(str(STAGED_SIGNALS_DIR / "*.json")))
    for path in files:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        assert record.get("berry_ids"), f"{record['id']}: expected fixture to already set berry_ids"
        errors = list(validator.iter_errors(record))
        assert errors == [], (record["id"], [e.message for e in errors])
