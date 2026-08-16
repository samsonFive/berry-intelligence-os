"""Generic YouTube caption/audio acquisition -- closes the gap between a
`youtube_feed`-discovered `DiscoveredMediaItem` (see
`app/services/media_discovery.py`'s `youtube_feed` adapter) and the exact
same normalized transcript contract `app/services/media_transcription.py`
already produces for `podcast_rss` items, so nothing downstream (Codex's
`transcript_evidence.py`/`media_orchestration.py`, or the review templates)
ever needs to know a transcript originated from YouTube.

## Where this sits

    youtube_feed DiscoveredMediaItem -> this module (Tier 2 captions, or
    Tier 3 audio-only stream resolution) -> media_transcription.py's
    existing normalization / faster-whisper / staging machinery -> STOP
    ---------------- TRUST / ANALYSIS BOUNDARY ----------------

This module never extracts CI claims, never creates atomic Evidence
proposals, never publishes trusted Evidence. It produces exactly the same
two raw materials `media_transcription.py`'s other tiers already produce:
(a) timed caption segments (handed to `media_transcription.normalize_transcript()`
by its caller, `media_transcription._run_tier2_youtube_captions()`), or (b)
a downloaded, playable local audio file (an `AcquiredMedia`, the exact same
dataclass `media_transcription.acquire_media()` returns for an RSS
enclosure) that `media_transcription`'s existing `FasterWhisperProvider`
path transcribes exactly as it already does for podcasts. This module never
builds a second speech-to-text integration.

## Generic, config-driven identity -- never source-specific (Phase 5)

Every function here decides whether/how to act on an item by reading
`item["raw_metadata"]["yt_video_id"]` -- the one field `media_discovery.py`'s
`youtube_feed` adapter populates for every item it normalizes, for any
Source configured with `{"adapter": "youtube_feed", ...}`, regardless of
that Source's identity. Nothing in this module ever branches on
`source_id`. A second YouTube-first Source (a different channel/playlist,
registered purely via `data/configuration/sources.json`) reaches this
module's full acquisition hierarchy with zero code changes here -- see
Phase 22 portability discussion in this feature's report.

## Caption hierarchy (Phase 6/7) -- yt-dlp's own info dict already
distinguishes this structurally, not by guessing

yt-dlp's `extract_info()` result carries two separate dicts:
`info["subtitles"]` -- tracks YouTube itself labels as uploader/human-
supplied (Tier 2a here) -- and `info["automatic_captions"]` -- YouTube's own
ASR output (Tier 2b). This module never inspects caption *content* to guess
which kind it is; it only trusts which of the two dicts a language key
appears in. `_select_caption_track()` always checks `subtitles` first.

## Language selection discipline -- never translates (Phase 15)

`info["automatic_captions"]` always additionally contains 100+ machine-
*translated* tracks (one per YouTube UI language) whenever ANY captions
exist for a video, regardless of what language was actually spoken. Those
are not usable transcripts of what was said -- selecting one would silently
fabricate a translation this project explicitly keeps out of scope.
`_select_caption_track()` only ever selects the track matching the video's
own detected spoken language (`info["language"]`, when yt-dlp reports it) or,
when that is absent, a track YouTube itself has unambiguously marked as the
original via a `<lang>-orig` key (observed in practice: a video with
non-English auto-captions carries e.g. both `es` and `es-orig` keys with
identical content -- `-orig` is the definitive original-language marker,
verified against a real Redagricola video, see this feature's report). If
neither signal is available, this module refuses to guess and returns no
caption result -- the caller falls through to Tier 3 (local Whisper, which
performs its own language detection directly from audio) rather than risk
silently selecting a translated caption as if it were the source transcript.

## Cache/idempotency -- keyed on stable identity, not ephemeral URLs (Phase 16)

Unlike an RSS enclosure URL (assumed durable once published -- see
`media_transcription.acquire_media()`'s own documented assumption), every
URL yt-dlp resolves for a YouTube video (captions endpoint query string,
audio CDN URL) is signed and changes on every resolution even when the
underlying video is completely unchanged. Caching on video identity instead
of on the resolved URL is therefore a *correctness* requirement here, not a
stylistic choice:
- Captions: `_caption_cache_key(video_id, kind, language)` -- a repeated run
  that would select the same kind+language reuses the previously fetched and
  parsed segments (`fetch_captions()`) without re-hitting YouTube's captions
  endpoint.
- Audio: `acquire_youtube_audio()` reuses a previously downloaded file
  whenever its cache sidecar's `video_id` still matches, regardless of the
  freshly resolved stream URL.
`force=True` bypasses both, exactly mirroring the `--force` convention
`media_transcription.py`'s Tier 1/3 already use.

## Honest limitation (Phase 18): no caption-track version identifier

YouTube exposes no ETag/hash/revision number for a caption track on this
module's public, credential-free surface. If a publisher edits caption
*text* without changing which kind/language would be selected, this module
cannot detect that automatically and will keep reusing the cached fetch --
`--force` is the only way to pick up such a change. This is the same shape
of limitation `media_transcription.acquire_media()` already accepts for RSS
enclosure URLs ("a URL is assumed stable once published"); it is not
special-cased away here, only documented honestly, per this phase's explicit
instruction not to build synchronization machinery to fake a reliability
guarantee YouTube itself does not offer.

## Failure handling (Phase 17)

    video private/deleted/geo-restricted/age-restricted -> MediaAcquisitionError
      (raised only from the Tier 3 audio path -- the final, authoritative
      acquisition-error surface; see module docstring notes below)
    no legitimate (non-translated) caption track available -> fetch_captions()
      returns None (not an error -- exactly like Tier 1's "no publisher
      transcript URL" case in media_transcription.py); caller falls through
    caption endpoint network/parse failure -> fetch_captions() returns None;
      caller falls through to Tier 3 (Phase 20 test: "caption acquisition
      failure can fall back to audio")
    yt-dlp not installed / import failure -> surfaces as MediaAcquisitionError
      only once Tier 3 actually needs it (captions degrade to "unavailable"
      silently, since Tier 3 is always the authoritative error reporter for
      a genuinely inaccessible video)

No function in this file ever leaves a partial/corrupt-looking media file or
caption artifact on disk: content is only written after it is fully
resolved in memory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from app.services import media_transcription

YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS = 300
CAPTIONS_FETCH_TIMEOUT_SECONDS = 30

CAPTION_TIER_HUMAN = "tier_2_youtube_human_captions"
CAPTION_TIER_AUTO = "tier_2_youtube_auto_captions"


class YouTubeUnavailableError(Exception):
    """The video is private/deleted/geo-restricted/age-restricted, or
    otherwise not reachable via legitimate, unauthenticated, credential-free
    access. A genuine terminal condition, distinct from a transient network
    failure -- see module docstring's Phase 17 failure-handling table."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Phase 5 -- generic identity
# ---------------------------------------------------------------------------


def youtube_video_id(item: dict[str, Any]) -> str | None:
    """The one signal this module trusts to recognize a YouTube-discovered
    item: `raw_metadata.yt_video_id`, populated only by
    `media_discovery.py`'s `youtube_feed` adapter (never by source_id).
    Deliberately does not fall back to the more generic `platform_item_id`
    field alone -- a future non-YouTube adapter could also populate that
    field with its own platform's id scheme, which would misclassify it."""
    raw = item.get("raw_metadata") or {}
    video_id = raw.get("yt_video_id")
    return video_id if isinstance(video_id, str) and video_id.strip() else None


def is_youtube_item(item: dict[str, Any]) -> bool:
    return youtube_video_id(item) is not None


# ---------------------------------------------------------------------------
# yt-dlp boundary -- real implementation, lazily imported so that importing
# this module (or media_transcription.py, which only imports this module
# lazily inside its YouTube-dispatch branches) never requires yt-dlp to be
# installed on the RSS-only code path. Tests inject a fake `info_fetcher`
# here instead of touching yt-dlp or the network at all (mirrors this
# project's existing httpx-monkeypatch convention for the *transport*
# boundary; here the boundary is yt-dlp's Python API instead of raw HTTP,
# per this task's own guidance to mock at the yt-dlp API boundary).
# ---------------------------------------------------------------------------


def _extract_info_real(video_id: str) -> dict[str, Any]:
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover -- exercised only when yt-dlp truly isn't installed
        raise RuntimeError(
            "yt-dlp is not installed -- add it from requirements.txt (`pip install -r requirements.txt`) "
            "to acquire YouTube captions or audio"
        ) from exc

    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise YouTubeUnavailableError(str(exc)) from exc
    if info is None:
        raise YouTubeUnavailableError(f"yt-dlp returned no info for video {video_id}")
    return info


def _download_text_real(url: str) -> str:
    response = httpx.get(
        url,
        timeout=CAPTIONS_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": media_transcription.MEDIA_DOWNLOAD_USER_AGENT},
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def _download_bytes_real(url: str) -> tuple[bytes, str | None]:
    response = httpx.get(
        url,
        timeout=YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS,
        headers={"User-Agent": media_transcription.MEDIA_DOWNLOAD_USER_AGENT},
        follow_redirects=True,
    )
    response.raise_for_status()
    headers = getattr(response, "headers", None)
    content_type = headers.get("content-type") if headers and hasattr(headers, "get") else None
    return response.content, content_type


# ---------------------------------------------------------------------------
# Phase 6/15 -- caption track selection
# ---------------------------------------------------------------------------


def _find_track_key(table: dict[str, Any], lang: str) -> str | None:
    if lang in table:
        return lang
    if f"{lang}-orig" in table:
        return f"{lang}-orig"
    return None


def _select_caption_track(info: dict[str, Any], requested_language: str | None) -> tuple[str, str, str] | None:
    """Returns `(kind, language_code, table_key)` -- `kind` is `"human"` or
    `"auto"`, `language_code` is the language this module will record
    (stripped of any `-orig` suffix), `table_key` is the literal key to look
    the track list up under. Returns None when no legitimate, confidently-
    sourced (non-translated) track is available -- see module docstring's
    language-selection discipline."""
    subtitles = info.get("subtitles") or {}
    autocaps = info.get("automatic_captions") or {}

    candidate = requested_language or info.get("language")
    if not candidate:
        orig_bases = {k[: -len("-orig")] for k in list(subtitles) + list(autocaps) if k.endswith("-orig")}
        if len(orig_bases) != 1:
            return None
        candidate = next(iter(orig_bases))

    key = _find_track_key(subtitles, candidate)
    if key:
        return "human", candidate, key
    key = _find_track_key(autocaps, candidate)
    if key:
        return "auto", candidate, key
    return None


def _vtt_track_url(tracks: list[dict[str, Any]]) -> str | None:
    for track in tracks:
        if track.get("ext") == "vtt" and track.get("url"):
            return track["url"]
    return None


# ---------------------------------------------------------------------------
# Phase 7 -- YouTube ASR's "rolling window" VTT cleanup (auto captions only)
# ---------------------------------------------------------------------------


def _dedupe_rolling_auto_captions(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """YouTube's ASR VTT emits a two-line rolling window: each new phrase
    first appears appended to the still-visible previous line (one cue), and
    then reappears alone once the window scrolls (the next cue, a bare
    repeat of that same tail). Fed directly into
    `media_transcription.parse_timed_text_captions()` (reused as-is, not
    duplicated -- this function only post-processes its *output*), this
    produces a segment list with every phrase appearing roughly twice and
    every visible two-line snapshot standing as its own redundant segment.

    Verified against a real Redagricola auto-caption track (video
    TRG0WsxJ1Lw, "El arandano esta conquistando a Ica", real Spanish ASR
    output) -- see this feature's report -- reducing 740 raw cues to 382
    clean, non-redundant phrase segments with correct start timestamps and
    zero content loss. Not applied to Tier 2a (human/manual) subtitle
    tracks, which are authored directly and don't exhibit this quirk."""
    cleaned: list[dict[str, Any]] = []
    anchor = ""
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if anchor and anchor.endswith(text):
            # A bare repeat of a tail already emitted as part of a longer
            # cue -- the window settling, not new content. Advance the
            # anchor to this (shorter) text so the *next* cue's
            # startswith-check below has the right prefix to compare
            # against, but never emit this cue itself.
            anchor = text
            continue
        if anchor and text.startswith(anchor):
            new_part = text[len(anchor) :].strip()
            if new_part:
                cleaned.append({**seg, "text": new_part})
            anchor = text
            continue
        cleaned.append(seg)
        anchor = text
    return cleaned


# ---------------------------------------------------------------------------
# Phase 16 -- caption cache identity + fetch
# ---------------------------------------------------------------------------


def _caption_cache_key(video_id: str, kind: str, language: str) -> str:
    basis = json.dumps({"video_id": video_id, "kind": kind, "language": language}, sort_keys=True)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class YouTubeCaptionAcquisition:
    segments: list[dict[str, Any]]
    language: str
    method: str  # TranscriptArtifact provenance.method vocabulary: publisher_provided | auto_generated
    tier: str  # CAPTION_TIER_HUMAN | CAPTION_TIER_AUTO
    caption_kind: str  # "human" | "auto" -- the finer-grained created_by differentiator (Phase 9)
    created_by: str
    source_url: str
    checksum_sha256: str
    cache_hit: bool
    cache_key: str
    raw_artifact_id: str


def fetch_captions(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    language: str | None = None,
    force: bool = False,
    now: str | None = None,
    info_fetcher: Callable[[str], dict[str, Any]] | None = None,
    downloader: Callable[[str], str] | None = None,
) -> YouTubeCaptionAcquisition | None:
    """Tier 2 entry point. Returns None -- never raises -- whenever no
    legitimate caption result is available for any reason (not a YouTube
    item, no usable track, network/parse failure, yt-dlp unavailable): every
    one of those is an expected "fall through to Tier 3" case, not an
    operational failure this function itself reports (see module docstring's
    Phase 17 table; Tier 3's audio path is the sole authoritative error
    surface)."""
    video_id = youtube_video_id(item)
    if not video_id:
        return None

    info_fetcher = info_fetcher or _extract_info_real
    try:
        info = info_fetcher(video_id)
    except Exception:  # noqa: BLE001 -- any inspection failure here just means "no captions available"; Tier 3 will independently discover and report a truly inaccessible video
        return None

    selected = _select_caption_track(info, language)
    if selected is None:
        return None
    kind, lang, table_key = selected
    table = (info.get("subtitles") or {}) if kind == "human" else (info.get("automatic_captions") or {})
    tracks = table.get(table_key) or []
    vtt_url = _vtt_track_url(tracks)
    if not vtt_url:
        return None

    cache_key = _caption_cache_key(video_id, kind, lang)
    raw_path = media_transcription.raw_transcripts_dir(inbox_dir) / f"yt-captions-{item['id']}.json"
    if not force and raw_path.exists():
        try:
            existing = json.loads(raw_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing is not None and existing.get("cache_key") == cache_key and existing.get("segments"):
            return YouTubeCaptionAcquisition(
                segments=existing["segments"],
                language=lang,
                method="publisher_provided" if kind == "human" else "auto_generated",
                tier=CAPTION_TIER_HUMAN if kind == "human" else CAPTION_TIER_AUTO,
                caption_kind=kind,
                created_by=existing.get("created_by", f"youtube-captions:{kind}:{lang}"),
                source_url=existing.get("source_url", vtt_url),
                checksum_sha256=existing["checksum_sha256"],
                cache_hit=True,
                cache_key=cache_key,
                raw_artifact_id=existing.get("id", f"yt-captions-{item['id']}"),
            )

    downloader = downloader or _download_text_real
    try:
        raw_text = downloader(vtt_url)
    except Exception:  # noqa: BLE001 -- caption body fetch failure falls through to Tier 3 (Phase 20 test 11), never raised
        return None

    try:
        segments = media_transcription.parse_timed_text_captions(raw_text)
    except media_transcription.RawTranscriptParseError:
        return None
    if kind == "auto":
        segments = _dedupe_rolling_auto_captions(segments)
    if not segments:
        return None

    checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    created_by = f"youtube-captions:{kind}:{lang}"
    now = now or _now_iso()
    artifact = {
        "id": f"yt-captions-{item['id']}",
        "record_type": "raw_youtube_captions_artifact",
        "item_id": item["id"],
        "video_id": video_id,
        "cache_key": cache_key,
        "caption_kind": kind,
        "language": lang,
        "source_url": vtt_url,
        "checksum_sha256": checksum,
        "created_by": created_by,
        "fetched_at": now,
        "segments": segments,
    }
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return YouTubeCaptionAcquisition(
        segments=segments,
        language=lang,
        method="publisher_provided" if kind == "human" else "auto_generated",
        tier=CAPTION_TIER_HUMAN if kind == "human" else CAPTION_TIER_AUTO,
        caption_kind=kind,
        created_by=created_by,
        source_url=vtt_url,
        checksum_sha256=checksum,
        cache_hit=False,
        cache_key=cache_key,
        raw_artifact_id=artifact["id"],
    )


# ---------------------------------------------------------------------------
# Phase 10 -- audio-only stream resolution + acquisition (Tier 3 fallback)
# ---------------------------------------------------------------------------


def _resolve_audio_format_real(
    video_id: str, info_fetcher: Callable[[str], dict[str, Any]]
) -> tuple[str, str, str, float | None]:
    """Returns `(stream_url, format_id, file_extension, duration_seconds)`
    for the best publicly accessible audio-only stream (highest bitrate
    `vcodec == "none"` format with a direct HTTPS URL -- the `bestaudio`
    selection this task's own grounding research recommended; no
    `--extract-audio`/ffmpeg post-processing is used or required, since
    faster-whisper decodes the downloaded container itself via PyAV -- see
    module docstring). Raises `media_transcription.MediaAcquisitionError`
    for a video this module cannot legitimately, unauthenticated-ly access
    (private/deleted/geo-restricted/age-restricted, or any other yt-dlp
    extraction failure) or that exposes no audio-only stream at all -- the
    Tier 3 terminal, actionable acquisition-error surface (Phase 17)."""
    try:
        info = info_fetcher(video_id)
    except YouTubeUnavailableError as exc:
        raise media_transcription.MediaAcquisitionError(
            f"YouTube video {video_id} is not accessible via legitimate, unauthenticated access: {exc}"
        ) from exc
    except RuntimeError as exc:
        raise media_transcription.MediaAcquisitionError(str(exc)) from exc

    formats = info.get("formats") or []
    audio_only = [
        f
        for f in formats
        if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none") and str(f.get("url") or "").startswith("http")
    ]
    if not audio_only:
        raise media_transcription.MediaAcquisitionError(
            f"no publicly accessible audio-only stream found for YouTube video {video_id}"
        )
    audio_only.sort(key=lambda f: f.get("abr") or 0, reverse=True)
    best = audio_only[0]
    ext = (best.get("ext") or "m4a").lstrip(".")
    return best["url"], str(best.get("format_id", "unknown")), ext, info.get("duration")


def acquire_youtube_audio(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    force: bool = False,
    now: str | None = None,
    info_fetcher: Callable[[str], dict[str, Any]] | None = None,
    downloader: Callable[[str], tuple[bytes, str | None]] | None = None,
) -> media_transcription.AcquiredMedia:
    """Downloads the item's best publicly accessible audio-only stream to
    the exact same `inbox/discovered_media/_media/<item_id><ext>` convention
    (and the exact same `AcquiredMedia` return shape) that
    `media_transcription.acquire_media()` already uses for RSS enclosures --
    one media-download convention, not two (Phase 10/11). Cache identity is
    the stable YouTube video id, not the resolved stream URL -- see module
    docstring's cache/idempotency section for why this must differ from
    `acquire_media()`'s URL-keyed cache. Raises
    `media_transcription.MediaAcquisitionError` for a missing/unreachable
    video, an empty download, or any HTTP failure -- never writes a
    truncated or corrupt-looking media file."""
    video_id = youtube_video_id(item)
    if not video_id:
        raise media_transcription.MediaAcquisitionError(
            f"item {item.get('id')!r} is not a YouTube-discovered item (no raw_metadata.yt_video_id)"
        )

    meta_path = media_transcription.media_dir(inbox_dir) / f"{item['id']}.meta.json"
    if not force and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        cached_path = Path(meta["path"]) if meta.get("path") else None
        if cached_path and cached_path.exists() and meta.get("video_id") == video_id:
            return media_transcription.AcquiredMedia(
                path=cached_path,
                media_url=meta.get("media_url", f"https://www.youtube.com/watch?v={video_id}"),
                checksum_sha256=meta["checksum_sha256"],
                byte_size=meta["byte_size"],
                content_type=meta.get("content_type"),
                downloaded_at=meta["downloaded_at"],
                reused_cache=True,
            )

    info_fetcher = info_fetcher or _extract_info_real
    stream_url, format_id, ext, duration = _resolve_audio_format_real(video_id, info_fetcher)

    downloader = downloader or _download_bytes_real
    try:
        content, content_type = downloader(stream_url)
    except media_transcription.MediaAcquisitionError:
        raise
    except Exception as exc:  # noqa: BLE001 -- any transport failure downloading the resolved stream
        raise media_transcription.MediaAcquisitionError(
            f"failed to download YouTube audio for {item.get('id')!r} (video {video_id}): {exc}"
        ) from exc
    if not content:
        raise media_transcription.MediaAcquisitionError(
            f"downloaded YouTube audio for {item.get('id')!r} (video {video_id}) was empty (0 bytes)"
        )

    now = now or _now_iso()
    checksum = hashlib.sha256(content).hexdigest()
    media_path = media_transcription.media_dir(inbox_dir) / f"{item['id']}.{ext}"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(content)

    meta = {
        "item_id": item["id"],
        "source_id": item.get("source_id"),
        "video_id": video_id,
        "format_id": format_id,
        "media_url": f"https://www.youtube.com/watch?v={video_id}",
        "path": str(media_path),
        "content_type": content_type,
        "byte_size": len(content),
        "checksum_sha256": checksum,
        "downloaded_at": now,
        "duration_seconds": duration,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return media_transcription.AcquiredMedia(
        path=media_path,
        media_url=meta["media_url"],
        checksum_sha256=checksum,
        byte_size=len(content),
        content_type=content_type,
        downloaded_at=now,
        reused_cache=False,
    )
