"""Faster collection scanning must preserve the existing identity suggestions."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

from app.services.variety_external_coverage import compare_baseline, load_external_baselines
from app.services.variety_universe.identity import resolve_identity


def test_projection_matches_resolver_for_saved_collections_and_editable_identity_fields():
    root = Path(__file__).resolve().parents[1]
    varieties = [
        {"id": "rasp", "name": "Lewis", "berry_ids": ["berry-raspberry"]},
        {"id": "black", "name": "Lewis", "berry_id": "berry-blackberry"},
        {"id": "blue", "name": "Bluecrop", "berry_ids": ["berry-blueberry"]},
        {"id": "alias", "name": "Human edited", "aliases": ["Blaue Donau", "Jewel"]},
        {"id": "company", "name": "Jewel", "entity_type": "company"},
        {"id": "code", "name": "Other", "attributes": {"selection_code": "ORUS 1234-1", "trade_name": "Rubel"}},
        {"id": "short", "name": "A"},
        {"id": "overlap", "name": "Duke extra words"},
        {"name": "Duke"},
    ]
    fields = ("trade_name", "commercial_name", "denomination", "selection_code",
              "breeder_code", "patent_number", "patent_id", "rights_id")
    varieties.extend({"id": field, "name": "Separate " + field,
                      "attributes": {field: "Jewel"}} for field in fields)
    original = deepcopy(varieties)
    entries_checked = 0
    for baseline in load_external_baselines(root / "data"):
        report = compare_baseline(baseline, varieties=varieties, candidates=[])
        for row in report["entries"]:
            berries = (["berry-blueberry"] if row.get("berry_scope") == "blueberry" else []) if row["genus"] == "Vaccinium" else {
                "Rubus": ["berry-raspberry", "berry-blackberry"], "Fragaria": ["berry-strawberry"]}[row["genus"]]
            expected = resolve_identity({"candidate_name": row["name"], "berry_ids": berries}, varieties)["matches"] if berries else []
            expected = {match["variety_id"]: match["variety_name"] for match in expected
                        if match["reason"] == "exact_identity_string"}
            assert {match["id"]: match["name"] for match in row["catalog_matches"]} == expected
            entries_checked += 1
    assert entries_checked > 2400
    assert varieties == original


def test_next_projection_uses_current_alias_crop_and_name_edits_without_stale_matches():
    baseline = {"id": "fixture", "source_title": "Fixture", "input_sha256": "fixture",
                "entries": [{"name": "Jewel", "genus": "Rubus", "references": []}]}
    varieties = [{"id": "editable", "name": "Jewel", "berry_ids": ["berry-raspberry"]}]
    assert compare_baseline(baseline, varieties=varieties, candidates=[])["entries"][0]["status"] == "catalog_name_found"
    varieties[0]["berry_ids"] = ["berry-blueberry"]
    assert compare_baseline(baseline, varieties=varieties, candidates=[])["entries"][0]["status"] == "no_name_match"
    varieties[0]["berry_ids"] = []
    varieties[0]["name"] = "New name"
    assert compare_baseline(baseline, varieties=varieties, candidates=[])["entries"][0]["status"] == "no_name_match"
    varieties[0]["aliases"] = ["Jewel"]
    assert compare_baseline(baseline, varieties=varieties, candidates=[])["entries"][0]["catalog_matches"] == [
        {"id": "editable", "name": "New name", "href": "/entities/variety/editable"}]


def test_company_source_work_stays_bounded_as_roster_grows_without_losing_name_scope(tmp_path, monkeypatch):
    from app.services import variety_portfolio_coverage as portfolio
    folder = tmp_path / "imports/competitor-coverage-registry-2026-09-21"
    folder.mkdir(parents=True)
    roster = [{"input_registry_name": "Tracked " + str(i), "canonical_entity_ids": ["company-a"],
               "resolution_status": "matched"} for i in range(20)]
    (folder / "reconciliation-matrix.json").write_text(json.dumps({"rows": roster}), encoding="utf-8")
    sources = [{"id": "source-" + str(i), "title": "Mixed source", "url": "https://example.test/varieties",
                "company_ids": ["company-a", "company-b"], "berry_ids": ["berry-raspberry"],
                "checked_on": "2026-10-07", "capture_status": "names_enumerated", "source_type": "breeder_catalog",
                "review_state": "unreviewed", "enumerated_scope": "Two explicit names", "limitations": "Not complete",
                "names": [{"candidate_name": "Name " + cid, "source_company_ids": [cid],
                           "source_company_context": "Printed under " + cid, "berry_id": "berry-raspberry"}
                          for cid in ("company-a", "company-b")]} for i in range(3)]
    entities = [{"id": cid, "name": cid, "entity_type": "company"} for cid in ("company-a", "company-b")]
    calls = []
    original = portfolio.source_company_ids
    def counted(source):
        calls.append(source["id"])
        return original(source)
    monkeypatch.setattr(portfolio, "source_company_ids", counted)
    inputs = deepcopy((sources, entities, roster))
    view = portfolio.portfolio_coverage(data_dir=tmp_path, sources=sources, varieties=[], entities=entities,
                                      candidates=[], today=date(2026, 10, 30))
    assert len(view["subjects"]) == 20
    assert all(row["named_occurrences"] == 3 and len(row["sources"]) == 3 for row in view["subjects"])
    assert len(calls) <= 3 * len(sources)
    assert (sources, entities, roster) == inputs
