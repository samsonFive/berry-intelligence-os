"""Contract checks for the first real recurring spoken-word Sources.

These are Source registrations only. Individual episodes/videos remain
future Evidence records; this module deliberately creates none.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app


ROOT = Path(__file__).resolve().parents[1]
SOURCE_IDS = {
    "source-lucentlands-podcast",
    "source-business-of-blueberries-podcast",
    "source-redagricola-on-the-road",
}


def _sources() -> list[dict]:
    return json.loads((ROOT / "data" / "configuration" / "sources.json").read_text(encoding="utf-8"))


def test_spoken_word_sources_follow_existing_registry_contract() -> None:
    sources = _sources()
    ids = [source["id"] for source in sources]
    assert len(ids) == len(set(ids))

    records = {source["id"]: source for source in sources if source["id"] in SOURCE_IDS}
    assert set(records) == SOURCE_IDS
    for record in records.values():
        assert record["type"] == "reference"
        assert record["value"].startswith("https://")
        assert record["url"] == record["value"]
        assert record["monitoring_priority"] == "high"
        assert record["update_cadence"] in main.SOURCE_CADENCES
        assert record["entity_types"] and set(record["entity_types"]) <= set(main.SOURCE_ENTITY_TYPES)
        assert record["berry_ids"] and set(record["berry_ids"]) <= set(main.BERRIES)
        assert record["region_coverage"] and set(record["region_coverage"]) <= set(main.SOURCE_REGIONS)
        assert record["enabled"] is True
        assert record["linked_competitor_ids"] == []


def test_source_repository_and_existing_filters_retrieve_new_sources() -> None:
    repository = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).sources
    assert {repository.get(source_id)["id"] for source_id in SOURCE_IDS} == SOURCE_IDS
    assert SOURCE_IDS <= {source["id"] for source in repository.list()}

    blueberry = main.filter_sources(repository.list(), berry="berry-blueberry")
    assert SOURCE_IDS <= {source["id"] for source in blueberry}
    africa = main.filter_sources(repository.list(), region="africa")
    assert "source-lucentlands-podcast" in {source["id"] for source in africa}


def test_sources_are_discoverable_in_existing_source_listing() -> None:
    response = TestClient(app).get("/sources")
    assert response.status_code == 200
    for label in (
        "Lucentlands Podcast",
        "The Business of Blueberries (USHBC / NABC)",
        "Redagrícola / Redagrícola On The Road",
    ):
        assert label in response.text


def test_source_registration_does_not_require_or_invent_evidence() -> None:
    evidence = main.get_repositories(main.DATA_DIR, main.SCHEMAS_DIR).evidence.list()
    assert not any(record.get("source_id") in SOURCE_IDS for record in evidence)


def test_domain_pack_keeps_new_sources_as_manual_reference_templates() -> None:
    pack = json.loads((ROOT / "domain-packs" / "berries" / "collector-templates.json").read_text(encoding="utf-8"))
    templates = {record["id"]: record for record in pack["collector_templates"]}
    assert SOURCE_IDS <= set(templates)
    assert all(templates[source_id]["collector_type"] == "reference_manual" for source_id in SOURCE_IDS)
