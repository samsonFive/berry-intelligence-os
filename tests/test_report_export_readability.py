"""Readable sparse exports preserve edits, source trace and external review status."""
from copy import deepcopy

from app.services.report_builder import pdf_export


def capture(monkeypatch):
    rendered = []
    original = pdf_export.Paragraph

    def paragraph(text, style, **kwargs):
        rendered.append((text, style.name))
        return original(text, style, **kwargs)

    monkeypatch.setattr(pdf_export, "Paragraph", paragraph)
    return rendered


def test_unfinished_sections_are_one_checklist_and_edits_stay_literal(monkeypatch):
    rendered = capture(monkeypatch)
    report = {"title": "Company brief", "sections": [
        {"section_id": "executive_summary", "title": "Executive summary", "status": "ai_draft", "generated_prose": "Old generated wording", "edited_prose": "Analyst takeaway preserved."},
        {"section_id": "market_context", "title": "Market context", "status": "unavailable", "generated_prose": "AI unavailable -- provider credential missing", "edited_prose": None},
        {"section_id": "variety_context", "title": "Variety context", "status": "unsupported", "generated_prose": "No sourced trial result was recorded.", "edited_prose": None},
        {"section_id": "empty", "title": "Deliberately blank", "status": "unavailable", "generated_prose": "Do not restore this", "edited_prose": ""},
    ]}
    before = deepcopy(report)
    assert pdf_export.render_report_pdf(report, {}, {}).startswith(b"%PDF")
    texts = [text for text, _ in rendered]
    assert "Incomplete working report: 2 sections still to prepare." in texts
    assert texts.count("Still to prepare") == 1
    assert ("Market context", "ReportH2") not in rendered
    assert "Not drafted" in texts and "No sourced trial result was recorded." in texts
    assert ("Analyst takeaway preserved.", "ReportTakeaway") in rendered
    assert ("Deliberately blank", "ReportH2") in rendered
    assert "No content in this section." in texts
    assert not any("provider credential" in text or "Do not restore this" in text for text in texts)
    assert report == before


def test_external_findings_escape_text_keep_original_urls_and_actual_review_status(monkeypatch):
    rendered = capture(monkeypatch)
    report = {"title": "Public research sample", "sections": [], "external_research_appendix": [
        {"title": "A & B <field trials>", "gap_label": "Genetics & trials", "url": "https://example.test/article?x=1&y=2#section", "provider": "Public & source", "retrieved_at": "2026-10-02T15:00:00Z", "reviewed": True, "included_in_report": True},
        {"title": "Unsafe link", "url": "https://user:password@example.test/private", "reviewed": False, "included_in_report": True},
        {"title": "Excluded finding", "url": "https://example.test/excluded", "included_in_report": False},
    ]}
    before = deepcopy(report)
    assert pdf_export.render_report_pdf(report, {}, {}).startswith(b"%PDF")
    texts = [text for text, _ in rendered]
    assert "A &amp; B &lt;field trials&gt;" in texts
    assert "Research topic: Genetics &amp; trials" in texts
    assert "Analyst marked reviewed - external context only" in texts
    assert "Unreviewed external finding" in texts
    assert any('href="https://example.test/article?x=1&amp;y=2#section"' in text for text in texts)
    assert any("Oct 2, 2026" in text for text in texts)
    assert "Original URL unavailable" in texts
    assert not any("password" in text or "Excluded finding" in text or "[Genetics" in text for text in texts)
    assert report == before


def test_source_appendix_rejects_nonpublic_links_and_formats_dates(monkeypatch):
    rendered = capture(monkeypatch)
    packet = {"recent_developments": [{"date": "2026-09-30"}], "source_trace": [{"id": "ev-plain", "title": "A recorded source", "source_name": "Publication", "date": "2026-09-30", "source_url": "http://127.0.0.1/private"}]}
    before = deepcopy(packet)
    assert pdf_export.render_report_pdf({"title": "Test", "sections": []}, packet, {}).startswith(b"%PDF")
    texts = [text for text, _ in rendered]
    assert any("Latest dated source in scope: Sep 30, 2026" in text for text in texts)
    assert any("Publication | Sep 30, 2026" in text for text in texts)
    assert not any("127.0.0.1" in text for text in texts)
    assert packet == before


def test_long_missing_source_explanation_can_flow_across_pages():
    report = {"title": "Long working report", "sections": [{"section_id": "context", "title": "Sourced context", "status": "unsupported", "generated_prose": "A retained gap explanation. " * 700, "edited_prose": None}]}
    assert pdf_export.render_report_pdf(report, {}, {}).startswith(b"%PDF")


def test_edited_items_get_reading_structure_without_rewriting_qualifiers(monkeypatch):
    rendered = capture(monkeypatch)
    report = {"title": "Edited brief", "sections": [{"section_id": "signals", "title": "Signals", "status": "structured", "generated_prose": "Old draft", "edited_prose": "[Analyst qualifier] First observation\nSecond observation - proposed"}]}
    before = deepcopy(report)
    assert pdf_export.render_report_pdf(report, {}, {}).startswith(b"%PDF")
    assert ("[Analyst qualifier] First observation", "ReportItem") in rendered
    assert ("Second observation - proposed", "ReportItem") in rendered
    assert not any("Old draft" in text for text, _ in rendered)
    assert report == before


def test_workspace_chunks_edited_items_and_keeps_form_text_and_external_status(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main
    from app.services.report_builder.reports_store import create_report, load_report

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "_build_packet_and_coverage", lambda scope: ({}, {"counts": {}, "gaps": []}))
    record = create_report(tmp_path, title="Edited brief", report_type="company_brief", scope={}, sections=[{"section_id": "signals", "title": "Signals", "status": "structured", "generated_prose": "Original draft", "edited_prose": "[Analyst qualifier] First observation\nSecond observation - proposed", "citation_ids": []}])
    page = TestClient(main.app).get(f"/reports/{record['id']}")
    assert page.status_code == 200
    assert '<ul class="report-reading-items"><li>[Analyst qualifier] First observation</li><li>Second observation - proposed</li></ul>' in page.text
    assert '[Analyst qualifier] First observation\nSecond observation - proposed</textarea>' in page.text
    assert load_report(tmp_path, record["id"]) == record
