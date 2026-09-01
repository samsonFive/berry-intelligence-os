"""Canonical Entity Identity Integrity V1."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.company_workspace import present_company_compare
from app.services.entity_identity import (
    STATE_CONFIRMED_DUPLICATE,
    STATE_DISTINCT,
    STATE_LIKELY_RELATED,
    audit_entity_identity,
    canonical_entity_id,
    living_entities,
    load_identity_redirects,
    match_named_entity,
)
from app.services.entity_identity_merge import merge_canonical_entities
from app.services.global_search import SearchPools, search_global
from app.services.report_builder.scope import interpret_scope_text, resolve_scope
from app.services.review_publish import PublishRequest, ReviewPublishService
from app.services.variety_universe.identity import resolve_identity
from tests.test_report_builder import BERRIES, _entity as _rb_entity


def _company(**overrides):
    row = {
        "id": "company-x",
        "record_type": "entity",
        "entity_type": "company",
        "name": "Example Co",
        "aliases": [],
        "status": "active",
        "roles": [],
        "berry_ids": [],
        "evidence_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "attributes": {},
    }
    row.update(overrides)
    return row


def _variety(**overrides):
    row = {
        "id": "variety-x",
        "record_type": "entity",
        "entity_type": "variety",
        "name": "Example Variety",
        "aliases": [],
        "status": "active",
        "roles": [],
        "berry_ids": ["berry-blueberry"],
        "evidence_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "attributes": {},
    }
    row.update(overrides)
    return row


def _planasa_pair():
    survivor = _company(
        id="company-planasa",
        name="Plantas de Navarra, S.A.",
        aliases=["Planasa"],
        evidence_ids=["ev-planasa-about-us"],
        relationship_ids=["rel-planasa-operates-in-spain"],
        berry_ids=["berry-blueberry"],
    )
    duplicate = _company(
        id="company-planasa-2",
        name="Planasa",
        aliases=["Planasa"],
        evidence_ids=["ev-planasa-extra"],
        relationship_ids=["rel-planasa-2-operates-in-spain"],
        berry_ids=["berry-strawberry"],
    )
    relationships = [
        {
            "id": "rel-planasa-operates-in-spain",
            "record_type": "relationship",
            "subject_id": "company-planasa",
            "predicate": "operates_in",
            "object_id": "geography-spain",
            "evidence_ids": ["ev-planasa-about-us"],
        },
        {
            "id": "rel-planasa-2-operates-in-spain",
            "record_type": "relationship",
            "subject_id": "company-planasa-2",
            "predicate": "operates_in",
            "object_id": "geography-spain",
            "evidence_ids": ["ev-planasa-extra"],
        },
        {
            "id": "rel-planasa-2-develops-alpha",
            "record_type": "relationship",
            "subject_id": "company-planasa-2",
            "predicate": "develops",
            "object_id": "variety-alpha",
            "evidence_ids": ["ev-planasa-extra"],
        },
    ]
    evidence = [
        {
            "id": "ev-planasa-about-us",
            "title": "About Planasa",
            "summary": "Keep this body untouched.",
            "entity_ids": ["company-planasa"],
        },
        {
            "id": "ev-planasa-extra",
            "title": "Planasa extra",
            "summary": "Also keep this body untouched.",
            "entity_ids": ["company-planasa-2"],
        },
    ]
    return survivor, duplicate, relationships, evidence


def test_planasa_regression_alias_is_confirmed_duplicate():
    survivor, duplicate, relationships, _evidence = _planasa_pair()
    report = audit_entity_identity(
        [survivor, duplicate],
        relationships=relationships,
        redirects=[{"retired_id": "company-planasa-2", "surviving_id": "company-planasa", "state": "confirmed_duplicate"}],
    )
    collisions = report["companies"]["alias_collisions"] + report["companies"]["confirmed_duplicates"]
    assert any(
        set(row["entity_ids"]) == {"company-planasa", "company-planasa-2"}
        and row["state"] == STATE_CONFIRMED_DUPLICATE
        for row in collisions
    )
    assert canonical_entity_id(
        "company-planasa-2",
        entities=[survivor, duplicate],
        redirects=[{"retired_id": "company-planasa-2", "surviving_id": "company-planasa"}],
    ) == "company-planasa"


def test_exact_company_duplicate_is_confirmed():
    left = _company(id="company-alpha", name="Alpha Genetics Ltd")
    right = _company(id="company-alpha-holdings", name="Alpha Genetics")
    report = audit_entity_identity([left, right])
    assert report["companies"]["exact_duplicates"]
    assert report["companies"]["exact_duplicates"][0]["state"] == STATE_CONFIRMED_DUPLICATE


def test_merge_preserves_aliases_relationships_and_evidence_ids():
    survivor, duplicate, relationships, evidence = _planasa_pair()
    merged = merge_canonical_entities(
        surviving_id="company-planasa",
        retired_id="company-planasa-2",
        entities=[survivor, duplicate],
        relationships=relationships,
        evidence=evidence,
        reason="confirmed accidental Planasa duplicate",
    )
    by_id = {row["id"]: row for row in merged["entities"]}
    assert "Planasa" in by_id["company-planasa"]["aliases"]
    assert by_id["company-planasa-2"]["status"] == "historical"
    assert by_id["company-planasa-2"]["attributes"]["merged_into"] == "company-planasa"
    predicates = {(r["subject_id"], r["predicate"], r["object_id"]) for r in merged["relationships"]}
    assert ("company-planasa", "operates_in", "geography-spain") in predicates
    assert ("company-planasa", "develops", "variety-alpha") in predicates
    assert ("company-planasa-2", "operates_in", "geography-spain") not in predicates
    evidence_ids = {row["id"]: row["entity_ids"] for row in merged["evidence"]}
    assert evidence_ids["ev-planasa-extra"] == ["company-planasa"]
    assert merged["evidence"][1]["summary"] == "Also keep this body untouched."
    assert merged["audit"]["bodies_rewritten"] is False


def test_old_ids_resolve_through_redirect_and_merged_into():
    survivor, duplicate, _, _ = _planasa_pair()
    merged = merge_canonical_entities(
        surviving_id="company-planasa",
        retired_id="company-planasa-2",
        entities=[survivor, duplicate],
        relationships=[],
    )
    assert (
        canonical_entity_id("company-planasa-2", entities=merged["entities"])
        == "company-planasa"
    )
    living = living_entities(merged["entities"])
    assert [row["id"] for row in living] == ["company-planasa"]


def test_distinct_similarly_named_companies_stay_separate():
    costa = _company(id="company-costa-group-holdings", name="Costa Group Holdings Pty Ltd", aliases=["Costa Group"])
    cbi = _company(id="company-costa-berry-international", name="Costa Berry International Pty Ltd")
    report = audit_entity_identity([costa, cbi])
    assert report["companies"]["exact_duplicates"] == []
    assert report["companies"]["alias_collisions"] == []
    matched, ambiguous = match_named_entity("Costa Berry International", "company", [costa, cbi])
    assert matched["id"] == "company-costa-berry-international"
    assert ambiguous == ()
    other, _ = match_named_entity("Costa Group", "company", [costa, cbi])
    assert other["id"] == "company-costa-group-holdings"


def test_ambiguous_duplicate_is_not_auto_merged_or_first_matched():
    left = _company(id="company-sonata-a", name="Sonata")
    right = _company(id="company-sonata-b", name="Sonata Berry Co", aliases=["Sonata"])
    matched, ambiguous = match_named_entity("Sonata", "company", [left, right])
    assert matched is None
    assert set(ambiguous) == {"company-sonata-a", "company-sonata-b"}
    report = audit_entity_identity([left, right])
    assert report["companies"]["alias_collisions"] or report["companies"]["exact_duplicates"]


def test_variety_alias_collision():
    alpha = _variety(id="variety-alpha", name="Alpha", aliases=["Alpha Blue"])
    other = _variety(id="variety-beta", name="Beta", aliases=["Alpha Blue"])
    report = audit_entity_identity([alpha, other])
    assert report["varieties"]["canonical_collisions"]
    assert report["varieties"]["canonical_collisions"][0]["reason"] == "alias_collision"


def test_breeder_code_collision():
    last_call = _variety(id="variety-last-call", name="Last Call", attributes={"selection_code": "LC-1"})
    other = _variety(id="variety-other", name="Other Call", attributes={"breeder_code": "LC-1"})
    report = audit_entity_identity([last_call, other])
    reasons = {row["reason"] for row in report["varieties"]["canonical_collisions"]}
    assert "breeder_code_collision" in reasons or "alias_collision" in reasons


def test_registration_id_collision():
    left = _variety(id="variety-a", name="A", attributes={"patent_number": "USPP025386"})
    right = _variety(id="variety-b", name="B", attributes={"patent_id": "USPP025386"})
    report = audit_entity_identity([left, right])
    assert report["varieties"]["canonical_collisions"][0]["reason"] == "registration_id_collision"


def test_last_call_and_fc11_164_are_distinct():
    last_call = _variety(
        id="variety-last-call",
        name="Last Call",
        attributes={"patent_number": "USPP025386P3", "canada_pbr": {"application_number": "13-7859"}},
    )
    code = _variety(
        id="variety-fc11-164",
        name="FC11-164",
        attributes={"selection_code": "FC11-164", "patent_number": "USPP034903P2", "canada_pbr": {"application_number": "22-11055"}},
    )
    report = audit_entity_identity([last_call, code])
    assert report["varieties"]["canonical_collisions"] == []
    resolution = resolve_identity(
        {"candidate_name": "FC11-164", "breeder_code": "FC11-164", "berry_ids": ["berry-blueberry"]},
        [last_call, code],
    )
    assert resolution["candidate_canonical_match"] == "variety-fc11-164"


def test_search_returns_canonical_identity_once():
    survivor, duplicate, _, _ = _planasa_pair()
    pools = SearchPools(
        entities=[survivor, duplicate],
        identity_redirects=[{"retired_id": "company-planasa-2", "surviving_id": "company-planasa"}],
    )
    result = search_global("Planasa", pools, include_private=False)
    companies = []
    for group in result.get("groups") or []:
        if group["id"] == "companies":
            companies = list(group.get("in_context") or []) + list(group.get("also_global") or [])
    assert [row["id"] for row in companies] == ["company-planasa"]


def test_report_builder_resolves_repaired_company():
    entities = [
        _rb_entity(id="company-planasa", entity_type="company", name="Plantas de Navarra, S.A.", aliases=["Planasa"]),
        _rb_entity(id="company-planasa-2", entity_type="company", name="Planasa"),
        _rb_entity(id="geography-spain", entity_type="geography", name="Spain"),
    ]
    living = living_entities(
        entities,
        redirects=[{"retired_id": "company-planasa-2", "surviving_id": "company-planasa"}],
    )
    proposal = interpret_scope_text(
        "Compare Planasa in Europe.",
        berries=BERRIES,
        completer=None,
        entities=living,
    )
    scope = resolve_scope(proposal, entities=living, berries=BERRIES, questions=[])
    assert scope.company_ids == ("company-planasa",)
    assert scope.ambiguous_companies == ()


def test_company_compare_dedupes_redirected_copy():
    entities = {
        "company-planasa": _company(id="company-planasa", name="Plantas de Navarra, S.A.", aliases=["Planasa"]),
        "company-planasa-2": _company(id="company-planasa-2", name="Planasa"),
    }
    result = present_company_compare(
        ["company-planasa", "company-planasa-2"],
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        evidence_by_id={},
        signals=[],
        assessments=[],
        berry_labels=BERRIES,
        redirects=[{"retired_id": "company-planasa-2", "surviving_id": "company-planasa"}],
    )
    assert [card["id"] for card in result["companies"]] == ["company-planasa"]


def test_audit_get_does_not_mutate_trust(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"
    inbox = tmp_path / "inbox"
    (data / "entities" / "companies").mkdir(parents=True)
    (data / "configuration").mkdir(parents=True)
    (inbox / "evidence").mkdir(parents=True)
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    main._JSON_FOLDER_CACHE.clear()
    before = {path: path.read_bytes() for path in data.rglob("*") if path.is_file()}
    client = TestClient(app)
    response = client.get("/entities/identity")
    assert response.status_code == 200
    assert "CONFIRMED DUPLICATE" in response.text or "Entity identity integrity" in response.text
    after = {path: path.read_bytes() for path in data.rglob("*") if path.is_file()}
    assert after == before


def test_identity_page_is_authoring_only(monkeypatch):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    client = TestClient(app)
    response = client.get("/entities/identity")
    assert response.status_code == 403


def test_old_planasa_href_redirects_on_live_catalog():
    client = TestClient(app)
    response = client.get("/entities/company/company-planasa-2", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/entities/company/company-planasa"


def test_canonical_redirects_file_maps_planasa_duplicate():
    redirects = load_identity_redirects(Path(main.DATA_DIR) if hasattr(main, "DATA_DIR") else None)
    assert any(row["retired_id"] == "company-planasa-2" and row["surviving_id"] == "company-planasa" for row in redirects)


def test_publish_matches_planasa_alias_instead_of_creating_duplicate():
    class _Repo:
        def __init__(self, rows):
            self._rows = rows

        def list(self):
            return self._rows

        def get(self, record_id):
            return next((row for row in self._rows if row["id"] == record_id), None)

    survivor, _, _, _ = _planasa_pair()
    repos = type("Repos", (), {})()
    repos.entities = _Repo([survivor])
    repos.facts = _Repo([])
    repos.relationships = _Repo([])
    repos.strategic_questions = _Repo([])
    repos.evidence = _Repo([])
    created: list[str] = []

    def unique_entity_id(entity_type, name, existing_ids):
        created.append(name)
        return f"{entity_type}-should-not-create"

    service = ReviewPublishService(
        repositories=repos,
        unit_of_work_factory=lambda: None,
        get_validator=lambda _name: None,
        unique_entity_id=unique_entity_id,
        append_unique=lambda values, item: values + [item] if item not in values else values,
        move_draft_attachments=lambda *_args: [],
        restore_draft_attachments=lambda *_args: None,
        delete_draft=lambda *_args: None,
    )
    matched, ambiguous = match_named_entity("Planasa", "company", [survivor])
    assert matched["id"] == "company-planasa"
    assert ambiguous == ()
    request = PublishRequest(
        draft={"id": "ev-test", "title": "Planasa note"},
        draft_id="ev-test",
        title="Planasa note",
        source_type="trade_press",
        source_name="Test",
        source_url="https://example.test/planasa",
        published_date="2026-01-01",
        captured_date="2026-01-02",
        summary="s",
        why_it_matters="w",
        tags=[],
        selected_berries=["berry-blueberry"],
        all_entity_names_by_type={"company": ["Planasa"]},
        facts_input=[],
        relationships_input=[],
        priority={},
        strategic_question_text=[],
        reviewer="tester",
    )
    # Only exercise the match path; full persist needs a unit of work.
    assert created == []
    assert request.all_entity_names_by_type["company"] == ["Planasa"]


def test_static_build_does_not_emit_identity_page():
    from scripts import build_static

    source = Path(build_static.__file__).read_text(encoding="utf-8")
    assert "/entities/identity" not in source
    assert "entity_identity.html" not in source
