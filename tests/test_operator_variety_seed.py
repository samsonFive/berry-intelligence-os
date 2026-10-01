import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services import operator_variety_seed as seeds
from app.services.variety_universe.candidates import load_variety_candidates

DATA = Path(__file__).resolve().parents[1] / "data"


def entities():
    return {row["id"]: row for row in main.all_entities()}


def test_photo_seeds_resolve_companies_without_asserting_roles_or_identity(tmp_path):
    world = entities()
    rows = seeds.seed_rows(DATA, world)
    assert len(rows) < len(seeds.fixture(DATA)["rows"])
    verity = next(row for row in rows if row["candidate_name"] == "Verity")
    assert len(verity["knowledge"]["company_associations"]) >= 2
    assert all(item["entity_id"] in world for row in rows for item in row["knowledge"]["company_associations"])
    assert all(row["source_tier"] == "weak_noncanonical_lead" for row in rows)
    assert all("breeder_owner" not in row and "proposed_relationships" not in row for row in rows)
    result = seeds.install(tmp_path, DATA, world)
    assert result["written_count"] == len(rows) and not result["rejected_count"]
    saved = load_variety_candidates(tmp_path)
    assert all(not row["human_gated"] and not row["auto_confirmed"] for row in saved)
    assert all(not row["breeder_owner"] and not row["applicant"] and not row["proposed_relationships"] for row in saved)
    assert all(row["identity_state"] != "confirmed_same" for row in saved)
    reviewed_path = tmp_path / "variety_candidates" / (saved[0]["id"] + ".json")
    reviewed = {**saved[0], "identity_state": "rejected", "reviewer": "Johnny", "review_notes": "Keep this decision"}
    reviewed_path.write_text(json.dumps(reviewed), encoding="utf-8")
    assert seeds.install(tmp_path, DATA, world)["written_count"] == 0
    assert json.loads(reviewed_path.read_text()) == reviewed


def test_filters_retain_all_associations_and_exceptions_are_not_imported(tmp_path):
    world = entities()
    view = seeds.workspace(tmp_path, DATA, world)
    assert view["installed"] == 0
    assert not list(tmp_path.iterdir())
    company_id = next(row["id"] for row in world.values() if row["name"] == "Fall Creek Farm & Nursery, Inc.")
    filtered = seeds.workspace(tmp_path, DATA, world, company=company_id, berry="berry-blueberry", letter="A")
    assert filtered["rows"] and all(row["candidate_name"].startswith("A") for row in filtered["rows"])
    assert all(row["berry_id"] == "berry-blueberry" for row in filtered["rows"])
    assert all(company_id in {item["entity_id"] for item in row["knowledge"]["company_associations"]} for row in filtered["rows"])
    assert seeds.workspace(tmp_path, DATA, world, q="nosuchvariety") ["rows"] == []
    names = {row["candidate_name"] for row in view["rows"]}
    assert "APF-122 (Mary Carmen & Madeline)" not in names
    assert len(view["exceptions"]) == 32


def test_seed_routes_are_pure_on_get_and_guard_import(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    assert client.get("/variety-seeds").status_code == 200
    assert not list(tmp_path.iterdir())
    assert client.post("/variety-seeds/import", headers={"Origin": "https://elsewhere.invalid"}).status_code == 403
    assert client.post("/variety-seeds/import", follow_redirects=False).status_code == 303
    response = client.get("/variety-seeds?q=Delizzimo")
    assert response.status_code == 200 and "ABZ Seeds" in response.text and "Review identity" in response.text
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.post("/variety-seeds/import").status_code == 403
