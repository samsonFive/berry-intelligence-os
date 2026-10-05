"""Retained intake/context workflows survive the shared shell migration."""
from html.parser import HTMLParser
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from app import main


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "form":
            self.current = {"attrs": attributes, "controls": []}
            self.forms.append(self.current)
        elif self.current is not None and tag in {"input", "textarea", "select", "button"}:
            self.current["controls"].append(attributes)

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    data_dir, inbox_dir = tmp_path / "data", tmp_path / "inbox"
    (data_dir / "evidence").mkdir(parents=True)
    inbox_dir.mkdir()
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "INBOX_DIR", inbox_dir)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    return TestClient(main.app), data_dir, inbox_dir


def test_intake_keeps_native_validation_fields_and_literal_notes(isolated):
    client, data_dir, inbox_dir = isolated
    page = client.get("/intake")
    assert page.status_code == 200
    form = next(row for row in Forms(page.text).forms if row["attrs"].get("class") == "intake-form")
    assert form["attrs"]["action"] == "/intake"
    assert form["attrs"]["method"] == "post"
    assert form["attrs"]["enctype"] == "multipart/form-data"
    fields = {row.get("name"): row for row in form["controls"] if row.get("name")}
    assert set(fields) == {"intake_type", "source_url", "title", "source_name", "published_date", "summary", "attachment", "suggested_competitors", "suggested_varieties", "why_it_matters", "submitted_by"}
    assert all("required" in fields[name] for name in ("source_url", "title", "summary", "submitted_by"))
    literal = "Analyst note [company-test]: preserve exact words <and brackets>."
    payload = dict(intake_type="article_or_url", title="Isolated layout fixture", source_url="https://example.org/story?original=1", source_name="Fixture publisher", summary=literal, submitted_by="Fixture analyst", published_date="2026-09-30", suggested_competitors="Company A, Company B", suggested_varieties="Example Blue")
    refused = client.post("/intake", data={**payload, "submitted_by": ""})
    assert refused.status_code == 400
    assert "Submitted by is required" in refused.text
    assert list((inbox_dir / "evidence").glob("*.json")) == []
    saved = client.post("/intake", data=payload, follow_redirects=False)
    assert saved.status_code == 303
    records = list((inbox_dir / "evidence").glob("*.json"))
    assert len(records) == 1
    draft = json.loads(records[0].read_text(encoding="utf-8"))
    assert draft["summary"] == literal
    assert draft["source_url"] == payload["source_url"]
    assert draft["published_date"] == "2026-09-30"
    assert draft["status"] == "draft"
    assert draft["fact_ids"] == []
    assert draft["suggested_competitors"] == ["Company A", "Company B"]
    assert list((data_dir / "evidence").glob("*.json")) == []
    response = client.get(saved.headers["location"])
    assert "stays out of the published newsfeed until it is reviewed" in response.text
    detail = client.get("/intake/" + draft["id"])
    assert "Analyst note [company-test]" in detail.text


def test_retained_context_post_preserves_query_and_session_scope(isolated):
    client, _, _ = isolated
    path = "/entities/company/compare?ids=company-a,company-b&berry=blueberry"
    page = client.get(path)
    assert page.status_code == 200
    form = next(row for row in Forms(page.text).forms if row["attrs"].get("class") == "v2-context")
    next_field = next(row for row in form["controls"] if row.get("name") == "next")
    assert next_field["value"] == path
    response = client.post("/ui/context", data={"berry": "raspberry", "view": "compact", "next": path}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == path
    assert response.cookies.get("bios_berry") == "berry-raspberry"
    assert response.cookies.get("bios_feed_view") == "compact"
    subsequent = client.get("/settings")
    assert '<option value="berry-raspberry" selected>' in subsequent.text
    assert 'href="/digest"' in subsequent.text
    assert 'id="v2SearchOffcanvas"' in subsequent.text
    assert 'id="v2ReaderOffcanvas"' in subsequent.text
    assert 'id="v2DesktopSidebar"' not in subsequent.text
