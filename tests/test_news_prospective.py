from contextlib import closing
from datetime import UTC, datetime, timedelta
import sqlite3
from types import SimpleNamespace

import pytest

from app import news_workspace_routes as routes
from app.services import feed_first_live, personal_digest, publisher_coverage
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider
from app.services.news_prospective import START_ENV, ProspectiveRun


def test_pilot_window_is_fixed_utc_and_disabled_without_explicit_start(monkeypatch):
    start = datetime(2026, 11, 12, 12, tzinfo=UTC)
    monkeypatch.delenv(START_ENV, raising=False)
    assert ProspectiveRun.from_environment(start) is None
    monkeypatch.setenv(START_ENV, "2026-11-12T12:00:00-08:00")
    with pytest.raises(ValueError, match="explicit UTC offset"):
        ProspectiveRun.from_environment(start)
    monkeypatch.setenv(START_ENV, start.isoformat())
    assert ProspectiveRun.from_environment(start - timedelta(microseconds=1)) is None
    active = ProspectiveRun.from_environment(start)
    assert active.window_end == start + timedelta(days=14)
    assert ProspectiveRun.from_environment(active.window_end) is None


def test_ledger_keeps_earliest_normalized_observation_and_excludes_late_stages(tmp_path):
    start = datetime(2026, 11, 12, 12, tzinfo=UTC)
    original = ProspectiveRun(start, start)
    retry = ProspectiveRun(start, start + timedelta(minutes=15))
    original_url = "https://www.publisher.example/story/?utm_source=wrapper#image"
    clean_url = "http://publisher.example/story"
    retry._observe("raw", original_url, "google_news_rss", "route", "2026-11-12", retry.started_at)
    retry.save(tmp_path, completed_at=retry.started_at.isoformat(), status="ready", route_attempts=[])
    original._observe("raw", clean_url, "google_news_rss", "route", "2026-11-12", start)
    original._observe("raw", "https://news.google.com/rss/articles/opaque", "google_news_rss", "route", None, start)
    original._observe("qualified", clean_url, "google_news_rss", "route", "2026-11-12", original.window_end)
    original._observe("raw", "http://127.0.0.1/story", "google_news_rss", "route", None, start)
    original.save(tmp_path, completed_at=start.isoformat(), status="ready", route_attempts=[])
    path = next(tmp_path.rglob("observations.sqlite3"))
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT count(*) FROM runs").fetchone() == (2,)
        assert set(db.execute("""
            SELECT normalized_url, stage, first_observed_at, publication_date,
                   exact_url_candidate, independent_reference FROM observations
            """).fetchall()) == {
                ("publisher.example/story", "raw", start.isoformat(timespec="microseconds"), "2026-11-12", 1, 0),
                ("news.google.com/rss/articles/opaque", "raw", start.isoformat(timespec="microseconds"), None, 0, 0),
            }


@pytest.mark.live_today
def test_scheduled_refresh_records_discovery_qualification_and_actual_news_eligibility(tmp_path, monkeypatch):
    stamp = datetime.now(UTC)
    monkeypatch.setenv(START_ENV, (stamp - timedelta(minutes=5)).isoformat())
    monkeypatch.setenv("BIOS_INBOX_DIR", str(tmp_path))
    query = feed_first_live.today_google_queries()[0]
    publisher = "publisher.example"

    def hit(title, snippet, path):
        url = f"https://{publisher}/news/{path}"
        return DiscoveryHit(title, url, publisher, stamp.date().isoformat(), snippet, query.id, query.text,
                            query.geography, query.berry, query.topic, "google_news_rss")

    stories = [
        hit("Blueberry nursery adds new cultivar trials in California",
            "The blueberry grower expands commercial production and trial acreage this season.", "eligible"),
        hit("Hidden Farm expands blueberry nursery",
            "A blueberry grower reports a production and acreage increase in California.", "muted"),
        hit("NFL players rank their Halloween candy", "A sweet discussion among fans.", "noise"),
    ]
    google = MemoryProvider(name="google_news_rss", hits_by_query_id={query.id: stories})
    monkeypatch.setattr(feed_first_live, "GoogleNewsRssProvider", lambda: google)
    monkeypatch.setattr(feed_first_live, "SpecialistRssProvider", lambda **_: MemoryProvider())
    monkeypatch.setattr(feed_first_live, "today_google_queries", lambda: [query])
    monkeypatch.setattr(publisher_coverage, "refresh_publisher_coverage", lambda _: [])
    monkeypatch.setattr(routes, "classify_stored_tags", lambda: None)
    image_calls = []
    def thumbnails(inbox, records, **kwargs):
        image_calls.append(([row['source_url'] for row in records], kwargs))
        return {'checked': 1, 'found': 1}
    monkeypatch.setattr(routes.news_images, 'collect', thumbnails)
    entity = {"id": "company-hidden-farm", "name": "Hidden Farm", "entity_type": "company"}
    context = {"entities": [entity], "official_hosts": set(), "official_host_map": {}, "muted_entity_ids": set(),
               "state": {"entity_tiers": {entity["id"]: "muted"}}}
    main = SimpleNamespace(INBOX_DIR=tmp_path, all_relationships=list, all_facts=list)
    monkeypatch.setattr(routes, "world", lambda: (
        main, context, {row["id"]: row for row in personal_digest.retained_news(tmp_path)}, {entity["id"]: entity}
    ))

    routes.run_refresh(tmp_path, context, [], update_publishers=False)
    assert not list(tmp_path.rglob("observations.sqlite3"))
    assert image_calls == []
    routes.run_refresh(tmp_path, context, [], update_publishers=True)
    assert len(image_calls) == 1
    assert image_calls[0][0] == [f'https://{publisher}/news/eligible']
    assert image_calls[0][1] == {'limit': 12, 'scan_limit': 108}
    assert routes.refresh_state(tmp_path)["status"] == "ready"
    path = next(tmp_path.rglob("observations.sqlite3"))
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT status, projection_status FROM runs").fetchall() == [("ready", "complete")]
        actual = db.execute("SELECT normalized_url, stage, independent_reference FROM observations").fetchall()
        assert set(actual) == {
            (f"{publisher}/news/{slug}", stage, 0) for slug, stages in {
                "eligible": ("raw", "qualified", "news_eligible"),
                "muted": ("raw", "qualified"),
                "noise": ("raw",),
            }.items() for stage in stages
        }
        assert db.execute("SELECT count(DISTINCT route_id) FROM observations").fetchone() == (1,)
