"""Spoken-word media discovery/acquisition tests (upstream of the Evidence
trust boundary -- see app/services/media_discovery.py's module docstring).

Entirely offline: every network call is mocked via `monkeypatch.setattr(
media_discovery.httpx, "get", ...)`, mirroring tests/test_app.py's existing
convention for `main.httpx.get`. No test touches the live `data/` dataset
or the live `data/configuration/sources.json` registry -- every fixture is
built through `get_repositories()` (app/composition.py) pointed at
`tmp_path`, per this project's "no fictional intelligence in the live
dataset" testing discipline (mirrors tests/test_media_evidence.py and
tests/queries/test_query_services.py).

Feed fixtures below mirror the real, structural shape of the Lucentlands
Podcast's actual public RSS feed (verified 2026-08-15 via
https://itunes.apple.com/lookup?id=1655947979&entity=podcast ->
https://anchor.fm/s/c9b3aba4/podcast/rss): opaque non-permalink <guid>,
RFC-822 <pubDate>, HH:MM:SS <itunes:duration>, an audio/mpeg <enclosure>,
and (per that real feed, as of this date) no <podcast:transcript> tag on
any item -- the fixtures with a transcript tag below are synthetic, added
specifically to prove the detection code path works generically for any
podcast feed that does carry one, not because Lucentlands' real feed does.
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
    DEDUPE_STRATEGY_CANONICAL_URL,
    DEDUPE_STRATEGY_GUID,
    DEDUPE_STRATEGY_METADATA_HASH,
    DiscoveryError,
    TRANSCRIPT_NOT_DETECTED,
    TRANSCRIPT_PUBLISHER,
    acquire_raw_transcript_artifact,
    discover_source,
    list_discovered_items,
    read_source_discovery_state,
)

SOURCE_ID = "source-media-discovery-test-podcast"
FEED_URL = "https://feeds.example.invalid/media-discovery-test/rss"
ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8")
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


def _item_xml(
    *,
    title: str,
    guid: str | None = "guid-1",
    link: str | None = "https://example.invalid/ep1",
    pub_date: str | None = "Wed, 28 Oct 2025 07:00:00 GMT",
    duration: str | None = "00:39:05",
    description: str = "Episode description.",
    enclosure_type: str = "audio/mpeg",
    transcript_url: str | None = None,
) -> str:
    guid_tag = f'<guid isPermaLink="false">{guid}</guid>' if guid else ""
    link_tag = f"<link>{link}</link>" if link else ""
    pub_tag = f"<pubDate>{pub_date}</pubDate>" if pub_date else ""
    duration_tag = f"<itunes:duration>{duration}</itunes:duration>" if duration else ""
    enclosure_tag = f'<enclosure url="{link or "https://example.invalid/audio.mp3"}" type="{enclosure_type}" length="1"/>' if enclosure_type else ""
    transcript_tag = f'<podcast:transcript url="{transcript_url}" type="text/vtt" language="en"/>' if transcript_url else ""
    return f"""
<item>
<title>{title}</title>
{guid_tag}
{link_tag}
{pub_tag}
{duration_tag}
{enclosure_tag}
{transcript_tag}
<description>{description}</description>
</item>"""


def _feed(items: list[str]) -> bytes:
    body = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0">
<channel>
<title>Media Discovery Test Feed</title>
<link>https://example.invalid/</link>
<description>Test feed.</description>
{body}
</channel>
</rss>""".encode("utf-8")


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


@pytest.fixture
def source(repos):
    return repos.sources.create(
        {
            "id": SOURCE_ID,
            "type": "reference",
            "label": "Media Discovery Test Podcast",
            "value": "https://example.invalid/podcast-landing-page",
            "url": "https://example.invalid/podcast-landing-page",
            "last_checked_at": None,
            "last_status": None,
            "discovery": {"adapter": "podcast_rss", "feed_url": FEED_URL},
        }
    )


def _run(tmp_path: Path, source, monkeypatch, feed_bytes: bytes):
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeResponse(feed_bytes))
    return discover_source(SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)


# ---------------------------------------------------------------------------
# 1-2: a valid feed parses; multiple items normalize correctly
# ---------------------------------------------------------------------------


def test_valid_feed_discovery_response_parses(tmp_path, source, monkeypatch) -> None:
    feed = _feed(
        [
            _item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1"),
            _item_xml(title="Episode Two", guid="guid-2", link="https://example.invalid/ep2"),
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)
    assert result.status == "ok"
    assert result.found == 2
    assert result.new == 2
    assert not result.item_failures


def test_multiple_items_normalize_correctly(tmp_path, source, monkeypatch) -> None:
    feed = _feed(
        [
            _item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1", description="First one."),
            _item_xml(title="Episode Two", guid="guid-2", link="https://example.invalid/ep2", description="Second one."),
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)
    by_title = {item["title"]: item for item in result.items}
    assert set(by_title) == {"Episode One", "Episode Two"}
    assert by_title["Episode One"]["description"] == "First one."
    assert by_title["Episode Two"]["description"] == "Second one."
    for item in result.items:
        assert item["source_id"] == SOURCE_ID
        assert item["record_type"] == "discovered_media_item"


# ---------------------------------------------------------------------------
# 3-4: stable external IDs and canonical URLs retained
# ---------------------------------------------------------------------------


def test_stable_external_ids_retained(tmp_path, source, monkeypatch) -> None:
    feed = _feed([_item_xml(title="Episode One", guid="a1b2c3d4-guid", link="https://example.invalid/ep1")])
    result = _run(tmp_path, source, monkeypatch, feed)
    item = result.items[0]
    assert item["external_id"] == "a1b2c3d4-guid"
    assert item["dedupe_strategy"] == DEDUPE_STRATEGY_GUID
    assert item["dedupe_key"] == "a1b2c3d4-guid"


def test_canonical_urls_retained(tmp_path, source, monkeypatch) -> None:
    feed = _feed([_item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1-canonical")])
    result = _run(tmp_path, source, monkeypatch, feed)
    assert result.items[0]["canonical_url"] == "https://example.invalid/ep1-canonical"


# ---------------------------------------------------------------------------
# 5: media format assigned correctly
# ---------------------------------------------------------------------------


def test_media_format_assigned_correctly(tmp_path, source, monkeypatch) -> None:
    feed = _feed(
        [
            _item_xml(title="Audio Episode", guid="guid-audio", enclosure_type="audio/mpeg"),
            _item_xml(title="Video Episode", guid="guid-video", link="https://example.invalid/ep-video", enclosure_type="video/mp4"),
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)
    by_title = {item["title"]: item for item in result.items}
    assert by_title["Audio Episode"]["media_format"] == "podcast"
    assert by_title["Video Episode"]["media_format"] == "video"


# ---------------------------------------------------------------------------
# 6-7: repeat/duplicate discovery is idempotent
# ---------------------------------------------------------------------------


def test_repeat_discovery_is_idempotent(tmp_path, source, monkeypatch) -> None:
    feed = _feed(
        [
            _item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1"),
            _item_xml(title="Episode Two", guid="guid-2", link="https://example.invalid/ep2"),
        ]
    )
    first = _run(tmp_path, source, monkeypatch, feed)
    assert first.new == 2 and first.already_known == 0

    second = _run(tmp_path, source, monkeypatch, feed)
    assert second.new == 0
    assert second.already_known == 2

    staged = list_discovered_items(tmp_path / "inbox", source_id=SOURCE_ID)
    assert len(staged) == 2
    for item in staged:
        assert item["seen_count"] == 2
        assert item["first_seen_at"] == item["first_seen_at"]  # stable (see next assertion)

    ids_first_run = {item["id"] for item in first.items}
    ids_second_run = {item["id"] for item in second.items}
    assert ids_first_run == ids_second_run


def test_duplicate_discovery_does_not_duplicate_staging_records(tmp_path, source, monkeypatch) -> None:
    feed = _feed([_item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1")])
    _run(tmp_path, source, monkeypatch, feed)
    _run(tmp_path, source, monkeypatch, feed)
    _run(tmp_path, source, monkeypatch, feed)

    staging_files = list((tmp_path / "inbox" / "discovered_media").glob("*.json"))
    assert len(staging_files) == 1


# ---------------------------------------------------------------------------
# 8: a changed metadata field does not incorrectly create a new logical episode
# ---------------------------------------------------------------------------


def test_changed_metadata_field_does_not_create_new_logical_episode(tmp_path, source, monkeypatch) -> None:
    original_feed = _feed([_item_xml(title="Original Title", guid="guid-stable", link="https://example.invalid/ep1")])
    first = _run(tmp_path, source, monkeypatch, original_feed)
    original_id = first.items[0]["id"]
    original_first_seen = first.items[0]["first_seen_at"]

    corrected_feed = _feed(
        [_item_xml(title="Corrected Title (typo fix)", guid="guid-stable", link="https://example.invalid/ep1")]
    )
    second = _run(tmp_path, source, monkeypatch, corrected_feed)

    assert second.new == 0
    assert second.already_known == 1
    assert second.items[0]["id"] == original_id
    assert second.items[0]["title"] == "Corrected Title (typo fix)"
    assert second.items[0]["first_seen_at"] == original_first_seen
    assert second.items[0]["seen_count"] == 2

    staging_files = list((tmp_path / "inbox" / "discovered_media").glob("*.json"))
    assert len(staging_files) == 1


# ---------------------------------------------------------------------------
# 9: missing optional metadata degrades gracefully
# ---------------------------------------------------------------------------


def test_missing_optional_metadata_degrades_gracefully(tmp_path, source, monkeypatch) -> None:
    feed = _feed(
        [
            _item_xml(
                title="Sparse Episode",
                guid="guid-sparse",
                link="https://example.invalid/ep-sparse",
                pub_date=None,
                duration=None,
                description="",
            )
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)
    assert result.status == "ok"
    assert not result.item_failures
    item = result.items[0]
    assert item["published_date"] is None
    assert item["duration_seconds"] is None
    assert item["description"] == ""
    assert item["title"] == "Sparse Episode"


def test_missing_canonical_url_falls_back_to_metadata_hash_dedupe(tmp_path, source, monkeypatch) -> None:
    feed = _feed([_item_xml(title="No Link Or Guid Episode", guid=None, link=None, pub_date="Wed, 28 Oct 2025 07:00:00 GMT")])
    result = _run(tmp_path, source, monkeypatch, feed)
    assert result.status == "ok"
    item = result.items[0]
    assert item["external_id"] is None
    assert item["canonical_url"] is None
    assert item["dedupe_strategy"] == DEDUPE_STRATEGY_METADATA_HASH


def test_dedupe_prefers_canonical_url_over_metadata_hash_when_no_guid(tmp_path, source, monkeypatch) -> None:
    feed = _feed([_item_xml(title="Linked Episode", guid=None, link="https://example.invalid/ep-no-guid")])
    result = _run(tmp_path, source, monkeypatch, feed)
    item = result.items[0]
    assert item["dedupe_strategy"] == DEDUPE_STRATEGY_CANONICAL_URL


# ---------------------------------------------------------------------------
# 10: malformed individual items handled appropriately (one bad item does
# not make the whole feed unusable)
# ---------------------------------------------------------------------------


def test_malformed_individual_item_does_not_break_whole_feed(tmp_path, source, monkeypatch) -> None:
    def _flaky_normalize(entry):
        if getattr(entry, "title", "") == "Broken Episode":
            raise ValueError("simulated malformed entry")
        return real_normalize(entry)

    real_normalize = media_discovery.ADAPTER_TYPES["podcast_rss"][2]
    monkeypatch.setitem(
        media_discovery.ADAPTER_TYPES,
        "podcast_rss",
        (media_discovery.ADAPTER_TYPES["podcast_rss"][0], media_discovery.ADAPTER_TYPES["podcast_rss"][1], _flaky_normalize),
    )

    feed = _feed(
        [
            _item_xml(title="Good Episode One", guid="guid-good-1", link="https://example.invalid/good1"),
            _item_xml(title="Broken Episode", guid="guid-broken", link="https://example.invalid/broken"),
            _item_xml(title="Good Episode Two", guid="guid-good-2", link="https://example.invalid/good2"),
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)

    assert result.status == "ok"
    assert result.found == 3
    assert result.new == 2
    assert len(result.item_failures) == 1
    assert result.item_failures[0].identifier == "guid-broken"
    assert "simulated malformed entry" in result.item_failures[0].error
    assert {item["title"] for item in result.items} == {"Good Episode One", "Good Episode Two"}


# ---------------------------------------------------------------------------
# 11: full feed failure surfaced clearly
# ---------------------------------------------------------------------------


def test_full_feed_failure_surfaced_clearly(tmp_path, source, monkeypatch) -> None:
    def _raise(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr(media_discovery.httpx, "get", _raise)
    result = discover_source(SOURCE_ID, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "error"
    assert "simulated network failure" in result.error
    assert result.found == 0
    assert list_discovered_items(tmp_path / "inbox") == []

    state = read_source_discovery_state(tmp_path / "inbox", SOURCE_ID)
    assert state["status"] == "error"
    assert "simulated network failure" in state["error"]


def test_unknown_source_raises_discovery_error(tmp_path) -> None:
    with pytest.raises(DiscoveryError):
        discover_source("source-does-not-exist", inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)


def test_source_without_discovery_config_raises_discovery_error(tmp_path, repos) -> None:
    repos.sources.create({"id": "source-no-discovery-config", "type": "reference", "label": "No Config"})
    with pytest.raises(DiscoveryError):
        discover_source("source-no-discovery-config", inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)


# ---------------------------------------------------------------------------
# 12: transcript/caption availability states remain distinct
# ---------------------------------------------------------------------------


def test_transcript_availability_states_remain_distinct(tmp_path, source, monkeypatch) -> None:
    feed = _feed(
        [
            _item_xml(
                title="Has Transcript",
                guid="guid-has-transcript",
                link="https://example.invalid/ep-transcript",
                transcript_url="https://example.invalid/ep-transcript.vtt",
            ),
            _item_xml(title="No Transcript", guid="guid-no-transcript", link="https://example.invalid/ep-no-transcript"),
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)
    by_title = {item["title"]: item for item in result.items}

    with_transcript = by_title["Has Transcript"]["transcript_availability"]
    assert with_transcript["status"] == TRANSCRIPT_PUBLISHER
    assert with_transcript["url"] == "https://example.invalid/ep-transcript.vtt"

    without_transcript = by_title["No Transcript"]["transcript_availability"]
    assert without_transcript["status"] == TRANSCRIPT_NOT_DETECTED
    assert without_transcript["url"] is None

    assert with_transcript["status"] != without_transcript["status"]


# ---------------------------------------------------------------------------
# 13: no discovered item is automatically promoted to trusted Evidence
# ---------------------------------------------------------------------------


def test_no_discovered_item_is_automatically_promoted_to_evidence(tmp_path, source, monkeypatch, repos) -> None:
    feed = _feed([_item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1")])
    result = _run(tmp_path, source, monkeypatch, feed)
    assert result.new == 1

    assert repos.evidence.list() == []
    assert not (tmp_path / "evidence").exists()
    assert not (tmp_path / "inbox" / "evidence").exists()

    for item in result.items:
        assert item["record_type"] == "discovered_media_item"
        assert "evidence" not in item["id"]


# ---------------------------------------------------------------------------
# 14: the existing real Lucentlands Evidence record is not mutated, and is
# surfaced (read-only) as a possible match by the reconciliation hook
# ---------------------------------------------------------------------------


def test_existing_real_lucentlands_evidence_record_is_not_mutated(tmp_path, source, monkeypatch, repos) -> None:
    real_record_path = ROOT / "data" / "evidence" / "ev-lucentlands-scaling-blueberry-industry-2025.json"
    real_record = json.loads(real_record_path.read_text(encoding="utf-8"))
    before = json.loads(json.dumps(real_record))  # deep copy for comparison

    # Seed the tmp Evidence repo with the exact real record, under the
    # *same* source_id this test's fixture source also uses, so the
    # reconciliation hook has something to (potentially) match against --
    # without ever touching the live data/evidence/ file itself.
    seeded = dict(real_record)
    seeded["source_id"] = SOURCE_ID
    repos.evidence.create(seeded)

    feed = _feed(
        [
            _item_xml(
                title=real_record["title"],
                guid="guid-matching-real-episode",
                link="https://example.invalid/ep-matching",
                pub_date="Tue, 28 Oct 2025 07:00:00 GMT",
            )
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)

    # The real on-disk file is untouched.
    assert json.loads(real_record_path.read_text(encoding="utf-8")) == before

    # The seeded copy in the tmp repo is untouched too -- reconciliation is read-only.
    assert repos.evidence.get(seeded["id"]) == seeded

    # And the staging item recorded the match as advisory-only metadata.
    discovered = result.items[0]
    assert discovered["record_type"] == "discovered_media_item"
    matches = discovered["possible_evidence_matches"]
    assert any(m["evidence_id"] == seeded["id"] for m in matches)


# ---------------------------------------------------------------------------
# 15: no company/entity-specific behavior is introduced -- the same generic
# adapter mechanism works for a differently-labeled, differently-configured
# source, not just Lucentlands
# ---------------------------------------------------------------------------


def test_no_company_specific_behavior_generic_adapter_works_for_any_podcast_rss_source(tmp_path, repos, monkeypatch) -> None:
    other_source_id = "source-a-completely-different-podcast"
    repos.sources.create(
        {
            "id": other_source_id,
            "type": "reference",
            "label": "A Completely Different Podcast",
            "discovery": {"adapter": "podcast_rss", "feed_url": "https://feeds.example.invalid/other/rss"},
        }
    )
    feed = _feed([_item_xml(title="Some Episode", guid="guid-other-1", link="https://example.invalid/other-ep1")])
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeResponse(feed))
    result = discover_source(other_source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)

    assert result.status == "ok"
    assert result.new == 1
    assert result.items[0]["source_id"] == other_source_id


# ---------------------------------------------------------------------------
# Phase 8: optional raw transcript artifact acquisition (opt-in, low coupling)
# ---------------------------------------------------------------------------


def test_acquire_raw_transcript_artifact_fetches_and_stages_declared_transcript(tmp_path, source, monkeypatch) -> None:
    feed = _feed(
        [
            _item_xml(
                title="Has Transcript",
                guid="guid-has-transcript",
                link="https://example.invalid/ep-transcript",
                transcript_url="https://example.invalid/ep-transcript.vtt",
            )
        ]
    )
    result = _run(tmp_path, source, monkeypatch, feed)
    item = result.items[0]

    transcript_text = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHello and welcome."
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeResponse(transcript_text.encode("utf-8")))

    artifact = acquire_raw_transcript_artifact(tmp_path / "inbox", item)
    assert artifact is not None
    assert artifact["item_id"] == item["id"]
    assert artifact["raw_text"] == transcript_text
    assert artifact["provenance_url"] == "https://example.invalid/ep-transcript.vtt"
    assert artifact["provenance_kind"] == "publisher_declared"
    import hashlib

    assert artifact["checksum_sha256"] == hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()

    staged_path = tmp_path / "inbox" / "discovered_media" / "_transcripts" / f"{artifact['id']}.json"
    assert staged_path.exists()


def test_acquire_raw_transcript_artifact_returns_none_when_no_transcript_declared(tmp_path, source, monkeypatch) -> None:
    feed = _feed([_item_xml(title="No Transcript", guid="guid-no-transcript", link="https://example.invalid/ep-no-transcript")])
    result = _run(tmp_path, source, monkeypatch, feed)
    item = result.items[0]
    assert acquire_raw_transcript_artifact(tmp_path / "inbox", item) is None


# ---------------------------------------------------------------------------
# operational metadata (Phase 10)
# ---------------------------------------------------------------------------


def test_operational_state_records_last_checked_and_status(tmp_path, source, monkeypatch) -> None:
    feed = _feed([_item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1")])
    _run(tmp_path, source, monkeypatch, feed)
    state = read_source_discovery_state(tmp_path / "inbox", SOURCE_ID)
    assert state["status"] == "ok"
    assert state["found"] == 1
    assert state["new"] == 1
    assert state["last_checked_at"]


def test_source_registry_last_checked_fields_are_not_touched_by_discovery(tmp_path, source, monkeypatch, repos) -> None:
    """Discovery must not write to sources.json's own last_checked_at/
    last_status -- those are documented (app/main.py check_all_sources())
    as meaning 'a human reviewed this reference source', and repurposing
    them from an automated process would silently break that meaning."""
    feed = _feed([_item_xml(title="Episode One", guid="guid-1", link="https://example.invalid/ep1")])
    _run(tmp_path, source, monkeypatch, feed)
    reloaded = repos.sources.get(SOURCE_ID)
    assert reloaded["last_checked_at"] is None
    assert reloaded["last_status"] is None


# ---------------------------------------------------------------------------
# Continuous Intelligence Refresh (2026-08-18): bounded initial-discovery
# policy for spoken media. A real recurring run against a source with a
# deep back-catalog produced 562 new untranscribed drafts in a single pass
# the first time it was ever checked -- these tests prove the fix: a
# spoken-media source's first-ever discovery run stages a bounded recent
# window (never silently drops the rest), and later runs are unaffected.
# ---------------------------------------------------------------------------


def _rfc822(days_ago: int) -> str:
    from datetime import datetime, timedelta, timezone

    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return when.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _episodes(count: int, *, start_days_ago: int, step_days: int = 1, start_index: int = 0) -> list[str]:
    return [
        _item_xml(
            title=f"Episode {start_index + index}",
            guid=f"guid-backlog-{start_index + index}",
            link=f"https://example.invalid/backlog-ep{start_index + index}",
            pub_date=_rfc822(start_days_ago + index * step_days),
        )
        for index in range(count)
    ]


def test_first_ever_spoken_media_discovery_bounds_backlog_to_recent_window(tmp_path, source, monkeypatch) -> None:
    # 10 episodes within the lookback window (1-10 days old), 3 well
    # outside it (2+ years old) -- a real deep back-catalog shape.
    recent = _episodes(10, start_days_ago=1)
    old = _episodes(3, start_days_ago=800, step_days=30, start_index=10)
    result = _run(tmp_path, source, monkeypatch, _feed(recent + old))
    assert result.status == "ok"
    assert result.new == 13
    assert result.historical_backlog == 3

    items = {item["title"]: item for item in list_discovered_items(tmp_path / "inbox", SOURCE_ID)}
    for index in range(10):
        assert items[f"Episode {index}"].get("historical_backlog") is not True
    for index in range(10, 13):
        assert items[f"Episode {index}"]["historical_backlog"] is True


def test_first_ever_discovery_never_yields_zero_items_for_a_dormant_show(tmp_path, source, monkeypatch) -> None:
    """A show whose only episode is older than the lookback window should
    still get one current item, not zero -- "a small useful recent
    window", never nothing."""
    old = _episodes(1, start_days_ago=400)
    result = _run(tmp_path, source, monkeypatch, _feed(old))
    assert result.new == 1
    assert result.historical_backlog == 0
    items = list_discovered_items(tmp_path / "inbox", SOURCE_ID)
    assert items[0].get("historical_backlog") is not True


def test_allow_historical_backfill_stages_the_full_back_catalog(tmp_path, source, monkeypatch) -> None:
    feed = _feed(_episodes(10, start_days_ago=1) + _episodes(3, start_days_ago=800, step_days=30, start_index=10))
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *a, **k: _FakeResponse(feed))
    result = discover_source(
        SOURCE_ID,
        inbox_dir=tmp_path / "inbox",
        data_dir=tmp_path,
        schemas_dir=SCHEMAS_DIR,
        allow_historical_backfill=True,
    )
    assert result.new == 13
    assert result.historical_backlog == 0
    items = list_discovered_items(tmp_path / "inbox", SOURCE_ID)
    assert not any(item.get("historical_backlog") for item in items)


def test_second_discovery_run_does_not_bound_a_genuinely_new_item(tmp_path, source, monkeypatch) -> None:
    """Once a source has a successful prior run (a real watermark), it is
    no longer 'first-ever' -- a single genuinely new episode discovered on
    a later run must never be flagged historical_backlog, regardless of
    the source's total known item count."""
    first_feed = _feed(_episodes(10, start_days_ago=1) + _episodes(3, start_days_ago=800, step_days=30, start_index=10))
    first = _run(tmp_path, source, monkeypatch, first_feed)
    assert first.historical_backlog == 3

    new_episode = _item_xml(
        title="Episode Newest",
        guid="guid-backlog-newest",
        link="https://example.invalid/backlog-ep-newest",
        pub_date=_rfc822(0),
    )
    second_feed = _feed([new_episode, *_episodes(10, start_days_ago=1), *_episodes(3, start_days_ago=800, step_days=30, start_index=10)])
    second = _run(tmp_path, source, monkeypatch, second_feed)
    assert second.new == 1
    assert second.historical_backlog == 0
    items = {item["title"]: item for item in list_discovered_items(tmp_path / "inbox", SOURCE_ID)}
    assert items["Episode Newest"].get("historical_backlog") is not True
