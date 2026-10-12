"""Personal reading continuity and trust boundaries, isolated from operator data."""
from copy import deepcopy
from datetime import date
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import analyst_queue as queue, feed_first as feed, personal_digest as digest
from app.services.feed_first_live import save_bundle
from app.services.feed_first_reader import save_capture


def article(item_id="ev-digest", **changes):
    row = {"id": item_id, "record_type": "evidence", "status": "published", "review_state": "published",
           "source_type": "trade_press", "source_name": "Berry Journal", "source_url": "https://example.invalid/" + item_id,
           "title": "Blueberry genetics expansion", "summary": "A blueberry nursery expands its growing programme.",
           "published_date": "2026-09-25", "captured_date": "2026-09-25", "submitted_by": "test",
           "reviewed_by": "test", "reviewed_at": "2026-09-25", "berry_ids": ["berry-blueberry"],
           "entity_ids": ["company-digest"], "geography_ids": ["geography-chile"],
           "priority": {key: {"level": "none", "rationale": ""} for key in ("reading", "testing", "monitoring", "commercial_position")}}
    row.update(changes)
    return row


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    repos = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR)
    repos.entities.create({"id": "company-digest", "record_type": "entity", "entity_type": "company", "name": "Berry Nursery", "status": "active"})
    repos.evidence.create(article())
    return TestClient(main.app), repos


def model(tmp_path, records, params=None):
    return digest.digest_model(records={row["id"]: row for row in records}, entities={}, state=feed.load_state(tmp_path),
                               reading=queue.load_state(tmp_path), params=params or {}, today=date(2026, 9, 30))


def test_exact_id_union_keeps_all_origins_and_subscription_is_explicit(tmp_path):
    row = article()
    row["priority"]["reading"]["level"] = "high"
    digest.set_personal_decision(tmp_path, row["id"], "save")
    list_id = digest.edit_list(tmp_path, action="create", name="Genetics", company_ids=["company-digest"], allowed_companies={"company-digest"})
    assert [origin["key"] for origin in model(tmp_path, [row])["cards"][0]["origins"]] == ["saved", "queue"]
    digest.edit_list(tmp_path, action="subscribe", list_id=list_id, allowed_companies=set())
    cards = model(tmp_path, [row])["cards"]
    assert len(cards) == 1
    assert {origin["key"] for origin in cards[0]["origins"]} == {"saved", "queue", list_id}
    digest.edit_list(tmp_path, action="unsubscribe", list_id=list_id, allowed_companies=set())
    assert len(model(tmp_path, [row])["cards"]) == 1
    assert feed.load_state(tmp_path)["company_lists"][list_id]["company_ids"] == ["company-digest"]


def test_membership_and_feedback_do_not_inject_unsubscribed_stories(tmp_path):
    digest.edit_list(tmp_path, action="create", name="Watch", company_ids=["company-digest"], allowed_companies={"company-digest"})
    digest.set_personal_decision(tmp_path, "ev-digest", "useful")
    assert model(tmp_path, [article()])["cards"] == []


def test_remembering_reading_position_is_not_a_queue_subscription(tmp_path):
    list_id = digest.edit_list(tmp_path, action="create", name="Genetics", company_ids=["company-digest"], allowed_companies={"company-digest"})
    digest.edit_list(tmp_path, action="subscribe", list_id=list_id, allowed_companies=set())
    digest.save_reader_location(tmp_path, "ev-digest", mode="article", position=320)
    assert {origin["key"] for origin in model(tmp_path, [article()])["cards"][0]["origins"]} == {list_id}
    digest.edit_list(tmp_path, action="unsubscribe", list_id=list_id, allowed_companies=set())
    assert not model(tmp_path, [article()])["cards"]
    assert queue.load_state(tmp_path)["reading"]["ev-digest"]["reader_positions"]["article"] == 320


def test_saved_and_completion_independent_legacy_opened_is_not_completed(tmp_path):
    state = feed.empty_state()
    state["decisions"]["ev-digest"] = {"saved": True, "read": True, "reaction": "up"}
    state["statements"]["ev-digest"] = [{"id": "statement-retained", "text": "Keep my reviewed note", "confirmed": True}]
    feed.save_state(tmp_path, state)
    assert model(tmp_path, [article()])["cards"][0]["progress"] == "unread"
    queue.apply_action(tmp_path, dimension="reading", item_id="ev-digest", action="mark_read")
    assert model(tmp_path, [article()])["cards"] == []
    completed = model(tmp_path, [article()], {"status": "completed"})["cards"][0]
    assert completed["decision"]["saved"]
    digest.set_personal_decision(tmp_path, "ev-digest", "unsave")
    assert queue.reading_state("ev-digest", queue.load_state(tmp_path)) == "read"
    assert feed.load_state(tmp_path)["statements"]["ev-digest"] == state["statements"]["ev-digest"]


def test_priority_progress_location_and_review_history_survive_each_other(tmp_path):
    queue.apply_action(tmp_path, dimension="reading", item_id="ev-digest", action="keep", reviewer="original")
    queue.apply_action(tmp_path, dimension="reading", item_id="ev-digest", action="set_priority", reading_priority="high")
    digest.save_reader_location(tmp_path, "ev-digest", mode="article", position=610)
    digest.save_reader_location(tmp_path, "ev-digest", mode="brief", position=140)
    queue.apply_action(tmp_path, dimension="reading", item_id="ev-digest", action="start")
    entry = queue.load_state(tmp_path)["reading"]["ev-digest"]
    assert entry["priority"] == "high" and entry["reader_positions"] == {"article": 610, "brief": 140}
    assert entry["state"] == "in_progress"
    queue.apply_action(tmp_path, dimension="reading", item_id="ev-digest", action="mark_read")
    queue.apply_action(tmp_path, dimension="reading", item_id="ev-digest", action="reopen")
    assert queue.load_state(tmp_path)["reading"]["ev-digest"]["priority"] == "high"
    from app.services.review_events import load_review_events
    events = load_review_events(tmp_path)
    assert any(event["action"] == "keep" and event["actor"] == "original" for event in events)
    assert any(event["action"] == "mark_read" for event in events)
    assert any(event["action"] == "set_priority" and "high" in event.get("notes", "") for event in events)


def test_retained_news_across_days_deduplicates_and_cannot_assert_trust(tmp_path):
    old = article(title="Older cached version")
    new = article(title="New cached version", status="published")
    save_bundle(tmp_path, {"today": "2026-09-20", "records": [old, article("ev-older")]})
    save_bundle(tmp_path, {"today": "2026-09-21", "records": [new]})
    records = digest.source_records([article()], tmp_path)
    assert len(records) == 2 and records["ev-digest"]["title"] == article()["title"]
    assert records["ev-digest"]["status"] == "published" and records["ev-older"]["status"] == "unreviewed"
    digest.set_personal_decision(tmp_path, "ev-older", "save")
    assert model(tmp_path, list(records.values()))["cards"][0]["id"] == "ev-older"


def test_missing_saved_source_retains_visible_mark_and_history(tmp_path):
    digest.set_personal_decision(tmp_path, "ev-missing", "save")
    queue.apply_action(tmp_path, dimension="reading", item_id="ev-missing", action="mark_read")
    result = model(tmp_path, [], {"status": "all"})
    assert result["cards"][0]["missing_source"] and result["cards"][0]["progress"] == "read"


@pytest.mark.parametrize("window,start,expected", [("7d", "2026-09-24", 1), ("30d", "2026-09-01", 2), ("ytd", "2026-01-01", 2)])
def test_dates_and_newest_first(tmp_path, window, start, expected):
    rows = [article("ev-old", published_date="2026-09-05"), article("ev-new", published_date="2026-09-30")]
    for row in rows:
        digest.set_personal_decision(tmp_path, row["id"], "save")
    result = model(tmp_path, rows, {"window": window})
    assert len(result["cards"]) == expected
    assert result["cards"][0]["id"] == "ev-new"
    assert len(model(tmp_path, rows, {"berry": "strawberry,blueberry", "country": "geography-chile"})["cards"]) == 2
    assert not model(tmp_path, rows, {"berry": "raspberry"})["cards"]


def test_list_validation_archive_and_state_round_trip(tmp_path):
    with pytest.raises(ValueError):
        digest.edit_list(tmp_path, action="create", name="Bad", company_ids=["person-wrong"], allowed_companies=set())
    list_id = digest.edit_list(tmp_path, action="create", name="List", company_ids=[], allowed_companies=set())
    with pytest.raises(ValueError):
        digest.edit_list(tmp_path, action="create", name="list", allowed_companies=set())
    digest.edit_list(tmp_path, action="subscribe", list_id=list_id, allowed_companies=set())
    feed.snapshot_state(tmp_path)
    digest.edit_list(tmp_path, action="archive", list_id=list_id, allowed_companies=set())
    state = feed.load_state(tmp_path)
    assert state["company_lists"][list_id]["archived"] and list_id not in state["digest_subscriptions"]
    assert digest.company_lists(state) == []


def test_save_from_news_then_digest_complete_reopen_and_old_saved_link(workspace):
    client, repos = workspace
    before = deepcopy(repos.evidence.get("ev-digest"))
    response = client.post("/api/feed-first/react", json={"item_id": "ev-digest", "action": "save"})
    assert response.status_code == 200
    page = client.get("/digest")
    assert page.status_code == 200 and before["title"] in page.text
    assert "data-open-reader" in page.text and "Company lists & subscriptions" in page.text
    assert client.post("/digest/stories/ev-digest", json={"action": "mark_read"}).status_code == 200
    assert before["title"] not in client.get("/digest").text
    assert before["title"] in client.get("/digest?status=completed").text
    assert before["title"] in client.get("/saved").text
    assert client.post("/digest/stories/ev-digest", json={"action": "reopen"}).status_code == 200
    assert before["title"] in client.get("/digest").text
    assert repos.evidence.get("ev-digest") == before


def test_get_is_read_only_and_feedback_does_not_extract(workspace, monkeypatch):
    client, repos = workspace
    digest.set_personal_decision(main.INBOX_DIR, "ev-digest", "save")
    original = feed.state_path(main.INBOX_DIR).read_bytes()
    monkeypatch.setattr(feed, "extract_statements", lambda *args, **kwargs: pytest.fail("Feedback must not extract"))
    monkeypatch.setattr("app.services.feed_first_reader.capture_item", lambda *args, **kwargs: pytest.fail("GET must not acquire"))
    assert client.get("/digest").status_code == 200
    assert client.get("/api/intelligence/ev-digest/reader?personal=1").status_code == 200
    assert feed.state_path(main.INBOX_DIR).read_bytes() == original
    assert not queue.state_path(main.INBOX_DIR).exists()
    assert client.post("/digest/stories/ev-digest", json={"action": "useful"}).status_code == 200
    state = feed.load_state(main.INBOX_DIR)
    assert state["decisions"]["ev-digest"]["reaction"] == "up" and state["statements"] == {}
    assert not state["decisions"]["ev-digest"].get("read")


def test_live_cached_reader_shows_original_separate_from_summary_and_review(workspace):
    client, _ = workspace
    row = article("ev-raw", status="published", summary="Short source synopsis.", article={"paragraphs": [{"text": "Original publisher paragraph, not the summary."}]})
    save_bundle(main.INBOX_DIR, {"today": "2026-09-20", "records": [row]})
    response = client.get("/api/intelligence/ev-raw/reader?personal=1")
    assert response.status_code == 200
    assert "Original publisher paragraph, not the summary." in response.text
    assert 'data-personal-mode="article" aria-pressed="true"' in response.text
    assert "Unreviewed" in response.text and "Read original at publisher" in response.text
    assert 'action="/varieties/discover-source/ev-raw"' in response.text
    assert '/review/ev-raw/publish' not in response.text
    assert client.get("/intelligence/ev-raw?personal=1").status_code == 200


def test_persisted_full_text_is_readable_and_offers_private_name_check(workspace):
    client, _ = workspace
    row = article('ev-full-text', article={'full_text':'Blackberry varieties include Full Text Lead. This is publisher text.'})
    save_bundle(main.INBOX_DIR, {'today':'2026-09-20', 'records':[row]})
    response = client.get('/api/intelligence/ev-full-text/reader?personal=1')
    assert response.status_code == 200 and 'class="article-prose"' in response.text
    assert 'Blackberry varieties include Full Text Lead.' in response.text
    assert 'action="/varieties/discover-source/ev-full-text"' in response.text


def test_summary_and_access_wall_never_masquerade_as_original(workspace):
    client, _ = workspace
    save_bundle(main.INBOX_DIR, {"today": "2026-09-20", "records": [article("ev-thin", summary="Only synopsis", article={"paragraphs": [{"text": "Only synopsis"}]}), article("ev-wall", article={"paragraphs": [{"text": "Verify you are a human. Subscribe to continue reading."}]})]})
    for item_id in ["ev-thin", "ev-wall"]:
        text = client.get(f"/api/intelligence/{item_id}/reader?personal=1").text
        assert 'class="article-prose"' not in text and "Article text isn’t available" in text
        assert '/varieties/discover-source/' not in text


def test_capture_only_on_explicit_action_and_uses_existing_capture_store(workspace, monkeypatch):
    client, _ = workspace
    called = []
    def capture(inbox_dir, record):
        called.append(record["id"])
        return save_capture(inbox_dir, record["id"], {"item_id": record["id"], "passages": ["Publisher original from the requested capture."], "availability": "partial"})
    monkeypatch.setattr("app.services.feed_first_reader.capture_item", capture)
    assert client.get("/api/intelligence/ev-digest/reader?personal=1").status_code == 200
    assert not called
    response = client.post("/api/digest/ev-digest/capture")
    assert response.status_code == 200 and "Publisher original from the requested capture." in response.text
    assert called == ["ev-digest"]


def test_patent_document_hierarchy_refresh_and_private_trust_boundaries(workspace, monkeypatch):
    from app.services import feed_first_reader as reader
    from app.services.patent_reader import patent_document
    from tests.test_patent_reader_document import HTML, URL
    client, repos = workspace
    before = repos.evidence.get("ev-digest")
    document = patent_document(HTML, URL)
    capture = {"ok": True, "item_id": before["id"], "requested_url": before["source_url"], "content_kind": "patent",
               "passages": [r["text"] for r in document["blocks"] if r["kind"] != "heading"],
               "document_blocks": document["blocks"] + [{"kind": "paragraph", "text": '<img src=x onerror="bad">'}], "availability": "partial"}
    reader.save_capture(main.INBOX_DIR, before["id"], capture)
    path = reader.capture_path(main.INBOX_DIR, before["id"])
    stored = path.read_bytes()
    calls = []
    monkeypatch.setattr(reader, "capture_item", lambda *args, **kwargs: calls.append(kwargs))
    response = client.get("/api/intelligence/ev-digest/reader?personal=1")
    assert response.status_code == 200 and calls == [] and path.read_bytes() == stored
    assert 'id="reader-document-claims" tabindex="-1">Claims (1)</h3>' in response.text and "<h4>COMPARISON</h4>" in response.text
    assert '>Site-specific result</td>' in response.text and "source claims, not reviewed facts" in response.text
    assert "&lt;img src=x" in response.text and '<img src=x onerror="bad">' not in response.text
    assert "Reload source text" in response.text and "Read original at publisher" in response.text
    assert client.post("/api/digest/ev-digest/capture?refresh=1").status_code == 200
    assert calls == [{"refresh": True}] and repos.evidence.get("ev-digest") == before
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    public = client.get("/api/intelligence/ev-digest/reader?personal=1")
    assert "as described and illustrated" not in public.text and "Reload source text" not in public.text
    assert '/varieties/discover-source/' not in public.text
    assert client.post("/api/digest/ev-digest/capture?refresh=1").status_code == 403


def test_subscriptions_route_populates_digest_then_unsubscribe_keeps_save(workspace):
    client, _ = workspace
    response = client.post("/digest/lists", data={"action": "create", "name": "Nurseries", "company_ids": "company-digest"}, follow_redirects=False)
    assert response.status_code == 303
    state = feed.load_state(main.INBOX_DIR)
    list_id = next(iter(state["company_lists"]))
    assert article()["title"] not in client.get("/digest").text
    client.post("/digest/lists", data={"action": "subscribe", "list_id": list_id})
    assert article()["title"] in client.get("/digest").text
    client.post("/digest/stories/ev-digest", json={"action": "save"})
    client.post("/digest/lists", data={"action": "unsubscribe", "list_id": list_id})
    assert article()["title"] in client.get("/digest").text


def test_invalid_readonly_and_cross_site_actions_are_blocked(workspace, monkeypatch):
    client, _ = workspace
    assert client.post("/digest/stories/ev-unknown", json={"action": "mark_read"}).status_code == 404
    assert client.post("/digest/stories/ev-digest", json={"action": "confirm"}).status_code == 400
    assert client.post("/digest/stories/ev-digest", json={"action": "set_priority", "priority": "urgent"}).status_code == 400
    assert client.post("/digest/stories/ev-digest", json={"action": "save"}, headers={"Origin": "https://unrelated.invalid"}).status_code == 403
    assert client.get("/digest?window=custom&start=bad-date").status_code == 400
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    for path, data in [("/digest/stories/ev-digest", {"action": "save"}), ("/digest/lists", {"action": "create", "name": "no"}), ("/digest/complete", {"item_ids": "ev-digest"}), ("/api/digest/ev-digest/capture", {})]:
        assert client.post(path, data=data).status_code == 403
    assert client.get("/digest").status_code == 200


def test_bulk_validates_whole_selection_before_writing_and_rejects_redirect(workspace):
    client, _ = workspace
    digest.set_personal_decision(main.INBOX_DIR, "ev-digest", "save")
    assert client.post("/digest/complete", data={"item_ids": ["ev-digest", "ev-unknown"]}).status_code == 404
    assert not queue.state_path(main.INBOX_DIR).exists()
    result = client.post("/digest/complete", data={"item_ids": "ev-digest", "return_to": "https://unrelated.invalid"}, follow_redirects=False)
    assert result.status_code == 303 and result.headers["location"] == "/digest"
    assert queue.reading_state("ev-digest", queue.load_state(main.INBOX_DIR)) == "read"


def test_parallel_personal_updates_do_not_overwrite_other_stories(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda index: digest.set_personal_decision(tmp_path, f"ev-concurrent-{index}", "save"), range(32)))
    assert len(feed.load_state(tmp_path)["decisions"]) == 32
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda index: digest.save_reader_location(tmp_path, f"ev-concurrent-{index}", mode="article", position=300), range(32)))
    assert len(queue.load_state(tmp_path)["reading"]) == 32


def test_canonical_record_controls_prose_scope_and_trust_when_cache_supplies_image(tmp_path):
    raw = article(title="Unreviewed replacement title", entity_ids=["company-wrong"], image_url="https://example.invalid/berry.jpg")
    save_bundle(tmp_path, {"today": "2026-09-20", "records": [raw]})
    original = article()
    result = digest.source_records([original], tmp_path)[original["id"]]
    assert result["title"] == original["title"] and result["entity_ids"] == original["entity_ids"]
    assert result["status"] == "published" and feed.safe_image_url(result) == raw["image_url"]
    assert "article" not in original  # Projection cannot mutate the canonical record.


def test_digest_preview_does_not_hydrate_article_or_transcript_body(tmp_path):
    row = article(article={"paragraphs": [{"text": "Long body must only be read in the selected Reader."}]}, transcript={"text": "Private transcript"})
    digest.set_personal_decision(tmp_path, row["id"], "save")
    card = model(tmp_path, [row])["cards"][0]
    assert card["passages"] == [row["summary"]]
    assert "paragraphs" not in card["record"]["article"] and "transcript" not in card["record"]


def test_registry_list_edit_preserves_brand_and_person_members(workspace):
    client, repos = workspace
    for key, entity_type in [("brand-roster", "brand"), ("person-roster", "person")]:
        repos.entities.create({"id": key, "record_type": "entity", "entity_type": entity_type, "name": key, "status": "unverified"})
    members = ["company-digest", "brand-roster", "person-roster"]
    list_id = digest.edit_list(main.INBOX_DIR, action="create", name="Registry", company_ids=members, allowed_companies=set(members))
    page = client.get("/digest").text
    assert 'value="brand-roster"' in page and 'value="person-roster"' in page
    response = client.post("/digest/lists", data={"action": "edit", "list_id": list_id, "name": "Registry updated", "company_ids": members}, follow_redirects=False)
    assert response.status_code == 303
    assert set(feed.load_state(main.INBOX_DIR)["company_lists"][list_id]["company_ids"]) == set(members)
