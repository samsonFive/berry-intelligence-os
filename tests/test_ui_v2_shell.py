"""V2 AppShell, berry context, Feed views, and slide-over Reader."""

from __future__ import annotations

import json
import time
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
    assert "v2-card-line" in compact.text
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


def test_collapsed_sidebar_is_an_icon_rail(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    client = TestClient(app)
    page = client.get("/brief")
    assert 'class="v2-nav-icon"' in page.text
    assert 'aria-label="Morning Brief"' in page.text
    assert 'title="Morning Brief"' in page.text
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "v2.css").read_text(encoding="utf-8")
    assert "grid-template-columns: 4.5rem minmax(0, 1fr)" in css
    assert "grid-template-columns: 0 minmax(0, 1fr)" not in css


def test_compact_feed_hides_browsing_chrome() -> None:
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "v2.css").read_text(encoding="utf-8")
    assert ".v2-feed-compact .v2-card-summary" in css
    assert ".v2-feed-compact .v2-card-chips" in css
    assert ".v2-feed-compact .v2-card-actions" in css
    assert ".v2-feed-compact .v2-card.is-current .v2-card-actions" in css


def test_reader_overlay_skips_morning_brief(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None
    calls = {"n": 0}
    original = main.build_morning_brief

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(main, "build_morning_brief", wrapped)
    draft = {
        "id": "ev-overlay-skip-brief",
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "intake_type": "article_or_url",
        "source_type": "article",
        "source_name": "Timing Journal",
        "title": "Overlay skip brief",
        "summary": "Short.",
        "submitted_by": "fixture",
        "evidence_role": "publication_artifact",
        "berry_ids": ["berry-strawberry"],
        "priority": deepcopy(PRIORITY),
        "article": {"paragraphs": [{"locator": "p1", "text": "Body."}]},
    }
    _write(tmp_path / "inbox" / "evidence" / f"{draft['id']}.json", draft)
    client = TestClient(app)
    fragment = client.get(f"/api/intelligence/{draft['id']}/reader")
    assert fragment.status_code == 200
    assert calls["n"] == 0
    assert "Body." in fragment.text


def test_reader_overlay_warm_is_under_500ms() -> None:
    client = TestClient(app)
    item_id = "ev-sample-variety-launch"
    warm = client.get(f"/api/intelligence/{item_id}/reader")
    assert warm.status_code == 200
    started = time.perf_counter()
    again = client.get(f"/api/intelligence/{item_id}/reader")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert again.status_code == 200
    assert elapsed_ms < 500, f"warm overlay took {elapsed_ms:.1f}ms"


def test_company_profile_is_v2_and_multi_berry() -> None:
    client = TestClient(app)
    page = client.get("/entities/company/company-driscolls")
    assert page.status_code == 200
    html = page.text
    assert "v2-company" in html
    assert "v2-berry-portfolio" in html
    assert ">STRAWBERRY<" in html
    assert ">BLUEBERRY<" in html
    assert ">RASPBERRY<" in html
    assert ">BLACKBERRY<" in html
    assert "What changed" in html
    assert "Recent intelligence" in html
    assert "Varieties / genetics" in html
    assert "Geographic activity" in html
    assert "Network / relationships" in html
    assert 'class="trust-summary bluf-metrics"' not in html
    assert 'id="v2ReaderOffcanvas"' in html
    assert "data-open-reader" in html
    strawberry = TestClient(app)
    strawberry.cookies.set("bios_berry", "berry-strawberry")
    page = strawberry.get("/entities/company/company-driscolls")
    assert page.status_code == 200
    assert "STRAWBERRY" in page.text
    assert "Strawberry context" in page.text or "strawberry context" in page.text.casefold()
    assert "Blueberry Landscape" not in page.text
