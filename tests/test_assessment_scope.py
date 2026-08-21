"""Assessment berry scope is stored market_ids only — never inferred."""

from __future__ import annotations

from pathlib import Path

from app import main
from app.main import BERRIES, all_assessments
from app.services.assessment_scope import (
    SCOPE_BERRY_SPECIFIC,
    SCOPE_MULTI_BERRY,
    SCOPE_UNSCOPED,
    assessment_berry_scope,
    attach_assessment_scope,
    parse_assessment_market_ids,
)
from fastapi.testclient import TestClient

from app.main import app

UNSCOPED_ID = "assessment-financial-capital-entering-berry-genetics-ownership"
BLUEBERRY_IDS = {
    "assessment-public-trait-claims-not-yet-comparable",
    "assessment-blueberry-genetics-commercialized-through-platforms",
    "assessment-southern-africa-licensing-enforcement",
    "assessment-public-observability-varies-by-breeder",
}


def test_live_assessments_classify_from_stored_market_ids() -> None:
    rows = {record["id"]: assessment_berry_scope(record, BERRIES) for record in all_assessments()}
    assert set(rows) == BLUEBERRY_IDS | {UNSCOPED_ID}
    assert rows[UNSCOPED_ID]["kind"] == SCOPE_UNSCOPED
    assert rows[UNSCOPED_ID]["berry_ids"] == []
    for assessment_id in BLUEBERRY_IDS:
        assert rows[assessment_id]["kind"] == SCOPE_BERRY_SPECIFIC
        assert rows[assessment_id]["berry_ids"] == ["berry-blueberry"]
        assert rows[assessment_id]["label"] == "Blueberry"
    assert not any(row["kind"] == SCOPE_MULTI_BERRY for row in rows.values())


def test_scope_does_not_infer_from_title_or_company_names() -> None:
    record = {
        "id": "assessment-synthetic-unscoped",
        "title": "Blueberry genetics ownership at Driscoll's strawberry programs",
        "rationale": "Mentions blueberry and strawberry in prose.",
        "entity_ids": ["company-driscolls"],
        "market_ids": [],
    }
    scope = assessment_berry_scope(record, BERRIES)
    assert scope["kind"] == SCOPE_UNSCOPED
    multi = assessment_berry_scope(
        {**record, "market_ids": ["berry-blueberry", "berry-strawberry"]},
        BERRIES,
    )
    assert multi["kind"] == SCOPE_MULTI_BERRY
    assert multi["berry_ids"] == ["berry-blueberry", "berry-strawberry"]


def test_company_bottom_line_labels_unscoped_and_does_not_hide() -> None:
    strawberry = TestClient(app)
    strawberry.cookies.set("bios_berry", "berry-strawberry")
    page = strawberry.get("/entities/company/company-driscolls")
    assert page.status_code == 200
    html = page.text
    assert UNSCOPED_ID in html
    assert "Company-wide / unscoped" in html
    assert "v2-mark-scope-unscoped" in html
    attached = attach_assessment_scope(all_assessments(), BERRIES)
    unscoped = next(row for row in attached if row["id"] == UNSCOPED_ID)
    assert "company-driscolls" in (unscoped.get("entity_ids") or [])


def test_assessment_list_and_detail_show_scope() -> None:
    client = TestClient(app)
    listing = client.get("/assessments")
    assert listing.status_code == 200
    assert "v2-assessment-list" in listing.text
    assert "Company-wide / unscoped" in listing.text
    assert "Blueberry" in listing.text
    detail = client.get(f"/assessments/{UNSCOPED_ID}")
    assert detail.status_code == 200
    assert "Berry scope" in detail.text
    assert "Company-wide / unscoped" in detail.text
    assert "Would change our view" in detail.text
    assert "Signal confirmation does not create this record" in detail.text
    blueberry = client.get("/assessments/assessment-southern-africa-licensing-enforcement")
    assert blueberry.status_code == 200
    assert "Blueberry" in blueberry.text


def test_parse_assessment_market_ids_keeps_only_known_berries() -> None:
    assert parse_assessment_market_ids([]) == []
    assert parse_assessment_market_ids(None) == []
    assert parse_assessment_market_ids(["berry-raspberry", "not-a-berry", "berry-blueberry", "berry-raspberry"]) == [
        "berry-blueberry",
        "berry-raspberry",
    ]


def _isolate_authoring(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox" / "evidence").mkdir(parents=True)
    (tmp_path / "data" / "configuration").mkdir(parents=True)
    (tmp_path / "data" / "facts").mkdir(parents=True)
    (tmp_path / "data" / "assessments").mkdir(parents=True)
    (tmp_path / "data" / "entities").mkdir(parents=True)
    (tmp_path / "data" / "evidence").mkdir(parents=True)
    (tmp_path / "data" / "configuration" / "sources.json").write_text("[]\n", encoding="utf-8")
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    repos.facts.create(
        {
            "id": "fact-scope-authoring",
            "record_type": "fact",
            "statement": "A supporting fact for scope authoring tests.",
            "classification": "fact",
            "confidence": "high",
            "status": "active",
            "reviewer": "fixture",
            "created_at": "2026-08-21",
            "evidence_ids": ["ev-scope-authoring"],
            "entity_ids": ["company-scope-authoring"],
        }
    )
    repos.entities.create(
        {
            "id": "company-scope-authoring",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Scope Authoring Co",
            "status": "active",
        }
    )


def _create_payload(**overrides) -> dict:
    payload = {
        "title": "Scope authoring fixture",
        "rationale": "Mentions blueberry in prose but that must not become scope.",
        "status": "active",
        "confidence": "medium",
        "fact_ids": "fact-scope-authoring",
        "signal_ids": "",
        "evidence_ids": "",
        "entity_ids": "company-scope-authoring",
        "strategic_question_ids": "",
        "counterevidence_ids": "",
        "reviewer": "analyst-fixture",
    }
    payload.update(overrides)
    return payload


def test_assessment_form_writes_optional_market_ids(monkeypatch, tmp_path: Path) -> None:
    _isolate_authoring(monkeypatch, tmp_path)
    client = TestClient(app)
    form = client.get("/assessments/new")
    assert form.status_code == 200
    assert 'name="market_ids"' in form.text
    assert 'value="berry-blueberry"' in form.text
    assert 'value="berry-strawberry"' in form.text
    assert 'value="berry-raspberry"' in form.text
    assert 'value="berry-blackberry"' in form.text
    missing_facts = client.post("/assessments", data=_create_payload(fact_ids=""), follow_redirects=False)
    assert missing_facts.status_code == 400
    assert "At least one supporting fact id is required" in missing_facts.text

    unscoped = client.post("/assessments", data=_create_payload(), follow_redirects=False)
    assert unscoped.status_code == 303
    unscoped_id = unscoped.headers["location"].rsplit("/", 1)[-1]
    unscoped_record = main.assessment_by_id(unscoped_id)
    assert unscoped_record is not None
    assert "market_ids" not in unscoped_record
    assert assessment_berry_scope(unscoped_record, BERRIES)["kind"] == SCOPE_UNSCOPED

    one = client.post(
        "/assessments",
        data=_create_payload(title="Blueberry-specific fixture", market_ids=["berry-blueberry"]),
        follow_redirects=False,
    )
    assert one.status_code == 303
    one_id = one.headers["location"].rsplit("/", 1)[-1]
    one_record = main.assessment_by_id(one_id)
    assert one_record["market_ids"] == ["berry-blueberry"]
    assert one_record["fact_ids"] == ["fact-scope-authoring"]
    assert assessment_berry_scope(one_record, BERRIES)["kind"] == SCOPE_BERRY_SPECIFIC

    multi = client.post(
        "/assessments",
        data=_create_payload(
            title="Multi-berry fixture",
            market_ids=["berry-strawberry", "berry-blueberry", "not-a-berry"],
        ),
        follow_redirects=False,
    )
    assert multi.status_code == 303
    multi_id = multi.headers["location"].rsplit("/", 1)[-1]
    multi_record = main.assessment_by_id(multi_id)
    assert multi_record["market_ids"] == ["berry-blueberry", "berry-strawberry"]
    assert assessment_berry_scope(multi_record, BERRIES)["kind"] == SCOPE_MULTI_BERRY


def test_assessment_edit_round_trips_stored_scope(monkeypatch, tmp_path: Path) -> None:
    _isolate_authoring(monkeypatch, tmp_path)
    client = TestClient(app)
    created = client.post(
        "/assessments",
        data=_create_payload(title="Round-trip scope", market_ids=["berry-blueberry"]),
        follow_redirects=False,
    )
    assessment_id = created.headers["location"].rsplit("/", 1)[-1]
    edit = client.get(f"/assessments/{assessment_id}/edit")
    assert edit.status_code == 200
    assert 'name="market_ids"' in edit.text
    assert 'value="berry-blueberry"' in edit.text
    assert "checked" in edit.text
    company = client.get("/entities/company/company-scope-authoring")
    assert company.status_code == 200
    assert "v2-mark-scope-berry_specific" in company.text
    assert "Blueberry" in company.text

    widened = client.post(
        f"/assessments/{assessment_id}",
        data=_create_payload(title="Round-trip scope", market_ids=["berry-blueberry", "berry-raspberry"]),
        follow_redirects=False,
    )
    assert widened.status_code == 303
    stored = main.assessment_by_id(assessment_id)
    assert stored["market_ids"] == ["berry-blueberry", "berry-raspberry"]
    assert stored["fact_ids"] == ["fact-scope-authoring"]
    assert stored["created_at"]
    company_multi = client.get("/entities/company/company-scope-authoring")
    assert "v2-mark-scope-multi_berry" in company_multi.text
    assert "Multi-berry" in company_multi.text

    cleared = client.post(
        f"/assessments/{assessment_id}",
        data=_create_payload(title="Round-trip scope"),
        follow_redirects=False,
    )
    assert cleared.status_code == 303
    unscoped = main.assessment_by_id(assessment_id)
    assert "market_ids" not in unscoped
    assert assessment_berry_scope(unscoped, BERRIES)["kind"] == SCOPE_UNSCOPED
    company_unscoped = client.get("/entities/company/company-scope-authoring")
    assert "v2-mark-scope-unscoped" in company_unscoped.text
    assert "Company-wide / unscoped" in company_unscoped.text
    detail = client.get(f"/assessments/{assessment_id}")
    assert "Company-wide / unscoped" in detail.text
    assert "Mentions blueberry in prose" in detail.text
