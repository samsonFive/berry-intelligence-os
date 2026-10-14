import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import analyst_accounts as accounts, publication_sources, news_workspace
from app.services.feed_first_reader import fetch_public_article, merge_capture
from app.session_auth import reset_login_failures
from app.services.source_body import looks_like_interstitial, reader_content


def test_additional_login_preserves_operator_and_first_login_opens_help(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "existing-analyst")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "existing-test-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "independent-long-test-session-signing-secret")
    monkeypatch.setenv("BIOS_BASIC_AUTH", "false")
    reset_login_failures()
    accounts.create_account(tmp_path, "new.analyst", "new-test-password")
    assert b"new-test-password" not in accounts.account_path(tmp_path).read_bytes()
    client = TestClient(main.app, follow_redirects=False)
    assert client.post("/login", data={"username": "new.analyst", "password": "wrong"}).status_code == 200
    assert accounts.load_accounts(tmp_path)["new.analyst"]["first_login"] is True
    first = client.post("/login", data={"username": "new.analyst", "password": "new-test-password", "next": "/today?window=7d"})
    assert first.headers["location"] == "/guide"
    assert client.get("/guide").status_code == 200
    client.post("/logout")
    again = client.post("/login", data={"username": "new.analyst", "password": "new-test-password", "next": "/today?window=7d"})
    assert again.headers["location"] == "/today?window=7d"
    client.post("/logout")
    old = client.post("/login", data={"username": "existing-analyst", "password": "existing-test-password"})
    assert old.headers["location"] == "/guide"
    with pytest.raises(ValueError, match="already exists"):
        accounts.create_account(tmp_path, "new.analyst", "replacement")
    client.post("/logout")
    accounts.set_account_enabled(tmp_path, "new.analyst", False)
    assert client.post("/login", data={"username": "new.analyst", "password": "new-test-password"}).status_code == 200
    accounts.account_path(tmp_path).write_text("corrupt account store")
    assert accounts.account_credentials_match(tmp_path, "new.analyst", "new-test-password") is False
    unavailable = client.post("/login", data={"username": "existing-analyst", "password": "existing-test-password"})
    assert unavailable.status_code == 503 and "temporarily unavailable" in unavailable.text
    assert "sqlite" not in unavailable.text and "corrupt account store" not in unavailable.text


def test_unicode_credentials_can_use_hash_login_without_comparison_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "existing-analyst")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "existing-test-password")
    accounts.create_account(tmp_path, "new.analyst", "Berries-é-test")
    response = TestClient(main.app, follow_redirects=False).post("/login", data={"username":"new.analyst","password":"Berries-é-test"})
    assert response.headers["location"] == "/guide"


def test_account_store_corruption_cannot_overwrite_existing_data(tmp_path):
    path = accounts.account_path(tmp_path)
    path.parent.mkdir()
    path.write_text("corrupted existing store")
    with pytest.raises(ValueError, match="preserved"):
        accounts.create_account(tmp_path, "new.analyst", "test-password")
    assert path.read_text() == "corrupted existing store"


CONSENT = ("If you choose to Accept all, we will also use cookies and data to develop and improve new services. "
           "Deliver and maintain Google services. Track outages and protect against spam. "
           "Measure audience engagement and site statistics. If you choose to Reject all, we will not use cookies for these additional purposes.")


def test_google_consent_is_not_article_text_even_in_old_saved_capture():
    assert looks_like_interstitial(CONSENT)
    old = {"ok": True, "availability": "full", "requested_url": "https://example.org/story", "passages": [CONSENT]}
    merged = merge_capture({"id": "story", "source_url": old["requested_url"]}, old)
    assert not merged.get("article")
    assert merged["reader_capture"]["availability"] == "blocked"
    assert not reader_content({"article": {"full_text": CONSENT}})["usable_in_app"]
    real = "A blueberry grower announced a new nursery expansion with increased production capacity for its partners. " * 15
    assert not looks_like_interstitial(real + " Our cookie policy is available on the website.")


def test_reader_decodes_publisher_and_rejects_google_host_even_without_wall_words():
    publisher = "https://example.org/blueberry-news"
    token = base64.urlsafe_b64encode(b"\x08\x13" + publisher.encode() + b"\x00").decode().rstrip("=")
    wrapper = "https://news.google.com/rss/articles/" + token
    requests = []
    def transport(request):
        requests.append(str(request.url))
        return httpx.Response(200, text="<p>Blueberry growers have opened a new nursery to increase capacity for their customers across growing regions.</p>")
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        capture = fetch_public_article(wrapper, client=client)
        assert capture["ok"] and capture["url"] == publisher
        blocked = fetch_public_article("https://news.google.com/rss/articles/undecodable", client=client)
    assert requests[0] == publisher
    assert not blocked["ok"] and not blocked["passages"]


def test_metadata_cache_tracks_rejection_edit_delete_and_isolation(tmp_path):
    folder = tmp_path / "evidence"; folder.mkdir()
    path = folder / "draft-one.json"
    record = {"id": "draft-one", "evidence_role": "publication_artifact", "status": "draft", "title": "Original", "entity_ids": ["company-a"]}
    path.write_text(json.dumps(record))
    first, _ = publication_sources.pending_source_previews(tmp_path)
    first[0]["entity_ids"].append("bad-mutation")
    assert publication_sources.pending_source_previews(tmp_path)[0][0]["entity_ids"] == ["company-a"]
    path.write_text(json.dumps({**record, "status": "rejected", "title": "Edited"}))
    fresh, _ = publication_sources.pending_source_previews(tmp_path)
    assert fresh[0]["status"] == "rejected" and fresh[0]["title"] == "Edited"
    path.unlink()
    assert publication_sources.pending_source_previews(tmp_path) == ([], [])


def test_qualification_cache_recomputes_changed_text_and_entity_names():
    news_workspace._qualifying_news.cache_clear()
    args = ("An unfamiliar company expands", "Company announces a new business development", "https://example.org/news", "2026-10-13")
    assert not news_workspace._qualifying_news(*args, (), ())
    assert news_workspace._qualifying_news(*args, ("unfamiliar company",), ())
    assert not news_workspace._qualifying_news("Football scores", "Recent football matches", args[2], args[3], ("unfamiliar company",), ())
