"""Dedicated SourceRepository tests (V2 Phase 2B.1,
docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 7).

Sources are the one documented storage exception -- persisted as a single
JSON array in `data/configuration/sources.json`, rewritten in full on
every change, rather than one-file-per-record like every other object
type. These tests exist to prove the *logical* record interface
(`get`/`list`/`create`/`update`/`delete`) works correctly for a caller who
has no reason to know that -- including, explicitly, that an unrelated
source already in the collection survives an update/delete/create of a
different source untouched.

Uses only a temporary copy of source-shaped fixture data
(`tmp_path`) -- never the live 120-source registry
(`data/configuration/sources.json`), per this task's explicit instruction.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.repositories.base import DuplicateRecord, RecordNotFound
from app.repositories.json.sources import JsonSourceRepository


def _source(suffix: str, **overrides) -> dict:
    record = {
        "id": f"source-test-{suffix}",
        "type": "rss",
        "label": f"Test Source {suffix}",
        "value": f"https://example.invalid/feed-{suffix}.xml",
        "url": f"https://example.invalid/{suffix}",
        "why_it_matters": "Because this is a test fixture.",
        "entity_types": [],
        "berry_ids": ["berry-blueberry"],
        "region_coverage": [],
        "monitoring_priority": "medium",
        "update_cadence": "daily",
        "linked_competitor_ids": [],
        "enabled": True,
        "created_at": "2026-08-14",
        "last_checked_at": None,
        "last_status": None,
    }
    record.update(overrides)
    return record


@pytest.fixture
def repo(tmp_path: Path) -> JsonSourceRepository:
    return JsonSourceRepository(data_dir=tmp_path)


# ---------------------------------------------------------------------------
# reading all sources / getting one source
# ---------------------------------------------------------------------------

def test_list_returns_every_source(repo: JsonSourceRepository) -> None:
    repo.create(_source("a"))
    repo.create(_source("b"))
    repo.create(_source("c"))
    assert {s["id"] for s in repo.list()} == {"source-test-a", "source-test-b", "source-test-c"}


def test_get_returns_one_source_by_id(repo: JsonSourceRepository) -> None:
    repo.create(_source("a"))
    repo.create(_source("b"))
    fetched = repo.get("source-test-b")
    assert fetched is not None
    assert fetched["label"] == "Test Source b"


def test_get_missing_source_returns_none(repo: JsonSourceRepository) -> None:
    assert repo.get("does-not-exist") is None


# ---------------------------------------------------------------------------
# adding / updating one source
# ---------------------------------------------------------------------------

def test_create_adds_a_source(repo: JsonSourceRepository) -> None:
    repo.create(_source("a"))
    assert repo.get("source-test-a") is not None


def test_create_rejects_duplicate_id(repo: JsonSourceRepository) -> None:
    repo.create(_source("a"))
    with pytest.raises(DuplicateRecord):
        repo.create(_source("a"))


def test_update_changes_only_the_targeted_source(repo: JsonSourceRepository) -> None:
    repo.create(_source("a"))
    repo.create(_source("b"))
    updated = repo.get("source-test-a")
    updated["enabled"] = False
    updated["last_status"] = "ok: 3 new item(s)"
    repo.update("source-test-a", updated)

    assert repo.get("source-test-a")["enabled"] is False
    assert repo.get("source-test-a")["last_status"] == "ok: 3 new item(s)"
    # The untouched source must be byte-for-byte identical to what was created.
    assert repo.get("source-test-b") == _source("b")


def test_update_raises_for_unknown_id(repo: JsonSourceRepository) -> None:
    with pytest.raises(RecordNotFound):
        repo.update("does-not-exist", _source("a", id="does-not-exist"))


# ---------------------------------------------------------------------------
# removing one source where current behavior permits it
# ---------------------------------------------------------------------------

def test_delete_removes_the_targeted_source(repo: JsonSourceRepository) -> None:
    repo.create(_source("a"))
    repo.create(_source("b"))
    repo.delete("source-test-a")
    assert repo.get("source-test-a") is None
    assert repo.get("source-test-b") is not None


def test_delete_raises_for_unknown_id(repo: JsonSourceRepository) -> None:
    with pytest.raises(RecordNotFound):
        repo.delete("does-not-exist")


# ---------------------------------------------------------------------------
# persistence round-trip
# ---------------------------------------------------------------------------

def test_round_trip_through_a_second_repository_instance(tmp_path: Path) -> None:
    first = JsonSourceRepository(data_dir=tmp_path)
    first.create(_source("a"))
    second = JsonSourceRepository(data_dir=tmp_path)
    assert second.get("source-test-a") == _source("a")


def test_round_trip_preserves_full_record_shape_on_disk(tmp_path: Path) -> None:
    repo = JsonSourceRepository(data_dir=tmp_path)
    repo.create(_source("a"))
    raw = json.loads((tmp_path / "configuration" / "sources.json").read_text(encoding="utf-8"))
    assert raw == [_source("a")]


# ---------------------------------------------------------------------------
# no accidental loss of unrelated source entries during collection rewrite
# ---------------------------------------------------------------------------

def test_no_collateral_loss_across_many_sequential_mutations(repo: JsonSourceRepository) -> None:
    # Every write to a JsonSourceRepository rewrites the entire backing
    # file (module docstring) -- this is the direct test that doing so
    # 12 times in a row across create/update/delete never drops or
    # corrupts an unrelated entry, which is the actual risk that storage
    # strategy introduces and every other repository in this package does
    # not have to guard against.
    for suffix in "abcdefghij":
        repo.create(_source(suffix))
    repo.delete("source-test-c")
    updated_e = repo.get("source-test-e")
    updated_e["enabled"] = False
    repo.update("source-test-e", updated_e)

    remaining_ids = {s["id"] for s in repo.list()}
    assert remaining_ids == {f"source-test-{c}" for c in "abdefghij"}
    for suffix in "abdfghij":  # every untouched source, byte-for-byte
        assert repo.get(f"source-test-{suffix}") == _source(suffix)
    assert repo.get("source-test-e")["enabled"] is False


def test_create_does_not_disturb_existing_sources(repo: JsonSourceRepository) -> None:
    repo.create(_source("a"))
    repo.create(_source("b"))
    assert repo.get("source-test-a") == _source("a")
