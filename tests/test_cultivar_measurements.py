"""Trust, source-version, scope and immutable-history acceptance checks."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.repositories.json.entities import EntityRepository
from app.repositories.json.evidence import EvidenceRepository
from app.repositories.json.facts import FactRepository
from app.repositories.paths import SCHEMAS_DIR
from app.repositories.unit_of_work import JsonUnitOfWork
from app.services.cultivar_measurements import (
    CultivarMeasurementError, candidate_statement, compatibility_key, get_measurement,
    list_measurements, load_evidence_dependencies, normalize_measurement, resolve_measurement_identity,
    review_measurement, stage_measurement,
)
from app.services.review_events import load_review_events
from app.services.review_publish import ApproveClaimRequest, ReviewPublishService


def _entity(entity_id, crop="berry-strawberry", kind="variety"):
    return {"id": entity_id, "record_type": "entity", "entity_type": kind,
            "name": entity_id, "status": "active", "berry_ids": [crop]}


def _row(**changes):
    result = {"id": "R-1", "region": "Spain", "subregion": "Huelva surveyed plants",
              "cultivar": "RedSayra", "record_kind": "cultivar", "aliases": [],
              "platform_entity_ids": ["variety-one"], "platform_candidate_ids": ["variety-one"],
              "claim": "Reported plant share", "evidence_type": "Reported planting share",
              "value": 13.5, "unit": "percent plants", "denominator": "All plants in the Huelva survey",
              "data_period": "2025/26", "source_ids": ["S1"], "limitations": "Province only.",
              "original_other_field": {"native": "kept"}}
    result.update(changes)
    return result


def _binding(**changes):
    result = {"source_id": "S1", "evidence_id": "ev-source", "source_url": "https://owner.example/report.pdf",
              "source_title": "Owner planting survey", "locator": "Figure 1, page 7",
              "source_dataset": "survey-2025-26", "captured_sha256": None, "capture_hash_kind": "unknown"}
    result.update(changes)
    return result


def _normalize(row=None, bindings=None, entities=None, **changes):
    return normalize_measurement(row or _row(), source_bindings=bindings or [_binding()],
                                 captured_at=changes.get("captured_at", "2026-11-15T00:00:00Z"),
                                 import_batch_id=changes.get("import_batch_id", "batch-one"),
                                 berry_id=changes.get("berry_id", "berry-strawberry"),
                                 entities_by_id=entities)


@pytest.fixture
def world(tmp_path):
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    repos = SimpleNamespace(entities=EntityRepository(data), evidence=EvidenceRepository(data), facts=FactRepository(data))
    for entity in [_entity("berry-strawberry", kind="berry"), _entity("berry-blueberry", "berry-blueberry", "berry"),
                   _entity("variety-one"), _entity("variety-two"), _entity("variety-medallion", "berry-blueberry")]:
        repos.entities.create(entity)
    repos.evidence.create({
        "id": "ev-source", "record_type": "evidence", "status": "published", "review_state": "published",
        "source_type": "report", "evidence_role": "publication_artifact", "title": "Owner planting survey",
        "captured_date": "2026-11-15", "source_url": "https://owner.example/report.pdf", "summary": "Source body",
        "submitted_by": "research-import", "entity_ids": ["berry-strawberry", "variety-one", "variety-two"],
        "fact_ids": [], "priority": {name: {"level": "none", "rationale": ""}
                                     for name in ("reading", "testing", "commercial_position", "monitoring")},
    })
    def validator(name):
        return Draft202012Validator(json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8")),
                                     format_checker=FormatChecker())
    service = ReviewPublishService(
        repos, lambda: JsonUnitOfWork(entities=repos.entities, evidence=repos.evidence, facts=repos.facts),
        validator, lambda *args: "unused", lambda items, value: list(dict.fromkeys([*items, value])),
        lambda *args: [], lambda *args: None, lambda *args: None, review_events_inbox=inbox,
    )
    return SimpleNamespace(data=data, inbox=inbox, repos=repos, service=service)


def _project(world, private=True):
    return list_measurements(world.inbox, facts=world.repos.facts.list(),
                             evidence_by_id={row["id"]: row for row in world.repos.evidence.list()},
                             entities_by_id={row["id"]: row for row in world.repos.entities.list()},
                             include_private=private)


def _review(world, record, **changes):
    values = dict(action="approve", reviewer="analyst", review_publish_service=world.service,
                  repos=world.repos, expected_content_sha256=record["content_sha256"], source_id="S1",
                  source_version_confirmed=True, source_confirmation_note="Read Figure 1 p7 in the matching 2025/26 report.")
    values.update(changes)
    return review_measurement(world.inbox, record["id"], **values)


def test_source_native_row_and_qualitative_aggregate_are_preserved(world):
    row = _row(record_kind="aggregate", cultivar="Plant Sciences exclusives", value=None, unit=None)
    record = _normalize(row)
    assert record["source_native"] == row
    assert record["cultivar_entity_id"] is None
    assert record["identity_status"] == "not_applicable"
    stage_measurement(world.inbox, record)
    assert world.repos.facts.list() == []
    assert _project(world, False) == []


def test_staging_is_idempotent_and_new_source_version_retains_prior_capture(world):
    first = _normalize()
    repeated = _normalize(captured_at="2026-11-16T00:00:00Z", import_batch_id="another-batch")
    assert first["id"] == repeated["id"]
    assert stage_measurement(world.inbox, first)["outcome"] == "created"
    assert stage_measurement(world.inbox, repeated)["outcome"] == "already_present_identical"
    changed = _normalize(bindings=[_binding(captured_sha256="a" * 64, capture_hash_kind="artifact")])
    assert changed["id"] != first["id"]
    stage_measurement(world.inbox, changed)
    assert len(_project(world)) == 2
    tampered = deepcopy(first)
    tampered["value"] = 99
    with pytest.raises(CultivarMeasurementError, match="content hash"):
        stage_measurement(world.inbox, tampered)
    assert get_measurement(world.inbox, first["id"])["value"] == 13.5


@pytest.mark.parametrize("field,value", [("cultivar", "Other cultivar"), ("denominator", "Summer crop only"),
    ("subregion", "National"), ("cohort", "Fall planting"), ("production_system", "organic"),
    ("unit", "percent output"), ("data_period", "2024/25")])
def test_distinct_populations_and_series_do_not_collapse(field, value):
    first = _normalize()
    second = _normalize(_row(**{field: value}))
    assert first["series_key"] != second["series_key"]


def test_source_dataset_is_part_of_series_identity():
    first = _normalize()
    second = _normalize(bindings=[_binding(source_dataset="other-survey")])
    assert compatibility_key(first) != compatibility_key(second)


def test_normalization_requires_explicit_crop_context():
    with pytest.raises(CultivarMeasurementError, match="explicit crop"):
        normalize_measurement(_row(), source_bindings=[_binding()], captured_at="2026-11-15T00:00:00Z",
                              import_batch_id="batch")


def test_source_approval_alone_never_approves_measurement_and_version_needs_confirmation(world):
    record = _normalize()
    stage_measurement(world.inbox, record)
    assert _project(world)[0]["review_state"] == "pending"
    assert _project(world, False) == []
    result = _review(world, record, source_version_confirmed=False, source_confirmation_note="")
    assert not result["ok"] and "source version" in " ".join(result["errors"])
    assert world.repos.facts.list() == []


def test_explicit_primary_source_selection_is_required(world):
    record = _normalize(bindings=[_binding(), _binding(source_id="S2", source_title="Second source")])
    stage_measurement(world.inbox, record)
    result = _review(world, record, source_id=None)
    assert not result["ok"] and "select the primary source" in " ".join(result["errors"])
    assert world.repos.facts.list() == []


def test_individual_claim_approval_is_scoped_and_retry_is_idempotent(world):
    record = _normalize()
    stage_measurement(world.inbox, record)
    result = _review(world, record)
    assert result["ok"]
    fact = world.repos.facts.get(result["fact_id"])
    assert fact["classification"] == "claim"
    assert set(fact["entity_ids"]) == {"berry-strawberry", "variety-one"}
    assert world.repos.entities.get("variety-two").get("fact_ids", []) == []
    assert _project(world)[0]["review_state"] == "reviewed"
    public = _project(world, False)
    assert len(public) == 1 and "source_native" not in public[0] and "review_events" not in public[0]
    assert _review(world, record)["fact_id"] == result["fact_id"]
    assert len(world.repos.facts.list()) == 1
    assert len(load_review_events(world.inbox, workflow="cultivar_measurement_review")) == 1
    assert load_review_events(world.inbox, workflow="evidence_claim_review")[0]["action"] == "approve_claim"


def test_old_approve_claim_callers_still_inherit_source_entity_scope(world):
    result = world.service.approve_claim(ApproveClaimRequest(
        evidence_id="ev-source", statement="Separate ordinary claim", proposed_statement="Separate ordinary claim",
        classification="fact", confidence="medium", reviewer="analyst", origin="publication_prose"))
    assert result.ok
    assert set(world.repos.facts.get(result.fact_id)["entity_ids"]) == {"berry-strawberry", "variety-one", "variety-two"}


def test_explicit_claim_entity_ids_must_exist(world):
    result = world.service.approve_claim(ApproveClaimRequest(
        evidence_id="ev-source", statement="Claim", proposed_statement="Claim", classification="claim",
        confidence="medium", reviewer="analyst", origin="test", entity_ids=["variety-does-not-exist"]))
    assert not result.ok and "do not resolve" in " ".join(result.schema_errors)
    assert world.repos.facts.list() == []


def test_mismatched_source_url_cannot_be_approved_even_with_manual_confirmation(world):
    record = _normalize(bindings=[_binding(source_url="https://other.example/report.pdf")])
    stage_measurement(world.inbox, record)
    assert not _review(world, record)["ok"]
    assert _project(world, False) == []


def test_access_reference_cannot_be_primary_measurement_source_even_if_same_url_is_published(world):
    record = _normalize(bindings=[_binding(source_intake_role="acquisition_or_context_inventory")])
    stage_measurement(world.inbox, record)
    assert not _review(world, record)["ok"]
    assert world.repos.facts.list() == []


def test_exact_retained_binary_hash_proves_source_version(world):
    evidence = world.repos.evidence.get("ev-source")
    evidence["discovery_provenance"] = {"retained_binary_sha256": "a" * 64}
    world.repos.evidence.update("ev-source", evidence)
    record = _normalize(bindings=[_binding(captured_sha256="a" * 64, capture_hash_kind="artifact")])
    stage_measurement(world.inbox, record)
    assert _review(world, record, source_version_confirmed=False, source_confirmation_note="")["ok"]


def test_exact_capture_still_needs_a_locator_or_reviewed_passage(world):
    evidence = world.repos.evidence.get("ev-source")
    evidence["artifact_sha256"] = "a" * 64
    world.repos.evidence.update("ev-source", evidence)
    record = _normalize(bindings=[_binding(captured_sha256="a" * 64, capture_hash_kind="artifact", locator="")])
    stage_measurement(world.inbox, record)
    result = _review(world, record, source_version_confirmed=False, source_confirmation_note="")
    assert not result["ok"] and "locator/passage" in " ".join(result["errors"])
    assert world.repos.facts.list() == []


def test_reject_and_defer_keep_history_without_trusted_writes(world):
    record = _normalize()
    stage_measurement(world.inbox, record)
    assert _review(world, record, action="defer", notes="Need current denominator.")["ok"]
    assert _project(world)[0]["review_state"] == "deferred"
    assert _review(world, record, action="reject", notes="Wrong production cohort.")["ok"]
    assert _project(world)[0]["review_state"] == "rejected"
    assert len(load_review_events(world.inbox, workflow="cultivar_measurement_review")) == 2
    assert world.repos.facts.list() == [] and _project(world, False) == []


def test_withdrawn_or_changed_source_cannot_keep_reviewed_projection(world):
    record = _normalize()
    stage_measurement(world.inbox, record)
    fact_id = _review(world, record)["fact_id"]
    evidence = world.repos.evidence.get("ev-source")
    evidence["article"] = {"content_sha256": "b" * 64, "body": "Changed revision"}
    world.repos.evidence.update("ev-source", evidence)
    assert _project(world, False) == []
    assert not _review(world, record, action="reject")["ok"]
    assert world.repos.facts.get(fact_id)["status"] == "active"
    # A later explicit source-version decision may revalidate the same claim.
    assert _review(world, record)["ok"]
    assert len(_project(world, False)) == 1
    fact = world.repos.facts.get(fact_id)
    fact["status"] = "withdrawn"
    world.repos.facts.update(fact_id, fact)
    assert _project(world, False) == []
    assert not _review(world, record)["ok"]


def test_cross_crop_identity_never_attaches_strawberry_to_blueberry_medallion(world):
    entities = {row["id"]: row for row in world.repos.entities.list()}
    record = _normalize(_row(cultivar="Medallion", platform_entity_ids=["variety-medallion"],
                             platform_candidate_ids=["variety-medallion"]), entities=entities)
    assert record["identity_status"] == "unresolved" and record["cultivar_entity_id"] is None
    stage_measurement(world.inbox, record)
    assert not _review(world, record)["ok"]
    result = resolve_measurement_identity(world.inbox, record["id"], selected_entity_id="variety-medallion",
        reviewer="analyst", notes="Attempted wrong-crop mapping", expected_content_sha256=record["content_sha256"], repos=world.repos)
    assert not result["ok"]
    assert world.repos.facts.list() == []


def test_identity_choice_is_generic_immutable_and_not_claim_approval(world):
    row = _row(berry_id="berry-blueberry", cultivar="Source-native Medallion", platform_entity_ids=["variety-medallion"],
               platform_candidate_ids=["variety-medallion", "variety-two"])
    record = _normalize(row)
    assert record["identity_status"] == "ambiguous" and record["cultivar_entity_id"] is None
    stage_measurement(world.inbox, record)
    assert not _review(world, record)["ok"]
    result = resolve_measurement_identity(world.inbox, record["id"], selected_entity_id="variety-medallion",
        reviewer="catalog-reviewer", notes="Source cultivar code checked against the blueberry identity.",
        expected_content_sha256=record["content_sha256"], repos=world.repos)
    assert result["ok"] and result["id"] != record["id"]
    revised = result["record"]
    assert revised["source_native"] == row and revised["supersedes"] == record["id"]
    assert revised["cultivar_entity_id"] == "variety-medallion"
    assert get_measurement(world.inbox, record["id"])["cultivar_entity_id"] is None
    assert {item["id"]: item for item in _project(world)}[record["id"]]["review_state"] == "superseded"
    assert world.repos.facts.list() == []
    assert not _review(world, record)["ok"]


def test_identity_audit_is_required_and_retry_recovers_missing_event(world):
    row = _row(platform_candidate_ids=["variety-one", "variety-two"])
    record = _normalize(row)
    stage_measurement(world.inbox, record)
    values = dict(selected_entity_id="variety-one", reviewer="catalog-reviewer", notes="Source code confirmed.",
                  expected_content_sha256=record["content_sha256"], repos=world.repos)
    revised = resolve_measurement_identity(world.inbox, record["id"], **values)["record"]
    # Simulate the narrowly recoverable crash: revision committed, decision
    # event not yet appended. Claim review must wait for recovery.
    for path in (world.inbox / "review_events" / "cultivar_measurement_review").rglob("*.json"):
        path.unlink()
    projected = {item["id"]: item for item in _project(world)}[revised["id"]]
    assert not projected["can_approve"] and any("audit event" in reason for reason in projected["blockers"])
    retried = resolve_measurement_identity(world.inbox, record["id"], **values)
    assert retried["id"] == revised["id"]
    projected = {item["id"]: item for item in _project(world)}[revised["id"]]
    assert projected["can_approve"]
    assert world.repos.facts.list() == []


def test_stale_digest_never_reaches_fact_gate(world):
    record = _normalize()
    stage_measurement(world.inbox, record)
    assert not _review(world, record, expected_content_sha256="0" * 64)["ok"]
    assert world.repos.facts.list() == []


def test_list_dependencies_never_hydrate_unrelated_article_bodies(world, monkeypatch):
    source = world.repos.evidence.get("ev-source")
    source["article"] = {"paragraphs": [{"index": 0, "text": "Relevant source body"}]}
    world.repos.evidence.update("ev-source", source)
    unrelated = deepcopy(source)
    unrelated.update(id="ev-unrelated", title="Unrelated publication")
    unrelated.pop("evidence_role", None)
    unrelated["article"] = {"paragraphs": [{"index": 0, "text": "Unrelated body must not hydrate"}]}
    world.repos.evidence.create(unrelated)
    reads = []
    original = Path.read_text
    def track_read(path, *args, **kwargs):
        if path.parent == world.data / "evidence":
            reads.append(path.stem)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", track_read)
    metadata = load_evidence_dependencies(world.data)
    assert set(metadata) == {"ev-source", "ev-unrelated"}
    assert all("article" not in row for row in metadata.values())
    assert metadata["ev-unrelated"]["status"] == "published"  # Legacy roles remain usable metadata.
    assert reads == []
    record = _normalize()
    stage_measurement(world.inbox, record)
    fact = {"status": "active", "origin": "cultivar_measurement:" + record["id"] + ":" + record["content_sha256"],
            "evidence_ids": ["ev-source"]}
    dependencies = load_evidence_dependencies(world.data, facts=[fact])
    assert "article" in dependencies["ev-source"] and "article" not in dependencies["ev-unrelated"]
    assert reads == ["ev-source"]


def test_explicit_source_ids_bound_metadata_reads_but_keep_active_version_dependencies(world, monkeypatch):
    from app.services import publication_sources
    source = world.repos.evidence.get("ev-source")
    source["article"] = {"paragraphs": [{"index": 0, "text": "Approved source version"}]}
    world.repos.evidence.update("ev-source", source)
    unrelated = deepcopy(source)
    unrelated.update(id="ev-unrelated", title="Unrelated publication")
    world.repos.evidence.create(unrelated)
    requested = deepcopy(source)
    requested.update(id="ev-requested", title="Requested source")
    world.repos.evidence.create(requested)
    previews = []
    original = publication_sources._current_preview
    def track_preview(path):
        previews.append(path.stem)
        return original(path)
    monkeypatch.setattr(publication_sources, "_current_preview", track_preview)
    record = _normalize()
    fact = {"status": "active", "origin": "cultivar_measurement:" + record["id"] + ":" + record["content_sha256"],
            "evidence_ids": ["ev-source"]}
    result = load_evidence_dependencies(world.data, facts=[fact], evidence_ids=["ev-requested", "../../outside"])
    assert set(previews) == {"ev-requested", "ev-source"}
    assert set(result) == {"ev-requested", "ev-source"}
    assert "article" not in result["ev-requested"]
    assert "article" in result["ev-source"]
    previews.clear()
    assert load_evidence_dependencies(world.data, evidence_ids=[]) == {}
    assert previews == []
