"""Competitor Landscape V1 — focused adapter, filter, and route tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.main import app
from app.services.competitor_landscape import (
    EXPECTED_REGISTRY_LABELS,
    CompetitorLandscapeAdapter,
    adapter_from_repositories,
    berry_status_for,
    build_landscape_context,
    filter_rows,
    filters_to_query,
    normalize_tier_status,
    parse_filters,
)

client = TestClient(app)


def test_fixture_universe_contains_exactly_33_registry_entries() -> None:
    adapter = CompetitorLandscapeAdapter()
    labels = adapter.roster_labels()
    assert len(labels) == 33
    assert len(set(labels)) == 33
    assert adapter.missing_expected_labels() == []
    assert adapter.unexpected_labels() == []
    assert set(labels) == set(EXPECTED_REGISTRY_LABELS)


def test_every_expected_spreadsheet_label_resolves() -> None:
    rows = CompetitorLandscapeAdapter().load_rows()
    by_label = {row["registry_label"]: row for row in rows}
    for label in EXPECTED_REGISTRY_LABELS:
        assert label in by_label
        assert by_label[label]["display_name"] == label


def test_default_view_returns_all_33() -> None:
    adapter = CompetitorLandscapeAdapter()
    context = build_landscape_context(adapter, parse_filters({}))
    assert context["universe_count"] == 33
    assert context["result_count"] == 33
    assert sum(band["count"] for band in context["bands"]) == 33


def test_blank_tier_fields_remain_visible_as_unknown() -> None:
    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    agro = next(row for row in rows if row["registry_label"] == "AgroBerries")
    assert berry_status_for(agro, "blueberry") == "Unknown/Unassigned"
    assert berry_status_for(agro, "strawberry") == "Unknown/Unassigned"
    # Still present in default landscape
    context = build_landscape_context(adapter, parse_filters({"berry": ["blueberry"]}))
    names = {
        company["display_name"]
        for band in context["bands"]
        for company in band["competitors"]
    }
    assert "AgroBerries" in names
    assert "Splendor Produce" in names
    assert context["tier_counts"]["Unknown/Unassigned"] >= 1


def test_berry_filters_evaluate_only_selected_berry() -> None:
    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    # Fall Creek is Blueberry Tier 1, Raspberry Tier 3 — not Strawberry Tier 1
    fall = next(row for row in rows if row["registry_label"] == "Fall Creek")
    assert berry_status_for(fall, "blueberry") == "Tier 1"
    assert berry_status_for(fall, "raspberry") == "Tier 3"
    assert berry_status_for(fall, "strawberry") == "Unknown/Unassigned"

    blue_tier1 = filter_rows(rows, parse_filters({"berry": ["blueberry"], "tier": ["Tier 1"]}))
    blue_names = {row["registry_label"] for row in blue_tier1}
    assert "Fall Creek" in blue_names
    assert "Fresh Forward" not in blue_names  # strawberry Tier 1 only

    straw_tier1 = filter_rows(rows, parse_filters({"berry": ["strawberry"], "tier": ["Tier 1"]}))
    straw_names = {row["registry_label"] for row in straw_tier1}
    assert "Fresh Forward" in straw_names
    assert "Fall Creek" not in straw_names


def test_present_and_tier_3_remain_distinct() -> None:
    assert normalize_tier_status("Present") == "Present"
    assert normalize_tier_status("Tier 3") == "Tier 3"
    assert normalize_tier_status("Present") != normalize_tier_status("Tier 3")

    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    expo = next(row for row in rows if row["registry_label"] == "Expoberries")
    assert berry_status_for(expo, "blueberry") == "Present"
    assert berry_status_for(expo, "blackberry") == "Tier 1"

    present_only = filter_rows(
        rows, parse_filters({"berry": ["blueberry"], "tier": ["Present"]})
    )
    present_names = {row["registry_label"] for row in present_only}
    assert "Expoberries" in present_names
    # IQ Berries blueberry is Tier 3, not Present
    assert "IQ Berries" not in present_names


def test_multi_region_filtering_works() -> None:
    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    demea = filter_rows(rows, parse_filters({"region": ["DEMEA"]}))
    names = {row["registry_label"] for row in demea}
    assert "Advanced Berry Breeding" in names
    assert "Planasa" in names
    # DOTA-only California Giant excluded
    assert "California Giant" not in names

    multi = filter_rows(rows, parse_filters({"region": ["DOTA", "DOA_DANZ"]}))
    multi_names = {row["registry_label"] for row in multi}
    assert "California Giant" in multi_names
    assert "Perfection Fresh" in multi_names
    assert "Advanced Berry Breeding" not in multi_names


def test_multi_type_filtering_works() -> None:
    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    breeding = filter_rows(rows, parse_filters({"type": ["Breeding"]}))
    names = {row["registry_label"] for row in breeding}
    assert "Fall Creek" in names  # Breeding; Genetics
    assert "Planasa" in names
    assert "AgroBerries" not in names

    tech = filter_rows(rows, parse_filters({"type": ["Technology"]}))
    tech_names = {row["registry_label"] for row in tech}
    assert "Pairwise" in tech_names
    assert "Australasian Plant Genetics" in tech_names


def test_combined_filters_work() -> None:
    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    matched = filter_rows(
        rows,
        parse_filters(
            {
                "berry": ["blueberry"],
                "region": ["DEMEA"],
                "tier": ["Tier 1"],
                "type": ["Breeding"],
            }
        ),
    )
    names = {row["registry_label"] for row in matched}
    assert "Fall Creek" in names
    assert "Hortifrut Genetica" in names
    assert "Mountain Blue" in names
    # Costa is Commercial Tier 1 blueberry DEMEA — wrong type
    assert "Costa" not in names


def test_query_parameters_restore_state() -> None:
    filters = parse_filters(
        {
            "berry": ["raspberry"],
            "region": ["DEMEA", "DOTA"],
            "tier": ["Tier 2"],
            "priority": ["Watch"],
            "type": ["Commercial"],
            "q": ["smart"],
            "company": ["pending-competitor-smart-berries"],
        }
    )
    assert filters.berry == "raspberry"
    assert filters.regions == ("DEMEA", "DOTA")
    assert filters.tier == "Tier 2"
    assert filters.priority == "Watch"
    assert filters.competitor_type == "Commercial"
    assert filters.q == "smart"
    assert filters.company == "pending-competitor-smart-berries"

    query = filters_to_query(filters)
    restored = parse_filters(parse_qs(query))
    assert restored.berry == filters.berry
    assert restored.regions == filters.regions
    assert restored.tier == filters.tier
    assert restored.priority == filters.priority
    assert restored.competitor_type == filters.competitor_type
    assert restored.q == filters.q
    assert restored.company == filters.company


def test_search_finds_canonical_names_and_aliases() -> None:
    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    by_name = filter_rows(rows, parse_filters({"q": ["Fall Creek"]}))
    assert {row["registry_label"] for row in by_name} == {"Fall Creek"}

    by_alias = filter_rows(rows, parse_filters({"q": ["MBO"]}))
    assert {row["registry_label"] for row in by_alias} == {"Mountain Blue"}

    by_alias2 = filter_rows(rows, parse_filters({"q": ["Plantas de Navarra"]}))
    assert {row["registry_label"] for row in by_alias2} == {"Planasa"}


def test_clear_all_restores_full_landscape_via_route() -> None:
    focused = client.get(
        "/competitors",
        params=[("berry", "strawberry"), ("tier", "Tier 1"), ("region", "DEMEA")],
    )
    assert focused.status_code == 200
    assert "of 33 competitors" in focused.text
    # Fresh Forward is strawberry Tier 1 DEMEA
    assert "Fresh Forward" in focused.text

    cleared = client.get("/competitors")
    assert cleared.status_code == 200
    assert "<strong>33</strong> of 33 competitors" in cleared.text
    # Unknown/unassigned commercial still visible
    assert "AgroBerries" in cleared.text
    assert "Splendor Produce" in cleared.text
    assert "University of Florida" in cleared.text


def test_company_drilldown_preserves_filters() -> None:
    response = client.get(
        "/competitors",
        params=[
            ("berry", "blueberry"),
            ("region", "DEMEA"),
            ("tier", "Tier 1"),
            ("company", "company-fall-creek-farm-and-nursery"),
        ],
    )
    assert response.status_code == 200
    assert "COMPETITOR DETAIL" in response.text
    assert "Fall Creek" in response.text
    assert "Return to landscape" in response.text
    # Preserve berry/region/tier on return link
    assert 'href="/competitors?berry=blueberry' in response.text
    assert "region=DEMEA" in response.text
    assert "tier=Tier+1" in response.text or "tier=Tier 1" in response.text
    # Does not invent genetics narrative
    assert "Open company profile" in response.text


def test_pending_incomplete_identities_render_honestly() -> None:
    adapter = CompetitorLandscapeAdapter()
    rows = adapter.load_rows()
    pending = next(row for row in rows if row["registry_label"] == "Pairwise")
    assert pending["canonical_or_pending_state"] == "pending"
    assert pending["entity_id"].startswith("pending-competitor-")
    assert pending["profile_url"] == ""
    assert pending["monitoring_state"] == "identity_pending"

    context = build_landscape_context(
        adapter,
        parse_filters({"company": [pending["entity_id"]]}),
    )
    detail = context["selected_company"]
    assert detail is not None
    assert any("pending" in gap.casefold() for gap in detail["data_gaps"])


def test_route_renders_desktop_structure_and_mobile_friendly_controls() -> None:
    response = client.get("/competitors")
    assert response.status_code == 200
    assert 'id="competitor-landscape"' in response.text
    assert 'id="competitor-landscape-filters"' in response.text
    assert "competitor-landscape-controls" in response.text
    assert 'name="berry"' in response.text
    assert 'name="region"' in response.text
    assert 'name="tier"' in response.text
    assert 'name="priority"' in response.text
    assert 'name="type"' in response.text
    assert 'name="q"' in response.text
    assert "Clear all" in response.text
    # All 33 names appear somewhere in default view
    for label in EXPECTED_REGISTRY_LABELS:
        assert label in response.text


def test_adapter_from_repositories_marks_known_entities_canonical() -> None:
    adapter = adapter_from_repositories(
        entities=[
            {
                "id": "company-fall-creek-farm-and-nursery",
                "name": "Fall Creek Farm & Nursery, Inc.",
                "aliases": ["Fall Creek"],
                "entity_type": "company",
            }
        ],
        evidence=[
            {
                "id": "ev-demo",
                "status": "published",
                "entity_ids": ["company-fall-creek-farm-and-nursery"],
            }
        ],
        relationships=[],
    )
    fall = next(row for row in adapter.load_rows() if row["registry_label"] == "Fall Creek")
    assert fall["canonical_or_pending_state"] == "canonical"
    assert fall["profile_url"] == "/entities/company/company-fall-creek-farm-and-nursery"
    assert fall["recent_usable_coverage_count"] == 1
