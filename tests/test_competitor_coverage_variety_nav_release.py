"""Release contract for the 77-line competitor registry and Variety Database nav."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.feed_first import filters_query
from app.services.seed_roster import build_roster, filter_roster, profile_url

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
MATRIX_PATH = DATA / "imports" / "competitor-coverage-registry-2026-09-21" / "reconciliation-matrix.json"

EXPECTED_INPUTS = [
    "ABZ Seeds", "Advanced Berry Breeding", "AgroBerries / BerryWorld", "Angus Soft Fruits",
    "Australasian Plant Genetics", "Australian Strawberry Distributors", "Bayer",
    "Benning Blueberries", "Berries del Oeste", "Berryplant / Fall Creek", "Berryum", "Biogea",
    "Black Venture Farm", "California Berry Cultivars", "California Giant", "Camposol", "CIV",
    "Cornell University", "Costa", "Cuna de Platero", "EU Plants Ltd.", "Expoberries",
    "Fall Creek", "Family Tree Farms", "Flevo Berry", "FNM", "Fresh Forward", "Fresh Kampo",
    "Fruitist", "G Berries", "Gem-Pack Berries", "Genetics Uruguay", "Grupo HerEs", "Hansa Bred",
    "Hortifrut", "Hortifrut Genetica", "Inkas Berries",
    "Institute of Botany, Chinese Academy of Sciences", "IQ Berries", "James Hutton Institute",
    "Limgroup", "Mario Aguas-Alvarado", "Marionnet", "Masia Ciscar", "Mattivi", "Miyoshi Group",
    "Mountain Blue Orchards / The Berry Collective", "NC State University", "NIAB EMR", "NIWA",
    "Novisiri Genetics", "Oishii", "Oregon Blueberry", "Ozblu", "Pairwise", "Perfection Fresh",
    "Planasa", "Plant Sciences", "Queensland Government", "Rijk Zwaan", "Royakkers",
    "Royal Berries", "Sant Orsola", "Singrow", "Smart Berries", "Splendor Produce", "SunBelle",
    "Surexport", "The Berry Collective", "UC Davis", "University of Arkansas",
    "University of Florida", "University of Georgia", "USDA", "Vissers", "Well-Pict", "Wish Farms",
]

ACCEPTED = {
    "EXISTING_EXACT", "EXISTING_ALIAS", "EXISTING_RELATIONSHIP", "CONFIRMED_DUPLICATE",
    "ADDED_CANONICAL_ENTITY", "EXCLUDED_WITH_REASON",
}


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _entities() -> list[dict]:
    rows = []
    for folder in (DATA / "entities").iterdir():
        if folder.is_dir():
            rows.extend(json.loads(path.read_text(encoding="utf-8")) for path in folder.glob("*.json"))
    return rows


def test_matrix_accounts_for_all_77_registry_lines_once() -> None:
    matrix = _matrix()
    rows = matrix["rows"]
    assert matrix["row_count"] == len(rows) == len(EXPECTED_INPUTS) == 77
    assert [row["input_registry_name"] for row in rows] == EXPECTED_INPUTS
    assert len({row["input_registry_name"] for row in rows}) == 77
    assert {row["resolution_status"] for row in rows} <= ACCEPTED


def test_reader_close_query_removes_selected_item_without_losing_sort() -> None:
    query = filters_query({"item": "ev-example", "sort": "rank"}, item="")
    assert "item=" not in query
    assert query == "sort=rank"


def test_every_represented_row_resolves_and_every_exclusion_is_specific() -> None:
    entity_ids = {entity["id"] for entity in _entities()}
    for row in _matrix()["rows"]:
        if row["resolution_status"] == "EXCLUDED_WITH_REASON":
            assert row["canonical_entity_ids"] == []
            assert len(row["notes"]) >= 40
            continue
        assert row["canonical_entity_ids"], row["input_registry_name"]
        assert set(row["canonical_entity_ids"]) <= entity_ids, row["input_registry_name"]
        assert row["canonical_entity_id"] in row["canonical_entity_ids"]
        assert row["canonical_entity_name"]
        assert row["action_taken"]


def test_slash_names_resolve_to_distinct_relationship_outcomes() -> None:
    rows = {row["input_registry_name"]: row for row in _matrix()["rows"]}
    assert rows["AgroBerries / BerryWorld"]["canonical_entity_ids"] == [
        "company-agroberries", "company-berryworld",
    ]
    assert "acquired" in rows["AgroBerries / BerryWorld"]["existing_alias_or_relationship"]
    assert rows["Berryplant / Fall Creek"]["canonical_entity_ids"] == [
        "company-fall-creek-italia", "company-fall-creek-farm-and-nursery",
    ]
    assert "Italian operation" in rows["Berryplant / Fall Creek"]["existing_alias_or_relationship"]
    assert rows["Mountain Blue Orchards / The Berry Collective"]["canonical_entity_ids"] == [
        "company-mountain-blue-orchards", "company-the-berry-collective",
    ]
    assert "50%" in rows["Mountain Blue Orchards / The Berry Collective"]["existing_alias_or_relationship"]


def test_known_aliases_and_corrected_duplicate_resolve_without_duplicate_cards() -> None:
    roster = build_roster(_entities())
    assert len(roster) == len({row["id"] for row in roster})
    checks = {
        "Benning Blueberries": "company-denning-blueberries",
        "Denning Blueberries": "company-denning-blueberries",
        "Novisiri Genetics": "company-nova-siri-genetics",
        "Hortifrut Genetica": "company-hortifrut",
        "Berryplant": "company-fall-creek-italia",
        "FNM": "company-fresas-nuevos-materiales",
    }
    for query, expected_id in checks.items():
        hits = filter_roster(roster, q=query, include_registries=True)
        assert [row["id"] for row in hits] == [expected_id], query


def test_every_new_entity_is_searchable_and_has_stable_detail_route() -> None:
    matrix = _matrix()
    roster = build_roster(_entities())
    added_ids = {
        entity_id
        for row in matrix["rows"]
        if row["resolution_status"] == "ADDED_CANONICAL_ENTITY"
        for entity_id in row["canonical_entity_ids"]
    }
    by_id = {row["id"]: row for row in roster}
    assert added_ids <= by_id.keys()
    for entity_id in added_ids:
        row = by_id[entity_id]
        hits = filter_roster(roster, q=row["canonical_name"], include_registries=True)
        assert any(hit["id"] == entity_id for hit in hits), entity_id
        assert profile_url(row).startswith("/entities/")


def test_every_represented_registry_identity_is_in_the_entities_projection() -> None:
    roster = build_roster(_entities())
    roster_ids = {row["id"] for row in roster}
    represented_ids = {
        entity_id
        for row in _matrix()["rows"]
        if row["resolution_status"] != "EXCLUDED_WITH_REASON"
        for entity_id in row["canonical_entity_ids"]
    }
    assert represented_ids <= roster_ids


def test_entities_projection_and_representative_detail_routes_load() -> None:
    client = TestClient(app)
    listing = client.get("/entities", params={"q": "ABZ Seeds"})
    assert listing.status_code == 200
    assert 'data-entity-id="company-abz-seeds"' in listing.text
    for route in (
        "/entities/company/company-abz-seeds?view=feed",
        "/entities/company/company-denning-blueberries?view=feed",
        "/entities/brand/brand-berryum?view=feed",
        "/entities/company/company-planasa",
    ):
        response = client.get(route)
        assert response.status_code == 200, route


def test_variety_database_nav_is_shared_exact_and_active() -> None:
    client = TestClient(app)
    for route in ("/today", "/entities", "/entities/company/company-planasa", "/learn"):
        response = client.get(route)
        assert response.status_code == 200, route
        assert 'href="/entities/variety"' in response.text
        assert "Variety Database" in response.text
    variety = client.get("/entities/variety")
    assert variety.status_code == 200
    assert "Variety Database" in variety.text
    assert 'aria-current="page"' in variety.text


def test_nav_sources_use_one_existing_destination() -> None:
    feed_nav = (REPO / "app" / "services" / "feed_first.py").read_text(encoding="utf-8")
    v2_nav = (REPO / "app" / "templates" / "_v2_sidebar.html").read_text(encoding="utf-8")
    stakeholder_nav = (REPO / "app" / "templates" / "_stakeholder_nav.html").read_text(encoding="utf-8")
    for source in (feed_nav, v2_nav, stakeholder_nav):
        assert "Variety Database" in source
        assert "/entities/variety" in source
    assert "/variety-database" not in "\n".join((feed_nav, v2_nav, stakeholder_nav))
