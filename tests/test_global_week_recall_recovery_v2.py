"""Global Week Recall Recovery V2 -- information-universe activation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.authoritative_registries.classify import (
    AUTHORITATIVE_REGISTRY,
    DISCOVERY_PROVIDER,
    LAYER_OF,
    SPECIALIST_SOURCE,
)
from app.services.global_week import (
    retrieve_window_for,
    run_week_intelligence,
    week_apac_focus_queries,
    week_catch_net_queries,
    week_queries,
)
from app.services.industry_pulse.apitube import APITUBE_SETUP, ApiTubeSearchProvider
from app.services.industry_pulse.credentials import APITUBE_API_KEY_ENV
from app.services.industry_pulse.errors import ProviderAuthError
from app.services.industry_pulse.live_stack import optional_sync_discovery_providers, week_discovery_stack
from app.services.industry_pulse.matrix import PulseQuery, query_count
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.specialist_feeds import (
    WEEK_SPECIALIST_FEEDS,
    SpecialistRssProvider,
    week_specialist_feed_queries,
    week_specialist_site_queries,
)


def _hit(**overrides) -> DiscoveryHit:
    base = dict(
        title="Hot summer boosts British blueberry volumes by 11 per cent",
        url="https://www.fruitnet.com/fresh-produce-journal/hot-summer-boosts-british-blueberry-volumes-by-11-per-cent/272546.article",
        source_domain="fruitnet.com",
        published_date="2026-09-01",
        snippet="The Summer Berry Company reported an 11 per cent increase in blueberry volumes after a consistent UK harvest.",
        query_id="feed:fruitnet",
        query_text="",
        geography="europe",
        berry="blueberry",
        topic="specialist_feed",
        provider="specialist_rss",
        origin_publisher_name="Fruitnet",
        origin_publisher_url="https://www.fruitnet.com/fresh-produce-journal/hot-summer-boosts-british-blueberry-volumes-by-11-per-cent/272546.article",
    )
    base.update(overrides)
    return DiscoveryHit(**base)


def test_pulse_matrix_stays_at_32():
    assert query_count() == 32


def test_retrieve_window_is_broader_than_display():
    assert retrieve_window_for("7d") == "30d"
    assert retrieve_window_for("24h") == "7d"
    assert retrieve_window_for("30d") == "30d"
    with pytest.raises(ValueError):
        retrieve_window_for("90d")


def test_week_queries_include_specialist_sites_and_apac_focus():
    rows = week_queries()
    kinds = {row.kind for row in rows}
    assert "specialist_site" in kinds
    assert "apac_focus" in kinds
    assert any(row.id == "site:fruitnet" for row in rows)
    assert any(row.id == "apac:en" for row in rows)
    assert any(row.id == "apac:zh-focus" for row in rows)
    assert any(row.id == "apac:ja-focus" for row in rows)
    assert len(week_specialist_site_queries()) == 9
    assert len(week_apac_focus_queries()) == 3


def test_week_catch_net_includes_apac_focus_not_site_queries():
    queries = [row.with_window("30d") for row in week_queries()]
    selected = week_catch_net_queries(queries)
    kinds = {row.kind for row in selected}
    assert "apac_focus" in kinds
    assert "specialist_site" not in kinds


def test_specialist_catalog_covers_required_publishers():
    hosts = {row["host"] for row in WEEK_SPECIALIST_FEEDS}
    for host in (
        "fruitnet.com",
        "freshplaza.com",
        "hortidaily.com",
        "freshfruitportal.com",
        "producereport.com",
        "perishablenews.com",
        "italianberry.it",
        "east-fruit.com",
        "thepacker.com",
    ):
        assert host in hosts
    assert len(week_specialist_feed_queries()) == len(WEEK_SPECIALIST_FEEDS)


def test_specialist_rss_maps_article_feed_without_google_when():
    fruitnet = _hit()

    class FakeFeed:
        entries = [
            type(
                "E",
                (),
                {
                    "title": fruitnet.title,
                    "link": fruitnet.url,
                    "summary": fruitnet.snippet,
                    "id": fruitnet.url,
                    "published_parsed": (2026, 9, 1, 13, 21, 0, 0, 244, 0),
                    "updated_parsed": None,
                    "author": "Julia Bottoms",
                    "source": {},
                },
            )()
        ]

    provider = SpecialistRssProvider(fetch=lambda url: (FakeFeed(), b"<rss/>"))
    query = PulseQuery(
        id="feed:fruitnet",
        text="https://www.fruitnet.com/45.rss",
        berry=None,
        geography="global",
        topic="specialist_feed",
        kind="specialist_feed",
        hl="en-GB",
        gl="GB",
        ceid="GB:en",
    )
    hits = provider.discover(query)
    assert len(hits) == 1
    assert hits[0].published_date == "2026-09-01"
    assert "fruitnet.com" in (hits[0].source_domain or "")
    assert hits[0].origin_publisher_name == "Fruitnet"
    assert hits[0].provider == "specialist_rss"


def test_fruitnet_british_blueberry_qualifies_and_is_in_window():
    hit = _hit()
    qualify_hit(hit, sources=[{"url": "https://www.fruitnet.com/", "entity_types": ["trade_press"]}])
    assert hit.qualifying is True
    edition = run_week_intelligence(
        window="7d",
        providers=[MemoryProvider(hits=[hit])],
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        entities=[{"id": "company-the-summer-berry-company", "name": "The Summer Berry Company", "entity_type": "company"}],
        varieties=[],
        sources=[],
    )
    urls = {item.url for item in edition.what_matters}
    assert fruitnet_url() in urls
    assert edition.stats["display_window"] == "7d"
    assert edition.stats["retrieve_window"] == "30d"
    assert edition.stats["regions"]["europe"] >= 1
    assert edition.pbr_regulatory == [] or isinstance(edition.pbr_regulatory, list)
    assert isinstance(edition.patents_genetics, list)


def fruitnet_url() -> str:
    return (
        "https://www.fruitnet.com/fresh-produce-journal/"
        "hot-summer-boosts-british-blueberry-volumes-by-11-per-cent/272546.article"
    )


def test_older_hortifrut_deal_stays_out_of_what_matters():
    old = _hit(
        title="Naturipe Farms and Hortifrut partner up with Mountain Blue Orchards",
        url="https://www.freshfruitportal.com/news/2026/07/30/hortifrut-mbo-berry-deal/",
        source_domain="freshfruitportal.com",
        published_date="2026-07-30",
        snippet="Hortifrut and Naturipe expand a berry genetics platform with Mountain Blue Orchards in the Americas.",
        origin_publisher_name="FreshFruitPortal",
        origin_publisher_url="https://www.freshfruitportal.com/news/2026/07/30/hortifrut-mbo-berry-deal/",
        geography="americas",
        query_id="feed:freshfruitportal",
    )
    edition = run_week_intelligence(
        window="7d",
        providers=[MemoryProvider(hits=[old])],
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        entities=[{"id": "company-hortifrut", "name": "Hortifrut", "entity_type": "company"}],
        varieties=[],
        sources=[],
    )
    assert old.url not in {item.url for item in edition.what_matters}
    assert old.url in {item.url for item in edition.older_circulating}


def test_guardian_uk_harvest_qualifies_without_named_cultivar():
    hit = _hit(
        title="Record heatwaves help deliver bumper UK berry harvest",
        url="https://www.theguardian.com/environment/2026/aug/27/record-heatwaves-help-deliver-bumper-uk-berry-harvest",
        source_domain="theguardian.com",
        published_date="2026-08-27",
        snippet="British Berry Growers said this year's haul is up as heatwaves and irrigation delivered a bumper berry harvest.",
        origin_publisher_name="The Guardian",
        origin_publisher_url="https://www.theguardian.com/environment/2026/aug/27/record-heatwaves-help-deliver-bumper-uk-berry-harvest",
        provider="google_news_rss",
        query_id="pulse:blueberry:europe",
    )
    qualify_hit(hit)
    assert hit.qualifying is True


def test_chinese_price_story_has_crop_identity():
    hit = _hit(
        title="蓝莓价格下跌 出口增加",
        url="https://example.com/cn-blueberry-price",
        source_domain="east-fruit.com",
        snippet="中国云南蓝莓种植面积扩大，价格下跌。",
        origin_publisher_name="EastFruit",
        berry=None,
        geography="apac",
    )
    qualify_hit(hit)
    assert hit.qualifying is True


def test_apitube_refuses_without_credentials(monkeypatch):
    monkeypatch.delenv(APITUBE_API_KEY_ENV, raising=False)
    with pytest.raises(ProviderAuthError) as exc:
        ApiTubeSearchProvider().discover(
            PulseQuery(
                id="ad-hoc",
                text="blueberry harvest",
                berry="blueberry",
                geography="global",
                topic="ad_hoc",
                kind="ad_hoc",
                hl="en-US",
                gl="US",
                ceid="US:en",
                date_window="7d",
            )
        )
    assert APITUBE_API_KEY_ENV in str(exc.value)
    assert "Operator setup" in APITUBE_SETUP


def test_optional_sync_providers_do_not_invent_keys(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv(APITUBE_API_KEY_ENV, raising=False)
    assert optional_sync_discovery_providers() == []


def test_week_stack_always_includes_specialist_rss():
    primary, catch_net, specialist = week_discovery_stack(perplexity_enabled=False)
    assert any(getattr(row, "name", "") == "google_news_rss" for row in primary)
    assert catch_net is None
    assert specialist.name == "specialist_rss"


def test_homepage_origin_does_not_collapse_distinct_fruitnet_stories():
    from app.services.industry_pulse.dedup import dedupe_hits, identity_key, unique_hits

    first = _hit()
    first.origin_publisher_url = "https://www.fruitnet.com"
    first.url = "fruitnet.com"
    first.wrapper_url = "https://news.google.com/rss/articles/one"
    second = _hit(
        title="UK growers seek retailer support as strawberry volumes surge",
        url="fruitnet.com",
        origin_publisher_url="https://www.fruitnet.com",
        wrapper_url="https://news.google.com/rss/articles/two",
        berry="strawberry",
    )
    assert identity_key(first) != identity_key(second)
    dedupe_hits([first, second])
    assert len(unique_hits([first, second])) == 2


def test_layers_are_not_all_news():
    assert LAYER_OF["specialist_rss"] == DISCOVERY_PROVIDER
    assert LAYER_OF["apitube"] == DISCOVERY_PROVIDER
    assert LAYER_OF["usda_pvpo"] == AUTHORITATIVE_REGISTRY
    assert LAYER_OF["fruitnet"] == SPECIALIST_SOURCE
    assert LAYER_OF["upov_pluto"] != DISCOVERY_PROVIDER
