"""Primary-page coverage keeps identity ambiguity and human decisions explicit."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import main
from app.services.variety_navigation import candidate_queue
from app.services.variety_portfolio_coverage import load_portfolio_observations, portfolio_coverage, reconcile_portfolios


def source(names, **extra):
    return {"id": "portfolio-test", "title": "Primary strawberry releases", "url": "https://example.test/varieties",
            "company_ids": ["company-a"], "berry_ids": ["berry-strawberry"], "checked_on": "2026-10-07",
            "capture_status": "names_enumerated", "source_type": "breeder_catalog", "review_state": "unreviewed",
            "enumerated_scope": "Linked release names", "limitations": "Partial historical coverage", "names": names, **extra}


ENTITIES = [{"id": "company-a", "entity_type": "company", "name": "Alpha"}]


def reconcile(sources, varieties=None, candidates=None):
    return reconcile_portfolios(sources=sources, varieties=varieties or [], entities=ENTITIES,
                               candidates=candidates or [], today=date(2026, 10, 7))


def test_shared_brand_does_not_collapse_two_denominations():
    names = [{"candidate_name": code, "trade_name": "Florida Pearl", "berry_id": "berry-strawberry"}
             for code in ("FL 16.78-109", "FL 19.66-220")]
    varieties = [{"id": "variety-pearl", "name": "Florida Pearl", "entity_type": "variety", "berry_ids": ["berry-strawberry"]}]
    rows, candidates = reconcile([source(names)], varieties)
    assert len(candidates) == 2 and len({c["id"] for c in candidates}) == 2
    assert rows[0]["matched"] == 0 and rows[0]["needs_review"] == 2
    assert all(not c["auto_confirmed"] and not c["human_gated"] for c in candidates)
    # The shared brand is a review suggestion, never enough for a catalog match.
    assert all(c["candidate_canonical_match"] == "variety-pearl" for c in candidates)


def test_ambiguous_alias_and_wrong_species_stay_unresolved():
    varieties = [{"id": "v1", "name": "A", "aliases": ["Shared"], "entity_type": "variety", "berry_ids": ["berry-strawberry"]},
                 {"id": "v2", "name": "B", "aliases": ["Shared"], "entity_type": "variety", "berry_ids": ["berry-strawberry"]},
                 {"id": "v3", "name": "Cherry", "entity_type": "variety", "berry_ids": ["berry-raspberry"]}]
    rows, candidates = reconcile([source([{"candidate_name": n, "berry_id": "berry-strawberry"} for n in ["Shared", "Cherry"]])], varieties)
    assert rows[0]["matched"] == 0 and rows[0]["needs_review"] == 2
    assert candidates[1]["candidate_canonical_match"] is None


def test_human_decisions_and_fields_survive_new_provenance():
    rejected = {"id": "vcand-old", "candidate_name": "Earlier", "berry_id": "berry-strawberry", "status": "rejected",
                "identity_state": "rejected", "human_gated": True, "review_notes": "Wrong kind of plant", "knowledge": {"notes": "User edit"}}
    distinct = {"id": "vcand-distinct", "candidate_name": "New", "berry_id": "berry-strawberry", "status": "reviewed",
                "identity_state": "distinct", "human_gated": True, "reviewer": "Human", "review_notes": "Keep separate"}
    original = deepcopy([rejected, distinct])
    rows, candidates = reconcile([source([{"candidate_name": n, "berry_id": "berry-strawberry"} for n in ["Earlier", "New"]])], candidates=original)
    assert original == [rejected, distinct]
    assert len(candidates) == 2 and rows[0]["closed"] == 1 and rows[0]["awaiting_catalog"] == 1
    assert candidates[0]["knowledge"] == rejected["knowledge"] and candidates[0]["review_notes"] == rejected["review_notes"]
    assert [c["id"] for c in candidate_queue(candidates, {"source": "portfolio-test", "company": "company-a"})["candidates"]] == ["vcand-distinct"]


def test_source_change_and_removal_rebuild_read_only_names():
    old = source([{"candidate_name": "Before", "berry_id": "berry-strawberry"}])
    rows, candidates = reconcile([old])
    assert candidates[0]["portfolio_sources"][0]["candidate_name"] == "Before"
    new = source([{"candidate_name": "After", "berry_id": "berry-strawberry"}])
    _, candidates = reconcile([new])
    assert [c["candidate_name"] for c in candidates] == ["After"]
    assert reconcile([]) == ([], [])


def test_failed_capture_is_not_zero_varieties_and_future_dates_are_flagged(tmp_path):
    rows = [source([], capture_status="unreadable"), source([], id="portfolio-future", checked_on="2027-01-01")]
    result = portfolio_coverage(data_dir=tmp_path, sources=rows, varieties=[], entities=ENTITIES, candidates=[], today=date(2026, 10, 7), filters={"berry": "berry-strawberry"})
    assert len(result["sources"]) == 2 and result["summary"]["unreadable_sections"] == 1
    assert result["sources"][1]["freshness"] == "Check date in future"


def test_real_manifest_preserves_registry_and_all_four_berry_denominators():
    from scripts.audit_variety_portfolios import audit
    report = audit(Path(__file__).resolve().parents[1] / "data")
    assert report["summary"]["registry_entries"] == 77
    assert report["summary"]["names"] == 93
    assert {r["id"]: r["names"] for r in report["by_berry"]} == {
        "berry-blueberry": 37, "berry-strawberry": 14, "berry-raspberry": 19, "berry-blackberry": 23}
    assert "visible_candidates" not in report
    assert all("review_notes" not in str(r) for r in report["subjects"])


def test_primary_candidates_render_only_in_authoring_and_get_never_persists(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    coverage = client.get("/varieties/coverage?berry=berry-strawberry")
    assert coverage.status_code == 200
    assert "Florida Foundation Seed Producers" in coverage.text and "Could not read" in coverage.text
    assert "Checked recently" in coverage.text
    candidates = client.get("/varieties/candidates?source=portfolio-uf-strawberry")
    assert candidates.status_code == 200 and "FL 19.66-220" in candidates.text and "Florida Pearl" in candidates.text
    assert "awaiting review; no company role approved" in candidates.text
    assert list(tmp_path.rglob("*.json")) == []
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    public = client.get("/varieties/coverage")
    assert public.status_code == 200
    assert "portfolio-uf-strawberry" not in public.text and "Primary portfolio coverage" not in public.text
    assert client.get("/varieties/candidates").status_code == 403


@pytest.mark.parametrize("change", [{"url": "javascript:alert(1)"}, {"checked_on": "unknown"}, {"capture_status": "complete_internet"}, {"title": ""}])
def test_invalid_source_metadata_fails_closed(tmp_path, change):
    folder = tmp_path / "imports/variety-portfolio-observations-test"
    folder.mkdir(parents=True)
    (folder / "observations.json").write_text(json.dumps({"kind": "unreviewed_portfolio_name_observations", "sources": [source([], **change)]}))
    with pytest.raises(ValueError):
        load_portfolio_observations(tmp_path)


def test_filters_scope_the_visible_counts_and_keep_unreadable_sources(tmp_path):
    sources = [source([{"candidate_name": "Straw", "berry_id": "berry-strawberry"}]),
               source([], id="unreadable", capture_status="unreadable"),
               source([{"candidate_name": "Blue", "berry_id": "berry-blueberry"}],
                      id="blue", berry_ids=["berry-blueberry"], title="Blueberry portfolio")]
    result = portfolio_coverage(data_dir=tmp_path, sources=sources, varieties=[], entities=ENTITIES,
                               candidates=[], filters={"berry": "berry-strawberry"})
    assert result["summary"]["names"] == 1 and result["summary"]["source_sections"] == 2
    assert result["summary"]["unreadable_sections"] == 1
    assert next(row for row in result["by_berry"] if row["id"] == "berry-blueberry")["names"] == 0


def test_bad_observations_do_not_break_existing_catalog_or_review(monkeypatch, tmp_path):
    from app.services import variety_portfolio_coverage as module
    def invalid(_data_dir):
        raise ValueError("Stored portfolio observations failed validation")
    monkeypatch.setattr(module, "load_portfolio_observations", invalid)
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    client = TestClient(main.app)
    for path in ("/varieties/coverage", "/varieties/candidates"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Primary portfolio checks are unavailable" in response.text
    assert list(tmp_path.rglob("*.json")) == []
