"""YouTube caption/audio acquisition tests
(app/services/youtube_media_acquisition.py + its dispatch wiring inside
app/services/media_transcription.py's transcribe_discovered_item()).

Entirely offline: every yt-dlp call is replaced by an injected
`info_fetcher`/`downloader` fake (mirrors this project's existing
`monkeypatch.setattr(..., httpx, "get", ...)` convention for RSS, but at the
yt-dlp API boundary this task's own grounding research called for -- no real
`yt_dlp.YoutubeDL` instance, no real network call, is ever constructed by
this file). No test touches the live `data/` dataset. The real, live-network
proof against a real Redagricola video (video id TRG0WsxJ1Lw, "El arandano
esta conquistando a Ica") was run once by hand outside pytest -- see this
feature's report -- and is not re-run automatically here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services import media_discovery, media_transcription as mt, youtube_media_acquisition as yt_acq
from app.services.transcript_evidence import TranscriptArtifact, TranscriptContractError

SOURCE_ID = "source-youtube-media-acquisition-test-channel"
VIDEO_ID = "aBcDeFgHiJk"
PARENT_EVIDENCE_ID = "ev-youtube-media-acquisition-test-parent"


# ---------------------------------------------------------------------------
# fixtures / fakes
# ---------------------------------------------------------------------------


def _youtube_item(
    *,
    video_id: str = VIDEO_ID,
    suffix: str = "yt1",
    source_id: str = SOURCE_ID,
) -> dict[str, Any]:
    """Shape mirrors exactly what media_discovery.py's real youtube_feed
    adapter (_normalize_youtube_feed_entry -> upsert_discovered_item)
    produces -- platform_item_id + raw_metadata.yt_video_id populated,
    external_id null, transcript_availability.status TRANSCRIPT_UNKNOWN."""
    return {
        "id": f"discovered-test-{suffix}",
        "record_type": "discovered_media_item",
        "source_id": source_id,
        "title": f"Test YouTube Video {suffix}",
        "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
        "external_id": None,
        "platform_item_id": video_id,
        "published_date": "2026-07-07",
        "duration_seconds": None,
        "media_format": "video",
        "transcript_availability": {
            "status": media_discovery.TRANSCRIPT_UNKNOWN,
            "checked_at": "2026-08-15T00:00:00+00:00",
            "url": None,
            "language": None,
        },
        "raw_metadata": {
            "yt_video_id": video_id,
            "yt_channel_id": "UC-test-channel",
            "feed_entry_id": f"yt:video:{video_id}",
            "raw_title": f"Test YouTube Video {suffix}",
            "raw_published": "2026-07-07T00:00:00+00:00",
            "media_thumbnail": [],
        },
    }


def _rss_item(suffix: str = "rss1") -> dict[str, Any]:
    """A plain podcast_rss-shaped item -- no raw_metadata.yt_video_id at
    all -- used to prove the YouTube dispatch never fires for it."""
    return {
        "id": f"discovered-rss-{suffix}",
        "record_type": "discovered_media_item",
        "source_id": "source-rss-regression-test-podcast",
        "title": f"Test RSS Episode {suffix}",
        "canonical_url": f"https://example.invalid/{suffix}",
        "external_id": f"guid-{suffix}",
        "platform_item_id": None,
        "published_date": "2025-10-28",
        "duration_seconds": 300,
        "media_format": "podcast",
        "transcript_availability": {
            "status": media_discovery.TRANSCRIPT_NOT_DETECTED,
            "checked_at": "2026-08-15T00:00:00+00:00",
            "url": None,
            "language": None,
        },
        "raw_metadata": {
            "enclosures": [{"url": "https://example.invalid/audio-rss1.mp3", "type": "audio/mpeg", "length_bytes": 12345}]
        },
    }


def _vtt(cues: list[tuple[str, str, str]]) -> str:
    body = "WEBVTT\n\n"
    for start, end, text in cues:
        body += f"{start} --> {end}\n{text}\n\n"
    return body


_CLEAN_VTT = _vtt(
    [
        ("00:00:00.000", "00:00:02.000", "Hello and welcome."),
        ("00:00:02.000", "00:00:04.500", "Today we discuss blueberries."),
    ]
)

# A small, synthetic version of YouTube ASR's real "rolling window" pattern
# (verified against a real Redagricola auto-caption track -- see
# youtube_media_acquisition.py's module docstring): each new phrase first
# appears appended to the prior line, then reappears alone once the window
# scrolls.
_ROLLING_AUTO_VTT = (
    "WEBVTT\nKind: captions\nLanguage: es\n\n"
    "00:00:00.000 --> 00:00:02.000\nIca siempre fue\n\n"
    "00:00:02.000 --> 00:00:02.010\nIca siempre fue\n\n"
    "00:00:02.010 --> 00:00:04.000\nIca siempre fue tierra de arandanos\n\n"
    "00:00:04.000 --> 00:00:04.010\ntierra de arandanos\n\n"
    "00:00:04.010 --> 00:00:06.000\ntierra de arandanos que crecen bien\n\n"
)


def _info(
    *,
    subtitles: dict[str, Any] | None = None,
    automatic_captions: dict[str, Any] | None = None,
    language: str | None = "es",
    duration: float | None = 120.0,
    formats: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    default_formats = [
        {"format_id": "139", "vcodec": "none", "acodec": "mp4a.40.5", "ext": "m4a", "abr": 48.0, "url": "https://r1---sn-example.googlevideo.com/videoplayback?id=low"},
        {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2", "ext": "m4a", "abr": 129.0, "url": "https://r1---sn-example.googlevideo.com/videoplayback?id=high"},
        {"format_id": "18", "vcodec": "avc1.42001E", "acodec": "mp4a.40.2", "ext": "mp4", "abr": 96.0, "url": "https://r1---sn-example.googlevideo.com/videoplayback?id=video"},
    ]
    return {
        "id": VIDEO_ID,
        "title": "Test video",
        "language": language,
        "duration": duration,
        "availability": "public",
        "subtitles": subtitles or {},
        "automatic_captions": automatic_captions or {},
        "formats": formats if formats is not None else default_formats,
    }


def _track(url: str, ext: str = "vtt") -> list[dict[str, Any]]:
    return [{"ext": ext, "url": url}]


class _FakeInfoFetcher:
    def __init__(self, info: dict[str, Any] | None = None, *, raises: Exception | None = None) -> None:
        self.info = info
        self.raises = raises
        self.calls: list[str] = []

    def __call__(self, video_id: str) -> dict[str, Any]:
        self.calls.append(video_id)
        if self.raises is not None:
            raise self.raises
        return self.info


class _FakeCaptionDownloader:
    def __init__(self, text_by_url: dict[str, str] | None = None, *, raises: Exception | None = None) -> None:
        self.text_by_url = text_by_url or {}
        self.raises = raises
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        if self.raises is not None:
            raise self.raises
        return self.text_by_url[url]


class _FakeAudioDownloader:
    def __init__(self, content: bytes = b"FAKE-M4A-AUDIO-BYTES", content_type: str = "audio/mp4", *, raises: Exception | None = None) -> None:
        self.content = content
        self.content_type = content_type
        self.raises = raises
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[bytes, str | None]:
        self.calls.append(url)
        if self.raises is not None:
            raise self.raises
        return self.content, self.content_type


class _FakeProvider:
    name = "fake-engine"

    def __init__(self, *, model_name: str = "small", calls: list[Path] | None = None) -> None:
        self.model_name = model_name
        self.calls = calls if calls is not None else []

    def transcribe(self, media_path: Path, *, language: str | None = None) -> mt.RawTranscription:
        self.calls.append(media_path)
        return mt.RawTranscription(
            segments=(mt.RawSegment(text="Whisper fallback text.", start_seconds=0.0, end_seconds=2.0),),
            detected_language="es",
            engine=self.name,
            engine_version="0.0-test",
            model=self.model_name,
            device="cpu",
            duration_seconds=2.0,
        )


# ---------------------------------------------------------------------------
# 1: video id is stable acquisition identity
# ---------------------------------------------------------------------------


def test_video_id_is_the_acquisition_identity() -> None:
    item = _youtube_item(video_id="xyz123")
    assert yt_acq.youtube_video_id(item) == "xyz123"
    assert yt_acq.is_youtube_item(item) is True


def test_rss_item_is_never_recognized_as_youtube() -> None:
    item = _rss_item()
    assert yt_acq.youtube_video_id(item) is None
    assert yt_acq.is_youtube_item(item) is False
    assert mt._is_youtube_item(item) is False


# ---------------------------------------------------------------------------
# 2/8: human captions preferred over machine captions; provenance
# ---------------------------------------------------------------------------


def test_human_captions_preferred_over_machine_captions(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(
        subtitles={"es": _track("https://captions.invalid/human-es.vtt")},
        automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")},
    )
    downloader = _FakeCaptionDownloader({"https://captions.invalid/human-es.vtt": _CLEAN_VTT})

    result = yt_acq.fetch_captions(
        tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader
    )

    assert result is not None
    assert result.caption_kind == "human"
    assert result.tier == yt_acq.CAPTION_TIER_HUMAN
    assert result.method == "publisher_provided"
    assert result.created_by == "youtube-captions:human:es"
    assert downloader.calls == ["https://captions.invalid/human-es.vtt"]  # auto track never fetched


# ---------------------------------------------------------------------------
# 3/9: machine captions preferred over local Whisper; provenance
# ---------------------------------------------------------------------------


def test_machine_captions_preferred_over_whisper(tmp_path: Path, monkeypatch) -> None:
    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})
    provider = _FakeProvider()

    outcome = mt.transcribe_discovered_item(
        tmp_path / "inbox",
        item,
        provider_factory=lambda: provider,
        caption_info_fetcher=_FakeInfoFetcher(info),
        caption_downloader=downloader,
    )

    assert outcome.status == "ok"
    assert outcome.tier == yt_acq.CAPTION_TIER_AUTO
    assert provider.calls == []  # Whisper never invoked
    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["provenance"]["method"] == "auto_generated"
    assert payload["provenance"]["created_by"] == "youtube-captions:auto:es"


# ---------------------------------------------------------------------------
# 4: audio transcription is the fallback when no usable captions exist
# ---------------------------------------------------------------------------


def test_audio_fallback_when_no_usable_captions(tmp_path: Path) -> None:
    item = _youtube_item()
    caption_info = _info(subtitles={}, automatic_captions={})
    audio_info = _info(subtitles={}, automatic_captions={})
    provider = _FakeProvider()
    audio_dl = _FakeAudioDownloader()

    outcome = mt.transcribe_discovered_item(
        tmp_path / "inbox",
        item,
        provider_factory=lambda: provider,
        caption_info_fetcher=_FakeInfoFetcher(caption_info),
        youtube_audio_info_fetcher=_FakeInfoFetcher(audio_info),
        youtube_audio_downloader=audio_dl,
    )

    assert outcome.status == "ok"
    assert outcome.tier == "tier_3_local_speech_to_text"
    assert len(provider.calls) == 1
    assert audio_dl.calls == ["https://r1---sn-example.googlevideo.com/videoplayback?id=high"]  # highest-abr format chosen
    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["segments"][0]["text"] == "Whisper fallback text."


def test_audio_fallback_completes_with_injected_fakes(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(subtitles={}, automatic_captions={})
    provider = _FakeProvider()
    audio_dl = _FakeAudioDownloader()

    acquired = yt_acq.acquire_youtube_audio(
        tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=audio_dl
    )
    assert acquired.path.exists()
    assert acquired.checksum_sha256
    assert audio_dl.calls == ["https://r1---sn-example.googlevideo.com/videoplayback?id=high"]  # highest-abr format chosen

    raw_artifact, cache_hit = mt.transcribe_media(
        tmp_path / "inbox", acquired.path, item=item, provider=provider, media_checksum_sha256=acquired.checksum_sha256
    )
    assert cache_hit is False
    assert len(provider.calls) == 1


# ---------------------------------------------------------------------------
# 5: caption timestamps normalize correctly (incl. the rolling-window dedupe)
# ---------------------------------------------------------------------------


def test_caption_timestamps_normalize_correctly(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert [s["start_seconds"] for s in result.segments] == [0.0, 2.0]
    assert [s["end_seconds"] for s in result.segments] == [2.0, 4.5]


def test_rolling_auto_caption_window_is_deduped_without_losing_content() -> None:
    raw_segments = mt.parse_timed_text_captions(_ROLLING_AUTO_VTT)
    assert len(raw_segments) == 5  # the raw, redundant cue count

    cleaned = yt_acq._dedupe_rolling_auto_captions(raw_segments)

    assert [s["text"] for s in cleaned] == ["Ica siempre fue", "tierra de arandanos", "que crecen bien"]
    full_text = " ".join(s["text"] for s in cleaned)
    assert full_text == "Ica siempre fue tierra de arandanos que crecen bien"


def test_human_captions_are_not_rolling_deduped(tmp_path: Path) -> None:
    """A manual/uploaded subtitle track is passed through unmodified --
    the rolling-window cleanup is an auto-caption-only quirk."""
    item = _youtube_item()
    info = _info(subtitles={"es": _track("https://captions.invalid/human-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/human-es.vtt": _ROLLING_AUTO_VTT})

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert len(result.segments) == 5  # NOT deduped -- passed straight through


# ---------------------------------------------------------------------------
# 6: language propagates correctly; never translated
# ---------------------------------------------------------------------------


def test_detected_video_language_selects_matching_track(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(
        language="es",
        automatic_captions={
            "es": _track("https://captions.invalid/auto-es.vtt"),
            "en": _track("https://captions.invalid/auto-en-TRANSLATED.vtt"),
            "fr": _track("https://captions.invalid/auto-fr-TRANSLATED.vtt"),
        },
    )
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert result.language == "es"
    assert downloader.calls == ["https://captions.invalid/auto-es.vtt"]  # translated en/fr tracks never touched


def test_orig_suffixed_key_used_when_bare_language_key_absent(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(
        language="es",
        automatic_captions={
            "es-orig": _track("https://captions.invalid/auto-es-orig.vtt"),
            "en": _track("https://captions.invalid/auto-en-TRANSLATED.vtt"),
        },
    )
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es-orig.vtt": _CLEAN_VTT})

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert result.language == "es"  # -orig suffix stripped for the recorded language


def test_ambiguous_language_never_guesses_a_translated_track(tmp_path: Path) -> None:
    """No declared video language, no -orig marker, two candidate original-
    language bases -- refuses to guess (falls through to Tier 3) rather
    than risk selecting a machine-translated caption (Phase 15)."""
    item = _youtube_item()
    info = _info(
        language=None,
        automatic_captions={
            "es": _track("https://captions.invalid/auto-es.vtt"),
            "pt": _track("https://captions.invalid/auto-pt.vtt"),
        },
    )
    downloader = _FakeCaptionDownloader()

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert result is None
    assert downloader.calls == []


# ---------------------------------------------------------------------------
# 7: speaker labels never invented
# ---------------------------------------------------------------------------


def test_speaker_labels_never_invented_from_captions(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})

    outcome = mt.transcribe_discovered_item(
        tmp_path / "inbox", item, caption_info_fetcher=_FakeInfoFetcher(info), caption_downloader=downloader
    )

    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert all(segment["speaker_label"] is None for segment in payload["segments"])


# ---------------------------------------------------------------------------
# 10: local Whisper provenance remains correct for a YouTube item
# ---------------------------------------------------------------------------


def test_whisper_provenance_correct_for_youtube_audio_fallback(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(subtitles={}, automatic_captions={})
    provider = _FakeProvider(model_name="small")
    audio_dl = _FakeAudioDownloader()

    acquired = yt_acq.acquire_youtube_audio(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=audio_dl)
    raw_artifact, _ = mt.transcribe_media(
        tmp_path / "inbox", acquired.path, item=item, provider=provider, media_checksum_sha256=acquired.checksum_sha256
    )
    payload = mt.normalize_transcript(
        item=item,
        segments=raw_artifact["segments"],
        language=raw_artifact["detected_language"],
        method="auto_generated",
        created_by=f"{raw_artifact['engine']}:{raw_artifact['model']}",
        created_at="2026-08-16",
        parent_evidence_id=None,
        acquisition={"tier": "tier_3_local_speech_to_text"},
    )
    assert payload["provenance"]["method"] == "auto_generated"
    assert payload["provenance"]["created_by"] == "fake-engine:small"  # distinct from any "youtube-captions:*" label


# ---------------------------------------------------------------------------
# 11: caption acquisition failure falls back to audio
# ---------------------------------------------------------------------------


def test_caption_body_fetch_failure_falls_back_to_tier3(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader(raises=RuntimeError("simulated captions endpoint failure"))

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert result is None  # never raises -- caller (transcribe_discovered_item) falls through to Tier 3


def test_caption_inspection_failure_falls_back_to_tier3(tmp_path: Path) -> None:
    item = _youtube_item()
    fetcher = _FakeInfoFetcher(raises=yt_acq.YouTubeUnavailableError("simulated inspection failure"))

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=fetcher)

    assert result is None


# ---------------------------------------------------------------------------
# 12/13: total acquisition failure produces no valid transcript; private
# /unavailable video produces a clear, actionable failure
# ---------------------------------------------------------------------------


def test_private_video_produces_clear_terminal_failure(tmp_path: Path) -> None:
    item = _youtube_item()
    caption_fetcher = _FakeInfoFetcher(raises=yt_acq.YouTubeUnavailableError("Private video. Sign in if you've been invited"))
    audio_fetcher = _FakeInfoFetcher(raises=yt_acq.YouTubeUnavailableError("Private video. Sign in if you've been invited"))

    outcome = mt.transcribe_discovered_item(
        tmp_path / "inbox",
        item,
        caption_info_fetcher=caption_fetcher,
        youtube_audio_info_fetcher=audio_fetcher,
    )

    # Tier 2 silently falls through (inspection fails there too); Tier 3
    # is the authoritative reporter of the real, actionable failure.
    assert outcome.status == "error"
    assert outcome.tier == "tier_3_local_speech_to_text"
    assert "not accessible" in outcome.error
    assert not mt.transcripts_dir(tmp_path / "inbox").exists()


def test_resolve_audio_format_raises_clear_error_for_unavailable_video(tmp_path: Path) -> None:
    item = _youtube_item()
    fetcher = _FakeInfoFetcher(raises=yt_acq.YouTubeUnavailableError("Private video"))

    with pytest.raises(mt.MediaAcquisitionError, match="not accessible"):
        yt_acq.acquire_youtube_audio(tmp_path / "inbox", item, info_fetcher=fetcher)


def test_no_audio_only_stream_available_fails_cleanly(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(formats=[{"format_id": "18", "vcodec": "avc1.42001E", "acodec": "mp4a.40.2", "ext": "mp4", "abr": 96.0, "url": "https://example.invalid/video-only"}])

    with pytest.raises(mt.MediaAcquisitionError, match="no publicly accessible audio-only stream"):
        yt_acq.acquire_youtube_audio(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info))


# ---------------------------------------------------------------------------
# 14: repeated caption use is idempotent
# ---------------------------------------------------------------------------


def test_repeated_caption_fetch_is_idempotent(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})
    inbox_dir = tmp_path / "inbox"

    first = yt_acq.fetch_captions(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)
    second = yt_acq.fetch_captions(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert downloader.calls == ["https://captions.invalid/auto-es.vtt"]  # fetched exactly once


def test_caption_cache_force_bypasses_cache(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})
    inbox_dir = tmp_path / "inbox"

    yt_acq.fetch_captions(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)
    second = yt_acq.fetch_captions(inbox_dir, item, force=True, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert second.cache_hit is False
    assert len(downloader.calls) == 2


# ---------------------------------------------------------------------------
# 15: repeated audio/STT use reuses cache -- keyed on video id, NOT on the
# (ephemeral, signed) resolved stream URL
# ---------------------------------------------------------------------------


def test_repeated_audio_acquisition_reuses_cache_despite_url_rotation(tmp_path: Path) -> None:
    item = _youtube_item()
    info_call_1 = _info(formats=[{"format_id": "139", "vcodec": "none", "acodec": "mp4a.40.5", "ext": "m4a", "abr": 48.0, "url": "https://cdn.invalid/session-1-signed-url"}])
    info_call_2 = _info(formats=[{"format_id": "139", "vcodec": "none", "acodec": "mp4a.40.5", "ext": "m4a", "abr": 48.0, "url": "https://cdn.invalid/session-2-DIFFERENT-signed-url"}])
    audio_dl = _FakeAudioDownloader()
    inbox_dir = tmp_path / "inbox"

    first = yt_acq.acquire_youtube_audio(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info_call_1), downloader=audio_dl)
    second = yt_acq.acquire_youtube_audio(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info_call_2), downloader=audio_dl)

    assert first.reused_cache is False
    assert second.reused_cache is True  # cache hit even though the resolved URL would have been different
    assert audio_dl.calls == ["https://cdn.invalid/session-1-signed-url"]  # never re-downloaded


def test_audio_cache_force_bypasses_cache(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info()
    audio_dl = _FakeAudioDownloader()
    inbox_dir = tmp_path / "inbox"

    yt_acq.acquire_youtube_audio(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=audio_dl)
    second = yt_acq.acquire_youtube_audio(inbox_dir, item, force=True, info_fetcher=_FakeInfoFetcher(info), downloader=audio_dl)

    assert second.reused_cache is False
    assert len(audio_dl.calls) == 2


# ---------------------------------------------------------------------------
# 16: RSS enclosure behavior is completely unaffected
# ---------------------------------------------------------------------------


def test_rss_item_never_dispatches_into_youtube_tier2(tmp_path: Path, monkeypatch) -> None:
    item = _rss_item()

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("YouTube info_fetcher must never be called for an RSS item")

    provider = _FakeProvider()

    def _mock_audio_get(*a, **k):
        class _R:
            content = b"fake audio"
            headers = {"content-type": "audio/mpeg"}

            def raise_for_status(self):
                return None

        return _R()

    monkeypatch.setattr(mt.httpx, "get", _mock_audio_get)

    outcome = mt.transcribe_discovered_item(
        tmp_path / "inbox",
        item,
        provider_factory=lambda: provider,
        caption_info_fetcher=_fail_if_called,
        caption_downloader=_fail_if_called,
    )

    assert outcome.status == "ok"
    assert outcome.tier == "tier_3_local_speech_to_text"
    assert len(provider.calls) == 1


def test_select_enclosure_url_unaffected_by_youtube_module(tmp_path: Path) -> None:
    item = _rss_item()
    assert mt.select_enclosure_url(item) == "https://example.invalid/audio-rss1.mp3"


# ---------------------------------------------------------------------------
# 20/21/22/23: no Evidence/Fact/Assessment/Recommendation created; no
# company-specific behavior -- a differently-shaped, non-Redagricola
# YouTube item reaches the exact same code path with zero special-casing
# ---------------------------------------------------------------------------


def test_no_atomic_evidence_or_trusted_records_created(tmp_path: Path) -> None:
    from app.composition import get_repositories
    from app.repositories.paths import SCHEMAS_DIR

    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})
    inbox_dir = tmp_path / "inbox"
    repos = get_repositories(tmp_path / "data", SCHEMAS_DIR)

    mt.transcribe_discovered_item(
        inbox_dir, item, parent_evidence_id=PARENT_EVIDENCE_ID, caption_info_fetcher=_FakeInfoFetcher(info), caption_downloader=downloader
    )

    assert not (inbox_dir / "evidence").exists()
    assert repos.evidence.list() == []
    assert repos.facts.list() == []
    assert repos.assessments.list() == []
    assert repos.recommendations.list() == []


def test_generic_adapter_works_unchanged_for_a_different_youtube_source(tmp_path: Path) -> None:
    """No source_id branching anywhere in this module: a completely
    different (fictional, non-Redagricola) YouTube-first source, with a
    different video id, reaches the identical acquisition mechanism."""
    item = _youtube_item(video_id="zzz999other", suffix="other-source", source_id="source-some-other-youtube-channel")
    info = _info(automatic_captions={"en": _track("https://captions.invalid/auto-en.vtt")}, language="en")
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-en.vtt": _CLEAN_VTT})

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert result is not None
    assert result.language == "en"
    assert result.tier == yt_acq.CAPTION_TIER_AUTO


# ---------------------------------------------------------------------------
# downstream TranscriptArtifact contract compatibility (Phase 21 discipline,
# same as tests/test_media_transcription.py's own contract tests)
# ---------------------------------------------------------------------------


def test_caption_transcript_satisfies_transcript_artifact_contract_once_resolved(tmp_path: Path) -> None:
    item = _youtube_item()
    info = _info(automatic_captions={"es": _track("https://captions.invalid/auto-es.vtt")})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/auto-es.vtt": _CLEAN_VTT})
    inbox_dir = tmp_path / "inbox"

    outcome = mt.transcribe_discovered_item(
        inbox_dir, item, parent_evidence_id=None, caption_info_fetcher=_FakeInfoFetcher(info), caption_downloader=downloader
    )
    assert outcome.status == "ok"
    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["record_type"] == "staged_transcript"
    with pytest.raises(TranscriptContractError):
        TranscriptArtifact.from_dict(payload)

    resolved = mt.resolve_parent_evidence(inbox_dir, item["id"], PARENT_EVIDENCE_ID)
    artifact = TranscriptArtifact.from_dict(resolved)
    assert artifact.parent_evidence_id == PARENT_EVIDENCE_ID
    assert len(artifact.segments) == 2
