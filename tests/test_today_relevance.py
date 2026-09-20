"""Today relevance: drop hobby/tomato/forex; keep industry + named companies."""

from app.services.industry_pulse.models import DiscoveryHit
from app.services.today_relevance import apply_today_relevance, collapse_story_clusters, today_noise_reason


def _hit(title, snippet="", **overrides):
    base = dict(
        title=title,
        url="https://example.test/" + title[:12].replace(" ", "-"),
        source_domain="example.test",
        published_date="2026-09-21",
        snippet=snippet,
        query_id="today:blueberry:global:24h",
        query_text="blueberry",
        geography="global",
        berry="blueberry",
        topic="industry_pulse",
        provider="google_news_rss",
        origin_publisher_url="https://example.test/x",
        qualifying=True,
    )
    base.update(overrides)
    return DiscoveryHit(**base)


def _entities():
    return [{"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek", "aliases": []}]


def test_hobby_garden_and_tomato_and_forex_drop():
    entities = _entities()
    hobby = _hit("How To Plant Highbush Blueberry Bushes", "Our Wild Garden backyard tips")
    tomato = _hit("Indigo Blue Berries Cherry Tomatoes Information and Facts", "Solanum lycopersicum")
    forex = _hit("一批美国蓝莓品种折戟云南-Blueberry Markets蓝莓外汇官网", "外汇")
    industry = _hit(
        "Fall Creek expands blueberry nursery harvest after new planting",
        "The breeder reports new acreage.",
    )
    assert today_noise_reason(hobby, named_entity=False)
    assert today_noise_reason(tomato, named_entity=False)
    assert today_noise_reason(forex, named_entity=False)
    kept, dropped = apply_today_relevance([hobby, tomato, forex, industry], entities=entities)
    titles = {hit.title for hit in kept}
    assert industry.title in titles
    assert hobby.title not in titles
    assert tomato.title not in titles
    assert dropped >= 3


def test_named_company_survives_without_strong_industry_if_already_named():
    hit = _hit("Fall Creek Spain update", "Nursery notes from the company.")
    kept, _dropped = apply_today_relevance([hit], entities=_entities())
    assert kept


def test_thin_industry_mention_without_company_drops():
    hit = _hit("Growers see new genetics", "Acreage.")
    kept, dropped = apply_today_relevance([hit], entities=_entities())
    assert kept == []
    assert dropped == 1


def test_consumer_buy_guide_drops():
    hit = _hit("Where to buy the best blueberries this weekend", "Walmart grocery haul and antioxidant snack list.")
    assert today_noise_reason(hit, named_entity=False)


def test_collapse_story_clusters_keeps_one_lead():
    records = [
        {"title": "Fall Creek expands nursery", "source_url": "https://a.example/story", "source_name": "A", "published_date": "2026-09-21"},
        {"title": "Fall Creek expands nursery", "source_url": "https://a.example/story?utm=1", "source_name": "B", "published_date": "2026-09-21"},
    ]
    collapsed = collapse_story_clusters(records)
    assert len(collapsed) == 1
    assert collapsed[0]["cluster_size"] >= 1
    assert collapsed[0]["story_cluster_id"].startswith("cluster-")
