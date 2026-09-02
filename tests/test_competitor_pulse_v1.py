from __future__ import annotations

from datetime import datetime, timezone

from app.services.competitor_pulse import (
    CATEGORY_COMMERCIAL,
    CATEGORY_MAINSTREAM,
    CATEGORY_MARKET,
    CATEGORY_PATENT,
    CATEGORY_VARIETY,
    TRUST_LABEL,
    BriefStatement,
    build_query_text,
    categorize_hit,
    company_query_terms,
    detect_berry,
    detect_geography,
    find_live_hit_by_url,
    generate_current_brief,
    run_company_pulse,
)
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider


def _hit(**overrides) -> DiscoveryHit:
    base = dict(
        title="Fall Creek unveils new blueberry cultivar",
        url="https://example.com/a",
        source_domain="example.com",
        published_date="2026-08-30",
        snippet="Fall Creek Farm & Nursery announced a new managed variety.",
        query_id="ad-hoc:any:global:any:7d",
        query_text="",
        geography="global",
        berry=None,
        topic="ad_hoc",
        provider="memory",
        origin_publisher_name="Example Trade Press",
        origin_publisher_url="https://example.com/a",
    )
    base.update(overrides)
    return DiscoveryHit(**base)


def test_company_query_terms_uses_name_aliases_and_owned_brand():
    company = {
        "id": "company-fall-creek-farm-and-nursery",
        "name": "Fall Creek Farm & Nursery, Inc.",
        "aliases": ["Fall Creek", "Fall Creek Nursery"],
    }
    relationships = [
        {
            "subject_id": "company-fall-creek-farm-and-nursery",
            "predicate": "owns",
            "object_id": "brand-sekoya",
            "status": "active",
        },
        {
            "subject_id": "company-other",
            "predicate": "owns",
            "object_id": "brand-unrelated",
            "status": "active",
        },
    ]
    entities_by_id = {"brand-sekoya": {"entity_type": "brand", "name": "Sekoya"}}
    terms = company_query_terms(company, relationships=relationships, entities_by_id=entities_by_id)
    assert terms == ["Fall Creek Farm & Nursery, Inc.", "Fall Creek", "Fall Creek Nursery", "Sekoya"]


def test_company_query_terms_never_invents_without_a_relationship():
    company = {"id": "company-x", "name": "Driscoll's, Inc.", "aliases": ["Driscoll's"]}
    terms = company_query_terms(company, relationships=[], entities_by_id={})
    assert terms == ["Driscoll's, Inc.", "Driscoll's"]


def test_build_query_text_quotes_multiword_terms():
    text = build_query_text(["Fall Creek", "Sekoya"])
    assert text == '("Fall Creek" OR Sekoya)'


def test_categorize_hit_patent_beats_variety_keyword_overlap():
    hit = _hit(title="CPVO grants plant breeders rights for new cultivar")
    assert categorize_hit(hit) == CATEGORY_PATENT


def test_categorize_hit_variety():
    hit = _hit(title="Breeder unveils new blueberry cultivar trial results", snippet="")
    assert categorize_hit(hit) == CATEGORY_VARIETY


def test_categorize_hit_commercial():
    hit = _hit(title="Company X announces partnership and licensing deal", snippet="")
    assert categorize_hit(hit) == CATEGORY_COMMERCIAL


def test_categorize_hit_market():
    hit = _hit(title="Export acreage and pricing report for the season", snippet="")
    assert categorize_hit(hit) == CATEGORY_MARKET


def test_categorize_hit_mainstream_when_only_named_company_matches():
    hit = _hit(title="Driscoll's reports quarterly earnings", snippet="")
    hit.qualify_reasons = ["named company Driscoll's"]
    assert categorize_hit(hit) == CATEGORY_MAINSTREAM


def test_detect_berry_and_geography_are_best_effort_and_never_invent():
    text = "Blueberry growers in Chile report a strong season"
    assert detect_berry(text) == "berry-blueberry"
    assert detect_geography(text) == "americas"
    assert detect_berry("A generic business story") is None
    assert detect_geography("A generic business story") is None


def test_run_company_pulse_qualifies_dedupes_and_labels_live_unreviewed():
    company = {"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek Farm & Nursery, Inc.", "aliases": ["Fall Creek"]}
    duplicate = _hit(url="https://example.com/a")
    unrelated = _hit(
        title="Local bakery shares strawberry shortcake recipe",
        snippet="A recipe for dessert.",
        url="https://example.com/b",
        origin_publisher_url="https://example.com/b",
    )
    provider = MemoryProvider(hits=[duplicate, duplicate, unrelated])
    result = run_company_pulse(
        company,
        window="7d",
        providers=[provider],
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    assert result.window == "7d"
    assert result.raw_hit_count == 3  # duplicate appears twice in the raw provider list + one unrelated hit
    assert result.qualifying_count == 1  # duplicate collapsed, recipe noise rejected
    assert result.items[0].trust_label == TRUST_LABEL
    assert result.items[0].url == "https://example.com/a"
    assert result.searched_at == "2026-09-01T00:00:00+00:00"


def test_run_company_pulse_rejects_unsupported_window():
    import pytest

    with pytest.raises(ValueError):
        run_company_pulse({"id": "c", "name": "X"}, window="90d", providers=[])


def test_run_company_pulse_rejects_ambiguous_short_alias_without_corroboration():
    # "Fall Creek" alone is also a real Wisconsin town -- a plain match with
    # no berry/industry signal must NOT qualify just because it echoes a
    # short company alias.
    company = {
        "id": "company-fall-creek-farm-and-nursery",
        "name": "Fall Creek Farm & Nursery, Inc.",
        "aliases": ["Fall Creek"],
    }
    town_noise = _hit(
        title="Fall Creek Library packs up and prepares to move into new building",
        snippet="",
        url="https://example.com/town",
        origin_publisher_url="https://example.com/town",
    )
    real_company_news = _hit(
        title="Fall Creek unveils new blueberry cultivar",
        snippet="Fall Creek Farm & Nursery announced a new managed variety.",
        url="https://example.com/company",
        origin_publisher_url="https://example.com/company",
    )
    provider = MemoryProvider(hits=[town_noise, real_company_news])
    result = run_company_pulse(company, providers=[provider])
    urls = {item.url for item in result.items}
    assert "https://example.com/company" in urls
    assert "https://example.com/town" not in urls


def test_run_company_pulse_rejects_same_topic_different_company_hit():
    # Provider returns a berry-industry story that qualifies on crop/industry
    # terms alone but never actually names Fall Creek anywhere -- it must
    # not be attributed to Fall Creek's pulse.
    company = {"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek Farm & Nursery, Inc.", "aliases": ["Fall Creek"]}
    unrelated_company_news = _hit(
        title="Berry Fresh to expand Oregon blueberry production",
        snippet="Berry Fresh announced an expansion of its Oregon operations.",
        url="https://example.com/other-company",
        origin_publisher_url="https://example.com/other-company",
    )
    provider = MemoryProvider(hits=[unrelated_company_news])
    result = run_company_pulse(company, providers=[provider])
    assert result.items == []


def test_run_company_pulse_matches_curly_apostrophe_in_provider_title():
    # Google News returns typographic "smart quotes"; company aliases in
    # this system's own entity records use a plain ASCII apostrophe. A
    # real mention must still match -- this was a genuine miss caught by
    # the mission's manual-web-challenge acceptance step (Driscoll's
    # lawsuit/leadership coverage silently invisible to the live page).
    company = {"id": "company-driscolls", "name": "Driscoll's, Inc.", "aliases": ["Driscoll's"]}
    hit = _hit(
        title="Driscoll’s CEO steps down amid growing pressure",
        snippet="Driscoll’s berries face scrutiny over sustainability claims.",
        url="https://example.com/lawsuit",
        origin_publisher_url="https://example.com/lawsuit",
    )
    provider = MemoryProvider(hits=[hit])
    result = run_company_pulse(company, providers=[provider])
    assert [item.url for item in result.items] == ["https://example.com/lawsuit"]


def test_run_company_pulse_survives_a_failing_provider():
    class Boom:
        name = "boom"

        def discover(self, query):
            raise RuntimeError("provider down")

    company = {"id": "company-x", "name": "Driscoll's, Inc.", "aliases": ["Driscoll's"]}
    result = run_company_pulse(company, providers=[Boom()])
    assert result.provider_telemetry["boom"]["errors"] == 1
    assert result.items == []


def test_generate_current_brief_grounds_every_statement():
    from app.services.competitor_pulse import CompanyPulseItem

    items = [
        CompanyPulseItem(
            title="Fall Creek unveils new cultivar",
            url="https://example.com/a",
            publisher="Example Trade Press",
            published_date="2026-08-30",
            captured_at="2026-09-01T00:00:00+00:00",
            snippet="A new managed variety.",
            category=CATEGORY_VARIETY,
            berry="berry-blueberry",
            geography=None,
            provider="memory",
            provider_query_provenance=["memory"],
        )
    ]

    class FakeResult:
        parsed = {"statements": [{"text": "Fall Creek unveiled a new cultivar.", "source_ids": ["live-0"]}]}

    def fake_completer(prompt, **kwargs):
        assert "internal" not in prompt.lower() or "internal strategy team" in prompt.lower()
        return FakeResult()

    statements = generate_current_brief(items, completer=fake_completer)
    assert statements == (BriefStatement(text="Fall Creek unveiled a new cultivar.", source_ids=("live-0",)),)


def test_generate_current_brief_drops_ungrounded_statements():
    from app.services.competitor_pulse import CompanyPulseItem

    items = [
        CompanyPulseItem(
            title="Fall Creek unveils new cultivar",
            url="https://example.com/a",
            publisher="Example Trade Press",
            published_date="2026-08-30",
            captured_at="2026-09-01T00:00:00+00:00",
            snippet="",
            category=CATEGORY_VARIETY,
            berry=None,
            geography=None,
            provider="memory",
            provider_query_provenance=["memory"],
        )
    ]

    class FakeResult:
        parsed = {"statements": [{"text": "Unsupported claim.", "source_ids": ["nonexistent-id"]}]}

    statements = generate_current_brief(items, completer=lambda *a, **k: FakeResult())
    assert statements == ()


def test_generate_current_brief_returns_empty_without_completer_or_items():
    assert generate_current_brief([], completer=lambda *a, **k: None) == ()
    assert generate_current_brief([object()], completer=None) == ()  # type: ignore[list-item]


def test_find_live_hit_by_url_matches_qualifying_deduped_hit():
    company = {"id": "company-fall-creek-farm-and-nursery", "name": "Fall Creek Farm & Nursery, Inc.", "aliases": ["Fall Creek"]}
    hit = _hit(url="https://example.com/a", origin_publisher_url="https://example.com/a")
    provider = MemoryProvider(hits=[hit])
    found = find_live_hit_by_url(company, window="7d", providers=[provider], url="https://example.com/a")
    assert found is not None
    assert found.url == "https://example.com/a"


def test_find_live_hit_by_url_returns_none_when_not_found():
    company = {"id": "company-x", "name": "Driscoll's, Inc.", "aliases": ["Driscoll's"]}
    provider = MemoryProvider(hits=[])
    found = find_live_hit_by_url(company, window="7d", providers=[provider], url="https://example.com/missing")
    assert found is None
