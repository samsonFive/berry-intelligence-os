"""Real HTML fetch + readable-text extraction for written articles.

This module owns exactly one job: given a URL, produce a normalized,
paragraph-indexed article body a human can review and a future qualified
model can later ground Atomic Evidence in. It does not discover sources,
does not decide relevance, does not call any AI provider, and never
attempts to bypass authentication or a paywall -- a wall is a terminal,
reportable failure, not something to work around.

Failure is always structured (`ArticleAcquisitionError.category`) so a
caller processing a batch of URLs can record *why* one item failed and
move on, rather than treating every failure the same way. One blocked or
malformed page must never abort a batch -- that discipline lives in the
caller (see `scripts/ingest_articles.py`), but the categories here are
what make that discipline possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import trafilatura

ARTICLE_ACQUISITION_VERSION = "article-acquisition-v1"
ARTICLE_FETCH_TIMEOUT_SECONDS = 20
ARTICLE_FETCH_USER_AGENT = "berry-intelligence-os-article-acquisition/1.0"
MIN_BODY_CHARS = 200

# Real, observed bot-wall/consent-wall signals. Deliberately the same
# recognize-don't-evade discipline as scripts/resolve_real_summaries.py's
# looks_blocked() -- extended here with a couple of generic paywall phrases
# since this module fetches full article pages, not just Google News
# redirect targets, and is far more likely to meet a subscription wall.
_BLOCK_SIGNALS = (
    "unusual traffic",
    "verify you are a human",
    "our systems have detected",
    "captcha",
    "access to this page has been denied",
    "additional security check is required",
    "attention required! | cloudflare",
    "checking your browser before accessing",
)
_PAYWALL_SIGNALS = (
    "subscribe to continue reading",
    "subscribe to read",
    "this content is for subscribers only",
    "already a subscriber? sign in",
    "create a free account to continue",
    "log in to continue reading",
)
_INTERSTITIAL_SIGNALS = (
    "before you continue to google",
    "consent.google.com",
    "we use cookies and data to",
    "privacy reminder",
)


class ArticleAcquisitionError(Exception):
    """A structured, categorized article-fetch failure.

    `category` is one of: timeout, http_error, blocked, paywall, interstitial,
    malformed_html, empty_body, redirect_error, script_rendered,
    transport_error. Never
    raised for "we chose not to try" (auth bypass) -- only for real,
    observed failure conditions.
    """

    def __init__(self, message: str, *, category: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class ArticleParagraph:
    index: int
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"index": self.index, "text": self.text}


@dataclass(frozen=True)
class ArticleBody:
    """A normalized, provenance-carrying article body -- this project's
    text-artifact analogue of a normalized transcript, deliberately not
    forced into TranscriptArtifact's audio-segment shape (no timestamps
    exist for written text; paragraph index is the locator instead)."""

    source_url: str
    paragraphs: tuple[ArticleParagraph, ...]
    word_count: int
    content_sha256: str
    fetched_at: str
    extractor: str
    extractor_version: str
    author: str | None = None
    final_url: str | None = None
    title: str | None = None
    published_date: str | None = None
    language: str | None = None

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.paragraphs)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "final_url": self.final_url,
            "paragraphs": [p.as_dict() for p in self.paragraphs],
            "word_count": self.word_count,
            "content_sha256": self.content_sha256,
            "author": self.author,
            "title": self.title,
            "published_date": self.published_date,
            "language": self.language,
            "acquisition": {
                "method": "readable_text_extraction",
                "extractor": self.extractor,
                "extractor_version": self.extractor_version,
                "fetched_at": self.fetched_at,
                "version": ARTICLE_ACQUISITION_VERSION,
            },
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def _looks_blocked_or_paywalled(html: str) -> str | None:
    """Returns a concrete wall category if a known signal is present in
    the visible page content, else None. Checked before attempting
    extraction so a wall is reported honestly rather than silently
    extracting whatever thin text sits in front of the wall.

    Script/style content is stripped before matching -- confirmed
    necessary against a real page: many ordinary, unblocked pages load a
    reCAPTCHA script (`<script src=".../recaptcha/api.js">`) for an
    unrelated comment/contact form, which would otherwise false-positive
    on the bare "captcha" signal despite the page being a normal 200 with
    real article content."""
    visible = _SCRIPT_STYLE_RE.sub(" ", html[:20000])
    haystack = visible[:6000].lower()
    if any(signal in haystack for signal in _INTERSTITIAL_SIGNALS):
        return "interstitial"
    if any(signal in haystack for signal in _BLOCK_SIGNALS):
        return "blocked"
    if any(signal in haystack for signal in _PAYWALL_SIGNALS):
        return "paywall"
    return None


_NAV_JUNK_LINES = {
    "you are here", "back to top", "home", "share this article", "share this",
    "read more", "related articles", "related stories", "sign up", "subscribe",
    "advertisement", "skip to content", "skip to main content", "menu",
}


def _split_paragraphs(text: str, *, title: str | None = None) -> tuple[ArticleParagraph, ...]:
    """Split trafilatura's extracted text into paragraphs and drop obvious
    leading chrome (nav breadcrumbs, a duplicated title line) confirmed
    against a real page during this feature's own pilot: trafilatura emits
    one paragraph per line (a single `\\n`, not a blank-line-separated
    `\\n\\n` as might be assumed), and on at least one real site emitted
    literal "You are here" / "Back to top" navigation lines followed by
    the article's own title, ahead of the real body. This is a small,
    targeted fix for junk actually observed, not an attempt at a general
    boilerplate remover -- see this module's docstring on scope."""
    raw_blocks = [block.strip() for block in (text or "").split("\n")]
    blocks = [block for block in raw_blocks if block]

    normalized_title = (title or "").strip().casefold()
    while blocks:
        candidate = blocks[0].casefold()
        if candidate in _NAV_JUNK_LINES or (normalized_title and candidate == normalized_title):
            blocks.pop(0)
            continue
        break

    # A bare photo-credit line embedded mid-article -- also confirmed
    # against a real page ("© J. Marchini Farms" appearing as its own
    # paragraph). Short and credit-shaped only; never touches a real
    # sentence that happens to mention a photo.
    blocks = [
        block for block in blocks
        if not (len(block) < 60 and re.match(r"^(©|image:|photo:|credit:)", block, re.IGNORECASE))
    ]

    return tuple(ArticleParagraph(index=i, text=block) for i, block in enumerate(blocks))


def fetch_article(url: str, *, timeout: float = ARTICLE_FETCH_TIMEOUT_SECONDS) -> ArticleBody:
    """Fetch one article URL and extract its readable body.

    Never attempts to authenticate, solve a CAPTCHA, or otherwise bypass a
    wall -- a detected wall is always a terminal ArticleAcquisitionError,
    not something this function works around.
    """
    if not url or not url.strip():
        raise ArticleAcquisitionError("empty article URL", category="malformed_html")

    try:
        response = httpx.get(
            url,
            timeout=timeout,
            headers={"User-Agent": ARTICLE_FETCH_USER_AGENT},
            follow_redirects=True,
        )
    except httpx.TimeoutException as exc:
        raise ArticleAcquisitionError(f"timed out fetching {url}: {exc}", category="timeout") from exc
    except httpx.TooManyRedirects as exc:
        raise ArticleAcquisitionError(f"redirect loop fetching {url}: {exc}", category="redirect_error") from exc
    except httpx.TransportError as exc:
        raise ArticleAcquisitionError(f"transport error fetching {url}: {exc}", category="transport_error") from exc

    if response.status_code == 403:
        raise ArticleAcquisitionError(f"403 fetching {url} -- likely bot-blocked", category="blocked")
    if response.status_code == 401:
        raise ArticleAcquisitionError(f"401 fetching {url} -- authentication required", category="paywall")
    if response.status_code >= 400:
        raise ArticleAcquisitionError(
            f"HTTP {response.status_code} fetching {url}", category="http_error"
        )

    # Google News RSS article links are JavaScript wrappers, not article
    # pages and not HTTP redirects. Treating their shared wrapper/chrome as
    # readable source text caused the historic repeated-body incident. A
    # publisher URL must be resolved by discovery before article extraction;
    # the wrapper itself can never be a FULL_ARTICLE artifact.
    requested_host = (urlparse(url).hostname or "").casefold()
    final_host = (urlparse(str(response.url)).hostname or "").casefold()
    if requested_host == "news.google.com" and final_host in {"news.google.com", "consent.google.com"}:
        raise ArticleAcquisitionError(
            "Google News wrapper did not resolve to a publisher article",
            category="interstitial" if final_host == "consent.google.com" else "script_rendered",
        )

    html = response.text
    wall = _looks_blocked_or_paywalled(html)
    if wall:
        raise ArticleAcquisitionError(f"{wall} wall detected fetching {url}", category=wall)

    try:
        extracted_json = trafilatura.extract(
            html,
            url=str(response.url),
            output_format="json",
            with_metadata=True,
            favor_precision=True,
            include_comments=False,
            include_tables=False,
        )
    except Exception as exc:  # noqa: BLE001 -- any extractor-internal failure is a reportable acquisition failure, not a crash
        raise ArticleAcquisitionError(f"extraction failed for {url}: {exc}", category="malformed_html") from exc

    if not extracted_json:
        raise ArticleAcquisitionError(f"no extractable article body found at {url}", category="empty_body")

    import json as _json

    try:
        extracted = _json.loads(extracted_json)
    except ValueError as exc:
        raise ArticleAcquisitionError(f"extractor returned malformed output for {url}: {exc}", category="malformed_html") from exc

    body_text = (extracted.get("text") or "").strip()
    if len(body_text) < MIN_BODY_CHARS:
        raise ArticleAcquisitionError(
            f"extracted body too short ({len(body_text)} chars) at {url} -- likely not a real article page",
            category="empty_body",
        )

    paragraphs = _split_paragraphs(body_text, title=extracted.get("title"))
    word_count = len(body_text.split())
    content_sha256 = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

    return ArticleBody(
        source_url=url,
        final_url=str(response.url) if str(response.url) != url else None,
        paragraphs=paragraphs,
        word_count=word_count,
        content_sha256=content_sha256,
        fetched_at=_now_iso(),
        extractor="trafilatura",
        extractor_version=trafilatura.__version__,
        author=extracted.get("author") or None,
        title=extracted.get("title") or None,
        published_date=extracted.get("date") or None,
        language=extracted.get("language") or None,
    )


def repeated_body_conflict(
    body: ArticleBody, existing_records: list[dict[str, Any]], *, threshold: int = 3,
) -> bool:
    """Reject the third use of one body across distinct publication URLs.

    Two matching bodies may be a legitimate reprint pair. Three or more
    distinct URLs use the same conservative conflict threshold as historic
    Source Fidelity Recovery.
    """
    urls = {
        str(record.get("source_url") or "").strip()
        for record in existing_records
        if isinstance(record.get("article"), dict)
        and record["article"].get("content_sha256") == body.content_sha256
        and record.get("source_url")
    }
    urls.add(body.source_url)
    return len(urls) >= threshold
