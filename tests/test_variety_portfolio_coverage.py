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
    assert report["summary"]["names"] == 1557
    assert report["summary"]["registry_entries_checked"] == 60
    assert [report["summary"][key] for key in ("registry_entries_partial_checks",
        "registry_entries_unavailable", "registry_entries_not_started", "registry_entries_identity_hold")] == [14, 1, 0, 2]
    benning = next(s for s in report["subjects"] if s["name"] == "Benning Blueberries")
    assert benning["source_status"] == "partial" and not benning["checked"] and benning["named_occurrences"] == 0
    assert {r["id"]: r["names"] for r in report["by_berry"]} == {
        "berry-blueberry": 423, "berry-strawberry": 729, "berry-raspberry": 259, "berry-blackberry": 146}
    sunbelle = next(s for s in report["subjects"] if s["name"] == "SunBelle")
    assert sunbelle["source_status"] == "partial" and not sunbelle["checked"]
    assert sunbelle["named_occurrences"] == 2
    assert "visible_candidates" not in report
    assert all("review_notes" not in str(r) for r in report["subjects"])
    abz = next(s for s in report["subjects"] if s["name"] == "ABZ Seeds")
    assert abz["starting_url"] == "https://www.abzseeds.com/high-tech-greenhouse"
    assert abz["starting_label"] == "Checked page ↗"
    assert any(s["id"] == "portfolio-abz-booklet" and s["capture_status"] == "unreadable" for s in report["sources"])


def test_osu_historical_release_list_accounts_for_all_entries_without_inventing_roles():
    sources = [row for row in load_portfolio_observations(Path(__file__).resolve().parents[1] / "data")
               if row["id"].startswith("portfolio-osu-cooperative-historical-")]
    rows, candidates = reconcile(sources)
    assert {row["berry_ids"][0]: len(row["names"]) for row in rows} == {
        "berry-blackberry": 19, "berry-strawberry": 11, "berry-raspberry": 9, "berry-blueberry": 6}
    assert all(not row["accounting_view"]["issues"] for row in rows)
    assert all(not row["company_ids"] and not row.get("published_date") for row in sources)
    named = {(row["candidate_name"], row["berry_id"]): row for row in candidates}
    for code, label, berry in [("APF-77", "Black Magic", "blackberry"),
                              ("ORUS 2240-1", "Sweet Sunrise", "strawberry"),
                              ("ORUS 2262-2", "Charm", "strawberry")]:
        candidate = named[code, "berry-" + berry]
        assert candidate["breeder_code"] == code and candidate["trade_name"] == label
        assert (label, "berry-" + berry) not in named
    assert named["Schwartz", "berry-strawberry"]["trade_name"] == "Puget Summer"
    assert ("Puget Summer", "berry-strawberry") not in named
    assert ("ORUS 2427-4", "berry-blackberry") in named
    assert ("ORUS 1939-4", "berry-blackberry") in named
    assert not {"Eclipse", "Columbia Sunrise"} & {name for name, berry in named}
    assert "WSU" in named["Cascade Bounty", "berry-raspberry"]["portfolio_sources"][0]["portfolio_context"]
    assert "University of Arkansas" in named["Prime-Jan", "berry-blackberry"]["portfolio_sources"][0]["portfolio_context"]
    assert "USPP 22,358" in named["Onyx", "berry-blackberry"]["portfolio_sources"][0]["portfolio_context"]
    for candidate in candidates:
        assert candidate["status"] == "proposed" and not candidate["human_gated"]
        assert not candidate["auto_confirmed"] and not candidate["aliases"]
        assert not candidate["breeder_owner"] and not candidate["proposed_relationships"]
        assert not candidate["deployment"] and not candidate["registration"]["official_registry_source"]
        assert not candidate["registration"]["grant_date"]


def test_original_public_program_grants_enrich_existing_candidates_without_overwriting_human_fields():
    all_sources = load_portfolio_observations(Path(__file__).resolve().parents[1] / "data")
    grants = [row for row in all_sources if row["id"].startswith("portfolio-public-program-grant-")]
    old_sources = [row for row in all_sources if row not in grants]
    _, before = reconcile(old_sources)
    _, after = reconcile(all_sources)
    assert {row["id"] for row in before} == {row["id"] for row in after}
    assert len(grants) == 3 and all(not row["company_ids"] for row in grants)
    expected = {"Onyx": ("USPP22358P2", 3, 6, "2010-02-22", "2011-12-20"),
                "APF-77": ("USPP24249P3", 4, 8, "2011-12-29", "2014-02-18"),
                "Columbia Giant": ("USPP28369P3", 4, 8, "2015-09-28", "2017-09-12")}
    for source_row in grants:
        observation = source_row["names"][0]
        grant, page, column, filed, granted = expected[observation["candidate_name"]]
        capture = source_row["capture_reference"]
        assert capture["visually_reviewed_pages"] == list(range(1, capture["page_count"] + 1))
        assert (capture["claim_page"], capture["claim_column"]) == (page, column)
        assert observation["product_url"].endswith(f"#page={page}")
        assert (observation["grant_number"], observation["application_date"], observation["grant_date"]) == (grant, filed, granted)
        assert capture["non_portfolio_context"] and source_row["accounting"]["observed_items"] == 1
        candidate = next(row for row in after if row["candidate_name"] == observation["candidate_name"]
                         and row["berry_id"] == "berry-blackberry")
        assert not candidate["human_gated"] and not candidate["auto_confirmed"]
        assert not candidate["aliases"] and not candidate["breeder_owner"]
        assert not candidate["proposed_relationships"] and not candidate["deployment"]
        human = deepcopy(candidate)
        human.update(human_gated=True, identity_state="distinct", review_notes="Human identity decision")
        human["registration"] = {**human["registration"], "grant_date": "2000-01-01", "official_registry_source": "https://example.test/human-check"}
        original = deepcopy(human)
        _, refreshed = reconcile(all_sources, candidates=[human])
        retained = next(row for row in refreshed if row["id"] == human["id"])
        assert retained["registration"] == original["registration"] and retained["review_notes"] == original["review_notes"]
        assert human == original
        reference = next(row for row in retained["portfolio_sources"] if row["id"] == source_row["id"])
        assert reference["grant_date"] == granted and reference["grant_number"] == grant
    onyx = next(row for row in grants if row["names"][0]["candidate_name"] == "Onyx")["names"][0]
    assert "ORUS 1523-4" in onyx["portfolio_context"] and "breeder_code" not in onyx and "photos" not in onyx
    assert "ORUS 1350-1" in next(row for row in grants if row["names"][0]["candidate_name"] == "Columbia Giant")["limitations"]


def test_source_plan_prefers_readable_then_partial_then_site_without_erasing_failed_capture(tmp_path):
    folder = tmp_path / "imports/competitor-coverage-registry-2026-09-21"
    folder.mkdir(parents=True)
    (folder / "reconciliation-matrix.json").write_text(json.dumps({"rows": [{
        "input_registry_name": "Alpha", "canonical_entity_ids": ["company-a"],
        "website": "https://example.test/", "resolution_status": "matched"}]}))
    failed = source([], id="failed", url="https://example.test/unreadable.pdf", capture_status="unreadable")
    partial = source([], id="partial", url="https://example.test/partial", capture_status="partial")
    readable = source([], id="readable", url="https://example.test/current")
    original = deepcopy([failed, partial, readable])
    def plan(rows):
        result = portfolio_coverage(data_dir=tmp_path, sources=rows, varieties=[], entities=ENTITIES, candidates=[])
        assert result["sources"][0]["capture_status"] == "unreadable"
        return result["subjects"][0]
    assert plan(original)["starting_url"] == readable["url"]
    assert plan(original[:2])["starting_label"] == "Partial page ↗"
    assert plan(original[:1])["starting_url"] == "https://example.test/"
    assert original == [failed, partial, readable]


def test_real_program_pages_keep_species_clone_scope_and_nursery_roles_explicit():
    sources = load_portfolio_observations(Path(__file__).resolve().parents[1] / "data")
    rows, candidates = reconcile(sources)
    niwa = next(r for r in rows if r["id"] == "portfolio-niwa-varieties")
    black_raspberries = [n for n in niwa["names"] if n["trade_name"] in {"Megan", "Selena"}]
    assert len(black_raspberries) == 2
    assert all(n["berry_id"] == "berry-raspberry" and "release" in n["portfolio_context"] for n in black_raspberries)
    clones = next(r for r in rows if r["id"] == "portfolio-niwa-clones")
    assert len(clones["names"]) == 7 and clones["accounting_view"]["accounted_items"] == 10
    assert len(clones["accounting_view"]["exclusions"]) == 3 and not clones["accounting_view"]["issues"]
    assert not any(c["candidate_name"] in {"NL 180106", "NL 183601", "NL 180122"} for c in candidates)
    shared_code = next(c for c in candidates if c["candidate_name"] == "NR 1849002")
    assert {p["id"] for p in shared_code["portfolio_sources"]} == {"portfolio-niwa-varieties", "portfolio-niwa-clones"}
    assert not shared_code["auto_confirmed"] and not shared_code["human_gated"]
    assert {p["trade_name"] for p in shared_code["portfolio_sources"]} == {"Baron", ""}
    nursery = next(c for c in candidates if c["source_id"] == "portfolio-vissers-strawberry")
    assert nursery["source_tier"] == "tier_2_nursery_catalog" and not nursery["breeder_owner"]
    assert not nursery["proposed_relationships"] and not nursery["deployment"]
    abz = [r for r in rows if r["id"].startswith("portfolio-abz-") and r["capture_status"] == "names_enumerated"]
    assert len(abz) == 9 and sum(len(r["names"]) for r in abz) == 21
    assert all(n["candidate_name"].endswith("F1") and n["product_url"] for r in abz for n in r["names"])
    assert not {"Patio Pleasure", "Home Harvest", "Early & Compact", "Semi-Double"} & {c["candidate_name"] for c in candidates}


def test_visual_pdf_names_keep_photo_codes_separate_and_do_not_approve_traits_or_rights():
    sources = load_portfolio_observations(Path(__file__).resolve().parents[1] / "data")
    observed = next(r for r in sources if r["id"] == "portfolio-uga-blueberry-ornamental-presentation")
    rows, candidates = reconcile([observed])
    assert observed["capture_reference"]["visually_checked_pages"] == observed["capture_reference"]["pages"] == 38
    assert rows[0]["accounting_view"]["accounted_items"] == 12
    assert not rows[0]["accounting_view"]["issues"]
    assert [r["label"] for r in rows[0]["accounting_view"]["exclusions"]] == ["Alapaha"]
    named = {r["candidate_name"]: r for r in candidates}
    assert {"Titan", "T-959", "Premier", "T-460", "T-1223", "TO-1398"} <= named.keys()
    assert named["Titan"]["id"] != named["T-959"]["id"]
    assert named["TO-1398"]["trade_name"] == "Gold Rush"
    assert "Alapaha" not in named and "Gold Rush" not in named
    assert "#page=20" in named["Premier"]["portfolio_sources"][0]["product_url"]
    for candidate in candidates:
        assert candidate["status"] == "proposed" and not candidate["human_gated"]
        assert not candidate["auto_confirmed"] and not candidate["aliases"]
        assert not candidate["breeder_owner"] and not candidate["deployment"]
        assert not candidate["proposed_relationships"]
        assert not candidate["registration"]["official_registry_source"]
        assert not candidate["registration"]["grant_date"]
        assert candidate["source_tier"] == "tier_3_conference"


def test_nonregistry_portfolio_references_never_become_official_registration_and_stored_rows_win():
    sources = [source([{"candidate_name": "Earlier", "berry_id": "berry-strawberry"}]),
               source([{"candidate_name": "New", "berry_id": "berry-strawberry"}], id="portfolio-new")]
    stored = {"id": "stored", "candidate_name": "Earlier", "berry_id": "berry-strawberry",
              "status": "reviewed", "human_gated": True, "identity_state": "distinct",
              "source_tier": "tier_1_registry", "registration": {"official_registry_source": "verified-registry"}}
    original = deepcopy(stored)
    _, candidates = reconcile(sources, candidates=[stored])
    earlier = next(c for c in candidates if c["id"] == "stored")
    new = next(c for c in candidates if c["candidate_name"] == "New")
    assert earlier["registration"] == original["registration"] and stored == original
    assert new["source_id"] == "portfolio-new" and not new["registration"]["official_registry_source"]
    assert new["source_tier"] == "tier_1_breeder_catalog"


def test_real_mixed_catalog_accounting_preserves_exclusions_and_uncertain_pairs():
    sources = load_portfolio_observations(Path(__file__).resolve().parents[1] / "data")
    rows, candidates = reconcile(sources)
    us = next(r for r in rows if r["id"] == "portfolio-planasa-us-products")
    es = next(r for r in rows if r["id"] == "portfolio-planasa-es-products")
    assert us["accounting_view"]["accounted_items"] == 53 and len(us["names"]) == 38
    assert es["accounting_view"]["accounted_items"] == 54 and len(es["names"]) == 38
    assert not us["accounting_view"]["issues"] and not es["accounting_view"]["issues"]
    assert {r["label"] for r in us["accounting_view"]["exclusions"]} >= {"Darbella", "Darzilla", "White Endive", "Garpek"}
    assert any(r["label"] == "Demoiselle" and "Species" in r["reason"] for r in es["accounting_view"]["exclusions"])
    assert not any(c.get("trade_name") in {"Darbella", "Darzilla", "Demoiselle"} for c in candidates)
    rainier = next(n for n in us["names"] if n["trade_name"] == "Black Rainier")
    assert any("Plablack 1737" in message for message in rainier["identity_notes"])
    assert any("Black Sultana" in message for message in rainier["identity_notes"])


def test_conflicting_pairs_do_not_get_automatic_catalog_match_but_human_decision_wins():
    names = [{"candidate_name": "CODE-1", "denomination": "CODE-1", "trade_name": label, "berry_id": "berry-strawberry"}
             for label in ("First", "Second")]
    varieties = [{"id": "v1", "name": "CODE-1", "entity_type": "variety", "berry_ids": ["berry-strawberry"]}]
    rows, candidates = reconcile([source(names)], varieties)
    assert rows[0]["matched"] == 0 and len(candidates) == 1
    assert len(candidates[0]["portfolio_sources"]) == 2 and candidates[0]["portfolio_identity_notes"]
    human = {**candidates[0], "human_gated": True, "identity_state": "confirmed_same", "candidate_canonical_match": "v1"}
    rows, candidates = reconcile([source(names)], varieties, [human])
    assert rows[0]["matched"] == 2 and candidates[0]["human_gated"]


def test_accounting_shortfall_is_visible_and_mixed_berry_filter_is_honest(tmp_path):
    names = [{"candidate_name": "Straw", "berry_id": "berry-strawberry"},
             {"candidate_name": "Blue", "berry_id": "berry-blueberry"}]
    mixed = source(names, berry_ids=["berry-strawberry", "berry-blueberry"],
                   accounting={"observed_items": 3, "reported_items": 5, "exclusions": []})
    result = portfolio_coverage(data_dir=tmp_path, sources=[mixed], varieties=[], entities=ENTITIES, candidates=[],
                                filters={"berry": "berry-blueberry"})
    assert result["summary"]["names"] == 1 and result["summary"]["needs_review"] == 1
    assert [r["candidate_name"] for r in result["sources"][0]["names"]] == ["Blue"]
    assert result["sources"][0]["accounting_view"]["accounted_items"] == 2
    assert len(result["sources"][0]["accounting_view"]["issues"]) == 2


@pytest.mark.parametrize("payload", [[], {"kind": "unreviewed_portfolio_name_observations", "sources": [1]},
    {"kind": "unreviewed_portfolio_name_observations", "sources": [source([1])]},
    {"kind": "unreviewed_portfolio_name_observations", "sources": [source([], accounting={"observed_items": True, "exclusions": []})]},
    {"kind": "unreviewed_portfolio_name_observations", "sources": [source([], accounting={"observed_items": 1, "exclusions": [{"label": "Apple"}]})]}])
def test_malformed_observation_shapes_raise_the_recoverable_validation_error(tmp_path, payload):
    folder = tmp_path / "imports/variety-portfolio-observations-bad"
    folder.mkdir(parents=True)
    (folder / "observations.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_portfolio_observations(tmp_path)


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
