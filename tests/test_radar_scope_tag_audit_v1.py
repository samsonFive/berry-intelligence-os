"""Radar data quality and scope-tag audit V1.

Proves the Inka Ica packing-plant defect: Spain entered because
EntityResolver treated 'Spanish firm' as event geography. Change Engine
is not modified.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.emerging_radar.cache import write_cache
from app.services.emerging_radar.cluster import EntityResolver, classify_event_type, cluster_hits
from app.services.emerging_radar.compose import compose_edition
from app.services.emerging_radar.models import Development
from app.services.emerging_radar.research_desk import developments_for
from app.services.emerging_radar.tag_audit import (
    RULE_BERRY_NOT_IN_TEXT,
    RULE_NATIONALITY_VS_PLACE,
    apply_deterministic_repair,
    audit_development,
    audit_radar_cache,
)
from app.services.geography_hierarchy import geography_scope_match
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.qualify import SOURCE_TRADE

EUROPE = frozenset({"geography-europe", "geography-spain", "geography-portugal", "geography-netherlands"})
INKA_SNIPPET = (
    '"It will probably be a new variety that is being developed this year (2025), '
    'together with Bloom Fresh (a Spanish firm that acquired 66% of the genetics '
    'business). The plan is that of these 200 hectares, 100 hectares will be used '
    'to replace older varieties that we still have (Biloxi and Matías), and the '
    'other 100 hectares will be used for new growth on the Ica farm," the executive explained.'
)


def _hit(**overrides) -> DiscoveryHit:
    base = dict(
        title="Inka's Berries operates a new blueberry packing plant in Ica",
        url="https://blueberriesconsulting.com/en/inkas-berries-opera-nueva-planta-de-empaque-de-arandanos-en-ica-los-destinos-a-atender/",
        source_domain="blueberriesconsulting.com",
        published_date="2026-08-28",
        snippet=INKA_SNIPPET,
        query_id="radar:exa:production-expansion",
        query_text="production expansion",
        geography="global",
        berry="blueberry",
        topic="radar_semantic",
        provider="exa",
        origin_publisher_name="Blueberries Consulting",
        origin_publisher_url="https://blueberriesconsulting.com/en/inkas-berries-opera-nueva-planta-de-empaque-de-arandanos-en-ica-los-destinos-a-atender/",
        qualifying=True,
        qualify_reasons=["explicit blueberry crop"],
        editorial_topic="production",
        source_context=SOURCE_TRADE,
    )
    base.update(overrides)
    return DiscoveryHit(**base)


def _stale_inka() -> Development:
    clustered = cluster_hits([_hit()], now=None)
    row = clustered[0]
    row.geography_ids = ("geography-spain",)
    row.geography_labels = ("Spain",)
    row.tag_provenance = ()
    row.event_type = "VARIETY_LAUNCH"
    row.what_happened = "Variety Launch: Inka's Berries operates a new blueberry packing plant in Ica"
    return row


def test_inka_spanish_firm_does_not_become_direct_spain() -> None:
    resolved = EntityResolver().resolve(
        f"{_hit().title} {INKA_SNIPPET}",
        title=_hit().title,
        snippet=INKA_SNIPPET,
    )
    assert resolved["geography_ids"] == ("geography-peru",)
    assert resolved["geography_labels"] == ("Peru",)
    assert "geography-spain" not in resolved["geography_ids"]
    origins = {(row["value"], row["origin"]) for row in resolved["tag_provenance"] if row["field"] == "geography"}
    assert ("geography-peru", "inferred_place") in origins
    assert ("geography-spain", "nationality_mention") in origins
    assert resolved["berry_ids"] == ("berry-blueberry",)


def test_inka_cluster_and_event_type_come_from_the_packing_plant_title() -> None:
    developments = cluster_hits([_hit()])
    assert len(developments) == 1
    row = developments[0]
    assert row.geography_ids == ("geography-peru",)
    assert row.event_type == "PRODUCTION_EXPANSION"
    assert row.berry_ids == ("berry-blueberry",)
    assert classify_event_type(f"{row.title} {INKA_SNIPPET}", title=row.title) == "PRODUCTION_EXPANSION"


def test_spain_noun_and_spanish_harvest_remain_spain() -> None:
    plant = EntityResolver().resolve(
        "Spain to open a blueberry packing plant in Huelva",
        title="Spain to open a blueberry packing plant in Huelva",
        snippet="The packing facility will serve export programmes.",
    )
    assert "geography-spain" in plant["geography_ids"]
    harvest = EntityResolver().resolve(
        "Spanish blueberry harvest delayed by weather",
        title="Spanish blueberry harvest delayed by weather",
        snippet="Growers in the south reported delayed picking.",
    )
    assert harvest["geography_ids"] == ("geography-spain",)


def test_planasa_huelva_and_atlantic_blue_keep_legitimate_spain() -> None:
    planasa = EntityResolver().resolve(
        "Planasa launches Blue Maldiva from Huelva, Spain",
        title="Planasa launches Blue Maldiva from Huelva, Spain",
        snippet="The breeding programme presented Blue Maldiva and Blue Manila in Huelva.",
    )
    assert "geography-spain" in planasa["geography_ids"]
    atlantic = EntityResolver().resolve(
        "Hortifrut Genetic Development continues Atlantic Blue work in Spain and Peru",
        title="Hortifrut Genetic Development continues Atlantic Blue work in Spain and Peru",
        snippet="The Royal Berries programme remains linked to Spain and Peru.",
    )
    assert "geography-spain" in atlantic["geography_ids"]
    assert "geography-peru" in atlantic["geography_ids"]


def test_hortifrut_mbo_americas_does_not_inherit_europe() -> None:
    resolved = EntityResolver().resolve(
        "Hortifrut completes MBO of Mountain Blue Orchards platform in the Americas",
        title="Hortifrut completes MBO of Mountain Blue Orchards platform in the Americas",
        snippet="The transaction covers the Americas berry platform.",
    )
    assert "geography-spain" not in resolved["geography_ids"]
    assert not geography_scope_match(resolved["geography_ids"], EUROPE)


def test_zara_strawberry_does_not_inherit_blueberry() -> None:
    resolved = EntityResolver(
        [
            {
                "id": "company-driscolls",
                "entity_type": "company",
                "name": "Driscoll's",
                "aliases": ["Driscolls"],
            }
        ]
    ).resolve(
        "Driscoll's Zara named best overall supermarket strawberry",
        title="Driscoll's Zara named best overall supermarket strawberry",
        snippet="The UK retailer trial scored Zara as the leading strawberry.",
    )
    assert resolved["berry_ids"] == ("berry-strawberry",)
    assert "berry-blueberry" not in resolved["berry_ids"]
    assert resolved["company_ids"] == ("company-driscolls",)


def test_un_m49_does_not_inherit_blueberry_from_a_geography_catalog() -> None:
    resolved = EntityResolver().resolve(
        "UN M49 Standard Country or Area Codes for Statistical Use",
        title="UN M49 Standard Country or Area Codes for Statistical Use",
        snippet="Statistical geographic codes used for country groupings.",
    )
    assert resolved["berry_ids"] == ()
    assert resolved["geography_ids"] == ()


def test_raspberry_patent_stays_raspberry() -> None:
    resolved = EntityResolver().resolve(
        "USPTO plant patent for a primocane raspberry cultivar",
        title="USPTO plant patent for a primocane raspberry cultivar",
        snippet="The patent describes a raspberry plant with primocane fruiting.",
    )
    assert resolved["berry_ids"] == ("berry-raspberry",)
    assert classify_event_type(
        "USPTO plant patent for a primocane raspberry cultivar",
        title="USPTO plant patent for a primocane raspberry cultivar",
    ) == "PATENT"


def test_stale_inka_cache_is_a_review_candidate_and_repairs_deterministically() -> None:
    stale = _stale_inka()
    candidate = audit_development(stale)
    assert candidate is not None
    assert RULE_NATIONALITY_VS_PLACE in {flag["rule"] for flag in candidate["flags"]}
    assert candidate["repair_eligible"] is True
    assert apply_deterministic_repair(stale) is True
    assert stale.geography_ids == ("geography-peru",)
    assert "geography-spain" not in stale.geography_ids
    assert stale.event_type == "PRODUCTION_EXPANSION"
    assert geography_scope_match(stale.geography_ids, EUROPE) is False


def test_berry_catalog_widening_is_manual_review_not_auto_repair() -> None:
    row = cluster_hits(
        [
            _hit(
                title="Driscoll's Zara named best overall supermarket strawberry",
                url="https://example.com/zara",
                snippet="Retail tasting of the Zara strawberry programme.",
                berry="strawberry",
            )
        ]
    )[0]
    row.berry_ids = ("berry-strawberry", "berry-blueberry")
    row.berry_labels = ("Strawberry", "Blueberry")
    candidate = audit_development(row)
    assert candidate is not None
    berry_flags = [flag for flag in candidate["flags"] if flag["field"] == "berry"]
    assert berry_flags
    assert berry_flags[0]["rule"] == RULE_BERRY_NOT_IN_TEXT
    assert berry_flags[0]["repair_eligible"] is False
    apply_deterministic_repair(row)
    assert "berry-blueberry" in row.berry_ids


def test_research_desk_rehydrates_inka_so_europe_scope_is_clean(tmp_path: Path) -> None:
    stale = _stale_inka()
    stale.id = "dev-d92892285194"
    edition = compose_edition(
        [stale],
        generated_at="2026-09-02T12:00:00+00:00",
        window="30d",
        latency_seconds=0.1,
        cache_status="fresh",
        expires_at="2026-09-03T12:00:00+00:00",
        stats={"board": 1, "catalog": 1},
    )
    write_cache(edition, inbox_dir=tmp_path)
    rows = developments_for(inbox_dir=tmp_path, timeframe="90d")
    assert rows
    inka = next(row for row in rows if row["id"] == "dev-d92892285194")
    assert inka["geography_ids"] == ["geography-peru"] or inka["geography_ids"] == ("geography-peru",)
    assert not geography_scope_match(inka["geography_ids"], EUROPE)
    assert inka["berry_ids"]
    audit = audit_radar_cache(inbox_dir=tmp_path, apply_repairs=False)
    assert audit["candidate_count"] >= 1
    assert any(row["id"] == "dev-d92892285194" for row in audit["candidates"])


def test_collection_ops_exposes_tag_quality_without_writing(tmp_path, monkeypatch) -> None:
    from app import main as main_mod

    monkeypatch.setattr(main_mod, "INBOX_DIR", tmp_path)
    client = TestClient(app)
    page = client.get("/collection-ops")
    assert page.status_code == 200
    assert "Radar tag-quality candidates" in page.text
    assert not (tmp_path / "operations" / "radar" / "cache.json").exists()
