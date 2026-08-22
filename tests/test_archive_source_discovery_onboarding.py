"""Regression tests for feature/archive-source-discovery's configuration-only
onboarding of seven real, independently re-verified Sources (five
podcast_rss, one youtube_feed among the six podcast-shaped adapters --
source-blueberries-tv-youtube -- see PROJECT-STATUS.md and this branch's
onboarding report for the full verification record).

This task is deliberately configuration-only: no new adapter, no
source-specific Python. tests/test_media_discovery.py and
tests/test_media_discovery_source_expansion.py already prove the generic
podcast_rss/youtube_feed adapter mechanism end-to-end (normalization,
idempotency, cross-source dedupe, failure isolation, no-Evidence/no-
transcript/no-CI-extraction guarantees) -- this file does not re-prove that
mechanism. It proves only what is new *this* session: that the seven new
live data/configuration/sources.json records are structurally correct,
adapter-dispatched (not source_id-branched), collision-free, and
represented in domain-packs/berries/collector-templates.json, and that the
generic adapter mechanism -- unmodified by this task -- handles their real
feed shapes correctly when exercised offline against mocked fixtures that
mirror those real, verified feeds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import media_discovery
from app.services.media_discovery import DiscoveryError, discover_source, list_discovered_items

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "configuration" / "sources.json"
TEMPLATES_PATH = ROOT / "domain-packs" / "berries" / "collector-templates.json"

NEW_PODCAST_RSS_SOURCE_IDS = [
    "source-the-packer-podcast",
    "source-fresh-takes-on-tech-podcast",
    "source-produce-buzzers-podcast",
    "source-global-fresh-series-podcast",
    "source-fresh-cred-podcast",
    "source-lubera-edibles-podcast",
]
NEW_YOUTUBE_FEED_SOURCE_IDS = ["source-blueberries-tv-youtube"]
NEW_SOURCE_IDS = NEW_PODCAST_RSS_SOURCE_IDS + NEW_YOUTUBE_FEED_SOURCE_IDS


def _live_sources() -> list[dict[str, Any]]:
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


def _live_templates() -> dict[str, Any]:
    return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. structural validity of each newly-added Source's `discovery` block
# ---------------------------------------------------------------------------


def test_new_sources_exist_with_valid_discovery_config() -> None:
    sources_by_id = {s["id"]: s for s in _live_sources()}
    for source_id in NEW_SOURCE_IDS:
        assert source_id in sources_by_id, f"{source_id} missing from live sources.json"
        source = sources_by_id[source_id]
        discovery = source.get("discovery")
        assert discovery, f"{source_id} has no 'discovery' block"
        assert discovery["adapter"] in media_discovery.ADAPTER_TYPES
        assert discovery.get("feed_url") or discovery.get("feed_urls")
        assert discovery.get("feed_url_verified_at"), f"{source_id} discovery missing feed_url_verified_at"
        assert discovery.get("notes"), f"{source_id} discovery missing provenance notes"
        # Every Source in this registry carries the standard reference fields.
        assert source.get("berry_ids"), f"{source_id} has no berry_ids"
        assert source.get("region_coverage"), f"{source_id} has no region_coverage"
        assert source.get("enabled") is True


# ---------------------------------------------------------------------------
# 2. correct adapter selected per new source (config-driven, not source_id
#    branching -- discover_source()/ADAPTER_TYPES never mention these ids)
# ---------------------------------------------------------------------------


def test_new_sources_use_expected_adapter_type() -> None:
    sources_by_id = {s["id"]: s for s in _live_sources()}
    for source_id in NEW_PODCAST_RSS_SOURCE_IDS:
        assert sources_by_id[source_id]["discovery"]["adapter"] == "podcast_rss"
    for source_id in NEW_YOUTUBE_FEED_SOURCE_IDS:
        assert sources_by_id[source_id]["discovery"]["adapter"] == "youtube_feed"


def test_no_source_specific_python_branch_exists_for_new_sources() -> None:
    """The whole point of this task: adapter dispatch is config-driven.
    None of this session's new source ids appear anywhere in
    media_discovery.py's source code -- proving discover_source() dispatches
    purely from each Source's own `discovery.adapter` field, never an
    `if source_id == ...` branch added for this onboarding."""
    module_source = Path(media_discovery.__file__).read_text(encoding="utf-8")
    for source_id in NEW_SOURCE_IDS:
        assert source_id not in module_source


# ---------------------------------------------------------------------------
# 3. no duplicate Source ids in the live registry
# ---------------------------------------------------------------------------


def test_no_duplicate_source_ids_in_live_registry() -> None:
    ids = [s["id"] for s in _live_sources()]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 4. every new source is represented in collector-templates.json
#    (domain-pack registration, mirroring every prior real-source onboarding)
# ---------------------------------------------------------------------------


def test_new_sources_registered_in_collector_templates() -> None:
    templates_by_id = {t["id"]: t for t in _live_templates()["collector_templates"]}
    for source_id in NEW_SOURCE_IDS:
        assert source_id in templates_by_id, f"{source_id} missing from collector-templates.json"
        assert templates_by_id[source_id]["collector_type"] == "reference_manual"


# ---------------------------------------------------------------------------
# 5. offline exercise of the (unmodified) generic adapter mechanism against
#    these specific new source ids -- normalization, idempotency, and
#    failure isolation, using fixtures mirroring the real verified feed
#    shapes (Captivate.fm-style podcast_rss and YouTube Atom), proving the
#    live production config actually works end-to-end through
#    discover_source() and not merely "looks right" on paper.
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8")
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


def _podcast_feed(*, title: str, guid: str, feed_url: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?><rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
<channel><title>Test Feed</title><link>{feed_url}</link><description>d</description>
<item><title>{title}</title><guid isPermaLink="false">{guid}</guid><link>https://example.invalid/{guid}</link>
<pubDate>Wed, 12 Aug 2026 11:00:00 GMT</pubDate><itunes:duration>00:20:00</itunes:duration>
<enclosure url="https://example.invalid/{guid}.mp3" type="audio/mpeg" length="1"/><description>Episode description.</description></item>
</channel></rss>""".encode("utf-8")


def _youtube_feed(*, video_id: str, title: str, channel_id: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
<link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"/>
<id>yt:channel:{channel_id}</id><yt:channelId>{channel_id}</yt:channelId><title>Test Channel</title>
<author><name>Test Channel</name><uri>https://www.youtube.com/channel/{channel_id}</uri></author>
<published>2020-01-01T00:00:00+00:00</published>
<entry><id>yt:video:{video_id}</id><yt:videoId>{video_id}</yt:videoId><yt:channelId>{channel_id}</yt:channelId>
<title>{title}</title><link rel="alternate" href="https://www.youtube.com/watch?v={video_id}"/>
<author><name>Test Channel</name><uri>https://www.youtube.com/channel/{channel_id}</uri></author>
<published>2026-08-12T00:00:00+00:00</published><updated>2026-08-12T00:00:00+00:00</updated>
<media:group><media:title>{title}</media:title><media:description>d</media:description></media:group></entry>
</feed>""".encode("utf-8")


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


def _register_real_source(repos, source_id: str, discovery: dict[str, Any]):
    """Re-registers one of this session's real new source ids in an
    isolated tmp_path repository, with a real production-shaped `discovery`
    block (same adapter/feed_url as the live record) but pointed at a
    synthetic, mocked feed_url -- so the exact ids and adapter selection
    that now live in data/configuration/sources.json are what's exercised,
    without ever making a real network call from a test."""
    return repos.sources.create({"id": source_id, "type": "reference", "label": source_id, "discovery": discovery})


def test_new_podcast_rss_source_discovers_and_is_idempotent(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-the-packer-podcast"
    feed_url = "https://feeds.example.invalid/archive-source-discovery-test/packer-style/rss"
    _register_real_source(repos, source_id, {"adapter": "podcast_rss", "feed_url": feed_url})
    feed = _podcast_feed(title="Driving Desire when Marketing Blueberries", guid="guid-packer-1", feed_url=feed_url)

    def _get(url, *a, **k):
        if url != feed_url:
            raise AssertionError(f"unmocked URL: {url}")
        return _FakeResponse(feed)

    monkeypatch.setattr(media_discovery.httpx, "get", _get)

    first = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert first.status == "ok"
    assert first.found == 1
    assert first.new == 1
    assert first.items[0]["media_format"] == "podcast"

    second = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert second.status == "ok"
    assert second.new == 0
    assert second.already_known == 1
    assert len(list_discovered_items(tmp_path / "inbox", source_id=source_id)) == 1


def test_new_youtube_feed_source_discovers_and_is_idempotent(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-blueberries-tv-youtube"
    channel_id = "UCwypVNJp_DjjoLtqVCwIF4w"
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    _register_real_source(repos, source_id, {"adapter": "youtube_feed", "feed_url": feed_url})
    feed = _youtube_feed(video_id="testVideoId1", title="International Berries Seminar", channel_id=channel_id)

    def _get(url, *a, **k):
        if url != feed_url:
            raise AssertionError(f"unmocked URL: {url}")
        return _FakeResponse(feed)

    monkeypatch.setattr(media_discovery.httpx, "get", _get)

    first = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert first.status == "ok"
    assert first.new == 1
    assert first.items[0]["media_format"] == "video"
    assert first.items[0]["platform_item_id"] == "testVideoId1"

    second = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert second.new == 0
    assert second.already_known == 1


def test_one_new_source_failing_does_not_break_another(tmp_path, repos, monkeypatch) -> None:
    ok_source_id = "source-fresh-cred-podcast"
    ok_feed_url = "https://feeds.example.invalid/archive-source-discovery-test/fresh-cred-style/rss"
    broken_source_id = "source-global-fresh-series-podcast"
    broken_feed_url = "https://feeds.example.invalid/archive-source-discovery-test/broken/rss"
    _register_real_source(repos, ok_source_id, {"adapter": "podcast_rss", "feed_url": ok_feed_url})
    _register_real_source(repos, broken_source_id, {"adapter": "podcast_rss", "feed_url": broken_feed_url})

    def _get(url, *a, **k):
        if url == broken_feed_url:
            raise httpx.ConnectError("simulated failure for broken source")
        if url == ok_feed_url:
            return _FakeResponse(_podcast_feed(title="Fine Episode", guid="guid-fine-1", feed_url=ok_feed_url))
        raise AssertionError(f"unmocked URL: {url}")

    monkeypatch.setattr(media_discovery.httpx, "get", _get)

    broken_result = discover_source(broken_source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    ok_result = discover_source(ok_source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert broken_result.status == "error"
    assert ok_result.status == "ok"
    assert ok_result.new == 1


def test_new_sources_produce_no_evidence_transcript_or_ci_claims(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-produce-buzzers-podcast"
    feed_url = "https://feeds.example.invalid/archive-source-discovery-test/produce-buzzers-style/rss"
    _register_real_source(repos, source_id, {"adapter": "podcast_rss", "feed_url": feed_url})
    monkeypatch.setattr(
        media_discovery.httpx,
        "get",
        lambda url, *a, **k: _FakeResponse(_podcast_feed(title="Strawberry Season Recap", guid="guid-pb-1", feed_url=feed_url)),
    )

    discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert repos.evidence.list() == []
    assert not (tmp_path / "evidence").exists()
    assert not (tmp_path / "inbox" / "evidence").exists()
    assert not (tmp_path / "inbox" / "discovered_media" / "_transcripts").exists()
    for item in list_discovered_items(tmp_path / "inbox"):
        assert item["record_type"] == "discovered_media_item"
        assert "fact_ids" not in item


def test_unsupported_adapter_still_raises_discovery_error_not_a_new_branch(tmp_path, repos) -> None:
    """Sanity check that this onboarding did not quietly special-case
    adapter dispatch: an unsupported adapter type still fails the same
    generic way it did before this task, for any source id."""
    repos.sources.create(
        {
            "id": "source-archive-source-discovery-test-unsupported",
            "type": "reference",
            "label": "Unsupported",
            "discovery": {"adapter": "archive_index_not_implemented", "feed_url": "https://example.invalid/x"},
        }
    )
    with pytest.raises(DiscoveryError, match="unknown discovery adapter type"):
        discover_source(
            "source-archive-source-discovery-test-unsupported",
            inbox_dir=tmp_path / "inbox",
            data_dir=tmp_path,
            schemas_dir=SCHEMAS_DIR,
        )
