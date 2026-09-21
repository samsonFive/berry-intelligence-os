"""Gate A / Gate 1 feed-first golden path."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.feed_first import (
    EXTRACTION_MODEL,
    apply_decision,
    build_feed,
    empty_state,
    extract_statements,
    load_state,
    parse_filters,
    playground_fixtures,
    set_entity_tier,
    statements_for_entity,
)
from app.services.feed_first_live import (
    OFFICIAL_SITE_HOST_CAP,
    live_disclosure,
    live_feed_bundle,
    live_item_id,
    save_bundle,
    today_official_site_queries,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider


def _record(**overrides):
    base = {
        "id": "ev-gate1-readable",
        "status": "published",
        "title": "Fall Creek Spain reaches 14 million blueberry plants after 10 years",
        "summary": "Fall Creek marked 10 years in Spain and reports 14 million plants.",
        "source_name": "FreshPlaza",
        "source_type": "trade_press",
        "source_url": "https://example.test/fall-creek-spain",
        "published_date": "2026-05-26",
        "captured_date": "2026-08-06",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek-farm-and-nursery"],
        "geography_ids": ["geography-spain"],
        "article": {
            "paragraphs": [
                {
                    "text": (
                        "Fall Creek Farm & Nursery marked 10 years of operations in Spain. "
                        "Established in 2016 with a two-hectare harvest using plug material from the U.S., "
                        "the operation has expanded to 14 million blueberry plants."
                    )
                }
            ]
        },
    }
    base.update(overrides)
    return base


def _entities():
    return [
        {
            "id": "company-fall-creek-farm-and-nursery",
            "name": "Fall Creek Farm & Nursery",
            "aliases": ["Fall Creek"],
            "entity_type": "company",
            "status": "active",
        }
    ]


def test_tokens_and_playground_exist():
    css = Path("app/static/berry_os.css").read_text(encoding="utf-8")
    assert "--bos-ink: #0b1020" in css
    assert "--bos-strawberry: #f43f5e" in css
    assert "prefers-reduced-motion" in css
    page = TestClient(app).get("/design-system")
    assert page.status_code == 200
    assert "data-design-system" in page.text
    assert "Playground fixtures only" in page.text
    assert "Card families" in page.text
    assert "Berry Growth Loader" in page.text


def _same_day_hit(**overrides):
    base = dict(
        title="Fall Creek expands blueberry nursery harvest after new planting",
        url="https://example.test/fall-creek-same-day",
        source_domain="freshplaza.com",
        published_date="2026-09-21",
        snippet="The blueberry breeder reports new acreage and plant production in Spain.",
        query_id="today:blueberry:global:30d",
        query_text="blueberry harvest",
        geography="global",
        berry="blueberry",
        topic="industry_pulse",
        provider="google_news_rss",
        origin_publisher_name="FreshPlaza",
        origin_publisher_url="https://example.test/fall-creek-same-day",
    )
    base.update(overrides)
    return DiscoveryHit(**base)


def _stub_live_bundle(records=None, *, today="2026-09-21"):
    rows = records if records is not None else [
        {
            "id": "live-demo-same-day",
            "status": "published",
            "trust_state": "LIVE",
            "review_state": "UNREVIEWED",
            "acquisition_lane": "google_news_rss",
            "live": True,
            "title": "Fall Creek expands blueberry nursery harvest after new planting",
            "summary": "The blueberry breeder reports new acreage and plant production in Spain.",
            "source_name": "FreshPlaza",
            "source_type": "trade_press",
            "source_url": "https://example.test/fall-creek-same-day",
            "published_date": today,
            "captured_date": today,
            "berry_ids": ["berry-blueberry"],
            "entity_ids": ["company-fall-creek-farm-and-nursery"],
            "geography_ids": ["geography-spain"],
            "tags": ["live", "unreviewed"],
            "publisher_description": "The blueberry breeder reports new acreage and plant production in Spain.",
        }
    ]
    return {
        "today": today,
        "fetched_at": f"{today}T12:00:00+00:00",
        "lanes": ["google_news_rss", "specialist_rss", "perplexity"],
        "lane_errors": [],
        "stats": {"same_day": len(rows), "discovered": len(rows), "qualified": len(rows)},
        "records": rows,
    }


def test_today_is_feed_first_front_door(monkeypatch):
    from app.services import feed_first_live

    monkeypatch.setattr(feed_first_live, "live_feed_bundle", lambda **kwargs: _stub_live_bundle())
    monkeypatch.setattr("app.services.clock.utc_now", lambda: datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc))
    page = TestClient(app).get("/")
    assert page.status_code in {200, 307}
    today = TestClient(app).get("/today")
    assert today.status_code == 200
    assert "data-feed-first-today" in today.text
    assert 'data-freshness="same-day"' in today.text
    assert "thumbs_up" in today.text
    assert "berry_os.css" in today.text
    assert "companies watched" in today.text
    assert "same-day" in today.text
    assert "not a live multi-lane poll" not in today.text
    assert "90 days" not in today.text
    assert 'name="tier"' in today.text
    assert 'name="crop"' in today.text
    assert 'name="source"' in today.text
    assert 'name="window"' in today.text
    assert 'name="state"' in today.text
    assert "Fall Creek expands blueberry nursery harvest" in today.text


@pytest.mark.live_today
def test_today_cache_miss_is_offline_until_explicit_refresh(tmp_path: Path, monkeypatch):
    from app import main
    from app.services import feed_first_live

    acquisition_calls: list[bool] = []

    def injected_acquisition(**kwargs):
        acquisition_calls.append(True)
        today = kwargs["today"]
        return [], {
            "today": today.isoformat(),
            "lanes": [],
            "lane_errors": [],
            "stats": {"same_day": 0, "week": 0},
            "cascade": {},
        }

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(feed_first_live, "collect_same_day_hits", injected_acquisition)

    ordinary = TestClient(main.app).get("/today")

    assert ordinary.status_code == 200
    assert acquisition_calls == []
    assert "data-feed-first-today" in ordinary.text
    assert "No cached Today edition yet" in live_disclosure(
        {"cache_state": "missing", "today": "2026-09-21"}
    )
    assert "refresh=1" in ordinary.text
    assert "Ready to fetch live stories" in ordinary.text
    assert ">Fetch live stories</a>" in ordinary.text
    assert not (tmp_path / "feed_first_live").exists()

    refreshed = TestClient(main.app).get("/today?refresh=1")

    assert refreshed.status_code == 200
    assert acquisition_calls == [True]
    assert (tmp_path / "feed_first_live").exists()


def test_legacy_briefing_still_available():
    page = TestClient(app).get("/today?view=briefing")
    assert page.status_code == 200
    assert "Daily Intelligence Briefing" in page.text
    assert "thumbs-up" not in page.text.lower()


def test_filters_and_card_families():
    official = _record(
        id="ev-official",
        source_type="company_website",
        source_name="Fall Creek",
        title="Our history",
    )
    social = _record(
        id="ev-catalog",
        source_type="company_catalog",
        title="Sekoya catalog",
    )
    registry = _record(
        id="ev-patent",
        source_type="patent_record",
        source_name="USPTO",
        title="Plant patent",
        berry_ids=["berry-blueberry"],
        entity_ids=["company-fall-creek-farm-and-nursery"],
    )
    blocked = _record(
        id="ev-blocked",
        title="Paywalled note",
        summary="Please log in to continue. Subscribe to continue reading.",
        article={"paragraphs": [{"text": "Please log in to continue. Subscribe to continue reading."}]},
    )
    feed = build_feed(
        evidence=[_record(), official, social, registry, blocked],
        entities=_entities(),
        state=empty_state(),
        filters=parse_filters({"crop": "blueberry", "window": "30d"}),
        today=date(2026, 6, 1),
    )
    kinds = {item["source_kind"] for item in feed["cards"]}
    families = {item["family"] for item in feed["cards"]}
    assert "article" in kinds
    assert "official" in kinds
    assert "registry" in kinds
    assert "social" in families or "social" in kinds
    assert feed["has_fallback"]
    blueberry = build_feed(
        evidence=[_record(), _record(id="ev-berry", berry_ids=["berry-strawberry"], title="Strawberry only")],
        entities=_entities(),
        state=empty_state(),
        filters=parse_filters({"crop": "blueberry", "window": "30d"}),
        today=date(2026, 6, 1),
    )
    assert all("blueberry" in item["crops"] for item in blueberry["cards"])


def test_thumbs_persist_undo_and_do_not_mute(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = _record()
    first = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    assert first["decision"]["reaction"] == "up"
    assert first["statements"]
    assert first["statements"][0]["extraction_model"] == EXTRACTION_MODEL
    retry = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    assert len(retry["statements"]) == len(first["statements"])
    assert {row["id"] for row in retry["statements"]} == {row["id"] for row in first["statements"]}
    down = apply_decision(inbox, item_id=record["id"], action="thumbs_down", evidence=[record])
    assert down["decision"]["reaction"] == "down"
    assert down["statements"] == []
    assert down["muted_world"] is False
    state = load_state(inbox)
    assert state["entity_tiers"] == {}
    undo = apply_decision(inbox, item_id=record["id"], action="clear_reaction", evidence=[record])
    assert undo["decision"]["reaction"] is None


def test_inbox_state_snapshot_restores_thumbs_without_touching_evidence(tmp_path: Path):
    from app.services.feed_first import latest_snapshot, restore_state, snapshot_state

    inbox = tmp_path / "inbox"
    record = _record()
    apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    snap = snapshot_state(inbox)
    assert snap.exists()
    apply_decision(inbox, item_id=record["id"], action="thumbs_down", evidence=[record])
    assert load_state(inbox)["decisions"][record["id"]]["reaction"] == "down"
    restored = restore_state(inbox, latest_snapshot(inbox))
    assert restored["decisions"][record["id"]]["reaction"] == "up"
    assert restored["statements"][record["id"]]
    assert not (tmp_path / "data" / "evidence").exists()


def test_thumbs_down_hides_from_default_feed(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = _record()
    apply_decision(inbox, item_id=record["id"], action="thumbs_down", evidence=[record])
    hidden = build_feed(
        evidence=[record],
        entities=_entities(),
        state=load_state(inbox),
        filters=parse_filters({"window": "30d"}),
        today=date(2026, 6, 1),
    )
    assert hidden["cards"] == []
    judged = build_feed(
        evidence=[record],
        entities=_entities(),
        state=load_state(inbox),
        filters=parse_filters({"state": "judged", "window": "30d"}),
        today=date(2026, 6, 1),
    )
    assert judged["cards"][0]["id"] == record["id"]


def test_blocked_body_yields_no_statements():
    blocked = _record(
        id="ev-blocked-extract",
        summary="Please log in to continue. Subscribe to continue reading.",
        article={"paragraphs": [{"text": "Please log in to continue. Subscribe to continue reading."}]},
    )
    assert extract_statements(blocked) == []


def test_statement_edit_keeps_original(tmp_path: Path):
    from app.services.feed_first import mutate_statement

    inbox = tmp_path / "inbox"
    record = _record()
    applied = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    statement_id = applied["statements"][0]["id"]
    original = applied["statements"][0]["original_extraction_text"]
    edited = mutate_statement(inbox, statement_id=statement_id, action="edit", text="Spain nursery now at 14 million plants.")
    assert edited is not None
    assert edited["statement_text"] == "Spain nursery now at 14 million plants."
    assert edited["original_extraction_text"] == original
    assert edited["supporting_passages"]


def test_tier_does_not_change_verification(tmp_path: Path):
    inbox = tmp_path / "inbox"
    set_entity_tier(inbox, entity_id="company-fall-creek-farm-and-nursery", tier="tier1")
    feed = build_feed(
        evidence=[_record()],
        entities=_entities(),
        state=load_state(inbox),
        filters=parse_filters({"tier": "tier1", "window": "30d"}),
        today=date(2026, 6, 1),
    )
    assert feed["cards"]
    assert feed["cards"][0]["entities"][0]["verification_status"] == "active"
    assert feed["cards"][0]["entities"][0]["tier"] == "tier1"


def test_react_http_and_entity_reflection(tmp_path, monkeypatch):
    from app import main

    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    record = _record()
    monkeypatch.setattr(main, "published_evidence", lambda: [record])
    client = TestClient(main.app)
    up = client.post("/api/feed-first/react", json={"item_id": record["id"], "action": "thumbs_up"})
    assert up.status_code == 200
    assert up.json()["decision"]["reaction"] == "up"
    retry = client.post("/api/feed-first/react", json={"item_id": record["id"], "action": "thumbs_up"})
    assert [row["id"] for row in retry.json()["statements"]] == [row["id"] for row in up.json()["statements"]]
    state = load_state(inbox)
    reflected = statements_for_entity(state, "company-fall-creek-farm-and-nursery")
    assert reflected == []
    from app.services.feed_first import mutate_statement

    confirmed = mutate_statement(
        inbox,
        statement_id=up.json()["statements"][0]["id"],
        action="confirm",
        canonical_fact_id="fact-gate1-http",
    )
    assert confirmed["statement_state"] == "trusted_analyst"
    assert statements_for_entity(
        load_state(inbox), "company-fall-creek-farm-and-nursery"
    )
    down = client.post("/api/feed-first/react", json={"item_id": record["id"], "action": "thumbs_down"})
    assert down.json()["muted_world"] is False


def test_human_gate_workspace_reviews_statement_in_place(tmp_path, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    record = _record()
    applied = apply_decision(tmp_path, item_id=record["id"], action="thumbs_up", evidence=[record])
    statement_id = applied["statements"][0]["id"]
    client = TestClient(main.app)

    page = client.get("/statements?review=unreviewed")
    assert page.status_code == 200
    assert "Review extracted intelligence" in page.text
    assert 'data-statement-action="approve"' in page.text
    assert 'data-statement-edit="' + statement_id + '"' in page.text
    assert "Gate 3 progress" in page.text

    for statement in applied["statements"]:
        reviewed = client.post(
            "/api/feed-first/statement",
            json={"statement_id": statement["id"], "action": "approve"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["statement"]["review_state"] == "reviewed"

    remaining = client.get("/statements?review=unreviewed")
    assert "Human gate complete" in remaining.text
    labeled = client.get("/statements?review=reviewed")
    assert statement_id in labeled.text


def test_people_watchlist_is_honest():
    page = TestClient(app).get("/people")
    assert page.status_code == 200
    assert "provider-unavailable" in page.text
    assert "discovery-only" in page.text
    assert "data-feed-first-people" in page.text
    assert "Empty watchlist" not in page.text
    assert "do not invent" in page.text.lower() or "Do not invent" in page.text


def test_following_tracks_seed_companies_and_excludes_registries():
    page = TestClient(app).get("/following")
    assert page.status_code == 200
    assert "data-feed-first-following" in page.text
    assert "145 companies" in page.text or "145 seed companies" in page.text
    assert "Candidate · unverified" in page.text
    assert "cpvo.europa.eu" not in page.text.lower()
    blueberry = TestClient(app).get("/following?crop=blueberry")
    assert blueberry.status_code == 200
    assert "Fall Creek" in blueberry.text
    registries = TestClient(app).get("/following?registries=1")
    assert "Community Plant Variety Office" in registries.text
    assert "Excluded from competitor" in registries.text or "excluded from competitor" in registries.text.lower()


def test_entities_roster_and_seed_only_profile():
    page = TestClient(app).get("/entities")
    assert page.status_code == 200
    assert "data-feed-first-entities" in page.text
    assert "tracked breeding world" in page.text.lower() or "Tracked breeding world" in page.text
    roster = __import__("app.services.seed_roster", fromlist=["build_roster"]).build_roster([])
    seed_only = next(row for row in roster if not row.get("trusted_entity_id") and row["competitor"])
    profile = TestClient(app).get(f"/entities/company/{seed_only['id']}")
    assert profile.status_code == 200
    assert "data-feed-first-entity" in profile.text
    assert seed_only["canonical_name"] in profile.text
    if seed_only["candidate"]:
        assert "Candidate-review" in profile.text or "unverified" in profile.text
    trusted = TestClient(app).get("/entities/company/company-fall-creek-farm-and-nursery")
    assert trusted.status_code == 200
    assert "From Today thumbs-up" in trusted.text or "Fall Creek" in trusted.text


def test_playground_fixtures_are_not_the_today_corpus(monkeypatch):
    from app.services import feed_first_live

    monkeypatch.setattr(feed_first_live, "live_feed_bundle", lambda **kwargs: _stub_live_bundle())
    ids = {row["id"] for row in playground_fixtures()}
    assert all(item_id.startswith("fixture-") for item_id in ids)
    today = TestClient(app).get("/today")
    assert "fixture-lead-article" not in today.text
    assert "14 million blueberry plants after 10 years" not in today.text


def test_default_window_is_seven_days_with_calendar_today_override_available():
    assert parse_filters({})["window"] == "7d"
    assert parse_filters({"window": "today"})["window"] == "today"
    assert parse_filters({"window": ""})["window"] == ""
    assert parse_filters({"window": "30d"})["window"] == "30d"


def test_today_window_is_calendar_equality_not_24h():
    yesterday = _record(id="ev-yesterday", published_date="2026-09-20")
    today_row = _record(id="ev-today", published_date="2026-09-21")
    feed = build_feed(
        evidence=[yesterday, today_row],
        entities=_entities(),
        state=empty_state(),
        filters=parse_filters({}),
        today=date(2026, 9, 21),
    )
    assert {item["id"] for item in feed["cards"]} == {"ev-today", "ev-yesterday"}
    week = build_feed(
        evidence=[yesterday, today_row],
        entities=_entities(),
        state=empty_state(),
        filters=parse_filters({"window": "7d"}),
        today=date(2026, 9, 21),
    )
    assert {item["id"] for item in week["cards"]} == {"ev-today", "ev-yesterday"}


def test_live_collector_keeps_week_and_drops_older_noise(tmp_path: Path):
    today = date(2026, 9, 21)
    hits = [
        _same_day_hit(),
        _same_day_hit(
            title="Yesterday blueberry harvest briefing from the same breeder",
            url="https://example.test/yesterday",
            origin_publisher_url="https://example.test/yesterday",
            published_date="2026-09-20",
        ),
        _same_day_hit(
            title="Undated blueberry nursery update",
            url="https://example.test/undated",
            origin_publisher_url="https://example.test/undated",
            published_date=None,
        ),
        _same_day_hit(
            title="Best blueberry muffin recipe for breakfast",
            url="https://example.test/recipe",
            origin_publisher_url="https://example.test/recipe",
            snippet="Calories and smoothie ideas for the weekend.",
        ),
        _same_day_hit(
            title="August 2026 stored blueberry recap",
            url="https://example.test/august",
            origin_publisher_url="https://example.test/august",
            published_date="2026-08-06",
        ),
        _same_day_hit(
            title="Canaccord Genuity raises BlackBerry price target to $10.3",
            url="https://example.test/bb-stock",
            origin_publisher_url="https://example.test/bb-stock",
            snippet="Analyst rating and shares outstanding for the smartphone company.",
            berry="blackberry",
        ),
    ]
    provider = MemoryProvider(hits_by_query_id={"today:blueberry:global:30d": hits})
    specialist = MemoryProvider(hits_by_query_id={})
    bundle = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=True,
        today=today,
        now=datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc),
        google_provider=provider,
        specialist_provider=specialist,
        enable_perplexity=False,
        enable_exa=False,
        enable_apitube=False,
    )
    assert bundle["today"] == "2026-09-21"
    assert bundle["stats"]["same_day"] == 1
    assert bundle["stats"]["week"] == 2
    assert bundle["stats"]["dropped_not_today"] >= 1
    dates = {row["published_date"] for row in bundle["records"]}
    assert dates == {"2026-09-21", "2026-09-20"}
    assert "2026-08-06" not in dates
    record = next(row for row in bundle["records"] if row["published_date"] == "2026-09-21")
    assert record["id"] == live_item_id("https://example.test/fall-creek-same-day")
    assert record["trust_state"] == "LIVE"
    assert record["review_state"] == "UNREVIEWED"
    assert "company-fall-creek-farm-and-nursery" in record["entity_ids"]


def test_yesterday_cache_is_never_served_as_today(tmp_path: Path):
    stale = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=True,
        today=date(2026, 9, 20),
        now=datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc),
        google_provider=MemoryProvider(
            hits_by_query_id={
                "today:blueberry:global:30d": [
                    _same_day_hit(published_date="2026-09-20", title="Sunday blueberry harvest note")
                ]
            }
        ),
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        enable_perplexity=False,
        enable_exa=False,
        enable_apitube=False,
    )
    assert stale["records"]
    monday = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=False,
        today=date(2026, 9, 21),
        now=datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc),
        google_provider=MemoryProvider(hits_by_query_id={}),
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        enable_perplexity=False,
        enable_exa=False,
        enable_apitube=False,
    )
    assert monday["today"] == "2026-09-21"
    assert monday["records"] == []
    assert all(row.get("published_date") != "2026-09-20" for row in monday["records"])


def test_fresh_cache_does_not_invoke_translation_or_image_network(tmp_path: Path, monkeypatch):
    today = date(2026, 9, 21)
    now = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
    record = {
        "id": "live-cached",
        "title": "今日のブルーベリー生産者市場更新",
        "summary": "生産量と収穫量に関する最新情報です",
        "source_url": "https://publisher.invalid/story",
        "origin_publisher_url": "https://publisher.invalid/",
        "published_date": today.isoformat(),
        "image_url": "",
    }
    save_bundle(
        tmp_path,
        {
            "today": today.isoformat(),
            "fetched_at": now.isoformat(),
            "records": [record],
            "stats": {"same_day": 1, "week": 1},
        },
    )
    calls: list[str] = []

    def unexpected_network(*args, **kwargs):
        calls.append("network")
        raise AssertionError("ordinary cached Today must not perform network enrichment")

    monkeypatch.setattr("app.services.feed_first_translate.perplexity_translator", unexpected_network)
    monkeypatch.setattr("app.services.feed_first_reader.fetch_source_preview_image", unexpected_network)
    monkeypatch.setattr("app.services.feed_first_reader.fetch_publisher_home_preview", unexpected_network)

    cached = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=False,
        today=today,
        now=now,
    )

    assert calls == []
    assert cached["records"][0]["title"] == record["title"]
    assert cached["records"][0]["image_url"] == ""


def test_stale_cache_can_be_presented_without_live_acquisition(tmp_path: Path, monkeypatch):
    today = date(2026, 9, 21)
    now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    save_bundle(
        tmp_path,
        {
            "today": today.isoformat(),
            "fetched_at": datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc).isoformat(),
            "records": [
                {
                    "id": "live-stale",
                    "title": "Fall Creek blueberry harvest update",
                    "summary": "The breeder reported its latest harvest.",
                    "source_url": "https://publisher.invalid/story",
                    "published_date": today.isoformat(),
                }
            ],
            "stats": {"same_day": 1, "week": 1},
        },
    )

    def unexpected_acquisition(**kwargs):
        raise AssertionError("stale cache presentation must not acquire live stories")

    monkeypatch.setattr(
        "app.services.feed_first_live.collect_same_day_hits",
        unexpected_acquisition,
    )

    stale = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=False,
        acquire_on_miss=False,
        today=today,
        now=now,
    )

    assert stale["cache_state"] == "stale"
    assert [row["id"] for row in stale["records"]] == ["live-stale"]
    assert "Select Refresh" in live_disclosure(stale)


def test_perplexity_same_day_hits_join_keyless_lanes(tmp_path: Path):
    today = date(2026, 9, 21)
    google = MemoryProvider(
        hits_by_query_id={
            "today:blueberry:global:30d": [_same_day_hit()],
        }
    )
    perplexity = MemoryProvider(
        name="perplexity",
        hits_by_query_id={
            "today:perplexity:blueberry:americas:24h": [
                _same_day_hit(
                    title="Planasa blueberry harvest volumes rise in Peru this morning",
                    url="https://example.test/planasa-same-day",
                    origin_publisher_url="https://example.test/planasa-same-day",
                    snippet="The breeder reports new acreage and export volumes from the Americas.",
                    provider="perplexity",
                    berry="blueberry",
                    geography="americas",
                    query_id="today:perplexity:blueberry:americas:24h",
                ),
                _same_day_hit(
                    title="Yesterday only: Planasa blueberry briefing",
                    url="https://example.test/planasa-yesterday",
                    origin_publisher_url="https://example.test/planasa-yesterday",
                    published_date="2026-09-20",
                    provider="perplexity",
                    query_id="today:perplexity:blueberry:americas:24h",
                ),
            ]
        },
    )
    bundle = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=True,
        today=today,
        now=datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc),
        google_provider=google,
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        perplexity_provider=perplexity,
        enable_exa=False,
        enable_apitube=False,
    )
    titles = {row["title"] for row in bundle["records"]}
    assert "Fall Creek expands blueberry nursery harvest after new planting" in titles
    assert "Planasa blueberry harvest volumes rise in Peru this morning" in titles
    assert "Yesterday only: Planasa blueberry briefing" in titles
    assert bundle["stats"]["same_day"] == 2
    assert bundle["stats"]["week"] == 3
    assert "perplexity" in bundle["lanes"]
    assert bundle["perplexity_enabled"] is True
    assert {row["published_date"] for row in bundle["records"]} == {"2026-09-21", "2026-09-20"}


def test_perplexity_failure_does_not_drop_google_hits(tmp_path: Path):
    class Boom:
        name = "perplexity"

        def discover(self, query):
            raise RuntimeError("429 rate limit")

    bundle = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=True,
        today=date(2026, 9, 21),
        now=datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc),
        google_provider=MemoryProvider(
            hits_by_query_id={"today:blueberry:global:30d": [_same_day_hit()]}
        ),
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        perplexity_provider=Boom(),
        enable_exa=False,
        enable_apitube=False,
    )
    assert bundle["records"]
    assert bundle["records"][0]["published_date"] == "2026-09-21"
    assert bundle["lane_errors"]
    assert bundle["lane_errors"][0]["provider"] == "perplexity"


def test_exa_and_apitube_same_day_hits_join_keyless_lanes(tmp_path: Path):
    today = date(2026, 9, 21)
    exa = MemoryProvider(
        name="exa",
        hits_by_query_id={
            "today:perplexity:all:global:24h": [
                _same_day_hit(
                    title="Hortifrut blueberry harvest volumes rise in Peru this morning",
                    url="https://example.test/hortifrut-exa",
                    origin_publisher_url="https://example.test/hortifrut-exa",
                    snippet="The grower-marketer reports new acreage from the Andes.",
                    provider="exa",
                    query_id="today:perplexity:all:global:24h",
                )
            ]
        },
    )
    apitube = MemoryProvider(
        name="apitube",
        hits_by_query_id={
            "today:perplexity:blueberry:americas:24h": [
                _same_day_hit(
                    title="Planasa strawberry nursery expansion announced today",
                    url="https://example.test/planasa-apitube",
                    origin_publisher_url="https://example.test/planasa-apitube",
                    snippet="The breeder reports new plant production in the Americas.",
                    provider="apitube",
                    berry="strawberry",
                    query_id="today:perplexity:blueberry:americas:24h",
                )
            ]
        },
    )
    bundle = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=True,
        today=today,
        now=datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc),
        google_provider=MemoryProvider(hits_by_query_id={}),
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        enable_perplexity=False,
        exa_provider=exa,
        apitube_provider=apitube,
    )
    titles = {row["title"] for row in bundle["records"]}
    assert "Hortifrut blueberry harvest volumes rise in Peru this morning" in titles
    assert "Planasa strawberry nursery expansion announced today" in titles
    assert "exa" in bundle["lanes"]
    assert "apitube" in bundle["lanes"]
    assert bundle["exa_enabled"] is True
    assert bundle["apitube_enabled"] is True


def test_today_http_does_not_read_stored_evidence(monkeypatch):
    from app import main
    from app.services import feed_first_live

    def _boom():
        raise AssertionError("stored published evidence must not back /today")

    monkeypatch.setattr(main, "published_evidence", _boom)
    monkeypatch.setattr(feed_first_live, "live_feed_bundle", lambda **kwargs: _stub_live_bundle())
    monkeypatch.setattr("app.services.clock.utc_now", lambda: datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc))
    page = TestClient(main.app).get("/today")
    assert page.status_code == 200
    assert "Fall Creek expands blueberry nursery harvest" in page.text
    assert "14 million blueberry plants after 10 years" not in page.text
    assert "not a live multi-lane poll" not in page.text


def _geo_entities():
    return [
        *_entities(),
        {"id": "geography-spain", "name": "Spain", "entity_type": "geography", "status": "active"},
        {"id": "geography-peru", "name": "Peru", "entity_type": "geography", "status": "active"},
        {"id": "company-hortifrut", "name": "Hortifrut", "entity_type": "company", "status": "active"},
    ]


def test_live_rows_tag_named_geography_and_filter():
    spain = _record(id="ev-spain")
    peru = _record(
        id="ev-peru",
        title="Peru blueberry export volumes rise",
        geography_ids=["geography-peru"],
    )
    feed = build_feed(
        evidence=[spain, peru],
        entities=_geo_entities(),
        state=empty_state(),
        filters=parse_filters({"window": "30d", "geography": "geography-spain"}),
        today=date(2026, 6, 1),
    )
    assert [item["id"] for item in feed["cards"]] == ["ev-spain"]
    assert feed["cards"][0]["geography_chips"][0]["name"] == "Spain"
    assert {row["id"] for row in feed["geography_options"]} == {"geography-peru", "geography-spain"}
    restored = parse_filters({"window": "30d", "geography": "geography-spain"})
    assert restored["geography"] == "geography-spain"


def test_live_collector_tags_spain_and_official_first_party(tmp_path: Path):
    today = date(2026, 9, 21)
    now = datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc)
    google = MemoryProvider(
        hits_by_query_id={
            "today:blueberry:global:30d": [_same_day_hit()],
            "today:official:hortifrut.com:24h": [
                _same_day_hit(
                    title="Hortifrut reports new blueberry plantings",
                    url="https://www.hortifrut.com/news/plantings",
                    source_domain="hortifrut.com",
                    origin_publisher_url="https://www.hortifrut.com/news/plantings",
                    origin_publisher_name="Hortifrut",
                    snippet="The company expands blueberry acreage in Spain.",
                    query_id="today:official:hortifrut.com:24h",
                )
            ],
        }
    )
    bundle = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_geo_entities(),
        sources=[],
        refresh=True,
        today=today,
        now=now,
        google_provider=google,
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        enable_perplexity=False,
        enable_exa=False,
        enable_apitube=False,
        official_hosts={"hortifrut.com"},
        official_host_map={"hortifrut.com": "company-hortifrut"},
    )
    titles = {row["title"]: row for row in bundle["records"]}
    fall_creek = titles["Fall Creek expands blueberry nursery harvest after new planting"]
    hortifrut = titles["Hortifrut reports new blueberry plantings"]
    assert "geography-spain" in fall_creek["geography_ids"]
    assert hortifrut["source_type"] == "company_website"
    assert hortifrut["acquisition_lane"] == "official_site"
    assert "company-hortifrut" in hortifrut["entity_ids"]
    assert "geography-spain" in hortifrut["geography_ids"]
    assert "official_site" in bundle["lanes"]
    assert bundle["stats"]["official_hits"] >= 1
    assert bundle["stats"]["official_hosts_polled"] >= 1

    cached = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_geo_entities(),
        sources=[],
        refresh=False,
        today=today,
        now=now,
        google_provider=MemoryProvider(hits_by_query_id={}),
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        enable_perplexity=False,
        enable_exa=False,
        enable_apitube=False,
    )
    assert all(row.get("geography_ids") for row in cached["records"])


def test_us_abbreviation_tags_united_states():
    from app.services.feed_first_live import match_geography_ids

    entities = [
        {
            "id": "geography-united-states",
            "name": "United States",
            "entity_type": "geography",
        }
    ]
    assert match_geography_ids("U.S. blueberry prices rise", entities) == [
        "geography-united-states"
    ]


def test_official_site_queries_stay_bounded():
    hosts = {f"grower{i}.example" for i in range(40)}
    queries = today_official_site_queries(hosts)
    assert len(queries) <= OFFICIAL_SITE_HOST_CAP
    assert any(query.id.startswith("today:official:hortifrut.com") for query in queries)
    assert all("site:" in query.text for query in queries)
