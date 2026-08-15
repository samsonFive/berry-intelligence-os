"""Media acquisition + local speech-to-text -- the bridge between a
discovered media item (`app/services/media_discovery.py`) and Codex's
provider-neutral transcript contract (`app/services/transcript_evidence.py`,
`TranscriptArtifact`), strictly outside the Evidence trust boundary.

## Where this sits

    Discovered Media Item -> Tier 1/2/3 acquisition -> raw provider-specific
    artifact -> normalization -> TranscriptArtifact-compatible dict -> STOP
    ---------------- TRUST / ANALYSIS BOUNDARY ----------------
    (Codex's TranscriptEvidenceExtractionService, not called from here)

This module never extracts CI claims, never creates atomic Evidence
proposals, never publishes trusted Evidence, and never calls
`TranscriptEvidenceExtractionService.run()`. It produces exactly one thing:
a dict that either satisfies `TranscriptArtifact.from_dict()` (a "resolved"
transcript, once a real Evidence id exists for the publication artifact) or
an equivalent "staged transcript" (same segments/provenance, but
`parent_evidence_id: null`, promotable later via `resolve_parent_evidence()`
-- see Phase 12 below). No function in this file writes to `data/evidence/`,
`data/facts/`, `data/assessments/`, `data/recommendations/`, or
`inbox/evidence/`.

## Acquisition hierarchy (explicit, in order -- Phase 4)

1. Tier 1 -- publisher-provided transcript: reuses
   `media_discovery.acquire_raw_transcript_artifact()` (an HTTP GET of a URL
   the publisher's own feed already declared via the Podcasting 2.0
   `<podcast:transcript>` tag -- no scraping, no guessing), then normalizes
   the fetched WebVTT/SRT body into timed segments here.
2. Tier 2 -- platform captions/subtitles: this phase implements
   *normalization only* (`normalize_platform_captions()`), given an
   already-legitimately-obtained captions document (e.g. a human operator
   downloads the platform's own official caption file by hand). It does
   NOT implement automated platform search/discovery (e.g. "find this
   episode on YouTube and pull its captions") -- that would require either
   API credentials (prohibited by this task) or scraping a platform's pages
   (also prohibited). `transcribe_discovered_item()` therefore only reaches
   Tier 2 when the caller supplies a captions document directly; absent
   that, an item whose `transcript_availability.status` is
   `platform_captions` falls through to Tier 3, exactly like
   `not_detected`/`unknown` -- never silently, always recorded in the
   returned `TranscriptionOutcome.tier`.
3. Tier 3 -- local speech-to-text: downloads the item's audio enclosure
   (`acquire_media()`) and transcribes it locally with a
   `TranscriptionProvider` (`FasterWhisperProvider` by default -- see
   below). Only reached when neither Tier 1 nor an already-supplied Tier 2
   document is usable.

## Raw vs. normalized boundary (Phase 3)

Every tier produces a raw, provider-specific artifact first (a fetched
VTT/SRT body for Tier 1/2, or a `raw_speech_to_text_artifact` JSON file for
Tier 3, both staged under `inbox/discovered_media/_transcripts/`) and only
*then* normalizes it into the provider-neutral shape
(`normalize_transcript()`) staged under `inbox/transcripts/`. Provider-
specific fields (engine name, model, device, VTT cue formatting, HTTP
metadata) live only in the raw artifact and in the normalized record's
`acquisition` block -- never inside `segments`/`provenance`/`language`,
which are exactly what `TranscriptArtifact.from_dict()` reads.

## Parent Evidence resolution (Phase 12)

Speech-to-text must not be gated on a trusted Evidence id existing yet.
`transcribe_discovered_item()` accepts `parent_evidence_id=None` (the
common case: a freshly discovered item with no reviewed publication
artifact) and produces a `record_type: "staged_transcript"` file with
`parent_evidence_id: null` -- same segments, same provenance, just not yet
linked. `resolve_parent_evidence()` later promotes that same file in place
to `record_type: "transcript_artifact"` with a real `parent_evidence_id`,
without re-running acquisition or transcription. When a real Evidence id is
already known up front (as it is for the Lucentlands POC,
`ev-lucentlands-scaling-blueberry-industry-2025`), pass it directly and a
fully-resolved artifact is produced immediately -- no separate promotion
step needed. This module never checks whether `parent_evidence_id` actually
resolves to a real, published, `publication_artifact`-role Evidence record
-- that validation belongs to
`TranscriptEvidenceExtractionService.run()` (never called from here) and to
`TranscriptArtifact.from_dict()`'s own regex check (only that the string
*looks like* an Evidence id).

## Idempotency / caching (Phase 14)

Two independent cache layers, both content-addressed:
- Media download: skipped (unless `force=True`) when a prior download's
  metadata sidecar names the same enclosure URL and the file still exists.
  Does not re-verify the remote body is unchanged (a URL is assumed stable
  once published, per Tier 1 fetch's own philosophy) -- if a publisher
  replaces a file's bytes at the same URL, `--force` is required.
- Transcription: `compute_cache_key()` hashes (item id, media checksum,
  engine name, model, requested language). A previously-produced raw STT
  artifact is reused whenever the key matches; any of those inputs changing
  is a cache miss. `--force` bypasses both layers unconditionally.

## Failure handling (Phase 15)

Every operational failure mode below raises a specific, caught exception;
`transcribe_discovered_item()` converts any of them into
`TranscriptionOutcome(status="error", ...)` -- it never raises for an
*expected* operational failure (mirrors
`media_discovery.DiscoveryRunResult`'s "failures are data" convention) and
never writes a normalized transcript file when a failure occurs (Phase 15's
"never produce a partially-valid-looking TranscriptArtifact" rule -- every
write happens only after all segments are known-good).

    media URL unavailable / HTTP failure      -> MediaAcquisitionError
    unsupported/corrupt audio                 -> TranscriptionError
    transcription dependency unavailable      -> TranscriptionDependencyError
    transcription process failure             -> TranscriptionError
    zero segments returned                    -> TranscriptionError
    malformed publisher transcript/captions   -> RawTranscriptParseError
    missing publication-artifact parent       -> NOT a failure; see Phase 12
    stale cached transcript                   -> automatic cache-key miss
    interrupted transcription                 -> propagates as TranscriptionError
    (or an uncaught KeyboardInterrupt/OSError, in which case no output file
    was written, since segments are only persisted once fully materialized)

## provenance.method mapping for platform captions (Phase 4/9, a genuine
judgment call `TranscriptArtifact`'s enum forces on this module -- see
`app/services/transcript_evidence.py`, not modified by this file)

`provenance.method` accepts exactly `publisher_provided` / `human_provided`
/ `auto_generated` -- there is no fourth value for "platform captions".
This module maps: machine/platform-generated captions -> `auto_generated`;
human-authored captions credited to the publisher/platform ->
`publisher_provided` (not `human_provided`, which this module reserves for
a transcript a human at this organization typed by hand -- not implemented
here, since no such intake path exists yet). See `normalize_platform_captions()`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

import httpx

from app.services import media_discovery

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

STAGING_SCHEMA_VERSION = 1

MEDIA_DOWNLOAD_TIMEOUT_SECONDS = 180
MEDIA_DOWNLOAD_USER_AGENT = "berry-intelligence-os-media-transcription/1.0"

# faster-whisper's own supported model sizes (per its published model card
# set) -- exposed here, not hardcoded to one choice, per Phase 8's "provide
# a configurable model choice ... document the available choices rather
# than baking one in". Rough quality/speed/local-resource tradeoff, CPU:
#   tiny     fastest, lowest quality  -- smoke-testing only
#   base     fast, low quality
#   small    balanced default -- reasonable quality at tolerable CPU runtime
#   medium   noticeably slower on CPU, better quality
#   large-v2 / large-v3   best quality, materially slower / more memory on CPU
AVAILABLE_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v2", "large-v3")
DEFAULT_WHISPER_MODEL = "small"


class MediaAcquisitionError(Exception):
    """Media URL missing/unreachable, HTTP failure, or a 0-byte download."""


class TranscriptionDependencyError(Exception):
    """The local speech-to-text engine (or a required native library) is
    not installed/loadable. Distinct from TranscriptionError (a dependency
    that loaded fine but failed to produce a usable result)."""


class TranscriptionError(Exception):
    """Corrupt/unsupported media, a transcription process failure, or zero
    segments returned. Never raised for an empty-but-legitimate transcript
    -- zero segments is always treated as a failure, not a valid empty
    result, per Phase 15."""


class RawTranscriptParseError(Exception):
    """A publisher transcript or captions document could not be parsed into
    timed segments (Phase 15's 'malformed publisher transcript'/'malformed
    captions'). Never silently degrades to untimed/guessed segments."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# staging directories -- reuses media_discovery's public staging_dir(); adds
# inbox/discovered_media/_media/ (raw audio) and inbox/transcripts/
# (normalized artifacts, staged or resolved). All gitignored via the
# project's existing blanket `inbox/` rule -- no .gitignore change needed.
# ---------------------------------------------------------------------------


def media_dir(inbox_dir: Path) -> Path:
    return media_discovery.staging_dir(inbox_dir) / "_media"


def raw_transcripts_dir(inbox_dir: Path) -> Path:
    """The same directory media_discovery.py's own Tier-1 fetcher already
    uses for its `raw_transcript_artifact` records -- reused here (per this
    task's own guidance to reuse it "if the shape fits") for this module's
    Tier-3 `raw_speech_to_text_artifact` records too, distinguished by a
    disjoint id prefix (`stt-` vs. `transcript-`) and `record_type`, so the
    two never collide or get confused despite sharing a directory."""
    return media_discovery.staging_dir(inbox_dir) / "_transcripts"


def transcripts_dir(inbox_dir: Path) -> Path:
    """Normalized TranscriptArtifact-shaped JSON, staged or fully resolved
    (Phase 13). Deliberately a sibling of `discovered_media/`, not nested
    inside it -- this is the layer's actual output, not raw intake."""
    return inbox_dir / "transcripts"


def _media_meta_path(inbox_dir: Path, item_id: str) -> Path:
    return media_dir(inbox_dir) / f"{item_id}.meta.json"


def load_discovered_item(inbox_dir: Path, item_id: str) -> dict[str, Any] | None:
    """Read one staged discovered-media-item record by id. Thin wrapper so
    the CLI doesn't need to know media_discovery.py's private path layout."""
    path = media_discovery.staging_dir(inbox_dir) / f"{item_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Phase 5/6 -- media acquisition
# ---------------------------------------------------------------------------


def select_enclosure_url(item: dict[str, Any]) -> str | None:
    """Picks the best playable-media URL from a discovered item's
    `raw_metadata.enclosures` (added by this task to
    `media_discovery._normalize_podcast_rss_entry()` -- additive, does not
    change any previously-emitted field). Prefers an explicitly audio/video
    typed enclosure; falls back to any enclosure with a URL; returns None
    (never guesses or fabricates a URL) if the item predates that field or
    genuinely has no enclosure -- Phase 5's "(1) RSS enclosure URL"
    preference order. Tiers 2/3 -- an official podcast-host or platform
    media URL beyond the RSS enclosure -- are not auto-discovered by this
    module (would require scraping or credentials); a caller may still
    reach Tier 3 by supplying `media_url_override` to `acquire_media()`."""
    enclosures = ((item.get("raw_metadata") or {}).get("enclosures")) or []
    for enclosure in enclosures:
        enclosure_type = (enclosure.get("type") or "").lower()
        if enclosure.get("url") and (enclosure_type.startswith("audio/") or enclosure_type.startswith("video/")):
            return enclosure["url"]
    for enclosure in enclosures:
        if enclosure.get("url"):
            return enclosure["url"]
    return None


_EXTENSION_BY_CONTENT_TYPE = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
}


def _extension_for(content_type: str | None, url: str) -> str:
    if content_type:
        base = content_type.split(";")[0].strip().lower()
        if base in _EXTENSION_BY_CONTENT_TYPE:
            return _EXTENSION_BY_CONTENT_TYPE[base]
    suffix = Path(urlparse(url).path).suffix
    return suffix if suffix else ".bin"


@dataclass(frozen=True)
class AcquiredMedia:
    path: Path
    media_url: str
    checksum_sha256: str
    byte_size: int
    content_type: str | None
    downloaded_at: str
    reused_cache: bool


def acquire_media(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    media_url_override: str | None = None,
    force: bool = False,
    now: str | None = None,
) -> AcquiredMedia:
    """Downloads the item's audio/video enclosure to
    `inbox/discovered_media/_media/<item_id><ext>` (deterministic filename
    from the item's stable id, never from its human-readable title --
    mirrors media_discovery.py's own dedupe-identity discipline), gitignored,
    outside trusted `data/`. Idempotent: a prior download is reused
    (unless `force=True`) when its metadata sidecar names the same media
    URL and the file still exists on disk. Raises MediaAcquisitionError for
    a missing/unreachable URL, any HTTP failure, or a 0-byte response --
    never writes a truncated or corrupt-looking media file."""
    media_url = media_url_override or select_enclosure_url(item)
    if not media_url:
        raise MediaAcquisitionError(
            f"no playable media enclosure URL recorded for item {item.get('id')!r} -- "
            "re-run discovery (this field was added after some items may have been staged) "
            "or pass media_url_override explicitly"
        )

    meta_path = _media_meta_path(inbox_dir, item["id"])
    if not force and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        cached_path = Path(meta["path"]) if meta.get("path") else None
        if cached_path and cached_path.exists() and meta.get("media_url") == media_url:
            return AcquiredMedia(
                path=cached_path,
                media_url=media_url,
                checksum_sha256=meta["checksum_sha256"],
                byte_size=meta["byte_size"],
                content_type=meta.get("content_type"),
                downloaded_at=meta["downloaded_at"],
                reused_cache=True,
            )

    now = now or _now_iso()
    try:
        response = httpx.get(
            media_url,
            timeout=MEDIA_DOWNLOAD_TIMEOUT_SECONDS,
            headers={"User-Agent": MEDIA_DOWNLOAD_USER_AGENT},
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MediaAcquisitionError(f"failed to download media for {item.get('id')!r} from {media_url}: {exc}") from exc

    content = response.content
    if not content:
        raise MediaAcquisitionError(f"downloaded media for {item.get('id')!r} from {media_url} was empty (0 bytes)")

    headers = getattr(response, "headers", None)
    content_type = headers.get("content-type") if headers and hasattr(headers, "get") else None
    checksum = hashlib.sha256(content).hexdigest()
    media_path = media_dir(inbox_dir) / f"{item['id']}{_extension_for(content_type, media_url)}"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(content)

    meta = {
        "item_id": item["id"],
        "source_id": item.get("source_id"),
        "media_url": media_url,
        "path": str(media_path),
        "content_type": content_type,
        "byte_size": len(content),
        "checksum_sha256": checksum,
        "downloaded_at": now,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return AcquiredMedia(
        path=media_path,
        media_url=media_url,
        checksum_sha256=checksum,
        byte_size=len(content),
        content_type=content_type,
        downloaded_at=now,
        reused_cache=False,
    )


# ---------------------------------------------------------------------------
# Phase 3/4 -- raw timed-text (WebVTT/SRT) parsing, shared by Tier 1 and
# Tier 2 normalization. Deliberately strict: raises rather than guessing.
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CUE_TIME_LINE_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})"
)
_TIMESTAMP_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})$")


def _timestamp_to_seconds(raw: str) -> float:
    match = _TIMESTAMP_RE.match(raw.strip())
    if not match:
        raise RawTranscriptParseError(f"unrecognized cue timestamp: {raw!r}")
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int(match.group(4).ljust(3, "0")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_timed_text_captions(raw_text: str) -> list[dict[str, Any]]:
    """Parses a WebVTT or SRT document into `[{"text", "start_seconds",
    "end_seconds"}, ...]`. Both formats share the same `HH:MM:SS.mmm -->
    HH:MM:SS.mmm` (VTT, '.') / `HH:MM:SS,mmm --> HH:MM:SS,mmm` (SRT, ',')
    cue-time line, so one scanner handles both; SRT's numeric cue-index
    lines are simply skipped (they don't match the cue-time regex). Strips
    inline VTT markup tags (`<i>`, `<c.colorname>`, etc.) from cue text.
    Raises RawTranscriptParseError -- never returns an empty/partial result
    -- if not a single valid timed cue is found, per Phase 15's 'malformed
    publisher transcript'/'malformed captions' handling."""
    if not raw_text or not raw_text.strip():
        raise RawTranscriptParseError("transcript/captions body is empty")

    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: list[dict[str, Any]] = []
    index = 0
    total = len(lines)
    while index < total:
        match = _CUE_TIME_LINE_RE.match(lines[index].strip())
        if not match:
            index += 1
            continue
        start = _timestamp_to_seconds(match.group("start"))
        end = _timestamp_to_seconds(match.group("end"))
        index += 1
        text_lines = []
        while index < total and lines[index].strip() != "":
            text_lines.append(lines[index].strip())
            index += 1
        text = _HTML_TAG_RE.sub("", " ".join(text_lines)).strip()
        if text:
            segments.append({"text": text, "start_seconds": start, "end_seconds": end})

    if not segments:
        raise RawTranscriptParseError("no timed cues found -- cannot produce a timestamped transcript")
    return segments


def normalize_platform_captions(raw_text: str, *, human_created: bool) -> tuple[list[dict[str, Any]], str]:
    """Tier 2 normalization entry point (see module docstring for why this
    is normalization-only, not automated platform discovery). Returns
    (segments, provenance_method) -- `auto_generated` for machine/platform-
    generated captions, `publisher_provided` for human-authored captions
    credited to the publisher/platform (the mapping this task's judgment
    call requires; see module docstring)."""
    segments = parse_timed_text_captions(raw_text)
    method = "publisher_provided" if human_created else "auto_generated"
    return segments, method


# ---------------------------------------------------------------------------
# Phase 7/8 -- local speech-to-text provider boundary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawSegment:
    text: str
    start_seconds: float
    end_seconds: float | None


@dataclass(frozen=True)
class RawTranscription:
    segments: tuple[RawSegment, ...]
    detected_language: str | None
    engine: str
    engine_version: str | None
    model: str
    device: str
    duration_seconds: float | None


class TranscriptionProvider(Protocol):
    name: str

    def transcribe(self, media_path: Path, *, language: str | None = None) -> RawTranscription: ...


def _faster_whisper_version() -> str | None:
    try:
        import importlib.metadata

        return importlib.metadata.version("faster-whisper")
    except Exception:  # noqa: BLE001 -- version string is diagnostic only, never load-bearing
        return None


class FasterWhisperProvider:
    """Local, offline speech-to-text via faster-whisper (CTranslate2-based
    Whisper). No external API, no credentials; model weights are cached
    locally by huggingface_hub on first real use. Not hardcoded as *the*
    TranscriptionProvider -- any object satisfying the Protocol above (e.g.
    a deterministic fake used by tests) works with `transcribe_media()`."""

    name = "faster-whisper"

    def __init__(self, *, model: str = DEFAULT_WHISPER_MODEL, device: str | None = None, compute_type: str | None = None) -> None:
        if model not in AVAILABLE_WHISPER_MODELS:
            raise ValueError(f"unsupported model {model!r}; choose one of {AVAILABLE_WHISPER_MODELS}")
        self.model_name = model
        self.device = device or self._detect_device()
        self.compute_type = compute_type or ("int8" if self.device == "cpu" else "float16")
        self._model: Any = None

    @staticmethod
    def _detect_device() -> str:
        # Deliberately simple (Phase 8's "do not over-engineer device
        # management"): only distinguishes "a usable CUDA device is
        # present" from "cpu", never multi-GPU selection or partial offload.
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
        except Exception:  # noqa: BLE001 -- any detection failure just means "assume cpu"
            pass
        return "cpu"

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionDependencyError(
                "faster-whisper is not installed -- add it from requirements.txt (`pip install -r requirements.txt`) "
                "to run local speech-to-text"
            ) from exc
        try:
            self._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        except Exception as exc:  # noqa: BLE001 -- any load failure (missing weights, unsupported device) is a dependency failure
            raise TranscriptionDependencyError(f"failed to load Whisper model {self.model_name!r} on {self.device!r}: {exc}") from exc
        return self._model

    def transcribe(self, media_path: Path, *, language: str | None = None) -> RawTranscription:
        if not media_path.exists():
            raise TranscriptionError(f"media file not found: {media_path}")
        model = self._load_model()
        try:
            segment_iter, info = model.transcribe(str(media_path), language=language, vad_filter=True)
            segments = tuple(
                RawSegment(text=raw.text.strip(), start_seconds=float(raw.start), end_seconds=float(raw.end))
                for raw in segment_iter
                if raw.text and raw.text.strip()
            )
        except TranscriptionDependencyError:
            raise
        except Exception as exc:  # noqa: BLE001 -- decode/inference failure (corrupt/unsupported media, etc.)
            raise TranscriptionError(f"local transcription failed for {media_path}: {exc}") from exc
        if not segments:
            raise TranscriptionError(f"transcription produced zero segments for {media_path} -- treated as a failure, not an empty result")
        return RawTranscription(
            segments=segments,
            detected_language=getattr(info, "language", None),
            engine=self.name,
            engine_version=_faster_whisper_version(),
            model=self.model_name,
            device=self.device,
            duration_seconds=getattr(info, "duration", None),
        )


# ---------------------------------------------------------------------------
# Phase 14 -- transcription cache identity + raw STT artifact persistence
# ---------------------------------------------------------------------------


def compute_cache_key(*, item_id: str, media_checksum_sha256: str, engine: str, model: str, language: str | None) -> str:
    basis = json.dumps(
        {"item_id": item_id, "media_checksum_sha256": media_checksum_sha256, "engine": engine, "model": model, "language": language},
        sort_keys=True,
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def transcribe_media(
    inbox_dir: Path,
    media_path: Path,
    *,
    item: dict[str, Any],
    provider: TranscriptionProvider,
    media_checksum_sha256: str,
    language: str | None = None,
    force: bool = False,
    now: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Runs (or reuses a cached run of) local speech-to-text for one item.
    Returns (raw_speech_to_text_artifact, cache_hit). The cache key covers
    item id, media checksum, engine, model, and requested language (Phase
    14) -- any change is a miss; `force=True` always re-transcribes."""
    model_name = getattr(provider, "model_name", getattr(provider, "name", "unknown"))
    cache_key = compute_cache_key(
        item_id=item["id"], media_checksum_sha256=media_checksum_sha256, engine=provider.name, model=model_name, language=language
    )
    raw_path = raw_transcripts_dir(inbox_dir) / f"stt-{item['id']}.json"
    if not force and raw_path.exists():
        try:
            existing = json.loads(raw_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing is not None and existing.get("cache_key") == cache_key:
            return existing, True

    now = now or _now_iso()
    raw = provider.transcribe(media_path, language=language)

    artifact = {
        "id": f"stt-{item['id']}",
        "record_type": "raw_speech_to_text_artifact",
        "staging_schema_version": STAGING_SCHEMA_VERSION,
        "item_id": item["id"],
        "source_id": item.get("source_id"),
        "cache_key": cache_key,
        "media_checksum_sha256": media_checksum_sha256,
        "engine": raw.engine,
        "engine_version": raw.engine_version,
        "model": raw.model,
        "device": raw.device,
        "language_requested": language,
        "detected_language": raw.detected_language,
        "media_duration_seconds": raw.duration_seconds,
        "transcribed_at": now,
        "segments": [
            {"text": segment.text, "start_seconds": segment.start_seconds, "end_seconds": segment.end_seconds}
            for segment in raw.segments
        ],
    }
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact, False


# ---------------------------------------------------------------------------
# Phase 3/11/12 -- normalization into the TranscriptArtifact-compatible shape
# ---------------------------------------------------------------------------


def normalize_transcript(
    *,
    item: dict[str, Any],
    segments: list[dict[str, Any]],
    language: str,
    method: str,
    created_by: str,
    created_at: str,
    parent_evidence_id: str | None,
    acquisition: dict[str, Any],
) -> dict[str, Any]:
    """Builds the normalized record. When `parent_evidence_id` is a real
    Evidence-shaped id string, the result satisfies
    `TranscriptArtifact.from_dict()` verbatim (extra keys --
    `id`/`record_type`/`item_id`/`source_id`/`acquisition`/`diagnostics` --
    are ignored by that pure parser, which only reads the specific keys its
    contract defines). When `parent_evidence_id` is None, the result is a
    `record_type: "staged_transcript"` -- same segments/provenance, just not
    yet linkable -- see `resolve_parent_evidence()`."""
    if not segments:
        raise TranscriptionError("cannot normalize an empty segment list into a transcript")
    ordered = sorted(segments, key=lambda s: s["start_seconds"])
    record_id = f"transcript-{item['id']}"
    return {
        "id": record_id,
        "record_type": "transcript_artifact" if parent_evidence_id else "staged_transcript",
        "schema_version": STAGING_SCHEMA_VERSION,
        "transcript_id": record_id,
        "item_id": item["id"],
        "source_id": item.get("source_id"),
        "parent_evidence_id": parent_evidence_id,
        "language": language,
        "provenance": {"method": method, "created_by": created_by, "created_at": created_at},
        "segments": [
            {
                "text": segment["text"],
                "start_seconds": segment["start_seconds"],
                "end_seconds": segment.get("end_seconds"),
                "speaker_label": segment.get("speaker_label"),
            }
            for segment in ordered
        ],
        "acquisition": acquisition,
    }


def write_transcript_artifact(inbox_dir: Path, payload: dict[str, Any]) -> Path:
    path = transcripts_dir(inbox_dir) / f"{payload['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_transcript_artifact(inbox_dir: Path, item_id: str) -> dict[str, Any] | None:
    path = transcripts_dir(inbox_dir) / f"transcript-{item_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_parent_evidence(inbox_dir: Path, item_id: str, parent_evidence_id: str) -> dict[str, Any]:
    """Promotes a previously-staged transcript (Phase 12) to a fully
    resolved, `TranscriptArtifact.from_dict()`-compatible record, in place
    -- same file, same segments/provenance, only `parent_evidence_id` and
    `record_type` change. Does not verify the id resolves to a real,
    published Evidence record with `evidence_role == "publication_artifact"`
    -- that check belongs to `TranscriptEvidenceExtractionService.run()`
    (never called from this module)."""
    if not re.fullmatch(r"ev-[a-z0-9-]+", parent_evidence_id):
        raise ValueError(f"parent_evidence_id does not look like an Evidence id: {parent_evidence_id!r}")
    payload = load_transcript_artifact(inbox_dir, item_id)
    if payload is None:
        raise TranscriptionError(f"no staged transcript found for item {item_id!r}")
    payload["parent_evidence_id"] = parent_evidence_id
    payload["record_type"] = "transcript_artifact"
    path = transcripts_dir(inbox_dir) / f"{payload['id']}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


# ---------------------------------------------------------------------------
# Phase 18 -- quality diagnostics
# ---------------------------------------------------------------------------


def compute_diagnostics(segments: list[dict[str, Any]], *, media_duration_seconds: float | None) -> dict[str, Any]:
    starts = [s["start_seconds"] for s in segments]
    monotonic = all(starts[i] <= starts[i + 1] for i in range(len(starts) - 1))
    ends = [s["end_seconds"] for s in segments if s.get("end_seconds") is not None]
    transcript_end_seconds = max(ends) if ends else (max(starts) if starts else 0.0)
    short_duration_segments = sum(
        1 for s in segments if s.get("end_seconds") is not None and (s["end_seconds"] - s["start_seconds"]) < 0.2
    )
    very_short_text_segments = sum(1 for s in segments if len(s["text"].strip()) < 2)
    coverage_ratio = (transcript_end_seconds / media_duration_seconds) if media_duration_seconds else None
    return {
        "segment_count": len(segments),
        "transcript_end_seconds": transcript_end_seconds,
        "timestamps_monotonic": monotonic,
        "short_duration_segment_count": short_duration_segments,
        "very_short_text_segment_count": very_short_text_segments,
        "media_duration_seconds": media_duration_seconds,
        "coverage_ratio": coverage_ratio,
        "low_coverage_suspected": coverage_ratio is not None and coverage_ratio < 0.5,
    }


# ---------------------------------------------------------------------------
# Phase 16 -- single-item orchestration (what the CLI calls)
# ---------------------------------------------------------------------------


@dataclass
class TranscriptionOutcome:
    status: str  # "ok" | "error"
    error: str | None = None
    tier: str | None = None
    cache_hit: bool = False
    output_path: Path | None = None
    segment_count: int = 0
    detected_language: str | None = None
    media_duration_seconds: float | None = None
    transcript_duration_seconds: float | None = None
    parent_evidence_id: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _run_tier1(
    inbox_dir: Path, item: dict[str, Any], *, parent_evidence_id: str | None, created_by: str | None, today: Callable[[], date]
) -> TranscriptionOutcome | None:
    """Returns None (not a failure) if the item's declared publisher
    transcript URL is missing despite the availability status claiming one
    -- caller falls through to Tier 3 in that case."""
    raw_artifact = media_discovery.acquire_raw_transcript_artifact(inbox_dir, item)
    if raw_artifact is None:
        return None
    segments = parse_timed_text_captions(raw_artifact["raw_text"])
    language = raw_artifact.get("language") or "unknown"
    acquisition = {
        "tier": "tier_1_publisher_transcript",
        "media_url": None,
        "source_url": raw_artifact["provenance_url"],
        "raw_artifact_id": raw_artifact["id"],
        "raw_artifact_checksum_sha256": raw_artifact["checksum_sha256"],
        "engine": None,
        "model": None,
        "device": None,
    }
    payload = normalize_transcript(
        item=item,
        segments=segments,
        language=language,
        method="publisher_provided",
        created_by=created_by or f"publisher:{item.get('source_id', 'unknown')}",
        created_at=today().isoformat(),
        parent_evidence_id=parent_evidence_id,
        acquisition=acquisition,
    )
    diagnostics = compute_diagnostics(payload["segments"], media_duration_seconds=item.get("duration_seconds"))
    payload["diagnostics"] = diagnostics
    output_path = write_transcript_artifact(inbox_dir, payload)
    return TranscriptionOutcome(
        status="ok",
        tier="tier_1_publisher_transcript",
        cache_hit=False,
        output_path=output_path,
        segment_count=len(payload["segments"]),
        detected_language=language,
        media_duration_seconds=item.get("duration_seconds"),
        transcript_duration_seconds=diagnostics["transcript_end_seconds"],
        parent_evidence_id=parent_evidence_id,
        diagnostics=diagnostics,
    )


def _run_tier3(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    model: str,
    device: str | None,
    language: str | None,
    parent_evidence_id: str | None,
    created_by: str | None,
    provider_factory: Callable[[], TranscriptionProvider] | None,
    force: bool,
    today: Callable[[], date],
) -> TranscriptionOutcome:
    acquired = acquire_media(inbox_dir, item, force=force)
    provider = (provider_factory or (lambda: FasterWhisperProvider(model=model, device=device)))()
    raw_artifact, cache_hit = transcribe_media(
        inbox_dir,
        acquired.path,
        item=item,
        provider=provider,
        media_checksum_sha256=acquired.checksum_sha256,
        language=language,
        force=force,
    )
    detected_language = raw_artifact.get("detected_language") or language or "unknown"
    acquisition = {
        "tier": "tier_3_local_speech_to_text",
        "media_url": acquired.media_url,
        "media_checksum_sha256": acquired.checksum_sha256,
        "media_path": str(acquired.path),
        "media_reused_from_cache": acquired.reused_cache,
        "raw_artifact_id": raw_artifact["id"],
        "cache_key": raw_artifact["cache_key"],
        "engine": raw_artifact["engine"],
        "engine_version": raw_artifact.get("engine_version"),
        "model": raw_artifact["model"],
        "device": raw_artifact["device"],
        "transcribed_at": raw_artifact["transcribed_at"],
    }
    payload = normalize_transcript(
        item=item,
        segments=raw_artifact["segments"],
        language=detected_language,
        method="auto_generated",
        created_by=created_by or f"{raw_artifact['engine']}:{raw_artifact['model']}",
        created_at=today().isoformat(),
        parent_evidence_id=parent_evidence_id,
        acquisition=acquisition,
    )
    media_duration = item.get("duration_seconds") or raw_artifact.get("media_duration_seconds")
    diagnostics = compute_diagnostics(payload["segments"], media_duration_seconds=media_duration)
    payload["diagnostics"] = diagnostics
    output_path = write_transcript_artifact(inbox_dir, payload)
    return TranscriptionOutcome(
        status="ok",
        tier="tier_3_local_speech_to_text",
        cache_hit=cache_hit,
        output_path=output_path,
        segment_count=len(payload["segments"]),
        detected_language=detected_language,
        media_duration_seconds=media_duration,
        transcript_duration_seconds=diagnostics["transcript_end_seconds"],
        parent_evidence_id=parent_evidence_id,
        diagnostics=diagnostics,
    )


def transcribe_discovered_item(
    inbox_dir: Path,
    item: dict[str, Any],
    *,
    model: str = DEFAULT_WHISPER_MODEL,
    device: str | None = None,
    language: str | None = None,
    parent_evidence_id: str | None = None,
    created_by: str | None = None,
    provider_factory: Callable[[], TranscriptionProvider] | None = None,
    force: bool = False,
    today: Callable[[], date] = date.today,
) -> TranscriptionOutcome:
    """Single-item orchestration (Phase 16): Tier 1 -> Tier 3 in that order
    (Tier 2 is reached only through `normalize_platform_captions()` called
    directly by a caller that already holds a captions document -- see
    module docstring). Never raises for an expected operational failure --
    returns `TranscriptionOutcome(status="error", ...)` instead. A missing
    `parent_evidence_id` is never a failure (Phase 12): the result is a
    valid staged transcript."""
    availability = item.get("transcript_availability") or {}
    status_value = availability.get("status")
    acquisition_errors = (MediaAcquisitionError, TranscriptionDependencyError, TranscriptionError, RawTranscriptParseError)

    outcome: TranscriptionOutcome | None = None
    if status_value == media_discovery.TRANSCRIPT_PUBLISHER:
        try:
            outcome = _run_tier1(inbox_dir, item, parent_evidence_id=parent_evidence_id, created_by=created_by, today=today)
        except acquisition_errors as exc:
            return TranscriptionOutcome(status="error", error=str(exc), tier="tier_1_publisher_transcript", parent_evidence_id=parent_evidence_id)

    if outcome is not None:
        return outcome

    try:
        return _run_tier3(
            inbox_dir,
            item,
            model=model,
            device=device,
            language=language,
            parent_evidence_id=parent_evidence_id,
            created_by=created_by,
            provider_factory=provider_factory,
            force=force,
            today=today,
        )
    except acquisition_errors as exc:
        return TranscriptionOutcome(status="error", error=str(exc), tier="tier_3_local_speech_to_text", parent_evidence_id=parent_evidence_id)
