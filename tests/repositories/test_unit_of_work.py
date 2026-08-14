"""Tests for the Unit-of-Work seam (V2 Phase 2B.1,
app/repositories/unit_of_work.py). Proves exactly the guarantees that
module's own docstring claims -- best-effort compensation on failure, no
compensation attempted on success, and that the module is honest about not
providing real atomicity -- using only temporary fixture data."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.repositories.base import RecordNotFound, TransactionError
from app.repositories.json.entities import EntityRepository
from app.repositories.json.evidence import EvidenceRepository
from app.repositories.unit_of_work import JsonUnitOfWork


def _entity(suffix: str) -> dict:
    return {
        "id": f"company-uow-test-{suffix}",
        "record_type": "entity",
        "entity_type": "company",
        "name": f"UoW Test Company {suffix}",
        "status": "active",
    }


def _evidence(suffix: str) -> dict:
    return {
        "id": f"ev-uow-test-{suffix}",
        "record_type": "evidence",
        "status": "published",
        "source_type": "article",
        "title": f"UoW test evidence {suffix}",
        "captured_date": "2026-08-14",
        "summary": "Summary.",
        "submitted_by": "uow-test",
        "priority": {
            dim: {"level": "none", "rationale": ""}
            for dim in ("reading", "testing", "commercial_position", "monitoring")
        },
    }


def test_clean_exit_leaves_every_created_record_in_place(tmp_path: Path) -> None:
    entities = EntityRepository(data_dir=tmp_path)
    evidence = EvidenceRepository(data_dir=tmp_path)
    with JsonUnitOfWork(entities=entities, evidence=evidence) as uow:
        uow.entities.create(_entity("a"))
        uow.evidence.create(_evidence("a"))
    assert entities.get("company-uow-test-a") is not None
    assert evidence.get("ev-uow-test-a") is not None


def test_exception_mid_block_rolls_back_records_created_so_far(tmp_path: Path) -> None:
    entities = EntityRepository(data_dir=tmp_path)
    evidence = EvidenceRepository(data_dir=tmp_path)
    with pytest.raises(RuntimeError):
        with JsonUnitOfWork(entities=entities, evidence=evidence) as uow:
            uow.entities.create(_entity("a"))
            uow.evidence.create(_evidence("a"))
            raise RuntimeError("simulated failure after two successful creates")
    # Best-effort compensation: both records created earlier in this same
    # unit of work are gone.
    assert entities.get("company-uow-test-a") is None
    assert evidence.get("ev-uow-test-a") is None


def test_original_exception_propagates_when_rollback_succeeds(tmp_path: Path) -> None:
    entities = EntityRepository(data_dir=tmp_path)
    with pytest.raises(ValueError, match="original failure"):
        with JsonUnitOfWork(entities=entities) as uow:
            uow.entities.create(_entity("a"))
            raise ValueError("original failure")


def test_records_created_outside_the_unit_of_work_are_never_touched_by_rollback(tmp_path: Path) -> None:
    entities = EntityRepository(data_dir=tmp_path)
    entities.create(_entity("pre-existing"))  # created directly, not through a UoW
    with pytest.raises(RuntimeError):
        with JsonUnitOfWork(entities=entities) as uow:
            uow.entities.create(_entity("a"))
            raise RuntimeError("boom")
    assert entities.get("company-uow-test-pre-existing") is not None
    assert entities.get("company-uow-test-a") is None


def test_rollback_cleanup_failure_raises_transaction_error_chained_to_original(tmp_path: Path) -> None:
    entities = EntityRepository(data_dir=tmp_path)
    with pytest.raises(TransactionError) as exc_info:
        with JsonUnitOfWork(entities=entities) as uow:
            created = uow.entities.create(_entity("a"))
            # Simulate something else deleting the record before rollback
            # gets a chance to -- proves cleanup failure is reported, not
            # silently swallowed, and the module docstring's own claim
            # about this case holds.
            entities.delete(created["id"])
            raise RuntimeError("boom")
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_two_repositories_created_in_order_roll_back_in_reverse_order(tmp_path: Path) -> None:
    # Not directly observable from the public interface, but reverse-order
    # rollback matters once real referential dependencies exist (e.g. a
    # Fact citing an Evidence id) -- deleting the Fact before the Evidence
    # it depends on, not the other way around. Verified here via the
    # simpler, currently-real case: both deletes succeed regardless of
    # order for independent records, so this test only pins the *order*
    # rollback happens in, for a future dependent-record case to rely on.
    entities = EntityRepository(data_dir=tmp_path)
    evidence = EvidenceRepository(data_dir=tmp_path)
    deleted_order: list[str] = []

    class _TrackingEntityRepository(EntityRepository):
        def delete(self, record_id: str) -> None:
            deleted_order.append(("entities", record_id))
            super().delete(record_id)

    class _TrackingEvidenceRepository(EvidenceRepository):
        def delete(self, record_id: str) -> None:
            deleted_order.append(("evidence", record_id))
            super().delete(record_id)

    tracked_entities = _TrackingEntityRepository(data_dir=tmp_path)
    tracked_evidence = _TrackingEvidenceRepository(data_dir=tmp_path)
    with pytest.raises(RuntimeError):
        with JsonUnitOfWork(entities=tracked_entities, evidence=tracked_evidence) as uow:
            uow.entities.create(_entity("a"))
            uow.evidence.create(_evidence("a"))
            raise RuntimeError("boom")
    assert deleted_order == [("evidence", "ev-uow-test-a"), ("entities", "company-uow-test-a")]
