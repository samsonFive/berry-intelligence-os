"""Canonical contract for Direct Source Upgrade + Coverage Gap Closure V1."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.article_dedup import normalize_canonical_url
from app.services.source_cadence import cadence_seconds
from app.services.source_freshness import STALE, classify_source_freshness
from app.services.source_lifecycle import is_collection_eligible


ROOT = Path(__file__).resolve().parents[1]
NEW_SOURCE_IDS = {
    "source-20260825-advanced-berry-breeding-news": "company-advanced-berry-breeding",
    "source-20260825-summer-berry-company-news": "company-the-summer-berry-company",
}
LINKAGE_UPGRADES = {
    "source-freshuelva-news": "company-freshuelva",
    "source-nova-siri-genetics-news": "company-nova-siri-genetics",
}


def _sources() -> dict[str, dict]:
    rows = json.loads((ROOT / "data" / "configuration" / "sources.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in rows}


def _policy() -> dict:
    return json.loads(
        (ROOT / "data" / "configuration" / "source_collection_cadence.json").read_text(encoding="utf-8")
    )


def test_new_direct_sources_are_bounded_official_rss_and_company_linked() -> None:
    sources = _sources()
    for source_id, company_id in NEW_SOURCE_IDS.items():
        source = sources[source_id]
        discovery = source["discovery"]
        assert source["enabled"] is True
        assert source["linked_competitor_ids"] == [company_id]
        assert discovery["adapter"] == "article_rss"
        assert discovery["feed_url"].startswith("https://")
        assert discovery["item_limit"] == 10
        assert discovery["feed_url_verified_at"] == "2026-08-25"
        assert source["update_cadence"] == "weekly"


def test_existing_direct_source_identity_is_preserved_when_linkage_is_added() -> None:
    sources = _sources()
    for source_id, company_id in LINKAGE_UPGRADES.items():
        source = sources[source_id]
        assert source["linked_competitor_ids"] == [company_id]
        assert source["created_at"] == "2026-08-20"
        assert source["discovery"]["adapter"] == "article_rss"


def test_coverage_mix_and_source_counts_are_selective_not_broad_expansion() -> None:
    sources = list(_sources().values())
    discoverable = [source for source in sources if source.get("enabled") and source.get("discovery")]
    eligible = [source for source in sources if is_collection_eligible(source)]
    direct_rss = [source for source in discoverable if source["discovery"]["adapter"] == "article_rss"]
    linked_direct = [
        source
        for source in discoverable
        if source["discovery"]["adapter"] != "news_search_rss" and source.get("linked_competitor_ids")
    ]

    assert len(sources) == 198
    assert len(discoverable) == 75
    assert len(eligible) == 74  # Growing Produce remains scheduled-but-paused/operator-action-required.
    assert len(direct_rss) == 33
    assert len(linked_direct) == 18
    assert sum("berry-blueberry" in source.get("berry_ids", []) for source in discoverable) == 63
    assert sum("berry-strawberry" in source.get("berry_ids", []) for source in discoverable) == 45
    assert sum("berry-raspberry" in source.get("berry_ids", []) for source in discoverable) == 44
    assert sum("berry-blackberry" in source.get("berry_ids", []) for source in discoverable) == 43


def test_weekly_cadence_and_never_run_freshness_remain_existing_semantics() -> None:
    sources = _sources()
    policy = _policy()
    for source_id in NEW_SOURCE_IDS:
        source = sources[source_id]
        assert cadence_seconds(source, policy) == 604800
        freshness = classify_source_freshness(source, discovery_state=None)
        assert freshness.state == STALE
        assert "no discovery run" in freshness.reason.casefold()


def test_direct_rss_tracking_variant_shares_canonical_article_identity() -> None:
    tracked = (
        "https://www.abbreeding.nl/2026/07/27/malaika-gold-excellent-taste-award-2026/"
        "?utm_source=rss&utm_medium=rss&utm_campaign=malaika-gold-excellent-taste-award-2026"
    )
    canonical = "https://www.abbreeding.nl/2026/07/27/malaika-gold-excellent-taste-award-2026/"
    assert normalize_canonical_url(tracked) == normalize_canonical_url(canonical)


def test_direct_caneberry_sources_coexist_with_generic_search_guardrail() -> None:
    sources = _sources()
    generic = sources["source-news-search-caneberry-global"]
    assert generic["discovery"]["adapter"] == "news_search_rss"
    assert sources["source-20260825-advanced-berry-breeding-news"]["berry_ids"] == ["berry-raspberry"]
    assert "berry-raspberry" in sources["source-20260825-summer-berry-company-news"]["berry_ids"]
    assert "berry-blackberry" in sources["source-20260825-summer-berry-company-news"]["berry_ids"]
