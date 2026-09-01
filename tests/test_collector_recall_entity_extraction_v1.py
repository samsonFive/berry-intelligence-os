"""Collector Recall + Entity Extraction Gap Closure V1.

Generalizable collector/extraction fixes. Does not edit the frozen 22-row
benchmark input. Does not write Sources, Evidence, or trusted Varieties.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import media_discovery
from app.services.geography_hierarchy import matched_geography_ids, resolve_geography_scope
from app.services.media_discovery import DiscoveryError, discover_source
from app.services.recall_audit.classify import (
    DATE_CHRONOLOGY_FAILURE,
    ENTITY_FOUND_IDENTITY_UNRESOLVED,
    FULLY_REPRESENTED,
    GEOGRAPHY_LINKAGE_FAILURE,
    ITEM_COLLECTED_ENTITY_MISSED,
    SOURCE_COLLECTED_ITEM_MISSED,
    classify_result,
    explicit_geography_ids,
    score_benchmark,
)
from app.services.relevance_screening import screen_discovered_item
from app.services.source_reacquisition import (
    load_committed_benchmark_urls,
    plan_uncollected_eligible_urls,
)
from app.services.variety_universe.corpus_discovery import (
    discover_corpus_variety_mentions,
    mentions_as_scoring_candidates,
)
from app.services.variety_universe.identity import STATE_DISTINCT, STATE_POSSIBLE_ALIAS, resolve_identity

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "data" / "imports" / "missed-intelligence-recall-audit-v1" / "benchmark.json"


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8")
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def repos(tmp_path: Path):
    return get_repositories(tmp_path, SCHEMAS_DIR)


def _rss(items: str, *, next_href: str | None = None) -> bytes:
    next_link = (
        f'<atom:link rel="next" href="{next_href}"/>' if next_href else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Publisher</title>
    {next_link}
    {items}
  </channel>
</rss>""".encode("utf-8")


def _item(title: str, url: str, day: str, guid: str) -> str:
    return f"""
    <item>
      <title>{title}</title>
      <link>{url}</link>
      <guid>{guid}</guid>
      <pubDate>Mon, {day} 00:00:00 GMT</pubDate>
    </item>
    """


def test_feed_pagination_surfaces_older_page(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-rss-window-test"
    page1 = "https://publisher.example.invalid/feed"
    page2 = "https://publisher.example.invalid/feed?page=2"
    repos.sources.create(
        {
            "id": source_id,
            "type": "rss",
            "label": "Publisher RSS",
            "discovery": {"adapter": "article_rss", "feed_url": page1, "max_feed_pages": 3},
        }
    )
    feeds = {
        page1: _rss(
            _item("Recent greenhouse lighting", "https://publisher.example.invalid/recent", "24 Aug 2026", "recent"),
            next_href=page2,
        ),
        page2: _rss(
            _item(
                "New blackberry cultivar launch",
                "https://publisher.example.invalid/loch-katrine",
                "01 Jan 2024",
                "older",
            )
        ),
    }

    def _get(url, *args, **kwargs):
        if url not in feeds:
            raise AssertionError(f"unmocked URL: {url}")
        return _FakeResponse(feeds[url])

    monkeypatch.setattr(media_discovery.httpx, "get", _get)
    result = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    urls = {item["canonical_url"] for item in result.items}
    assert "https://publisher.example.invalid/loch-katrine" in urls
    assert result.found == 2


def test_search_query_catchnet_keeps_cultivar_and_pbr_on_existing_source() -> None:
    sources = _load_json(ROOT / "data" / "configuration" / "sources.json")
    caneberry = next(row for row in sources if row["id"] == "source-news-search-caneberry-global")
    query = caneberry["discovery"]["feed_url"]
    assert "cultivar" in query
    assert "PBR" in query
    assert query.count("news.google.com/rss/search") == 1


def test_named_cultivar_launch_is_not_relevance_rejected() -> None:
    screen = screen_discovered_item(
        {
            "title": "New blackberry Loch Katrine to debut at Fruit Focus",
            "summary": "James Hutton blackberry cultivar launch",
            "source_name": "FreshPlaza",
        }
    )
    assert screen.decision == "process"


def test_unrelated_item_still_relevance_rejected() -> None:
    screen = screen_discovered_item(
        {
            "title": "City council parking rates change next month",
            "summary": "Municipal notice",
            "source_name": "Local Gazette",
        }
    )
    assert screen.decision == "skip"


def test_historical_reacquisition_plans_collection_eligible_missed_urls() -> None:
    sources = [
        {
            "id": "source-freshplaza-global",
            "enabled": True,
            "url": "https://www.freshplaza.com/",
            "discovery": {"adapter": "article_rss", "feed_url": "https://www.freshplaza.com/rss.xml"},
        }
    ]
    planned = plan_uncollected_eligible_urls(
        [
            "https://www.freshplaza.com/europe/article/9746367/new-blackberry-loch-katrine-to-debut-at-fruit-focus/",
            "https://italianberry.it/en/news/fresh-blackberries-quality-varieties-europe-consumption",
            "https://www.freshplaza.com/europe/article/9746367/new-blackberry-loch-katrine-to-debut-at-fruit-focus/",
        ],
        sources=sources,
        published_evidence=[],
    )
    assert len(planned) == 1
    assert planned[0]["historical_backlog"] is True
    assert planned[0]["network_acquisition_performed"] is False
    assert planned[0]["host"] == "freshplaza.com"


def test_historical_planner_skips_already_published_url() -> None:
    sources = [
        {
            "id": "source-one",
            "enabled": True,
            "url": "https://publisher.example.invalid/",
            "discovery": {"adapter": "article_rss", "feed_url": "https://publisher.example.invalid/feed"},
        }
    ]
    url = "https://publisher.example.invalid/already"
    planned = plan_uncollected_eligible_urls(
        [url],
        sources=sources,
        published_evidence=[{"id": "ev-1", "status": "published", "source_url": url}],
    )
    assert planned == []


def test_committed_benchmark_urls_are_generic_not_hardcoded_ids() -> None:
    urls = load_committed_benchmark_urls(ROOT / "data")
    assert any("freshplaza.com" in url for url in urls)
    assert any("fallcreeknursery.com/commercial-fruit-growers" in url for url in urls)


def test_sitemap_per_include_pattern_limit_keeps_each_path_family(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-sitemap-path-families"
    feed_url = "https://nursery.example.invalid/sitemap.xml"
    repos.sources.create(
        {
            "id": source_id,
            "type": "reference",
            "label": "Nursery",
            "discovery": {
                "adapter": "sitemap_xml",
                "feed_url": feed_url,
                "include_url_patterns": [r"/blog/", r"/commercial-fruit-growers/"],
                "sort": "published_desc",
                "item_limit_per_include_pattern": 1,
            },
        }
    )
    sitemap = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://nursery.example.invalid/about</loc><lastmod>2026-08-24</lastmod></url>
  <url><loc>https://nursery.example.invalid/blog/newest</loc><lastmod>2026-08-22</lastmod></url>
  <url><loc>https://nursery.example.invalid/blog/older</loc><lastmod>2026-07-01</lastmod></url>
  <url><loc>https://nursery.example.invalid/commercial-fruit-growers/south-africa</loc><lastmod>2026-01-01</lastmod></url>
</urlset>"""
    monkeypatch.setattr(media_discovery.httpx, "get", lambda *args, **kwargs: _FakeResponse(sitemap))
    result = discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)
    urls = [item["canonical_url"] for item in result.items]
    assert urls == [
        "https://nursery.example.invalid/blog/newest",
        "https://nursery.example.invalid/commercial-fruit-growers/south-africa",
    ]


def test_item_limit_per_include_pattern_must_be_positive(tmp_path, repos, monkeypatch) -> None:
    source_id = "source-bad-pattern-limit"
    feed_url = "https://nursery.example.invalid/sitemap.xml"
    repos.sources.create(
        {
            "id": source_id,
            "type": "reference",
            "label": "Nursery",
            "discovery": {
                "adapter": "sitemap_xml",
                "feed_url": feed_url,
                "include_url_patterns": [r"/blog/"],
                "item_limit_per_include_pattern": 0,
            },
        }
    )
    monkeypatch.setattr(
        media_discovery.httpx,
        "get",
        lambda *args, **kwargs: _FakeResponse(
            b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        ),
    )
    with pytest.raises(DiscoveryError, match="item_limit_per_include_pattern"):
        discover_source(source_id, inbox_dir=tmp_path / "inbox", data_dir=tmp_path, schemas_dir=SCHEMAS_DIR)


def _nda_evidence() -> dict:
    return {
        "id": "ev-nda-table",
        "status": "published",
        "source_type": "government_registry",
        "title": "Berries South Africa blueberry variety list 2025",
        "summary": "Official list including AzraBlue 'FCM14-031', AtlasBlue 'FCM12-045', and Sekoya Beauty 'FCM12-097'.",
        "source_url": "https://www.nda.gov.za/list.pdf",
        "published_date": "2025-01-01",
        "captured_date": "2026-08-03",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek-farm-and-nursery", "geography-south-africa"],
        "tags": ["cultivar-registry"],
    }


def test_explicit_cultivar_table_extraction_creates_new_candidate() -> None:
    report = discover_corpus_variety_mentions(
        varieties=[{"id": "variety-sekoya-beauty", "name": "Sekoya Beauty", "berry_ids": ["berry-blueberry"]}],
        entities=[{"id": "company-fall-creek-farm-and-nursery", "entity_type": "company", "name": "Fall Creek"}],
        published_evidence=[_nda_evidence()],
        facts=[],
        existing_candidates=[],
    )
    names = {row["candidate_name"] for row in report["new_mentions"]}
    assert "AzraBlue" in names
    assert "AtlasBlue" in names
    azra = next(row for row in report["new_mentions"] if row["candidate_name"] == "AzraBlue")
    assert azra["published_date"] == "2025-01-01"
    assert "ev-nda-table" in azra["evidence_ids"]


def test_already_canonical_variety_is_not_a_new_candidate() -> None:
    report = discover_corpus_variety_mentions(
        varieties=[{"id": "variety-sekoya-beauty", "name": "Sekoya Beauty", "berry_ids": ["berry-blueberry"]}],
        entities=[],
        published_evidence=[_nda_evidence()],
        facts=[],
        existing_candidates=[],
    )
    assert any(row["candidate_name"] == "Sekoya Beauty" for row in report["already_canonical"])
    assert all(row["candidate_name"] != "Sekoya Beauty" for row in report["new_mentions"])


def test_launch_title_extracts_named_variety_not_body_capitals() -> None:
    evidence = {
        "id": "ev-apex-title",
        "status": "published",
        "source_type": "news_search",
        "title": "Fall Creek launches Apex blueberry variety - Fruitnet",
        "summary": "Latest addition to Fall Creek Collection has 45-day shelf-life. Unrelated TokenWord should not become a cultivar.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["company-fall-creek-farm-and-nursery"],
        "published_date": "2026-04-07",
        "captured_date": "2026-08-06",
    }
    report = discover_corpus_variety_mentions(
        varieties=[],
        entities=[{"id": "company-fall-creek-farm-and-nursery", "entity_type": "company", "name": "Fall Creek"}],
        published_evidence=[evidence],
        facts=[],
        existing_candidates=[],
    )
    names = {row["candidate_name"] for row in report["mentions"]}
    assert "Apex" in names
    assert "TokenWord" not in names
    assert "Fall Creek" not in names
    apex = next(row for row in report["mentions"] if row["candidate_name"] == "Apex")
    assert apex["mention_kind"] == "launch_title"
    assert apex["published_date"] == "2026-04-07"


def test_company_on_collected_item_is_not_an_entity_miss() -> None:
    miss = classify_result(
        {
            "qualification": "qualifying",
            "matched_evidence_id": "ev-1",
            "expected_entity_id": "company-fall-creek-farm-and-nursery",
        },
        sources=[],
        published_evidence=[
            {
                "id": "ev-1",
                "entity_ids": ["company-fall-creek-farm-and-nursery"],
                "geography_ids": [],
            }
        ],
        varieties=[],
    )["miss_classification"]
    assert miss == FULLY_REPRESENTED


def test_non_variety_false_positive_excluded_from_title_scan() -> None:
    evidence = {
        "id": "ev-two-new",
        "status": "published",
        "source_type": "trade_press",
        "title": "Fall Creek introduces two new berry varieties",
        "summary": "Owner event coverage.",
        "berry_ids": ["berry-blueberry"],
    }
    report = discover_corpus_variety_mentions(
        varieties=[],
        entities=[{"id": "company-fall-creek-farm-and-nursery", "entity_type": "company", "name": "Fall Creek"}],
        published_evidence=[evidence],
        facts=[],
        existing_candidates=[],
    )
    names = {row["candidate_name"].casefold() for row in report["mentions"]}
    assert "two new" not in names
    assert "two" not in names


def test_explicit_identity_proof_routes_to_possible_alias_review() -> None:
    variety = {
        "id": "variety-fc11-164",
        "name": "FC11-164",
        "aliases": ["FC11-164"],
        "berry_ids": ["berry-blueberry"],
        "attributes": {"selection_code": "FC11-164", "commercial_name": None},
    }
    proven = resolve_identity(
        {"candidate_name": "FC11-164", "berry_id": "berry-blueberry"},
        [variety],
    )
    assert proven["identity_state"] == STATE_POSSIBLE_ALIAS
    assert proven["auto_confirmed"] is False


def test_insufficient_identity_stays_unresolved() -> None:
    variety = {
        "id": "variety-fc11-164",
        "name": "FC11-164",
        "aliases": ["FC11-164"],
        "berry_ids": ["berry-blueberry"],
        "attributes": {"commercial_name": None},
    }
    unresolved = resolve_identity(
        {"candidate_name": "Everlast", "berry_id": "berry-blueberry"},
        [variety],
    )
    assert unresolved["identity_state"] == STATE_DISTINCT
    assert unresolved.get("auto_confirmed") is not True
    assert variety["attributes"]["commercial_name"] is None
    assert "Everlast" not in (variety.get("aliases") or [])
    miss = classify_result(
        {
            "qualification": "qualifying",
            "matched_entity_id": "variety-fc11-164",
            "expected_alias": "Everlast",
            "url": "https://www.hortidaily.com/article/9864508/fall-creek-introduces-two-new-berry-varieties/",
        },
        sources=[],
        published_evidence=[],
        varieties=[variety],
    )["miss_classification"]
    assert miss == ENTITY_FOUND_IDENTITY_UNRESOLVED


def test_published_date_preserved_and_captured_date_not_masquerading() -> None:
    evidence = {
        "id": "ev-dated",
        "status": "published",
        "source_type": "government_registry",
        "title": "Blueberry cultivar 'Adelita'",
        "summary": "The blueberry cultivar 'Adelita' is listed.",
        "published_date": "2016-06-01",
        "captured_date": "2026-08-25",
        "berry_ids": ["berry-blueberry"],
        "tags": ["registry"],
    }
    report = discover_corpus_variety_mentions(
        varieties=[],
        entities=[],
        published_evidence=[evidence],
        facts=[],
        existing_candidates=[],
    )
    adelita = next(row for row in report["mentions"] if row["candidate_name"] == "Adelita")
    assert adelita["published_date"] == "2016-06-01"


def test_unknown_date_stays_unknown() -> None:
    evidence = {
        "id": "ev-undated",
        "status": "published",
        "source_type": "government_registry",
        "title": "Blueberry cultivar 'MysteryName'",
        "summary": "The blueberry cultivar 'MysteryName' is listed.",
        "published_date": None,
        "captured_date": "2026-08-25",
        "berry_ids": ["berry-blueberry"],
        "tags": ["registry"],
    }
    report = discover_corpus_variety_mentions(
        varieties=[],
        entities=[],
        published_evidence=[evidence],
        facts=[],
        existing_candidates=[],
    )
    mention = next(row for row in report["mentions"] if row["candidate_name"] == "MysteryName")
    assert mention["published_date"] == ""
    miss = classify_result(
        {
            "qualification": "qualifying",
            "matched_evidence_id": "ev-undated",
            "expected_date": "2025-01",
        },
        sources=[],
        published_evidence=[evidence],
        varieties=[],
        candidates=mentions_as_scoring_candidates(report),
    )["miss_classification"]
    assert miss == DATE_CHRONOLOGY_FAILURE


def test_explicit_geography_dual_field_and_linked_evidence() -> None:
    evidence = {
        "id": "ev-geo",
        "geography_ids": ["geography-united-kingdom"],
        "entity_ids": ["variety-victoria"],
    }
    variety = {
        "id": "variety-victoria",
        "geography_ids": [],
        "evidence_ids": ["ev-geo"],
        "entity_ids": ["geography-united-states"],
    }
    assert "geography-united-kingdom" in explicit_geography_ids(evidence)
    assert "geography-south-africa" in explicit_geography_ids(
        {"entity_ids": ["geography-south-africa"], "geography_ids": []}
    )
    linked = explicit_geography_ids(
        variety, evidence_by_id={"ev-geo": evidence}, follow_linked_evidence=True
    )
    assert "geography-united-kingdom" in linked
    assert "geography-united-states" in linked


def test_geography_hierarchy_no_sibling_leakage() -> None:
    relationships = [
        {
            "id": "rel-spain-europe",
            "subject_id": "geography-spain",
            "object_id": "geography-europe",
            "predicate": "part_of",
            "status": "active",
        },
        {
            "id": "rel-portugal-europe",
            "subject_id": "geography-portugal",
            "object_id": "geography-europe",
            "predicate": "part_of",
            "status": "active",
        },
    ]
    spain_scope = resolve_geography_scope("geography-spain", relationships=relationships)
    record = {"geography_ids": ["geography-portugal"], "entity_ids": []}
    assert matched_geography_ids(record, spain_scope.all_ids) == ()
    miss = classify_result(
        {
            "qualification": "qualifying",
            "matched_evidence_id": "ev-apex",
            "expected_entity_id": "company-fall-creek-farm-and-nursery",
            "expected_geography_id": "geography-united-states",
        },
        sources=[],
        published_evidence=[
            {
                "id": "ev-apex",
                "entity_ids": ["company-fall-creek-farm-and-nursery"],
                "geography_ids": [],
                "tags": ["Peru blueberry export"],
            }
        ],
        varieties=[],
    )["miss_classification"]
    assert miss == GEOGRAPHY_LINKAGE_FAILURE


def test_frozen_benchmark_input_unchanged() -> None:
    payload = _load_json(BENCHMARK_PATH)
    assert payload["id"] == "recall-audit-genetics-eu-uk-sa-us-v1"
    assert len(payload["results"]) == 22
    assert {row["id"] for row in payload["results"]} == {
        "RA-EU-BK-01",
        "RA-EU-BK-03",
        "RA-EU-BK-04",
        "RA-EU-BK-GEO",
        "RA-UK-RB-01",
        "RA-UK-RB-02",
        "RA-UK-RB-03",
        "RA-SA-BB-01",
        "RA-SA-BB-02",
        "RA-SA-BB-03",
        "RA-SA-BB-DATE",
        "RA-US-BB-01",
        "RA-US-BB-ID",
        "RA-US-BB-03",
        "RA-US-BB-04",
        "RA-US-BB-05",
        "RA-US-BB-06",
        "RA-US-BB-07",
        "RA-EU-ST-01",
        "RA-EU-ST-02",
        "RA-EU-ST-05",
        "RA-EU-ST-06",
    }


def test_scoring_does_not_write_trust_objects(tmp_path) -> None:
    sources = _load_json(ROOT / "data" / "configuration" / "sources.json")
    evidence = [_load_json(path) for path in sorted((ROOT / "data" / "evidence").glob("*.json"))]
    varieties = [
        _load_json(path) for path in sorted((ROOT / "data" / "entities" / "varieties").glob("*.json"))
    ]
    sources_mtime = (ROOT / "data" / "configuration" / "sources.json").stat().st_mtime
    evidence_count = len(list((ROOT / "data" / "evidence").glob("*.json")))
    variety_count = len(list((ROOT / "data" / "entities" / "varieties").glob("*.json")))
    scored = score_benchmark(
        _load_json(BENCHMARK_PATH),
        sources=sources,
        published_evidence=evidence,
        varieties=varieties,
    )
    assert scored["counts"][FULLY_REPRESENTED] == 3
    assert scored["counts"][ITEM_COLLECTED_ENTITY_MISSED] == 0
    assert scored["counts"][SOURCE_COLLECTED_ITEM_MISSED] == 8
    assert (ROOT / "data" / "configuration" / "sources.json").stat().st_mtime == sources_mtime
    assert len(list((ROOT / "data" / "evidence").glob("*.json"))) == evidence_count
    assert len(list((ROOT / "data" / "entities" / "varieties").glob("*.json"))) == variety_count
    assert not (tmp_path / "evidence").exists()


def test_cross_publisher_url_is_not_the_same_item() -> None:
    miss = classify_result(
        {
            "qualification": "qualifying",
            "url": "https://www.freshfruitportal.com/news/2026/04/07/fall-creek-apex/",
            "cultivar_names": ["Apex"],
        },
        sources=[
            {
                "id": "source-ffp",
                "enabled": True,
                "url": "https://www.freshfruitportal.com/",
                "discovery": {"adapter": "article_rss", "feed_url": "https://www.freshfruitportal.com/feed"},
            }
        ],
        published_evidence=[
            {
                "id": "ev-gnews",
                "status": "published",
                "source_url": "https://news.google.com/rss/articles/CBMilwF",
                "origin_domain": "fruitnet.com",
                "title": "Fall Creek launches Apex blueberry variety - Fruitnet",
                "entity_ids": ["company-fall-creek-farm-and-nursery"],
            }
        ],
        varieties=[],
    )["miss_classification"]
    assert miss == SOURCE_COLLECTED_ITEM_MISSED
