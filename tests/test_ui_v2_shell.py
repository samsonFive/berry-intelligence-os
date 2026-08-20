"""V2 AppShell, berry context, Feed views, and slide-over Reader."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.ui_context import landscape_href, matches_berry_context, parse_berry, parse_feed_view


PRIORITY = {
    dimension: {"level": "none", "rationale": ""}
    for dimension in ("reading", "testing", "commercial_position", "monitoring")
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "evidence").mkdir(parents=True, exist_ok=True)


def test_parse_berry_and_landscape_href() -> None:
    berries = main.BERRIES
    assert parse_berry("global", berries) == "global"
    assert parse_berry("strawberry", berries) == "berry-strawberry"
    assert parse_berry("berry-raspberry", berries) == "berry-raspberry"
    assert parse_feed_view("compact") == "compact"
    assert parse_feed_view("nope") == "grid"
    assert landscape_href("global") == "/entities/berry"
    assert landscape_href("berry-blackberry") == "/landscapes/berries/blackberry"


def test_matches_berry_context_uses_record_ids() -> None:
    item = {"berry_ids": ["berry-strawberry"], "title": "x"}
    assert matches_berry_context(item, "global")
    assert matches_berry_context(item, "berry-strawberry")
    assert not matches_berry_context(item, "berry-blueberry")


def test_shell_nav_groups_and_offcanvas(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    client = TestClient(app)
    page = client.get("/brief")
    assert page.status_code == 200
    html = page.text
    assert 'class="v2-nav-group">Work</p>' in html
    assert ">Decide<" in html
    assert ">Monitor<" in html
    assert ">Library<" in html
    assert "v2-nav-disclosure" in html
    assert "Blueberry Landscape" not in html
    assert "Live Intelligence" in html
    assert 'id="v2NavOffcanvas"' in html
    assert 'id="v2-berry"' in html
    assert "Strawberry" in html
    assert "Blackberry" in html
    assert "All companies — coming later" in html
    assert "All geographies — coming later" in html
    assert "/static/vendor/bootstrap/bootstrap.min.css" in html
    assert "/static/v2.css" in html


def test_feed_grid_compact_and_reader_fragment(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    draft = {
        "id": "ev-intel-v2-shell",
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "intake_type": "article_or_url",
        "source_type": "article",
        "source_name": "Synthetic Journal",
        "source_url": "https://example.invalid/v2",
        "published_date": "2026-08-18",
        "captured_date": "2026-08-18",
        "title": "Synthetic strawberry article v2-shell",
        "summary": "A concise strawberry supply brief.",
        "why_it_matters": "Retail programs can move volume.",
        "submitted_by": "fixture",
        "evidence_role": "publication_artifact",
        "berry_ids": ["berry-strawberry"],
        "suggested_competitors": [],
        "suggested_varieties": [],
        "attachments": [],
        "priority": deepcopy(PRIORITY),
        "article": {"paragraphs": [{"locator": "p1", "text": "Acquired strawberry article body."}]},
    }
    _write(tmp_path / "inbox" / "evidence" / f"{draft['id']}.json", draft)
    client = TestClient(app)
    grid = client.get("/work-queue?view=grid")
    assert grid.status_code == 200
    assert "v2-feed-grid" in grid.text
    assert "data-open-reader" in grid.text
    assert "Synthetic strawberry article v2-shell" in grid.text
    compact = client.get("/work-queue?view=compact")
    assert "v2-feed-compact" in compact.text
    blueberry = client.get("/work-queue?berry=blueberry")
    assert "Synthetic strawberry article v2-shell" not in blueberry.text
    strawberry = client.get("/work-queue?berry=strawberry")
    assert "Synthetic strawberry article v2-shell" in strawberry.text
    fragment = client.get(f"/api/intelligence/{draft['id']}/reader")
    assert fragment.status_code == 200
    assert "Acquired strawberry article body." in fragment.text
    assert "Open full reader" in fragment.text
    assert "<html" not in fragment.text.casefold()


def test_ui_context_post_sets_cookie(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    client = TestClient(app, follow_redirects=False)
    response = client.post("/ui/context", data={"berry": "raspberry", "view": "compact", "next": "/brief"})
    assert response.status_code == 303
    assert response.headers["location"] == "/brief"
    assert "bios_berry=berry-raspberry" in response.headers.get("set-cookie", "") or response.cookies.get("bios_berry") == "berry-raspberry"
    assert response.cookies.get("bios_feed_view") == "compact"


def test_reader_overlay_endpoint_is_not_a_full_page(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    client = TestClient(app)
    missing = client.get("/api/intelligence/does-not-exist/reader")
    assert missing.status_code == 404
