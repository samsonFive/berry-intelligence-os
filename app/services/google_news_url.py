"""Resolve Google News RSS wrapper URLs to a publisher article URL.

Local decode only. Does not fetch, does not call an undocumented Google
endpoint, and does not treat wrapper HTML as an article body.

Google News RSS `<link>` values are `news.google.com/rss/articles/<token>`
identifiers. The token is a base64url payload that often already contains
the publisher URL. HTTP follow-redirects against the wrapper itself do not
yield that URL (TD-059): Google returns a 200 SPA shell. Fetching that
shell as readable source caused the historic repeated-body incident.

A wrapper that cannot be decoded is returned unchanged so
`fetch_article()`'s existing `script_rendered` / `interstitial` guards
still fire. Publisher homepages are not accepted as article URLs.
"""

from __future__ import annotations

import base64
import re
from urllib.parse import parse_qs, unquote, urlparse

GOOGLE_NEWS_WRAPPER_HOSTS = frozenset({"news.google.com"})
_GOOGLE_TRACKING_HOSTS = frozenset({
    "news.google.com",
    "consent.google.com",
    "www.google.com",
    "google.com",
    "accounts.google.com",
})
_MAX_DECODE_DEPTH = 3
_HTTP_URL_RE = re.compile(rb"https?://[^\x00-\x20\x7f-\xff\"'<>\\]+")
_NESTED_TOKEN_RE = re.compile(rb"(?:CBMi|AU_)?[A-Za-z0-9_-]{16,}")


def is_google_news_wrapper(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").casefold()
    if host not in GOOGLE_NEWS_WRAPPER_HOSTS:
        return False
    path = parsed.path.casefold()
    return "/rss/articles/" in path or path.startswith("/articles/")


def resolve_google_news_url(url: str | None) -> str:
    """Return a publisher article URL when one is encoded in `url`.

    Non-wrapper URLs and undecodable wrappers are returned unchanged
    (empty input stays empty).
    """
    text = (url or "").strip()
    if not text or not is_google_news_wrapper(text):
        return text
    token = urlparse(text).path.rstrip("/").rsplit("/", 1)[-1]
    if not token:
        return text
    resolved = _decode_token(token, depth=0)
    return resolved or text


def _decode_token(token: str, *, depth: int) -> str | None:
    if depth >= _MAX_DECODE_DEPTH or not token:
        return None
    payload = _b64decode(token)
    if payload is None:
        return None
    for candidate in _urls_from_payload(payload):
        publisher = _publisher_article_url(candidate)
        if publisher:
            return publisher
    for nested in _nested_tokens(payload):
        found = _decode_token(nested, depth=depth + 1)
        if found:
            return found
    return None


def _b64decode(token: str) -> bytes | None:
    padded = token + ("=" * ((4 - len(token) % 4) % 4))
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return None


def _urls_from_payload(payload: bytes) -> list[str]:
    found: list[str] = []
    for match in _HTTP_URL_RE.finditer(payload):
        raw = match.group(0).decode("ascii", errors="ignore").rstrip(".,);]")
        if raw:
            found.append(raw)
    return found


def _nested_tokens(payload: bytes) -> list[str]:
    tokens: list[str] = []
    for match in _NESTED_TOKEN_RE.finditer(payload):
        tokens.append(match.group(0).decode("ascii"))
    return tokens


def _publisher_article_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if not host:
        return None
    if host in {"www.google.com", "google.com"} and parsed.path.rstrip("/") == "/url":
        target = parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("url")
        if not target:
            return None
        return _publisher_article_url(unquote(target[0]))
    if host in _GOOGLE_TRACKING_HOSTS:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.path in {"", "/"}:
        return None
    return url
