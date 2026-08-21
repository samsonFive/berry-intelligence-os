"""Assessment berry scope is stored market_ids only — never inferred."""

from __future__ import annotations

from app.main import BERRIES, all_assessments
from app.services.assessment_scope import (
    SCOPE_BERRY_SPECIFIC,
    SCOPE_MULTI_BERRY,
    SCOPE_UNSCOPED,
    assessment_berry_scope,
    attach_assessment_scope,
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
