"""Competitive Moves V1 — derivation, patterns, seams, stakeholder UI."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.competitive_moves.board import compose_moves_board
from app.services.competitive_moves.derive import classify_move_type, derive_moves
from app.services.competitive_moves.models import MOVE_TYPES, TRUST_LIVE_MOVE
from app.services.competitive_moves.patterns import detect_patterns
from app.services.competitive_moves.research_desk import competitive_moves_for
from app.services.emerging_radar.cluster import cluster_hits
from app.services.emerging_radar.compose import attach_market_context
from app.services.emerging_radar.models import TRUST_LIVE, Development, SourceRef
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import SOURCE_TRADE

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

ENTITIES = [
    {"id": "company-hortifrut", "entity_type": "company", "name": "Hortifrut S.A.", "aliases": ["Hortifrut"]},
    {"id": "company-fall-creek-farm-and-nursery", "entity_type": "company", "name": "Fall Creek Farm & Nursery, Inc.", "aliases": ["Fall Creek"]},
    {"id": "company-planasa", "entity_type": "company", "name": "Plantas de Navarra, S.A.", "aliases": ["Planasa"]},
    {"id": "company-driscolls", "entity_type": "company", "name": "Driscoll's", "aliases": ["Driscolls"]},
    {"id": "variety-sekoya-nova", "entity_type": "variety", "name": "SEKOYA Nova", "aliases": ["Sekoya Nova"]},
]


def _hit(**overrides) -> DiscoveryHit:
    base = dict(
        title="Hortifrut and Naturipe expand a berry genetics platform",
        url="https://example.com/hortifrut-platform",
        source_domain="example.com",
        published_date="2026-08-17",
        snippet="Hortifrut licensed a managed variety platform with Naturipe.",
        query_id="radar:exa:licensing",
        query_text="licensing",
        geography="global",
        berry="blueberry",
        topic="radar_semantic",
        provider="exa",
        origin_publisher_name="Trade",
        origin_publisher_url="https://example.com/hortifrut-platform",
        qualifying=True,
        qualify_reasons=["named company Hortifrut", "explicit blueberry crop"],
        editorial_topic="variety_genetics",
        source_context=SOURCE_TRADE,
    )
    base.update(overrides)
    return DiscoveryHit(**base)


class FakeMarketRepo:
    def __init__(self) -> None:
        self.rows = [
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


def test_taxonomy_is_restrained() -> None:
    assert len(MOVE_TYPES) == 14
    assert "STRATEGY" not in MOVE_TYPES


def test_move_derivation_maps_event_types() -> None:
    rows = cluster_hits(
        [
            _hit(),
            _hit(
                title="Fall Creek introduces SEKOYA Nova blueberry",
                url="https://hortidaily.com/fall-creek-nova",
                source_domain="hortidaily.com",
                origin_publisher_url="https://hortidaily.com/fall-creek-nova",
                snippet="Fall Creek unveils SEKOYA Nova.",
                berry="blueberry",
            ),
            _hit(
                title="Planasa appoints Hans Liekens as Global Head of Innovation",
                url="https://italianberry.it/planasa-hans",
                source_domain="italianberry.it",
                origin_publisher_url="https://italianberry.it/planasa-hans",
                snippet="Planasa appointed Hans Liekens.",
                berry="strawberry",
                provider="specialist_rss",
            ),
            _hit(
                title="Driscoll's filed appeal in strawberry patent case",
                url="https://thepacker.com/driscoll-patent",
                source_domain="thepacker.com",
                origin_publisher_url="https://thepacker.com/driscoll-patent",
                snippet="Driscoll's appealed a strawberry patent ruling.",
                berry="strawberry",
                provider="specialist_rss",
            ),
        ],
        entities=ENTITIES,
        now=NOW,
    )
    types = {classify_move_type(row) for row in rows}
    assert "LICENSING" in types or "VARIETY_COMMERCIALIZATION" in types or "PARTNERSHIP" in types
    assert "GENETICS_LAUNCH" in types
    assert "LEADERSHIP" in types
    assert "PBR / IP" in types
    moves = derive_moves(rows, today=date(2026, 9, 2))
    assert all(move.trust_state == TRUST_LIVE_MOVE for move in moves)
    assert all(move.development_trust_state == TRUST_LIVE for move in moves)
    companies = {move.company_id for move in moves}
    assert "company-hortifrut" in companies
    assert "company-fall-creek-farm-and-nursery" in companies
    assert "company-planasa" in companies


def test_syndicated_developments_are_not_double_counted() -> None:
    hits = [
        _hit(),
        _hit(
            title="Hortifrut and Naturipe expand a berry genetics platform",
            url="https://www.msn.com/hortifrut-platform",
            source_domain="msn.com",
            origin_publisher_url="https://www.msn.com/hortifrut-platform",
            origin_publisher_name="MSN",
            snippet="Hortifrut licensed a managed variety platform with Naturipe.",
        ),
    ]
    developments = cluster_hits(hits, entities=ENTITIES, now=NOW)
    moves = derive_moves(developments)
    hort = [row for row in moves if row.company_id == "company-hortifrut"]
    assert len(hort) == 1
    assert hort[0].supporting_development_ids
    publishers = {src["publisher"] for src in hort[0].supporting_sources}
    assert "MSN" not in publishers or len(hort[0].supporting_sources) == 1


def test_pattern_grouping_requires_multiple_supporting_moves() -> None:
    rows = cluster_hits(
        [
            _hit(),
            _hit(
                title="Hortifrut packing expansion in Peru blueberries",
                url="https://freshplaza.com/hortifrut-peru",
                source_domain="freshplaza.com",
                origin_publisher_url="https://freshplaza.com/hortifrut-peru",
                snippet="Hortifrut announced a packing plant expansion in Peru.",
                provider="specialist_rss",
            ),
            _hit(
                title="Fall Creek introduces SEKOYA Nova blueberry",
                url="https://hortidaily.com/nova",
                source_domain="hortidaily.com",
                origin_publisher_url="https://hortidaily.com/nova",
                snippet="Fall Creek unveils SEKOYA Nova.",
            ),
        ],
        entities=ENTITIES,
        now=NOW,
    )
    moves = derive_moves(rows)
    patterns = detect_patterns(moves)
    hort = [row for row in patterns if row.company_id == "company-hortifrut"]
    assert hort
    assert hort[0].label == "REPEATED MOVE PATTERN"
    assert "strategy" not in hort[0].why.lower() or "not" in hort[0].why.lower()
    fall = [row for row in patterns if row.company_id == "company-fall-creek-farm-and-nursery"]
    assert fall == []


def test_chronology_reuses_development_dates() -> None:
    rows = cluster_hits(
        [
            _hit(published_date="2026-08-01"),
            _hit(
                title="Hortifrut packing expansion in Peru blueberries",
                url="https://freshplaza.com/hortifrut-peru",
                source_domain="freshplaza.com",
                origin_publisher_url="https://freshplaza.com/hortifrut-peru",
                snippet="Hortifrut announced a packing plant expansion in Peru.",
                published_date="2026-08-20",
                provider="specialist_rss",
            ),
        ],
        entities=ENTITIES,
        now=NOW,
    )
    moves = derive_moves(rows)
    hort = [row for row in moves if row.company_id == "company-hortifrut"]
    assert hort
    dates = [item.date for move in hort for item in move.timeline]
    assert dates
    assert all(item.trust_state == TRUST_LIVE for move in hort for item in move.timeline)


def test_market_context_copied_not_causal() -> None:
    rows = cluster_hits(
        [
            _hit(
                title="Peruvian blueberry packing expansion announced by Hortifrut",
                url="https://freshplaza.com/peru-pack",
                source_domain="freshplaza.com",
                origin_publisher_url="https://freshplaza.com/peru-pack",
                snippet="Hortifrut is expanding blueberry packing in Peru.",
                berry="blueberry",
                provider="specialist_rss",
            )
        ],
        entities=ENTITIES,
        now=NOW,
    )
    attach_market_context(rows, repo=FakeMarketRepo())
    moves = derive_moves(rows)
    assert moves
    assert moves[0].market_context
    assert "Not a claim" in moves[0].market_context["disclaimer"]


def test_trust_separation_never_promotes_moves() -> None:
    rows = cluster_hits([_hit()], entities=ENTITIES, now=NOW)
    rows[0].trusted_context = [{"kind": "TRUSTED EVIDENCE", "id": "ev-1", "title": "Hortifrut genetics", "href": "/evidence/ev-1", "relation": "related"}]
    moves = derive_moves(rows)
    assert moves[0].trust_state == TRUST_LIVE_MOVE
    assert moves[0].trusted_context[0]["kind"] == "TRUSTED EVIDENCE"


def test_competitive_moves_for_research_desk() -> None:
    rows = cluster_hits(
        [
            _hit(),
            _hit(
                title="Hortifrut packing expansion in Peru blueberries",
                url="https://freshplaza.com/hortifrut-peru",
                source_domain="freshplaza.com",
                origin_publisher_url="https://freshplaza.com/hortifrut-peru",
                snippet="Hortifrut announced a packing plant expansion in Peru.",
                provider="specialist_rss",
            ),
        ],
        entities=ENTITIES,
        now=NOW,
    )
    found = competitive_moves_for(
        companies=["company-hortifrut"],
        geography="geography-peru",
        berries=["berry-blueberry"],
        developments=rows,
        timeframe="30d",
        today=date(2026, 9, 2),
    )
    assert found
    assert all(row["company_id"] == "company-hortifrut" for row in found)
    assert all(row["trust_state"] == TRUST_LIVE_MOVE for row in found)


def test_moves_page_uses_radar_cache_not_fetch(monkeypatch, tmp_path: Path) -> None:
    rows = cluster_hits([_hit()], entities=ENTITIES, now=NOW)
    board = compose_moves_board(rows)
    monkeypatch.setattr("app.main.compose_moves_board", lambda inbox_dir=None: board)
    page = TestClient(app).get("/moves")
    assert page.status_code == 200
    html = page.text
    assert "Who is moving" in html
    assert "LIVE / UNREVIEWED MOVE" in html
    assert "Hortifrut" in html
    assert ">Moves<" in html


def test_company_page_shows_recent_competitive_moves(monkeypatch) -> None:
    rows = cluster_hits(
        [
            _hit(
                title="Planasa appoints Hans Liekens as Global Head of Innovation",
                url="https://italianberry.it/planasa-hans",
                source_domain="italianberry.it",
                origin_publisher_url="https://italianberry.it/planasa-hans",
                snippet="Planasa appointed Hans Liekens.",
                provider="specialist_rss",
            )
        ],
        entities=ENTITIES,
        now=NOW,
    )
    board = compose_moves_board(rows)
    monkeypatch.setattr("app.services.competitive_moves.board.compose_moves_board", lambda inbox_dir=None, developments=None: board)
    page = TestClient(app).get("/entities/company/company-planasa")
    assert page.status_code == 200
    assert "Recent competitive moves" in page.text
    assert "LIVE / UNREVIEWED MOVE" in page.text
    assert "Hans Liekens" in page.text


def test_investment_marketplace_is_not_an_acquisition() -> None:
    rows = cluster_hits(
        [
            _hit(
                title="Naturipe Farms, Hortifrut Collaborate with MBO to Expand One of the World's Most Comprehensive Berry Genetics Platforms - Agriculture Investment Marketplace",
                url="https://investinag.com/hortifrut-mbo",
                source_domain="investinag.com",
                origin_publisher_url="https://investinag.com/hortifrut-mbo",
                snippet="Hortifrut and Naturipe expanded a genetics platform with MBO.",
            )
        ],
        entities=ENTITIES,
        now=NOW,
    )
    assert classify_move_type(rows[0]) != "ACQUISITION / INVESTMENT"


def test_marketing_campaign_is_not_a_genetics_launch() -> None:
    rows = cluster_hits(
        [
            _hit(
                title="Hortifrut Launches a blueberry marketing campaign for retailers",
                url="https://thepacker.com/hortifrut-campaign",
                source_domain="thepacker.com",
                origin_publisher_url="https://thepacker.com/hortifrut-campaign",
                snippet="Hortifrut launched a marketing campaign for blueberries.",
                provider="specialist_rss",
            )
        ],
        entities=ENTITIES,
        now=NOW,
    )
    moves = derive_moves(rows)
    assert all(row.move_type != "GENETICS_LAUNCH" for row in moves)
