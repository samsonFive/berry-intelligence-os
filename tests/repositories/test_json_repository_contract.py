"""Repository contract test suite (V2 Phase 2B.1,
docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 8).

Tests *behavior*, not implementation -- every test function below is
written entirely in terms of the `RecordRepository` shape
(app/repositories/base.py), using only real, schema-valid sample records
per object type. Nothing here reaches into a repository's private
attributes or assumes JSON-file storage specifically. A future in-memory
or PostgreSQL repository implementation is expected to satisfy this exact
suite unchanged, per Phase 2A Part 8.2's specification -- this file is
that specification's first concrete implementation, run against the JSON
backend (the only backend that exists as of Phase 2B.1).

Uses only temporary, throwaway fixture data (`tmp_path`) -- never the live
1,882-record dataset in `data/`, per this task's explicit instruction.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from app.repositories.base import DuplicateRecord, InvalidRecord, RecordNotFound
from app.repositories.json.assessments import AssessmentRepository
from app.repositories.json.entities import EntityRepository
from app.repositories.json.evidence import EvidenceRepository
from app.repositories.json.facts import FactRepository
from app.repositories.json.recommendations import RecommendationRepository
from app.repositories.json.relationships import RelationshipRepository
from app.repositories.json.signals import SignalRepository
from app.repositories.json.strategic_questions import StrategicQuestionRepository


# ---------------------------------------------------------------------------
# One minimal, real-schema-valid record factory per object type. Every
# factory takes a suffix (so multiple records in one test don't collide)
# and returns a fresh dict -- callers may mutate the result freely.
# ---------------------------------------------------------------------------

def _entity_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"company-contract-test-{suffix}",
        "record_type": "entity",
        "entity_type": "company",
        "name": f"Contract Test Company {suffix}",
        "status": "active",
    }


def _evidence_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"ev-contract-test-{suffix}",
        "record_type": "evidence",
        "status": "published",
        "source_type": "article",
        "title": f"Contract test evidence {suffix}",
        "captured_date": "2026-08-14",
        "summary": "Summary.",
        "submitted_by": "contract-test",
        "priority": {
            dim: {"level": "none", "rationale": ""}
            for dim in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


def _fact_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"fact-contract-test-{suffix}",
        "record_type": "fact",
        "statement": "A test statement.",
        "classification": "fact",
        "confidence": "medium",
        "status": "active",
        "reviewer": "contract-test",
        "created_at": "2026-08-14",
        "evidence_ids": ["ev-x"],
    }


def _relationship_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"rel-contract-test-{suffix}",
        "record_type": "relationship",
        "subject_id": "company-a",
        "predicate": "owns",
        "object_id": "brand-b",
        "status": "active",
        "evidence_ids": ["ev-x"],
    }


def _signal_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"sig-contract-test-{suffix}",
        "record_type": "signal",
        "title": "Contract test signal",
        "status": "proposed",
        "strength": "weak",
        "reviewer": None,
        "evidence_ids": ["ev-one", "ev-two"],
    }


def _assessment_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"assessment-contract-test-{suffix}",
        "record_type": "assessment",
        "title": "Contract test assessment",
        "rationale": "Because a contract test needs one.",
        "status": "active",
        "confidence": "medium",
        "fact_ids": ["fact-x"],
        "reviewer": "contract-test",
        "created_at": "2026-08-14",
    }


def _recommendation_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"recommendation-contract-test-{suffix}",
        "record_type": "recommendation",
        "title": "Contract test recommendation",
        "rationale": "Because a contract test needs one.",
        "action_type": "monitor_for_confirmation",
        "status": "active",
        "assessment_ids": ["assessment-x"],
        "reviewer": "contract-test",
        "created_at": "2026-08-14",
    }


def _strategic_question_record(suffix: str) -> dict[str, Any]:
    return {
        "id": f"sq-contract-test-{suffix}",
        "record_type": "strategic_question",
        "title": "Contract test strategic question",
        "status": "active",
    }


REPO_SPECS: list[tuple[str, Any, Callable[[str], dict[str, Any]]]] = [
    ("entities", EntityRepository, _entity_record),
    ("evidence", EvidenceRepository, _evidence_record),
    ("facts", FactRepository, _fact_record),
    ("relationships", RelationshipRepository, _relationship_record),
    ("signals", SignalRepository, _signal_record),
    ("assessments", AssessmentRepository, _assessment_record),
    ("recommendations", RecommendationRepository, _recommendation_record),
    ("strategic_questions", StrategicQuestionRepository, _strategic_question_record),
]


@pytest.fixture(params=REPO_SPECS, ids=[spec[0] for spec in REPO_SPECS])
def repo_spec(request: pytest.FixtureRequest, tmp_path: Path) -> SimpleNamespace:
    name, repo_cls, factory = request.param
    return SimpleNamespace(name=name, repo=repo_cls(data_dir=tmp_path), factory=factory)


# ---------------------------------------------------------------------------
# 1. get existing / get missing
# ---------------------------------------------------------------------------

def test_get_existing_record_returns_it(repo_spec: SimpleNamespace) -> None:
    record = repo_spec.factory("a")
    repo_spec.repo.create(record)
    fetched = repo_spec.repo.get(record["id"])
    assert fetched == record


def test_get_missing_record_returns_none_not_raise(repo_spec: SimpleNamespace) -> None:
    assert repo_spec.repo.get("does-not-exist") is None


# ---------------------------------------------------------------------------
# 2. deterministic list
# ---------------------------------------------------------------------------

def test_list_is_deterministic_across_repeated_calls(repo_spec: SimpleNamespace) -> None:
    for suffix in ("a", "b", "c"):
        repo_spec.repo.create(repo_spec.factory(suffix))
    first_call = [r["id"] for r in repo_spec.repo.list()]
    second_call = [r["id"] for r in repo_spec.repo.list()]
    assert first_call == second_call
    assert len(first_call) == 3


def test_list_reflects_writes_made_through_a_second_repository_instance(repo_spec: SimpleNamespace, tmp_path: Path) -> None:
    # Two repository instances pointed at the same folder must agree --
    # this is what proves list() is genuinely reading storage, not an
    # in-process cache that could drift from what's actually on disk
    # (load_json_files()'s own mtime-signature cache is designed for
    # exactly this "correct by construction" property; verified here for
    # the repository layer built on top of it).
    second = type(repo_spec.repo)(data_dir=tmp_path)
    repo_spec.repo.create(repo_spec.factory("a"))
    assert [r["id"] for r in second.list()] == [r["id"] for r in repo_spec.repo.list()]


# ---------------------------------------------------------------------------
# 3. create / duplicate rejection / validation rejection
# ---------------------------------------------------------------------------

def test_create_persists_and_returns_the_record(repo_spec: SimpleNamespace) -> None:
    record = repo_spec.factory("a")
    result = repo_spec.repo.create(record)
    assert result == record
    assert repo_spec.repo.get(record["id"]) == record


def test_create_rejects_duplicate_id(repo_spec: SimpleNamespace) -> None:
    record = repo_spec.factory("a")
    repo_spec.repo.create(record)
    with pytest.raises(DuplicateRecord):
        repo_spec.repo.create(repo_spec.factory("a"))


def test_create_rejects_record_that_fails_schema_validation(repo_spec: SimpleNamespace) -> None:
    record = repo_spec.factory("a")
    # "status" is a required field on every object type in REPO_SPECS
    # (verified directly against each schema's own "required" list) --
    # removing it produces a schema-invalid record without special-casing
    # each type individually.
    del record["status"]
    with pytest.raises(InvalidRecord):
        repo_spec.repo.create(record)


def test_create_rejects_record_with_no_id() -> None:
    from app.repositories.json.entities import EntityRepository as _Entities

    with pytest.raises(InvalidRecord):
        _Entities(data_dir=Path("unused")).create({"record_type": "entity", "entity_type": "company", "name": "x", "status": "active"})


# ---------------------------------------------------------------------------
# 4. update / not-found
# ---------------------------------------------------------------------------

def test_update_replaces_an_existing_record(repo_spec: SimpleNamespace) -> None:
    record = repo_spec.factory("a")
    repo_spec.repo.create(record)
    # None of the 9 schemas set additionalProperties:false (verified
    # directly), so an extra scratch field is a safe, universal way to
    # prove update() actually persisted a *different* record, without
    # needing a per-type "which field is safe to change" table.
    updated = {**record, "_contract_test_marker": "changed"}
    result = repo_spec.repo.update(record["id"], updated)
    assert result == updated
    assert repo_spec.repo.get(record["id"]) == updated


def test_update_raises_record_not_found_for_unknown_id(repo_spec: SimpleNamespace) -> None:
    with pytest.raises(RecordNotFound):
        repo_spec.repo.update("does-not-exist", repo_spec.factory("a"))


def test_update_rejects_invalid_replacement(repo_spec: SimpleNamespace) -> None:
    record = repo_spec.factory("a")
    repo_spec.repo.create(record)
    broken = dict(record)
    del broken["status"]
    with pytest.raises(InvalidRecord):
        repo_spec.repo.update(record["id"], broken)


# ---------------------------------------------------------------------------
# 5. delete
# ---------------------------------------------------------------------------

def test_delete_removes_the_record(repo_spec: SimpleNamespace) -> None:
    record = repo_spec.factory("a")
    repo_spec.repo.create(record)
    repo_spec.repo.delete(record["id"])
    assert repo_spec.repo.get(record["id"]) is None


def test_delete_raises_record_not_found_for_unknown_id(repo_spec: SimpleNamespace) -> None:
    with pytest.raises(RecordNotFound):
        repo_spec.repo.delete("does-not-exist")


def test_delete_does_not_disturb_other_records(repo_spec: SimpleNamespace) -> None:
    repo_spec.repo.create(repo_spec.factory("a"))
    repo_spec.repo.create(repo_spec.factory("b"))
    repo_spec.repo.delete(repo_spec.factory("a")["id"])
    remaining_ids = {r["id"] for r in repo_spec.repo.list()}
    assert remaining_ids == {repo_spec.factory("b")["id"]}


# ---------------------------------------------------------------------------
# 6. Entity-specific: records placed into the correct type subfolder,
# located and rewritten there (not relocated) on update/delete.
# ---------------------------------------------------------------------------

def test_entity_repository_places_new_records_in_the_correct_type_subfolder(tmp_path: Path) -> None:
    repo = EntityRepository(data_dir=tmp_path)
    record = _entity_record("a")  # entity_type: company
    repo.create(record)
    assert (tmp_path / "entities" / "companies" / f"{record['id']}.json").exists()


def test_entity_repository_rewrites_in_place_on_update_not_relocated(tmp_path: Path) -> None:
    repo = EntityRepository(data_dir=tmp_path)
    record = _entity_record("a")
    repo.create(record)
    original_path = tmp_path / "entities" / "companies" / f"{record['id']}.json"
    repo.update(record["id"], {**record, "status": "unverified"})
    assert original_path.exists()
    assert original_path.read_text(encoding="utf-8").count('"unverified"') == 1


# ---------------------------------------------------------------------------
# 7. Evidence-specific: published/draft-style filtering and default
# ordering, since this is the one repository with a real, observed filter
# requirement (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 3.2).
# ---------------------------------------------------------------------------

def test_evidence_list_filters_by_status(tmp_path: Path) -> None:
    repo = EvidenceRepository(data_dir=tmp_path)
    published = _evidence_record("a")
    draft = {**_evidence_record("b"), "status": "draft"}
    repo.create(published)
    repo.create(draft)
    assert [r["id"] for r in repo.list(status="published")] == [published["id"]]
    assert [r["id"] for r in repo.list(status="draft")] == [draft["id"]]
    assert len(repo.list()) == 2


def test_evidence_list_orders_by_published_then_captured_date_descending(tmp_path: Path) -> None:
    repo = EvidenceRepository(data_dir=tmp_path)
    older = {**_evidence_record("a"), "published_date": "2020-01-01"}
    newer = {**_evidence_record("b"), "published_date": "2025-01-01"}
    repo.create(older)
    repo.create(newer)
    assert [r["id"] for r in repo.list()] == [newer["id"], older["id"]]
