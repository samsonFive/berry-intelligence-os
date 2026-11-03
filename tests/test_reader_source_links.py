"""Publisher navigation is honest, read-only and independent of source trust."""
import base64
from copy import deepcopy

from html.parser import HTMLParser
import re
import pytest

from app import main
from app.services import feed_first, feed_first_reader as reader, publisher_coverage
from app.services.feed_first_live import save_bundle
from app.services.reader_source_links import source_links
from tests.test_personal_digest import article, workspace

class LinkParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = {**dict(attrs), "text": ""}

    def handle_data(self, text):
        if self.current is not None:
            self.current["text"] += text

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append(self.current)
            self.current = None


def anchor(html, **attrs):
    return next(link for link in LinkParser(html).links if all(link.get(key) == value for key, value in attrs.items()))


WRAPPER = "https://news.google.com/rss/articles/opaque-unresolved-id"
HOME = "https://publisher.example"
ARTICLE = HOME + "/blueberry-nursery"
PROSE = "Blueberry growers announced a new nursery in Spain to supply commercial producers."


def captured(**changes):
    return {"item_id": "ev-links", "requested_url": WRAPPER, "url": ARTICLE,
            "ok": True, "availability": "partial", "passages": [PROSE], **changes}


def stored(workspace, **changes):
    client, _ = workspace
    row = article("ev-links", source_url=WRAPPER, origin_publisher_url=HOME, **changes)
    save_bundle(main.INBOX_DIR, {"today": "2026-11-03", "records": [row]})
    return client, row


def test_local_decode_keeps_original_identity_and_review_fields():
    token = base64.urlsafe_b64encode(b"\x08\x13" + ARTICLE.encode() + b"\x00").decode().rstrip("=")
    row = article(source_url="https://news.google.com/rss/articles/" + token)
    before = deepcopy(row)
    card = feed_first.present_item(row, entities_by_id={}, state=feed_first.empty_state(), filters={})
    assert card["source_link_url"] == ARTICLE
    assert card["source_link_label"] == "Read original at publisher"
    assert card["source_url"] == before["source_url"] and card["record"] == before and row == before


@pytest.mark.parametrize("url", [WRAPPER, "https://consent.google.com/m", "https://accounts.google.com/ServiceLogin",
                                 "https://NEWS.GOOGLE.COM./articles/opaque", "https://www.google.com/url?q=anything"])
def test_google_shells_are_never_described_as_publisher_articles(url):
    links = source_links({"source_url": url, "origin_publisher_url": HOME})
    assert links["source_link_url"] == url and links["source_link_unresolved"]
    assert links["source_link_label"] == "Open Google News link" and links["publisher_home_url"] == HOME


@pytest.mark.parametrize("url", ["javascript:alert(1)", "http://127.0.0.1/private", "http://2130706433/story",
                                 "https://user:secret@publisher.example/story", "https://[invalid/story", None])
def test_unsafe_or_malformed_originals_do_not_acquire_an_unrelated_destination(url):
    links = source_links({"id": "ev-links", "source_url": url}, capture=captured(), resolved_url=ARTICLE)
    assert links["source_link_url"] == "" and not links["publisher_home_url"]


@pytest.mark.parametrize("changes", [
    {"item_id": "other"}, {"requested_url": HOME + "/other"}, {"ok": False}, {"ok": "true"},
    {"availability": "blocked"}, {"availability": "error"}, {"url": "https://consent.google.com/m"},
    {"url": "http://127.0.0.1/story"}, {"url": HOME},
])
def test_mismatched_failed_homepage_and_consent_captures_cannot_supply_article_link(changes):
    row = {"id": "ev-links", "source_url": WRAPPER}
    assert source_links(row, capture=captured(**changes))["source_link_url"] == WRAPPER


def test_successful_exact_source_capture_and_legacy_missing_item_id_remain_usable():
    row = {"id": "ev-links", "source_url": WRAPPER}
    before = deepcopy(row)
    capture = captured()
    assert source_links(row, capture=capture)["source_link_url"] == ARTICLE
    del capture["item_id"]
    assert source_links(row, capture=capture)["source_link_url"] == ARTICLE
    assert row == before
    assert source_links({"source_url": HOME})["source_link_label"] == "Open source website"


def test_recorded_publisher_fallback_excludes_google_and_private_hosts():
    for home in ("http://127.0.0.1", "https://consent.google.com/m", "javascript:alert(1)"):
        assert source_links({"source_url": WRAPPER, "origin_publisher_url": home}, publisher_url=HOME)["publisher_home_url"] == HOME
    assert not source_links({"source_url": ARTICLE, "origin_publisher_url": HOME})["publisher_home_url"]


def test_reader_reuses_exact_success_without_fetch_or_url_rewrite(workspace, monkeypatch):
    client, row = stored(workspace)
    path = reader.save_capture(main.INBOX_DIR, row["id"], captured())
    before = path.read_bytes()
    monkeypatch.setattr(reader, "fetch_public_article", lambda *a, **k: pytest.fail("GET must not fetch"))
    monkeypatch.setattr(publisher_coverage, "cached_publisher_target", lambda *a: pytest.fail("Resolved capture needs no discovery lookup"))
    response = client.get("/api/intelligence/ev-links/reader?personal=1")
    assert response.status_code == 200
    assert anchor(response.text, **{"aria-label": "Read original at publisher (new tab)"})["href"] == ARTICLE
    assert anchor(response.text, text="Read original at publisher ↗")["href"] == ARTICLE
    assert PROSE in response.text and "hasn’t been recovered" not in response.text
    assert path.read_bytes() == before and row["source_url"] == WRAPPER


def test_unresolved_reader_keeps_publisher_home_visible_and_explains_consent(workspace, monkeypatch):
    client, _ = stored(workspace)
    reader.save_capture(main.INBOX_DIR, "ev-links", captured(ok=False, availability="blocked", url="https://consent.google.com/m", passages=[]))
    monkeypatch.setattr(reader, "fetch_public_article", lambda *a, **k: pytest.fail("GET must not fetch"))
    response = client.get("/api/intelligence/ev-links/reader?personal=1")
    assert response.status_code == 200
    assert anchor(response.text, text="Open Google News link ↗")["href"] == WRAPPER
    assert anchor(response.text, text="Publisher website ↗")["href"] == HOME
    assert "hasn’t been recovered from Google News yet" in response.text
    assert "Open the publisher link above" not in response.text
    assert "consent.google.com" not in str(LinkParser(response.text).links)


def test_reader_uses_existing_verified_discovery_without_network(workspace, monkeypatch):
    client, _ = stored(workspace)
    monkeypatch.setattr(publisher_coverage, "cached_publisher_target", lambda inbox, record: ARTICLE)
    monkeypatch.setattr(reader, "fetch_public_article", lambda *a, **k: pytest.fail("GET must not fetch"))
    response = client.get("/api/intelligence/ev-links/reader?personal=1")
    assert anchor(response.text, text="Read original at publisher ↗")["href"] == ARTICLE
    assert "hasn’t been recovered" not in response.text


def test_news_labels_unresolved_wrapper_without_loading_capture_body(workspace, monkeypatch):
    client, _ = stored(workspace)
    monkeypatch.setattr(reader, "load_capture", lambda *a: pytest.fail("Feed must not hydrate capture bodies"))
    monkeypatch.setattr(publisher_coverage, "cached_publisher_target", lambda *a: pytest.fail("Feed must not scan discovery"))
    monkeypatch.setattr(reader, "fetch_public_article", lambda *a, **k: pytest.fail("GET must not fetch"))
    response = client.get("/today?view=unreviewed")
    card = re.search(r'<article[^>]*data-item-id="ev-links".*?</article>', response.text, re.S)
    assert response.status_code == 200 and card
    assert anchor(card.group(), **{"aria-label": "Open Google News link (new tab)"})["href"] == WRAPPER
    assert "Read original at publisher" not in card.group()
