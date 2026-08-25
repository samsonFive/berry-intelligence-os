"""Saved Brief Packs V1 -- stores an analyst's Brief Pack SELECTION only
(TD-097's recommended resolution), never duplicated intelligence
content. A saved pack is not a trust object and not a historical
snapshot: reopening one always renders CURRENT trusted data."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.brief_pack import assessment_snapshot
from app.services.saved_brief_packs import (
    archive_pack,
    duplicate_pack,
    list_packs,
    load_pack,
    pack_query_string,
    present_pack_row,
    save_pack,
    unarchive_pack,
)


def _save(inbox_dir: Path, **overrides):
    defaults = dict(
        title="Q3 Blueberry Update",
        context_note="Prepared for leadership review",
        berry_id="berry-blueberry",
        window_days=14,
        company_ids=["company-planasa"],
        variety_ids=[],
        signal_ids=[],
        assessment_ids=[],
        concept_slugs=[],
    )
    defaults.update(overrides)
    return save_pack(inbox_dir, **defaults)


# --- persistence model -------------------------------------------------


def test_save_as_creates_new_pack_with_id_and_timestamps(tmp_path: Path) -> None:
    record = _save(tmp_path)
    assert record["id"].startswith("bp-")
    assert record["created_at"] == record["updated_at"]
    assert record["status"] == "active"
    assert record["title"] == "Q3 Blueberry Update"


def test_save_changes_updates_existing_pack_in_place(tmp_path: Path) -> None:
    created = _save(tmp_path)
    updated = _save(tmp_path, pack_id=created["id"], title="Q3 Blueberry Update (revised)")
    assert updated["id"] == created["id"]
    assert updated["created_at"] == created["created_at"]
    assert updated["title"] == "Q3 Blueberry Update (revised)"
    assert len(list_packs(tmp_path)) == 1  # never a duplicate row


def test_save_changes_unknown_pack_id_raises(tmp_path: Path) -> None:
    try:
        save_pack(tmp_path, pack_id="bp-doesnotexist", title="x", context_note="", berry_id="", window_days=14,
                   company_ids=[], variety_ids=[], signal_ids=[], assessment_ids=[], concept_slugs=[])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_saved_pack_stores_selection_ids_only_no_resolved_content(tmp_path: Path) -> None:
    record = _save(tmp_path)
    stored_keys = set(record.keys())
    forbidden = {"title_text", "body", "article", "companies", "varieties", "recent_evidence", "top_observations", "rationale"}
    assert not (stored_keys & forbidden)
    assert record["company_ids"] == ["company-planasa"]


def test_empty_title_falls_back_to_untitled(tmp_path: Path) -> None:
    record = _save(tmp_path, title="   ")
    assert record["title"] == "Untitled brief pack"


# --- duplicate / archive / unarchive ------------------------------------


def test_duplicate_creates_new_id_with_same_selections(tmp_path: Path) -> None:
    original = _save(tmp_path)
    copy = duplicate_pack(tmp_path, original["id"])
    assert copy["id"] != original["id"]
    assert copy["company_ids"] == original["company_ids"]
    assert copy["title"] == "Q3 Blueberry Update (copy)"
    # editing the copy must never touch the original
    save_pack(tmp_path, pack_id=copy["id"], title="Renamed copy", context_note="", berry_id="",
              window_days=14, company_ids=[], variety_ids=[], signal_ids=[], assessment_ids=[], concept_slugs=[])
    assert load_pack(tmp_path, original["id"])["title"] == "Q3 Blueberry Update"


def test_duplicate_missing_pack_returns_none(tmp_path: Path) -> None:
    assert duplicate_pack(tmp_path, "bp-doesnotexist") is None


def test_archive_is_reversible_and_removes_from_active_list(tmp_path: Path) -> None:
    record = _save(tmp_path)
    assert len(list_packs(tmp_path, status="active")) == 1
    archive_pack(tmp_path, record["id"])
    assert len(list_packs(tmp_path, status="active")) == 0
    assert len(list_packs(tmp_path, status="archived")) == 1
    unarchive_pack(tmp_path, record["id"])
    assert len(list_packs(tmp_path, status="active")) == 1
    assert len(list_packs(tmp_path, status="archived")) == 0


def test_archive_missing_pack_returns_none(tmp_path: Path) -> None:
    assert archive_pack(tmp_path, "bp-doesnotexist") is None


# --- listing / ordering --------------------------------------------------


def test_list_packs_newest_updated_first(tmp_path: Path) -> None:
    import json

    a = _save(tmp_path, title="First")
    b = _save(tmp_path, title="Second")
    # Real-clock second-precision timestamps can tie within one test run
    # (same class of race the Review Session history sort hit) -- pin
    # them explicitly so ordering is deterministic rather than flaky.
    a_path = tmp_path / "brief_packs" / f"{a['id']}.json"
    b_path = tmp_path / "brief_packs" / f"{b['id']}.json"
    a_blob = json.loads(a_path.read_text(encoding="utf-8"))
    b_blob = json.loads(b_path.read_text(encoding="utf-8"))
    a_blob["updated_at"] = "2026-06-01T00:00:00+00:00"
    b_blob["updated_at"] = "2026-01-01T00:00:00+00:00"
    a_path.write_text(json.dumps(a_blob), encoding="utf-8")
    b_path.write_text(json.dumps(b_blob), encoding="utf-8")
    rows = list_packs(tmp_path)
    assert rows[0]["id"] == a["id"]  # most recently updated, not most recently created


def test_present_pack_row_computes_hrefs_and_selection_count(tmp_path: Path) -> None:
    record = _save(tmp_path, company_ids=["company-planasa", "company-driscolls"], variety_ids=["variety-x"])
    row = present_pack_row(record)
    assert row["selection_count"] == 3
    assert row["open_href"].startswith("/brief-pack?")
    assert "present=1" in row["present_href"]
    assert f"pack_id={record['id']}" in row["open_href"]


def test_pack_query_string_round_trips_selection(tmp_path: Path) -> None:
    record = _save(tmp_path, company_ids=["company-planasa"], berry_id="berry-blueberry", window_days=30)
    qs = pack_query_string(record)
    assert "companies=company-planasa" in qs
    assert "berry=berry-blueberry" in qs
    assert "days=30" in qs


# --- route-level: backward compatibility, save, open, duplicate, archive -


def test_existing_brief_pack_url_without_pack_id_still_works():
    client = TestClient(app)
    page = client.get("/brief-pack", params={"companies": "company-planasa"})
    assert page.status_code == 200
    assert "LIVE BRIEF" not in page.text  # no saved_pack banner when there is no pack_id


def test_save_route_creates_pack_and_redirects_with_pack_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    resp = client.post(
        "/brief-packs/save",
        data={"title": "New pack", "companies": "company-planasa", "save_mode": "new"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "pack_id=bp-" in resp.headers["location"]
    assert len(list_packs(tmp_path)) == 1


def test_reopening_saved_pack_shows_live_brief_banner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    record = _save(tmp_path, title="Reopen Me")
    page = client.get(f"/brief-pack?pack_id={record['id']}&companies=company-planasa")
    assert page.status_code == 200
    assert "LIVE BRIEF" in page.text
    assert "Reopen Me" in page.text


def test_save_changes_route_updates_in_place(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    record = _save(tmp_path, title="Original title")
    resp = client.post(
        "/brief-packs/save",
        data={"title": "Updated title", "companies": "company-planasa", "pack_id": record["id"], "save_mode": "update"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    reloaded = load_pack(tmp_path, record["id"])
    assert reloaded["title"] == "Updated title"
    assert len(list_packs(tmp_path)) == 1


def test_save_as_new_from_an_opened_pack_does_not_mutate_original(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    record = _save(tmp_path, title="Original")
    resp = client.post(
        "/brief-packs/save",
        data={"title": "Forked", "companies": "company-driscolls", "pack_id": record["id"], "save_mode": "new"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert len(list_packs(tmp_path)) == 2
    assert load_pack(tmp_path, record["id"])["title"] == "Original"
    assert load_pack(tmp_path, record["id"])["company_ids"] == ["company-planasa"]


def test_duplicate_route(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    record = _save(tmp_path)
    resp = client.post(f"/brief-packs/{record['id']}/duplicate", follow_redirects=False)
    assert resp.status_code == 303
    assert len(list_packs(tmp_path)) == 2


def test_duplicate_route_missing_pack_404(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    resp = client.post("/brief-packs/bp-doesnotexist/duplicate")
    assert resp.status_code == 404


def test_archive_and_unarchive_routes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    record = _save(tmp_path)
    client.post(f"/brief-packs/{record['id']}/archive")
    assert load_pack(tmp_path, record["id"])["status"] == "archived"
    client.post(f"/brief-packs/{record['id']}/unarchive")
    assert load_pack(tmp_path, record["id"])["status"] == "active"


def test_saved_brief_packs_index_lists_active_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    _save(tmp_path, title="Visible pack")
    page = client.get("/brief-packs")
    assert page.status_code == 200
    assert "Visible pack" in page.text


def test_saved_brief_packs_index_archived_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    record = _save(tmp_path, title="Archived pack")
    archive_pack(tmp_path, record["id"])
    active_page = client.get("/brief-packs")
    assert "Archived pack" not in active_page.text
    archived_page = client.get("/brief-packs?status=archived")
    assert "Archived pack" in archived_page.text


def test_empty_saved_brief_packs_index_honest_empty_state():
    client = TestClient(app)
    # Uses the real INBOX_DIR (no monkeypatch) -- just checks it never crashes
    page = client.get("/brief-packs")
    assert page.status_code == 200


# --- trust preservation / missing-object graceful handling ---------------


def test_saving_never_creates_fact_evidence_signal_or_assessment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    client.post(
        "/brief-packs/save",
        data={"title": "No mutation check", "companies": "company-planasa", "save_mode": "new"},
    )
    # The only thing on disk must be under inbox/brief_packs/ -- nothing
    # written to data/ (the trusted corpus) at all.
    assert not (tmp_path / "data").exists()
    packs_dir = tmp_path / "brief_packs"
    assert packs_dir.is_dir()
    assert len(list(packs_dir.glob("bp-*.json"))) == 1


def test_reopened_pack_with_removed_object_id_shows_invalid_not_crash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client = TestClient(main.app)
    record = _save(tmp_path, company_ids=["company-totally-fake-xyz"])
    page = client.get(f"/brief-pack?pack_id={record['id']}&companies=company-totally-fake-xyz")
    assert page.status_code == 200
    assert "company-totally-fake-xyz" in page.text  # honestly listed as not found, not silently dropped


def test_no_score_or_ranking_language_on_saved_packs_index():
    client = TestClient(app)
    page = client.get("/brief-packs")
    lowered = page.text.casefold()
    for forbidden in ("readiness score", "completeness score", "priority rank"):
        assert forbidden not in lowered


# --- concurrent canonical change (a reopened pack must never preserve an
# obsolete AI PROPOSED / REVIEWED badge) ------------------------------------


def test_reopened_pack_reflects_ai_proposed_to_reviewed_transition() -> None:
    # compose_brief_pack() (and therefore a saved pack's live reopen) is a
    # pure function over whatever assessment records it is handed -- it
    # never caches or freezes a badge from an earlier render.
    assessments_by_id = {"assessment-1": {"id": "assessment-1", "title": "T", "ai_proposed": True}}
    before = assessment_snapshot("assessment-1", assessments_by_id, [])
    assert before["ai_proposed"] is True

    assessments_by_id["assessment-1"]["ai_proposed"] = False
    after = assessment_snapshot("assessment-1", assessments_by_id, [])
    assert after["ai_proposed"] is False


# --- static/privacy safety ------------------------------------------------
# The definitive leak check is build_static.py's own generated/ scan, run
# separately (no /brief-packs* route is registered in build_static.py).
