"""Emerging Developments Radar V1 — clustering, corroboration, seams, UI."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.emerging_radar.cache import (
    append_watch_events,
    cache_is_fresh,
    edition_from_cache,
)
from app.services.emerging_radar.cluster import (
    classify_event_type,
    cluster_hits,
    corroboration_shape,
    source_from_hit,
)
from app.services.emerging_radar.compose import (
    apply_watchlist,
    attach_market_context,
    attach_trusted_context,
)
from app.services.emerging_radar.models import TRUST_LIVE
from app.services.emerging_radar.queries import (
    radar_google_queries,
    radar_query_budget,
    radar_semantic_queries,
)
from app.services.emerging_radar.research_desk import developments_for
from app.services.emerging_radar.run import run_radar_intelligence
from app.services.industry_pulse.matrix import generate_pulse_queries
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import SOURCE_TRADE, qualify_hit
from app.services.industry_pulse.run import names_from_entities
from app.services.watchlist import add_watch

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def _hit(**overrides) -> DiscoveryHit:
    base = dict(
        title="Pairwise announces seedless blackberry innovation with a nursery partner",
        url="https://example.com/pairwise-seedless",
        source_domain="example.com",
        published_date="2026-08-28",
        snippet="Pairwise and a caneberry breeding partner described a seedless blackberry cultivar for commercial trials.",
        query_id="radar:exa:unusual-rd",
        query_text="unusual berry research",
        geography="global",
        berry="blackberry",
        topic="radar_semantic",
        provider="exa",
        origin_publisher_name="Specialty trade",
        origin_publisher_url="https://example.com/pairwise-seedless",
        qualifying=True,
        qualify_reasons=["named company Pairwise", "explicit blackberry crop"],
        editorial_topic="variety_genetics",
        source_context=SOURCE_TRADE,
    )
    base.update(overrides)
    return DiscoveryHit(**base)


ENTITIES = [
    {
        "id": "company-pairwise",
        "entity_type": "company",
        "name": "Pairwise",
        "aliases": ["Pairwise Plants"],
    },
    {
        "id": "company-driscolls",
        "entity_type": "company",
        "name": "Driscoll's",
        "aliases": ["Driscolls"],
    },
    {
        "id": "variety-sekoya",
        "entity_type": "variety",
        "name": "Sekoya",
        "aliases": ["Sekoya Pop"],
    },
]


class FakeMarketRepo:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or [
            {
                "metric": "EXPORT_VOLUME",
                "unit": "t",
                "source_commodity_code": "BLUEBERRY",
                "form": "fresh",
                "geography": "PE",
                "geography_id": "geography-peru",
                "berry_id": "berry-blueberry",
                "period": "2024",
                "period_type": "year",
                "value": 100.0,
            },
            {
                "metric": "EXPORT_VOLUME",
                "unit": "t",
                "source_commodity_code": "BLUEBERRY",
                "form": "fresh",
                "geography": "PE",
                "geography_id": "geography-peru",
                "berry_id": "berry-blueberry",
                "period": "2025",
                "period_type": "year",
                "value": 132.2,
            },
        ]

    def latest_by_key(self, **filters):
        out = list(self.rows)
        if filters.get("berry_id"):
            out = [row for row in out if row.get("berry_id") == filters["berry_id"]]
        if filters.get("geography_id"):
            out = [row for row in out if row.get("geography_id") == filters["geography_id"]]
        return out


def test_radar_queries_are_not_pulse_32_and_stay_simple() -> None:
    google = radar_google_queries()
    semantic = radar_semantic_queries()
    pulse = generate_pulse_queries()
    assert len(pulse) == 32
    assert len(google) == 8
    assert len(semantic) == 12
    budget = radar_query_budget()
    assert budget["pulse_32"] == 0
    assert budget["exa_semantic"] == 12
    for query in semantic:
        assert query.kind == "radar_semantic"
        assert query.text.count("(") <= 1
        assert "when:" not in query.text
    for query in google:
        assert query.kind == "radar_theme"
        assert len(query.text) < 120


def test_event_taxonomy_is_restrained() -> None:
    assert classify_event_type("exclusive license for a new blueberry cultivar") == "LICENSING"
    assert classify_event_type("greenhouse production expansion in Peru") == "PRODUCTION_EXPANSION"
    assert classify_event_type("seedless blackberry CRISPR trial") == "GENETICS_INNOVATION"
    assert classify_event_type("PBR certificate issued for a raspberry") == "PBR"


def test_clustering_merges_syndicated_copies_but_not_independent_publishers() -> None:
    original = _hit()
    syndicate = _hit(
        title="Pairwise announces seedless blackberry innovation with a nursery partner",
        url="https://www.msn.com/en-us/pairwise-seedless",
        source_domain="msn.com",
        origin_publisher_name="MSN",
        origin_publisher_url="https://www.msn.com/en-us/pairwise-seedless",
        provider="google_news_rss",
    )
    independent = _hit(
        title="Pairwise seedless blackberry cultivar heads into grower trials",
        url="https://www.fruitnet.com/pairwise-trials",
        source_domain="fruitnet.com",
        origin_publisher_name="Fruitnet",
        origin_publisher_url="https://www.fruitnet.com/pairwise-trials",
        provider="specialist_rss",
        snippet="Fruitnet reports Pairwise is taking the seedless blackberry into licensed grower trials in California.",
    )
    other = _hit(
        title="Driscoll's strawberries open a new packing plant in Morocco",
        url="https://freshplaza.com/driscolls-morocco",
        source_domain="freshplaza.com",
        origin_publisher_name="FreshPlaza",
        origin_publisher_url="https://freshplaza.com/driscolls-morocco",
        berry="strawberry",
        provider="google_news_rss",
        snippet="Driscoll's announced a strawberry packing expansion in Morocco.",
        qualify_reasons=["named company Driscoll's", "explicit strawberry crop"],
    )
    developments = cluster_hits(
        [original, syndicate, independent, other],
        entities=ENTITIES,
        now=NOW,
    )
    assert len(developments) == 2
    pairwise = next(row for row in developments if "Pairwise" in row.title or "pairwise" in " ".join(row.company_names))
    assert pairwise.source_count == 3
    assert pairwise.independent_source_count >= 2
    assert pairwise.corroboration in {"MULTIPLE INDEPENDENT SOURCES", "COMPANY CLAIM + INDEPENDENT REPORT"}
    msn = [source for source in pairwise.sources if "msn.com" in source.domain]
    assert msn
    assert msn[0].syndicated is True


def test_semantic_similarity_proposes_but_does_not_silently_merge() -> None:
    a = _hit(title="Havecon builds a berry greenhouse in the Netherlands")
    b = _hit(
        title="Royal Berry expands glasshouse berry production with a Dutch partner",
        url="https://hortidaily.com/royal-berry",
        source_domain="hortidaily.com",
        origin_publisher_url="https://hortidaily.com/royal-berry",
        origin_publisher_name="HortiDaily",
        snippet="Royal Berry is expanding controlled-environment berry production.",
        qualify_reasons=["explicit berry-industry collective"],
    )
    developments = cluster_hits([a, b], entities=ENTITIES, now=NOW)
    assert len(developments) == 2


def test_corroboration_shapes_are_explicit_not_scores() -> None:
    one = [source_from_hit(_hit())]
    assert corroboration_shape(one)[0] == "ONE SOURCE"
    linkedin = source_from_hit(
        _hit(
            url="https://www.linkedin.com/posts/breeder-123",
            source_domain="linkedin.com",
            origin_publisher_url="https://www.linkedin.com/posts/breeder-123",
            origin_publisher_name="LinkedIn",
        )
    )
    assert linkedin.social is True
    shape, _ = corroboration_shape([linkedin])
    assert shape == "COMMUNITY / CHATTER — UNVERIFIED"
    official = source_from_hit(_hit())
    official.official = True
    official.domain = "ams.usda.gov"
    official.registry = True
    press = source_from_hit(
        _hit(
            url="https://freshplaza.com/usda-note",
            source_domain="freshplaza.com",
            origin_publisher_url="https://freshplaza.com/usda-note",
        )
    )
    assert corroboration_shape([official, press])[0] in {"OFFICIAL + PRESS", "REGISTRY + PRESS"}


def test_story_evolution_updates_one_development() -> None:
    first = cluster_hits([_hit()], entities=ENTITIES, now=NOW)
    later_hit = _hit(
        title="Pairwise confirms commercial seedless blackberry trials with a West Coast nursery",
        url="https://freshplaza.com/pairwise-confirms",
        source_domain="freshplaza.com",
        origin_publisher_url="https://freshplaza.com/pairwise-confirms",
        origin_publisher_name="FreshPlaza",
        published_date="2026-09-01",
        provider="specialist_rss",
        snippet="The company confirmed acreage for first commercial seedless blackberry fruit.",
    )
    second = cluster_hits([_hit(), later_hit], entities=ENTITIES, previous=first, now=NOW)
    assert len(second) == 1
    row = second[0]
    assert row.id == first[0].id
    assert row.first_seen == first[0].first_seen
    kinds = {event.kind for event in row.evolution}
    assert "FIRST_SEEN" in kinds
    assert "NEW_SOURCE" in kinds


def test_publisher_homepage_urls_do_not_collapse_distinct_developments() -> None:
    nova = _hit(
        title="Nova Siri Genetics set to distribute 150 millions of strawberry plants",
        url="https://italianberry.it",
        source_domain="italianberry.it",
        origin_publisher_url="https://italianberry.it",
        origin_publisher_name="Italian Berry",
        provider="specialist_rss",
        snippet="Nova Siri Genetics will increase strawberry plant distribution by 15 percent.",
        berry="strawberry",
    )
    ceo = _hit(
        title="Brie Reiter Smith appointed CEO of Driscoll's",
        url="https://italianberry.it",
        source_domain="italianberry.it",
        origin_publisher_url="https://italianberry.it",
        origin_publisher_name="Italian Berry",
        provider="specialist_rss",
        snippet="Driscoll's appointed Brie Reiter Smith as chief executive officer.",
        berry="",
    )
    first = cluster_hits([nova], entities=ENTITIES, now=NOW)
    second = cluster_hits([nova, ceo], entities=ENTITIES, previous=first, now=NOW)
    assert len(second) == 2
    assert len({row.id for row in second}) == 2
    titles = " ".join(row.title for row in second)
    assert "Nova Siri" in titles
    assert "Brie Reiter" in titles
    assert second[0].id == first[0].id or second[1].id == first[0].id


def test_no_trust_mutation_when_attaching_trusted_context() -> None:
    evidence = [
        {
            "id": "ev-pairwise-1",
            "title": "Pairwise public note",
            "status": "published",
            "entity_ids": ["company-pairwise"],
            "summary": "Trusted write-up",
        }
    ]
    snapshot = json.dumps(evidence)
    developments = cluster_hits([_hit()], entities=ENTITIES, now=NOW)
    attach_trusted_context(developments, evidence=evidence, assessments=[])
    assert json.dumps(evidence) == snapshot
    assert developments[0].trust_state == TRUST_LIVE
    assert developments[0].trusted_context
    assert developments[0].trusted_context[0]["kind"] == "TRUSTED EVIDENCE"


def test_watchlist_seam_emits_event_without_notifications(tmp_path: Path) -> None:
    add_watch(tmp_path, "company", "company-pairwise")
    developments = cluster_hits([_hit()], entities=ENTITIES, now=NOW)
    events = apply_watchlist(developments, [{"watch_type": "company", "object_id": "company-pairwise"}])
    assert events
    assert events[0]["event_type"] == "watchlist_development_match"
    assert events[0]["development_id"] == developments[0].id
    path = append_watch_events(events, inbox_dir=tmp_path)
    assert path is not None
    written = path.read_text(encoding="utf-8")
    assert "watchlist_development_match" in written
    append_watch_events(events, inbox_dir=tmp_path)
    assert written == path.read_text(encoding="utf-8")


def test_market_context_is_linked_not_causal() -> None:
    hit = _hit(
        title="Peruvian blueberry packing expansion announced",
        snippet="A new packing plant for blueberries in Peru is under construction.",
        berry="blueberry",
        qualify_reasons=["explicit blueberry crop"],
    )
    developments = cluster_hits([hit], entities=ENTITIES, now=NOW)
    attach_market_context(developments, repo=FakeMarketRepo())
    assert developments[0].geography_ids
    assert developments[0].market_context
    assert "Not a claim" in developments[0].market_context["disclaimer"]
    assert any("EXPORT_VOLUME" in row["label"] for row in developments[0].market_context["rows"])


def test_parenthetical_third_party_nationality_is_not_tagged_as_geography() -> None:
    # Real production defect: "Inka's Berries operates a new blueberry
    # packing plant in Ica" (a Peru story) was tagged geography-spain
    # purely because its snippet named an unrelated co-investor
    # parenthetically as "(a Spanish firm...)". The event's own location
    # is Ica (title + main-clause "Ica farm"), which maps to Peru. Spain
    # must not become the direct geography from the parenthetical firm.
    hit = _hit(
        title="Inka's Berries operates a new blueberry packing plant in Ica",
        snippet=(
            "It will probably be a new variety that is being developed this year, together with "
            "Bloom Fresh (a Spanish firm that acquired 66% of the genetics business). The plan is "
            "that of these 200 hectares, 100 hectares will be used for new growth on the Ica farm."
        ),
        berry="blueberry",
        qualify_reasons=["explicit blueberry crop"],
    )
    developments = cluster_hits([hit], entities=ENTITIES, now=NOW)
    assert developments[0].geography_ids == ("geography-peru",)
    assert "geography-spain" not in developments[0].geography_ids


def test_geography_stated_in_main_clause_still_resolves() -> None:
    # The fix must not blind the whole pipeline to real geography
    # mentions -- only parenthetical asides are excluded.
    hit = _hit(
        title="Berry Fresh expands blueberry production in Chile",
        snippet="The company confirmed a new planting program in Chile this season.",
        berry="blueberry",
        qualify_reasons=["explicit blueberry crop"],
    )
    developments = cluster_hits([hit], entities=ENTITIES, now=NOW)
    assert "geography-chile" in developments[0].geography_ids


def test_geography_named_only_inside_parens_is_still_excluded_even_when_it_is_the_only_mention() -> None:
    # A stricter check than the two above: even when a geography name
    # appears NOWHERE outside parentheses, it must not leak through.
    hit = _hit(
        title="Regional berry group announces new partnership",
        snippet="The consortium partnered with a fruit cooperative (based in Poland) on logistics.",
        berry="blueberry",
        qualify_reasons=["explicit blueberry crop"],
    )
    developments = cluster_hits([hit], entities=ENTITIES, now=NOW)
    assert developments[0].geography_ids == ()


def test_developments_for_research_desk_filters() -> None:
    rows = cluster_hits(
        [
            _hit(),
            _hit(
                title="Driscoll's strawberries open a new packing plant in Morocco",
                url="https://freshplaza.com/driscolls-morocco",
                source_domain="freshplaza.com",
                origin_publisher_url="https://freshplaza.com/driscolls-morocco",
                berry="strawberry",
                snippet="Driscoll's announced a strawberry packing expansion in Morocco.",
                qualify_reasons=["named company Driscoll's", "explicit strawberry crop"],
            ),
        ],
        entities=ENTITIES,
        now=NOW,
    )
    found = developments_for(
        company_ids=["company-pairwise"],
        berry_ids=["berry-blackberry"],
        event_types=["GENETICS_INNOVATION", "VARIETY_LAUNCH", "PARTNERSHIP", "LICENSING"],
        developments=rows,
        timeframe="30d",
        today=date(2026, 9, 2),
    )
    assert found
    assert all(row["trust_state"] == TRUST_LIVE for row in found)
    assert all("company-pairwise" in row["company_ids"] for row in found)


def test_linkedin_is_metadata_only_not_scraped() -> None:
    hit = _hit(
        title="Breeder notes a new caneberry license on LinkedIn",
        url="https://www.linkedin.com/posts/public-breeder-post",
        source_domain="linkedin.com",
        origin_publisher_url="https://www.linkedin.com/posts/public-breeder-post",
        origin_publisher_name="LinkedIn",
        snippet="Public post about a blackberry licensing conversation.",
    )
    source = source_from_hit(hit)
    assert source.social is True
    assert "linkedin.com" in source.url
    developments = cluster_hits([hit], entities=ENTITIES, now=NOW)
    assert developments[0].weak_signal_label == "COMMUNITY / CHATTER — UNVERIFIED"
    profile = _hit(
        title="Jessica Gilbert",
        url="https://www.linkedin.com/in/jessica-gilbert",
        source_domain="linkedin.com",
        origin_publisher_url="https://www.linkedin.com/in/jessica-gilbert",
        origin_publisher_name="LinkedIn",
    )
    assert cluster_hits([profile], entities=ENTITIES, now=NOW) == []


def test_entertainment_driscoll_false_positive_is_rejected() -> None:
    hit = _hit(
        title="Grey's Anatomy recap: Driscoll's soap-opera storyline",
        snippet="Last night's episode.",
        qualifying=False,
        url="https://tv.example/greys",
        source_domain="tv.example",
    )
    qualify_hit(hit, company_names=names_from_entities(ENTITIES, prefix="company-"), variety_names=())
    assert hit.qualifying is False
    assert cluster_hits([hit], entities=ENTITIES, now=NOW) == []


def test_run_radar_persists_cache_and_does_not_call_pulse_32(tmp_path: Path) -> None:
    edition = run_radar_intelligence(
        providers=(),
        entities=ENTITIES,
        evidence=[],
        assessments=[],
        inbox_dir=tmp_path,
        persist=True,
        now=NOW,
        seed_hits=[_hit()],
        market_repo=FakeMarketRepo(),
    )
    assert edition.developments
    assert edition.trust_label == TRUST_LIVE
    assert cache_is_fresh(inbox_dir=tmp_path, now=NOW)
    loaded = edition_from_cache(inbox_dir=tmp_path, now=NOW)
    assert loaded is not None
    assert loaded.developments[0].id == edition.developments[0].id


def _stub_edition(tmp_path: Path):
    return run_radar_intelligence(
        providers=(),
        entities=ENTITIES,
        evidence=[],
        assessments=[],
        inbox_dir=tmp_path,
        persist=True,
        now=NOW,
        seed_hits=[_hit()],
    )


def test_radar_shell_does_not_fetch(monkeypatch, tmp_path: Path) -> None:
    def boom(**kwargs):
        raise AssertionError("empty /radar must not run live discovery")

    monkeypatch.setattr("app.main.INBOX_DIR", tmp_path)
    monkeypatch.setattr("app.main.run_radar_intelligence", boom)
    page = TestClient(app).get("/radar")
    assert page.status_code == 200
    html = page.text
    assert "Emerging developments" in html
    assert "LIVE / UNREVIEWED DEVELOPMENT" in html
    assert ">Radar<" in html
    assert "stakeholder.css" in html
    assert "Publication Review" not in html
    assert "/radar/live" in html


def test_radar_live_renders_development_cards(monkeypatch, tmp_path: Path) -> None:
    edition = _stub_edition(tmp_path)
    monkeypatch.setattr("app.main.INBOX_DIR", tmp_path)
    monkeypatch.setattr("app.main.run_radar_intelligence", lambda **kwargs: edition)
    page = TestClient(app).get("/radar/live")
    assert page.status_code == 200
    html = page.text
    assert "Why this is on your radar" in html
    assert "LIVE / UNREVIEWED DEVELOPMENT" in html
    assert "Pairwise" in html
    detail = TestClient(app).get(f"/radar/{edition.developments[0].id}")
    assert detail.status_code == 200
    assert "How this story evolved" in detail.text
