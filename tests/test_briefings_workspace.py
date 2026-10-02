"""Reporting-family continuity, deliberate provider work and private boundaries."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.main as main
from app.services.report_builder.reports_store import create_report, load_report


def no_provider(*args, **kwargs):
    raise AssertionError("Browsing must not initialize or call an external provider")


def test_meeting_scope_keeps_repeated_and_csv_selections():
    request = Request({"type": "http", "method": "GET", "path": "/war-room", "headers": [], "query_string": b"berry=blueberry&company_ids=company-planasa,company-hortifrut&company_ids=company-planasa&company_ids=company-fall-creek&geography_ids=geography-peru&geography_ids=geography-china&days=7"})
    scope = main._war_room_scope_from_params(request)
    assert scope.company_ids == ("company-planasa", "company-hortifrut", "company-fall-creek")
    assert scope.geography_ids == ("geography-peru", "geography-china")
    assert scope.berry_id == "berry-blueberry"
    assert scope.window_days == 7


def test_browsing_meeting_and_hub_never_starts_provider(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "maybe_untrusted_completer", no_provider)
    monkeypatch.setattr(main, "_radar_edition_live", no_provider)
    monkeypatch.setattr(main, "_compute_nav_work_counts", no_provider)
    client = TestClient(main.app)
    hub = client.get("/briefings")
    assert hub.status_code == 200
    for href in ("/war-room", "/brief-pack", "/brief-packs", "/reports/new", "/explorer", "/readout", "/news-packets"):
        assert f'href="{href}"' in hub.text
    meeting = client.get("/war-room?berry=blueberry&company_ids=company-planasa")
    assert meeting.status_code == 200
    assert "Meeting Prep" in meeting.text
    assert "SUGGESTED DISCUSSION QUESTIONS" in meeting.text
    assert not list(tmp_path.glob("war_room_sessions/*.json"))


def test_old_refresh_bookmark_is_confirmation_and_post_preserves_scope(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "_radar_edition_live", lambda: calls.append("refresh"))
    client = TestClient(main.app)
    url = "/war-room/live?berry=blueberry&company_ids=company-planasa&company_ids=company-hortifrut&days=7"
    page = client.get(url)
    assert page.status_code == 200
    assert "Refresh the saved feeds?" in page.text
    assert calls == []
    response = client.post(url, follow_redirects=False)
    assert calls == ["refresh"]
    assert response.status_code == 303
    assert response.headers["location"] == url.replace("/live", "")


def test_ai_question_generation_requires_explicit_post(monkeypatch):
    calls = []
    original = main._compose_war_room_for_request

    def compose(scope, *, generate_questions=False):
        calls.append(generate_questions)
        return original(scope, generate_questions=False)

    monkeypatch.setattr(main, "_compose_war_room_for_request", compose)
    client = TestClient(main.app)
    assert client.get("/war-room?berry=blueberry").status_code == 200
    assert client.post("/war-room/questions?berry=blueberry").status_code == 200
    assert calls == [False, True]
    assert client.get("/war-room/questions?berry=blueberry").status_code == 405
    assert client.post("/war-room/questions").status_code == 422


@pytest.mark.parametrize("method,path", [
    ("get", "/briefings"), ("get", "/brief-pack"), ("get", "/brief-packs"),
    ("get", "/reports"), ("get", "/reports/new"), ("get", "/reports/rp-private/export.pdf"),
    ("get", "/war-room"), ("get", "/war-room/live"), ("post", "/war-room/live"),
    ("post", "/war-room/notes"), ("post", "/war-room/questions"),
    ("post", "/brief-packs/save"), ("post", "/reports/new"),
])
def test_private_reporting_stores_and_actions_fail_closed_in_readonly(monkeypatch, method, path):
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(main, "maybe_untrusted_completer", no_provider)
    assert getattr(TestClient(main.app), method)(path).status_code == 403


def test_edited_report_stays_in_working_library_and_export_uses_edit(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "maybe_untrusted_completer", no_provider)
    record = create_report(tmp_path, title="Before edit", report_type="company_brief", scope={"company_ids": ["company-planasa"], "berry_id": "berry-blueberry"}, sections=[{"section_id": "summary", "title": "Summary", "generated_prose": "Original draft", "edited_prose": None, "citation_ids": [], "status": "unavailable"}])
    client = TestClient(main.app)
    response = client.post(f"/reports/{record['id']}/save", data={"title": "Edited working report", "section_ids": ["summary"], "section_texts": ["Analyst takeaway preserved"]}, follow_redirects=False)
    assert response.status_code == 303
    reopened = client.get(response.headers["location"])
    assert reopened.status_code == 200
    assert "Analyst takeaway preserved" in reopened.text
    assert "Edited working report" in client.get("/reports").text
    assert "Edited working report" not in client.get("/reports?status=draft").text
    assert "Edited working report" in client.get("/reports?status=active").text
    persisted = load_report(tmp_path, record["id"])
    assert persisted["sections"][0]["generated_prose"] == "Original draft"
    assert persisted["sections"][0]["edited_prose"] == "Analyst takeaway preserved"
    export = client.get(f"/reports/{record['id']}/export.pdf")
    assert export.status_code == 200 and export.content.startswith(b"%PDF")
    assert export.headers["content-type"] == "application/pdf"
    assert load_report(tmp_path, record["id"]) == persisted
    assert client.get("/reports?status=unknown").status_code == 422


def test_report_named_selections_preserve_repeated_and_csv_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "maybe_untrusted_completer", no_provider)
    client = TestClient(main.app)
    start = client.get("/reports/new?company_ids=company-planasa&geography_ids=geography-peru")
    assert start.status_code == 200
    assert 'name="company_ids" value="company-planasa" checked' in start.text
    assert 'name="geography_ids" value="geography-peru" checked' in start.text
    assert "Company ids (comma-separated)" not in start.text
    preview = client.post("/reports/new", data={"step": "preview", "report_type": "decision_memo", "company_ids": ["company-planasa", "company-hortifrut,company-planasa"], "geography_ids": ["geography-peru", "geography-china"], "date_window_days": "7"})
    assert preview.status_code == 200
    assert 'name="company_ids" value="company-planasa,company-hortifrut"' in preview.text
    assert 'name="geography_ids" value="geography-peru,geography-china"' in preview.text
    assert not list(tmp_path.glob("reports/*.json"))


def test_pdf_preserves_line_breaks_and_deliberately_empty_edits(monkeypatch):
    from app.services.report_builder import pdf_export
    rendered = []
    original = pdf_export.Paragraph

    def paragraph(text, style):
        rendered.append((text, style.name))
        return original(text, style)

    monkeypatch.setattr(pdf_export, "Paragraph", paragraph)
    report = {"title": "Report <sample>", "scope": {"berry_id": "berry-blueberry"}, "sections": [
        {"title": "Edited", "generated_prose": "Old wording must not return", "edited_prose": "", "status": "unavailable"},
        {"title": "List", "generated_prose": "Old", "edited_prose": "First <source>\nSecond & source", "status": "unavailable"},
    ]}
    assert pdf_export.render_report_pdf(report, {}, {}).startswith(b"%PDF")
    assert ("Report &lt;sample&gt;", "ReportTitle") in rendered
    assert ("Berry: Blueberry", "ReportMeta") in rendered
    assert ("First &lt;source&gt;<br/>Second &amp; source", "ReportBody") in rendered
    assert not any("Old wording" in text for text, _ in rendered)


def test_report_display_hides_generated_internal_prefixes_without_changing_edits():
    from copy import deepcopy
    from app.services.report_builder.presentation import section_text
    packet = {"signals": [{"id": "sig-1", "title": "Momentum"}], "known_ids": {"sig-1"}}
    section = {"section_id": "signals", "status": "structured", "generated_prose": "[sig-1] Momentum — proposed\n[Analyst qualifier] Keep this", "edited_prose": None}
    snapshot = deepcopy(section)
    assert section_text(section, packet) == "Momentum — proposed\n[Analyst qualifier] Keep this"
    assert section == snapshot
    section["edited_prose"] = "[sig-1] My deliberately written note"
    assert section_text(section, packet) == section["edited_prose"]
    section["edited_prose"] = ""
    assert section_text(section, packet) == ""


def test_save_only_changes_edited_fields_and_preserves_explicit_clear(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "maybe_untrusted_completer", no_provider)
    record = create_report(tmp_path, title="Edit preservation", report_type="company_brief", scope={}, sections=[
        {"section_id": "summary", "title": "Summary", "generated_prose": "Original summary", "edited_prose": None, "citation_ids": [], "status": "structured"},
        {"section_id": "signals", "title": "Signals", "generated_prose": "[sig-1] Momentum", "edited_prose": None, "citation_ids": [], "status": "structured"},
    ])
    monkeypatch.setattr(main, "_build_packet_and_coverage", lambda scope: ({"known_ids": {"sig-1"}}, {}))
    client = TestClient(main.app)
    response = client.post(f"/reports/{record['id']}/save", data={"title": record["title"], "section_ids": ["summary", "signals"], "section_texts": ["", "Momentum"]}, follow_redirects=False)
    assert response.status_code == 303
    sections = load_report(tmp_path, record["id"])["sections"]
    assert sections[0]["edited_prose"] == ""
    assert sections[1]["edited_prose"] is None
    assert sections[1]["generated_prose"] == "[sig-1] Momentum"
