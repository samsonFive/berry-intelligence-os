"""The lightweight overlay index must retain current Reader semantics."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.repositories.json.entities import EntityRepository
from app.services.request_corpus import RequestCorpus, bind_request_corpus, reset_request_corpus


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def test_reader_index_returns_only_display_fields_and_isolates_mutation(tmp_path: Path) -> None:
    record = {
        "id": "company-orchard", "entity_type": "company", "name": "Orchard Group",
        "aliases": ["Orchard Alias"], "also_known_as": ["Example Orchard"],
        "attributes": {"catalog_visibility": "published", "nested": {"notes": ["retained metadata"]}},
        "description": "Full entity details are not Reader display fields.",
    }
    _write(tmp_path / "entities/companies/orchard.json", record)
    repo = EntityRepository(data_dir=tmp_path)
    expected = {field: deepcopy(record[field]) for field in ("id", "name", "entity_type", "aliases", "also_known_as")}
    projected = repo.reader_index(include_workspace=True)
    assert projected == {record["id"]: expected}
    projected[record["id"]]["aliases"].append("caller mutation")
    projected[record["id"]]["also_known_as"].clear()
    projected[record["id"]]["name"] = "caller rename"
    projected.clear()
    assert repo.reader_index(include_workspace=True) == {record["id"]: expected}
    assert repo.get(record["id"]) == record


def test_reader_index_observes_external_name_alias_addition_and_deletion_edits(tmp_path: Path) -> None:
    path = tmp_path / "entities/companies/orchard.json"
    record = {"id": "company-orchard", "entity_type": "company", "name": "Old Orchard", "aliases": ["Old Alias"]}
    _write(path, record)
    repo = EntityRepository(data_dir=tmp_path)
    assert repo.reader_index(include_workspace=True)[record["id"]]["name"] == "Old Orchard"
    previous = path.stat()
    _write(path, {**record, "name": "Renamed Orchard Group", "aliases": ["New Alias", "Another new alias"]})
    # Overlayfs can preserve mtime during same-tick edits; the existing size
    # component of the repository signature must still invalidate this read.
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    changed = repo.reader_index(include_workspace=True)[record["id"]]
    assert changed["name"] == "Renamed Orchard Group"
    assert changed["aliases"] == ["New Alias", "Another new alias"]
    new_path = tmp_path / "entities/companies/second.json"
    _write(new_path, {"id": "company-second", "name": "Second Orchard", "entity_type": "company"})
    assert "company-second" in repo.reader_index(include_workspace=True)
    new_path.unlink()
    assert "company-second" not in repo.reader_index(include_workspace=True)


def test_reader_index_preserves_request_corpus_duplicate_and_workspace_visibility(monkeypatch, tmp_path: Path) -> None:
    shared_id = "company-duplicate"
    _write(tmp_path / "entities/companies/first.json", {
        "id": shared_id, "entity_type": "company", "name": "Earlier public row",
    })
    _write(tmp_path / "entities/varieties/last.json", {
        "id": shared_id, "entity_type": "company", "name": "Last workspace row",
        "attributes": {"catalog_visibility": "workspace"},
    })
    repo = EntityRepository(data_dir=tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    token = bind_request_corpus(RequestCorpus(data_dir=tmp_path, schemas_dir=main.SCHEMAS_DIR, inbox_dir=tmp_path / "inbox"))
    try:
        assert shared_id not in main.entity_index()
        assert repo.reader_index(include_workspace=False) == main.entity_index() == {}
    finally:
        reset_request_corpus(token)
    assert repo.reader_index(include_workspace=True)[shared_id]["name"] == "Last workspace row"


def test_actual_overlay_refreshes_both_alias_fields_name_and_workspace_visibility(monkeypatch, tmp_path: Path) -> None:
    data, inbox = tmp_path / "data", tmp_path / "inbox"
    monkeypatch.setattr(main, "DATA_DIR", data)
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    inbox.mkdir()
    item_id = "ev-reader-projection"
    _write(data / "evidence" / f"{item_id}.json", {
        "id": item_id, "status": "published", "source_type": "article",
        "title": "Example Orchard and Internal Selection trial", "summary": "A public trial.",
        "entity_ids": ["company-orchard", "variety-internal"],
        "article": {"paragraphs": [{"locator": "p1", "text": "Fixture source body remains intact."}]},
    })
    company = {"id": "company-orchard", "entity_type": "company", "name": "Orchard Group",
               "aliases": ["Orchard Alias"], "also_known_as": ["Example Orchard"]}
    company_path = data / "entities/companies/orchard.json"
    _write(company_path, company)
    _write(data / "entities/varieties/internal.json", {
        "id": "variety-internal", "entity_type": "variety", "name": "Internal Selection",
        "attributes": {"catalog_visibility": "workspace"},
    })
    calls = []
    original = EntityRepository.reader_index
    def track(self, *, include_workspace):
        calls.append(include_workspace)
        return original(self, include_workspace=include_workspace)
    monkeypatch.setattr(EntityRepository, "reader_index", track)
    client = TestClient(main.app)
    url = f"/api/intelligence/{item_id}/reader"
    public = client.get(url)
    assert public.status_code == 200
    assert 'href="/entities/company/company-orchard">Orchard Group</a>' in public.text
    assert '<p class="v2-card-subject">' in public.text
    assert 'href="/entities/variety/variety-internal"' not in public.text
    _write(company_path, {**company, "name": "Renamed Orchard Group", "aliases": ["Example Orchard"], "also_known_as": []})
    edited = client.get(url)
    assert edited.status_code == 200
    assert 'href="/entities/company/company-orchard">Renamed Orchard Group</a>' in edited.text
    assert '<p class="v2-card-subject">' in edited.text
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    workspace = client.get(url)
    assert workspace.status_code == 200
    assert 'href="/entities/variety/variety-internal">Internal Selection</a>' in workspace.text
    assert "Fixture source body remains intact." in public.text and "Fixture source body remains intact." in workspace.text
    assert calls == [False, False, True]
    full_page = client.get(f"/intelligence/{item_id}")
    assert full_page.status_code == 200
    assert calls == [False, False, True], "Full-page Reader must retain the complete entity index"
