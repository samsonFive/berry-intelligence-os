"""Focused acceptance tests for the canonical competitor integration."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition import get_repositories
from app.main import app
from app.repositories.paths import SCHEMAS_DIR
from app.services.competitor_landscape import (
    CompetitorLandscapeAdapter,
    adapter_from_repositories,
    build_landscape_context,
    filter_rows,
    parse_filters,
)
from app.services.competitor_registry import monitoring_maturity_for_entity


ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def canonical_adapter(*, inbox_dir: Path | None = None) -> CompetitorLandscapeAdapter:
    repos = get_repositories(ROOT / "data", SCHEMAS_DIR)
    evidence = [row for row in repos.evidence.list() if row.get("status") == "published"]
    return adapter_from_repositories(
        data_dir=ROOT / "data",
        inbox_dir=inbox_dir or ROOT / "inbox",
        entities=repos.entities.list(),
        sources=repos.sources.list(),
        evidence=evidence,
        relationships=repos.relationships.list(),
    )


def test_production_adapter_requires_canonical_rows_or_explicit_test_fixture() -> None:
    with pytest.raises(ValueError, match="canonical_rows"):
        CompetitorLandscapeAdapter()


def test_canonical_roster_accounts_for_all_33_without_fake_companies() -> None:
    rows = canonical_adapter().load_rows()
    assert len(rows) == 33
    assert len({row["entity_id"] for row in rows}) == 33
    assert all(row["canonical_or_pending_state"] == "canonical" for row in rows)
    assert all(not row["entity_id"].startswith("pending-competitor-") for row in rows)
    assert {row["registry_label"] for row in rows} == set(
        canonical_adapter().roster_labels()
    )


def test_non_company_entities_keep_their_canonical_types_and_routes() -> None:
    rows = canonical_adapter().load_rows()
    ozblu = next(row for row in rows if row["registry_label"] == "Ozblu")
    uc_davis = next(row for row in rows if row["registry_label"] == "UC Davis")
    assert (ozblu["entity_id"], ozblu["entity_type"], ozblu["profile_url"]) == (
        "brand-ozblu", "brand", "/entities/brand/brand-ozblu"
    )
    assert (uc_davis["entity_id"], uc_davis["entity_type"], uc_davis["profile_url"]) == (
        "breeding_program-uc-davis-strawberry",
        "breeding_program",
        "/entities/breeding_program/breeding_program-uc-davis-strawberry",
    )


def test_alias_search_resolves_to_one_canonical_row() -> None:
    rows = canonical_adapter().load_rows()
    assert {row["registry_label"] for row in filter_rows(rows, parse_filters({"q": "MBO"}))} == {
        "Mountain Blue"
    }
    assert {row["registry_label"] for row in filter_rows(rows, parse_filters({"q": "Fruitist"}))} == {
        "Fruitist"
    }


def test_california_giant_exposes_simultaneous_honest_states() -> None:
    row = next(
        row for row in canonical_adapter().load_rows()
        if row["registry_label"] == "California Giant"
    )
    state = row["monitoring_maturity"]
    assert state["entity_represented"] is True
    assert state["official_source_blocked"] is True
    assert state["linked_source_count"] == 0
    assert state["discovery_configured"] is False
    assert state["discovery_operational"] is False
    assert state["readable_content_acquired"] is False
    assert state["current_coverage_available"] is False
    assert state["manual_or_alternative_source_required"] is True
    assert row["genetics_relationships"][0]["status"] == "disputed"


def test_runtime_discovery_and_readable_acquisition_are_separate_facets(tmp_path: Path) -> None:
    source_id = "source-integration-example"
    state_dir = tmp_path / "discovered_media" / "_state"
    state_dir.mkdir(parents=True)
    (state_dir / f"{source_id}.json").write_text(
        '{"status":"success","last_checked_at":"2026-09-15T01:00:00Z",'
        '"last_success_at":"2026-09-15T01:00:00Z"}', encoding="utf-8"
    )
    outcome_dir = tmp_path / "operations" / "article_acquisition_outcomes" / source_id / "item-1"
    outcome_dir.mkdir(parents=True)
    (outcome_dir / "attempt.json").write_text(
        '{"outcome_category":"readable_article_body",'
        '"attempted_at":"2026-09-15T01:01:00Z",'
        '"recorded_at":"2026-09-15T01:01:00Z",'
        '"article_published_date":"2026-09-14"}', encoding="utf-8"
    )
    entity = {"id": "company-example", "name": "Example", "entity_type": "company"}
    source = {
        "id": source_id,
        "enabled": True,
        "lifecycle_state": "active",
        "linked_competitor_ids": [entity["id"]],
        "discovery": {"adapter": "article_rss", "feed_url": "https://example.test/feed"},
    }
    maturity = monitoring_maturity_for_entity(
        entity, sources=[source], published=[], inbox_dir=tmp_path, today=date(2026, 9, 15)
    )
    assert maturity["discovery_configured"] is True
    assert maturity["discovery_operational"] is True
    assert maturity["readable_content_acquired"] is True
    assert maturity["current_coverage_available"] is False
    assert maturity["maturity_level"] == 4


def test_route_uses_canonical_registry_and_labels_pending_relationships() -> None:
    response = client.get(
        "/competitors",
        params={"company": "company-california-giant-berry-farms"},
    )
    assert response.status_code == 200
    assert "Showing the canonical 33-entry internal roster" in response.text
    assert "Official source blocked" in response.text
    assert "No explicitly linked runnable source" in response.text
    assert "No usable published coverage in the last 90 days" in response.text
    assert "Pending review" in response.text
    assert "complete 33-entry competitor-universe fixture" not in response.text


def test_default_context_accounts_for_every_canonical_row() -> None:
    context = build_landscape_context(canonical_adapter(), parse_filters({}))
    assert context["universe_count"] == 33
    assert context["result_count"] == 33
    assert context["completeness"]["represented"] == 33
    assert context["missing_expected_labels"] == []
