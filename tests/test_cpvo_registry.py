"""CPVO public register monitor -- Variety Intelligence Backbone V1.

No live network in pytest: `search` is always a fake/injected callable here,
matching this project's existing patent-monitor test convention. The real
endpoint (https://online.plantvarieties.eu/api/publicSearch/v3/publicSearch)
was proven live, by hand, during the mission -- see
docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md Part 4/5.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.services.cpvo_registry import (
    CPVO_DOES_NOT_PROVE,
    CpvoRegistryError,
    berry_id_for_species,
    build_cpvo_review_draft,
    canonical_filing_id,
    normalize_cpvo_register_row,
    run_cpvo_registry_monitor,
)
from app.services.patent_monitor.entity_link import suggest_entity_links

ROOT = Path(__file__).resolve().parents[1]


def _row(**overrides):
    base = {
        "denomination": "Malaika",
        "specieId": "RUB01",
        "speciesName": "Rubus idaeus L.",
        "grantNumber": 12345,
        "grantingDate": "2020-06-01",
        "applicationStatus": "T",
        "applicants": ["Advanced Berry Breeding B.V."],
        "applicationDate": "2018-03-01",
        "applicationNumber": 20180001,
        "expirationDate": None,
        "titleStatus": "approved",
        "examOfficeCountry": "Netherlands",
        "examOfficeName": "Raad voor Plantenrassen",
        "breedersReference": "malaika",
    }
    base.update(overrides)
    return base


def test_berry_id_for_species_maps_real_cpvo_species_strings() -> None:
    assert berry_id_for_species("Fragaria x ananassa Duchesne ex Rozier") == "berry-strawberry"
    assert berry_id_for_species("Vaccinium corymbosum L.") == "berry-blueberry"
    assert berry_id_for_species("Rubus idaeus L.") == "berry-raspberry"
    assert berry_id_for_species("Gerbera L.") is None
    assert berry_id_for_species(None) is None
    assert berry_id_for_species("") is None


def test_canonical_filing_id_is_deterministic_and_distinguishes_office() -> None:
    a = canonical_filing_id(20180001, "Raad voor Plantenrassen")
    b = canonical_filing_id(20180001, "Raad voor Plantenrassen")
    c = canonical_filing_id(20180001, "Bundessortenamt")
    assert a == b
    assert a != c


def test_normalize_row_never_confuses_denomination_with_species() -> None:
    filing = normalize_cpvo_register_row(_row())
    assert filing["denomination"] == "Malaika"
    assert filing["cultivar_name"] == "Malaika"
    assert filing["species_name"] == "Rubus idaeus L."
    assert filing["applicants"] == ["Advanced Berry Breeding B.V."]
    assert filing["jurisdiction"] == "EU (CPVO)"
    assert filing["source_url"].startswith("https://online.plantvarieties.eu/publicSearch?")


def test_build_review_draft_never_auto_trusts_and_states_what_it_does_not_prove() -> None:
    filing = normalize_cpvo_register_row(_row())
    entities = [
        {
            "id": "company-advanced-berry-breeding",
            "record_type": "entity",
            "entity_type": "company",
            "name": "Advanced Berry Breeding B.V.",
            "aliases": [],
            "status": "active",
        },
        {
            "id": "variety-malaika",
            "record_type": "entity",
            "entity_type": "variety",
            "name": "Malaika",
            "aliases": [],
            "berry_ids": ["berry-raspberry"],
            "status": "active",
        },
    ]
    filing_for_matching = {
        "applicants": filing["applicants"],
        "cultivar_name": filing["cultivar_name"],
        "publication_number": filing["application_number"],
    }
    suggestions = suggest_entity_links(filing_for_matching, entities)
    draft = build_cpvo_review_draft(filing, berry_id="berry-raspberry", suggestions=suggestions, captured_date="2026-08-21")

    assert draft["status"] == "draft"
    assert draft["review_state"] == "in_review"
    assert draft["verification_state"] == "unverified"
    assert draft["validated"] is False
    assert draft["auto_captured"] is False
    assert draft["does_not_prove"] == list(CPVO_DOES_NOT_PROVE)
    assert "company-advanced-berry-breeding" in draft["entity_ids"]
    assert "variety-malaika" in draft["entity_ids"]
    assert draft["berry_ids"] == ["berry-raspberry"]
    assert draft["source_type"] == "plant_breeders_rights_record"
    assert draft["intake_type"] == "pvr_filing"

    schema = json.loads((ROOT / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(draft))
    assert not errors, [e.message for e in errors]


def test_run_monitor_is_idempotent_and_species_filters_cross_genus_noise(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    (data_dir / "entities" / "varieties").mkdir(parents=True)
    (data_dir / "entities" / "companies").mkdir(parents=True)
    (data_dir / "entities" / "varieties" / "variety-malaika.json").write_text(
        json.dumps(
            {
                "id": "variety-malaika",
                "record_type": "entity",
                "entity_type": "variety",
                "name": "Malaika",
                "aliases": [],
                "berry_ids": ["berry-raspberry"],
                "status": "active",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "entities" / "companies" / "company-abb.json").write_text(
        json.dumps(
            {
                "id": "company-advanced-berry-breeding",
                "record_type": "entity",
                "entity_type": "company",
                "name": "Advanced Berry Breeding B.V.",
                "aliases": [],
                "status": "active",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    calls: list[str] = []

    def fake_search(denomination: str, **kwargs):
        calls.append(denomination)
        if denomination == "Malaika":
            # A real-shaped response mix: the true raspberry hit plus a
            # same-denomination different-genus row (a real observed CPVO
            # behavior -- see docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md Part
            # 13, "Sonata" collides across Cynara/Fragaria/Hordeum). Species
            # filtering must keep only the raspberry row.
            return [_row(), _row(specieId="AMAR1", speciesName="Amaranthus L.", applicationNumber=99999999)]
        return []

    first = run_cpvo_registry_monitor(data_dir=data_dir, inbox_dir=inbox, search=fake_search)
    assert first["berry_relevant_filings"] == 1
    assert first["review_ready"] == 1
    assert len(first["created"]) == 1
    draft_path = inbox / "evidence" / first["created"][0]
    draft_path = draft_path.with_suffix(".json") if not str(draft_path).endswith(".json") else draft_path
    written = list((inbox / "evidence").glob("ev-cpvo-*.json"))
    assert len(written) == 1
    draft = json.loads(written[0].read_text(encoding="utf-8"))
    assert draft["berry_ids"] == ["berry-raspberry"]

    second = run_cpvo_registry_monitor(data_dir=data_dir, inbox_dir=inbox, search=fake_search)
    assert second["duplicates"] == 1
    assert second["created"] == []
    assert len(list((inbox / "evidence").glob("ev-cpvo-*.json"))) == 1


def test_search_error_is_isolated_per_query(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    inbox = tmp_path / "inbox"
    (data_dir / "entities" / "varieties").mkdir(parents=True)
    (data_dir / "entities" / "varieties" / "variety-a.json").write_text(
        json.dumps({"id": "variety-a", "record_type": "entity", "entity_type": "variety", "name": "AAAA", "status": "active"}) + "\n",
        encoding="utf-8",
    )
    (data_dir / "entities" / "varieties" / "variety-b.json").write_text(
        json.dumps({"id": "variety-b", "record_type": "entity", "entity_type": "variety", "name": "BBBB", "status": "active"}) + "\n",
        encoding="utf-8",
    )

    def flaky_search(denomination: str, **kwargs):
        if denomination == "AAAA":
            raise ValueError("unexpected adapter failure")
        return []

    result = run_cpvo_registry_monitor(data_dir=data_dir, inbox_dir=inbox, search=flaky_search)
    assert len(result["failed"]) == 1
    assert result["queried"] == 2
