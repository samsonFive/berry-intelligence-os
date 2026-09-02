"""Global Week Intelligence V1 -- live weekly editorial plane."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.global_week import (
    DEFAULT_WINDOW,
    LIVE_WINDOWS,
    TRUST_LABEL,
    BriefStatement,
    WeekItem,
    berries_mentioned,
    compose_edition,
    diverse_take,
    find_week_hit_by_url,
    generate_week_brief,
    run_week_intelligence,
    week_catch_net_queries,
    week_queries,
)
from app.services.industry_pulse.matrix import generate_pulse_queries, query_count, regional_language_queries
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider
from app.services.industry_pulse.qualify import EDITORIAL_COMPETITOR, EDITORIAL_VARIETY, SOURCE_GOV_AG, SOURCE_TRADE

REPO = Path(__file__).resolve().parents[1]


def _hit(**overrides) -> DiscoveryHit:
    base = dict(
        title="Fall Creek unveils new blueberry cultivar in Chile",
        url="https://example.com/a",
        source_domain="example.com",
        published_date="2026-08-30",
        snippet="Fall Creek Farm & Nursery announced a new managed variety for Peru and Chile growers.",
        query_id="pulse:blueberry:americas:7d",
        query_text="",
        geography="americas",
        berry="blueberry",
        topic="industry_pulse",
        provider="memory",
        origin_publisher_name="FreshPlaza",
        origin_publisher_url="https://example.com/a",
    )
    base.update(overrides)
    return DiscoveryHit(**base)


def _item(**overrides) -> WeekItem:
    base = dict(
        title="Fall Creek unveils new blueberry cultivar",
        url="https://example.com/a",
        publisher="FreshPlaza",
        published_date="2026-08-30",
        captured_at="2026-09-01T00:00:00+00:00",
        snippet="A new managed variety.",
        berry="blueberry",
        berries=("blueberry",),
        geography="americas",
        geographies=("americas",),
        provider="memory",
        providers=("memory",),
        query_id="pulse:blueberry:americas:7d",
        qualify_reasons=["named company Fall Creek", "explicit blueberry crop"],
        editorial_topic=EDITORIAL_VARIETY,
        source_context=SOURCE_TRADE,
        specialist=True,
        official=False,
        explicit_event=True,
        named_entity_count=1,
        corroboration=2,
        rank_reasons=("Named competitor, cultivar, or regulatory event",),
        trust_label=TRUST_LABEL,
    )
    base.update(overrides)
    return WeekItem(**base)


def test_industry_pulse_matrix_stays_at_32():
    assert query_count() == 32
    assert len(generate_pulse_queries()) == 32


def test_week_queries_add_bounded_language_and_retail_only():
    rows = week_queries()
    language = regional_language_queries()
    assert len(language) == 5
    assert {row.geography for row in language} == {"americas", "europe", "africa", "apac"}
    assert len(rows) == 32 + 5 + 1
    assert any(row.id == "topic:retail:global" for row in rows)
    assert any(row.id == "lang:apac:zh" for row in rows)
    assert any(row.id == "lang:apac:ja" for row in rows)
    assert all(row.kind in {"berry_geography", "topic_global", "regional_language"} for row in rows)


def test_week_catch_net_includes_apac_without_doubling_the_matrix():
    queries = [row.with_window("7d") for row in week_queries()]
    selected = week_catch_net_queries(queries)
    geos = {row.geography for row in selected if row.kind == "berry_geography"}
    assert "apac" in geos
    assert "americas" in geos
    assert len(selected) < len(queries)


def test_windows_are_24h_7d_30d_default_7d():
    assert LIVE_WINDOWS == ("24h", "7d", "30d")
    assert DEFAULT_WINDOW == "7d"


def test_berries_mentioned_does_not_hide_blackberry_behind_blueberry():
    text = "Blackberry growers in Mexico expand primocane acreage"
    assert berries_mentioned(text) == ("blackberry",)
    both = berries_mentioned("Blueberry and raspberry harvest in Spain")
    assert "blueberry" in both
    assert "raspberry" in both


def test_query_berry_does_not_force_a_second_crop():
    text = "Two new strawberry varieties will bring sweeter berries to the winter market"
    assert berries_mentioned(text, query_berry="blackberry") == ("strawberry",)


def test_query_geography_does_not_relabel_a_named_place():
    from app.services.global_week import geographies_mentioned

    assert geographies_mentioned("University of Arkansas blackberry cultivar award", query_geography="africa") == ()
    assert geographies_mentioned("Blueberry growers in Chile report a strong season", query_geography="africa") == (
        "americas",
    )
    assert geographies_mentioned("Record heatwaves help British blueberry harvest") == ("europe",)
    items = [
        _item(title=f"Story {i}", url=f"https://example.com/{i}", publisher="Same Press", published_date=f"2026-08-3{i}")
        for i in range(1, 6)
    ]
    items.append(_item(title="Other", url="https://other.example/x", publisher="Other Press"))
    taken = diverse_take(items, limit=8, max_per_publisher=2)
    same = [item for item in taken if item.publisher == "Same Press"]
    assert len(same) == 2
    assert any(item.publisher == "Other Press" for item in taken)


def test_ranking_is_lexicographic_not_a_score():
    weak_recent = _item(
        title="Generic berry note",
        url="https://example.com/weak",
        publisher="Blog",
        published_date="2026-09-01",
        explicit_event=False,
        official=False,
        specialist=False,
        corroboration=1,
        named_entity_count=0,
        editorial_topic=None,
    )
    official_older = _item(
        title="CPVO grants plant breeders rights",
        url="https://example.com/pbr",
        publisher="CPVO",
        published_date="2026-08-20",
        explicit_event=True,
        official=True,
        specialist=False,
        corroboration=1,
        named_entity_count=0,
        editorial_topic=EDITORIAL_VARIETY,
        source_context=SOURCE_GOV_AG,
    )
    edition = compose_edition(
        [weak_recent, official_older],
        window="7d",
        searched_at="2026-09-01T00:00:00+00:00",
        latency_seconds=0.1,
        raw_hit_count=2,
        unique_count=2,
        provider_telemetry={"memory": {"queries_issued": 1, "hits_returned": 2, "errors": 0}},
        query_failures=[],
        query_count=1,
    )
    assert edition.what_matters[0].url == "https://example.com/pbr"
    dumped = edition.as_dict()
    assert "importance_score" not in str(dumped)
    assert "priority score" not in str(dumped).lower()
    assert edition.what_matters[0].rank_reasons[0] == "Named competitor, cultivar, or regulatory event"


def test_compose_edition_reports_regions_and_berries_independently():
    items = [
        _item(geography="americas", geographies=("americas",), berry="blueberry", berries=("blueberry",)),
        _item(
            title="Spanish strawberry launch",
            url="https://example.com/eu",
            publisher="Revista",
            geography="europe",
            geographies=("europe",),
            berry="strawberry",
            berries=("strawberry",),
            editorial_topic=EDITORIAL_COMPETITOR,
        ),
    ]
    edition = compose_edition(
        items,
        window="7d",
        searched_at="2026-09-01T00:00:00+00:00",
        latency_seconds=0.2,
        raw_hit_count=2,
        unique_count=2,
        provider_telemetry={},
        query_failures=[],
        query_count=2,
    )
    assert edition.stats["regions"]["americas"] == 1
    assert edition.stats["regions"]["europe"] == 1
    assert edition.stats["regions"]["africa"] == 0
    assert edition.stats["regions"]["apac"] == 0
    assert edition.stats["berries"]["blueberry"] == 1
    assert edition.stats["berries"]["strawberry"] == 1
    assert edition.stats["berries"]["raspberry"] == 0
    assert edition.stats["berries"]["blackberry"] == 0
    assert "africa" in edition.weak_regions
    assert "apac" in edition.weak_regions
    assert "raspberry" in edition.weak_berries
    assert "blackberry" in edition.weak_berries
    assert edition.trust_label == TRUST_LABEL


def test_run_week_qualifies_dedupes_and_stays_live_unreviewed():
    duplicate = _hit()
    recipe = _hit(
        title="Strawberry shortcake recipe for the weekend",
        snippet="A dessert recipe with calories.",
        url="https://example.com/recipe",
        origin_publisher_url="https://example.com/recipe",
        berry="strawberry",
        geography="global",
    )
    provider = MemoryProvider(hits=[duplicate, duplicate, recipe])
    edition = run_week_intelligence(
        window="7d",
        providers=[provider],
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        entities=[{"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek Farm & Nursery", "entity_type": "company"}],
        varieties=[{"name": "Sekoya Grande", "aliases": ["Sekoya"]}],
        sources=[],
    )
    assert edition.window == "7d"
    assert edition.trust_label == TRUST_LABEL
    urls = {item.url for item in edition.items}
    assert "https://example.com/a" in urls
    assert "https://example.com/recipe" not in urls
    assert all(item.trust_label == TRUST_LABEL for item in edition.items)


def test_run_week_keeps_older_dates_out_of_what_matters():
    stale = _hit(
        title="USDA strawberry production expands with newer varieties",
        snippet="Official USDA report on strawberry acreage and new cultivars.",
        url="https://example.com/usda/article",
        origin_publisher_url="https://example.com/usda/article",
        published_date="2021-05-19",
        source_domain="ers.usda.gov",
        origin_publisher_name="USDA",
    )
    current = _hit()
    provider = MemoryProvider(hits=[stale, current])
    edition = run_week_intelligence(
        window="7d",
        providers=[provider],
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        entities=[{"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek Farm & Nursery", "entity_type": "company"}],
        varieties=[],
        sources=[],
    )
    matter_urls = {item.url for item in edition.what_matters}
    older_urls = {item.url for item in edition.older_circulating}
    assert "https://example.com/a" in matter_urls
    assert "https://example.com/usda/article" not in matter_urls
    assert "https://example.com/usda/article" in older_urls


def test_run_week_keeps_homepage_results_when_that_is_all_the_provider_gave():
    home = _hit(
        url="https://www.ers.usda.gov/",
        origin_publisher_url="https://www.ers.usda.gov/",
        source_domain="ers.usda.gov",
        wrapper_url="https://news.google.com/articles/abc",
    )
    provider = MemoryProvider(hits=[home])
    edition = run_week_intelligence(
        window="7d",
        providers=[provider],
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        entities=[{"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek Farm & Nursery", "entity_type": "company"}],
        varieties=[],
        sources=[],
    )
    urls = {item.url for item in edition.items}
    assert "https://news.google.com/articles/abc" in urls


def test_run_week_rejects_unsupported_window():
    import pytest

    with pytest.raises(ValueError):
        run_week_intelligence(window="90d", providers=[])


def test_run_week_survives_a_failing_provider():
    class Boom:
        name = "boom"

        def discover(self, query):
            raise RuntimeError("provider down")

    edition = run_week_intelligence(window="7d", providers=[Boom()], entities=[], varieties=[], sources=[])
    assert edition.provider_telemetry["boom"]["errors"] >= 1
    assert edition.items == []


def test_generate_week_brief_grounds_every_statement():
    items = [_item()]

    class FakeResult:
        parsed = {"statements": [{"text": "Fall Creek unveiled a new cultivar.", "source_ids": ["live-0"]}]}

    statements = generate_week_brief(items, completer=lambda *a, **k: FakeResult())
    assert statements == (BriefStatement(text="Fall Creek unveiled a new cultivar.", source_ids=("live-0",)),)


def test_generate_week_brief_drops_ungrounded_and_private_material():
    items = [_item()]

    class FakeResult:
        parsed = {"statements": [{"text": "Internal assessment says acquire them.", "source_ids": ["secret-1"]}]}

    assert generate_week_brief(items, completer=lambda *a, **k: FakeResult()) == ()
    assert generate_week_brief([], completer=lambda *a, **k: FakeResult()) == ()
    assert generate_week_brief(items, completer=None) == ()


def test_find_week_hit_by_url_matches_qualifying_item():
    provider = MemoryProvider(hits=[_hit()])
    found = find_week_hit_by_url(
        url="https://example.com/a",
        window="7d",
        providers=[provider],
        entities=[{"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek Farm & Nursery", "entity_type": "company"}],
        varieties=[],
        sources=[],
        query_id="pulse:blueberry:americas:7d",
    )
    assert found is not None
    assert found.qualifying is True


def test_week_shell_does_not_fetch_and_matches_stakeholder_chrome(monkeypatch):
    def boom(**kwargs):
        raise AssertionError("shell must not run live discovery")

    monkeypatch.setattr("app.main.run_week_intelligence", boom)
    page = TestClient(app).get("/week")
    assert page.status_code == 200
    html = page.text
    assert "What changed this week?" in html
    assert "LIVE / UNREVIEWED" in html
    assert "This week" in html
    assert "stakeholder.css" in html
    assert 'class="sh-nav' in html
    assert "industry-pulse" not in html
    assert "elapsed_ms" not in html
    assert "Publication Review" not in html
    assert "Coverage Assurance" not in html
    assert "Collection Operations" not in html
    assert "/week/live?window=7d" in html


def test_week_live_renders_edition_and_keeps_trust_separate(monkeypatch):
    edition = compose_edition(
        [_item()],
        window="7d",
        searched_at="2026-09-01T00:00:00+00:00",
        latency_seconds=1.2,
        raw_hit_count=4,
        unique_count=2,
        provider_telemetry={"memory": {"queries_issued": 1, "hits_returned": 4, "errors": 0}},
        query_failures=[],
        query_count=1,
    )
    monkeypatch.setattr("app.main.run_week_intelligence", lambda **kwargs: edition)
    monkeypatch.setattr("app.main.generate_week_brief", lambda *a, **k: ())
    page = TestClient(app).get("/week/live", params={"window": "7d"})
    assert page.status_code == 200
    html = page.text
    assert "What matters most" in html
    assert "Older items still in this live search" in html
    assert "Competitor moves" in html
    assert "Varieties / genetics" in html
    assert "By region" in html
    assert "By berry" in html
    assert "Americas" in html
    assert "APAC" in html
    assert "Blackberry" in html
    assert "Raspberry" in html
    assert "LIVE / UNREVIEWED" in html
    assert "Send to review" in html
    assert "FreshPlaza" in html
    assert "via memory" in html
    assert "importance score" not in html.lower()
    assert "base.html" not in html or "base_stakeholder" in Path(REPO / "app" / "templates" / "week.html").read_text(encoding="utf-8")


def test_week_fragment_is_edition_only(monkeypatch):
    edition = compose_edition(
        [_item()],
        window="7d",
        searched_at="2026-09-01T00:00:00+00:00",
        latency_seconds=0.4,
        raw_hit_count=1,
        unique_count=1,
        provider_telemetry={},
        query_failures=[],
        query_count=1,
    )
    monkeypatch.setattr("app.main.run_week_intelligence", lambda **kwargs: edition)
    monkeypatch.setattr("app.main.generate_week_brief", lambda *a, **k: ())
    page = TestClient(app).get("/week/live", params={"window": "7d", "fragment": "1"})
    assert page.status_code == 200
    assert "What matters most" in page.text
    assert "<html" not in page.text.lower()


def test_send_to_review_uses_publication_intake_only(monkeypatch):
    from app.services.industry_pulse.intake import IntakeSummary

    captured: dict = {}

    def fake_find(**kwargs):
        hit = _hit()
        hit.qualifying = True
        return hit

    def fake_intake(hits, **kwargs):
        captured["hits"] = hits
        captured["kwargs"] = kwargs
        return IntakeSummary(drafts_created=1)

    monkeypatch.setattr("app.main.find_week_hit_by_url", fake_find)
    monkeypatch.setattr("app.main.intake_qualified_hits", fake_intake)
    resp = TestClient(app).post(
        "/week/review",
        data={"url": "https://example.com/a", "window": "7d", "query_id": "pulse:blueberry:americas:7d"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "promoted=promoted" in resp.headers["location"]
    assert captured["hits"][0].url == "https://example.com/a"


def test_today_and_nav_point_at_this_week():
    page = TestClient(app).get("/today")
    assert page.status_code == 200
    assert ">This week<" in page.text
    assert "What changed this week?" in page.text
    assert "stakeholder.css" in page.text


def test_week_template_is_stakeholder_shell_not_workbench():
    week = (REPO / "app" / "templates" / "week.html").read_text(encoding="utf-8")
    assert 'extends "base_stakeholder.html"' in week
    assert 'extends "base.html"' not in week
    nav = (REPO / "app" / "templates" / "_stakeholder_nav.html").read_text(encoding="utf-8")
    assert 'href="/week"' in nav
    static = (REPO / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert "/week/live" not in static
    assert "week.html" not in static
