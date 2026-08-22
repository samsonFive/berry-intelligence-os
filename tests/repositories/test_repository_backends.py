from __future__ import annotations

from pathlib import Path

import pytest

from app.repositories.base import DuplicateRecord, InvalidRecord, RecordNotFound
from app.repositories.memory import get_memory_repositories
from app.repositories.json.assessments import AssessmentRepository
from app.repositories.json.entities import EntityRepository
from app.repositories.json.evidence import EvidenceRepository
from app.repositories.json.facts import FactRepository
from app.repositories.json.recommendations import RecommendationRepository
from app.repositories.json.relationships import RelationshipRepository
from app.repositories.json.signals import SignalRepository
from app.repositories.json.sources import JsonSourceRepository
from app.repositories.json.strategic_questions import StrategicQuestionRepository
from tests.repositories.test_json_repository_contract import REPO_SPECS
from tests.repositories.test_source_repository import _source

JSON_CLASSES = dict((name, cls) for name, cls, _factory in REPO_SPECS) | {"sources": JsonSourceRepository}
FACTORIES = dict((name, factory) for name, _cls, factory in REPO_SPECS) | {"sources": _source}


@pytest.fixture(params=["json", "memory"])
def backend(request, tmp_path: Path):
    if request.param == "memory":
        return request.param, get_memory_repositories()
    return request.param, None


@pytest.mark.parametrize("family", [*JSON_CLASSES])
def test_shared_logical_repository_contract(backend, family: str, tmp_path: Path) -> None:
    backend_name, bundle = backend
    repo = getattr(bundle, family) if bundle else JSON_CLASSES[family](data_dir=tmp_path / family)
    make = FACTORIES[family]
    first, second = make("a"), make("b")
    returned = repo.create(first)
    assert returned == first and repo.get(first["id"]) == first
    returned["_returned_mutation"] = True
    assert "_returned_mutation" not in repo.get(first["id"])
    assert repo.get("missing") is None
    repo.create(second)
    assert {r["id"] for r in repo.list()} == {first["id"], second["id"]}
    assert [r["id"] for r in repo.list()] == [r["id"] for r in repo.list()]
    if "status" in first:
        assert {r["id"] for r in repo.list(status=first["status"])} == {first["id"], second["id"]}
    with pytest.raises(DuplicateRecord): repo.create(make("a"))
    changed = {**first, "_contract_marker": "changed"}
    assert repo.update(first["id"], changed) == changed
    with pytest.raises(RecordNotFound): repo.update("missing", {**changed, "id": "missing"})
    if family != "sources":
        broken = dict(changed)
        del broken["status"]
        with pytest.raises(InvalidRecord): repo.update(first["id"], broken)
    with pytest.raises(RecordNotFound): repo.delete("missing")
    fetched = repo.get(first["id"])
    fetched["_contract_marker"] = "mutated outside repository"
    assert repo.get(first["id"])["_contract_marker"] == "changed"
    listed = repo.list()
    listed[0]["_list_mutation"] = True
    assert all("_list_mutation" not in record for record in repo.list())
    repo.delete(first["id"])
    assert repo.get(first["id"]) is None and repo.get(second["id"]) == second


@pytest.mark.parametrize("backend_name", ["json", "memory"])
def test_evidence_ordering_contract_is_backend_independent(backend_name: str, tmp_path: Path) -> None:
    repo = get_memory_repositories().evidence if backend_name == "memory" else EvidenceRepository(data_dir=tmp_path)
    make = FACTORIES["evidence"]
    older = {**make("old"), "published_date": "2020-01-01"}
    newer = {**make("new"), "published_date": "2025-01-01"}
    repo.create_many([older, newer])
    assert [record["id"] for record in repo.list()] == [newer["id"], older["id"]]


def test_independent_memory_bundles_do_not_share_state() -> None:
    first, second = get_memory_repositories(), get_memory_repositories()
    first.entities.create(FACTORIES["entities"]("a"))
    assert second.entities.list() == []


def test_memory_validation_matches_json_contract() -> None:
    repo = get_memory_repositories().entities
    broken = FACTORIES["entities"]("a")
    del broken["status"]
    with pytest.raises(InvalidRecord): repo.create(broken)


def test_memory_backend_performs_no_filesystem_writes(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs): raise AssertionError("filesystem write attempted")
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    repo = get_memory_repositories().entities
    repo.create(FACTORIES["entities"]("a"))
    repo.update(FACTORIES["entities"]("a")["id"], {**FACTORIES["entities"]("a"), "name": "changed"})
    repo.delete(FACTORIES["entities"]("a")["id"])
