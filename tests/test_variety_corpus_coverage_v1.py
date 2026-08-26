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
    assert "Trusted Varieties:" in page.text
    assert "Discovered Candidates:" in page.text
    assert "Unresolved identities:" in page.text
    assert "Last Call" in page.text
    assert 'id="variety-variety-roberto"' not in page.text
    assert "not a completeness score" in page.text.lower()


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
    assert "Trusted Varieties" in page.text
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
