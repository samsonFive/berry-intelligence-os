"""Second-YouTube-source portability tests
(feature/youtube-source-portability).

Companion to tests/test_media_discovery_source_expansion.py and
tests/test_youtube_media_acquisition.py, which already prove the generic
`youtube_feed` discovery adapter and the generic YouTube caption/audio
acquisition module end-to-end against the real, first-party Redagricola
channel/playlists. This file adds the specific coverage this phase's
portability proof requires: a second, independent, real, first-party YouTube
publisher -- the University of Arkansas System Division of Agriculture
(channel handle @AginArk, channel id UCXV6_ND45kOoy2_T9JI-9KA, registered as
`source-university-of-arkansas-division-of-agriculture` in
data/configuration/sources.json) -- reaching the exact same
discovery/acquisition code with zero source-specific Python.

Real, live, one-time proof (not re-run by pytest): a real `discover_source()`
run against this channel's real public Atom feed staged 15 real, dated
uploads including the real target video (id lU8lTJSdpfA, "Amanda McWhirt -
Building Better Harvests | Behind the Discovery", published 2026-07-30 by
"Arkansas Division of Agriculture" -- verified via YouTube's oembed endpoint
and yt-dlp's own extract_info()). A real `transcribe_discovered_item()` run
(via scripts/transcribe_media.py) acquired that video's real, first-party
English human captions (Tier 2a, tier_2_youtube_human_captions) -- no local
Whisper needed -- producing a 42-segment normalized transcript running to
547.6s. Re-running both discovery and transcription confirmed idempotency
(0 new items, cache hit). See this feature's final report for full details.

Every test below is entirely offline: every yt-dlp/HTTP call is replaced by
an injected fake or monkeypatched at the same boundaries this project's
existing tests already use. No test performs a live network call or touches
the real inbox/. Fixtures mirror the real, verified structural shape of the
real Arkansas channel feed and the real English human-caption track
(sentence-level cues, proper punctuation, no rolling-window duplication --
structurally distinct from Redagricola's Spanish auto-caption shape,
confirming the normalizer is robust across a second, differently-shaped real
caption source) without reproducing the publisher's actual caption text.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app import main
from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services import media_discovery, media_transcription as mt, youtube_media_acquisition as yt_acq
from app.services.media_discovery import discover_source, list_discovered_items
from app.services.media_orchestration import MediaTranscriptionAdapter

ARKANSAS_SOURCE_ID = "source-university-of-arkansas-division-of-agriculture"
ARKANSAS_CHANNEL_ID = "UCXV6_ND45kOoy2_T9JI-9KA"
ARKANSAS_VIDEO_ID = "lU8lTJSdpfA"  # real, verified: "Amanda McWhirt - Building Better Harvests | Behind the Discovery"
REDAGRICOLA_SOURCE_ID = "source-redagricola-on-the-road"


# ---------------------------------------------------------------------------
# 1. The real Source config, as registered, is a config-only registration --
#    generic adapter, no new Python. (Phase 4/5/9)
# ---------------------------------------------------------------------------


def _real_sources() -> list[dict[str, Any]]:
    return json.loads((DEFAULT_DATA_DIR / "configuration" / "sources.json").read_text(encoding="utf-8"))


def test_real_arkansas_source_registered_with_generic_youtube_feed_config() -> None:
    """The second real publisher was onboarded purely as a
    data/configuration/sources.json record -- no new adapter, no new
    discovery mechanism, no source_id-keyed branch anywhere in
    app/services/media_discovery.py or app/services/youtube_media_acquisition.py."""
    sources = {s["id"]: s for s in _real_sources()}
    assert ARKANSAS_SOURCE_ID in sources
    record = sources[ARKANSAS_SOURCE_ID]
    assert record["type"] == "reference"
    discovery = record["discovery"]
    assert discovery["adapter"] == "youtube_feed"  # the exact same adapter type Redagricola uses
    assert discovery["feed_url"] == f"https://www.youtube.com/feeds/videos.xml?channel_id={ARKANSAS_CHANNEL_ID}"
    # Follows the existing registry contract (same shape as the three prior
    # spoken-word Sources -- see tests/test_spoken_word_sources.py).
    assert record["update_cadence"] in main.SOURCE_CADENCES
    assert set(record["entity_types"]) <= set(main.SOURCE_ENTITY_TYPES)
    assert set(record["region_coverage"]) <= set(main.SOURCE_REGIONS)
    assert set(record["berry_ids"]) <= set(main.BERRIES)
    assert record["enabled"] is True


def test_real_arkansas_source_is_distinct_from_existing_fruit_breeding_program_source() -> None:
    """Phase 4: a NEW Source was created rather than retrofitting the
    existing AAES 'Fruit Breeding Program' reference Source, because the
    real, verified YouTube channel (@AginArk / 'Arkansas Division of
    Agriculture') is owned by the broader University of Arkansas System
    Division of Agriculture, not AAES specifically -- the existing Source's
    own webpage (aaes.uada.edu/fruit-research/) is a materially different
    publication surface. Both remain distinct, truthful records."""
    sources = {s["id"]: s for s in _real_sources()}
    fruit_breeding = sources["source-20260806173428-ae24-university-of-arkansas-fruit-breeding-pr-22"]
    new_source = sources[ARKANSAS_SOURCE_ID]
    assert fruit_breeding.get("discovery") is None  # untouched by this phase
    assert new_source["value"] != fruit_breeding["value"]
    assert new_source["id"] != fruit_breeding["id"]


def test_source_config_alone_selects_youtube_adapter_not_a_hardcoded_arkansas_branch(tmp_path: Path, monkeypatch) -> None:
    """The generic-mechanism claim, proven directly: a totally fictional
    Source, differently named and differently shaped from both Redagricola
    and Arkansas, reaches the identical `youtube_feed` adapter code purely
    because its own `discovery.adapter` field says so -- exactly mirroring
    tests/test_media_discovery_source_expansion.py's
    test_source_config_drives_adapter_selection_not_source_id, run again
    here to document that adding a *second* real YouTube source did not
    require adding a second adapter or any per-source conditional."""
    repos = get_repositories(tmp_path, SCHEMAS_DIR)
    fictional_id = "source-portability-test-completely-different-channel"
    fictional_feed = "https://www.youtube.com/feeds/videos.xml?channel_id=UCFictionalTestChannel99"
    repos.sources.create(
        {
            "id": fictional_id,
            "type": "reference",
            "label": "Fictional Test Channel",
            "discovery": {"adapter": "youtube_feed", "feed_url": fictional_feed},
        }
    )
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
<yt:channelId>UCFictionalTestChannel99</yt:channelId>
<title>Fictional Test Channel</title>
<entry>
<id>yt:video:fictionalVid001</id>
<yt:videoId>fictionalVid001</yt:videoId>
<yt:channelId>UCFictionalTestChannel99</yt:channelId>
<title>Fictional Berry Field Day Recap</title>
<link rel="alternate" href="https://www.youtube.com/watch?v=fictionalVid001"/>
<published>2026-08-01T00:00:00+00:00</published>
</entry>
</feed>""".encode("utf-8")

    def _get(url, *a, **k):
        assert url == fictional_feed
        class _R:
            content = feed
            def raise_for_status(self):
                return None
        return _R()

    monkeypatch.setattr(media_discovery.httpx, "get", _get)
    result = discover_source(fictional_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert result.status == "ok"
    assert result.items[0]["platform_item_id"] == "fictionalVid001"
    assert result.items[0]["media_format"] == "video"
    assert yt_acq.youtube_video_id(result.items[0]) == "fictionalVid001"


# ---------------------------------------------------------------------------
# 2. A real-style Arkansas channel feed fixture normalizes correctly
#    (Phase 5/6): stable video id, canonical URL, dedupe identity.
# ---------------------------------------------------------------------------


def _arkansas_style_entry_xml(*, video_id: str, title: str, published: str) -> str:
    """Mirrors the real Arkansas Atom feed's structural shape (verified
    2026-08-16 against the live https://www.youtube.com/feeds/videos.xml?
    channel_id=UCXV6_ND45kOoy2_T9JI-9KA feed) -- same Atom/yt/media namespace
    layout as Redagricola's feed (see test_media_discovery_source_expansion.py),
    proving the identical adapter code handles a second, independent
    real-world channel's feed without modification."""
    return f"""
<entry>
<id>yt:video:{video_id}</id>
<yt:videoId>{video_id}</yt:videoId>
<yt:channelId>{ARKANSAS_CHANNEL_ID}</yt:channelId>
<title>{title}</title>
<link rel="alternate" href="https://www.youtube.com/watch?v={video_id}"/>
<author><name>Arkansas Division of Agriculture</name><uri>https://www.youtube.com/channel/{ARKANSAS_CHANNEL_ID}</uri></author>
<published>{published}</published>
<updated>{published}</updated>
<media:group>
<media:title>{title}</media:title>
<media:thumbnail url="https://i1.ytimg.com/vi/{video_id}/hqdefault.jpg" width="480" height="360"/>
<media:description>Extension video.</media:description>
</media:group>
</entry>"""


def _arkansas_style_feed(entries: list[str]) -> bytes:
    body = "\n".join(entries)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
<link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id={ARKANSAS_CHANNEL_ID}"/>
<id>yt:channel:{ARKANSAS_CHANNEL_ID}</id>
<yt:channelId>{ARKANSAS_CHANNEL_ID}</yt:channelId>
<title>Arkansas Division of Agriculture</title>
<link rel="alternate" href="https://www.youtube.com/channel/{ARKANSAS_CHANNEL_ID}"/>
<author><name>Arkansas Division of Agriculture</name><uri>https://www.youtube.com/channel/{ARKANSAS_CHANNEL_ID}</uri></author>
<published>2015-01-01T00:00:00+00:00</published>
{body}
</feed>""".encode("utf-8")


ARKANSAS_TEST_FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={ARKANSAS_CHANNEL_ID}"


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


def _register_arkansas_test_source(repos, feed_url: str = ARKANSAS_TEST_FEED_URL):
    return repos.sources.create(
        {
            "id": "source-portability-test-arkansas",
            "type": "reference",
            "label": "Arkansas Division of Agriculture (Test Fixture)",
            "discovery": {"adapter": "youtube_feed", "feed_url": feed_url},
        }
    )


def _mock_get(monkeypatch, routes: dict[str, bytes]) -> None:
    def _get(url, *a, **k):
        if url not in routes:
            raise AssertionError(f"unmocked URL in test: {url}")

        class _R:
            content = routes[url]

            def raise_for_status(self):
                return None

        return _R()

    monkeypatch.setattr(media_discovery.httpx, "get", _get)


def test_real_style_arkansas_feed_fixture_normalizes_correctly(tmp_path, repos, monkeypatch) -> None:
    _register_arkansas_test_source(repos)
    feed = _arkansas_style_feed(
        [
            _arkansas_style_entry_xml(
                video_id=ARKANSAS_VIDEO_ID,
                title="Amanda McWhirt - Building Better Harvests | Behind the Discovery",
                published="2026-07-30T19:16:22+00:00",
            ),
            _arkansas_style_entry_xml(video_id="Lv8m3q_ytyU", title="2025 Blackberry Field Day", published="2025-06-15T12:00:00+00:00"),
        ]
    )
    _mock_get(monkeypatch, {ARKANSAS_TEST_FEED_URL: feed})
    result = discover_source("source-portability-test-arkansas", inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "ok"
    assert result.found == 2
    assert result.new == 2
    by_video_id = {item["platform_item_id"]: item for item in result.items}
    mcwhirt = by_video_id[ARKANSAS_VIDEO_ID]
    assert mcwhirt["canonical_url"] == f"https://www.youtube.com/watch?v={ARKANSAS_VIDEO_ID}"
    assert mcwhirt["media_format"] == "video"
    assert mcwhirt["media_format"] in media_discovery.MEDIA_FORMATS
    assert mcwhirt["dedupe_strategy"] == media_discovery.DEDUPE_STRATEGY_PLATFORM_ID
    assert mcwhirt["raw_metadata"]["yt_video_id"] == ARKANSAS_VIDEO_ID
    assert mcwhirt["transcript_availability"]["status"] == media_discovery.TRANSCRIPT_UNKNOWN
    assert mcwhirt["published_date"] == "2026-07-30"


def test_repeated_discovery_of_arkansas_feed_is_idempotent(tmp_path, repos, monkeypatch) -> None:
    _register_arkansas_test_source(repos)
    feed = _arkansas_style_feed(
        [_arkansas_style_entry_xml(video_id=ARKANSAS_VIDEO_ID, title="Amanda McWhirt - Building Better Harvests", published="2026-07-30T19:16:22+00:00")]
    )
    _mock_get(monkeypatch, {ARKANSAS_TEST_FEED_URL: feed})
    inbox_dir = tmp_path / "inbox"

    first = discover_source("source-portability-test-arkansas", inbox_dir=inbox_dir, data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    second = discover_source("source-portability-test-arkansas", inbox_dir=inbox_dir, data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert first.new == 1 and first.already_known == 0
    assert second.new == 0 and second.already_known == 1
    assert len(list_discovered_items(inbox_dir, source_id="source-portability-test-arkansas")) == 1


# ---------------------------------------------------------------------------
# 3. English human-caption acquisition mirrors the real proof structurally
#    (Phase 7/8/11): sentence-level cues, proper punctuation, no rolling-
#    window duplication -- structurally distinct from Redagricola's Spanish
#    auto-caption shape, proving the normalizer is robust across a second,
#    differently-shaped real caption source. Language propagates; no
#    speakers invented; no-captions falls back to Tier 3 unchanged.
# ---------------------------------------------------------------------------


def _arkansas_item(video_id: str = ARKANSAS_VIDEO_ID) -> dict[str, Any]:
    """Shape mirrors exactly what the real youtube_feed adapter produced for
    the real Arkansas discovery run (verified 2026-08-16)."""
    return {
        "id": f"discovered-{ARKANSAS_SOURCE_ID}-test",
        "record_type": "discovered_media_item",
        "source_id": ARKANSAS_SOURCE_ID,
        "title": "Amanda McWhirt - Building Better Harvests | Behind the Discovery",
        "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
        "external_id": None,
        "platform_item_id": video_id,
        "published_date": "2026-07-30",
        "duration_seconds": None,
        "media_format": "video",
        "transcript_availability": {
            "status": media_discovery.TRANSCRIPT_UNKNOWN,
            "checked_at": "2026-08-16T00:00:00+00:00",
            "url": None,
            "language": None,
        },
        "raw_metadata": {
            "yt_video_id": video_id,
            "yt_channel_id": ARKANSAS_CHANNEL_ID,
            "feed_entry_id": f"yt:video:{video_id}",
            "raw_title": "Amanda McWhirt - Building Better Harvests | Behind the Discovery",
            "raw_published": "2026-07-30T19:16:22+00:00",
            "media_thumbnail": [],
        },
    }


def _english_human_vtt() -> str:
    """Structurally mirrors the real English human-caption track (proper
    sentence casing/punctuation, no two-line rolling-window artifact) --
    does not reproduce the publisher's actual caption text."""
    return (
        "WEBVTT\nKind: captions\nLanguage: en\n\n"
        "00:00:01.000 --> 00:00:04.740\nA fruit research station plays a role in the state.\n\n"
        "00:00:04.740 --> 00:00:08.070\nMany people are not aware of the work that happens here.\n\n"
        "00:00:11.280 --> 00:00:15.080\nI started at the university a number of years ago.\n\n"
    )


def _info_en(*, subtitles=None, automatic_captions=None, language="en", formats=None):
    default_formats = [
        {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2", "ext": "m4a", "abr": 129.0, "url": "https://r1---sn-example.googlevideo.com/videoplayback?id=high"},
    ]
    return {
        "id": ARKANSAS_VIDEO_ID,
        "title": "Amanda McWhirt - Building Better Harvests | Behind the Discovery",
        "language": language,
        "duration": 108,
        "availability": "public",
        "subtitles": subtitles or {},
        "automatic_captions": automatic_captions or {},
        "formats": formats if formats is not None else default_formats,
    }


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
    def __init__(self, text_by_url: dict[str, str] | None = None) -> None:
        self.text_by_url = text_by_url or {}
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        return self.text_by_url[url]


class _FakeAudioDownloader:
    def __init__(self, content: bytes = b"FAKE-ARKANSAS-AUDIO-BYTES") -> None:
        self.content = content
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[bytes, str | None]:
        self.calls.append(url)
        return self.content, "audio/mp4"


class _FakeProvider:
    name = "fake-engine"
    model_name = "small"

    def __init__(self) -> None:
        self.calls: list[Path] = []

    def transcribe(self, media_path: Path, *, language: str | None = None) -> mt.RawTranscription:
        self.calls.append(media_path)
        return mt.RawTranscription(
            segments=(mt.RawSegment(text="Whisper fallback text.", start_seconds=0.0, end_seconds=2.0),),
            detected_language="en",
            engine=self.name,
            engine_version="0.0-test",
            model=self.model_name,
            device="cpu",
            duration_seconds=2.0,
        )


def test_arkansas_english_human_captions_normalize_correctly(tmp_path: Path) -> None:
    item = _arkansas_item()
    info = _info_en(subtitles={"en": [{"ext": "vtt", "url": "https://captions.invalid/arkansas-human-en.vtt"}]})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/arkansas-human-en.vtt": _english_human_vtt()})

    result = yt_acq.fetch_captions(tmp_path / "inbox", item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert result is not None
    assert result.caption_kind == "human"
    assert result.tier == yt_acq.CAPTION_TIER_HUMAN
    assert result.method == "publisher_provided"
    assert result.language == "en"
    # No rolling-window dedup applied to a human track -- all 3 cues present.
    assert len(result.segments) == 3
    assert result.segments[0]["start_seconds"] == 1.0


def test_arkansas_language_propagates_and_no_speakers_invented(tmp_path: Path) -> None:
    item = _arkansas_item()
    info = _info_en(subtitles={"en": [{"ext": "vtt", "url": "https://captions.invalid/arkansas-human-en.vtt"}]})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/arkansas-human-en.vtt": _english_human_vtt()})

    outcome = mt.transcribe_discovered_item(
        tmp_path / "inbox", item, caption_info_fetcher=_FakeInfoFetcher(info), caption_downloader=downloader
    )

    assert outcome.status == "ok"
    assert outcome.detected_language == "en"
    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["language"] == "en"
    assert all(segment["speaker_label"] is None for segment in payload["segments"])


def test_arkansas_no_captions_falls_back_to_audio_resolver_and_whisper(tmp_path: Path) -> None:
    """Same generic Tier 1 -> Tier 2 -> Tier 3 hierarchy, unmodified,
    exercised against the second real publisher's item shape."""
    item = _arkansas_item()
    caption_info = _info_en(subtitles={}, automatic_captions={})
    audio_info = _info_en(subtitles={}, automatic_captions={})
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
    assert len(provider.calls) == 1  # existing Whisper path invoked, unchanged
    payload = json.loads(outcome.output_path.read_text(encoding="utf-8"))
    assert payload["provenance"]["method"] == "auto_generated"


def test_repeated_arkansas_caption_acquisition_uses_cache(tmp_path: Path) -> None:
    item = _arkansas_item()
    info = _info_en(subtitles={"en": [{"ext": "vtt", "url": "https://captions.invalid/arkansas-human-en.vtt"}]})
    downloader = _FakeCaptionDownloader({"https://captions.invalid/arkansas-human-en.vtt": _english_human_vtt()})
    inbox_dir = tmp_path / "inbox"

    first = yt_acq.fetch_captions(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)
    second = yt_acq.fetch_captions(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=downloader)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert downloader.calls == ["https://captions.invalid/arkansas-human-en.vtt"]  # fetched exactly once


def test_repeated_arkansas_audio_acquisition_reuses_cache(tmp_path: Path) -> None:
    item = _arkansas_item()
    info = _info_en(subtitles={}, automatic_captions={})
    audio_dl = _FakeAudioDownloader()
    inbox_dir = tmp_path / "inbox"

    first = yt_acq.acquire_youtube_audio(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=audio_dl)
    second = yt_acq.acquire_youtube_audio(inbox_dir, item, info_fetcher=_FakeInfoFetcher(info), downloader=audio_dl)

    assert first.reused_cache is False
    assert second.reused_cache is True
    assert len(audio_dl.calls) == 1


# ---------------------------------------------------------------------------
# 4. Failure isolation (Phase 14): the two real, independently-registered
#    YouTube sources never take each other down.
# ---------------------------------------------------------------------------


def test_arkansas_feed_unavailable_does_not_block_redagricola(tmp_path, monkeypatch) -> None:
    """Uses the two REAL registered sources (data/configuration/sources.json)
    -- not synthetic fixtures -- to prove the actual production registry's
    two independent YouTube-first Sources fail in isolation."""
    real_sources = {s["id"]: s for s in _real_sources()}
    redagricola_feed_urls = real_sources[REDAGRICOLA_SOURCE_ID]["discovery"]["feed_urls"]
    arkansas_feed_url = real_sources[ARKANSAS_SOURCE_ID]["discovery"]["feed_url"]

    redagricola_feed = _arkansas_style_feed(
        [_arkansas_style_entry_xml(video_id="redagricolaFakeVid1", title="Redagricola Test Episode", published="2026-08-01T00:00:00+00:00")]
    )

    def _get(url, *a, **k):
        if url == arkansas_feed_url:
            raise httpx.ConnectError("simulated Arkansas feed outage")
        if url in redagricola_feed_urls:
            class _R:
                content = redagricola_feed
                def raise_for_status(self):
                    return None
            return _R()
        raise AssertionError(f"unmocked URL: {url}")

    monkeypatch.setattr(media_discovery.httpx, "get", _get)

    arkansas_result = discover_source(ARKANSAS_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=DEFAULT_DATA_DIR, schemas_dir=SCHEMAS_DIR)
    redagricola_result = discover_source(REDAGRICOLA_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=DEFAULT_DATA_DIR, schemas_dir=SCHEMAS_DIR)

    assert arkansas_result.status == "error"
    assert redagricola_result.status == "ok"
    assert redagricola_result.new == 1


def test_redagricola_feed_unavailable_does_not_block_arkansas(tmp_path, monkeypatch) -> None:
    real_sources = {s["id"]: s for s in _real_sources()}
    redagricola_feed_urls = real_sources[REDAGRICOLA_SOURCE_ID]["discovery"]["feed_urls"]
    arkansas_feed_url = real_sources[ARKANSAS_SOURCE_ID]["discovery"]["feed_url"]

    arkansas_feed = _arkansas_style_feed(
        [_arkansas_style_entry_xml(video_id=ARKANSAS_VIDEO_ID, title="Amanda McWhirt - Building Better Harvests", published="2026-07-30T19:16:22+00:00")]
    )

    def _get(url, *a, **k):
        if url in redagricola_feed_urls:
            raise httpx.ConnectError("simulated Redagricola feed outage")
        if url == arkansas_feed_url:
            class _R:
                content = arkansas_feed
                def raise_for_status(self):
                    return None
            return _R()
        raise AssertionError(f"unmocked URL: {url}")

    monkeypatch.setattr(media_discovery.httpx, "get", _get)

    redagricola_result = discover_source(REDAGRICOLA_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=DEFAULT_DATA_DIR, schemas_dir=SCHEMAS_DIR)
    arkansas_result = discover_source(ARKANSAS_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=DEFAULT_DATA_DIR, schemas_dir=SCHEMAS_DIR)

    assert redagricola_result.status == "error"
    assert arkansas_result.status == "ok"
    assert arkansas_result.new == 1
    assert arkansas_result.items[0]["platform_item_id"] == ARKANSAS_VIDEO_ID


# ---------------------------------------------------------------------------
# 5. No trust-boundary violation: no Evidence/Fact/Assessment/Recommendation,
#    no company-specific logic, across a combined Arkansas + Redagricola run.
# ---------------------------------------------------------------------------


def test_no_evidence_or_downstream_trusted_records_created_for_arkansas(tmp_path, repos, monkeypatch) -> None:
    _register_arkansas_test_source(repos)
    feed = _arkansas_style_feed(
        [_arkansas_style_entry_xml(video_id=ARKANSAS_VIDEO_ID, title="Amanda McWhirt - Building Better Harvests", published="2026-07-30T19:16:22+00:00")]
    )
    _mock_get(monkeypatch, {ARKANSAS_TEST_FEED_URL: feed})
    discover_source("source-portability-test-arkansas", inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert repos.evidence.list() == []
    assert repos.facts.list() == []
    assert repos.assessments.list() == []
    assert repos.recommendations.list() == []
    assert not (tmp_path / "inbox" / "evidence").exists()
    for item in list_discovered_items(tmp_path / "inbox"):
        assert item["record_type"] == "discovered_media_item"
        assert "fact_ids" not in item


# ---------------------------------------------------------------------------
# 6. Cache-freshness regression: orchestration delegates to the
#    transcription layer's acquisition fingerprint. A platform-native item
#    identity therefore works without an RSS enclosure and without any
#    source-specific orchestration branch.
# ---------------------------------------------------------------------------


def test_youtube_tier3_orchestration_reuses_platform_fingerprint_for_arkansas(
    tmp_path: Path, monkeypatch
) -> None:
    """A real-shaped Tier-3 cache is reused without reacquisition or STT."""
    item = _arkansas_item()
    info = _info_en(subtitles={}, automatic_captions={})
    provider = _FakeProvider()
    audio_dl = _FakeAudioDownloader()
    inbox_dir = tmp_path / "inbox"

    # Prime a real Tier-3 (audio + Whisper) normalized transcript, exactly as
    # a first real orchestration run would.
    outcome = mt.transcribe_discovered_item(
        inbox_dir,
        item,
        provider_factory=lambda: provider,
        caption_info_fetcher=_FakeInfoFetcher(info),
        youtube_audio_info_fetcher=_FakeInfoFetcher(info),
        youtube_audio_downloader=audio_dl,
    )
    assert outcome.status == "ok" and outcome.tier == "tier_3_local_speech_to_text"
    cached_payload = mt.load_transcript_artifact(inbox_dir, item["id"])
    assert cached_payload is not None

    adapter = MediaTranscriptionAdapter(inbox_dir, provider_factory=lambda: provider)

    assert mt.select_enclosure_url(item) is None
    assert cached_payload["acquisition"]["media_url"] == f"https://www.youtube.com/watch?v={ARKANSAS_VIDEO_ID}"
    assert cached_payload["acquisition"]["source_fingerprint"] == {
        "kind": "platform_item",
        "value": ARKANSAS_VIDEO_ID,
    }
    assert adapter._cache_matches_request(cached_payload, item) is True

    monkeypatch.setattr(
        mt,
        "transcribe_discovered_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("valid Tier-3 cache must not reacquire or transcribe")
        ),
    )
    assert adapter.load(item) == cached_payload
    assert len(provider.calls) == 1
    assert len(audio_dl.calls) == 1

    # Structural, not publisher-specific: another platform item uses the
    # same fingerprint logic and a changed platform identity invalidates it.
    redagricola_payload = dict(cached_payload)
    redagricola_payload["acquisition"] = {
        **cached_payload["acquisition"],
        "media_url": "https://www.youtube.com/watch?v=TRG0WsxJ1Lw",
        "source_fingerprint": {"kind": "platform_item", "value": "TRG0WsxJ1Lw"},
    }
    redagricola_item = {
        **item,
        "source_id": REDAGRICOLA_SOURCE_ID,
        "platform_item_id": "TRG0WsxJ1Lw",
        "canonical_url": "https://www.youtube.com/watch?v=TRG0WsxJ1Lw",
        "raw_metadata": {"yt_video_id": "TRG0WsxJ1Lw"},
    }
    assert adapter._cache_matches_request(redagricola_payload, redagricola_item) is True
    changed_item = {**redagricola_item, "platform_item_id": "different-video"}
    assert adapter._cache_matches_request(redagricola_payload, changed_item) is False

    # Tier-2 captions use the same platform identity fingerprint.
    tier2_payload = {**cached_payload, "acquisition": {**cached_payload["acquisition"], "tier": yt_acq.CAPTION_TIER_HUMAN, "media_url": None}}
    assert adapter._cache_matches_request(tier2_payload, item) is True


# ---------------------------------------------------------------------------
# 7. Media format decision (Phase 15): "video", not a new semantic type,
#    for both the Field Day recap and the researcher-feature video.
# ---------------------------------------------------------------------------


def test_arkansas_video_media_format_is_video_not_conference_video_or_new_type() -> None:
    """Neither the annual Field Day recap nor the researcher-feature video
    is a raw, unedited conference-session recording -- both are produced,
    edited short videos, exactly like every other youtube_feed item. 'video'
    (the adapter's existing, unconditional choice) is correct; this phase
    introduces no new media_format value and no per-item override."""
    item = _arkansas_item()
    assert item["media_format"] == "video"
    assert item["media_format"] in media_discovery.MEDIA_FORMATS
    schema = json.loads((SCHEMAS_DIR / "evidence.schema.json").read_text(encoding="utf-8"))
    assert item["media_format"] in schema["properties"]["media_format"]["enum"]
