from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
import sqlite3
import shutil
import subprocess
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import analyst_accounts, feed_first_reader as reader, personal_digest
from app.services.source_body import clean_reader_text, reader_content


PROSE = "Blueberry growers announced a new nursery in Spain to increase plant supply for commercial producers."
URL = "https://publisher.example/blueberry-nursery"


@pytest.mark.skipif(not shutil.which("node"), reason="Node.js is unavailable")
def test_shipped_reader_and_refresh_javascript_behaviors():
    for script in ("tests/reader_auto_capture_checks.js", "tests/news_refresh_browser_checks.js"):
        result = subprocess.run([shutil.which("node"), script], capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("message", [
    "If you choose to Accept all, we will also use cookies and data to develop and improve new services.",
    "You're seeing this because this is the first time you visited this website.",
    "You’re seeing this because this is the first time you visited this website.",
    "Accept All", "Cookie settings", "Please disable your ad blocker to continue reading.",
])
def test_ui_text_is_removed_anywhere_without_losing_source_prose(message):
    passages = [PROSE, message, PROSE + " The company will work with local farms."]
    assert reader.display_reader_passages(passages) == [passages[0], passages[2]]
    assert clean_reader_text(message + "\n" + PROSE) == PROSE
    record = {"article": {"paragraphs": [{"text": row} for row in passages]}}
    before = deepcopy(record)
    assert PROSE in reader_content(record)["body"]
    assert message not in reader_content(record)["body"]
    assert record == before


def test_article_reporting_about_consent_is_not_stripped():
    source = "Researchers reported that cookie settings and the Accept All button confused website visitors."
    assert reader.display_reader_passages([source]) == [source]
    assert reader.display_reader_passages(["Growers discussed new blueberry cookies sold through local retailers."]) == ["Growers discussed new blueberry cookies sold through local retailers."]


def test_dialogs_are_omitted_without_hiding_real_article():
    html = f"<main><article><p>{PROSE}</p><div role='dialog'><p>You're seeing this because this is your first visit.</p></div><p>{PROSE}</p></article></main>"
    assert reader.paragraphs_from_html(html) == [PROSE, PROSE]


def test_shared_legacy_reader_also_hides_mixed_ui_without_changing_source(tmp_path):
    from app.services.intelligence_feed import build_reader
    record = {"id": "story", "title": "Blueberry nursery", "source_url": URL,
              "article": {"paragraphs": [{"text": PROSE}, {"text": "You're seeing this because this is your first visit."}]}}
    before = deepcopy(record)
    projected = build_reader(record, entities=[], berry_labels={}, inbox_dir=tmp_path, published=[], atomic_drafts=[])
    assert [row["text"] for row in projected["paragraphs"]] == [PROSE]
    assert record == before


def test_cache_warmup_is_read_only_and_does_not_call_collection(selected_story, monkeypatch):
    from app.services.news_warmup import warm_news_cache
    from app.services import feed_first_live
    client, inbox = selected_story
    monkeypatch.setattr(feed_first_live, "live_feed_bundle", lambda **kw: pytest.fail("Warm-up cannot collect news"))
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    before = {str(path): path.read_bytes() for path in inbox.rglob("*") if path.is_file()}
    warm_news_cache()
    assert {str(path): path.read_bytes() for path in inbox.rglob("*") if path.is_file()} == before


def test_new_capture_can_replace_old_consent_only_in_display_projection():
    record = {"id": "story", "source_url": URL, "article": {"full_text": "If you choose to Accept all, we use cookies and data to improve services."}}
    before = deepcopy(record)
    captured = {"ok": True, "availability": "partial", "requested_url": URL, "passages": [PROSE]}
    result = reader.merge_capture(record, captured)
    assert result["article"]["paragraphs"][0]["text"] == PROSE
    assert record == before


def test_repeated_concurrent_openings_share_capture_and_changed_url_retries(tmp_path, monkeypatch):
    calls = []
    def capture(url, **kwargs):
        calls.append(url)
        time.sleep(.03)
        return {"ok": True, "availability": "partial", "url": url, "passages": [PROSE], "retrieved_at": datetime.now(UTC).isoformat()}
    monkeypatch.setattr(reader, "fetch_public_article", capture)
    record = {"id": "story", "source_url": URL}
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: reader.capture_item(tmp_path, record), range(4)))
    assert len(rows) == 4 and calls == [URL]
    reader.capture_item(tmp_path, {**record, "source_url": URL + "-updated"})
    assert calls == [URL, URL + "-updated"]


def test_failed_opening_is_bounded_and_explicit_retry_bypasses_cooldown(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(reader, "fetch_public_article", lambda url, **kw: (calls.append(url) or reader.empty_capture(url, reason="blocked")))
    record = {"id": "story", "source_url": URL}
    assert not reader.capture_item(tmp_path, record)["ok"]
    assert not reader.capture_item(tmp_path, record)["ok"]
    assert calls == [URL]
    reader.capture_item(tmp_path, record, refresh=True)
    assert calls == [URL, URL]


def test_live_account_schema_and_first_login_history_survive_additive_migration(tmp_path):
    path = analyst_accounts.account_path(tmp_path)
    path.parent.mkdir()
    salt = "1234567890abcdef1234567890abcdef"
    encoded = "scrypt$" + salt + "$" + analyst_accounts.password_digest("test-password", salt)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users (username TEXT PRIMARY KEY, password_hash TEXT, first_login_at TEXT)")
        db.execute("INSERT INTO users VALUES (?,?,?)", ("existing.runtime", encoded, "2026-10-13T12:00:00Z"))
    assert analyst_accounts.account_credentials_match(tmp_path, "existing.runtime", "test-password")
    assert analyst_accounts.first_login_destination(tmp_path, "existing.runtime", "/today") == "/today"
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT password_hash, first_login_at FROM users").fetchone() == (encoded, "2026-10-13T12:00:00Z")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: analyst_accounts.first_login_destination(tmp_path, "new.runtime", "/today"), range(8)))
    assert results.count("/guide") == 1


@pytest.fixture
def selected_story(tmp_path, monkeypatch):
    from app.services.feed_first_live import save_bundle
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_entities", lambda: [])
    monkeypatch.setattr(main, "all_facts", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "_feed_first_world", lambda: {"entities": [], "state": {}})
    monkeypatch.setattr(main, "get_draft", lambda key: None)
    save_bundle(tmp_path, {"today": "2026-10-14", "records": [{"id": "story", "source_url": URL, "title": "Blueberry nursery expansion", "summary": "A brief publisher synopsis.", "source_type": "trade_press"}]})
    return TestClient(main.app), tmp_path


def test_one_story_click_returns_loading_shell_then_capture_without_full_feed_scan(selected_story, monkeypatch):
    client, inbox = selected_story
    calls = []
    monkeypatch.setattr(reader, "fetch_public_article", lambda url, **kw: (calls.append(url) or {"ok": True, "availability": "partial", "url": url, "passages": [PROSE]}))
    first = client.get("/api/intelligence/story/reader?personal=1")
    assert first.status_code == 200 and 'data-auto-capture="true"' in first.text
    assert "Loading publisher article" in first.text and "Read original at publisher" in first.text
    assert calls == []
    monkeypatch.setattr(personal_digest, "source_records", lambda *a, **k: pytest.fail("Capture must not build the whole feed"))
    response = client.post("/api/digest/story/capture")
    assert response.status_code == 200 and PROSE in response.text and 'data-auto-capture="false"' in response.text
    assert calls == [URL]
    again = client.get("/api/intelligence/story/reader?personal=1")
    assert 'data-auto-capture="false"' in again.text and PROSE in again.text


def test_capture_failure_stays_readable_without_an_automatic_retry_loop(selected_story, monkeypatch):
    client, _ = selected_story
    monkeypatch.setattr(reader, "fetch_public_article", lambda url, **kw: reader.empty_capture(url, reason="blocked"))
    response = client.post("/api/digest/story/capture")
    assert response.status_code == 200 and 'data-auto-capture="false"' in response.text
    assert "Retry source text" in response.text and "consent or access page" in response.text
    assert "A brief publisher synopsis." in response.text
