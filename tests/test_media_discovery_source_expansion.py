"""Source-expansion regression tests (feature/spoken-word-source-expansion).

Companion to tests/test_media_discovery.py, which already proves the
generic podcast_rss adapter mechanism end-to-end against a synthetic feed.
This file adds coverage this phase's real-publisher onboarding work
specifically introduced or exercised for the first time:

  * A second, structurally different real podcast_rss publisher shape
    (Captivate.fm, as actually served by The Business of Blueberries'
    real feed -- MM:SS itunes:duration, a channel-level <link> repeated on
    every item rather than a per-episode canonical URL, a timezone-offset
    <pubDate>) discovered with the *same* adapter code, zero changes.
  * The new youtube_feed adapter (a public YouTube channel/playlist Atom
    feed, as actually served by Redagricola's real "On The Road TV"
    playlists), including its platform_item_id-first dedupe identity and
    its honest TRANSCRIPT_UNKNOWN caption-availability reporting.
  * discover_source()'s new `feed_urls` (plural) support, added because
    Redagricola's "On The Road" resolves to two independent per-country
    playlists with no single combined feed.
  * Cross-publisher, cross-adapter-type dedupe/failure-isolation
    guarantees: identical titles from different sources/adapters never
    collide; one failing source (or one failing feed within a
    multi-feed_urls source) never breaks discovery for anything else.
  * scripts/discover_media.py's new `--all` flag.

Entirely offline, same convention as tests/test_media_discovery.py: every
network call is mocked via `monkeypatch.setattr(media_discovery.httpx,
"get", ...)`. No test touches the live data/ dataset or the live
data/configuration/sources.json registry -- every fixture is built through
get_repositories() pointed at tmp_path.

Feed fixtures mirror the real, verified structural shape of the actual
public feeds this phase onboarded (see this module's companion report /
data/configuration/sources.json's `discovery.notes` on
source-business-of-blueberries-podcast and source-redagricola-on-the-road
for exactly how and when each was verified) -- not invented shapes.
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
from app.services.media_discovery import (
    DEDUPE_STRATEGY_PLATFORM_ID,
    DiscoveryError,
    TRANSCRIPT_NOT_DETECTED,
    TRANSCRIPT_UNKNOWN,
    discover_source,
    list_discovered_items,
)

import scripts.discover_media as discover_media_cli


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8")
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


# ---------------------------------------------------------------------------
# fixture builders -- Captivate.fm-shaped podcast_rss feed (Business of
# Blueberries' real host), structurally distinct from Anchor/Spotify-for-
# Podcasters (Lucentlands' real host, see tests/test_media_discovery.py)
# ---------------------------------------------------------------------------


def _captivate_item_xml(
    *,
    title: str,
    guid: str,
    channel_link: str = "https://blueberries.captivate.fm",
    pub_date: str = "Fri, 31 Jul 2026 13:00:00 -0700",
    duration: str = "43:49",  # MM:SS, not Lucentlands' HH:MM:SS
    description: str = "Episode description.",
    enclosure_url: str | None = None,
) -> str:
    enclosure_url = enclosure_url or f"https://episodes.captivate.fm/episode/{guid}.mp3"
    return f"""
<item>
<title>{title}</title>
<guid isPermaLink="false">{guid}</guid>
<link><![CDATA[{channel_link}]]></link>
<pubDate>{pub_date}</pubDate>
<enclosure url="{enclosure_url}" length="63011345" type="audio/mpeg"/>
<itunes:duration>{duration}</itunes:duration>
<description>{description}</description>
</item>"""


def _captivate_feed(items: list[str]) -> bytes:
    body = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?><rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" version="2.0">
<channel>
<title>The Business of Blueberries (Test Fixture)</title>
<generator>Captivate.fm</generator>
<link>https://blueberries.captivate.fm</link>
<description>Test fixture mirroring the real Captivate.fm feed shape.</description>
{body}
</channel>
</rss>""".encode("utf-8")


# ---------------------------------------------------------------------------
# fixture builders -- YouTube channel/playlist Atom feed (Redagricola's
# real "On The Road TV" shape)
# ---------------------------------------------------------------------------


def _youtube_entry_xml(
    *,
    video_id: str,
    title: str,
    channel_id: str = "UCTestChannelId0000000000",
    published: str = "2026-08-11T01:00:36+00:00",
    description: str = "Video description.",
) -> str:
    return f"""
<entry>
<id>yt:video:{video_id}</id>
<yt:videoId>{video_id}</yt:videoId>
<yt:channelId>{channel_id}</yt:channelId>
<title>{title}</title>
<link rel="alternate" href="https://www.youtube.com/watch?v={video_id}"/>
<author><name>Test Channel</name><uri>https://www.youtube.com/channel/{channel_id}</uri></author>
<published>{published}</published>
<updated>{published}</updated>
<media:group>
<media:title>{title}</media:title>
<media:thumbnail url="https://i1.ytimg.com/vi/{video_id}/hqdefault.jpg" width="480" height="360"/>
<media:description>{description}</media:description>
</media:group>
</entry>"""


def _youtube_feed(entries: list[str], channel_id: str = "UCTestChannelId0000000000") -> bytes:
    body = "\n".join(entries)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
<link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"/>
<id>yt:channel:{channel_id}</id>
<yt:channelId>{channel_id}</yt:channelId>
<title>Test YouTube Channel</title>
<link rel="alternate" href="https://www.youtube.com/channel/{channel_id}"/>
<author><name>Test Channel</name><uri>https://www.youtube.com/channel/{channel_id}</uri></author>
<published>2020-01-01T00:00:00+00:00</published>
{body}
</feed>""".encode("utf-8")


def _mock_get(monkeypatch, routes: dict[str, bytes]) -> None:
    """Route httpx.get(url) -> _FakeResponse(routes[url]) for exact-match
    URLs; raises for anything unrouted so a test can't accidentally depend
    on a real network call it forgot to mock."""

    def _get(url, *a, **k):
        if url not in routes:
            raise AssertionError(f"unmocked URL in test: {url}")
        return _FakeResponse(routes[url])

    monkeypatch.setattr(media_discovery.httpx, "get", _get)


BOB_SOURCE_ID = "source-media-discovery-test-bob-style"
BOB_FEED_URL = "https://feeds.example.invalid/bob-style/rss"
YT_SOURCE_ID = "source-media-discovery-test-youtube"
YT_FEED_URL_A = "https://www.youtube.com/feeds/videos.xml?playlist_id=TESTPLAYLISTA"
YT_FEED_URL_B = "https://www.youtube.com/feeds/videos.xml?playlist_id=TESTPLAYLISTB"


def _bob_source(repos):
    return repos.sources.create(
        {
            "id": BOB_SOURCE_ID,
            "type": "reference",
            "label": "Captivate-style Test Podcast",
            "discovery": {"adapter": "podcast_rss", "feed_url": BOB_FEED_URL},
        }
    )


def _youtube_source(repos, *, feed_urls: list[str] | None = None, feed_url: str | None = None):
    discovery: dict[str, Any] = {"adapter": "youtube_feed"}
    if feed_urls is not None:
        discovery["feed_urls"] = feed_urls
    if feed_url is not None:
        discovery["feed_url"] = feed_url
    return repos.sources.create(
        {
            "id": YT_SOURCE_ID,
            "type": "reference",
            "label": "Test YouTube Series",
            "discovery": discovery,
        }
    )


# ---------------------------------------------------------------------------
# 1. Business-of-Blueberries-shaped (Captivate.fm) feed discovers correctly
# ---------------------------------------------------------------------------


def test_captivate_style_feed_discovers_correctly(tmp_path, repos, monkeypatch) -> None:
    _bob_source(repos)
    feed = _captivate_feed(
        [
            _captivate_item_xml(title="How Region X Is Preparing For The Season", guid="guid-bob-1"),
            _captivate_item_xml(title="Crop Report Roundup", guid="guid-bob-2", duration="1:05:30"),
        ]
    )
    _mock_get(monkeypatch, {BOB_FEED_URL: feed})
    result = discover_source(BOB_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "ok"
    assert result.found == 2
    assert result.new == 2
    assert not result.item_failures
    by_title = {item["title"]: item for item in result.items}
    # MM:SS duration parses correctly (43:49 -> 2629s), same generic parser
    # used for Lucentlands' HH:MM:SS -- no adapter code change required.
    assert by_title["How Region X Is Preparing For The Season"]["duration_seconds"] == 43 * 60 + 49
    # H:MM:SS (single-digit hour) also parses correctly.
    assert by_title["Crop Report Roundup"]["duration_seconds"] == 1 * 3600 + 5 * 60 + 30
    assert by_title["How Region X Is Preparing For The Season"]["media_format"] == "podcast"
    # A channel-level <link> repeated on every item (Captivate's real shape,
    # unlike Anchor's per-episode canonical URL) is still accepted as-is --
    # this module makes no assumption that <link> is per-episode.
    assert by_title["How Region X Is Preparing For The Season"]["canonical_url"] == "https://blueberries.captivate.fm"
    # GUID dedupe still wins regardless, so the shared <link> never causes
    # a collision between these two distinct episodes.
    assert result.items[0]["dedupe_strategy"] == "guid"


def test_captivate_style_and_anchor_style_feeds_both_handled_by_same_adapter_code(tmp_path, repos, monkeypatch) -> None:
    """Different RSS hosts/generators (Anchor vs Captivate.fm), same
    podcast_rss adapter, zero code branching -- the core Phase 5 claim,
    proven offline/regression-safe rather than only via the one-time real
    discovery run documented in this phase's report."""
    _bob_source(repos)
    anchor_source_id = "source-media-discovery-test-anchor-style"
    anchor_feed_url = "https://feeds.example.invalid/anchor-style/rss"
    repos.sources.create(
        {
            "id": anchor_source_id,
            "type": "reference",
            "label": "Anchor-style Test Podcast",
            "discovery": {"adapter": "podcast_rss", "feed_url": anchor_feed_url},
        }
    )
    anchor_feed = f"""<?xml version="1.0" encoding="UTF-8"?><rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
<channel><title>Anchor-style Feed</title><generator>Anchor Podcasts</generator><link>https://example.invalid/</link><description>d</description>
<item><title>Anchor Episode</title><guid isPermaLink="false">anchor-guid-1</guid><link>https://example.invalid/anchor-ep1</link>
<pubDate>Wed, 28 Oct 2025 07:00:00 GMT</pubDate><itunes:duration>00:39:05</itunes:duration>
<enclosure url="https://example.invalid/anchor-ep1.mp3" type="audio/mpeg" length="1"/><description>d</description></item>
</channel></rss>""".encode("utf-8")

    _mock_get(
        monkeypatch,
        {
            BOB_FEED_URL: _captivate_feed([_captivate_item_xml(title="Captivate Episode", guid="guid-bob-1")]),
            anchor_feed_url: anchor_feed,
        },
    )

    bob_result = discover_source(BOB_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    anchor_result = discover_source(anchor_source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert bob_result.status == "ok" and bob_result.new == 1
    assert anchor_result.status == "ok" and anchor_result.new == 1
    assert bob_result.items[0]["media_format"] == "podcast"
    assert anchor_result.items[0]["media_format"] == "podcast"


# ---------------------------------------------------------------------------
# 2. youtube_feed adapter: discovers correctly, video-id-first identity,
#    canonical URL, video classification, honest caption-availability
# ---------------------------------------------------------------------------


def test_youtube_feed_discovers_correctly(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    feed = _youtube_feed(
        [
            _youtube_entry_xml(video_id="videoAAAAAA", title="Grower Interview One"),
            _youtube_entry_xml(video_id="videoBBBBBB", title="Grower Interview Two"),
        ]
    )
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed})
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "ok"
    assert result.found == 2
    assert result.new == 2
    assert not result.item_failures
    for item in result.items:
        assert item["source_id"] == YT_SOURCE_ID
        assert item["record_type"] == "discovered_media_item"


def test_youtube_video_id_is_stable_platform_identity(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    feed = _youtube_feed([_youtube_entry_xml(video_id="stableVideoId1", title="Some Title")])
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed})
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    item = result.items[0]
    assert item["platform_item_id"] == "stableVideoId1"
    assert item["external_id"] is None
    assert item["dedupe_strategy"] == DEDUPE_STRATEGY_PLATFORM_ID
    assert item["dedupe_key"] == "stableVideoId1"


def test_youtube_canonical_video_url_normalized(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    feed = _youtube_feed([_youtube_entry_xml(video_id="canonUrlTest1", title="Some Title")])
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed})
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert result.items[0]["canonical_url"] == "https://www.youtube.com/watch?v=canonUrlTest1"


def test_youtube_media_format_is_video_not_a_new_semantic_type(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    feed = _youtube_feed([_youtube_entry_xml(video_id="formatTest1", title="Some Title")])
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed})
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert result.items[0]["media_format"] == "video"
    assert result.items[0]["media_format"] in media_discovery.MEDIA_FORMATS


def test_youtube_caption_availability_reported_as_unknown_not_confused_with_trusted_transcript(tmp_path, repos, monkeypatch) -> None:
    """The public YouTube Atom feed carries no caption signal at all --
    reporting TRANSCRIPT_NOT_DETECTED (a claim that absence was verified)
    would be dishonest. TRANSCRIPT_UNKNOWN is the only correct answer, and
    must never be confusable with a genuine publisher/trusted transcript
    status."""
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    feed = _youtube_feed([_youtube_entry_xml(video_id="captionTest1", title="Some Title")])
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed})
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    availability = result.items[0]["transcript_availability"]
    assert availability["status"] == TRANSCRIPT_UNKNOWN
    assert availability["status"] != TRANSCRIPT_NOT_DETECTED
    assert availability["url"] is None


def test_youtube_duration_not_exposed_degrades_to_none(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    feed = _youtube_feed([_youtube_entry_xml(video_id="durationTest1", title="Some Title")])
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed})
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert result.items[0]["duration_seconds"] is None


# ---------------------------------------------------------------------------
# 3. discover_source() feed_urls (plural) support
# ---------------------------------------------------------------------------


def test_multiple_feed_urls_are_combined_into_one_source_result(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_urls=[YT_FEED_URL_A, YT_FEED_URL_B])
    feed_a = _youtube_feed([_youtube_entry_xml(video_id="fromPlaylistA1", title="Peru Episode")])
    feed_b = _youtube_feed([_youtube_entry_xml(video_id="fromPlaylistB1", title="Chile Episode")])
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed_a, YT_FEED_URL_B: feed_b})

    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert result.status == "ok"
    assert result.found == 2
    assert result.new == 2
    assert not result.feed_failures
    video_ids = {item["platform_item_id"] for item in result.items}
    assert video_ids == {"fromPlaylistA1", "fromPlaylistB1"}


def test_one_feed_url_failing_does_not_fail_the_whole_source_when_another_succeeds(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_urls=[YT_FEED_URL_A, YT_FEED_URL_B])

    def _get(url, *a, **k):
        if url == YT_FEED_URL_A:
            raise httpx.ConnectError("simulated network failure for playlist A")
        return _FakeResponse(_youtube_feed([_youtube_entry_xml(video_id="fromPlaylistB1", title="Chile Episode")]))

    monkeypatch.setattr(media_discovery.httpx, "get", _get)
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "ok"
    assert result.found == 1
    assert result.new == 1
    assert len(result.feed_failures) == 1
    assert result.feed_failures[0]["feed_url"] == YT_FEED_URL_A
    assert "simulated network failure" in result.feed_failures[0]["error"]


def test_all_feed_urls_failing_is_a_whole_source_error(tmp_path, repos, monkeypatch) -> None:
    _youtube_source(repos, feed_urls=[YT_FEED_URL_A, YT_FEED_URL_B])

    def _raise(*a, **k):
        raise httpx.ConnectError("simulated total outage")

    monkeypatch.setattr(media_discovery.httpx, "get", _raise)
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "error"
    assert "simulated total outage" in result.error
    assert len(result.feed_failures) == 2
    assert list_discovered_items(tmp_path / "inbox", source_id=YT_SOURCE_ID) == []


def test_single_feed_url_backward_compatible_with_feed_urls_plural_field_absent(tmp_path, repos, monkeypatch) -> None:
    """Every existing single-feed_url source (Lucentlands, Business of
    Blueberries) must keep working through the exact same code path,
    unaffected by feed_urls (plural) existing as an option."""
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    feed = _youtube_feed([_youtube_entry_xml(video_id="singleFeedTest1", title="Some Title")])
    _mock_get(monkeypatch, {YT_FEED_URL_A: feed})
    result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert result.status == "ok"
    assert result.new == 1
    assert result.feed_failures == []


# ---------------------------------------------------------------------------
# 4. cross-publisher / cross-adapter-type dedupe and failure isolation
# ---------------------------------------------------------------------------


def test_identical_titles_from_different_sources_do_not_collide(tmp_path, repos, monkeypatch) -> None:
    _bob_source(repos)
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    shared_title = "Blueberry Market Outlook"
    _mock_get(
        monkeypatch,
        {
            BOB_FEED_URL: _captivate_feed([_captivate_item_xml(title=shared_title, guid="guid-shared-title-podcast")]),
            YT_FEED_URL_A: _youtube_feed([_youtube_entry_xml(video_id="sharedTitleVideo1", title=shared_title)]),
        },
    )
    bob_result = discover_source(BOB_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    yt_result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert bob_result.items[0]["id"] != yt_result.items[0]["id"]
    all_items = list_discovered_items(tmp_path / "inbox")
    assert len(all_items) == 2
    assert len({item["id"] for item in all_items}) == 2


def test_malformed_source_does_not_break_other_sources_in_sequential_runs(tmp_path, repos, monkeypatch) -> None:
    _bob_source(repos)
    broken_source_id = "source-media-discovery-test-broken"
    broken_feed_url = "https://feeds.example.invalid/broken/rss"
    repos.sources.create(
        {
            "id": broken_source_id,
            "type": "reference",
            "label": "Broken Test Source",
            "discovery": {"adapter": "podcast_rss", "feed_url": broken_feed_url},
        }
    )

    def _get(url, *a, **k):
        if url == broken_feed_url:
            raise httpx.ConnectError("simulated broken source")
        if url == BOB_FEED_URL:
            return _FakeResponse(_captivate_feed([_captivate_item_xml(title="Fine Episode", guid="guid-fine-1")]))
        raise AssertionError(f"unmocked URL: {url}")

    monkeypatch.setattr(media_discovery.httpx, "get", _get)

    broken_result = discover_source(broken_source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    bob_result = discover_source(BOB_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert broken_result.status == "error"
    assert bob_result.status == "ok"
    assert bob_result.new == 1


def test_unsupported_adapter_type_fails_clearly(tmp_path, repos) -> None:
    repos.sources.create(
        {
            "id": "source-media-discovery-test-unsupported-adapter",
            "type": "reference",
            "label": "Unsupported Adapter Source",
            "discovery": {"adapter": "some_future_adapter_not_yet_built", "feed_url": "https://example.invalid/whatever"},
        }
    )
    with pytest.raises(DiscoveryError, match="unknown discovery adapter type"):
        discover_source(
            "source-media-discovery-test-unsupported-adapter",
            inbox_dir=tmp_path / "inbox",
            data_dir=tmp_path,
            schemas_dir=SCHEMAS_DIR,
        )


def test_sitemap_xml_discovers_only_configured_recent_article_urls(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-sitemap-test"
    feed_url = "https://publisher.example.invalid/news-sitemap.xml"
    repos.sources.create(
        {
            "id": source_id,
            "type": "reference",
            "label": "Publisher newsroom",
            "discovery": {
                "adapter": "sitemap_xml",
                "feed_url": feed_url,
                "include_url_patterns": [r"/news/"],
                "exclude_url_patterns": [r"/news/tag/"],
                "sort": "published_desc",
                "item_limit": 2,
            },
        }
    )
    sitemap = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://publisher.example.invalid/about</loc><lastmod>2026-08-24</lastmod></url>
  <url><loc>https://publisher.example.invalid/news/older-story</loc><lastmod>2026-07-01</lastmod></url>
  <url><loc>https://publisher.example.invalid/news/tag/berries</loc><lastmod>2026-08-23</lastmod></url>
  <url><loc>https://publisher.example.invalid/news/newest-story</loc><lastmod>2026-08-22T10:00:00+00:00</lastmod></url>
  <url><loc>https://publisher.example.invalid/news/middle-story</loc><lastmod>2026-08-01</lastmod></url>
  <url><loc>https://publisher.example.invalid/news/corrupt-future-story</loc><lastmod>8842-08-23</lastmod></url>
</urlset>"""
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *args, **kwargs: _FakeResponse(sitemap))

    result = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "ok"
    assert result.found == 6
    assert result.new == 2
    assert [item["canonical_url"] for item in result.items] == [
        "https://publisher.example.invalid/news/newest-story",
        "https://publisher.example.invalid/news/middle-story",
    ]
    assert result.items[0]["published_date"] == "2026-08-22"
    assert result.items[0]["dedupe_strategy"] == "canonical_url"
    assert all("corrupt-future-story" not in item["canonical_url"] for item in result.items)


def test_sitemap_xml_rejects_index_documents_without_following_them(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-sitemap-index-test"
    feed_url = "https://publisher.example.invalid/sitemap.xml"
    repos.sources.create(
        {"id": source_id, "type": "reference", "label": "Index", "discovery": {"adapter": "sitemap_xml", "feed_url": feed_url}}
    )
    index = b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://publisher.example.invalid/news-sitemap.xml</loc></sitemap>
    </sitemapindex>"""
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *args, **kwargs: _FakeResponse(index))

    result = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "error"
    assert "leaf <urlset>" in (result.error or "")
    assert list_discovered_items(tmp_path / "inbox", source_id=source_id) == []


def test_discovery_item_limit_must_be_positive_integer(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-bad-limit-test"
    feed_url = "https://publisher.example.invalid/feed.xml"
    repos.sources.create(
        {"id": source_id, "type": "reference", "label": "Bad limit", "discovery": {"adapter": "article_rss", "feed_url": feed_url, "item_limit": 0}}
    )
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *args, **kwargs: _FakeResponse(_captivate_feed([])))

    with pytest.raises(DiscoveryError, match="positive integer"):
        discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)


def test_source_config_drives_adapter_selection_not_source_id(tmp_path, repos, monkeypatch) -> None:
    """The exact same discover_source() call, differing only in what a
    Source's own 'discovery.adapter' field says, produces a podcast item
    for one source and a video item for another -- proving dispatch is
    config-driven, not `if source_id == ...`."""
    _bob_source(repos)
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    _mock_get(
        monkeypatch,
        {
            BOB_FEED_URL: _captivate_feed([_captivate_item_xml(title="Podcast Item", guid="guid-dispatch-1")]),
            YT_FEED_URL_A: _youtube_feed([_youtube_entry_xml(video_id="dispatchVideo1", title="Video Item")]),
        },
    )
    bob_result = discover_source(BOB_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    yt_result = discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    assert bob_result.items[0]["media_format"] == "podcast"
    assert yt_result.items[0]["media_format"] == "video"


def test_no_evidence_transcript_or_ci_claims_produced_across_both_adapters(tmp_path, repos, monkeypatch) -> None:
    _bob_source(repos)
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    _mock_get(
        monkeypatch,
        {
            BOB_FEED_URL: _captivate_feed([_captivate_item_xml(title="Podcast Item", guid="guid-notrust-1")]),
            YT_FEED_URL_A: _youtube_feed([_youtube_entry_xml(video_id="notrustVideo1", title="Video Item")]),
        },
    )
    discover_source(BOB_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    discover_source(YT_SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert repos.evidence.list() == []
    assert not (tmp_path / "evidence").exists()
    assert not (tmp_path / "inbox" / "evidence").exists()
    assert not (tmp_path / "inbox" / "discovered_media" / "_transcripts").exists()
    for item in list_discovered_items(tmp_path / "inbox"):
        assert item["record_type"] == "discovered_media_item"
        assert "fact_ids" not in item
        assert "evidence" not in item["id"]


# ---------------------------------------------------------------------------
# 5. scripts/discover_media.py --all
# ---------------------------------------------------------------------------


def test_cli_all_flag_runs_every_source_with_a_discovery_block(tmp_path, repos, monkeypatch, capsys) -> None:
    _bob_source(repos)
    _youtube_source(repos, feed_url=YT_FEED_URL_A)
    # A reference source with no discovery block at all -- must be silently
    # skipped by --all, not reported as a failure.
    repos.sources.create({"id": "source-media-discovery-test-manual-only", "type": "reference", "label": "Manual Only"})

    _mock_get(
        monkeypatch,
        {
            BOB_FEED_URL: _captivate_feed([_captivate_item_xml(title="Podcast Item", guid="guid-cli-1")]),
            YT_FEED_URL_A: _youtube_feed([_youtube_entry_xml(video_id="cliVideo1", title="Video Item")]),
        },
    )

    exit_code = discover_media_cli.main(
        ["--all", "--data-dir", str(tmp_path), "--schemas-dir", str(SCHEMAS_DIR), "--inbox-dir", str(tmp_path / "inbox")]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert BOB_SOURCE_ID in out
    assert YT_SOURCE_ID in out
    assert "source-media-discovery-test-manual-only" not in out


def test_cli_all_flag_one_source_failure_does_not_stop_others(tmp_path, repos, monkeypatch, capsys) -> None:
    _bob_source(repos)
    broken_source_id = "source-media-discovery-test-cli-broken"
    broken_feed_url = "https://feeds.example.invalid/cli-broken/rss"
    repos.sources.create(
        {
            "id": broken_source_id,
            "type": "reference",
            "label": "CLI Broken Source",
            "discovery": {"adapter": "podcast_rss", "feed_url": broken_feed_url},
        }
    )

    def _get(url, *a, **k):
        if url == broken_feed_url:
            raise httpx.ConnectError("simulated cli source failure")
        if url == BOB_FEED_URL:
            return _FakeResponse(_captivate_feed([_captivate_item_xml(title="Still Works", guid="guid-cli-still-works")]))
        raise AssertionError(f"unmocked URL: {url}")

    monkeypatch.setattr(media_discovery.httpx, "get", _get)

    exit_code = discover_media_cli.main(
        ["--all", "--data-dir", str(tmp_path), "--schemas-dir", str(SCHEMAS_DIR), "--inbox-dir", str(tmp_path / "inbox")]
    )
    out = capsys.readouterr().out
    assert exit_code == 1  # overall failure reported...
    assert "simulated cli source failure" in out
    # ...but the other source's success is still fully reported.
    assert BOB_SOURCE_ID in out
    assert "status: ok" in out
    bob_items = list_discovered_items(tmp_path / "inbox", source_id=BOB_SOURCE_ID)
    assert len(bob_items) == 1


def test_cli_all_flag_does_not_write_evidence_or_transcripts(tmp_path, repos, monkeypatch) -> None:
    _bob_source(repos)
    _mock_get(monkeypatch, {BOB_FEED_URL: _captivate_feed([_captivate_item_xml(title="Item", guid="guid-cli-notranscript")])})
    exit_code = discover_media_cli.main(
        ["--all", "--data-dir", str(tmp_path), "--schemas-dir", str(SCHEMAS_DIR), "--inbox-dir", str(tmp_path / "inbox")]
    )
    assert exit_code == 0
    assert repos.evidence.list() == []
    assert not (tmp_path / "inbox" / "discovered_media" / "_transcripts").exists()
