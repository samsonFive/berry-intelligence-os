"""Presentation Credibility Audit + Executive UX Hardening V1 -- an
Assessment's ai_proposed status must be visible everywhere the Assessment
itself is shown, never silently dropped into a bare "ASSESSMENT" badge
indistinguishable from reviewed analyst judgment. Real production data:
company-planasa is linked to both an AI-proposed and a reviewed
Assessment, so its own pages exercise both badge states."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_planasa_is_linked_to_both_assessment_kinds():
    from app.main import all_assessments

    ass = all_assessments()
    planasa_linked = [a for a in ass if "company-planasa" in (a.get("entity_ids") or [])]
    assert any(a.get("ai_proposed") for a in planasa_linked)
    assert any(not a.get("ai_proposed") for a in planasa_linked)


def test_company_profile_shows_both_ai_proposed_and_reviewed():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text
    assert "REVIEWED" in page.text


def test_company_portfolio_shows_both_ai_proposed_and_reviewed():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text
    assert "REVIEWED" in page.text


def test_company_compare_shows_both_ai_proposed_and_reviewed():
    client = TestClient(app)
    page = client.get("/entities/company/compare?ids=company-planasa,company-costa-group-holdings")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text
    assert "REVIEWED" in page.text


def test_variety_profile_shows_ai_proposed():
    client = TestClient(app)
    page = client.get("/entities/variety/variety-blue-manila")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text


def test_variety_compare_shows_ai_proposed():
    client = TestClient(app)
    page = client.get("/entities/variety/compare?ids=variety-blue-manila,variety-drisblueseventeen")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text


def test_geography_detail_shows_ai_proposed():
    client = TestClient(app)
    page = client.get("/geographies/geography-south-africa")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text


def test_assessment_detail_shows_ai_proposed_badge():
    client = TestClient(app)
    page = client.get("/assessments/assessment-blueberry-genetics-commercialized-through-platforms")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text


def test_assessment_detail_shows_reviewed_badge():
    client = TestClient(app)
    page = client.get("/assessments/assessment-financial-capital-entering-berry-genetics-ownership")
    assert page.status_code == 200
    assert "REVIEWED" in page.text


def test_intelligence_timeline_preserves_assessment_type_label():
    # The shared Timeline row is a mixed chronological list -- unlike the
    # standalone "Assessments" sections, it must keep the "ASSESSMENT" type
    # label alongside the AI PROPOSED / REVIEWED disclosure, since nothing
    # else in that mixed list identifies the record's kind. A deliberate
    # design choice, not a leftover bare badge: see docs/v2/
    # PRESENTATION-CREDIBILITY-AUDIT-V1.md.
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert '<span class="badge badge-assessment">ASSESSMENT</span>' in page.text
    assert "AI PROPOSED" in page.text


def test_company_portfolio_no_bare_none_for_signals():
    client = TestClient(app)
    page = client.get("/entities/company/company-planasa/portfolio")
    assert page.status_code == 200
    assert "<span class=\"v2-meta\">None</span>" not in page.text
    assert "No confirmed Signal captured" in page.text or "Signals: " in page.text


def test_no_forbidden_scoring_language_introduced():
    client = TestClient(app)
    for path in (
        "/entities/company/company-planasa",
        "/entities/company/company-planasa/portfolio",
        "/geographies/geography-south-africa",
    ):
        page = client.get(path)
        lowered = page.text.casefold()
        for forbidden in ("threat score", "market power", "competitive strength score"):
            assert forbidden not in lowered
