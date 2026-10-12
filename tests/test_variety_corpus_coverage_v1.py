"""Corpus → Variety universe coverage: explicit cultivar identities become candidates."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.variety_universe.candidates import load_variety_candidates, persist_variety_candidates
from app.services.variety_universe.corpus_discovery import (
    build_discovered_candidates,
    discover_corpus_variety_mentions,
    merge_visible_candidates,
)
from app.services.variety_universe.coverage import coverage_matrix, universe_headcounts
from app.services.variety_universe.registry_import import build_candidate, import_registry_rows, load_registry_rows


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "imports"
    / "variety-universe-eu-uk-sa-v1"
    / "registry_rows.json"
)


def _varieties() -> list[dict]:
    return [e for e in main.all_entities() if e.get("entity_type") == "variety"]


def _corpus(extra_evidence=None, extra_facts=None):
    evidence = list(main.published_evidence()) + list(extra_evidence or [])
    facts = list(main.all_facts()) + list(extra_facts or [])
    entities = list(main.all_entities())
    return _varieties(), entities, evidence, facts


def _adelita_records() -> tuple[dict, dict]:
    evidence = {
        "id": "ev-test-adelita-pbr",
        "record_type": "evidence",
        "status": "published",
        "source_type": "plant_breeders_rights_record",
        "title": "Canada PBR strawberry register — cultivar 'Adelita'",
        "source_name": "Canadian Food Inspection Agency",
        "source_id": "source-cfia-strawberry-index",
        "source_url": "https://example.test/cfia/strawberry/adelita",
        "published_date": "2016-06-01",
        "captured_date": "2026-08-25",
        "summary": "The strawberry cultivar 'Adelita' is listed on the Canadian plant breeders' rights strawberry register index. Applicant Planasa.",
        "berry_ids": ["berry-strawberry"],
        "entity_ids": ["company-planasa"],
        "tags": ["registry", "cultivar-registry"],
    }
    fact = {
        "id": "fact-test-adelita-denomination",
        "record_type": "fact",
        "statement": "The Canadian plant breeders' rights strawberry register index lists the strawberry cultivar 'Adelita', applicant Planasa.",
        "classification": "fact",
        "confidence": "high",
        "status": "active",
        "reviewer": "test",
        "created_at": "2026-08-25",
        "evidence_ids": ["ev-test-adelita-pbr"],
        "entity_ids": ["company-planasa"],
    }
    return evidence, fact


def test_roberto_is_explicit_in_cfia_index_but_not_canonical() -> None:
    varieties, entities, evidence, facts = _corpus()
    names = {e["name"] for e in varieties}
    aliases = {alias for e in varieties for alias in (e.get("aliases") or [])}
    assert "Roberto" not in names
    assert "Roberto" not in aliases
    fact = next(row for row in facts if row["id"] == "fact-cfia-driscolls-21-denominations")
    evidence_row = next(row for row in evidence if row["id"] == "ev-cfia-blueberry-index")
    assert "Roberto" in fact["statement"]
    assert "Roberto" in evidence_row["summary"]
    assert "variety-roberto" not in (fact.get("entity_ids") or [])
    assert "variety-roberto" not in (evidence_row.get("entity_ids") or [])
    report = discover_corpus_variety_mentions(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    roberto = next(m for m in report["mentions"] if m["candidate_name"] == "Roberto")
    assert roberto["berry_id"] == "berry-blueberry"
    assert roberto["disposition"] == "new_candidate"
    assert "ev-cfia-blueberry-index" in roberto["evidence_ids"]
    assert "fact-cfia-driscolls-21-denominations" in roberto["fact_ids"]
    assert roberto["breeder_owner"]


def test_adelita_fixture_becomes_strawberry_candidate() -> None:
    evidence, fact = _adelita_records()
    varieties, entities, published, facts = _corpus([evidence], [fact])
    names = {e["name"] for e in varieties}
    assert "Adelita" not in names
    report = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=published,
        facts=facts,
        existing_candidates=[],
    )
    adelita = next(row for row in report["candidates"] if row["candidate_name"] == "Adelita")
    assert adelita["berry_id"] == "berry-strawberry"
    assert adelita["identity_state"] == "distinct"
    assert adelita["auto_confirmed"] is False
    assert adelita["source_url"] == "https://example.test/cfia/strawberry/adelita"


def test_explicit_variety_mention_already_canonical_is_not_a_new_candidate() -> None:
    varieties, entities, evidence, facts = _corpus()
    trusted_before = {e["id"] for e in varieties}
    report = discover_corpus_variety_mentions(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    kimberley = next(m for m in report["already_canonical"] if m["candidate_name"] == "Kimberley")
    assert kimberley["canonical_variety_id"] == "variety-drisbluetwentyone"
    assert not any(m["candidate_name"] == "Kimberley" for m in report["new_mentions"])
    built = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    assert not any(row["candidate_name"] == "Kimberley" for row in built["candidates"])
    assert {e["id"] for e in _varieties()} == trusted_before


def test_explicit_variety_mention_already_candidate_is_not_duplicated(tmp_path: Path) -> None:
    varieties, entities, evidence, facts = _corpus()
    existing = [
        build_candidate(
            {
                "candidate_name": "Roberto",
                "berry_id": "berry-blueberry",
                "source_id": "ev-cfia-blueberry-index",
                "source_url": "https://active.inspection.gc.ca/english/plaveg/pbrpov/cropreport/ble.shtml",
                "source_tier": "tier_1_registry",
            },
            varieties=varieties,
        )
    ]
    persist_variety_candidates(existing, inbox_dir=tmp_path / "inbox")
    loaded = load_variety_candidates(tmp_path / "inbox")
    report = discover_corpus_variety_mentions(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=loaded,
    )
    assert any(m["candidate_name"] == "Roberto" and m["disposition"] == "already_candidate" for m in report["mentions"])
    built = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=loaded,
    )
    assert not any(row["candidate_name"] == "Roberto" for row in built["candidates"])


def test_explicit_new_variety_mention_is_distinct() -> None:
    extra = {
        "id": "ev-test-new-cultivar",
        "status": "published",
        "source_type": "government_registry",
        "title": "National register — blueberry cultivar 'NovaPrime'",
        "source_name": "Test Registry",
        "source_id": "source-test-registry",
        "source_url": "https://example.test/novaprime",
        "summary": "The blueberry cultivar 'NovaPrime' is entered on the national register.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "tags": ["registry"],
    }
    fact = {
        "id": "fact-test-novaprime",
        "statement": "The blueberry cultivar 'NovaPrime' is entered on the national register.",
        "classification": "fact",
        "confidence": "high",
        "status": "active",
        "reviewer": "test",
        "created_at": "2026-08-25",
        "evidence_ids": ["ev-test-new-cultivar"],
        "entity_ids": [],
    }
    varieties, entities, evidence, facts = _corpus([extra], [fact])
    report = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    row = next(c for c in report["candidates"] if c["candidate_name"] == "NovaPrime")
    assert row["identity_state"] == "distinct"
    assert row["candidate_canonical_match"] is None


def test_ambiguous_alias_stays_unresolved() -> None:
    extra = {
        "id": "ev-test-ambiguous-last-call",
        "status": "published",
        "source_type": "plant_breeders_rights_record",
        "title": "Trial note",
        "source_name": "CPVO",
        "source_id": "source-cpvo-public-register",
        "source_url": "https://example.test/last-call-trial",
        "summary": "The blueberry cultivar 'Fall Creek Last Call Selection Trial 11' was observed.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "tags": ["registry"],
    }
    fact = {
        "id": "fact-test-ambiguous-last-call",
        "statement": "The blueberry cultivar 'Fall Creek Last Call Selection Trial 11' was observed in the trial.",
        "classification": "fact",
        "confidence": "high",
        "status": "active",
        "reviewer": "test",
        "created_at": "2026-08-25",
        "evidence_ids": ["ev-test-ambiguous-last-call"],
        "entity_ids": [],
    }
    varieties, entities, evidence, facts = _corpus([extra], [fact])
    report = discover_corpus_variety_mentions(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    mention = next(m for m in report["mentions"] if "Last Call" in m["candidate_name"])
    assert mention["disposition"] == "unresolved"
    assert mention["identity_state"] == "unknown"


def test_non_variety_capitalized_term_not_promoted() -> None:
    extra = {
        "id": "ev-test-california-pbr",
        "status": "published",
        "source_type": "plant_breeders_rights_record",
        "title": "California examination site",
        "source_name": "CFIA",
        "source_id": "source-cfia",
        "source_url": "https://example.test/california",
        "summary": "The trial was conducted in California. No cultivar denomination is listed here.",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": ["geography-united-states"],
        "tags": ["registry"],
    }
    varieties, entities, evidence, facts = _corpus([extra], [])
    report = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    names = {row["candidate_name"] for row in report["candidates"]}
    assert "California" not in names


def test_berry_mismatch_is_not_folded_into_canonical() -> None:
    extra = {
        "id": "ev-test-last-call-strawberry",
        "status": "published",
        "source_type": "plant_breeders_rights_record",
        "title": "Strawberry cultivar 'Last Call'",
        "source_name": "CPVO",
        "source_id": "source-cpvo-public-register",
        "source_url": "https://example.test/last-call-strawberry",
        "summary": "The strawberry cultivar 'Last Call' appears on a strawberry register.",
        "berry_ids": ["berry-strawberry"],
        "entity_ids": [],
        "tags": ["registry"],
    }
    fact = {
        "id": "fact-test-last-call-strawberry",
        "statement": "The strawberry cultivar 'Last Call' appears on a strawberry register.",
        "classification": "fact",
        "confidence": "high",
        "status": "active",
        "reviewer": "test",
        "created_at": "2026-08-25",
        "evidence_ids": ["ev-test-last-call-strawberry"],
        "entity_ids": [],
    }
    varieties, entities, evidence, facts = _corpus([extra], [fact])
    report = discover_corpus_variety_mentions(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    mention = next(m for m in report["mentions"] if m["candidate_name"] == "Last Call" and m.get("berry_id") == "berry-strawberry")
    assert mention["disposition"] == "berry_mismatch"
    built = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    assert not any(
        row["candidate_name"] == "Last Call" and row.get("berry_id") == "berry-strawberry"
        for row in built["candidates"]
    )


def test_source_provenance_required_and_candidate_only_persistence(tmp_path: Path) -> None:
    trusted_before = {path.name for path in Path(main.DATA_DIR, "entities", "varieties").glob("*.json")}
    varieties, entities, evidence, facts = _corpus()
    report = build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    assert report["candidates"]
    assert all(row.get("source_id") or row.get("source_url") for row in report["candidates"])
    written = persist_variety_candidates(report["candidates"], inbox_dir=tmp_path / "inbox")
    assert written
    after = {path.name for path in Path(main.DATA_DIR, "entities", "varieties").glob("*.json")}
    assert after == trusted_before
    inbox_names = {row["candidate_name"] for row in load_variety_candidates(tmp_path / "inbox")}
    assert "Roberto" in inbox_names
    assert "variety-roberto.json" not in after


def test_no_trusted_variety_mutation_from_discovery() -> None:
    before = [e for e in _varieties()]
    varieties, entities, evidence, facts = _corpus()
    build_discovered_candidates(
        varieties=varieties,
        entities=entities,
        published_evidence=evidence,
        facts=facts,
        existing_candidates=[],
    )
    after = [e for e in _varieties()]
    assert after == before


def test_get_does_not_persist_corpus_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
    page = TestClient(app).get("/varieties/candidates")
    assert page.status_code == 200
    assert "Roberto" in page.text
    assert "Candidate (untrusted)" in page.text
    assert list((tmp_path / "inbox" / "variety_candidates").glob("*.json")) == []


def test_variety_index_keeps_canonical_list_and_shows_universe_counts() -> None:
    page = TestClient(app).get("/entities/variety")
    assert page.status_code == 200
    assert "catalog varieties" in page.text
    assert "candidates" in page.text
    assert "unresolved identities" in page.text
    assert "Last Call" in page.text
    assert 'id="variety-variety-roberto"' not in page.text
    assert "not completeness or market share" in page.text.lower()


def test_coverage_counts_include_corpus_candidates() -> None:
    varieties, visible, report = main.variety_candidate_universe()
    matrix = coverage_matrix(
        varieties=varieties,
        entities=main.all_entities(),
        relationships=main.all_relationships(),
        published_evidence=main.published_evidence(),
        facts=main.all_facts(),
        candidates=visible,
    )
    heads = universe_headcounts(varieties=varieties, candidates=visible)
    assert heads["trusted_varieties"] == len(varieties)
    assert heads["discovered_candidates"] >= 1
    assert matrix["universe"]["discovered_candidates"] == heads["discovered_candidates"]
    assert report["mention_count"] >= 1
    assert any(m["candidate_name"] == "Roberto" for m in report["new_mentions"])
    page = TestClient(app).get("/varieties/coverage")
    assert page.status_code == 200
    assert "Catalog varieties" in page.text
    assert "Catalog entries include active, unverified and historical records" in page.text
    assert "Trusted Varieties" not in page.text
    assert "Corpus reconciliation" in page.text
    assert "completeness score" in page.text.lower()


def test_candidates_page_forbidden_when_not_authoring(monkeypatch) -> None:
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    page = TestClient(app).get("/varieties/candidates")
    assert page.status_code == 403


def test_merge_visible_does_not_overwrite_human_inbox_row() -> None:
    inbox = [
        {
            "id": "vcand-human",
            "candidate_name": "Roberto",
            "berry_id": "berry-blueberry",
            "identity_state": "distinct",
            "status": "reviewed",
            "reviewer": "analyst",
        }
    ]
    discovered = [
        {
            "id": "vcand-discovered",
            "candidate_name": "Roberto",
            "berry_id": "berry-blueberry",
            "identity_state": "distinct",
            "status": "proposed",
        }
    ]
    merged = merge_visible_candidates(inbox, discovered)
    assert len(merged) == 1
    assert merged[0]["id"] == "vcand-human"
    assert merged[0]["reviewer"] == "analyst"


def test_registry_import_still_does_not_write_canonical(tmp_path: Path) -> None:
    before = {e["id"] for e in _varieties()}
    import_registry_rows(load_registry_rows(FIXTURE), varieties=_varieties(), inbox_dir=tmp_path / "inbox")
    assert {e["id"] for e in _varieties()} == before


def test_hortifrut_and_mbg_portfolios_are_captured_without_role_approval():
    varieties, entities, evidence, facts = _corpus()
    report = build_discovered_candidates(varieties=varieties, entities=entities, published_evidence=evidence, facts=facts)
    hort = {m["candidate_name"]: m for m in report["mentions"] if "ev-hortifrut-genetic-development" in m["evidence_ids"]}
    assert set(hort) >= {"Prelude", "Daybreak", "Stellar", "Candycrunch", "Apolo", "Bliss", "Temptation", "Robust", "Envy", "Keepsake", "Sensation", "Rocio", "Corona", "Draper", "Aurora", "Liberty", "Osorno"}
    assert hort["Keepsake"]["canonical_variety_id"] == "variety-keepsake"
    mbg = [m for m in report["mentions"] if "ev-mbg-berry-blue-varieties" in m["evidence_ids"]]
    assert len(mbg) == 16
    assert next(m for m in mbg if m["candidate_name"] == "Daybreak")["breeder_code"] == "BB07-210FL-18"
    prelude = next(c for c in report["candidates"] if c["candidate_name"] == "Prelude")
    assert prelude["source_tier"] == "tier_1_breeder_catalog"
    assert not prelude["proposed_relationships"] and not prelude["auto_confirmed"]
    assert {"ev-hortifrut-genetic-development", "ev-mbg-berry-blue-varieties"} <= set(prelude["knowledge"]["evidence_ids"])


def test_explicit_summary_lists_respect_species_and_ignore_generic_prose():
    source = {"id": "ev-list", "status": "published", "source_type": "trade_press", "source_url": "https://example.test",
              "berry_ids": ["berry-blueberry", "berry-raspberry"],
              "summary": "Blueberry varieties including 'Azure', Daybreak and Prelude, lists test stations in Chile and Peru. Raspberry varieties: Ruby and Pacific Star. Companies including Acme and Beta are present."}
    canonical = [{"id": "variety-a", "name": "Azure", "aliases": ["Azure Blue"], "berry_ids": ["berry-blueberry"]}]
    r = build_discovered_candidates(varieties=canonical, entities=[], published_evidence=[source], facts=[])
    assert {(m["candidate_name"], m["berry_id"]) for m in r["mentions"]} == {
        ("Azure", "berry-blueberry"), ("Daybreak", "berry-blueberry"), ("Prelude", "berry-blueberry"),
        ("Ruby", "berry-raspberry"), ("Pacific Star", "berry-raspberry")}
    assert next(m for m in r["mentions"] if m["candidate_name"] == "Azure")["disposition"] == "already_canonical"
    assert all(c["source_tier"] != "tier_1_registry" for c in r["candidates"])
    source["status"] = "draft"
    assert not build_discovered_candidates(varieties=[], entities=[], published_evidence=[source], facts=[])["mentions"]


def test_rejected_name_is_not_resurrected_and_source_changes_remove_discovery():
    source = {"id": "ev-list", "status": "published", "berry_ids": ["berry-blueberry"], "summary": "Blueberry varieties including Prelude and Daybreak."}
    existing = [{"id": "vcand-human", "candidate_name": "Prelude", "berry_id": "berry-blueberry", "status": "rejected", "identity_state": "rejected", "reviewer": "operator"}]
    r = build_discovered_candidates(varieties=[], entities=[], published_evidence=[source], facts=[], existing_candidates=existing)
    assert [c["candidate_name"] for c in r["candidates"]] == ["Daybreak"]
    merged = merge_visible_candidates(existing, r["candidates"] + [{**existing[0], "id": "another-id", "status": "proposed"}])
    assert len(merged) == 2 and merged[0] == existing[0]
    source["summary"] = "Blueberry breeding stations in Chile and Peru."
    assert not build_discovered_candidates(varieties=[], entities=[], published_evidence=[source], facts=[])["candidates"]


def test_ambiguous_exact_alias_does_not_pick_first_catalog_identity():
    varieties = [{"id": key, "name": key, "aliases": ["Shared"], "berry_ids": ["berry-blueberry"]} for key in ["variety-one", "variety-two"]]
    r = discover_corpus_variety_mentions(varieties=varieties, entities=[], published_evidence=[{
        "id": "ev-list", "status": "published", "berry_ids": ["berry-blueberry"], "summary": "Blueberry varieties including Shared."}], facts=[])
    assert not r["already_canonical"]
    assert r["mentions"][0]["disposition"] == "possible_alias"


def test_summary_names_preserve_plus_and_separate_codes_from_names():
    sources = [
        {"id": "ev-types", "status": "published", "berry_ids": ["berry-strawberry"], "summary": "Strawberry varieties such as June-bearing, everbearing and day-neutral types."},
        {"id": "ev-names", "status": "published", "berry_ids": ["berry-blueberry"], "summary": "Blueberry varieties including Abril Blue+, ArabellaBlue FC14-062 and FCM14-057."},
    ]
    r = build_discovered_candidates(varieties=[], entities=[], published_evidence=sources, facts=[])
    assert {c["candidate_name"] for c in r["candidates"]} == {"Abril Blue+", "ArabellaBlue", "FCM14-057"}
    assert next(c for c in r["candidates"] if c["candidate_name"] == "ArabellaBlue")["breeder_code"] == "FC14-062"


def test_directory_search_and_source_queue_surface_missing_portfolio_names(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    client = TestClient(app)
    page = client.get("/entities/variety?q=Prelude&berry=berry-blueberry")
    assert page.status_code == 200
    assert "additional names awaiting catalog review" in page.text and "Prelude" in page.text
    assert 'id="variety-variety-prelude"' not in page.text
    queue = client.get("/varieties/candidates?source=ev-hortifrut-genetic-development&berry=berry-blueberry")
    assert queue.status_code == 200
    assert "Prelude" in queue.text and "Sensation" in queue.text
    assert "Source context, not an approved breeder or owner relationship" in queue.text
    assert not (tmp_path / "inbox" / "variety_candidates").exists()


def test_explicit_names_keep_accents_and_license_lists_are_context_bounded():
    source = {"id": "ev-list", "status": "published", "berry_ids": ["berry-blueberry"],
              "summary": "Blueberry varieties including María and Étoile. The company licenses 'Rocio' and 'Corona' from another programme."}
    r = build_discovered_candidates(varieties=[], entities=[], published_evidence=[source], facts=[])
    assert {c["candidate_name"] for c in r["candidates"]} == {"María", "Étoile", "Rocio", "Corona"}
    assert all(not c["proposed_relationships"] for c in r["candidates"])
    source["summary"] = "The company licenses 'Brand Name' for its packaging."
    assert not build_discovered_candidates(varieties=[], entities=[], published_evidence=[source], facts=[])["candidates"]


def test_previously_imported_name_gains_readonly_source_context_without_editing_decision():
    from copy import deepcopy
    from app.services.variety_navigation import candidate_queue
    inbox = [{"id": "vcand-human", "candidate_name": "Prelude", "berry_id": "berry-blueberry", "status": "reviewed",
              "identity_state": "distinct", "reviewer": "operator", "review_notes": "Keep my spelling", "knowledge": {"origin": "photo", "evidence_ids": []}}]
    before = deepcopy(inbox)
    source = {"id": "ev-list", "status": "published", "berry_ids": ["berry-blueberry"], "summary": "Blueberry varieties including Prelude."}
    report = build_discovered_candidates(varieties=[], entities=[], published_evidence=[source], facts=[], existing_candidates=inbox)
    visible = merge_visible_candidates(inbox, report["candidates"], report=report)
    assert inbox == before and visible[0]["knowledge"] == before[0]["knowledge"]
    assert visible[0]["reviewer"] == "operator" and visible[0]["review_notes"] == "Keep my spelling"
    assert visible[0]["corpus_evidence_ids"] == ["ev-list"]
    assert candidate_queue(visible, {"source": "ev-list"})["candidates"] == visible
