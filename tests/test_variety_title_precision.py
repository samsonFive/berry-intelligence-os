"""Observed title mistakes plus explicit positive controls, never model qualification."""
from copy import deepcopy
import json
from pathlib import Path

from scripts.audit_variety_name_recall import audit
from app.services.variety_universe.corpus_discovery import (
    build_discovered_candidates, discover_corpus_variety_mentions, merge_visible_candidates,
)
from app.services.variety_universe.candidates import (
    apply_identity_decision, load_variety_candidates, persist_variety_candidates,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "benchmarks/variety-title-precision-v1.json"


def test_targeted_title_diagnostic_removes_prose_without_hiding_the_f1_miss():
    before = FIXTURE.read_bytes()
    report = audit(FIXTURE)
    summary = report["summary"]
    assert summary["cases"] == 14 and summary["cases_passed"] == 13
    assert summary["expected_name_occurrences"] == 6
    assert summary["fully_correct_name_occurrences"] == 5
    assert summary["unexpected_name_occurrences"] == 0
    cases = {case["id"]: case for case in report["cases"]}
    assert not cases["f1-launch"]["passed"]
    assert cases["f1-launch"]["errors"] == {"name_missing": 1}
    assert cases["f1-launch"]["exclusions"][0]["reason"] == "parentage_or_selection_code"
    assert cases["capitalized-new-is-name"]["passed"]
    assert FIXTURE.read_bytes() == before


def test_original_recall_diagnostic_retains_all_unsupported_cases():
    summary = audit(ROOT / "benchmarks/variety-name-recall-v1.json")["summary"]
    assert summary["cases"] == 24 and summary["expected_name_occurrences"] == 64
    assert summary["detected_name_occurrences"] == 50
    assert summary["missed_name_occurrences"] == 14
    assert summary["unexpected_name_occurrences"] == 0


def test_real_blugenix_summary_retains_the_five_names_without_a_brand_phrase_candidate():
    source = json.loads((ROOT / "data/evidence/ev-producereport-blugenix-2026.json").read_text(encoding="utf-8"))
    before = deepcopy(source)
    result = discover_corpus_variety_mentions(varieties=[], entities=[], facts=[], published_evidence=[source])
    names = {row["candidate_name"] for row in result["mentions"]}
    assert {"Bounty", "Breeze", "Cascade", "Delight", "Eterna"} <= names
    assert "BluGenix with five" not in names
    assert all(row["source_url"] == source["source_url"] for row in result["mentions"])
    assert source == before


def test_old_private_review_is_preserved_when_transient_title_detection_disappears(tmp_path):
    source = next(case["inputs"]["evidence"][0] for case in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
                  if "Cornell releases two new" in case["inputs"]["evidence"][0]["title"])
    old = apply_identity_decision({"id": "vcand-old-title-fixture", "record_type": "variety_candidate",
        "candidate_name": "two new", "berry_id": "berry-raspberry", "source_url": source["source_url"],
        "knowledge": {"operator_annotation": "Keep source history"}},
        decision="unknown", reviewer="fictional-reviewer", notes="Fictional historical private decision")
    path, = persist_variety_candidates([old], inbox_dir=tmp_path)
    before = path.read_bytes()
    saved = load_variety_candidates(tmp_path)
    result = build_discovered_candidates(varieties=[], entities=[], facts=[], published_evidence=[source], existing_candidates=saved)
    assert result["mentions"] == [] and result["candidates"] == []
    assert merge_visible_candidates(saved, result["candidates"], report=result) == saved
    assert path.read_bytes() == before


def test_explicit_title_species_overrides_wrong_source_tag_without_roles_or_facts():
    source = {"id": "ev-title-species", "status": "published", "source_type": "trade_press",
              "title": "Example introduces Nova Blue blueberry variety", "summary": "",
              "source_url": "https://example.test/title?original=1", "berry_ids": ["berry-raspberry"]}
    result = discover_corpus_variety_mentions(varieties=[], entities=[], facts=[], published_evidence=[source])
    row, = result["mentions"]
    assert row["candidate_name"] == "Nova Blue" and row["berry_id"] == "berry-blueberry"
    assert row["source_url"] == source["source_url"] and row["evidence_ids"] == [source["id"]]
    assert row.get("canonical_variety_id") is None
