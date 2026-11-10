from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.services.feed_first_live import PRIORITY_PUBLISHER_QUERY_CAP, REGIONAL_QUERY_CAP, hit_to_record, live_feed_bundle
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider
from app.services.industry_pulse.qualify import qualify_hit
from app.services.industry_pulse.regional_news import REGIONAL_NEWS_PROVIDER, regional_news_queries
from app.services.industry_pulse.specialist_feeds import PRIORITY_PUBLISHER_PREFIX, week_specialist_feed_queries
from app.services.today_relevance import apply_today_relevance


def test_regional_news_rotation_reaches_four_crops_and_retains_discoveries(tmp_path, monkeypatch):
    published = date(2026, 11, 10)
    examples = {
        "US:en": ("California strawberry farm closures trigger layoffs", "strawberry"),
        "MX:es": ("Despidos en fincas de frambuesas en México", "raspberry"),
        "BR:pt": ("Seca reduz colheita de amora-preta no Brasil", "blackberry"),
        "CN:zh-Hans": ("中国蓝莓出口增长", "blueberry"),
    }
    configured = regional_news_queries()
    regions = {"africa", "americas", "apac", "europe"}
    assert {(query.geography, query.berry) for query in configured if query.berry} == {
        (region, crop) for region in regions for _, crop in examples.values()
    }
    assert {query.hl for query in configured} >= {"es-419", "fr-FR", "pl-PL", "pt-BR", "zh-CN", "ja-JP"}
    assert all(query.text.endswith("when:7d") for query in configured)

    class RegionalProvider:
        name = "test_google"

        def discover(self, query):
            if not query.id.startswith("today:regional:"):
                return []
            if query.ceid == "MA:fr":
                raise TimeoutError("publisher index timeout")
            if query.ceid not in examples:
                return []
            title, crop = examples[query.ceid]
            if query.berry and query.berry != crop:
                return []
            url = f"https://{crop}.example/news/closure"
            return [DiscoveryHit(
                title=title, url=url, source_domain=f"{crop}.example", published_date=published.isoformat(),
                snippet="", query_id=query.id, query_text=query.text, geography=query.geography,
                berry=None, topic=query.topic, provider=self.name, origin_publisher_url=url,
            )]

    options = {
        "inbox_dir": tmp_path, "refresh": True, "google_provider": RegionalProvider(),
        "specialist_provider": MemoryProvider(hits_by_query_id={}), "enable_perplexity": False,
        "enable_exa": False, "enable_apitube": False,
        "fetch_preview_images": False,
    }
    translations = []
    monkeypatch.setattr("app.services.feed_first_translate.perplexity_translator", lambda *args: translations.append(args))
    attempts = {}
    for _ in range((len(configured) + REGIONAL_QUERY_CAP - 1) // REGIONAL_QUERY_CAP):
        bundle = live_feed_bundle(today=published, **options)
        regional = [row for row in bundle["route_attempts"] if row["provider"] == REGIONAL_NEWS_PROVIDER]
        assert len(regional) == bundle["stats"]["regional_queries_polled"] == REGIONAL_QUERY_CAP
        attempts.update((row["query_id"], row) for row in regional)
    assert set(attempts) == {query.id for query in configured}
    assert {row["status"] for row in attempts.values()} == {"returned", "no_hits", "failed"}
    assert next(row for row in attempts.values() if row["edition"] == "MA:fr")["status"] == "failed"
    assert {tuple(row["berry_ids"]) for row in bundle["records"]} == {
        (f"berry-{crop}",) for _, crop in examples.values()
    }
    assert all(row["review_state"] == "UNREVIEWED" for row in bundle["records"])
    assert {row["discovery_provenance"]["query_edition"] for row in bundle["records"]} == set(examples)
    assert not translations

    options["google_provider"] = MemoryProvider(hits_by_query_id={})
    after_outage = live_feed_bundle(today=published + timedelta(days=2), **options)
    assert len(after_outage["records"]) == 4
    assert {row["captured_date"] for row in after_outage["records"]} == {published.isoformat()}
    assert after_outage["stats"]["regional_hits"] == 0
    expired = live_feed_bundle(today=published + timedelta(days=31), **options)
    assert not expired["records"]


def test_confirmed_publisher_headline_keeps_crop_provenance_and_type():
    published = date(2026, 11, 10)
    url = "https://publisher.example/news/crop"
    hit = DiscoveryHit(
        title="Seca reduz colheita de amora-preta no Brasil", url=url, source_domain="publisher.example",
        published_date=published.isoformat(), snippet="", query_id="publisher-fixture", query_text="",
        geography="americas", berry=None, topic=None, provider="specialist_rss",
        provider_metadata={"publisher_route": "direct_rss", "publisher_source_type": "news_search",
                           "query_edition": "BR:pt"},
    )
    assert apply_today_relevance([qualify_hit(hit)], entities=[])[0] == [hit]
    row = hit_to_record(hit, today=published, entities=[])
    assert row["source_type"] == "news_search"
    assert row["berry_ids"] == ["berry-blackberry"]
    assert row["discovery_provenance"]["query_edition"] == "BR:pt"
    assert row["discovery_provenance"]["publisher_route"] == "direct_rss"

    hit.provider_metadata.clear()
    assert not apply_today_relevance([qualify_hit(hit)], entities=[])[0]


def test_priority_publishers_rotate_without_losing_cards_or_legacy_checks(tmp_path):
    today = date(2026, 11, 10)
    configured = week_specialist_feed_queries(include_priority=True)
    legacy_ids = {query.id for query in week_specialist_feed_queries()}
    priority_ids = [query.id for query in configured if query.id.startswith(PRIORITY_PUBLISHER_PREFIX)]
    publisher_id = priority_ids[0]
    url = "https://publisher.example/news/blueberry"
    hit = DiscoveryHit(
        title="Blueberry exports increase", url=url, source_domain="publisher.example",
        published_date=today.isoformat(), snippet="", query_id=publisher_id, query_text="",
        geography="global", berry=None, topic=None, provider="specialist_rss",
        provider_metadata={"publisher_route": "indexed", "publisher_source_type": "news_search"},
    )
    options = {
        "inbox_dir": tmp_path, "refresh": True, "today": today,
        "google_provider": MemoryProvider(hits_by_query_id={}),
        "specialist_provider": MemoryProvider(name="specialist_rss", hits_by_query_id={publisher_id: [hit]}),
        "enable_perplexity": False, "enable_exa": False, "enable_apitube": False,
        "translate_live": False, "fetch_preview_images": False,
    }
    first = live_feed_bundle(**options)
    second = live_feed_bundle(**options)
    first_ids = {row["query_id"] for row in first["route_attempts"]}
    second_ids = {row["query_id"] for row in second["route_attempts"]}
    assert first_ids.intersection(priority_ids) == set(priority_ids[:PRIORITY_PUBLISHER_QUERY_CAP])
    assert publisher_id not in second_ids
    assert legacy_ids <= first_ids and legacy_ids <= second_ids
    assert first["stats"]["priority_hits"] == 1 and second["stats"]["priority_hits"] == 0
    assert [row["source_url"] for row in second["records"]] == [url]
    assert [row["berry_ids"] for row in second["records"]] == [["berry-blueberry"]]


@pytest.mark.parametrize("provider", [REGIONAL_NEWS_PROVIDER, "specialist_rss"])
def test_shared_variety_names_require_plant_context_on_new_routes(provider):
    today = date(2026, 11, 10)
    url = "https://publisher.example/news/story"
    entities = [{"id": f"variety-{name.lower()}", "name": name} for name in ("Candy", "Ventura", "Star")]
    names = [entity["name"] for entity in entities]
    candy = DiscoveryHit(
        title="NFL players rank their favorite Halloween Candy", url=url, source_domain="publisher.example",
        published_date=today.isoformat(), snippet="A variety of candy competed for the top spot.",
        query_id="publisher-fixture", query_text="", geography="americas", berry=None, topic=None, provider=provider,
        provider_metadata={"publisher_route": "indexed"},
    )
    assert not qualify_hit(candy, variety_names=names).qualifying
    local = replace(candy, title="Grower plans to close six farms in Ventura County",
                    snippet="The Ventura County Star reported announced layoffs at recently unionized farms.")
    assert not qualify_hit(local, variety_names=names).qualifying

    strawberry = replace(local, title="Strawberry grower plans farm closures in Ventura County")
    assert qualify_hit(strawberry, variety_names=names).qualifying
    assert hit_to_record(strawberry, today=today, entities=entities)["entity_ids"] == []

    cultivar = replace(candy, title="Breeder releases Candy cultivar for commercial planting", snippet="")
    assert qualify_hit(cultivar, variety_names=names).qualifying
    assert hit_to_record(cultivar, today=today, entities=entities)["entity_ids"] == ["variety-candy"]
