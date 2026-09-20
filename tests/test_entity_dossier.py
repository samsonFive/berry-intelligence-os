from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.entity_dossier import (
    build_dossier,
    decide_proposal,
    launch_gap_research,
)
from app.services.feed_first import (
    apply_decision,
    load_state,
    mutate_statement,
    mutate_statements,
    statements_for_entity,
    trusted_statements,
)
from app.services.feed_first_trust import confirm_feed_statement


ENTITY_ID = "company-fall-creek-farm-and-nursery"


def _record() -> dict:
    passage = (
        "Fall Creek Farm & Nursery marked 10 years of operations in Spain. "
        "The nursery expanded to 14 million blueberry plants in 2026."
    )
    return {
        "id": "ev-dossier-representative",
        "record_type": "evidence",
        "status": "published",
        "title": "Fall Creek Spain reaches 14 million blueberry plants",
        "summary": "Fall Creek reports nursery expansion in Spain.",
        "source_name": "FreshPlaza",
        "source_url": "https://example.test/fall-creek-spain",
        "source_type": "trade_press",
        "published_date": "2026-05-26",
        "captured_date": "2026-05-26",
        "entity_ids": [ENTITY_ID],
        "berry_ids": ["berry-blueberry"],
        "geography_ids": ["geography-spain"],
        "article": {"paragraphs": [{"index": 0, "text": passage}]},
    }


def _plant_rights_record() -> dict:
    return {
        "id": "ev-cfia-pbr-blue-ribbon",
        "record_type": "evidence",
        "status": "published",
        "source_type": "plant_breeders_rights_record",
        "title": "Plant Breeders' Rights record - Blue Ribbon",
        "source_name": "Canadian Food Inspection Agency",
        "source_url": "https://example.test/pbr/blue-ribbon",
        "entity_ids": [ENTITY_ID],
        "summary": (
            "Canadian plant breeders' rights record for Blue Ribbon. "
            "Application 12-7574 dated 2012-03-26, granted 2016-11-12, "
            "certificate 5369, expiring 2036-11-12."
        ),
    }


def _entity() -> dict:
    return {
        "id": ENTITY_ID,
        "record_type": "entity",
        "entity_type": "company",
        "name": "Fall Creek Farm & Nursery",
        "status": "active",
        "roles": ["breeder", "nursery"],
        "berry_ids": ["berry-blueberry"],
    }


def test_thumbsup_stages_recoverable_candidates_without_trusting(tmp_path: Path):
    result = apply_decision(
        tmp_path,
        item_id=_record()["id"],
        action="thumbs_up",
        evidence=[_record()],
    )
    assert result["decision"]["reaction"] == "up"
    assert result["statements"]
    assert {row["statement_state"] for row in result["statements"]} == {
        "pending_confirmation"
    }
    locator = result["statements"][0]["support_locators"][0]
    exact = result["statements"][0]["supporting_passages"][0]
    full = _record()["article"]["paragraphs"][0]["text"]
    assert locator["medium"] == "article_paragraph"
    assert locator["paragraph_index"] == 0
    assert full[locator["start_offset"] : locator["end_offset"]] == exact
    assert locator["exact"] == exact
    state = load_state(tmp_path)
    assert statements_for_entity(state, ENTITY_ID) == []
    assert trusted_statements(state) == []
    assert state["reaction_events"][0]["purpose"] == "ranking_feedback"


def test_confirmation_is_the_only_dossier_transition(tmp_path: Path):
    staged = apply_decision(
        tmp_path,
        item_id=_record()["id"],
        action="thumbs_up",
        evidence=[_record()],
    )
    first = staged["statements"][0]
    confirmed = mutate_statement(
        tmp_path,
        statement_id=first["id"],
        action="confirm",
        canonical_fact_id="fact-gate1-confirmed",
    )
    assert confirmed is not None
    assert confirmed["statement_state"] == "trusted_analyst"
    projected = statements_for_entity(load_state(tmp_path), ENTITY_ID)
    assert [row["id"] for row in projected] == [first["id"]]
    assert confirmed["decision_history"][-1]["surface"] == "reader_evidence_lens"

    retracted = mutate_statement(
        tmp_path,
        statement_id=first["id"],
        action="retract",
    )
    assert retracted is not None
    assert retracted["statement_state"] == "removed"
    assert statements_for_entity(load_state(tmp_path), ENTITY_ID) == []


def test_confirm_selected_batch_does_not_confirm_unselected(tmp_path: Path):
    staged = apply_decision(
        tmp_path,
        item_id=_record()["id"],
        action="thumbs_up",
        evidence=[_record()],
    )
    ids = [row["id"] for row in staged["statements"]]
    updated = mutate_statements(
        tmp_path,
        statement_ids=ids[:1],
        action="confirm",
        canonical_fact_ids={ids[0]: "fact-gate1-batch"},
    )
    assert [row["statement_state"] for row in updated] == ["trusted_analyst"]
    all_rows = load_state(tmp_path)["statements"][_record()["id"]]
    assert all_rows[0]["statement_state"] == "trusted_analyst"
    assert all(
        row["statement_state"] == "pending_confirmation" for row in all_rows[1:]
    )


def test_dossier_projects_confirmed_facts_and_honest_assessment(tmp_path: Path):
    staged = apply_decision(
        tmp_path,
        item_id=_record()["id"],
        action="thumbs_up",
        evidence=[_record()],
    )
    mutate_statement(
        tmp_path,
        statement_id=staged["statements"][0]["id"],
        action="confirm",
        canonical_fact_id="fact-gate1-dossier",
    )
    dossier = build_dossier(
        entity_id=ENTITY_ID,
        entity=_entity(),
        profile={
            "canonical_name": "Fall Creek Farm & Nursery",
            "official_website": "https://www.fallcreeknursery.com/",
            "crops": ["blueberry"],
        },
        state=load_state(tmp_path),
    )
    assert dossier["recent_changes"]
    assert dossier["statement_groups"]["scale-performance"]
    assert dossier["assessment"]["state"] == "insufficient_evidence"
    assert dossier["coverage"]["applicable"] == 8
    assert dossier["registry_version"] == "1.0.0"


def test_targeted_existing_corpus_research_stays_proposed_until_approval(
    tmp_path: Path,
):
    result = launch_gap_research(
        tmp_path,
        entity_id=ENTITY_ID,
        question_id="entity.performance.plants_sold",
        evidence=[_record()],
    )
    assert result["run"]["scope"] == "one_entity_one_question_existing_corpus"
    assert result["run"]["provider_calls"] == 0
    assert result["proposal"]["statement_state"] == "proposed"
    assert statements_for_entity(load_state(tmp_path), ENTITY_ID) == []

    approved = decide_proposal(
        tmp_path,
        proposal_id=result["proposal"]["id"],
        action="approve",
        canonical_fact_id="fact-gate1-research",
    )
    assert approved is not None
    assert approved["statement_state"] == "trusted_analyst"
    projected = statements_for_entity(load_state(tmp_path), ENTITY_ID)
    assert projected[0]["origin"] == "autonomous_gap_research"
    assert projected[0]["evidence_id"] == _record()["id"]


def test_plants_sold_research_rejects_pbr_numbers_and_selects_quantity_headline(
    tmp_path: Path,
):
    valid_headline = _record()
    valid_headline["article"] = {"paragraphs": []}
    result = launch_gap_research(
        tmp_path,
        entity_id=ENTITY_ID,
        question_id="entity.performance.plants_sold",
        evidence=[_plant_rights_record(), valid_headline],
    )

    assert result["proposal"]["evidence_id"] == valid_headline["id"]
    assert result["proposal"]["statement_text"] == valid_headline["title"]
    assert result["proposal"]["support_locators"][0]["medium"] == "headline"


def test_plants_sold_research_returns_no_evidence_for_pbr_record(tmp_path: Path):
    result = launch_gap_research(
        tmp_path,
        entity_id=ENTITY_ID,
        question_id="entity.performance.plants_sold",
        evidence=[_plant_rights_record()],
    )

    assert result["run"]["status"] == "searched_no_evidence"
    assert result["proposal"] is None


def test_company_route_renders_wide_living_dossier():
    page = TestClient(app).get(f"/entities/company/{ENTITY_ID}")
    assert page.status_code == 200
    assert "data-entity-dossier" in page.text
    assert "Identity & footprint" in page.text
    assert "Activity & scale" in page.text
    assert "Competitive posture" in page.text
    assert "Vulnerabilities" in page.text
    assert "What changed" in page.text
    assert "No 151×75 sweep" in page.text
    assert "bos-entity-logo" in page.text
    assert "data-archetype=\"specialist_breeder_nursery\"" in page.text


def test_dossier_nav_wraps_without_horizontal_scrolling():
    css = Path("app/static/berry_os.css").read_text(encoding="utf-8")
    assert ".bos-dossier-outline" in css
    assert "grid-template-columns: repeat(7, minmax(0, 1fr))" in css
    assert "overflow: visible" in css


def test_gate2_archetypes_route_questions_and_sections_differently():
    state = {"statements": {}, "research_proposals": {}, "research_runs": {}}
    planasa = build_dossier(
        entity_id="company-planasa",
        entity={
            "roles": ["breeder", "nursery", "plant_producer"],
            "attributes": {"ownership": "private"},
        },
        profile={"seed_entity_type": "private company", "crops": ["strawberry"]},
        state=state,
    )
    fall_creek = build_dossier(
        entity_id=ENTITY_ID,
        entity=_entity(),
        profile={"seed_entity_type": "private company", "crops": ["blueberry"]},
        state=state,
    )
    university = build_dossier(
        entity_id="company-university-of-florida",
        entity={
            "roles": ["public_research_institution", "breeder"],
            "attributes": {"sector": "public_research"},
        },
        profile={},
        state=state,
    )
    hortifrut = build_dossier(
        entity_id="company-hortifrut",
        entity={
            "roles": [
                "grower",
                "marketer",
                "breeding_joint_venture_partner",
                "genetics_licensee",
            ]
        },
        profile={"seed_entity_type": "public company"},
        state=state,
    )
    registry = build_dossier(
        entity_id="seed-org-0147",
        entity={},
        profile={"is_registry": True, "seed_entity_type": "registry"},
        state=state,
    )

    assert planasa["archetype"] == "integrated_private_genetics"
    assert fall_creek["archetype"] == "specialist_breeder_nursery"
    assert university["archetype"] == "public_research_program"
    assert hortifrut["archetype"] == "grower_marketer_genetics"
    assert registry["archetype"] == "registry_source_system"
    assert registry["competitor_eligible"] is False
    assert "competitive-assessment" not in registry["applicable_section_ids"]
    assert "scale-performance" not in university["applicable_section_ids"]
    assert "genetics-cultivars" not in hortifrut["applicable_section_ids"]

    question_states = {
        dossier["archetype"]: {
            row["id"]: row["answer_state"] for row in dossier["questions"]
        }
        for dossier in (planasa, fall_creek, university, hortifrut, registry)
    }
    assert (
        question_states["integrated_private_genetics"][
            "entity.performance.plants_sold"
        ]
        != "not_applicable"
    )
    assert (
        question_states["public_research_program"][
            "entity.performance.plants_sold"
        ]
        == "not_applicable"
    )
    assert (
        question_states["registry_source_system"]["entity.activity.berry_roles"]
        == "not_applicable"
    )


def test_gate2_real_archetype_routes_are_queryable_and_distinct():
    routes = {
        "/entities/company/company-planasa": "integrated_private_genetics",
        "/entities/company/company-university-of-florida": "public_research_program",
        "/entities/company/company-hortifrut": "grower_marketer_genetics",
        "/entities/company/seed-org-0147": "registry_source_system",
    }
    client = TestClient(app)
    for route, archetype in routes.items():
        page = client.get(route)
        assert page.status_code == 200
        assert f'data-archetype="{archetype}"' in page.text
    registry = client.get("/entities/company/seed-org-0147")
    assert "Excluded from competitor counts" in registry.text
    assert 'id="competitive-assessment"' not in registry.text
    assert "Competitive posture" not in registry.text
    assert "Vulnerabilities" not in registry.text


def test_canonical_bridge_reuses_existing_published_evidence():
    record = _record()
    evidence = {record["id"]: record}
    repositories = SimpleNamespace(
        evidence=SimpleNamespace(get=lambda record_id: evidence.get(record_id)),
        entities=SimpleNamespace(list=lambda: [_entity()]),
    )

    class Service:
        request = None

        def approve_claim(self, request):
            self.request = request
            return SimpleNamespace(
                ok=True,
                fact_id="fact-canonical-existing",
                schema_errors=[],
            )

    service = Service()
    fact_id = confirm_feed_statement(
        service=service,
        repositories=repositories,
        record=record,
        statement={
            "statement_text": "The nursery expanded to 14 million blueberry plants in 2026.",
            "original_extraction_text": "The nursery expanded to 14 million blueberry plants in 2026.",
            "entity_ids": [ENTITY_ID],
        },
        reviewer="johnny",
    )
    assert fact_id == "fact-canonical-existing"
    assert service.request.evidence_id == record["id"]
    assert service.request.origin == "feed_thumbsup_extraction"


def test_canonical_bridge_publishes_live_item_and_fact_together():
    record = {**_record(), "id": "live-fall-creek-14m", "status": "live"}
    evidence: dict[str, dict] = {}
    repositories = SimpleNamespace(
        evidence=SimpleNamespace(get=lambda record_id: evidence.get(record_id)),
        entities=SimpleNamespace(list=lambda: [_entity()]),
    )

    class Service:
        def publish(self, request):
            evidence[request.draft_id] = {
                "id": request.draft_id,
                "status": "published",
                "fact_ids": [f"fact-{request.draft_id[3:]}-1"],
            }
            return SimpleNamespace(
                ok=True,
                evidence_id=request.draft_id,
                schema_errors=[],
                conflicts=[],
            )

    fact_id = confirm_feed_statement(
        service=Service(),
        repositories=repositories,
        record=record,
        statement={
            "statement_text": "The nursery expanded to 14 million blueberry plants in 2026.",
            "original_extraction_text": "The nursery expanded to 14 million blueberry plants in 2026.",
            "entity_ids": [ENTITY_ID],
        },
        reviewer="johnny",
    )
    assert fact_id.startswith("fact-feed-")
    assert len(evidence) == 1
