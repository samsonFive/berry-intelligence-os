"""Spoken-word media discovery/acquisition -- the upstream edge of the
future audio/video intelligence pipeline, strictly outside the Evidence
trust boundary.

## Where this sits

    External Source -> Discovery -> Normalized Staging Item -> Optional Raw
    Transcript Artifact
    ---------------- TRUST / ANALYSIS BOUNDARY ----------------
    (future interpretation/extraction/review pipeline)

A discovered podcast episode produced by this module is never Evidence. A
transcript acquired by this module is never Evidence and never a Fact. No
function in this file writes to `data/evidence/`, `data/facts/`,
`data/assessments/`, `data/recommendations/`, or `inbox/evidence/` (the
existing draft-Evidence intake this module deliberately does not touch --
see `move_draft_attachments()`/`save_draft()` in `app/main.py`). Everything
this module produces lives under `inbox/discovered_media/`, itself inside
the project's pre-existing "runtime-created, untrusted, disposable"
`inbox/` convention (`.gitignore`; `docs/04-technical-architecture/
ARCHITECTURE.md` "Intake and the inbox").

## Architecture: one generic adapter mechanism, not a Lucentlands-specific one

A `MediaDiscoveryAdapter` is a `(fetch, list_entries, normalize)` function
triple keyed by an `adapter type` string -- `"podcast_rss"` (any podcast
RSS/Atom feed) and `"youtube_feed"` (any public YouTube channel/playlist
Atom feed, `https://www.youtube.com/feeds/videos.xml?channel_id=...` or
`?playlist_id=...`, no API key or credentials required) as of the
spoken-word-source-expansion phase. Which adapter type a given Source uses,
and that adapter's configuration (its feed URL(s)), is read from that
Source's own record in `data/configuration/sources.json` -- an optional
`discovery` object (`{"adapter": "podcast_rss", "feed_url": "..."}`, or
`{"adapter": ..., "feed_urls": [...]}` for a source whose content spans more
than one feed -- see `discover_source()`) -- not hardcoded per source_id in
this module. Registering a *second* source on an adapter type that already
exists therefore requires zero code changes: add the same shape of
`discovery` block, pointing at that show's own feed(s), to that source's
registry entry. `source-lucentlands-podcast` and
`source-business-of-blueberries-podcast` both use `podcast_rss` (with zero
adapter code changes between them -- see this module's companion report for
the real, verified comparison); `source-redagricola-on-the-road` uses
`youtube_feed`, since "Redagricola On The Road" resolves to a YouTube-native
video series (two per-country playlists), not an RSS podcast. New adapter
types are added only for a genuinely new publication technology, never for
a new publisher on an existing one.

## Dedupe / idempotency

Every normalized item gets a durable identity via `_dedupe_identity()`,
preferring (in order) a publisher/feed GUID, a platform-native item id
(exercised by the youtube_feed adapter, which populates `platform_item_id`
with YouTube's own video id rather than a feed GUID), a normalized
canonical URL, and finally a hash of normalized title+published_date as a
last resort. The staging record's filename is derived from that identity,
never from title -- so a publisher correcting a typo in an episode title on
a later poll does not create a second logical item (`upsert_discovered_item()`
below updates the existing record's mutable fields in place instead).

## Reconciliation, not import

`possible_evidence_matches()` inspects already-published Evidence read-only
(via `EvidenceRepository.list()`) to flag *candidate* matches between a
freshly discovered item and Evidence a human already created by hand (e.g.
`ev-lucentlands-scaling-blueberry-industry-2025`, entered before this
adapter existed). It never mutates Evidence, never creates Evidence, and is
advisory only -- a future review step decides what a "match" means for its
own architecture; this module does not encode that decision.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

import feedparser
import httpx

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR

STAGING_SCHEMA_VERSION = 1

MEDIA_DISCOVERY_FETCH_TIMEOUT_SECONDS = 15
MEDIA_DISCOVERY_USER_AGENT = "berry-intelligence-os-media-discovery/1.0"

# Mirrors evidence.schema.json's `media_format` enum (schemas/evidence.schema.json)
# so a future promotion step can copy this value across verbatim -- this
# module does not import that schema or validate against it (staging
# records are not Evidence and must not claim to be), it only reuses the
# same vocabulary deliberately.
MEDIA_FORMATS = {"web_article", "podcast", "video", "conference_video"}

# Distinct from evidence.schema.json's `transcript.status` (not_available /
# pending / available) on purpose: this is a *detection* result about what
# the publisher/platform exposes, produced before any transcript has been
# acquired or reviewed, not a statement about whether Evidence has a
# transcript.
TRANSCRIPT_UNKNOWN = "unknown"
TRANSCRIPT_NOT_DETECTED = "not_detected"
TRANSCRIPT_PUBLISHER = "publisher_transcript"
TRANSCRIPT_PLATFORM_CAPTIONS = "platform_captions"
# Distinct from all of the above: a written article has no transcript
# concept at all, so "not_detected" (checked, none found) would be a false
# claim that a check for a nonexistent thing was performed. This is the
# signal app/services/media_orchestration.py's transcription-skip guard
# keys off of.
TRANSCRIPT_NOT_APPLICABLE = "not_applicable"

DEDUPE_STRATEGY_GUID = "guid"
DEDUPE_STRATEGY_PLATFORM_ID = "platform_id"
DEDUPE_STRATEGY_CANONICAL_URL = "canonical_url"
DEDUPE_STRATEGY_METADATA_HASH = "metadata_hash"

# Bounded initial-discovery policy for spoken media (Continuous Intelligence
# Refresh, 2026-08-18). A real recurring run against a source with a deep
# back-catalog (a podcast feed with hundreds of episodes) produced 562 new
# untranscribed drafts in a single pass the first time it was ever checked --
# useful diagnostic evidence, but not acceptable recurring behavior. Article
# sources are deliberately NOT bounded here: their volume is already gated
# downstream by app/services/relevance_screen.py's body-aware screening
# before a draft is ever created, so discovery-time item count was never the
# article flood's cause the way it is for spoken media (podcast/video items
# get a draft unconditionally -- there is no per-episode relevance screen).
SPOKEN_MEDIA_FORMATS = {"podcast", "video", "conference_video"}
INITIAL_DISCOVERY_MAX_ITEMS = 10
INITIAL_DISCOVERY_LOOKBACK_DAYS = 30


class DiscoveryError(Exception):
    """Raised only for programmer-error inputs (unknown source_id, unknown
    adapter type) -- never for network/feed failures, which are captured in
    a DiscoveryRunResult instead so one bad source doesn't crash a caller
    iterating over several."""


# ---------------------------------------------------------------------------
# small, local helpers (deliberately not imported from app.main -- that
# module is under concurrent, active edit by another workstream right now;
# this module stays self-contained so the two can't collide)
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


def _slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return slug[:60] or "item"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_url_for_dedupe(url: str) -> str:
    """Best-effort canonicalization so trivial URL variance (scheme case,
    a trailing slash, a `www.` prefix, a tracking query string) doesn't
    manufacture a second logical item out of the same episode. Not a
    general-purpose URL normalizer -- just enough determinism for dedupe."""
    parsed = urlparse((url or "").strip())
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))


def _parse_duration_to_seconds(raw: str | None) -> int | None:
    """`itunes:duration` is documented as HH:MM:SS but publishers routinely
    emit MM:SS or a bare integer second count -- accept all three, and
    degrade to None (not 0, which would falsely claim a known zero-length
    episode) for anything else."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    parts = raw.split(":")
    if not all(p.isdigit() for p in parts) or not (1 <= len(parts) <= 3):
        return None
    parts_int = [int(p) for p in parts]
    while len(parts_int) < 3:
        parts_int.insert(0, 0)
    hours, minutes, seconds = parts_int
    return hours * 3600 + minutes * 60 + seconds


def _parse_published_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def classify_initial_backlog(
    indexed_items: list[tuple[int, "NormalizedItem"]],
    *,
    now: str,
    allow_historical_backfill: bool = False,
) -> set[int]:
    """Returns the subset of `indexed_items`' indexes that should be flagged
    `historical_backlog` on a spoken-media source's first-ever discovery
    run. `indexed_items` is `(index, normalized_item)` pairs for exactly one
    discover_source() call's successfully-normalized entries -- article
    items are never included by the caller (see SPOKEN_MEDIA_FORMATS above).

    Policy: keep the INITIAL_DISCOVERY_MAX_ITEMS most recent items published
    within INITIAL_DISCOVERY_LOOKBACK_DAYS of `now`, plus always the single
    most recent item regardless of age (a dormant show's only recent episode
    being 40 days old should still yield one item, not zero -- "capture a
    small useful recent window", not "capture nothing"). Everything else is
    backlog. `allow_historical_backfill=True` is the explicit operator
    override for intentional historical backfill -- returns an empty set,
    keeping every item current."""
    if allow_historical_backfill or not indexed_items:
        return set()
    now_date = _parse_published_date(now[:10]) or datetime.now(timezone.utc).date()
    ranked = sorted(
        indexed_items,
        key=lambda pair: _parse_published_date(pair[1].published_date) or datetime.min.date(),
        reverse=True,
    )
    keep: set[int] = set()
    for rank, (index, item) in enumerate(ranked):
        if rank >= INITIAL_DISCOVERY_MAX_ITEMS:
            break
        published = _parse_published_date(item.published_date)
        within_lookback = published is not None and (now_date - published).days <= INITIAL_DISCOVERY_LOOKBACK_DAYS
        if within_lookback or rank == 0:
            keep.add(index)
    return {index for index, _item in ranked if index not in keep}


# ---------------------------------------------------------------------------
# adapter mechanism
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalizedItem:
    """One discovered episode/video, normalized but not yet assigned a
    dedupe identity or persisted -- `discover_source()` fills in `id`/
    `dedupe_strategy`/`dedupe_key` after this is produced."""

    title: str
    media_format: str
    canonical_url: str | None
    external_id: str | None
    platform_item_id: str | None
    published_date: str | None
    description: str
    duration_seconds: int | None
    transcript_availability: dict[str, Any]
    raw_metadata: dict[str, Any]


def _fetch_podcast_rss(feed_url: str) -> tuple[Any, bytes]:
    """Fetch + parse an RSS/Atom podcast feed. Raises on transport failure
    (caller turns that into a feed-level DiscoveryRunResult failure, never
    a crash) -- but does NOT raise on a malformed-but-partially-readable
    feed body, since feedparser is deliberately lenient (`bozo` flag) and a
    feed with one broken tag still usually yields readable <item> entries."""
    response = httpx.get(
        feed_url,
        timeout=MEDIA_DISCOVERY_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": MEDIA_DISCOVERY_USER_AGENT},
        follow_redirects=True,
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    return parsed, response.content


def _classify_podcast_media_format(entry: Any) -> str:
    """Podcast-RSS-specific classification, based on the enclosure MIME
    type the publisher declared -- not a guess from the title/description.
    Deliberately does not touch Entity Type (per project principle): this
    is describing the physical form of the item, the same distinction
    evidence.schema.json's `media_format` field draws for Evidence."""
    enclosures = getattr(entry, "enclosures", None) or []
    for enclosure in enclosures:
        enclosure_type = (enclosure.get("type") or "").lower()
        if enclosure_type.startswith("video/"):
            return "video"
        if enclosure_type.startswith("audio/"):
            return "podcast"
    # A podcast_rss adapter with no recognizable enclosure still came from
    # an audio-first feed -- "podcast" is the adapter's own default, not a
    # claim about content nothing here actually inspected.
    return "podcast"


def _detect_podcast_transcript_availability(entry: Any) -> dict[str, Any]:
    """Inspects only the standards-based Podcasting 2.0 `<podcast:transcript>`
    tag (feedparser exposes it as `entry.podcast_transcript`, a dict with
    `url`/`type`/`language` -- verified against feedparser 6.0.11, the
    version this project pins). This is a generic, structural check any
    podcast RSS feed can carry -- not scraping, not a guess from prose, and
    not a claim that a transcript is trustworthy, just that the publisher's
    own feed declares one exists. Absence of the tag is a definitive
    "not_detected" (we did check), not "unknown" (we didn't)."""
    transcript = getattr(entry, "podcast_transcript", None)
    checked_at = _now_iso()
    if not transcript or not transcript.get("url"):
        return {"status": TRANSCRIPT_NOT_DETECTED, "checked_at": checked_at, "url": None, "language": None}
    return {
        "status": TRANSCRIPT_PUBLISHER,
        "checked_at": checked_at,
        "url": transcript.get("url"),
        "language": transcript.get("language"),
        "declared_type": transcript.get("type"),
    }


def _normalize_podcast_rss_entry(entry: Any) -> NormalizedItem:
    title = _strip_html(getattr(entry, "title", "") or "(untitled)")
    description = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))[:4000]
    canonical_url = getattr(entry, "link", None) or None

    # feedparser maps <guid> to entry.id regardless of isPermaLink; when
    # isPermaLink is absent/false (the common case for podcast hosts, which
    # use an opaque UUID) entry.id is a durable publisher identifier
    # distinct from the episode's canonical URL -- exactly the GUID dedupe
    # strategy wants. When a feed has no <guid> at all, feedparser falls
    # back to using the link as entry.id, which duplicates canonical_url;
    # harmless, since the dedupe strategy prefers guid but the two resolve
    # to the same identity in that case anyway.
    external_id = getattr(entry, "id", None) or None

    published_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    published_date = None
    if published_parsed:
        try:
            published_date = datetime(*published_parsed[:6], tzinfo=timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            published_date = None

    duration_seconds = _parse_duration_to_seconds(getattr(entry, "itunes_duration", None))
    media_format = _classify_podcast_media_format(entry)
    transcript_availability = _detect_podcast_transcript_availability(entry)

    raw_enclosures = getattr(entry, "enclosures", None) or []
    raw_metadata = {
        "feed_guid": external_id,
        "feed_link": canonical_url,
        "raw_title": getattr(entry, "title", None),
        "raw_published": getattr(entry, "published", None),
        "raw_itunes_duration": getattr(entry, "itunes_duration", None),
        "enclosure_types": [e.get("type") for e in raw_enclosures],
        # Added for the downstream media-acquisition/transcription layer
        # (app/services/media_transcription.py): the enclosure's own
        # direct media URL, distinct from `canonical_url` (the episode's
        # webpage link, e.g. a Spotify-for-Podcasters episode page) --
        # additive only, does not change any previously-emitted field.
        "enclosures": [
            {
                "url": e.get("href"),
                "type": e.get("type"),
                "length_bytes": int(e["length"]) if str(e.get("length") or "").isdigit() else None,
            }
            for e in raw_enclosures
            if e.get("href")
        ],
    }

    return NormalizedItem(
        title=title,
        media_format=media_format,
        canonical_url=canonical_url,
        external_id=external_id,
        platform_item_id=None,
        published_date=published_date,
        description=description,
        duration_seconds=duration_seconds,
        transcript_availability=transcript_availability,
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# youtube_feed adapter -- YouTube's own public, credential-free channel/
# playlist Atom feeds (`https://www.youtube.com/feeds/videos.xml?channel_id=
# ...` or `?playlist_id=...`; verified 2026-08-15 against the real
# Redagricola channel and its "Redagricola On The Road TV" playlists --
# see this module's companion report). No API key, no OAuth, no scraping:
# these are the same public Atom feeds YouTube has served for its
# subscription/RSS-reader integration for years.
#
# Fetching and listing entries is identical to podcast_rss (an HTTP GET
# followed by feedparser.parse(), then that parsed feed's `.entries`) --
# feedparser handles YouTube's Atom shape (including its `yt:` namespace)
# natively, so `_fetch_podcast_rss`/`_podcast_rss_entries` are reused as-is
# here rather than duplicated; only *normalization* differs per adapter
# type, per this module's "one generic adapter mechanism" architecture.
# ---------------------------------------------------------------------------


def _detect_youtube_transcript_availability(entry: Any) -> dict[str, Any]:
    """Unlike podcast_rss's `<podcast:transcript>` tag, YouTube's public
    channel/playlist Atom feed carries no caption/transcript signal at all
    -- there is no credential-free, non-scraping way to learn caption
    availability from this feed alone (the video *page* exposes a caption
    track list, but fetching and parsing that page is exactly the fragile,
    publisher-hostile scraping this module's docstring rules out as a
    mechanism). Reporting TRANSCRIPT_NOT_DETECTED here would be a false
    claim of a check that was never performed; TRANSCRIPT_UNKNOWN (defined
    alongside TRANSCRIPT_PLATFORM_CAPTIONS at the top of this module,
    reserved for exactly this case since before any adapter used it) is the
    only honest answer. A caller that separately confirms captions exist
    (e.g. by inspecting the actual video page) is expected to use
    TRANSCRIPT_PLATFORM_CAPTIONS for that -- and, per this module's
    docstring, must never treat auto-generated captions as a trusted,
    publisher-authored transcript."""
    return {"status": TRANSCRIPT_UNKNOWN, "checked_at": _now_iso(), "url": None, "language": None}


def _normalize_youtube_feed_entry(entry: Any) -> NormalizedItem:
    title = _strip_html(getattr(entry, "title", "") or "(untitled)")
    description = _strip_html(getattr(entry, "summary", ""))[:4000]
    canonical_url = getattr(entry, "link", None) or None

    # `yt:videoId` is YouTube's own stable, platform-native identifier for
    # this upload -- distinct from the feed entry's Atom `<id>` (which is
    # merely `yt:video:<videoId>`, a derived value, not a separate
    # publisher-declared GUID) and from `canonical_url` (whose query string
    # this module's generic `_normalize_url_for_dedupe()` helper would
    # actually strip, making the URL alone unsuitable as a fallback dedupe
    # key for every video sharing the same `/watch` path -- exactly why the
    # dedupe hierarchy's video-id-first preference is a correctness
    # requirement here, not just a stylistic choice). Populating
    # `platform_item_id` (not `external_id`) is what makes `_dedupe_identity()`
    # select DEDUPE_STRATEGY_PLATFORM_ID for every youtube_feed item.
    video_id = getattr(entry, "yt_videoid", None) or None

    published_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    published_date = None
    if published_parsed:
        try:
            published_date = datetime(*published_parsed[:6], tzinfo=timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            published_date = None

    transcript_availability = _detect_youtube_transcript_availability(entry)

    raw_metadata = {
        "yt_video_id": video_id,
        "yt_channel_id": getattr(entry, "yt_channelid", None),
        "feed_entry_id": getattr(entry, "id", None),
        "raw_title": getattr(entry, "title", None),
        "raw_published": getattr(entry, "published", None),
        "media_thumbnail": [t.get("url") for t in (getattr(entry, "media_thumbnail", None) or []) if t.get("url")],
    }

    return NormalizedItem(
        # Per Phase 9(c): normalize onto evidence.schema.json's existing
        # media_format vocabulary, never a new "youtube" semantic type.
        # Every item from this adapter is a YouTube upload, hence "video"
        # unconditionally -- no per-source override exists (or is needed)
        # today, since no YouTube source onboarded in this phase is a
        # conference archive; a future conference-archive YouTube source
        # would be a small, separate config field, not a fork of this
        # function.
        title=title,
        media_format="video",
        canonical_url=canonical_url,
        external_id=None,
        platform_item_id=video_id,
        published_date=published_date,
        description=description,
        # Not exposed by this feed at all (unlike itunes:duration on a
        # podcast feed) -- correctly None (unknown), not a guess, and not
        # fetched by loading the video page.
        duration_seconds=None,
        transcript_availability=transcript_availability,
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# article_rss adapter -- a plain news/trade-press RSS or Atom feed of
# written articles. Fetching and listing entries is identical to
# podcast_rss/youtube_feed (an HTTP GET followed by feedparser.parse());
# feedparser already handles ordinary news feeds the same way it handles
# podcast feeds (proven live elsewhere in this project against Fresh Fruit
# Portal's berries-tagged feed). Only *normalization* differs, per this
# module's "one generic adapter mechanism" architecture -- this adapter
# does not fetch the article's HTML body; that is a separate, heavier step
# owned by app/services/article_acquisition.py, run later against a
# specific discovered item, not against every entry in a feed on every
# poll.
# ---------------------------------------------------------------------------


def _normalize_article_rss_entry(entry: Any) -> NormalizedItem:
    title = _strip_html(getattr(entry, "title", "") or "(untitled)")
    description = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))[:4000]
    canonical_url = getattr(entry, "link", None) or None
    # Same GUID-preference reasoning as _normalize_podcast_rss_entry(): a
    # news feed's <guid> is a durable publisher identifier when present,
    # falls back to the link otherwise (harmless, since dedupe then keys
    # on canonical_url anyway).
    external_id = getattr(entry, "id", None) or None

    published_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    published_date = None
    if published_parsed:
        try:
            published_date = datetime(*published_parsed[:6], tzinfo=timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            published_date = None

    author = _strip_html(getattr(entry, "author", "") or "") or None

    raw_metadata = {
        "feed_guid": external_id,
        "feed_link": canonical_url,
        "raw_title": getattr(entry, "title", None),
        "raw_published": getattr(entry, "published", None),
        "raw_author": author,
    }

    return NormalizedItem(
        title=title,
        media_format="web_article",
        canonical_url=canonical_url,
        external_id=external_id,
        platform_item_id=None,
        published_date=published_date,
        description=description,
        # A written article has no runtime duration -- correctly None
        # (not applicable), never a guess.
        duration_seconds=None,
        transcript_availability={
            "status": TRANSCRIPT_NOT_APPLICABLE,
            "checked_at": _now_iso(),
            "url": None,
            "language": None,
        },
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# news_search_rss adapter -- a Google News RSS *search* feed (already this
# project's proven mechanism for mainstream/keyword monitoring, via the
# older app/main.py "keyword" source loop and its google_news_rss_url()).
# Fetching/listing is identical to article_rss/podcast_rss -- it is still
# plain RSS. The one real difference: every <item>'s own <link> is a
# news.google.com redirect, never the publisher's URL, so the *real*
# publisher must be recovered from Google's own <source> tag on the entry
# (entry.source.title/href) -- app/main.py's build_auto_evidence() already
# established this exact recovery precedent for the older pipeline; this
# adapter ports the same recovery into the modern discover -> screen ->
# acquire -> draft pipeline (media_discovery.py -> article_refresh.py ->
# inbox/evidence/ review) so mainstream-press items get real body-aware
# relevance screening and a human review gate, instead of the older
# pipeline's direct, unreviewed write to data/evidence/ as validated=false.
# ---------------------------------------------------------------------------


def _normalize_news_search_entry(entry: Any) -> NormalizedItem:
    base = _normalize_article_rss_entry(entry)
    origin = getattr(entry, "source", None)
    publisher_name = (origin.get("title") if origin else None) or None
    publisher_url = (origin.get("href") if origin else None) or None
    raw_metadata = dict(base.raw_metadata)
    raw_metadata["origin_publisher_name"] = publisher_name
    raw_metadata["origin_publisher_url"] = publisher_url
    # canonical_url deliberately stays the news.google.com redirect (not
    # replaced by publisher_url): the redirect is a real, stable, working
    # link to the article, and this project's existing keyword-source
    # precedent (app/main.py's build_auto_evidence()) does the same --
    # only the *publisher attribution* is recovered, not a rewritten URL.
    return NormalizedItem(
        title=base.title,
        media_format=base.media_format,
        canonical_url=base.canonical_url,
        external_id=base.external_id,
        platform_item_id=base.platform_item_id,
        published_date=base.published_date,
        description=base.description,
        duration_seconds=base.duration_seconds,
        transcript_availability=base.transcript_availability,
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# government_register_json adapter -- Federal Register's own public
# documents.json search API (no auth, no scraping; api.federalregister.gov
# doubles as www.federalregister.gov/api/v1/documents.json). A genuinely new
# fetch/list pair, not a reuse of the RSS trio: this project verified live
# (2026-08-20) that Federal Register's *RSS* search endpoint
# (documents/search.rss?...) returns an access-gate HTML page for an
# ordinary httpx client, while the JSON API at the same path prefix returns
# real results for the identical query and User-Agent -- so RSS is not a
# usable transport for this source, even though it is for article_rss/
# news_search_rss. This is the one genuinely new adapter this mission adds;
# every other new source reuses an existing adapter (see sources.json).
# ---------------------------------------------------------------------------


def _fetch_federal_register_json(feed_url: str) -> tuple[Any, bytes]:
    response = httpx.get(
        feed_url,
        timeout=MEDIA_DISCOVERY_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": MEDIA_DISCOVERY_USER_AGENT},
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json(), response.content


def _federal_register_entries(parsed: Any) -> list[Any]:
    return list((parsed or {}).get("results") or [])


def _normalize_federal_register_entry(entry: Any) -> NormalizedItem:
    entry = entry or {}
    title = (entry.get("title") or "(untitled)").strip()
    description = (entry.get("abstract") or "")[:4000]
    canonical_url = entry.get("html_url") or None
    external_id = entry.get("document_number") or None
    published_date = entry.get("publication_date") or None
    raw_metadata = {
        "document_number": external_id,
        "agencies": [a.get("name") for a in (entry.get("agencies") or []) if isinstance(a, dict) and a.get("name")],
        "document_type": entry.get("type"),
        "pdf_url": entry.get("pdf_url"),
    }
    return NormalizedItem(
        title=title,
        media_format="web_article",
        canonical_url=canonical_url,
        external_id=external_id,
        platform_item_id=None,
        published_date=published_date,
        description=description,
        duration_seconds=None,
        transcript_availability={
            "status": TRANSCRIPT_NOT_APPLICABLE,
            "checked_at": _now_iso(),
            "url": None,
            "language": None,
        },
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# government_recall_json adapter -- openFDA's public food enforcement/recall
# API (api.fda.gov/food/enforcement.json), no auth, no scraping. Global
# Qualitative Coverage Expansion V1 mission (2026-08-21): live-verified this
# returns real, current 2026 recall records, including exact matches for two
# real recall-benchmark events (a frozen-blueberry E. coli O145:H28 recall
# and a frozen-blueberry Listeria recall) found via a generic
# product-description query, not by searching for those specific events.
# Reuses the exact same generic fetch/list pair as government_register_json
# (both are plain JSON GET -> {"results": [...]}) -- only the normalize
# function differs, since openFDA's record shape (product_description/
# reason_for_recall/recall_number/report_date) has no fields in common with
# Federal Register's (title/abstract/document_number/publication_date).
# Food-safety recall provenance is preserved directly, not laundered through
# a "negative news" label -- see _normalize_fda_recall_entry's does_not_prove-
# relevant raw_metadata (classification/voluntary_mandated/recalling_firm).
# ---------------------------------------------------------------------------


def _normalize_fda_recall_entry(entry: Any) -> NormalizedItem:
    entry = entry or {}
    recall_number = entry.get("recall_number") or None
    product = (entry.get("product_description") or "").strip()
    reason = (entry.get("reason_for_recall") or "").strip()
    firm = (entry.get("recalling_firm") or "").strip()
    # A short, human title -- openFDA has no title field at all, only long
    # structured product_description/reason_for_recall text.
    product_short = (product[:120] + "...") if len(product) > 120 else product
    title = f"FDA recall: {product_short}" + (f" ({firm})" if firm else "")
    report_date = entry.get("report_date") or ""
    published_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}" if len(report_date) == 8 else None
    # A deterministic, always-resolvable deep link to this exact record --
    # openFDA provides no human press-release URL, so the API's own
    # quoted-exact-match query for this recall_number is the most honest,
    # real, working canonical_url available (live-verified 2026-08-21).
    canonical_url = (
        f"https://api.fda.gov/food/enforcement.json?search=recall_number:%22{recall_number}%22"
        if recall_number else None
    )
    raw_metadata = {
        "recall_number": recall_number,
        "recalling_firm": firm or None,
        "classification": entry.get("classification"),
        "voluntary_mandated": entry.get("voluntary_mandated"),
        "distribution_pattern": entry.get("distribution_pattern"),
        "recall_initiation_date": entry.get("recall_initiation_date"),
        "status": entry.get("status"),
    }
    return NormalizedItem(
        title=title,
        media_format="web_article",
        canonical_url=canonical_url,
        external_id=recall_number,
        platform_item_id=None,
        published_date=published_date,
        description=reason,
        duration_seconds=None,
        transcript_availability={
            "status": TRANSCRIPT_NOT_APPLICABLE,
            "checked_at": _now_iso(),
            "url": None,
            "language": None,
        },
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# government_alert_json adapter -- the UK Food Standards Agency's public
# Linked Data API (data.food.gov.uk/food-alerts), no auth, Open Government
# Licence. Global Qualitative Coverage Expansion V2 mission (2026-08-22):
# live-verified real, current 2026 UK food alerts (Product Recall
# Information Notices, Allergy Alerts, Food Alerts for Action), including a
# real berry-relevant match ("Tesco recalls Tesco Grape & Berry Medley
# because of contamination with salmonella", 2026-02-16) found via a
# generic recency-sorted pull, not by searching for that headline. Distinct
# adapter from government_recall_json (openFDA) because the JSON shape
# differs (top-level "items" not "results"; title/description/created/
# modified/alertURL/notation fields, not FDA's product_description/
# reason_for_recall/report_date/recall_number) -- "alert" rather than
# "recall" in the name because the FSA's own API covers a broader category
# (allergy alerts and public-health actions alongside recalls) than
# openFDA's narrower enforcement-record scope, matching this mission's own
# "recalls, outbreak investigations, contamination notices, import alerts,
# public-health actions" requirement. Reuses the same generic JSON fetch as
# government_register_json/government_recall_json -- only list-entries and
# normalize differ.
# ---------------------------------------------------------------------------


def _uk_fsa_entries(parsed: Any) -> list[Any]:
    return list((parsed or {}).get("items") or [])


def _normalize_uk_fsa_entry(entry: Any) -> NormalizedItem:
    entry = entry or {}
    title = (entry.get("title") or "(untitled)").strip()
    description = (entry.get("description") or "")[:4000]
    canonical_url = entry.get("alertURL") or None
    external_id = entry.get("notation") or None
    published_date = entry.get("created") or None
    business = entry.get("reportingBusiness") or {}
    raw_metadata = {
        "notation": external_id,
        "reporting_business": business.get("commonName"),
        "alert_types": [t.rsplit("/", 1)[-1] for t in (entry.get("type") or []) if isinstance(t, str)],
        "modified": entry.get("modified"),
    }
    return NormalizedItem(
        title=f"UK FSA alert: {title}" if not title.lower().startswith("uk fsa") else title,
        media_format="web_article",
        canonical_url=canonical_url,
        external_id=external_id,
        platform_item_id=None,
        published_date=published_date,
        description=description,
        duration_seconds=None,
        transcript_availability={
            "status": TRANSCRIPT_NOT_APPLICABLE,
            "checked_at": _now_iso(),
            "url": None,
            "language": None,
        },
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# sec_edgar_search_json adapter -- SEC EDGAR's public full-text search API
# (efts.sec.gov/LATEST/search-index), no auth, no scraping. Unknown-Event
# Discovery + Query Coverage V3 mission (2026-08-23): a real primary-source
# gap this benchmark itself names (BM-C-07's own citation is "SEC 8-K,
# 2026") -- Corporate-class investment/expansion events a publicly-traded
# berry-adjacent company discloses in a routine quarterly 8-K earnings
# exhibit, before or instead of any trade-press pickup. Live-verified
# 2026-08-23: a bare cross-company "blueberry" full-text search across all
# 8-K filers is real but noisy (13 of 18 real hits were unrelated
# companies -- a restaurant chain's investor slide deck, a tobacco company,
# a mining company -- whose filings happen to contain the word
# incidentally); scoping the same query to a specific company's own CIK
# (ciks= param) returned 32/32 genuinely relevant Mission Produce filings,
# zero noise. Sources therefore MUST be CIK-scoped to one already-known
# public company, never a bare species-word search -- the "entity x event
# class" bounded-query-family principle applied to a government source.
# Reuses the same generic JSON fetch as government_register_json/
# government_recall_json/government_alert_json -- only list-entries and
# normalize differ (EDGAR's shape nests real fields under
# hits.hits[]._source, unlike any of the three existing adapters).
# ---------------------------------------------------------------------------


def _sec_edgar_entries(parsed: Any) -> list[Any]:
    return list(((parsed or {}).get("hits") or {}).get("hits") or [])


def _normalize_sec_edgar_entry(entry: Any) -> NormalizedItem:
    entry = entry or {}
    source = entry.get("_source") or {}
    display_names = source.get("display_names") or []
    company = display_names[0] if display_names else "(unknown filer)"
    form = source.get("form") or "filing"
    file_date = source.get("file_date") or None
    accession = source.get("adsh") or ""
    file_type = source.get("file_type") or ""
    # entry["_id"] is "{accession-with-dashes}:{filename}" -- the only place
    # the actual exhibit filename appears in this API's response shape.
    raw_id = str(entry.get("_id") or "")
    filename = raw_id.split(":", 1)[1] if ":" in raw_id else ""
    ciks = source.get("ciks") or []
    cik = ciks[0].lstrip("0") if ciks else ""
    canonical_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{filename}"
        if cik and accession and filename else None
    )
    # file_date, not just form/file_type, is the one field that actually
    # distinguishes one real filing from another -- found live (2026-08-23):
    # a company with several years of quarterly 8-Ks all use the identical
    # EX-99.1 exhibit type, so a title built from company+form+file_type
    # alone produced 27 real, distinct filings under one identical title
    # in the real review queue, a genuine review-usability regression this
    # mission's own precision discipline (Section 12) requires fixing.
    title = f"{company} {form} filing" + (f" ({file_date})" if file_date else "") + (f" ({file_type})" if file_type else "")
    raw_metadata = {
        "accession_number": accession or None,
        "form": form,
        "items": source.get("items"),
        "cik": ciks[0] if ciks else None,
        "period_ending": source.get("period_ending"),
    }
    return NormalizedItem(
        title=title,
        media_format="web_article",
        canonical_url=canonical_url,
        external_id=raw_id or None,
        platform_item_id=None,
        published_date=file_date,
        description=f"SEC {form} exhibit, items {', '.join(source.get('items') or [])}.".strip(),
        duration_seconds=None,
        transcript_availability={
            "status": TRANSCRIPT_NOT_APPLICABLE,
            "checked_at": _now_iso(),
            "url": None,
            "language": None,
        },
        raw_metadata=raw_metadata,
    )


# adapter type -> (fetch, normalize-one-entry, list-entries-from-parsed)
def _podcast_rss_entries(parsed: Any) -> list[Any]:
    return list(parsed.entries or [])


ADAPTER_TYPES: dict[str, tuple[Callable[[str], tuple[Any, bytes]], Callable[[Any], list[Any]], Callable[[Any], NormalizedItem]]] = {
    "podcast_rss": (_fetch_podcast_rss, _podcast_rss_entries, _normalize_podcast_rss_entry),
    # Reuses the same generic fetch/list-entries pair as podcast_rss (see
    # the youtube_feed section above) -- only the normalize function
    # differs, which is precisely the "new publication technology = one
    # adapter, not new source-specific Python" rule this registry exists
    # to enforce.
    "youtube_feed": (_fetch_podcast_rss, _podcast_rss_entries, _normalize_youtube_feed_entry),
    # Same reuse: a news/article RSS feed is fetched and listed exactly
    # like a podcast feed (an <item>/<entry> list feedparser already
    # understands generically); only normalize differs. A government
    # register's own search-RSS feed (e.g. Federal Register) is also
    # ordinary RSS with real canonical URLs -- it registers under this same
    # adapter, not a new one; see data/configuration/sources.json.
    "article_rss": (_fetch_podcast_rss, _podcast_rss_entries, _normalize_article_rss_entry),
    # Google News RSS search -- mainstream/keyword-company monitoring
    # through the modern review pipeline. See module docstring above.
    "news_search_rss": (_fetch_podcast_rss, _podcast_rss_entries, _normalize_news_search_entry),
    # Federal Register's public JSON search API. See section above.
    "government_register_json": (
        _fetch_federal_register_json, _federal_register_entries, _normalize_federal_register_entry,
    ),
    # openFDA's public food enforcement/recall JSON API. Reuses the same
    # generic JSON fetch/list pair as government_register_json -- see
    # section above.
    "government_recall_json": (
        _fetch_federal_register_json, _federal_register_entries, _normalize_fda_recall_entry,
    ),
    # UK Food Standards Agency's public Linked Data alerts API. Reuses the
    # same generic JSON fetch as the two adapters above -- see section
    # above.
    "government_alert_json": (
        _fetch_federal_register_json, _uk_fsa_entries, _normalize_uk_fsa_entry,
    ),
    # SEC EDGAR's public full-text search API. Reuses the same generic JSON
    # fetch as the three adapters above -- see section above. Sources using
    # this adapter must be CIK-scoped (ciks= in the feed_url), never a bare
    # cross-company keyword search.
    "sec_edgar_search_json": (
        _fetch_federal_register_json, _sec_edgar_entries, _normalize_sec_edgar_entry,
    ),
}


# ---------------------------------------------------------------------------
# dedupe identity
# ---------------------------------------------------------------------------


def _dedupe_identity(item: NormalizedItem) -> tuple[str, str]:
    """Durable-identifier preference order per this phase's spec: publisher
    GUID, then platform-native item id, then canonical URL, then a hash of
    normalized metadata as a last resort. Never title alone."""
    if item.external_id:
        return DEDUPE_STRATEGY_GUID, item.external_id
    if item.platform_item_id:
        return DEDUPE_STRATEGY_PLATFORM_ID, item.platform_item_id
    if item.canonical_url:
        return DEDUPE_STRATEGY_CANONICAL_URL, _normalize_url_for_dedupe(item.canonical_url)
    basis = json.dumps({"title": item.title, "published_date": item.published_date}, sort_keys=True)
    return DEDUPE_STRATEGY_METADATA_HASH, hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _staging_item_id(source_id: str, dedupe_strategy: str, dedupe_key: str) -> str:
    digest = hashlib.sha256(f"{dedupe_strategy}:{dedupe_key}".encode("utf-8")).hexdigest()[:16]
    return f"discovered-{_slugify(source_id)}-{digest}"


# ---------------------------------------------------------------------------
# staging persistence (inbox/discovered_media/ -- untrusted, disposable,
# never read by scripts/validate_records.py or scripts/build_static.py)
# ---------------------------------------------------------------------------


def staging_dir(inbox_dir: Path) -> Path:
    return inbox_dir / "discovered_media"


def _state_dir(inbox_dir: Path) -> Path:
    return staging_dir(inbox_dir) / "_state"


def _transcripts_dir(inbox_dir: Path) -> Path:
    return staging_dir(inbox_dir) / "_transcripts"


def _item_path(inbox_dir: Path, item_id: str) -> Path:
    return staging_dir(inbox_dir) / f"{item_id}.json"


def list_discovered_items(inbox_dir: Path, source_id: str | None = None) -> list[dict[str, Any]]:
    """Read-only listing of everything currently staged -- used by the CLI
    and by tests, never by scripts/build_static.py."""
    folder = staging_dir(inbox_dir)
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if source_id is None or record.get("source_id") == source_id:
            items.append(record)
    return items


def _load_existing_item(inbox_dir: Path, item_id: str) -> dict[str, Any] | None:
    path = _item_path(inbox_dir, item_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_item(inbox_dir: Path, item_id: str, record: dict[str, Any]) -> None:
    path = _item_path(inbox_dir, item_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Fields a re-discovery is allowed to refresh in place. Identity fields
# (id, source_id, dedupe_strategy, dedupe_key, external_id, first_seen_at)
# are deliberately excluded -- refreshing them would break the very
# idempotency this exists to guarantee.
_REFRESHABLE_FIELDS = (
    "title",
    "description",
    "media_format",
    "canonical_url",
    "published_date",
    "duration_seconds",
    "transcript_availability",
    "raw_metadata",
)


def upsert_discovered_item(
    inbox_dir: Path,
    source_id: str,
    item: NormalizedItem,
    *,
    now: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Write (or refresh) one staged item. Returns (record, is_new).

    Idempotency contract: calling this twice with logically-the-same item
    (same dedupe identity) never creates a second file and never resets
    first_seen_at/seen_count -- it updates the existing record's
    descriptive fields and bumps last_seen_at/seen_count instead. This is
    what makes repeated `discover_source()` runs against an unchanged feed
    a no-op at the staging-record level.
    """
    now = now or _now_iso()
    dedupe_strategy, dedupe_key = _dedupe_identity(item)
    item_id = _staging_item_id(source_id, dedupe_strategy, dedupe_key)

    existing = _load_existing_item(inbox_dir, item_id)
    fresh_fields = {
        "title": item.title,
        "description": item.description,
        "media_format": item.media_format,
        "canonical_url": item.canonical_url,
        "published_date": item.published_date,
        "duration_seconds": item.duration_seconds,
        "transcript_availability": item.transcript_availability,
        "raw_metadata": item.raw_metadata,
    }

    if existing is None:
        record = {
            "id": item_id,
            "record_type": "discovered_media_item",
            "staging_schema_version": STAGING_SCHEMA_VERSION,
            "source_id": source_id,
            "external_id": item.external_id,
            "platform_item_id": item.platform_item_id,
            "dedupe_strategy": dedupe_strategy,
            "dedupe_key": dedupe_key,
            "possible_evidence_matches": [],
            "first_seen_at": now,
            "last_seen_at": now,
            "seen_count": 1,
            **fresh_fields,
        }
        _write_item(inbox_dir, item_id, record)
        return record, True

    merged = dict(existing)
    for key in _REFRESHABLE_FIELDS:
        if key in fresh_fields:
            merged[key] = fresh_fields[key]
    merged["last_seen_at"] = now
    merged["seen_count"] = int(existing.get("seen_count", 1)) + 1
    _write_item(inbox_dir, item_id, merged)
    return merged, False


# ---------------------------------------------------------------------------
# reconciliation with already-known (manually-entered) Evidence -- read-only
# ---------------------------------------------------------------------------


def _normalize_title_for_match(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).strip()


def find_possible_evidence_matches(
    item_id: str,
    normalized_item: dict[str, Any],
    source_id: str,
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    schemas_dir: Path = SCHEMAS_DIR,
) -> list[dict[str, Any]]:
    """Advisory-only: flags Evidence records that *might* be the same
    real-world episode as this staged item, e.g. because a human already
    hand-entered it (as `ev-lucentlands-scaling-blueberry-industry-2025`
    was) before this discovery adapter existed. Read-only against
    EvidenceRepository -- never creates, updates, or deletes Evidence, and
    is not itself a claim of identity, only a suggestion for a future human
    or review step to confirm.

    Matching signal is deliberately conservative and explainable: same
    source_id plus either (a) a normalized-title containment match or (b)
    an exact published_date match. Both reasons are recorded so a reviewer
    can see *why* something was flagged."""
    repos = get_repositories(data_dir, schemas_dir)
    candidates = [r for r in repos.evidence.list() if r.get("source_id") == source_id]
    if not candidates:
        return []

    item_title = _normalize_title_for_match(normalized_item.get("title", ""))
    item_date = normalized_item.get("published_date")

    matches = []
    for record in candidates:
        reasons = []
        record_title = _normalize_title_for_match(record.get("title", ""))
        if item_title and record_title and (item_title in record_title or record_title in item_title):
            reasons.append("title_match")
        if item_date and record.get("published_date") == item_date:
            reasons.append("published_date_match")
        if reasons:
            matches.append(
                {
                    "evidence_id": record["id"],
                    "reasons": reasons,
                    "confidence": "medium" if len(reasons) > 1 else "low",
                }
            )
    return matches


# ---------------------------------------------------------------------------
# operational metadata (Phase 10) -- per-source discovery-run state, kept
# separate from data/configuration/sources.json's own last_checked_at/
# last_status, which are documented (app/main.py check_all_sources()) as
# meaning "a human reviewed this reference source" and must not be
# repurposed by an automated process
# ---------------------------------------------------------------------------


def _state_path(inbox_dir: Path, source_id: str) -> Path:
    return _state_dir(inbox_dir) / f"{_slugify(source_id)}.json"


def read_source_discovery_state(inbox_dir: Path, source_id: str) -> dict[str, Any] | None:
    path = _state_path(inbox_dir, source_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_source_discovery_state(inbox_dir: Path, source_id: str, state: dict[str, Any]) -> None:
    path = _state_path(inbox_dir, source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# top-level discovery run
# ---------------------------------------------------------------------------


@dataclass
class ItemFailure:
    index: int
    identifier: str | None
    error: str


@dataclass
class DiscoveryRunResult:
    source_id: str
    status: str  # "ok" | "error"
    error: str | None = None
    found: int = 0
    new: int = 0
    already_known: int = 0
    # Of `new`, how many were flagged historical_backlog by
    # classify_initial_backlog() on a spoken-media source's first-ever
    # discovery run -- staged (never dropped), but excluded from the
    # recurring orchestration pass's normal drafting by default.
    historical_backlog: int = 0
    item_failures: list[ItemFailure] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)
    # Populated only for a source configured with more than one feed_url
    # (Phase 7-8's "On The Road" resolves to two separate, per-country
    # YouTube playlists, not one combined feed -- see discover_source()).
    # One feed failing does not fail the whole source as long as at least
    # one of its feeds returned entries; each failure is recorded here so
    # it's visible in a run report without being conflated with an
    # item-level failure (a bad individual entry within an otherwise-good
    # feed) or a whole-source failure (every configured feed unreachable).
    feed_failures: list[dict[str, str]] = field(default_factory=list)

    def as_summary_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "status": self.status,
            "error": self.error,
            "found": self.found,
            "new": self.new,
            "already_known": self.already_known,
            "historical_backlog": self.historical_backlog,
            "item_failures": [
                {"index": f.index, "identifier": f.identifier, "error": f.error} for f in self.item_failures
            ],
            "feed_failures": self.feed_failures,
        }


def discover_source(
    source_id: str,
    *,
    inbox_dir: Path,
    data_dir: Path = DEFAULT_DATA_DIR,
    schemas_dir: Path = SCHEMAS_DIR,
    allow_historical_backfill: bool = False,
) -> DiscoveryRunResult:
    """Run discovery for exactly one Source. Never raises for network/feed
    problems (Phase 6's "understanding failures" requirement) -- those
    become `status="error"` with a message on the returned result. Only
    raises `DiscoveryError` for a caller mistake (unknown source_id, or a
    source with no usable `discovery` configuration), since those indicate
    a bug in the caller, not an operational failure to report and move on
    from.

    A Source's `discovery` config carries either a single `feed_url`
    (every podcast_rss source registered so far) or a `feed_urls` list
    (plural -- e.g. Redagricola's "On The Road" resolves to two separate,
    per-country YouTube playlist feeds with no single combined feed to
    point at instead). This is a generic capability of every adapter type,
    not a Redagricola-specific branch: any Source, on any adapter, may
    have more than one feed. `feed_url` (singular) keeps working exactly
    as before for every existing single-feed source.

    `allow_historical_backfill` is the explicit operator override for
    intentional historical backfill of a spoken-media source's full
    back-catalog; by default (False), a source's first-ever successful
    discovery run only stages a bounded recent window of podcast/video
    items (see `classify_initial_backlog()`) -- older entries are still
    staged (never silently dropped) but flagged `historical_backlog: true`
    so the recurring orchestration pass does not turn them into review
    drafts by default.
    """
    repos = get_repositories(data_dir, schemas_dir)
    source = repos.sources.get(source_id)
    if source is None:
        raise DiscoveryError(f"unknown source_id: {source_id!r}")

    discovery_config = source.get("discovery") or {}
    adapter_type = discovery_config.get("adapter")
    feed_urls = discovery_config.get("feed_urls") or ([discovery_config["feed_url"]] if discovery_config.get("feed_url") else [])
    if not adapter_type or not feed_urls:
        raise DiscoveryError(
            f"source {source_id!r} has no usable 'discovery' configuration "
            f"(expected {{'adapter': ..., 'feed_url': ...}} or {{'adapter': ..., 'feed_urls': [...]}} "
            f"on its sources.json record)"
        )
    if adapter_type not in ADAPTER_TYPES:
        raise DiscoveryError(f"unknown discovery adapter type: {adapter_type!r}")

    fetch, list_entries, normalize = ADAPTER_TYPES[adapter_type]
    now = _now_iso()

    entries: list[Any] = []
    feed_failures: list[dict[str, str]] = []
    for feed_url in feed_urls:
        try:
            parsed, _raw_bytes = fetch(feed_url)
        except Exception as exc:  # noqa: BLE001 -- any transport/parsing failure is a reportable, non-fatal run result
            feed_failures.append({"feed_url": feed_url, "error": str(exc)})
            continue
        entries.extend(list_entries(parsed))

    # last_success_at is carried forward across a failed attempt rather than
    # overwritten -- distinct from last_checked_at (this attempt), it is
    # what cadence-aware freshness (app/services/source_freshness.py) needs
    # to tell "no new stories since our last real check" apart from "we
    # haven't actually managed to check this source lately."
    prior_state = read_source_discovery_state(inbox_dir, source_id) or {}
    prior_last_success_at = prior_state.get("last_success_at")

    if not entries and feed_failures:
        # Every configured feed failed -- a whole-source error, same shape
        # callers already handle for the single-feed_url case.
        combined_error = "; ".join(f"{f['feed_url']}: {f['error']}" for f in feed_failures)
        result = DiscoveryRunResult(source_id=source_id, status="error", error=combined_error, feed_failures=feed_failures)
        _write_source_discovery_state(
            inbox_dir, source_id,
            {**result.as_summary_dict(), "last_checked_at": now, "last_success_at": prior_last_success_at},
        )
        return result

    result = DiscoveryRunResult(source_id=source_id, status="ok", found=len(entries), feed_failures=feed_failures)

    # Normalize every entry first (same per-entry failure isolation as
    # before -- one bad entry's normalize() call never aborts the feed) so
    # the bounded-backlog policy below can see every successfully-normalized
    # item's media_format/published_date before any of them are staged.
    normalized_pairs: list[tuple[int, Any, NormalizedItem]] = []
    for index, entry in enumerate(entries):
        identifier = getattr(entry, "id", None) or getattr(entry, "link", None) or getattr(entry, "title", None)
        try:
            normalized_pairs.append((index, entry, normalize(entry)))
        except Exception as exc:  # noqa: BLE001 -- one bad item must not abort the whole feed
            result.item_failures.append(ItemFailure(index=index, identifier=str(identifier) if identifier else None, error=str(exc)))

    first_ever_success = prior_last_success_at is None
    backlog_indexes: set[int] = set()
    if first_ever_success:
        spoken_pairs = [
            (index, item) for index, _entry, item in normalized_pairs if item.media_format in SPOKEN_MEDIA_FORMATS
        ]
        backlog_indexes = classify_initial_backlog(
            spoken_pairs, now=now, allow_historical_backfill=allow_historical_backfill
        )

    for index, entry, normalized in normalized_pairs:
        identifier = getattr(entry, "id", None) or getattr(entry, "link", None) or getattr(entry, "title", None)
        try:
            record, is_new = upsert_discovered_item(inbox_dir, source_id, normalized, now=now)
            if is_new and index in backlog_indexes:
                record["historical_backlog"] = True
            record["possible_evidence_matches"] = find_possible_evidence_matches(
                record["id"], record, source_id, data_dir=data_dir, schemas_dir=schemas_dir
            )
            _write_item(inbox_dir, record["id"], record)
            result.items.append(record)
            if is_new:
                result.new += 1
                if index in backlog_indexes:
                    result.historical_backlog += 1
            else:
                result.already_known += 1
        except Exception as exc:  # noqa: BLE001 -- one bad item must not abort the whole feed
            result.item_failures.append(ItemFailure(index=index, identifier=str(identifier) if identifier else None, error=str(exc)))

    _write_source_discovery_state(
        inbox_dir, source_id,
        {**result.as_summary_dict(), "last_checked_at": now, "last_success_at": now},
    )
    return result


# ---------------------------------------------------------------------------
# Phase 8 -- optional raw transcript artifact acquisition. Opt-in only
# (never runs as part of discover_source()); low-coupling by design: a
# single HTTP GET of a URL the publisher's own feed already declared, no
# scraping, no auth, no third-party transcript service.
# ---------------------------------------------------------------------------


def acquire_raw_transcript_artifact(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any] | None:
    """Fetch and stage the raw transcript text for one discovered item, if
    (and only if) that item's `transcript_availability` names a publisher
    URL. Returns None (does nothing) for any other state -- this function
    never guesses a URL and never falls back to generating a transcript.
    The result is staging/raw material only: it is never transformed into
    Evidence, a Fact, or any trusted record by this module."""
    availability = item.get("transcript_availability") or {}
    url = availability.get("url")
    if availability.get("status") != TRANSCRIPT_PUBLISHER or not url:
        return None

    now = now or _now_iso()
    response = httpx.get(url, timeout=MEDIA_DISCOVERY_FETCH_TIMEOUT_SECONDS, headers={"User-Agent": MEDIA_DISCOVERY_USER_AGENT})
    response.raise_for_status()
    raw_text = response.text
    checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    artifact = {
        "id": f"transcript-{item['id']}",
        "record_type": "raw_transcript_artifact",
        "staging_schema_version": STAGING_SCHEMA_VERSION,
        "item_id": item["id"],
        "source_id": item.get("source_id"),
        "acquisition_method": "http_get_publisher_declared_transcript_url",
        "acquired_at": now,
        "language": availability.get("language"),
        "provenance_url": url,
        "provenance_kind": "publisher_declared",
        "raw_text": raw_text,
        "checksum_sha256": checksum,
    }
    path = _transcripts_dir(inbox_dir) / f"{artifact['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact
