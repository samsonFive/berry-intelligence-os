"""Source / Entity Intelligence Timeline V1 -- shared query layer tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.queries.timeline import entity_intelligence_timeline


def _entity(**overrides):
    row = {
        "record_type": "entity",
        "status": "active",
        "aliases": [],
        "berry_ids": [],
        "attributes": {},
    }
    row.update(overrides)
    return row


def _entities():
    rows = [
        _entity(id="company-x", entity_type="company", name="Company X"),
        _entity(id="variety-y", entity_type="variety", name="Variety Y", berry_ids=["berry-blueberry"]),
        _entity(id="geography-us", entity_type="geography", name="United States"),
    ]
    return {row["id"]: row for row in rows}


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "record_type": "evidence",
        "status": "published",
        "source_type": "trade_press",
        "title": "Some article",
        "summary": "A summary.",
        "captured_date": "2026-01-01",
        "entity_ids": ["company-x"],
        "geography_ids": [],
    }
    row.update(overrides)
    return row


def test_evidence_row_uses_published_date_only_no_captured_fallback():
    entities = _entities()
    evidence = [_evidence(id="ev-undated", published_date=None, captured_date="2026-05-01")]
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={r["id"]: r for r in evidence},
    )
    assert result["dated"] == []
    assert result["undated_count"] == 1
    assert result["undated"][0]["kind"] == "evidence"


def test_evidence_row_dated_when_published_date_present():
    entities = _entities()
    evidence = [_evidence(id="ev-dated", published_date="2026-03-10")]
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={r["id"]: r for r in evidence},
    )
    assert result["dated_count"] == 1
    assert result["dated"][0]["date"] == "2026-03-10"
    assert result["dated"][0]["is_fallback_date"] is False


def test_fact_prefers_event_date_over_created_at_and_flags_fallback():
    entities = _entities()
    evidence = [_evidence(id="ev-1", published_date="2026-01-05")]
    evidence_idx = {r["id"]: r for r in evidence}
    fact_with_event_date = {
        "id": "fact-a",
        "statement": "Company X does something.",
        "classification": "fact",
        "confidence": "high",
        "status": "active",
        "created_at": "2026-06-01",
        "event_date": "2025-11-20",
        "evidence_ids": ["ev-1"],
        "entity_ids": ["company-x"],
    }
    fact_without_event_date = {
        "id": "fact-b",
        "statement": "Company X does another thing.",
        "classification": "claim",
        "confidence": "low",
        "status": "active",
        "created_at": "2026-06-02",
        "event_date": None,
        "evidence_ids": ["ev-1"],
        "entity_ids": ["company-x"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[fact_with_event_date, fact_without_event_date],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx=evidence_idx,
    )
    # Both facts share ev-1, which IS in linked_evidence -> both should be
    # grouped as derived_items under the evidence row, not flat top-level.
    assert result["dated_count"] == 1
    evidence_row = result["dated"][0]
    assert evidence_row["kind"] == "evidence"
    derived = {row["id"]: row for row in evidence_row["derived_items"]}
    assert derived["fact-a"]["date"] == "2025-11-20"
    assert derived["fact-a"]["is_fallback_date"] is False
    assert derived["fact-b"]["date"] == "2026-06-02"
    assert derived["fact-b"]["is_fallback_date"] is True
    assert derived["fact-b"]["date_basis"] == "created_at"


def test_fact_without_any_date_or_evidence_fallback_is_undated():
    entities = _entities()
    fact = {
        "id": "fact-c",
        "statement": "Undated claim.",
        "classification": "claim",
        "confidence": "low",
        "status": "active",
        "created_at": None,
        "event_date": None,
        "evidence_ids": ["ev-missing"],
        "entity_ids": ["company-x"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],
        entity_facts=[fact],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={},
    )
    assert result["dated"] == []
    assert result["undated_count"] == 1
    assert result["undated"][0]["kind"] == "fact"


def test_relationship_uses_effective_date_then_evidence_fallback():
    entities = _entities()
    evidence = [_evidence(id="ev-2", published_date="2024-08-01", entity_ids=["company-x", "variety-y"])]
    evidence_idx = {r["id"]: r for r in evidence}
    rel_with_date = {
        "id": "rel-a",
        "subject_id": "company-x",
        "predicate": "develops",
        "object_id": "variety-y",
        "status": "active",
        "effective_date": "2020-01-01",
        "evidence_ids": ["ev-2"],
    }
    rel_without_date = {
        "id": "rel-b",
        "subject_id": "company-x",
        "predicate": "markets",
        "object_id": "variety-y",
        "status": "active",
        "effective_date": None,
        "evidence_ids": ["ev-2"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[],
        entity_relationships=[rel_with_date, rel_without_date],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx=evidence_idx,
    )
    evidence_row = result["dated"][0]
    derived = {row["id"]: row for row in evidence_row["derived_items"]}
    assert derived["rel-a"]["date"] == "2020-01-01"
    assert derived["rel-a"]["is_fallback_date"] is False
    assert derived["rel-b"]["date"] == "2024-08-01"
    assert derived["rel-b"]["is_fallback_date"] is True
    assert derived["rel-b"]["date_basis"] == "evidence_published_date"


def test_signal_uses_first_seen_then_last_updated_then_evidence_fallback():
    entities = _entities()
    evidence = [_evidence(id="ev-3", published_date="2023-05-05")]
    evidence_idx = {r["id"]: r for r in evidence}
    signal_no_dates = {
        "id": "signal-a",
        "title": "A pattern across evidence.",
        "status": "proposed",
        "evidence_ids": ["ev-3"],
        "strength": "moderate",
        "first_seen": None,
        "last_updated": None,
        "entity_ids": ["company-x"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],  # ev-3 deliberately NOT in linked_evidence -> Signal stays top-level with lineage
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[signal_no_dates],
        entity_assessments=[],
        evidence_idx=evidence_idx,
    )
    assert result["dated_count"] == 1
    row = result["dated"][0]
    assert row["kind"] == "signal"
    assert row["date"] == "2023-05-05"
    assert row["is_fallback_date"] is True
    assert row["date_basis"] == "evidence_published_date"
    assert row["lineage"][0]["id"] == "ev-3"


def test_signal_with_zero_dates_and_no_resolvable_evidence_is_undated():
    entities = _entities()
    signal = {
        "id": "signal-b",
        "title": "Nothing dateable here.",
        "status": "proposed",
        "evidence_ids": ["ev-missing-a", "ev-missing-b"],
        "strength": "weak",
        "entity_ids": ["company-x"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[signal],
        entity_assessments=[],
        evidence_idx={},
    )
    assert result["dated"] == []
    assert result["undated"][0]["kind"] == "signal"


def test_assessment_uses_created_at_as_the_real_semantic_date_no_fallback_flag():
    entities = _entities()
    assessment = {
        "id": "assessment-a",
        "title": "An analyst interpretation.",
        "rationale": "Because of X and Y.",
        "status": "active",
        "confidence": "medium",
        "fact_ids": ["fact-z"],
        "reviewer": "analyst",
        "created_at": "2026-04-15",
        "entity_ids": ["company-x"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[assessment],
        evidence_idx={},
    )
    row = result["dated"][0]
    assert row["kind"] == "assessment"
    assert row["date"] == "2026-04-15"
    assert row["date_basis"] == "created_at"
    assert row["is_fallback_date"] is False


def test_rights_and_commercial_are_evidence_sub_kinds_not_flattened():
    entities = _entities()
    rights = _evidence(
        id="ev-rights",
        source_type="patent_record",
        title="USPP12345 - Some variety",
        published_date="2019-06-01",
    )
    commercial = _evidence(
        id="ev-commercial",
        intake_type="commercial_observation",
        commercial_observation={"observed_at": "2026-02-14", "retailer_name": "Tesco"},
        title="Retail listing",
        published_date=None,
    )
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[rights, commercial],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={"ev-rights": rights, "ev-commercial": commercial},
    )
    kinds = {row["id"]: row["kind"] for row in result["dated"]}
    assert kinds["ev-rights"] == "rights"
    assert kinds["ev-commercial"] == "commercial"
    commercial_row = next(r for r in result["dated"] if r["id"] == "ev-commercial")
    assert commercial_row["date"] == "2026-02-14"
    assert commercial_row["retailer_name"] == "Tesco"


def test_fact_evidence_not_in_linked_evidence_gets_lineage_not_grouping():
    entities = _entities()
    other_evidence = _evidence(id="ev-elsewhere", published_date="2022-01-01", title="Elsewhere article")
    fact = {
        "id": "fact-elsewhere",
        "statement": "A fact citing evidence not shown as its own row here.",
        "classification": "fact",
        "confidence": "high",
        "status": "active",
        "created_at": "2022-01-02",
        "event_date": None,
        "evidence_ids": ["ev-elsewhere"],
        "entity_ids": ["company-x"],
    }
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],  # deliberately empty -- ev-elsewhere is not one of THIS entity's own linked_evidence
        entity_facts=[fact],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={"ev-elsewhere": other_evidence},
    )
    assert result["dated_count"] == 1
    row = result["dated"][0]
    assert row["kind"] == "fact"
    assert row["lineage"][0]["id"] == "ev-elsewhere"
    assert row["lineage"][0]["href"] == "/evidence/ev-elsewhere"


def test_sort_is_newest_first_and_deterministic():
    entities = _entities()
    evidence = [
        _evidence(id="ev-early", published_date="2020-01-01"),
        _evidence(id="ev-late", published_date="2024-01-01"),
        _evidence(id="ev-mid", published_date="2022-01-01"),
    ]
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={r["id"]: r for r in evidence},
    )
    assert [row["id"] for row in result["dated"]] == ["ev-late", "ev-mid", "ev-early"]


def test_empty_entity_has_no_fabricated_rows():
    entities = _entities()
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=[],
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={},
    )
    assert result["has_any"] is False
    assert result["dated"] == []
    assert result["undated"] == []


def test_kinds_and_berries_present_reflect_only_real_rows():
    entities = _entities()
    evidence = [_evidence(id="ev-berry", published_date="2026-01-01", berry_ids=["berry-blueberry"])]
    result = entity_intelligence_timeline(
        entity_id="company-x",
        entities=entities,
        linked_evidence=evidence,
        entity_facts=[],
        entity_relationships=[],
        entity_signals=[],
        entity_assessments=[],
        evidence_idx={r["id"]: r for r in evidence},
    )
    assert result["kinds_present"] == ["evidence"]
    assert result["berries_present"] == ["berry-blueberry"]


# --- Route-level integration against real data -------------------------


def test_company_profile_route_renders_timeline_for_real_data():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "Intelligence timeline" in page.text
    assert "not a new record type" in page.text
    assert "ASSESSMENT" in page.text
    assert "RELATIONSHIP" in page.text or "Relationship" in page.text
    assert 'id="intelligence-timeline"' in page.text


def test_variety_profile_route_renders_timeline_for_real_data():
    client = TestClient(app)
    page = client.get("/entities/variety/variety-sekoya-grande")
    assert page.status_code == 200
    assert 'id="intelligence-timeline"' in page.text
    # Complements, does not duplicate, the Variety Intelligence V2 section.
    assert 'id="variety-intelligence"' in page.text


def test_timeline_empty_state_for_sparse_entity_does_not_fabricate():
    client = TestClient(app)
    page = client.get("/entities/variety/variety-amalia-rossa")
    assert page.status_code == 200
    assert 'id="intelligence-timeline"' in page.text


def test_timeline_does_not_leak_pending_or_signal_candidate_content():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    # No pending-review or signal-candidate vocabulary should appear inside
    # the timeline section specifically.
    start = page.text.index('id="intelligence-timeline"')
    end = page.text.index("</section>", start)
    section_html = page.text[start:end]
    assert "in_review" not in section_html
    assert "signal_candidate" not in section_html.lower()
