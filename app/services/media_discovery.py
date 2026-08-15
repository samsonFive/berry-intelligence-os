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

A `MediaDiscoveryAdapter` is a `(fetch, normalize)` function pair keyed by an
`adapter type` string (currently only `"podcast_rss"`). Which adapter type a
given Source uses, and that adapter's configuration (e.g. its feed URL), is
read from that Source's own record in `data/configuration/sources.json` --
an optional `discovery` object (`{"adapter": "podcast_rss", "feed_url":
"..."}`)  -- not hardcoded per source_id in this module. Registering a
*second* podcast RSS source therefore requires zero code changes: add the
same `discovery` block, pointing at that show's own feed, to that source's
registry entry. `source-lucentlands-podcast` is the only source with a
`discovery` block populated today (the "one generic adapter, Lucentlands
only" instruction for this phase); `source-business-of-blueberries-podcast`
and `source-redagricola-on-the-road` were deliberately left without one --
see this module's companion report for why extending to them was not
attempted in this phase (an unverified feed URL is worse than none).

## Dedupe / idempotency

Every normalized item gets a durable identity via `_dedupe_identity()`,
preferring (in order) a publisher/feed GUID, a platform-native item id (not
yet exercised by any adapter in this phase), a normalized canonical URL,
and finally a hash of normalized title+published_date as a last resort.
The staging record's filename is derived from that identity, never from
title -- so a publisher correcting a typo in an episode title on a later
poll does not create a second logical item (`upsert_discovered_item()`
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

DEDUPE_STRATEGY_GUID = "guid"
DEDUPE_STRATEGY_PLATFORM_ID = "platform_id"
DEDUPE_STRATEGY_CANONICAL_URL = "canonical_url"
DEDUPE_STRATEGY_METADATA_HASH = "metadata_hash"


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


# adapter type -> (fetch, normalize-one-entry, list-entries-from-parsed)
def _podcast_rss_entries(parsed: Any) -> list[Any]:
    return list(parsed.entries or [])


ADAPTER_TYPES: dict[str, tuple[Callable[[str], tuple[Any, bytes]], Callable[[Any], list[Any]], Callable[[Any], NormalizedItem]]] = {
    "podcast_rss": (_fetch_podcast_rss, _podcast_rss_entries, _normalize_podcast_rss_entry),
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
    item_failures: list[ItemFailure] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)

    def as_summary_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "status": self.status,
            "error": self.error,
            "found": self.found,
            "new": self.new,
            "already_known": self.already_known,
            "item_failures": [
                {"index": f.index, "identifier": f.identifier, "error": f.error} for f in self.item_failures
            ],
        }


def discover_source(
    source_id: str,
    *,
    inbox_dir: Path,
    data_dir: Path = DEFAULT_DATA_DIR,
    schemas_dir: Path = SCHEMAS_DIR,
) -> DiscoveryRunResult:
    """Run discovery for exactly one Source. Never raises for network/feed
    problems (Phase 6's "understanding failures" requirement) -- those
    become `status="error"` with a message on the returned result. Only
    raises `DiscoveryError` for a caller mistake (unknown source_id, or a
    source with no usable `discovery` configuration), since those indicate
    a bug in the caller, not an operational failure to report and move on
    from.
    """
    repos = get_repositories(data_dir, schemas_dir)
    source = repos.sources.get(source_id)
    if source is None:
        raise DiscoveryError(f"unknown source_id: {source_id!r}")

    discovery_config = source.get("discovery") or {}
    adapter_type = discovery_config.get("adapter")
    feed_url = discovery_config.get("feed_url")
    if not adapter_type or not feed_url:
        raise DiscoveryError(
            f"source {source_id!r} has no usable 'discovery' configuration "
            f"(expected {{'adapter': ..., 'feed_url': ...}} on its sources.json record)"
        )
    if adapter_type not in ADAPTER_TYPES:
        raise DiscoveryError(f"unknown discovery adapter type: {adapter_type!r}")

    fetch, list_entries, normalize = ADAPTER_TYPES[adapter_type]
    now = _now_iso()

    try:
        parsed, _raw_bytes = fetch(feed_url)
    except Exception as exc:  # noqa: BLE001 -- any transport/parsing failure is a reportable, non-fatal run result
        result = DiscoveryRunResult(source_id=source_id, status="error", error=str(exc))
        _write_source_discovery_state(inbox_dir, source_id, {**result.as_summary_dict(), "last_checked_at": now})
        return result

    entries = list_entries(parsed)
    result = DiscoveryRunResult(source_id=source_id, status="ok", found=len(entries))

    for index, entry in enumerate(entries):
        identifier = getattr(entry, "id", None) or getattr(entry, "link", None) or getattr(entry, "title", None)
        try:
            normalized = normalize(entry)
            record, is_new = upsert_discovered_item(inbox_dir, source_id, normalized, now=now)
            record["possible_evidence_matches"] = find_possible_evidence_matches(
                record["id"], record, source_id, data_dir=data_dir, schemas_dir=schemas_dir
            )
            _write_item(inbox_dir, record["id"], record)
            result.items.append(record)
            if is_new:
                result.new += 1
            else:
                result.already_known += 1
        except Exception as exc:  # noqa: BLE001 -- one bad item must not abort the whole feed
            result.item_failures.append(ItemFailure(index=index, identifier=str(identifier) if identifier else None, error=str(exc)))

    _write_source_discovery_state(inbox_dir, source_id, {**result.as_summary_dict(), "last_checked_at": now})
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
