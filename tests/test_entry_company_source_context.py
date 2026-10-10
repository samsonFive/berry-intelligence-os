"""A mixed-program publication must not assign every name to every company."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.services.company_variety_discoveries import company_variety_discoveries
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios


ENTITIES = [{"id": f"company-{c}", "name": c.upper(), "entity_type": "company"} for c in ("a", "b", "publisher")]


def source(names, identifier="mixed"):
    return {"id": identifier, "title": "Mixed programs", "url": "https://example.org/register",
            "checked_on": "2026-10-09", "capture_status": "partial", "review_state": "unreviewed",
            "source_type": "cultivar_register", "company_ids": ["company-publisher"],
            "berry_ids": ["berry-blueberry", "berry-raspberry"], "enumerated_scope": "Three described entries",
            "limitations": "Not complete", "names": names}


def entries():
    return [
        {"candidate_name": "Alpha", "berry_id": "berry-blueberry", "source_company_ids": ["company-a"], "source_company_context": "Entry names A."},
        {"candidate_name": "Beta", "berry_id": "berry-raspberry", "source_company_ids": ["company-b"], "source_company_context": "Entry names B."},
        {"candidate_name": "Unknown", "berry_id": "berry-blueberry", "source_company_ids": []},
    ]


def test_company_filters_and_profiles_use_the_entry_without_creating_roles(tmp_path):
    sources = [source(entries())]
    original = deepcopy(sources)
    rows, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=ENTITIES, candidates=[])
    for cid, expected in (("company-a", "Alpha"), ("company-b", "Beta")):
        scoped = candidate_queue(candidates, {"company": cid, "source": "mixed"})
        assert [c["candidate_name"] for c in scoped["candidates"]] == [expected]
        profile = company_variety_discoveries(entity_id=cid, sources=rows)
        assert [r["name"] for r in profile["rows"]] == [expected]
        report = portfolio_coverage(data_dir=tmp_path, sources=sources, varieties=[], entities=ENTITIES, candidates=[], filters={"company":cid})
        assert report["summary"]["names"] == 1
        assert [n["candidate_name"] for s in report["sources"] for n in s["names"]] == [expected]
    assert candidate_queue(candidates, {"company":"company-publisher"})["candidates"] == []
    assert company_variety_discoveries(entity_id="company-publisher", sources=rows)["rows"] == []
    assert all(not c["human_gated"] and not c["auto_confirmed"] and not c["breeder_owner"] and not c["proposed_relationships"] for c in candidates)
    assert sources == original


def test_joint_company_and_source_filters_do_not_borrow_another_source_association():
    one = entries()[0]
    two = {**one, "source_company_ids":["company-b"], "source_company_context":"Other entry names B."}
    _, candidates = reconcile_portfolios(sources=[source([one], "one"),source([two], "two")], varieties=[], entities=ENTITIES, candidates=[])
    assert len(candidate_queue(candidates, {"company":"company-b"})["candidates"]) == 1
    assert candidate_queue(candidates, {"company":"company-b","source":"one"})["candidates"] == []
    assert len(candidate_queue(candidates, {"company":"company-b","source":"two"})["candidates"]) == 1


def test_unresolved_organization_wording_is_searchable_without_an_assignment():
    unknown = {"candidate_name":"Unnamed Program Selection", "berry_id":"berry-blueberry",
               "source_company_ids":[], "source_company_context":"Entry names Orchard Research Group; identity unresolved."}
    original = deepcopy(unknown)
    _, candidates = reconcile_portfolios(sources=[source([unknown])], varieties=[], entities=ENTITIES, candidates=[])
    assert len(candidate_queue(candidates, {"q":"Orchard Research Group", "source":"mixed"})["candidates"]) == 1
    assert candidate_queue(candidates, {"q":"Orchard Research Group", "company":"company-publisher"})["candidates"] == []
    assert unknown == original
    assert not candidates[0]["portfolio_sources"][0]["companies"]
    assert not candidates[0]["breeder_owner"] and not candidates[0]["proposed_relationships"]


def test_older_single_program_sources_keep_ids_and_saved_decisions_on_replay():
    legacy = source([{"candidate_name":"Alpha","berry_id":"berry-blueberry"}])
    _, old = reconcile_portfolios(sources=[legacy], varieties=[], entities=ENTITIES, candidates=[])
    human = {**old[0], "human_gated":True,"identity_state":"rejected","status":"rejected","review_notes":"Keep separate", "photos":[{"operator_choice":"Retain"}]}
    original = deepcopy(human)
    updated = {**legacy,"names":[entries()[0]]}
    _, new = reconcile_portfolios(sources=[updated], varieties=[], entities=ENTITIES, candidates=[human])
    assert new[0]["id"] == old[0]["id"] and human == original
    assert all(new[0][k] == human[k] for k in ("status","human_gated","identity_state","review_notes","photos"))
    assert new[0]["portfolio_sources"][0]["companies"][0]["entity_id"] == "company-a"
    assert old[0]["portfolio_sources"][0]["companies"][0]["entity_id"] == "company-publisher"


@pytest.mark.parametrize("field,value", [("source_company_ids","company-a"),("source_company_ids",[{}]),("source_company_ids",[" "]),("source_company_context",{}),("source_company_context","")])
def test_invalid_entry_associations_fail_closed(tmp_path, field, value):
    name = {**entries()[0], field:value}
    folder = tmp_path / "imports/variety-portfolio-observations-2026-10-09-test"
    folder.mkdir(parents=True)
    (folder / "observations.json").write_text(json.dumps({"kind":"unreviewed_portfolio_name_observations","sources":[source([name])]}))
    with pytest.raises(ValueError, match="failed validation"):
        load_portfolio_observations(tmp_path)


def test_registry_company_accounting_does_not_count_other_programs(tmp_path):
    folder = tmp_path / "imports/competitor-coverage-registry-2026-09-21"
    folder.mkdir(parents=True)
    (folder / "reconciliation-matrix.json").write_text(json.dumps({"rows":[
        {"input_registry_name":e["name"],"canonical_entity_ids":[e["id"]],"resolution_status":"matched","website":""} for e in ENTITIES
    ]}))
    report = portfolio_coverage(data_dir=tmp_path, sources=[source(entries())], varieties=[], entities=ENTITIES, candidates=[])
    subjects = {s["entity_ids"][0]:s for s in report["subjects"]}
    assert subjects["company-a"]["named_occurrences"] == 1 and subjects["company-a"]["berry_ids"] == ["berry-blueberry"]
    assert subjects["company-b"]["named_occurrences"] == 1 and subjects["company-b"]["berry_ids"] == ["berry-raspberry"]
    assert subjects["company-publisher"]["named_occurrences"] == 0 and not subjects["company-publisher"]["checked"]


def test_real_register_company_context_preserves_cultivars_and_institute_boundaries():
    data = Path(__file__).resolve().parents[1] / "data"
    sources = [s for s in load_portfolio_observations(data) if s["id"].startswith("portfolio-register52-2024-")]
    all_names = [n for s in sources for n in s["names"]]
    mapped = [n for n in all_names if n.get("source_company_ids")]
    assert len(all_names) == 388 and len(mapped) == 160
    assert len({cid for n in mapped for cid in n["source_company_ids"]}) == 20
    bonnie = next(n for n in mapped if n["candidate_name"] == "Bonnie Lewis")
    assert bonnie["source_company_ids"] == ["company-james-hutton-institute"]
    costa = [n for n in mapped if "company-costa-berry-international" in n["source_company_ids"]]
    assert len(costa) == 8  # Not blanket assignment to the wider Costa parent.
    assert all(n["product_url"].endswith("#page=11") and "company-university-of-florida" in n["source_company_ids"] for n in costa)
    entities = [json.loads(p.read_text(encoding="utf-8")) for p in (data / "entities").rglob("*.json")]
    _, before = reconcile_portfolios(sources=[{**s,"names":[{k:v for k,v in n.items() if k not in {"source_company_ids","source_company_context"}} for n in s["names"]]} for s in sources], varieties=[],entities=entities,candidates=[])
    _, after = reconcile_portfolios(sources=sources,varieties=[],entities=entities,candidates=[])
    assert {(c["candidate_name"],c["berry_id"]):c["id"] for c in before} == {(c["candidate_name"],c["berry_id"]):c["id"] for c in after}
    assert all(not c["human_gated"] and not c["proposed_relationships"] and not c["breeder_owner"] for c in after)


def test_actual_origin_program_and_unknown_labels_remain_distinct_and_unreviewed():
    data = Path(__file__).resolve().parents[1] / "data"
    sources = [s for s in load_portfolio_observations(data) if s["id"].startswith("portfolio-register52-2024-")]
    names = [n for s in sources for n in s["names"]]
    georgia = [n for n in names if n.get("source_company_ids") == ["breeding_program-university-of-georgia-blueberry"]]
    assert len(georgia) == 9
    assert next(n for n in georgia if n["candidate_name"] == "TH-1987")["product_url"].endswith("#page=14")
    assert len([n for n in names if n.get("source_company_ids") == ["company-next-progeny"]]) == 3
    unresolved = [n for n in names if n.get("source_company_context") and not n.get("source_company_ids")]
    assert len(unresolved) == 60
    assert all(n["source_company_ids"] == [] for n in unresolved)
    entities = [json.loads(p.read_text(encoding="utf-8")) for p in (data / "entities").rglob("*.json")]
    _, candidates = reconcile_portfolios(sources=sources, varieties=[], entities=entities, candidates=[])
    for query, expected in (("Rutgers University",3), ("Five Acres Breeding",1), ("Five Aces Breeding",4), ("Allberry",8), ("Berryworld Plus",1)):
        hits = candidate_queue(candidates, {"q":query})["candidates"]
        assert len(hits) == expected
        assert all(not c["portfolio_sources"][0]["companies"] and not c["human_gated"] for c in hits)
    assert len(candidate_queue(candidates, {"company":"breeding_program-university-of-georgia-blueberry"})["candidates"]) == 9
    assert not candidate_queue(candidates, {"company":"breeding_program-njaes-rutgers-strawberry", "q":"Rutgers University"})["candidates"]


def test_existing_breeding_program_varieties_tab_uses_source_names_without_writes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    page = TestClient(main.app).get("/entities/breeding_program/breeding_program-university-of-georgia-blueberry?tab=varieties")
    assert page.status_code == 200
    assert 'aria-current="page">Varieties' in page.text
    assert "TH-1987" in page.text and "Varieties named in sources" in page.text
    assert "portfolio-register52-2024-blueberry-main" in page.text
    assert "Reviewed variety links · 0" in page.text
    assert not list(tmp_path.iterdir())
