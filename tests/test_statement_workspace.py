"""Statement triage keeps human confirmation and private state separate."""
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import feed_first
from app.services.statement_workspace import present_statements


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    record = {"id": "ev-statement-workspace", "status": "published", "title": "The source article", "source_name": "Example publication", "published_date": "2026-09-30", "source_url": "https://example.test/news?original=1"}
    row = {"id": "statement-review-example", "feed_item_id": record["id"], "statement_text": "The company announced a partnership.", "original_extraction_text": "Original extracted wording.", "statement_state": "pending_confirmation", "importance_state": "normal", "entity_ids": ["company-sample", "geography-sample", "variety-sample", "unknown-record"], "supporting_passages": ["First exact passage.", "Second exact passage."], "extraction_model": "internal/model-reference", "confidence": "medium"}
    state = feed_first.empty_state()
    state["statements"] = {record["id"]: [row]}
    feed_first.save_state(main.INBOX_DIR, state)
    monkeypatch.setattr(main, "published_evidence", lambda: [record])
    monkeypatch.setattr(main, "_feed_first_world", lambda: {"state": feed_first.load_state(main.INBOX_DIR), "entities": [{"id": "company-sample", "name": "Example Company", "entity_type": "company"}, {"id": "geography-sample", "name": "Example Region", "entity_type": "geography"}, {"id": "variety-sample", "name": "Example Variety", "entity_type": "variety"}], "nav": [], "counts": {}})
    return TestClient(main.app), row, record


def test_review_browse_keeps_exact_text_history_and_state(workspace):
    client, row, _ = workspace
    before = feed_first.state_path(main.INBOX_DIR).read_bytes()
    page = client.get("/statements?review=all")
    assert page.status_code == 200
    assert "intelligence_workspace.css" in page.text
    assert "Keep wording" in page.text and "Awaiting confirmation" in page.text
    assert "triage does not confirm a statement" in page.text
    assert row["statement_text"] in page.text
    assert all(passage in page.text for passage in row["supporting_passages"])
    assert "Original extracted wording." in page.text
    assert 'href="/geographies/geography-sample"' in page.text
    assert 'href="/entities/variety/variety-sample"' in page.text
    assert '>company-sample<' not in page.text
    assert 'bos-shell' not in page.text and 'data-confirm-all' not in page.text
    assert '/intelligence/ev-statement-workspace?personal=1' in page.text
    assert feed_first.state_path(main.INBOX_DIR).read_bytes() == before


def test_triage_edit_remove_restore_do_not_confirm(workspace):
    client, row, _ = workspace
    for action, extra in [("approve", {}), ("edit", {"text": "Edited analyst wording."}), ("important", {}), ("demote", {}), ("remove", {}), ("restore", {})]:
        response = client.post("/api/feed-first/statement", json={"statement_id": row["id"], "action": action, **extra})
        assert response.status_code == 200
        saved = response.json()["statement"]
        assert not saved.get("canonical_fact_id") and not saved.get("confirmed_at")
    assert saved["statement_state"] == "pending_confirmation"
    assert saved["statement_text"] == "Edited analyst wording."
    assert saved["original_extraction_text"] == row["original_extraction_text"]
    assert saved["supporting_passages"] == row["supporting_passages"]
    assert saved["analyst_edit_history"][0]["from"] == row["statement_text"]
    assert "Triaged" in client.get("/statements?review=reviewed").text


def test_read_only_blocks_private_page_and_every_write_before_loading(workspace, monkeypatch):
    client, row, _ = workspace
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(main, "_feed_first_world", lambda: pytest.fail("Private statements must not load in a published snapshot"))
    before = feed_first.state_path(main.INBOX_DIR).read_bytes()
    assert client.get("/statements").status_code == 403
    for action in ("approve", "edit", "remove", "restore", "confirm", "reject"):
        assert client.post("/api/feed-first/statement", json={"statement_id": row["id"], "action": action}).status_code == 403
    assert feed_first.state_path(main.INBOX_DIR).read_bytes() == before


@pytest.mark.parametrize("headers", [{"origin": "https://other.example"}, {"sec-fetch-site": "cross-site"}])
def test_cross_site_change_blocked_without_mutation(workspace, headers):
    client, row, _ = workspace
    before = feed_first.state_path(main.INBOX_DIR).read_bytes()
    assert client.post("/api/feed-first/statement", headers=headers, json={"statement_id": row["id"], "action": "approve"}).status_code == 403
    assert feed_first.state_path(main.INBOX_DIR).read_bytes() == before


def test_bulk_confirmation_never_starts_canonical_write(workspace, monkeypatch):
    from app.services import feed_first_trust
    client, row, _ = workspace
    monkeypatch.setattr(feed_first_trust, "confirm_feed_statement", lambda **kwargs: pytest.fail("A bulk request must not write a Fact"))
    before = feed_first.state_path(main.INBOX_DIR).read_bytes()
    response = client.post("/api/feed-first/statement", json={"statement_ids": [row["id"], "statement-other"], "action": "confirm"})
    assert response.status_code == 400 and "one statement at a time" in response.text
    with pytest.raises(ValueError, match="one statement at a time"):
        feed_first.mutate_statements(main.INBOX_DIR, statement_ids=[row["id"], "statement-other"], action="confirm")
    assert feed_first.state_path(main.INBOX_DIR).read_bytes() == before
    template = Path("app/templates/feed_first_today.html").read_text(encoding="utf-8")
    script = Path("app/static/feed_first.js").read_text(encoding="utf-8")
    assert "data-confirm-all" not in template + script
    assert "data-confirm-selected" not in template + script
    assert 'data-statement-action="confirm"' in template
    assert 'data-reject-selected' in template + script


def test_unknown_scope_does_not_silently_change_review_filter(workspace):
    client, _, _ = workspace
    assert client.get("/statements?review=unexpected").status_code == 422


def test_selected_reader_retains_every_passage_and_individual_decisions(workspace):
    client, row, _ = workspace
    page = client.get("/api/intelligence/ev-statement-workspace/reader?personal=1")
    assert page.status_code == 200
    assert "Review individual statements" in page.text
    assert all(passage in page.text for passage in row["supporting_passages"])
    assert 'data-reader-statement-action="confirm"' in page.text
    assert "Confirm this statement" in page.text
    assert "data-confirm-all" not in page.text
    full = client.get("/intelligence/ev-statement-workspace?personal=1&return_to=%2Fstatements%3Freview%3Dall")
    assert 'href="/statements?review=all"' in full.text


def test_unpublished_source_cannot_skip_publication_review(workspace, monkeypatch, tmp_path):
    from app.services import feed_first_trust
    client, row, _ = workspace
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(feed_first_trust, "confirm_feed_statement", lambda **kwargs: pytest.fail("An unpublished source must not be promoted through statement confirmation"))
    before = feed_first.state_path(main.INBOX_DIR).read_bytes()
    response = client.post("/api/feed-first/statement", json={"statement_id": row["id"], "action": "confirm"})
    assert response.status_code == 400 and "publication" in response.text
    assert feed_first.state_path(main.INBOX_DIR).read_bytes() == before


def test_already_decided_statement_cannot_write_fact_before_state_validation(workspace, monkeypatch):
    from app.services import feed_first_trust
    client, row, _ = workspace
    feed_first.mutate_statement(main.INBOX_DIR, statement_id=row["id"], action="reject")
    before = feed_first.state_path(main.INBOX_DIR).read_bytes()
    monkeypatch.setattr(feed_first_trust, "confirm_feed_statement", lambda **kwargs: pytest.fail("Validate the statement state before any canonical write"))
    response = client.post("/api/feed-first/statement", json={"statement_id": row["id"], "action": "confirm"})
    assert response.status_code == 400 and "not awaiting confirmation" in response.text
    assert feed_first.state_path(main.INBOX_DIR).read_bytes() == before


def test_published_reader_never_loads_private_statements_or_capture(workspace, monkeypatch):
    from app.services import feed_first_reader
    client, row, _ = workspace
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    monkeypatch.setattr(main, "_feed_first_world", lambda: pytest.fail("No private statement state in the published Reader"))
    monkeypatch.setattr(feed_first_reader, "load_capture", lambda *args: pytest.fail("No private source capture in the published Reader"))
    monkeypatch.setattr(main, "get_draft", lambda *args: pytest.fail("No private draft lookup in the published Reader"))
    page = client.get("/api/intelligence/ev-statement-workspace/reader?personal=1")
    assert page.status_code == 200
    assert row["id"] not in page.text and row["statement_text"] not in page.text
    assert "Review individual statements" not in page.text


def test_public_reader_does_not_open_a_retained_raw_story(workspace, monkeypatch):
    from app.services.personal_digest import source_records
    from app.services.feed_first_live import save_bundle
    client, _, record = workspace
    raw = {**record, "id": "live-private-story", "status": "unreviewed"}
    save_bundle(main.INBOX_DIR, {"today": "2026-10-02", "records": [raw]})
    assert raw["id"] in source_records([record], main.INBOX_DIR)
    assert raw["id"] not in source_records([record], main.INBOX_DIR, include_private=False)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    for path in ["/intelligence/live-private-story", "/intelligence/live-private-story?personal=1", "/api/intelligence/live-private-story/reader?personal=1"]:
        assert client.get(path).status_code == 404


def test_missing_and_unsafe_source_metadata_stay_honest_and_unchanged():
    row = {"id": "statement-private", "feed_item_id": "missing-source", "statement_state": "mystery-state", "source_context": {"source_url": "javascript:alert(1)"}, "supporting_passages": ["Retained source text"]}
    original = deepcopy(row)
    shown = present_statements([row], {}, [], return_to="/statements")[0]
    assert shown["reader_url"] == "" and not shown["source_url"]
    assert shown["article_title"] == "Article title unavailable"
    assert shown["state_label"] == "Status unavailable"
    assert row == original
