"""app/services/entity_alias_recall.py -- non-mutating alias-based evidence
recall for entities added after some of their evidence was already
published.

Real gap: SanLucar and USHBC were added as tracked company entities after
older evidence genuinely mentioning them by name had already been human-
reviewed and published, so that evidence's entity_ids was never backfilled
to include them -- and never will be by the existing pipeline, since
app/main.py's auto_tag_geography_and_entities() deliberately skips any
record with validated=True to keep already-reviewed trusted records
immutable. These tests prove the recall path finds those older mentions
without ever writing to or mutating the original evidence records.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from app.services.entity_alias_recall import alias_linked_evidence, linked_evidence_for_entity

REPO_ROOT = Path(__file__).resolve().parents[1]


def _entity(entity_id: str, name: str, aliases: list[str]) -> dict:
    return {"id": entity_id, "entity_type": "company", "name": name, "aliases": aliases}


def _evidence(evidence_id: str, title: str, entity_ids: list[str] | None = None) -> dict:
    return {"id": evidence_id, "title": title, "entity_ids": entity_ids or [], "published_date": "2026-07-01"}


def _variety(entity_id: str, name: str, aliases: list[str], berry: str = "berry-blackberry") -> dict:
    return {
        "id": entity_id,
        "entity_type": "variety",
        "name": name,
        "aliases": aliases,
        "berry_ids": [berry],
    }


def test_finds_a_name_mention_missing_from_entity_ids() -> None:
    entity = _entity("company-sanlucar", "SanLucar", ["SanLucar"])
    records = [_evidence("ev-1", "SanLucar acquires stake in Twin River Berries")]

    matches = alias_linked_evidence(entity, records, already_linked_ids=set())

    assert len(matches) == 1
    assert matches[0]["id"] == "ev-1"
    assert matches[0]["link_mechanism"] == "alias_recall"


def test_never_mutates_the_original_record() -> None:
    entity = _entity("company-sanlucar", "SanLucar", ["SanLucar"])
    original = _evidence("ev-1", "SanLucar acquires stake in Twin River Berries")
    snapshot = copy.deepcopy(original)
    records = [original]

    matches = alias_linked_evidence(entity, records, already_linked_ids=set())

    assert original == snapshot, "the source record must never be modified in place"
    assert "link_mechanism" not in original
    assert matches[0] is not original


def test_excludes_records_already_linked_via_entity_ids() -> None:
    entity = _entity("company-sanlucar", "SanLucar", ["SanLucar"])
    records = [_evidence("ev-1", "SanLucar news", entity_ids=["company-sanlucar"])]

    matches = alias_linked_evidence(entity, records, already_linked_ids={"ev-1"})

    assert matches == []


def test_skips_entities_with_no_alias_long_enough_to_match_safely() -> None:
    # A bare short acronym would produce false positives against unrelated
    # text -- entities must supply a real alias/name, not rely on a
    # substring match against something like "US" or "Co".
    entity = {"id": "company-x", "entity_type": "company", "name": "X", "aliases": []}
    records = [_evidence("ev-1", "Some article that says X a lot")]

    matches = alias_linked_evidence(entity, records, already_linked_ids=set())

    assert matches == []


def test_does_not_match_unrelated_evidence() -> None:
    entity = _entity("company-sanlucar", "SanLucar", ["SanLucar"])
    records = [_evidence("ev-1", "Driscoll's announces new variety")]

    matches = alias_linked_evidence(entity, records, already_linked_ids=set())

    assert matches == []


def test_linked_evidence_for_entity_merges_direct_and_recalled_with_mechanism_tags() -> None:
    entity = _entity("company-sanlucar", "SanLucar", ["SanLucar"])
    records = [
        _evidence("ev-direct", "SanLucar Q2 results", entity_ids=["company-sanlucar"]),
        _evidence("ev-recalled", "SanLucar acquires stake in Twin River Berries"),
        _evidence("ev-unrelated", "Driscoll's announces new variety"),
    ]

    linked = linked_evidence_for_entity(entity, records)

    by_id = {r["id"]: r for r in linked}
    assert set(by_id) == {"ev-direct", "ev-recalled"}
    assert by_id["ev-direct"]["link_mechanism"] == "entity_id"
    assert by_id["ev-recalled"]["link_mechanism"] == "alias_recall"


def test_real_canonical_data_recalls_sanlucar_and_ushbc_older_evidence_without_mutation() -> None:
    """Prove against the real canonical data/ tree (not a fixture) that
    SanLucar and USHBC -- the two companies confirmed during Phase B
    coverage review to have older published evidence with real name
    mentions but empty entity_ids -- actually get recalled, and that the
    on-disk evidence files are untouched by the process."""
    entities_dir = REPO_ROOT / "data" / "entities" / "companies"
    evidence_dir = REPO_ROOT / "data" / "evidence"
    assert entities_dir.is_dir() and evidence_dir.is_dir()

    published = []
    raw_bytes_before = {}
    for f in evidence_dir.glob("*.json"):
        raw_bytes_before[f] = f.read_bytes()
        record = json.loads(raw_bytes_before[f])
        if record.get("status") == "published":
            published.append(record)

    for company_id in ("company-sanlucar", "company-ushbc"):
        entity_file = entities_dir / f"{company_id}.json"
        entity = json.loads(entity_file.read_text(encoding="utf-8"))
        assert entity["id"] == company_id

        direct = [r for r in published if company_id in (r.get("entity_ids") or [])]
        linked = linked_evidence_for_entity(entity, published)
        recalled = [r for r in linked if r["link_mechanism"] == "alias_recall"]

        assert len(linked) >= len(direct), f"{company_id}: recall must never return fewer than the direct link count"
        assert recalled, f"{company_id}: expected at least one alias-recalled older record in real canonical data"

    for f, before in raw_bytes_before.items():
        assert f.read_bytes() == before, f"{f} was modified on disk -- recall must never write to trusted evidence"


def test_victoria_geography_collision_is_rejected_against_real_canonical_records() -> None:
    entities = {}
    for path in (REPO_ROOT / "data" / "entities").glob("*/*.json"):
        entity = json.loads(path.read_text(encoding="utf-8"))
        entities[entity["id"]] = entity
    evidence_dir = REPO_ROOT / "data" / "evidence"
    victoria = entities["variety-victoria"]
    costa = json.loads((evidence_dir / "ev-costa-ownership-2024.json").read_text(encoding="utf-8"))
    legitimate = json.loads(
        (evidence_dir / "ev-hortweek-driscolls-victoria-award.json").read_text(encoding="utf-8")
    )

    linked = linked_evidence_for_entity(victoria, [costa, legitimate], entities=entities)

    assert [record["id"] for record in linked] == ["ev-hortweek-driscolls-victoria-award"]
    assert linked[0]["link_mechanism"] == "entity_id"


def test_explicit_id_survives_even_when_text_looks_geographic_or_has_no_context() -> None:
    victoria = _variety("variety-victoria", "Victoria", ["Driscoll's Victoria"])
    record = {
        **_evidence("ev-explicit", "Operations in Victoria state", ["variety-victoria"]),
        "summary": "Geelong, Victoria market update.",
        "berry_ids": ["berry-blueberry"],
    }

    linked = linked_evidence_for_entity(victoria, [record])

    assert [row["id"] for row in linked] == ["ev-explicit"]
    assert linked[0]["link_mechanism"] == "entity_id"


def test_legitimate_contextual_variety_alias_survives_case_and_punctuation() -> None:
    variety = _variety("variety-victoria", "Victoria", ["Driscoll's Victoria"])
    record = {
        **_evidence("ev-context", "DRISCOLL’S VICTORIA wins best new variety"),
        "summary": "The blackberry cultivar is grown commercially.",
        "berry_ids": ["berry-blackberry"],
    }

    linked = linked_evidence_for_entity(variety, [record])

    assert [row["id"] for row in linked] == ["ev-context"]
    assert linked[0]["link_matched_alias"] == "Driscoll's Victoria"
    assert linked[0]["link_matched_field"] == "title"


def test_ordinary_word_and_substring_variety_aliases_do_not_overmatch() -> None:
    cargo = _variety("variety-cargo", "Cargo", [], "berry-blueberry")
    dina = _variety("variety-dina", "Dina", [], "berry-blueberry")
    records = [
        {**_evidence("ev-cargo", "Peru expands air cargo capacity"), "berry_ids": ["berry-blueberry"]},
        {**_evidence("ev-andina", "Agencia Andina reports blueberry exports"), "berry_ids": ["berry-blueberry"]},
    ]

    assert linked_evidence_for_entity(cargo, records) == []
    assert linked_evidence_for_entity(dina, records) == []


def test_longer_variety_name_does_not_ground_shorter_variety() -> None:
    eureka = _variety("variety-eureka", "Eureka", [], "berry-blueberry")
    sunrise = _variety("variety-eureka-sunrise", "Eureka Sunrise", [], "berry-blueberry")
    entities = {row["id"]: row for row in (eureka, sunrise)}
    record = {
        **_evidence("ev-sunrise", "Taste award for Eureka Sunrise blueberry variety"),
        "berry_ids": ["berry-blueberry"],
    }

    assert linked_evidence_for_entity(eureka, [record], entities=entities) == []
    assert [r["id"] for r in linked_evidence_for_entity(sunrise, [record], entities=entities)] == ["ev-sunrise"]


def test_exact_title_reference_is_a_strong_variety_identity_match() -> None:
    variety = _variety("variety-ponca", "Ponca", [])
    record = _evidence("ev-ponca", "ponca")

    linked = linked_evidence_for_entity(variety, [record])

    assert linked[0]["link_match_type"] == "exact_strong_identity"


def test_exact_title_does_not_override_structured_geography_context() -> None:
    victoria = _variety("variety-victoria", "Victoria", [])
    record = {
        **_evidence("ev-victoria-place", "Victoria"),
        "geography_ids": ["geography-australia"],
    }

    assert linked_evidence_for_entity(victoria, [record]) == []


def test_company_matching_keeps_bounded_legal_and_alias_recall() -> None:
    company = _entity("company-planasa", "Plantas de Navarra, S.A.", ["Planasa"])
    records = [
        _evidence("ev-title", "PLANASA expands its breeding portfolio"),
        {**_evidence("ev-summary", "Market update"), "summary": "The breeder Planasa launched two cultivars."},
    ]

    linked = linked_evidence_for_entity(company, records)

    assert [row["id"] for row in linked] == ["ev-title", "ev-summary"]


def test_company_alias_uses_boundaries_and_does_not_match_common_word_or_substring() -> None:
    berry_blue = _entity("company-berry-blue-llc", "Berry Blue, LLC", ["Berry Blue"])
    chambers = _entity("company-chambers", "Chambers", [])
    records = [
        _evidence("ev-blue", "Planasa - Blueberry Blue Maldiva"),
        {**_evidence("ev-chambers", "Technology update"), "summary": "Low-atmosphere vacuum chambers improve storage."},
    ]

    assert linked_evidence_for_entity(berry_blue, records) == []
    assert linked_evidence_for_entity(chambers, records) == []


def test_matching_is_deterministic_and_does_not_mutate_inputs() -> None:
    variety = _variety("variety-arana", "Arana", [], "berry-blueberry")
    record = {
        **_evidence("ev-arana", "Arana is the best blueberry cultivar"),
        "berry_ids": ["berry-blueberry"],
    }
    entity_snapshot = copy.deepcopy(variety)
    record_snapshot = copy.deepcopy(record)

    first = linked_evidence_for_entity(variety, [record])
    second = linked_evidence_for_entity(variety, [record])

    assert first == second
    assert variety == entity_snapshot
    assert record == record_snapshot
