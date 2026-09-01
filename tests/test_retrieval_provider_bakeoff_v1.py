"""Retrieval provider bake-off V1.

Adapters behind DiscoveryProvider. Production Industry Pulse stays on
Google News RSS. No homepage/front-page edits.
"""

from __future__ import annotations

import inspect
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.services.industry_pulse.authority import authority_tier, is_unknown_unknown
from app.services.industry_pulse.bakeoff import (
    PROPRIETARY_TOKENS,
    assert_public_queries,
    bakeoff_queries,
    evaluate_hits,
    run_bakeoff,
)
from app.services.industry_pulse.brightdata import BrightDataSearchProvider
from app.services.industry_pulse.dedup import dedupe_hits, identity_key, unique_hits
from app.services.industry_pulse.errors import (
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.industry_pulse.exa import ExaSearchProvider
from app.services.industry_pulse.fallback import discover_with_fallback
from app.services.industry_pulse.firecrawl import FirecrawlSearchProvider
from app.services.industry_pulse.matrix import generate_pulse_queries
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.novelty import classify_hit
from app.services.industry_pulse.perplexity_provider import PerplexitySearchProvider
from app.services.industry_pulse.providers import (
    GoogleNewsRssProvider,
    MemoryProvider,
    discover,
    hits_from_web_rows,
)
from app.services.industry_pulse.query_text import (
    date_window_of,
    exa_start_published,
    firecrawl_tbs,
    iso_country,
    perplexity_date_kwargs,
    semantic_query_text,
)
from app.services.industry_pulse.run import run_pulse
from app.services.industry_pulse.slices import BAKEOFF_SLICES, slice_query
from app.services.industry_pulse.union import union_hits
from app.services.recall_audit.classify import SOURCE_UNKNOWN, classify_result

REPO = Path(__file__).resolve().parents[1]
TODAY = date(2026, 9, 1)


class FakeJsonResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body

    @property
    def text(self) -> str:
        return json.dumps(self._body)


class SequencePost:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def _hit(**kwargs) -> DiscoveryHit:
    row = dict(
        title="Planasa launches new strawberry variety in Spain",
        url="https://www.freshplaza.com/article/planasa-strawberry",
        source_domain="freshplaza.com",
        published_date="2026-09-01",
        snippet="Planasa commercial launch of a new strawberry cultivar for Spanish growers.",
        query_id="bakeoff:E:europe:7d",
        query_text="strawberry genetics commercialization",
        geography="europe",
        berry="strawberry",
        topic="commercial_launch",
        provider="memory",
        origin_publisher_name="FreshPlaza",
        origin_publisher_url="https://www.freshplaza.com/article/planasa-strawberry",
    )
    row.update(kwargs)
    return DiscoveryHit(**row)


def _query(window: str = "7d", *, google_when: bool = False):
    return slice_query(BAKEOFF_SLICES[0], window, google_when=google_when)


def test_google_news_provider_unchanged() -> None:
    source = inspect.getsource(GoogleNewsRssProvider.discover)
    assert "_fetch_paginated_rss" in source
    assert "query.feed_url()" in source
    pulse_source = inspect.getsource(run_pulse)
    assert "GoogleNewsRssProvider()" in pulse_source
    assert "ExaSearchProvider" not in pulse_source


def test_exa_conforms_to_discovery_provider() -> None:
    post = SequencePost(
        [
            FakeJsonResponse(
                200,
                {
                    "results": [
                        {
                            "title": "EU blackberry cultivar list",
                            "url": "https://online.plantvarieties.eu/blackberry",
                            "publishedDate": "2026-08-31",
                            "highlights": ["cultivar registration"],
                            "score": 0.91,
                            "id": "exa-1",
                        }
                    ]
                },
            )
        ]
    )
    provider = ExaSearchProvider(api_key="exa-test", post=post, today=TODAY)
    query = _query("7d", google_when=True)
    assert "when:" in query.text
    hits = provider.discover(query)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider == "exa"
    assert hit.url.endswith("/blackberry")
    assert hit.published_date == "2026-08-31"
    assert hit.provider_metadata["exa_score"] == 0.91
    body = post.calls[0]["json"]
    assert "when:" not in body["query"]
    assert body["startPublishedDate"].startswith("2026-08-25")
    assert body["userLocation"] == "GB"


def test_normalized_outputs_compatible() -> None:
    rows = [
        {
            "title": "Fall Creek blueberry catalogue",
            "url": "https://www.fallcreeknursery.com/varieties",
            "published_date": "2026-08-30",
            "snippet": "cultivar portfolio",
            "provider_metadata": {"exa_score": 0.4},
        }
    ]
    hits = hits_from_web_rows(rows, query=_query("3d"), provider_name="exa")
    assert set(hits[0].as_dict()) >= {
        "title",
        "url",
        "source_domain",
        "published_date",
        "snippet",
        "provider",
        "geography",
        "berry",
        "topic",
    }
    assert hits[0].source_domain == "fallcreeknursery.com"


def test_provider_metadata_does_not_infect_classify() -> None:
    hit = _hit(provider="exa", provider_metadata={"exa_score": 0.99, "exa_id": "x"})
    classified = classify_hit(hit, sources=[], published_evidence=[])
    result = classify_result(
        {
            "qualification": "qualifying",
            "url": hit.url,
            "domain": hit.source_domain,
            "title": hit.title,
        },
        sources=[],
        published_evidence=[],
        varieties=[],
    )
    assert "exa_score" not in result
    assert classified.miss_classification in {SOURCE_UNKNOWN, classified.miss_classification}
    assert classified.provider_metadata["exa_score"] == 0.99


def test_date_window_translation() -> None:
    google = _query("24h", google_when=True)
    other = _query("24h", google_when=False)
    assert "when:1d" in google.text
    assert "when:" not in other.text
    assert date_window_of(google) == "24h"
    assert "when:" not in semantic_query_text(google)
    assert "OR" in google.text
    assert google.berry == other.berry and google.geography == other.geography
    assert perplexity_date_kwargs("24h", today=TODAY) == {"search_recency_filter": "day"}
    assert perplexity_date_kwargs("3d", today=TODAY)["search_after_date_filter"] == "08/29/2026"
    assert firecrawl_tbs("7d", today=TODAY) == "qdr:w"
    assert firecrawl_tbs("3d", today=TODAY).startswith("cdr:1,cd_min:")
    assert exa_start_published("7d", today=TODAY).startswith("2026-08-25")


def test_geography_berry_topic_translation() -> None:
    europe = slice_query(BAKEOFF_SLICES[0], "7d")
    africa = slice_query(BAKEOFF_SLICES[2], "7d")
    us = slice_query(BAKEOFF_SLICES[3], "7d")
    assert europe.geography == "europe" and europe.berry == "blackberry"
    assert africa.gl == "ZA" and iso_country("africa") == "ZA"
    assert us.berry == "blueberry" and us.topic == "pbr_patent"
    assert iso_country("americas") == "US"
    assert iso_country("global") is None
    google = slice_query(BAKEOFF_SLICES[0], "7d", google_when=True)
    assert "blackberry" in google.text.lower() or "zarzamora" in google.text.lower()
    assert "breeder" in google.text.lower() or "genetics" in google.text.lower()
    hits = discover(
        "blueberry genetics",
        date_window="3d",
        geography="africa",
        berry="blueberry",
        topic="breeder_genetics",
        provider=MemoryProvider(hits=[_hit(geography="africa", berry="blueberry")]),
    )
    assert hits[0].geography == "africa"
    assert hits[0].berry == "blueberry"


def test_provider_failure_timeout_and_rate_limit() -> None:
    query = _query("7d")
    failing = ExaSearchProvider(api_key="exa-test", post=SequencePost([FakeJsonResponse(500, {"error": "nope"})]))
    with pytest.raises(ProviderUnavailableError):
        failing.discover(query)
    timed = ExaSearchProvider(api_key="exa-test", post=SequencePost([httpx.TimeoutException("late")]))
    with pytest.raises(ProviderTimeoutError):
        timed.discover(query)
    limited = FirecrawlSearchProvider(api_key="fc-test", post=SequencePost([FakeJsonResponse(429, {"error": "slow"})]))
    with pytest.raises(ProviderRateLimitError):
        limited.discover(query)
    with pytest.raises(ProviderAuthError):
        ExaSearchProvider(api_key="").discover(query)
    with pytest.raises(ProviderAuthError):
        BrightDataSearchProvider().discover(query)


def test_perplexity_maps_gateway_failures() -> None:
    query = _query("7d")
    provider = PerplexitySearchProvider(
        api_key="pplx-test",
        post=SequencePost([FakeJsonResponse(429, {"error": {"message": "rate"}})]),
        today=TODAY,
    )
    with pytest.raises(ProviderRateLimitError):
        provider.discover(query)


def test_dedup_union_and_same_url_two_providers() -> None:
    left = _hit(provider="google_news_rss")
    right = _hit(
        provider="perplexity",
        url="https://www.freshplaza.com/article/planasa-strawberry?utm=1",
        origin_publisher_url="https://www.freshplaza.com/article/planasa-strawberry",
    )
    only_right = _hit(
        title="USDA blueberry PBR notice",
        url="https://www.ams.usda.gov/pbr/blueberry",
        source_domain="ams.usda.gov",
        origin_publisher_url="https://www.ams.usda.gov/pbr/blueberry",
        provider="perplexity",
    )
    assert identity_key(left) == identity_key(right)
    merged = unique_hits(dedupe_hits([left, right, only_right]))
    assert len(merged) == 2
    report = union_hits([left], [right, only_right], left_name="google_news_rss", right_name="perplexity")
    assert report["both"] == 1
    assert report["only_left"] == 0
    assert report["only_right"] == 1
    assert report["both_hosts"] == 1
    assert "freshplaza.com" in report["both_host_names"]


def test_unknown_source_and_unknown_unknown() -> None:
    hit = classify_hit(
        _hit(
            source_domain="newberrypress.invalid",
            url="https://newberrypress.invalid/a",
            origin_publisher_url="https://newberrypress.invalid/a",
            qualifying=True,
            qualify_reason="qualifying: berry market/production/trade/IP/research terms",
        ),
        sources=[],
        published_evidence=[],
    )
    assert hit.miss_classification == SOURCE_UNKNOWN
    assert is_unknown_unknown(
        "newberrypress.invalid",
        known_sources=set(),
        universe=set(),
        cited=set(),
    )
    assert not is_unknown_unknown(
        "freshplaza.com",
        known_sources={"freshplaza.com"},
        universe=set(),
        cited=set(),
    )


def test_no_trust_mutation(tmp_path: Path) -> None:
    evidence = tmp_path / "data" / "evidence"
    evidence.mkdir(parents=True)
    sources = tmp_path / "data" / "configuration" / "sources.json"
    sources.parent.mkdir(parents=True)
    sources.write_text("[]", encoding="utf-8")
    report = run_bakeoff(
        sources=[],
        published_evidence=[],
        data_dir=tmp_path / "data",
        include_live=False,
        today=TODAY,
    )
    assert report["auto_trust"] is False
    assert report["production_provider"] == "google_news_rss"
    assert list(evidence.glob("*.json")) == []
    assert sources.read_text(encoding="utf-8") == "[]"


def test_no_static_leakage() -> None:
    source = (REPO / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert "retrieval_bakeoff" not in source
    assert "/industry-pulse" not in source
    feed = (REPO / "app" / "templates" / "feed.html").read_text(encoding="utf-8")
    today = (REPO / "app" / "templates" / "today.html").read_text(encoding="utf-8")
    assert "retrieval_bakeoff" not in feed
    assert "retrieval_bakeoff" not in today


def test_no_proprietary_prompt_leakage() -> None:
    queries = bakeoff_queries(google_when=False)
    assert_public_queries(queries)
    blob = " ".join(query.text for query in queries)
    for token in PROPRIETARY_TOKENS:
        assert token.lower() not in blob.lower()
    adapter = (REPO / "app" / "services" / "industry_pulse" / "perplexity_provider.py").read_text(encoding="utf-8")
    assert "PerplexityResearchClient" not in adapter
    assert "Does not send Assessments" in adapter


def test_deterministic_fallback_when_paid_unavailable() -> None:
    query = _query("7d")
    fallback_hits = [_hit(provider="google_news_rss")]
    hits = discover_with_fallback(
        query,
        primary=ExaSearchProvider(api_key=""),
        fallback=MemoryProvider(hits_by_query_id={query.id: fallback_hits}),
    )
    assert hits[0].provider == "memory"
    live = MemoryProvider(hits_by_query_id={query.id: [_hit(provider="exa", title="paid hit")]})
    hits = discover_with_fallback(
        query,
        primary=live,
        fallback=MemoryProvider(hits_by_query_id={query.id: fallback_hits}),
    )
    assert hits[0].title == "paid hit"


def test_evaluate_hits_raw_metrics_not_composite() -> None:
    metrics = evaluate_hits(
        [
            _hit(),
            _hit(
                title="Blueberry muffin recipe",
                snippet="dessert calories",
                url="https://recipes.invalid/muffin",
                source_domain="recipes.invalid",
                origin_publisher_url="https://recipes.invalid/muffin",
            ),
            _hit(
                title="USDA PBR blueberry cultivar list",
                url="https://www.ams.usda.gov/services/plant-variety-protection",
                source_domain="ams.usda.gov",
                origin_publisher_url="https://www.ams.usda.gov/services/plant-variety-protection",
                snippet="registration list of cultivars",
            ),
        ],
        provider="exa",
        live=True,
        sources=[],
        published_evidence=[],
        universe_entries=[],
        api_calls=18,
        latency_seconds_total=9.0,
    )
    payload = metrics.as_dict()
    assert "score" not in payload
    assert payload["unique_urls"] == 3
    assert payload["qualifying"] >= 1
    assert payload["non_qualifying"] >= 1
    assert payload["tier1"] >= 1
    assert payload["cultivar_dense"] >= 1
    assert payload["api_calls"] == 18
    assert payload["estimated_cost_usd"] == 0.126


def test_firecrawl_search_and_scrape_mocked() -> None:
    search = SequencePost(
        [
            FakeJsonResponse(
                200,
                {"data": {"web": [{"title": "Trial results", "url": "https://extension.oregonstate.edu/berry", "description": "cultivar trial"}]}},
            )
        ]
    )
    hits = FirecrawlSearchProvider(api_key="fc-test", post=search, today=TODAY).discover(_query("24h", google_when=True))
    assert hits[0].provider == "firecrawl"
    assert "when:" not in search.calls[0]["json"]["query"]
    assert search.calls[0]["json"]["tbs"] == "qdr:d"
    scrape = SequencePost(
        [
            FakeJsonResponse(
                200,
                {"data": {"markdown": "| Cultivar | Yield |\n| --- | --- |\n| A | 1 |", "metadata": {"title": "Catalogue"}}},
            )
        ]
    )
    page = FirecrawlSearchProvider(api_key="fc-test", post=scrape).scrape("https://example.invalid/table")
    assert page["success"] is True
    assert page["has_table"] is True


def test_authority_tier1_government() -> None:
    assert authority_tier("ams.usda.gov", class_map={}) == "tier1"
    assert authority_tier("oregonstate.edu", class_map={}) == "tier2"


def test_production_pulse_default_is_google(monkeypatch) -> None:
    captured = {}

    class Recorder(GoogleNewsRssProvider):
        def discover(self, query):
            captured["name"] = self.name
            return []

    monkeypatch.setattr("app.services.industry_pulse.run.GoogleNewsRssProvider", Recorder)
    report = run_pulse(sources=[], published_evidence=[], today=TODAY)
    assert captured["name"] == "google_news_rss"
    assert report["provider"] == "google_news_rss"


def test_existing_google_matrix_still_32() -> None:
    assert len(generate_pulse_queries()) == 32


def test_offline_bakeoff_marks_paid_unavailable() -> None:
    report = run_bakeoff(sources=[], published_evidence=[], include_live=False, today=TODAY)
    by_name = {row["provider"]: row for row in report["providers"]}
    assert by_name["google_news_rss"]["live"] is False
    assert by_name["google_news_rss"]["unavailable_reason"] == "live fetch disabled"
    assert by_name["exa"]["live"] is False
    assert "EXA_API_KEY" in (by_name["exa"]["unavailable_reason"] or "")
    assert by_name["firecrawl"]["live"] is False
    assert by_name["brightdata"]["live"] is False
