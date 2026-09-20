"""P0 acceptance matrix for the feed-first path. Not a Gate 5 release."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.feed_first import (
    apply_decision,
    build_feed,
    empty_state,
    extract_statements,
    load_state,
    parse_filters,
    set_entity_tier,
)
from app.services.feed_first_live import live_feed_bundle
from app.services.seed_roster import build_roster, roster_counts


def _record(**overrides):
    base = {
        "id": "ev-accept",
        "status": "published",
        "title": "Fall Creek Spain reaches 14 million blueberry plants after 10 years",
        "summary": "Fall Creek marked 10 years in Spain and reports 14 million plants.",
        "source_name": "FreshPlaza",
        "source_type": "trade_press",
        "source_url": "https://example.test/fall-creek-spain",
        "published_date": "2026-05-26",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek-farm-and-nursery"],
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


def test_p0_today_is_front_door_and_not_review_ops():
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    assert "data-feed-first-today" in page.text
    assert "Publication Review" not in page.text


def test_p0_thumbs_persist_undo_idempotent_and_do_not_mute(tmp_path):
    inbox = tmp_path / "inbox"
    record = _record()
    first = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    retry = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    assert [row["id"] for row in retry["statements"]] == [row["id"] for row in first["statements"]]
    down = apply_decision(inbox, item_id=record["id"], action="thumbs_down", evidence=[record])
    assert down["muted_world"] is False
    assert down["statements"] == []
    undo = apply_decision(inbox, item_id=record["id"], action="clear_reaction", evidence=[record])
    assert undo["decision"]["reaction"] is None


def test_p0_save_does_not_imply_trust(tmp_path):
    inbox = tmp_path / "inbox"
    record = _record()
    saved = apply_decision(inbox, item_id=record["id"], action="save", evidence=[record])
    assert saved["decision"]["saved"] is True
    assert saved["statements"] == []


def test_p0_statement_has_exact_support_and_keeps_original(tmp_path):
    from app.services.feed_first import mutate_statement

    inbox = tmp_path / "inbox"
    record = _record()
    applied = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    statement = applied["statements"][0]
    assert statement["supporting_passages"]
    assert statement["supporting_passages"][0]
    original = statement["original_extraction_text"]
    edited = mutate_statement(
        inbox, statement_id=statement["id"], action="edit", text="Spain nursery now reports 14 million plants."
    )
    assert edited["original_extraction_text"] == original
    assert edited["statement_text"] != original


def test_p0_tier_does_not_change_verification(tmp_path):
    inbox = tmp_path / "inbox"
    set_entity_tier(inbox, entity_id="company-fall-creek-farm-and-nursery", tier="tier1")
    feed = build_feed(
        evidence=[_record()],
        entities=[
            {
                "id": "company-fall-creek-farm-and-nursery",
                "name": "Fall Creek",
                "status": "active",
                "verification_status": "verified-secondary",
            }
        ],
        state=load_state(inbox),
        filters=parse_filters({"tier": "tier1", "window": "30d"}),
        today=date(2026, 6, 1),
    )
    assert feed["cards"][0]["entities"][0]["verification_status"] == "verified-secondary"
    assert feed["cards"][0]["entities"][0]["tier"] == "tier1"


def test_p0_blocked_body_yields_no_statements():
    blocked = _record(
        summary="Please log in to continue. Subscribe to continue reading.",
        article={"paragraphs": [{"text": "Please log in to continue. Subscribe to continue reading."}]},
    )
    assert extract_statements(blocked) == []


def test_p0_seed_not_bulk_trusted_and_registries_excluded():
    counts = roster_counts(build_roster([]))
    assert counts["tracked_companies"] == 145
    assert counts["registries"] == 6
    assert counts["candidates"] == 61
    roster = build_roster([])
    assert all(row["status"] == "unverified" for row in roster if row["candidate"])
    assert all(row["competitor"] is False for row in roster if row["is_registry"])


def test_p0_reader_keyboard_help_and_research_ops_are_not_home():
    today = TestClient(app).get("/today")
    assert "data-keyboard-help" in today.text
    ops = TestClient(app).get("/research-ops")
    assert ops.status_code == 200
    assert "data-feed-first-ops" in ops.text
    assert "CatchAll" in ops.text


def test_p1_feed_first_company_profile_is_berry_os():
    page = TestClient(app).get("/entities/company/company-fall-creek-farm-and-nursery")
    assert page.status_code == 200
    assert "data-feed-first-company" in page.text
    assert "From Today thumbs-up" in page.text
    assert "Create 90-day report" not in page.text
    explicit = TestClient(app).get("/entities/company/company-fall-creek-farm-and-nursery?view=feed")
    assert "data-feed-first-company" in explicit.text
    legacy = TestClient(app).get("/entities/company/company-fall-creek-farm-and-nursery?view=legacy")
    assert legacy.status_code == 200
    assert "data-feed-first-company" not in legacy.text


def test_p1_people_saved_landscapes_and_reader_help_are_in_the_shell():
    people = TestClient(app).get("/people")
    assert people.status_code == 200
    assert "data-feed-first-people" in people.text
    assert "provider-unavailable" in people.text
    assert "/people/person-" in people.text
    saved = TestClient(app).get("/saved")
    assert saved.status_code == 200
    assert "data-feed-first-saved" in saved.text
    assert "Save is a board, not trust" in saved.text
    landscapes = TestClient(app).get("/landscapes?view=feed")
    assert landscapes.status_code == 200
    assert "data-feed-first-landscapes" in landscapes.text
    ops = TestClient(app).get("/research-ops")
    assert "Reader bake-off" in ops.text
    assert "Official social" in ops.text
    today = TestClient(app).get("/today")
    assert "data-viewport-shell" in today.text
    css = TestClient(app).get("/static/berry_os.css")
    assert "@media (min-width: 2560px)" in css.text
    assert "@media (min-width: 1920px)" in css.text
    assert "@media (max-width: 1280px)" in css.text
    statements = TestClient(app).get("/statements")
    assert statements.status_code == 200
    assert "data-feed-first-statements" in statements.text
    week = TestClient(app).get("/week?view=feed")
    assert week.status_code == 200
    assert "data-feed-first-week" in week.text
    assert "stored August evidence" in week.text
    legacy_week = TestClient(app).get("/week")
    assert "data-feed-first-week" not in legacy_week.text
    ops = TestClient(app).get("/research-ops")
    assert "Rollback rehearsal" in ops.text
    today = TestClient(app).get("/today")
    assert 'href="/statements"' in today.text
    assert 'href="/week?view=feed"' in today.text


def test_p0_filter_tier1_crop_unread_30d_restores_url_and_facets(tmp_path):
    from urllib.parse import parse_qsl

    from app.services.feed_first import filters_query

    inbox = tmp_path / "inbox"
    set_entity_tier(inbox, entity_id="company-fall-creek-farm-and-nursery", tier="tier1")
    keep = _record(id="keep-tier1-unread")
    wrong_crop = _record(
        id="wrong-crop",
        title="Fall Creek strawberry trial note",
        berry_ids=["berry-strawberry"],
    )
    aged = _record(id="too-old", published_date="2026-03-01")
    other = _record(
        id="other-company",
        title="Hortifrut blueberry harvest volumes rise",
        entity_ids=["company-hortifrut"],
    )
    apply_decision(inbox, item_id=other["id"], action="read", evidence=[other])
    entities = [
        {
            "id": "company-fall-creek-farm-and-nursery",
            "name": "Fall Creek",
            "status": "active",
            "verification_status": "verified-secondary",
        },
        {
            "id": "company-hortifrut",
            "name": "Hortifrut",
            "status": "active",
            "verification_status": "unverified",
        },
    ]
    filters = parse_filters({"tier": "tier1", "crop": "blueberry", "state": "unread", "window": "30d"})
    feed = build_feed(
        evidence=[keep, wrong_crop, aged, other],
        entities=entities,
        state=load_state(inbox),
        filters=filters,
        today=date(2026, 6, 1),
    )
    assert [card["id"] for card in feed["cards"]] == ["keep-tier1-unread"]
    assert feed["facet_counts"]["total"] == 3
    assert feed["facet_counts"]["crop"]["blueberry"] == 2
    assert feed["facet_counts"]["crop"]["strawberry"] == 1
    assert feed["facet_counts"]["tier"]["tier1"] == 2
    assert feed["facet_counts"]["state"]["unread"] == 2
    restored = parse_filters(dict(parse_qsl(filters_query(filters))))
    assert restored["tier"] == "tier1"
    assert restored["crop"] == "blueberry"
    assert restored["state"] == "unread"
    assert restored["window"] == "30d"
    page = TestClient(app).get("/today?tier=tier1&crop=blueberry&state=unread&window=30d")
    assert page.status_code == 200
    assert 'name="tier"' in page.text
    assert "value=\"tier1\" selected" in page.text or "value='tier1' selected" in page.text
    assert "value=\"blueberry\" selected" in page.text
    assert "value=\"unread\" selected" in page.text
    assert "value=\"30d\" selected" in page.text
    assert "data-facet-counts" in page.text
    assert "data-filter-chips" in page.text
    assert 'data-clear-filter="crop"' in page.text
    assert 'data-clear-filter="window"' in page.text
    chips = feed["filter_chips"]
    assert {row["key"] for row in chips} >= {"tier", "crop", "state", "window"}
    crop_chip = next(row for row in chips if row["key"] == "crop")
    assert "crop=" not in crop_chip["href"]
    assert "tier=tier1" in crop_chip["href"]


def test_p0_statement_important_demote_remove_restore(tmp_path):
    from app.services.feed_first import mutate_statement, statements_index

    inbox = tmp_path / "inbox"
    record = _record()
    applied = apply_decision(inbox, item_id=record["id"], action="thumbs_up", evidence=[record])
    statement_id = applied["statements"][0]["id"]
    important = mutate_statement(inbox, statement_id=statement_id, action="important")
    assert important["importance_state"] == "important"
    demoted = mutate_statement(inbox, statement_id=statement_id, action="demote")
    assert demoted["importance_state"] == "demoted"
    removed = mutate_statement(inbox, statement_id=statement_id, action="remove")
    assert removed["statement_state"] == "removed"
    assert statement_id not in {row["id"] for row in statements_index(load_state(inbox))}
    restored = mutate_statement(inbox, statement_id=statement_id, action="restore")
    assert restored["statement_state"] == "trusted_editable"
    assert statement_id in {row["id"] for row in statements_index(load_state(inbox))}
    template = Path("app/templates/feed_first_today.html").read_text(encoding="utf-8")
    script = Path("app/static/feed_first.js").read_text(encoding="utf-8")
    assert 'data-statement-action="restore"' in template
    assert 'data-statement-action="restore"' in script


def test_p0_one_story_once_keeps_cluster_on_the_card():
    from app.services.today_relevance import collapse_story_clusters

    records = collapse_story_clusters(
        [
            {
                **_record(id="lead-wish"),
                "title": "Wish Farms and Clarifresh transform berry quality control",
                "source_url": "https://perishablenews.example/wish",
                "source_name": "Perishable News",
                "acquisition_lane": "specialist_rss",
            },
            {
                **_record(id="dup-wish"),
                "title": "Wish Farms and Clarifresh transform berry quality control",
                "source_url": "https://perishablenews.example/wish?utm_source=exa",
                "source_name": "Exa",
                "acquisition_lane": "exa",
            },
        ]
    )
    feed = build_feed(
        evidence=records,
        entities=[
            {
                "id": "company-fall-creek-farm-and-nursery",
                "name": "Fall Creek",
                "status": "active",
                "verification_status": "verified-secondary",
            }
        ],
        state=empty_state(),
        filters=parse_filters({"window": "30d"}),
        today=date(2026, 6, 1),
    )
    assert len(feed["cards"]) == 1
    card = feed["cards"][0]
    assert card["cluster_size"] == 2
    assert card["cluster_sources"] == ["perishablenews.example"]
    today = TestClient(app).get("/today")
    assert "cluster ×" in today.text or "Also seen via" in today.text or "data-feed-first-today" in today.text


def test_p0_unknown_date_does_not_masquerade_as_new():
    undated = _record(id="undated", published_date="")
    dated = _record(id="dated", published_date="2026-06-01")
    today_feed = build_feed(
        evidence=[undated, dated],
        entities=[
            {
                "id": "company-fall-creek-farm-and-nursery",
                "name": "Fall Creek",
                "status": "active",
                "verification_status": "verified-secondary",
            }
        ],
        state=empty_state(),
        filters=parse_filters({}),
        today=date(2026, 6, 1),
    )
    assert [card["id"] for card in today_feed["cards"]] == ["dated"]
    all_time = build_feed(
        evidence=[undated, dated],
        entities=[
            {
                "id": "company-fall-creek-farm-and-nursery",
                "name": "Fall Creek",
                "status": "active",
                "verification_status": "verified-secondary",
            }
        ],
        state=empty_state(),
        filters=parse_filters({"window": ""}),
        today=date(2026, 6, 1),
    )
    by_id = {card["id"]: card for card in all_time["cards"]}
    assert by_id["undated"]["date_uncertain"] is True
    assert by_id["dated"]["date_uncertain"] is False
    assert all_time["cards"][0]["id"] == "dated"


def test_p0_source_failure_is_recorded_without_dropping_history(tmp_path):
    from datetime import datetime, timezone

    from app.services.industry_pulse.providers import MemoryProvider
    from app.services.research_ops_health import public_lane_errors
    from tests.test_feed_first_gate1 import _entities, _same_day_hit

    class Boom:
        name = "perplexity"

        def discover(self, query):
            raise RuntimeError("EXA_API_KEY=sk-secret-must-not-leak")

    bundle = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=True,
        today=date(2026, 9, 21),
        now=datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc),
        google_provider=MemoryProvider(
            hits_by_query_id={"today:blueberry:global:24h": [_same_day_hit()]}
        ),
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        perplexity_provider=Boom(),
        enable_exa=False,
        enable_apitube=False,
    )
    assert bundle["records"]
    assert bundle["lane_errors"]
    public = public_lane_errors(bundle["lane_errors"])
    assert public[0]["provider"] == "perplexity"
    assert public[0]["error_class"] == "RuntimeError"
    leaked = " ".join(f"{row['provider']} {row['error_class']}" for row in public)
    assert "sk-secret" not in leaked
    assert "EXA_API_KEY" not in leaked


def test_p1_watch_coverage_and_ops_health_are_inspectable():
    from app.services.research_ops_health import research_ops_health
    from app.services.seed_roster import build_roster, roster_counts

    counts = roster_counts(build_roster([]))
    health = research_ops_health(
        bundle={
            "fetched_at": "2026-09-20T12:00:00+00:00",
            "lanes": ["google_news_rss", "specialist_rss", "perplexity"],
            "lane_errors": [{"provider": "perplexity", "error_class": "TimeoutError", "error": "TimeoutError: token=abcd"}],
            "stats": {"same_day": 1, "week": 4},
            "records": [
                {"cluster_size": 3, "title": "Wish Farms"},
                {"cluster_size": 1, "title": "Planasa"},
            ],
        },
        counts=counts,
    )
    assert health["watches"]["official_site_watches"] == 84
    assert health["watches"]["mention_watches"] == 145
    assert health["clusters"]["clustered_stories"] == 1
    assert health["clusters"]["extra_lane_hits"] == 2
    assert health["lane_errors"][0] == {"provider": "perplexity", "error_class": "TimeoutError"}
    ops = TestClient(app).get("/research-ops")
    assert ops.status_code == 200
    assert "data-watch-coverage" in ops.text
    assert "data-cluster-stats" in ops.text
    assert "data-lane-errors" in ops.text
    assert "official-site watches" in ops.text
    assert "Error class only" in ops.text
