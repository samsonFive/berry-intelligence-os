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
