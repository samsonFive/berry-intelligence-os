from __future__ import annotations

from pathlib import Path

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
    updated = mutate_statements(tmp_path, statement_ids=ids[:1], action="confirm")
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
        question_id="entity.geography.headquarters",
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
    )
    assert approved is not None
    assert approved["statement_state"] == "trusted_analyst"
    projected = statements_for_entity(load_state(tmp_path), ENTITY_ID)
    assert projected[0]["origin"] == "autonomous_gap_research"
    assert projected[0]["evidence_id"] == _record()["id"]


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
