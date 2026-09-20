"""P1 leftovers that do not need Johnny: muted, PDF, gallery, cascade, corroboration."""

from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.feed_first import (
    apply_decision,
    build_feed,
    extract_statements,
    load_state,
    parse_filters,
    set_entity_tier,
)
from app.services.feed_first_live import (
    cost_cascade_decision,
    live_feed_bundle,
    match_entity_ids,
)
from app.services.feed_first_reader import (
    bakeoff_report,
    extract_article_images,
    extract_pdf_text,
    looks_like_pdf,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider


def _record(**overrides):
    base = {
        "id": "ev-leftover",
        "status": "published",
        "title": "Fall Creek Spain reaches 14 million blueberry plants after 10 years",
        "summary": "Fall Creek marked 10 years in Spain and reports 14 million plants.",
        "source_name": "FreshPlaza",
        "source_type": "trade_press",
        "source_url": "https://example.test/fall-creek-spain",
        "published_date": "2026-05-26",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek-farm-and-nursery"],
        "cluster_sources": ["befve.com"],
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


def test_muted_drops_from_default_today_but_stays_searchable(tmp_path):
    record = _record()
    set_entity_tier(
        tmp_path,
        entity_id="company-fall-creek-farm-and-nursery",
        tier="muted",
    )
    state = load_state(tmp_path)
    hidden = build_feed(
        evidence=[record],
        entities=_entities(),
        state=state,
        filters=parse_filters({}),
        today=date(2026, 5, 26),
    )
    assert hidden["cards"] == []
    searched = build_feed(
        evidence=[record],
        entities=_entities(),
        state=state,
        filters=parse_filters({"q": "Fall Creek"}),
        today=date(2026, 5, 26),
    )
    assert [row["id"] for row in searched["cards"]] == [record["id"]]
    by_tier = build_feed(
        evidence=[record],
        entities=_entities(),
        state=state,
        filters=parse_filters({"tier": "muted"}),
        today=date(2026, 5, 26),
    )
    assert by_tier["cards"][0]["muted"] is True
    down = apply_decision(tmp_path, item_id=record["id"], action="thumbs_down", evidence=[record])
    assert down["muted_world"] is False


def test_muted_ids_are_skipped_in_live_entity_match():
    text = "Fall Creek expands blueberry nursery harvest"
    assert match_entity_ids(text, _entities()) == ["company-fall-creek-farm-and-nursery"]
    assert (
        match_entity_ids(
            text,
            _entities(),
            skip_ids=["company-fall-creek-farm-and-nursery"],
        )
        == []
    )


def test_following_keeps_muted_rows_searchable():
    from app.services.seed_roster import following_model

    model = following_model([], q="Fall Creek")
    assert model["rows"]
    target = model["rows"][0]["id"]
    muted = following_model(
        [],
        q=model["rows"][0]["canonical_name"],
        entity_tiers={target: "muted"},
    )
    assert muted["rows"]
    assert muted["rows"][0]["muted"] is True


def test_pdf_text_route_is_honest():
    pdf = (
        b"%PDF-1.1\nBT\n(Fall Creek nursery volumes rose this season in Spain.) Tj\nET\n"
    )
    assert looks_like_pdf("https://example.test/brief.pdf", body=pdf)
    passages = extract_pdf_text(pdf)
    assert passages
    assert "Fall Creek nursery volumes rose this season" in passages[0]
    assert extract_pdf_text(b"<html>not a pdf</html>") == []


def test_multi_image_extract_skips_logos():
    html = (
        "<p>Wish Farms cut strawberry inspection time by 70 percent this season after the Clarifresh rollout.</p>"
        '<meta property="og:image" content="https://cdn.example.test/hero.jpg">'
        '<img src="https://cdn.example.test/pack-two.jpg">'
        '<img src="https://logo.example.test/brand-logo.png">'
    )
    urls = [row["url"] for row in extract_article_images(html)]
    assert "https://cdn.example.test/hero.jpg" in urls
    assert "https://cdn.example.test/pack-two.jpg" in urls
    assert all("logo" not in url for url in urls)


def test_statements_link_corroboration_without_merging_support():
    rows = extract_statements(_record())
    assert rows
    assert rows[0]["supporting_passages"]
    names = [row["name"] for row in rows[0]["corroborating_sources"]]
    assert "befve.com" in names
    assert rows[0]["corroborating_sources"][0]["independent"] == "true"


def test_cost_cascade_skips_secondary_when_primary_is_thick(tmp_path):
    class CountingExa:
        name = "exa"

        def __init__(self):
            self.calls = 0

        def discover(self, query):
            self.calls += 1
            return [
                _same_day_hit(
                    title="Hortifrut blueberry harvest volumes rise in Peru this morning",
                    url="https://example.test/hortifrut-exa",
                    origin_publisher_url="https://example.test/hortifrut-exa",
                    provider="exa",
                    query_id=getattr(query, "id", "today:perplexity:all:global:24h"),
                )
            ]

    primary = [
        _same_day_hit(
            title=f"Fall Creek blueberry nursery harvest briefing {index} in Spain",
            url=f"https://example.test/fc-primary-{index}",
            origin_publisher_url=f"https://example.test/fc-primary-{index}",
        )
        for index in range(8)
    ]
    exa = CountingExa()
    bundle = live_feed_bundle(
        inbox_dir=tmp_path,
        entities=_entities(),
        sources=[],
        refresh=True,
        today=date(2026, 9, 21),
        now=datetime(2026, 9, 21, 15, 0, tzinfo=timezone.utc),
        google_provider=MemoryProvider(hits_by_query_id={"today:blueberry:global:30d": primary}),
        specialist_provider=MemoryProvider(hits_by_query_id={}),
        enable_perplexity=False,
        exa_provider=exa,
        enable_apitube=False,
    )
    assert bundle["cascade"]["secondary_fired"] is False
    assert bundle["cascade"]["reason"] == "primary_sufficient"
    assert exa.calls == 0
    assert "exa" not in bundle["lanes"]


def test_cost_cascade_fires_secondary_when_primary_is_thin():
    decision = cost_cascade_decision(primary_unique=1, secondary_available=True)
    assert decision["secondary_fired"] is True
    assert decision["reason"] == "primary_thin"


def test_bakeoff_audit_does_not_invent_vendors():
    report = bakeoff_report(
        firecrawl=False,
        jina=False,
        cascade={"reason": "primary_sufficient"},
        stats={"week": 12},
    )
    assert report["coverage_audit"]["unique_finds"] == 12
    assert "unused" in report["firecrawl"]["notes"].casefold()


def test_non_english_items_are_held_off_today():
    english = _record()
    chinese = _record(
        id="ev-zh",
        title="莓果龍頭進中國被偷光",
        summary="美國莓果龍頭進中國市場",
    )
    feed = build_feed(
        evidence=[english, chinese],
        entities=_entities(),
        state={"decisions": {}, "entity_tiers": {}, "statements": {}},
        filters=parse_filters({}),
        today=date(2026, 5, 26),
    )
    assert [row["id"] for row in feed["cards"]] == [english["id"]]
    assert feed["held_non_english"] == 1
    assert "not in English" in feed["disclosure"]


def test_off_topic_passages_do_not_enter_the_reader():
    from app.services.feed_first import captured_passages

    record = _record(
        title="Hoddys launches South Island berry production",
        summary="Hoddys Fruit Co planted strawberries in New Zealand.",
        article={
            "paragraphs": [
                {"text": "When Lance Double started his solar business in 2009, he was a one-man band."},
                {"text": "Hoddys Fruit Co planted seven hectares of strawberries on the South Island this season."},
            ]
        },
    )
    passages = captured_passages(record)
    blob = " ".join(passages).casefold()
    assert "strawberry" in blob or "hoddys" in blob
    assert "solar business" not in blob


def test_empty_copy_follows_selected_window():
    from app.services.feed_first import empty_feed_copy

    today = empty_feed_copy("today", date(2026, 9, 20))
    month = empty_feed_copy("30d", date(2026, 9, 20))
    assert "today" in today["title"].casefold()
    assert "30 days" in month["title"]
    assert "same-day qualified" not in month["body"]


def test_today_and_ops_expose_leftover_contracts():
    today = TestClient(app).get("/today")
    assert today.status_code == 200
    assert 'href="#today-feed"' in today.text
    assert "bos-skip" in today.text
    css = Path("app/static/berry_os.css").read_text(encoding="utf-8")
    assert ":focus-visible" in css
    html = Path("app/templates/feed_first_today.html").read_text(encoding="utf-8")
    assert "data-gallery-next" in html
    assert "data-story-thread" in html
    assert "data-corroboration" in html
    ops = TestClient(app).get("/research-ops")
    assert ops.status_code == 200
    assert "data-cost-cascade" in ops.text
    assert "data-coverage-audit" in ops.text
    assert "Cost cascade" in ops.text
    css = Path("app/static/berry_os.css").read_text(encoding="utf-8")
    assert "repeat(auto-fill, minmax(260px, 1fr))" in css
    assert "repeat(auto-fill, minmax(180px, 1fr))" in css
    following = TestClient(app).get("/following")
    assert "bos-card is-tile" in following.text
    assert "URL-status rows repaired" not in following.text
