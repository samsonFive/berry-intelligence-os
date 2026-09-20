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


def test_exa_superfruit_directory_and_pyo_drop_industry_kept():
    from app.services.today_relevance import filter_today_records

    superfruit = _hit(
        "Spain Blueberry: The Juicy Secret Behind Europe’s Rising Superfruit - MyDesignation",
        "A juicy secret behind Europe's rising superfruit.",
        url="https://test.mydesignation.com/spain-blueberry-the-juicy-secret-behind-europes-rising-superfruit",
        source_domain="test.mydesignation.com",
        origin_publisher_url="https://test.mydesignation.com/spain-blueberry-the-juicy-secret-behind-europes-rising-superfruit",
        provider="exa",
    )
    directory = _hit(
        "North Bay Produce - International Blueberry Organization",
        "Member directory profile.",
        url="https://www.internationalblueberry.org/north-bay-produce/",
        source_domain="internationalblueberry.org",
        origin_publisher_url="https://www.internationalblueberry.org/north-bay-produce/",
        provider="exa",
    )
    translation = _hit(
        "The Cranberry In Spanish Translation And Uses: From Bog To Bottle - MyDesignation",
        "From bog to bottle translation copy.",
        url="https://test.mydesignation.com/the-cranberry-in-spanish-translation-and-uses-from-bog-to-bottle",
        source_domain="test.mydesignation.com",
        origin_publisher_url="https://test.mydesignation.com/the-cranberry-in-spanish-translation-and-uses-from-bog-to-bottle",
        provider="exa",
    )
    pyo = _hit(
        "Blueberry Picking in Connecticut | Lyman Orchards",
        "Pick your own blueberries this weekend.",
        url="https://lymanorchards.com/pick-your-own/blueberries/",
        source_domain="lymanorchards.com",
        origin_publisher_url="https://lymanorchards.com/pick-your-own/blueberries/",
        provider="perplexity",
    )
    mango = _hit(
        '"There is no need to rush the mango harvest, since crop volumes are down 40%"',
        "Mango harvest volumes are down.",
        url="https://freshplaza.com/article/9874296/mango-harvest",
        source_domain="freshplaza.com",
        provider="specialist_rss",
    )
    industry = _hit(
        "China: blueberry crop tops 100.000 hectares while export is starting by Italianberry",
        "Blueberry acreage and export from the commercial crop.",
        url="https://befve.com/en/china-blueberry-crop-tops-100-000-hectares-while-export-is-starting-by-italianberry/",
        source_domain="befve.com",
        origin_publisher_url="https://befve.com/en/china-blueberry-crop-tops-100-000-hectares-while-export-is-starting-by-italianberry/",
        provider="exa",
    )
    assert today_noise_reason(superfruit, named_entity=True)
    assert today_noise_reason(directory, named_entity=True)
    assert today_noise_reason(translation, named_entity=False)
    assert today_noise_reason(pyo, named_entity=False)
    assert today_noise_reason(mango, named_entity=False)
    kept, dropped = apply_today_relevance(
        [superfruit, directory, translation, pyo, mango, industry],
        entities=_entities(),
    )
    assert dropped >= 5
    assert [hit.title for hit in kept] == [industry.title]
    records, dropped_records = filter_today_records(
        [
            {"title": superfruit.title, "summary": superfruit.snippet, "source_url": superfruit.url},
            {
                "title": "Demand for larger blueberry packs takes the market beyond the familiar 125g",
                "summary": "Retail packs move beyond 125g for blueberry exporters.",
                "source_url": "https://freshplaza.com/article/9874367/demand-for-larger-blueberry-packs",
            },
        ],
        entities=_entities(),
    )
    assert dropped_records == 1
    assert records[0]["title"].startswith("Demand for larger")
    seminar = _hit(
        "XXV Seminar Chile 2023 - Blueberries Consulting",
        "Event listing for the 2023 Chile blueberry seminar.",
        url="https://blueberriesconsulting.com/en/seminario/xxv-seminario-chile-2023/",
        source_domain="blueberriesconsulting.com",
        origin_publisher_url="https://blueberriesconsulting.com/en/seminario/xxv-seminario-chile-2023/",
        provider="exa",
    )
    current = _hit(
        "Photoreport: 43rd International Berries Seminar Morocco 2026",
        "Growers and breeders met on varietal timing and acreage.",
        url="https://hortidaily.com/article/9874082/photoreport-43rd-international-berries-seminar-morocco-2026",
        source_domain="hortidaily.com",
        provider="specialist_rss",
    )
    assert today_noise_reason(seminar, named_entity=True)
    kept_seminar, dropped_seminar = apply_today_relevance([seminar, current], entities=_entities())
    assert dropped_seminar == 1
    assert [hit.title for hit in kept_seminar] == [current.title]


def test_collapse_story_clusters_keeps_one_lead():
    records = [
        {"title": "Fall Creek expands nursery", "source_url": "https://a.example/story", "source_name": "A", "published_date": "2026-09-21"},
        {"title": "Fall Creek expands nursery", "source_url": "https://a.example/story?utm=1", "source_name": "B", "published_date": "2026-09-21"},
    ]
    collapsed = collapse_story_clusters(records)
    assert len(collapsed) == 1
    assert collapsed[0]["cluster_size"] == 2
    assert collapsed[0]["cluster_sources"] == ["a.example"]
    assert collapsed[0]["story_cluster_id"].startswith("cluster-")
    assert collapsed[0]["source_url"] == "https://a.example/story"
    assert len(collapsed[0]["discovery_urls"]) == 2


def test_collapse_story_clusters_merges_utm_and_publisher_suffix():
    records = [
        {
            "title": "Wish Farms and Clarifresh transform berry quality control",
            "source_url": "https://perishablenews.example/wish-farms",
            "source_name": "Perishable News",
            "acquisition_lane": "specialist_rss",
            "published_date": "2026-09-18",
        },
        {
            "title": "Wish Farms and Clarifresh transform berry quality control - PerishableNews",
            "source_url": "https://perishablenews.example/wish-farms?utm_source=exa&utm_medium=api",
            "source_name": "Exa",
            "acquisition_lane": "exa",
            "published_date": "2026-09-18",
        },
        {
            "title": "Planasa blueberry harvest volumes rise in Peru",
            "source_url": "https://freshplaza.example/planasa-peru",
            "source_name": "FreshPlaza",
            "acquisition_lane": "google_news_rss",
            "published_date": "2026-09-18",
        },
    ]
    collapsed = collapse_story_clusters(records)
    assert [row["title"] for row in collapsed] == [
        "Wish Farms and Clarifresh transform berry quality control",
        "Planasa blueberry harvest volumes rise in Peru",
    ]
    wish = collapsed[0]
    assert wish["cluster_size"] == 2
    assert wish["cluster_sources"] == ["perishablenews.example"]
    assert wish["discovery_urls"] == [
        "https://perishablenews.example/wish-farms",
        "https://perishablenews.example/wish-farms?utm_source=exa&utm_medium=api",
    ]
    assert collapsed[1]["cluster_size"] == 1
    assert collapsed[1]["cluster_sources"] == []


def test_collapse_story_clusters_unions_same_canonical_url():
    records = [
        {
            "title": "Hoddys Berry Farm harvest note",
            "source_url": "https://hoddys.example/news?utm_campaign=today",
            "source_name": "Google News",
            "published_date": "2026-09-20",
        },
        {
            "title": "Season update from the farm",
            "source_url": "https://www.hoddys.example/news",
            "source_name": "Official site",
            "published_date": "2026-09-20",
        },
    ]
    collapsed = collapse_story_clusters(records)
    assert len(collapsed) == 1
    assert collapsed[0]["cluster_size"] == 2
    assert collapsed[0]["cluster_sources"] == ["Official site"]


def test_collapse_story_clusters_merges_bylined_republish():
    records = [
        {
            "title": "Demand for larger blueberry packs takes the market beyond the familiar 125g",
            "source_url": "https://freshplaza.example/larger-packs",
            "source_name": "FreshPlaza",
            "acquisition_lane": "specialist_rss",
            "published_date": "2026-09-18",
        },
        {
            "title": "Demand for larger blueberry packs takes the market beyond the familiar 125g by Paras Pack and FreshPlaza - Befve & Co",
            "source_url": "https://befve.example/demand-for-larger-blueberry-packs",
            "source_name": "Befve",
            "acquisition_lane": "exa",
            "published_date": "2026-09-19",
        },
        {
            "title": "Wish Farms Cuts Berry Inspection Time 70% With Clarifresh AI - The Packer",
            "source_url": "https://thepacker.example/wish-farms",
            "source_name": "The Packer",
            "published_date": "2026-09-15",
        },
    ]
    collapsed = collapse_story_clusters(records)
    assert len(collapsed) == 2
    assert collapsed[0]["cluster_size"] == 2
    assert collapsed[0]["cluster_sources"] == ["befve.example"]
    assert collapsed[1]["cluster_size"] == 1
