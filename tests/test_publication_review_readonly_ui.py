"""Publication Review read-only UI Slice 1 — focused route/template/safety tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import publication_review_readonly as readonly
from app.services.publication_review_readonly import (
    build_publication_review_readonly_view,
    load_rehearsal_fixture_records,
    project_detail,
    project_queue_item,
    select_source_drafts,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO / "tests" / "fixtures" / "publication_review_readonly_rehearsal.json"
REQUIRED_STATES = {
    "readable_body",
    "transcript",
    "metadata_only",
    "navigation_only_shell",
    "probable_duplicate",
    "uncertain_date",
    "missing_entity_match",
    "upgraded_acquisition",
    "already_handled_by_another_reviewer",
    "validation_failure",
}


@pytest.fixture()
def rehearsal_drafts() -> list[dict]:
    return load_rehearsal_fixture_records()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "pending_publication_drafts", lambda: [])
    monkeypatch.setenv("BIOS_PUBLICATION_REVIEW_REHEARSAL_UI", "1")
    return TestClient(main.app)


def test_rehearsal_fixture_covers_ten_states(rehearsal_drafts: list[dict]) -> None:
    assert FIXTURE_PATH.exists()
    states = {row["fixture_state"] for row in rehearsal_drafts}
    assert states == REQUIRED_STATES
    assert "tests/fixtures/publication_review_readonly_rehearsal.json" in str(FIXTURE_PATH)


def test_decisions_enabled_always_false(rehearsal_drafts: list[dict]) -> None:
    view = build_publication_review_readonly_view(drafts=rehearsal_drafts)
    assert view["decisions_enabled"] is False
    assert view["bulk_approval_available"] is False
    assert view["detail"]["decisions_enabled"] is False
    assert view["detail"]["decision_controls"]["enabled"] is False
    assert view["detail"]["permitted_commands"] == []
    assert readonly.decisions_enabled() is False


def test_honest_empty_when_no_durable_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIOS_PUBLICATION_REVIEW_REHEARSAL_UI", raising=False)
    drafts, source = select_source_drafts(durable_drafts=[])
    assert drafts == []
    assert source == "durable"
    view = build_publication_review_readonly_view(drafts=drafts, source=source)
    assert view["empty"] is True
    assert "does not invent backlog" in view["empty_message"]


def test_queue_is_body_free(rehearsal_drafts: list[dict]) -> None:
    item = project_queue_item(rehearsal_drafts[0])
    assert "body_text" not in item
    assert "limited_explanation" not in item
    assert item["draft_id"]
    assert item["permitted_commands"] == []


def test_detail_hydrates_body_and_trust_bands(rehearsal_drafts: list[dict]) -> None:
    readable = next(d for d in rehearsal_drafts if d["fixture_state"] == "readable_body")
    detail = project_detail(readable)
    assert detail["body_text"]
    assert "trusted_source_metadata" in detail["trust_bands"]
    assert "Atomic Evidence" in detail["atomic_evidence_note"]


def test_warn_versus_block_semantics(rehearsal_drafts: list[dict]) -> None:
    dup = next(d for d in rehearsal_drafts if d["fixture_state"] == "probable_duplicate")
    fail = next(d for d in rehearsal_drafts if d["fixture_state"] == "validation_failure")
    dup_item = project_queue_item(dup)
    fail_item = project_queue_item(fail)
    assert dup_item["warning_count"] >= 1
    assert dup_item["blocker_count"] == 0
    assert fail_item["blocker_count"] >= 1
    assert fail_item["needs_attention_rank"] <= dup_item["needs_attention_rank"]


def test_route_renders_queue_and_disabled_controls(client: TestClient) -> None:
    page = client.get("/review-ops/publications")
    assert page.status_code == 200
    assert "Publication Review" in page.text
    assert "decisions_enabled: false" in page.text
    assert 'data-decisions-enabled="false"' in page.text
    assert 'data-pagefind-ignore' in page.text
    assert "Approve publication" in page.text
    assert 'data-enabled="false"' in page.text
    assert "disabled" in page.text
    assert "Bulk approval is not available" in page.text
    assert "Atomic Evidence" in page.text
    # All ten fixture headlines reachable via queue or first selection
    assert "Pending review:" in page.text


@pytest.mark.parametrize(
    "draft_id,needle",
    [
        ("pub-readable-ok", "Extracted readable body"),
        ("pub-transcript", "Transcript"),
        ("pub-metadata-only", "No usable acquired body"),
        ("pub-nav-shell", "navigation"),
        ("pub-probable-duplicate", "Probable duplicate"),
        ("pub-uncertain-date", "Uncertain date"),
        ("pub-missing-entity", "Missing entity"),
        ("pub-upgraded", "upgraded"),
        ("pub-concurrent", "already"),
        ("pub-validation-fail", "Blocking"),
    ],
)
def test_each_rehearsal_state_renders(client: TestClient, draft_id: str, needle: str) -> None:
    page = client.get(f"/review-ops/publications/{draft_id}")
    assert page.status_code == 200
    assert needle.lower() in page.text.lower() or draft_id in page.text
    assert 'data-decision="approve_publication"' in page.text
    assert "Decision service connection is not part" in page.text


def test_no_decision_mutation_routes_registered() -> None:
    paths = {getattr(route, "path", "") for route in main.app.routes}
    forbidden = {
        "/review-ops/publications/{draft_id}/approve",
        "/review-ops/publications/{draft_id}/reject",
        "/review-ops/publications/{draft_id}/defer",
        "/review-ops/publications/{draft_id}/request-correction",
        "/api/publication-reviews/{draft_id}/approve",
    }
    assert not (forbidden & paths)
    methods = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", []) or [])))
        for route in main.app.routes
        if str(getattr(route, "path", "")).startswith("/review-ops/publications")
    }
    for path, route_methods in methods:
        assert "POST" not in route_methods
        assert "PUT" not in route_methods
        assert "PATCH" not in route_methods
        assert "DELETE" not in route_methods


def test_decision_buttons_do_not_submit(client: TestClient) -> None:
    page = client.get("/review-ops/publications/pub-readable-ok")
    assert 'data-decision="approve_publication"' in page.text
    assert 'data-enabled="false"' in page.text
    assert page.text.count("data-decision=") == 4
    assert page.text.count('disabled') >= 4
    # No dedicated decision POST form on this page
    assert 'action="/review-ops/publications' not in page.text
    assert "/approve" not in page.text
    assert "Confirm approve publication" not in page.text


def test_review_ops_links_readonly_workspace() -> None:
    page = TestClient(main.app).get("/review-ops")
    assert page.status_code == 200
    assert 'href="/review-ops/publications"' in page.text


def test_not_in_public_static_nav_or_build_script() -> None:
    sidebar = (REPO / "app" / "templates" / "_v2_sidebar.html").read_text(encoding="utf-8")
    # Private review-ops block already gated; new path must not appear as a public Library/Monitor link
    assert sidebar.count("/review-ops/publications") == 0
    build_src = (REPO / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert "/review-ops/publications" not in build_src
    assert "publication_review_readonly" not in build_src


def test_rehearsal_fixtures_not_shipped_under_data() -> None:
    data_hits = list((REPO / "data").rglob("*publication_review_readonly_rehearsal*"))
    assert data_hits == []
    # Must live only under tests/
    assert FIXTURE_PATH.exists()
    assert "tests/fixtures" in str(FIXTURE_PATH)


def test_content_filters(client: TestClient) -> None:
    page = client.get("/review-ops/publications?filter=transcript")
    assert page.status_code == 200
    assert 'aria-current="true"' in page.text
    assert "Transcript" in page.text


def test_today_and_reader_pvs_untouched_by_slice_css() -> None:
    today_css = (REPO / "app" / "static" / "daily_briefing.css").read_text(encoding="utf-8")
    pvs = (REPO / "app" / "static" / "pvs_tokens.css").read_text(encoding="utf-8")
    slice_css = (REPO / "app" / "static" / "publication_review_readonly.css").read_text(encoding="utf-8")
    # Slice CSS is scoped and must not redefine PVS root tokens
    assert ":root" not in slice_css
    assert "--pvs-navy" in pvs
    assert "daily-briefing" in today_css
    assert "pub-review-ro" in slice_css


def test_guide_static_surface_has_no_queue_leak(client: TestClient, rehearsal_drafts: list[dict]) -> None:
    guide = client.get("/guide")
    assert guide.status_code == 200
    for draft in rehearsal_drafts:
        assert draft["draft_id"] not in guide.text
        assert draft["headline"] not in guide.text
