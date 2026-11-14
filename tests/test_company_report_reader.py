"""The native company reader preserves the saved report and makes navigation explicit."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.services.report_builder.company_report_reader import (
    MAX_READER_BYTES,
    load_company_report_reader,
    present_authored_company_report,
    present_company_review,
    select_company_reader,
)


@pytest.fixture
def authored():
    return {
        "title": "Example berry developments",
        "subtitle": "Company review",
        "as_of": "2026-11-13",
        "scope": "July through November; original publication and event timing remain distinct.",
        "executive": [{"title": f"Theme {i}", "body": f"Authored theme {i}."} for i in range(1, 5)],
        "companies": [
            {"name": "Example Seeds", "status": "Ready with attribution", "overview": "A named release with a qualified trial result", "platform": "An archived source was inspected.",
             "stories": [{"headline": "Named release announced", "publication_date": "2026-10-02", "event_date": "First sales planned for 2027",
                          "summary": "The company announced a release.", "why_it_matters": "A new option for growers.", "caveat": "A plan is not completed adoption.",
                          "sources": [{"label": "Company announcement", "url": "https://example.org/release"}, {"label": "Trade report", "url": "https://example.net/report"}]}],
             "follow_up": "Ask for independent trial details.", "excluded": "The previous season's launch was outside the window."},
            {"name": "Other Nursery", "status": "Feature lead", "overview": "Current catalogue; no dated substantive launch",
             "stories": [{"headline": "Catalogue remains available", "publication_date": "Undated", "summary": "A present claim only.", "caveat": "Not a first-launch date.",
                          "sources": [{"label": "Catalogue", "url": "https://example.org/release"}]}]},
        ],
        "methodology": ["Platform first; public gaps second."],
        "coverage_notes": ["No finding does not establish inactivity."],
    }


def test_authored_reader_preserves_every_finding_and_material_qualification(authored):
    original = deepcopy(authored)
    reader = present_authored_company_report(authored)
    assert authored == original
    assert reader["company_count"] == 2
    assert reader["story_count"] == 2
    assert reader["source_count"] == 3
    assert reader["unique_source_count"] == 2
    assert reader["executive"] == authored["executive"]
    first = reader["companies"][0]
    assert first["key"] == "example-seeds"
    assert first["overview"] == authored["companies"][0]["overview"]
    assert first["platform"] == authored["companies"][0]["platform"]
    assert first["excluded"] == authored["companies"][0]["excluded"]
    story = first["stories"][0]
    for field in ("headline", "publication_date", "event_date", "summary", "why_it_matters", "caveat"):
        assert story[field] == authored["companies"][0]["stories"][0][field]
    assert reader["companies"][1]["stories"][0]["publication_date"] == "Undated"


def test_company_navigation_has_explicit_current_position_and_boundaries(authored):
    reader = present_authored_company_report(authored)
    overview = select_company_reader(reader)
    assert overview["current_company"] is None and overview["unknown_company"] is False
    first = select_company_reader(reader, "example-seeds")
    assert first["current_company"]["position"] == 1
    assert first["previous_company"] is None
    assert first["next_company"]["name"] == "Other Nursery"
    last = select_company_reader(reader, "other-nursery")
    assert last["previous_company"]["name"] == "Example Seeds"
    assert last["next_company"] is None
    missing = select_company_reader(reader, "not-in-this-report")
    assert missing["current_company"] is None and missing["unknown_company"] is True


def test_duplicate_requested_names_get_unique_navigation_without_losing_rows(authored):
    authored["companies"][1]["name"] = "Example Seeds"
    reader = present_authored_company_report(authored)
    assert [company["key"] for company in reader["companies"]] == ["example-seeds", "example-seeds-2"]
    assert reader["story_count"] == 2


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///private/source", "https://user:secret@example.org/article", "http://127.0.0.1/secret"])
def test_unsafe_source_url_is_never_an_actionable_link_but_source_label_survives(authored, url):
    authored["companies"][0]["stories"][0]["sources"][0]["url"] = url
    source = present_authored_company_report(authored)["companies"][0]["stories"][0]["sources"][0]
    assert source["url"] == "" and source["link_unavailable"]
    assert source["label"] == "Company announcement"


def test_bad_optional_reader_falls_back_without_a_write(authored, tmp_path):
    path = tmp_path / "reader.json"
    path.write_text(json.dumps(authored), encoding="utf-8")
    before = path.read_bytes()
    assert load_company_report_reader(path)["story_count"] == 2
    assert path.read_bytes() == before
    path.write_text('{"companies": []}', encoding="utf-8")
    assert load_company_report_reader(path) is None
    path.write_bytes(b"{" * (MAX_READER_BYTES + 1))
    assert load_company_report_reader(path) is None
    assert load_company_report_reader(None) is None
    assert load_company_report_reader(tmp_path / "absent.json") is None


def test_overflow_is_refused_instead_of_silently_truncating_requested_companies(authored):
    authored["companies"] = [{"name": f"Company {i}", "stories": []} for i in range(101)]
    with pytest.raises(ValueError, match="bounds"):
        present_authored_company_report(authored)


@pytest.fixture
def snapshot():
    return {
        "schema_version": 1, "from_date": "2025-07-01", "through_date": "2026-11-13", "as_of": "2026-11-13", "topic": "Strawberry releases",
        "companies": [
            {"key": "company-one", "requested_name": "Example Seeds", "disposition": "has_findings", "archive_status": "complete", "web_status": "partial", "notes": ["Archive searched before web."]},
            {"key": "company-two", "requested_name": "Unresolved Nursery", "disposition": "identity_unresolved", "notes": ["Identity not resolved."]},
        ],
        "sources": [{"id": "source-one", "title": "Announcement", "url": "https://example.org/announcement", "origin": "archive", "trust_class": "published", "capture_status": "body", "excerpt": "The source's literal passage."}],
        "entries": [
            {"id": "entry-one", "company_key": "company-one", "headline": "Original headline", "published_date": "2026-10-02", "event_date": "2027 planned", "summary": "Original wording.", "news_angle": "Grower access.", "qualification": "Plan remains unconfirmed.", "source_ids": ["source-one"], "included": True, "entry_type": "development", "review_status": "unreviewed", "edits": {"headline": "Analyst's corrected headline", "summary": "Analyst's qualified wording."}},
            {"id": "entry-two", "company_key": "company-two", "headline": "Possible identity match", "published_date": "", "summary": "Unresolved source association.", "qualification": "Do not attribute before resolving identity.", "source_ids": ["source-one"], "included": False, "entry_type": "lead", "review_status": "unreviewed"},
        ],
    }


def test_generated_reader_uses_same_saved_edits_and_keeps_excluded_leads_visible(snapshot):
    original = deepcopy(snapshot)
    reader = present_company_review(snapshot)
    assert snapshot == original
    assert reader["is_working"]
    assert reader["companies"][0]["archive_status_label"] == "Searched within the configured bounds"
    assert reader["companies"][0]["web_status_label"] == "Partial search"
    assert reader["overview_label"] == "Latest reported developments"
    assert reader["executive"][0]["title"] == "Analyst's corrected headline"
    assert len(reader["executive"]) == 1
    story = reader["companies"][0]["stories"][0]
    assert story["summary"] == "Analyst's qualified wording."
    assert story["key"] == "entry-one"
    assert story["analyst_edited"] and story["sources"][0]["excerpt"] == "The source's literal passage."
    lead_company = reader["companies"][1]
    assert lead_company["status"] == "Identity unresolved"
    assert lead_company["stories"][0]["included"] is False
    assert lead_company["stories"][0]["caveat"] == "Do not attribute before resolving identity."


def test_broken_snapshot_source_or_company_reference_is_not_hidden(snapshot):
    snapshot["entries"][0]["source_ids"] = ["missing-source"]
    with pytest.raises(ValueError, match="missing"):
        present_company_review(snapshot)
    snapshot["entries"][0]["source_ids"] = ["source-one"]
    snapshot["entries"][0]["company_key"] = "missing-company"
    with pytest.raises(ValueError, match="no requested company"):
        present_company_review(snapshot)


@pytest.mark.parametrize("identity_status,label", [("unverified", "Unverified directory identity"), ("active", "Identity review required")])
def test_reader_does_not_present_unverified_directory_identity_as_resolved(snapshot, identity_status, label):
    company = snapshot["companies"][1]
    company.update(canonical_name="Possible Nursery Directory Record", resolution="resolved", company_id="company-two",
        identity_status=identity_status, identity_verification_required=True)
    reader = present_company_review(snapshot)
    current = select_company_reader(reader, company["key"])["current_company"]
    assert current["name"] == "Unresolved Nursery"
    assert current["canonical_name"] == "Possible Nursery Directory Record"
    assert current["identity_label"] == current["status"] == label
    assert current["notes"] == ["Identity not resolved."]
    assert current["stories"][0]["included"] is False


def test_saved_editor_text_bounds_remain_readable_without_truncation(snapshot):
    snapshot["entries"][0]["edits"].update(headline="H" * 6000, event_date="E" * 6000)
    reader = present_company_review(snapshot)
    assert reader["executive"][0]["title"] == "H" * 6000
    story = reader["companies"][0]["stories"][0]
    assert story["headline"] == "H" * 6000
    assert story["event_date"] == "E" * 6000


@pytest.fixture
def native_library(authored, tmp_path, monkeypatch):
    import app.main as main
    from fastapi.testclient import TestClient

    root = tmp_path / "library"
    root.mkdir()
    (root / "report.html").write_text("<!doctype html><p>Original exported report</p>", encoding="utf-8")
    (root / "report.pdf").write_bytes(b"%PDF-1.4 original saved export")
    (root / "reader.json").write_text(json.dumps(authored), encoding="utf-8")
    (root / "library.json").write_text(json.dumps({"reports": [{
        "id": "company-review", "title": "Synthetic company review", "subtitle": "A dated review", "summary": "A synthetic test report.",
        "published_date": "2026-11-13", "berry_id": "berry-strawberry", "page_count": 1,
        "files": {"html": "report.html", "pdf": "report.pdf", "reader": "reader.json"},
    }]}), encoding="utf-8")
    monkeypatch.setattr(main, "REPORT_LIBRARY_DIR", root)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("Reading must not initiate research or generation")
    monkeypatch.setattr(main, "maybe_untrusted_completer", forbidden)
    monkeypatch.setattr(main, "_build_packet_and_coverage", forbidden)
    return root, TestClient(main.app)


def test_native_reader_has_overview_company_navigation_and_visible_qualification(native_library):
    root, client = native_library
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    overview = client.get("/reports/library/company-review")
    assert overview.status_code == 200
    assert "<iframe" not in overview.text
    assert "reader-lead-finding" in overview.text and "Theme 1" in overview.text
    assert "Report overview" in overview.text and "Find a company" in overview.text
    assert "Theme 4" in overview.text  # Secondary qualifications still exist.
    company = client.get("/reports/library/company-review?company=example-seeds")
    assert company.status_code == 200
    assert "A plan is not completed adoption." in company.text
    assert 'aria-label="Next company: Other Nursery"' in company.text
    assert 'href="https://example.org/release"' in company.text
    assert "reader-story-qualification" in company.text
    assert client.get("/reports/library/company-review/document").text == "<!doctype html><p>Original exported report</p>"
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


def test_native_reader_escapes_authored_text_and_never_exposes_raw_json(native_library):
    root, client = native_library
    authored = json.loads((root / "reader.json").read_text())
    authored["companies"][0]["stories"][0]["summary"] = '<script>alert("unsafe")</script>'
    (root / "reader.json").write_text(json.dumps(authored), encoding="utf-8")
    response = client.get("/reports/library/company-review?company=example-seeds")
    assert '&lt;script&gt;' in response.text
    assert '<script>alert(' not in response.text
    assert client.get("/reports/library/company-review/reader.json").status_code == 404


def test_malformed_optional_reader_preserves_legacy_artifact_view(native_library):
    root, client = native_library
    (root / "reader.json").write_text("{}", encoding="utf-8")
    response = client.get("/reports/library/company-review")
    assert response.status_code == 200
    assert '<iframe' in response.text
    assert client.get("/reports/library/company-review/download.pdf").content == b"%PDF-1.4 original saved export"


@pytest.mark.parametrize("eligibility,can_include", [("background", True), ("metadata_only", False), ("blocked", False)])
def test_entry_editor_keeps_source_comparison_and_truthful_lead_inclusion(native_library, snapshot, monkeypatch, eligibility, can_include):
    import app.main as main
    from app.services.report_builder import reports_store

    _, client = native_library
    monkeypatch.setattr(main, "_social_eligible_outputs", lambda rows: rows)
    source = snapshot["sources"][0]
    source.update(source_version="retained-version", eligibility=eligibility)
    entry = snapshot["entries"][0]
    entry.update(company_id="company-example", entry_type="lead", included=False)
    snapshot["companies"][0].update(company_id="company-example", resolution="resolved", identity_status="active", identity_verification_required=False)
    record = reports_store.create_report(main.INBOX_DIR, title="Synthetic reviewed report", report_type="company_news_review",
        scope={"company_news_review": snapshot, "version": 1}, sections=[])
    path = main.INBOX_DIR / "reports" / (record["id"] + ".json")
    before = path.read_bytes()
    response = client.get(f"/reports/{record['id']}/company-news/entry/{entry['id']}")
    assert response.status_code == 200
    assert "Retained sources" in response.text and "The source&#39;s literal passage." in response.text
    assert ('name="included"' in response.text) is can_include
    if can_include:
        assert "Include as a reporting lead after review" in response.text
        assert "It remains labelled as a reporting lead." in response.text
    assert path.read_bytes() == before
