"""Local Google News wrapper decode — no HTTP, no undocumented Google APIs."""

from __future__ import annotations

import base64
from urllib.parse import quote

from app.services.google_news_url import (
    is_google_news_wrapper,
    resolve_google_news_url,
)


PUBLISHER = "https://www.freshplaza.test/article/99/blueberry-acreage-peru"


def google_news_article_url(publisher_url: str, *, nested: bool = False) -> str:
    """Build a wrapper whose token contains `publisher_url` the same way
    production decode reads it: a base64url payload with an embedded
    https URL, optionally nested one layer deeper."""
    inner = base64.urlsafe_b64encode(b"\x08\x13" + publisher_url.encode("utf-8")).decode("ascii").rstrip("=")
    if nested:
        inner = base64.urlsafe_b64encode(b"\x0a" + inner.encode("ascii")).decode("ascii").rstrip("=")
    return f"https://news.google.com/rss/articles/{inner}"


def test_non_wrapper_urls_are_unchanged() -> None:
    assert resolve_google_news_url("https://www.freshplaza.com/story/1") == "https://www.freshplaza.com/story/1"
    assert resolve_google_news_url("") == ""
    assert resolve_google_news_url(None) == ""


def test_simple_encoded_token_resolves_to_publisher_article() -> None:
    wrapper = google_news_article_url(PUBLISHER)
    assert is_google_news_wrapper(wrapper)
    assert resolve_google_news_url(wrapper) == PUBLISHER


def test_nested_encoded_token_resolves_to_publisher_article() -> None:
    wrapper = google_news_article_url(PUBLISHER, nested=True)
    assert resolve_google_news_url(wrapper) == PUBLISHER


def test_google_url_redirect_query_is_unwrapped() -> None:
    tracked = "https://www.google.com/url?q=" + quote(PUBLISHER, safe="")
    wrapper = google_news_article_url(tracked)
    assert resolve_google_news_url(wrapper) == PUBLISHER


def test_homepage_and_google_hosts_are_not_accepted_as_articles() -> None:
    homepage = google_news_article_url("https://www.freshplaza.test/")
    google_host = google_news_article_url("https://news.google.com/rss/articles/other")
    assert resolve_google_news_url(homepage) == homepage
    assert resolve_google_news_url(google_host) == google_host


def test_undecodable_wrapper_is_returned_unchanged() -> None:
    wrapper = "https://news.google.com/rss/articles/wrapper"
    assert resolve_google_news_url(wrapper) == wrapper


def test_invalid_base64_does_not_raise() -> None:
    wrapper = "https://news.google.com/rss/articles/!!!"
    assert resolve_google_news_url(wrapper) == wrapper


def test_query_string_on_wrapper_is_ignored_for_decode() -> None:
    wrapper = google_news_article_url(PUBLISHER) + "?oc=5&hl=en-US"
    assert resolve_google_news_url(wrapper) == PUBLISHER


def test_resolve_is_deterministic_across_repeated_calls() -> None:
    wrapper = google_news_article_url(PUBLISHER, nested=True)
    assert resolve_google_news_url(wrapper) == resolve_google_news_url(wrapper) == PUBLISHER
