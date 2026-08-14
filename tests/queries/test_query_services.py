"""Core query-service tests (V2 Phase 2B.2,
docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 9).

Written entirely against the query-service public methods
(app/queries/*.py), using real, schema-valid fixture records built through
`get_repositories()`/`get_query_services()` (app/composition.py) pointed
at a temporary directory -- never the live 1,882-record dataset. Nothing
here asserts on JSON file layout; a future PostgreSQL-backed repository
set is expected to satisfy these same tests unchanged, same as the
Phase 2B.1 repository contract suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.composition import get_query_services, get_repositories
from app.repositories.paths import SCHEMAS_DIR


# ---------------------------------------------------------------------------
# Minimal, schema-valid record factories (mirrors
# tests/repositories/test_json_repository_contract.py's own factories,
# extended with the linkage/scope fields these query-service tests need).
# ---------------------------------------------------------------------------

def _entity(suffix: str, entity_type: str = "company") -> dict[str, Any]:
    return {
        "id": f"{entity_type}-qs-test-{suffix}",
        "record_type": "entity",
        "entity_type": entity_type,
        "name": f"QS Test {entity_type.title()} {suffix}",
        "status": "active",
    }


def _evidence(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"ev-qs-test-{suffix}",
        "record_type": "evidence",
        "status": "published",
        "source_type": "article",
        "title": f"QS test evidence {suffix}",
        "captured_date": "2026-08-14",
        "published_date": "2026-08-10",
        "summary": "Summary.",
        "submitted_by": "qs-test",
        "entity_ids": [],
        "strategic_question_ids": [],
        "priority": {
            dim: {"level": "none", "rationale": ""}
            for dim in ("reading", "testing", "commercial_position", "monitoring")
        },
    }
    record.update(overrides)
    return record


def _fact(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"fact-qs-test-{suffix}",
        "record_type": "fact",
        "statement": "A test statement.",
        "classification": "fact",
        "confidence": "medium",
        "status": "active",
        "reviewer": "qs-test",
        "created_at": "2026-08-14",
        "evidence_ids": ["ev-x"],
        "entity_ids": [],
    }
    record.update(overrides)
    return record


def _relationship(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"rel-qs-test-{suffix}",
        "record_type": "relationship",
        "subject_id": "company-a",
        "predicate": "owns",
        "object_id": "brand-b",
        "status": "active",
        "evidence_ids": ["ev-x"],
    }
    record.update(overrides)
    return record


def _signal(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"sig-qs-test-{suffix}",
        "record_type": "signal",
        "title": f"QS test signal {suffix}",
        "status": "active",
        "strength": "medium",
        "reviewer": "qs-test",
        "evidence_ids": ["ev-x", "ev-y"],
        "fact_ids": [],
        "entity_ids": [],
        "strategic_question_ids": [],
    }
    record.update(overrides)
    return record


def _assessment(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"assessment-qs-test-{suffix}",
        "record_type": "assessment",
        "title": f"QS test assessment {suffix}",
        "rationale": "Because a test needs one.",
        "status": "active",
        "confidence": "medium",
        "fact_ids": ["fact-x"],
        "evidence_ids": [],
        "entity_ids": [],
        "strategic_question_ids": [],
        "reviewer": "qs-test",
        "created_at": "2026-08-14",
    }
    record.update(overrides)
    return record


def _recommendation(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"recommendation-qs-test-{suffix}",
        "record_type": "recommendation",
        "title": f"QS test recommendation {suffix}",
        "rationale": "Because a test needs one.",
        "action_type": "monitor_for_confirmation",
        "status": "active",
        "assessment_ids": ["assessment-x"],
        "signal_ids": [],
        "fact_ids": [],
        "evidence_ids": [],
        "entity_ids": [],
        "strategic_question_ids": [],
        "reviewer": "qs-test",
        "created_at": "2026-08-14",
    }
    record.update(overrides)
    return record


def _strategic_question(suffix: str, **overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"sq-qs-test-{suffix}",
        "record_type": "strategic_question",
        "title": f"QS test SQ {suffix}",
        "status": "active",
    }
    record.update(overrides)
    return record


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


@pytest.fixture
def queries(tmp_path: Path):
    return get_query_services(tmp_path, SCHEMAS_DIR)


# ---------------------------------------------------------------------------
# ReferenceQueryService -- single-hop reverse references
# ---------------------------------------------------------------------------

def test_facts_for_evidence_returns_only_facts_citing_it(repos, queries) -> None:
    repos.facts.create(_fact("a", evidence_ids=["ev-target"]))
    repos.facts.create(_fact("b", evidence_ids=["ev-other"]))
    result = queries.reference.facts_for_evidence("ev-target")
    assert [f["id"] for f in result] == ["fact-qs-test-a"]


def test_relationships_for_evidence_returns_only_relationships_citing_it(repos, queries) -> None:
    repos.relationships.create(_relationship("a", evidence_ids=["ev-target"]))
    repos.relationships.create(_relationship("b", evidence_ids=["ev-other"]))
    result = queries.reference.relationships_for_evidence("ev-target")
    assert [r["id"] for r in result] == ["rel-qs-test-a"]


def test_evidence_for_strategic_question_excludes_unpublished(repos, queries) -> None:
    repos.evidence.create(_evidence("published", status="published", strategic_question_ids=["sq-1"]))
    repos.evidence.create(_evidence("draft", status="draft", strategic_question_ids=["sq-1"]))
    result = queries.reference.evidence_for_strategic_question("sq-1")
    assert [r["id"] for r in result] == ["ev-qs-test-published"]


# ---------------------------------------------------------------------------
# EntityIntelligenceQueryService -- everything touching one Entity
# ---------------------------------------------------------------------------

def test_evidence_for_entity_is_published_only_and_entity_scoped(repos, queries) -> None:
    repos.evidence.create(_evidence("hit", status="published", entity_ids=["company-x"]))
    repos.evidence.create(_evidence("miss-entity", status="published", entity_ids=["company-y"]))
    repos.evidence.create(_evidence("miss-status", status="draft", entity_ids=["company-x"]))
    result = queries.entity_intelligence.evidence_for_entity("company-x")
    assert [r["id"] for r in result] == ["ev-qs-test-hit"]


def test_facts_signals_assessments_recommendations_for_entity(repos, queries) -> None:
    repos.facts.create(_fact("hit", entity_ids=["company-x"]))
    repos.facts.create(_fact("miss", entity_ids=["company-y"]))
    repos.signals.create(_signal("hit", entity_ids=["company-x"]))
    repos.assessments.create(_assessment("hit", entity_ids=["company-x"]))
    repos.recommendations.create(_recommendation("hit", entity_ids=["company-x"]))

    assert [f["id"] for f in queries.entity_intelligence.facts_for_entity("company-x")] == ["fact-qs-test-hit"]
    assert [s["id"] for s in queries.entity_intelligence.signals_for_entity("company-x")] == ["sig-qs-test-hit"]
    assert [a["id"] for a in queries.entity_intelligence.assessments_for_entity("company-x")] == [
        "assessment-qs-test-hit"
    ]
    assert [r["id"] for r in queries.entity_intelligence.recommendations_for_entity("company-x")] == [
        "recommendation-qs-test-hit"
    ]


def test_strategic_questions_for_entity_unions_across_record_types(repos, queries) -> None:
    repos.strategic_questions.create(_strategic_question("from-evidence"))
    repos.strategic_questions.create(_strategic_question("from-signal"))
    repos.strategic_questions.create(_strategic_question("unrelated"))

    linked_evidence = [_evidence("e", strategic_question_ids=["sq-qs-test-from-evidence"])]
    entity_signals = [_signal("s", strategic_question_ids=["sq-qs-test-from-signal"])]
    result = queries.entity_intelligence.strategic_questions_for_entity(linked_evidence, entity_signals, [], [])
    assert {sq["id"] for sq in result} == {"sq-qs-test-from-evidence", "sq-qs-test-from-signal"}


# ---------------------------------------------------------------------------
# LineageQueryService -- resolving a record's own linkage-id fields,
# including missing/partial data
# ---------------------------------------------------------------------------

def test_resolve_linked_evidence_drops_unpublished_and_unknown_ids(repos, queries) -> None:
    repos.evidence.create(_evidence("known", status="published"))
    repos.evidence.create(_evidence("unpublished", status="draft"))
    result = queries.lineage.resolve_linked_evidence(
        ["ev-qs-test-known", "ev-qs-test-unpublished", "ev-does-not-exist"]
    )
    assert [r["id"] for r in result] == ["ev-qs-test-known"]


def test_resolve_linked_facts_handles_missing_ids(repos, queries) -> None:
    repos.facts.create(_fact("known"))
    result = queries.lineage.resolve_linked_facts(["fact-qs-test-known", "fact-does-not-exist"])
    assert [f["id"] for f in result] == ["fact-qs-test-known"]


def test_resolve_linked_none_ids_returns_empty(repos, queries) -> None:
    assert queries.lineage.resolve_linked_facts(None) == []
    assert queries.lineage.resolve_linked_evidence(None) == []
    assert queries.lineage.resolve_linked_signals(None) == []
    assert queries.lineage.resolve_linked_assessments(None) == []
    assert queries.lineage.resolve_linked_strategic_questions(None) == []


def test_resolve_linked_entities_preserves_order_and_drops_unknown(repos, queries) -> None:
    entities = {"company-a": {"id": "company-a", "name": "A"}, "company-b": {"id": "company-b", "name": "B"}}
    result = queries.lineage.resolve_linked_entities(["company-b", "company-missing", "company-a"], entities)
    assert [e["id"] for e in result] == ["company-b", "company-a"]


# ---------------------------------------------------------------------------
# ScopeQueryService -- D-012 explicit vs. derived analytical scope
# ---------------------------------------------------------------------------

def test_explicit_scope_is_none_for_legacy_record_with_no_scope_fields(queries) -> None:
    record = {"id": "x", "entity_ids": ["company-a"]}
    assert queries.scope.explicit_scope(record) is None
    assert queries.scope.has_explicit_scope(record) is False


def test_explicit_scope_unifies_market_ids_and_berry_ids(queries) -> None:
    assessment = {"id": "a1", "market_ids": ["berry-blueberry"]}
    signal = {"id": "s1", "berry_ids": ["berry-blueberry"]}
    assert queries.scope.explicit_scope(assessment)["market_ids"] == ["berry-blueberry"]
    assert queries.scope.explicit_scope(signal)["market_ids"] == ["berry-blueberry"]


def test_records_by_entity_intersection_is_the_legacy_derived_rule(queries) -> None:
    records = [
        {"id": "hit", "entity_ids": ["company-a"]},
        {"id": "miss", "entity_ids": ["company-z"]},
    ]
    result = queries.scope.records_by_entity_intersection(records, {"company-a"})
    assert [r["id"] for r in result] == ["hit"]


def test_scope_disagreements_flags_explicit_scope_with_no_entity_overlap(queries) -> None:
    agreeing = {"id": "agrees", "market_ids": ["berry-blueberry"], "entity_ids": ["company-a"]}
    disagreeing = {"id": "disagrees", "market_ids": ["berry-blueberry"], "entity_ids": ["company-z"]}
    no_explicit_scope = {"id": "no-scope", "entity_ids": ["company-z"]}
    result = queries.scope.scope_disagreements([agreeing, disagreeing, no_explicit_scope], {"company-a"})
    assert [r["id"] for r in result] == ["disagrees"]


# ---------------------------------------------------------------------------
# CoverageQueryService -- domain-neutral counts, never rankings
# ---------------------------------------------------------------------------

def test_evidence_source_breakdown_counts_primary_sources(queries) -> None:
    evidence = [
        {"source_type": "patent_record"},
        {"source_type": "patent_record"},
        {"source_type": "news_search"},
    ]
    counts, primary = queries.coverage.evidence_source_breakdown(evidence, {"patent_record"})
    assert counts["patent_record"] == 2
    assert primary == 2


def test_fact_confidence_and_disputes_scoped_to_entity_set(repos, queries) -> None:
    repos.facts.create(_fact("relevant", entity_ids=["company-a"], confidence="high", status="disputed"))
    repos.facts.create(_fact("irrelevant", entity_ids=["company-z"], confidence="low", status="disputed"))
    confidence_counts, disputed = queries.coverage.fact_confidence_and_disputes({"company-a"})
    assert confidence_counts["high"] == 1
    assert [f["id"] for f in disputed] == ["fact-qs-test-relevant"]


def test_disputed_relationships_scoped_to_entity_set(repos, queries) -> None:
    repos.relationships.create(_relationship("relevant", subject_id="company-a", status="disputed"))
    repos.relationships.create(_relationship("irrelevant", subject_id="company-z", status="disputed"))
    result = queries.coverage.disputed_relationships({"company-a"})
    assert [r["id"] for r in result] == ["rel-qs-test-relevant"]


def test_active_strategic_questions_filters_status(repos, queries) -> None:
    repos.strategic_questions.create(_strategic_question("active", status="active"))
    repos.strategic_questions.create(_strategic_question("answered", status="answered"))
    result = queries.coverage.active_strategic_questions()
    assert [sq["id"] for sq in result] == ["sq-qs-test-active"]


# ---------------------------------------------------------------------------
# Composition boundary -- cached per (data_dir, schemas_dir), never a
# stale fixed singleton (app/composition.py's own reason for existing)
# ---------------------------------------------------------------------------

def test_get_repositories_is_cached_per_data_dir(tmp_path: Path) -> None:
    a = get_repositories(tmp_path, SCHEMAS_DIR)
    b = get_repositories(tmp_path, SCHEMAS_DIR)
    assert a is b


def test_get_repositories_is_isolated_across_data_dirs(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    repos_a = get_repositories(dir_a, SCHEMAS_DIR)
    repos_b = get_repositories(dir_b, SCHEMAS_DIR)
    assert repos_a is not repos_b
    repos_a.entities.create(_entity("only-in-a"))
    assert repos_b.entities.list() == []
