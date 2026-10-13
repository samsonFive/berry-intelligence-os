"""Recall diagnostics expose failures; passing tests do not qualify extraction."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("variety_name_recall_audit", ROOT / "scripts/audit_variety_name_recall.py")
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def case():
    return {"id": "score-control", "format": "identity", "language": "en", "fixture_kind": "synthetic_control",
            "inputs": {"evidence": []}, "expected": [{"name": "Test Name", "berry_id": "berry-raspberry",
            "breeder_code": "NR 1849002", "disposition": "possible_alias", "canonical_variety_id": None,
            "evidence_ids": ["ev-a", "ev-b"], "source_url": "https://example.test/a?ver=1"}]}


def fake(rows, exclusions=None):
    def discover(**kwargs):
        # Mutating the scorer's input must not mutate the caller fixture.
        kwargs["published_evidence"].append({"id": "fake"})
        return {"mentions": rows, "exclusions": exclusions or []}
    return discover


def test_scorer_keeps_species_code_identity_and_provenance_errors_separate():
    fixture = case()
    before = deepcopy(fixture)
    row = {"candidate_name": "Test Name", "berry_id": "berry-blackberry", "breeder_code": "NR 999",
           "disposition": "already_canonical", "canonical_variety_id": "variety-wrong", "evidence_ids": ["ev-a"],
           "source_url": "https://example.test/a"}
    result = audit_module.score_case(fixture, discover=fake([row]))
    assert fixture == before
    assert result["detected_names"] == 1 and result["fully_correct_names"] == 0
    assert result["errors"] == {key: 1 for key in ["wrong_berry", "wrong_or_missing_code", "wrong_disposition",
        "wrong_catalog_link", "missing_source_reference", "changed_or_missing_source_url"]}


def test_scorer_exposes_misses_unexpected_names_and_missing_exclusions():
    fixture = case()
    fixture["required_exclusion_reasons"] = ["berry_not_established"]
    result = audit_module.score_case(fixture, discover=fake([{"candidate_name": "Not A Cultivar", "berry_id": "berry-raspberry"}]))
    assert result["errors"] == {"name_missing": 1, "unexpected_name": 1, "missing_exclusion": 1}
    total = audit_module.aggregate([result])
    assert total["name_recall"] == 0 and total["name_precision"] == 0
    empty = audit_module.aggregate([])
    assert empty["name_recall"] is None and empty["name_precision"] is None


def test_correct_detection_does_not_hide_an_extra_species_assignment():
    fixture = case()
    expected = fixture["expected"][0]
    correct = {"candidate_name": expected["name"], **{key: value for key, value in expected.items() if key != "name"}}
    wrong = {**correct, "berry_id": "berry-blackberry"}
    result = audit_module.score_case(fixture, discover=fake([correct, wrong]))
    assert result["fully_correct_names"] == 1
    assert not result["passed"] and result["errors"] == {"unexpected_berry_assignment": 1}


def test_curated_fixture_retains_all_crops_and_known_unsupported_formats():
    fixture = json.loads(audit_module.DEFAULT_FIXTURE.read_text(encoding="utf-8"))
    assert len(fixture["cases"]) == 24
    assert "not independently human-verified" in fixture["review_status"]
    assert {row["berry_id"] for item in fixture["cases"] for row in item["expected"]} == {
        "berry-blueberry", "berry-strawberry", "berry-raspberry", "berry-blackberry"}
    result = audit_module.audit()
    assert sum(row["expected_name_occurrences"] for row in result["by_berry"].values()) == 64
    assert sum(row["detected_name_occurrences"] for row in result["by_berry"].values()) == result["summary"]["detected_name_occurrences"]
    cases = {row["id"]: row for row in result["cases"]}
    for key in ("hortifrut-eleven", "niwa-codes", "abz-f1-labels", "niwa-black-raspberry", "code-two-sources"):
        assert cases[key]["passed"], cases[key]
    # A failed diagnostic is an honest gap, not a pytest failure or qualification.
    for key in ("mixed-table", "spanish-list", "polish-list"):
        assert cases[key]["passed"], cases[key]
    assert not cases["body-only"]["passed"] and cases["body-only"]["errors"]["name_missing"] == 4
    assert cases["ambiguous-alias"]["unresolved_names"] == 1
    assert all(cases[key]["passed"] for key in ("generic-types", "geography-list", "brand-only", "mixed-untyped", "unpublished"))


def test_fixture_schema_and_duplicate_id_are_rejected(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps({"schema_version": "unknown"}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        audit_module.audit(path)
    path.write_text(json.dumps({"schema_version": "variety-name-recall-v1", "cases": [case(), case()]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        audit_module.audit(path)


def test_cli_refuses_canonical_or_fixture_overwrite():
    before = audit_module.DEFAULT_FIXTURE.read_bytes()
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/audit_variety_name_recall.py"),
        "--output", str(audit_module.DEFAULT_FIXTURE)], cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode != 0 and "never data/ or benchmarks/" in completed.stderr
    assert audit_module.DEFAULT_FIXTURE.read_bytes() == before


def test_long_name_limit_never_emits_a_truncated_identity():
    from app.services.variety_universe.corpus_discovery import discover_corpus_variety_mentions
    result = discover_corpus_variety_mentions(varieties=[], entities=[], facts=[], published_evidence=[{
        "id": "ev-long", "status": "published", "berry_ids": ["berry-strawberry"],
        "summary": "Strawberry varieties include One Two Three Four Five Six Seven Eight Nine Ten."}])
    assert result["mentions"] == []


def article_case():
    source = {"id": "ev-recall-article", "status": "in_review",
              "source_url": "https://example.test/profile?original=1", "summary": "A cultivar profile.",
              "berry_ids": ["berry-raspberry"], "article": {
                  "title": "Fictional blueberry profile",
                  "paragraphs": [{"text": "Cultivar name: Fictional Field (selection code FL 123)"}]}}
    return {"id": "explicit-article", "format": "article_profile_field", "language": "en",
            "fixture_kind": "synthetic_control", "inputs": {"evidence": [], "source_text_records": [source]},
            "expected": [{"name": "Fictional Field", "berry_id": "berry-blueberry", "breeder_code": "FL 123",
                          "evidence_ids": [source["id"]], "source_url": source["source_url"]}]}


def test_explicit_supported_article_is_scored_with_unreviewed_source_provenance():
    fixture = article_case()
    before = deepcopy(fixture)
    result = audit_module.score_case(fixture)
    assert result["passed"] and result["fully_correct_names"] == 1
    assert result["explicit_source_text_records"] == 1
    observed = result["checks"][0]["observed"]
    assert observed["source_publication_reviewed"] is False
    assert observed["source_text_basis"] == "available_article_text"
    assert fixture == before


def test_evidence_article_is_not_implicitly_opted_into_source_text_scoring():
    fixture = article_case()
    source = fixture["inputs"].pop("source_text_records")[0]
    source["status"] = "published"
    fixture["inputs"]["evidence"] = [source]
    result = audit_module.score_case(fixture)
    assert result["explicit_source_text_records"] == 0
    assert not result["passed"] and result["errors"] == {"name_missing": 1}


def test_explicit_article_diagnostic_keeps_false_positives_and_wrong_codes_visible():
    fixture = article_case()
    fixture["inputs"]["source_text_records"][0]["article"]["paragraphs"].append(
        {"text": "Blueberry varieties include Unexpected Name."})
    fixture["expected"][0]["breeder_code"] = "FL 999"
    result = audit_module.score_case(fixture)
    assert result["errors"] == {"unexpected_name": 1, "wrong_or_missing_code": 1}
    assert not result["passed"]


def test_nested_explicit_article_inputs_survive_scorer_mutation():
    fixture = article_case()
    before = deepcopy(fixture)
    def mutate(**kwargs):
        kwargs["source_text_records"][0]["article"]["paragraphs"][0]["text"] = "changed"
        return {"mentions": [], "exclusions": []}
    audit_module.score_case(fixture, discover=mutate)
    assert fixture == before


@pytest.mark.parametrize("expected", [None, {}, [{"name": "", "berry_id": "berry-blueberry"}],
                                      [{"name": "Missing Crop"}]])
def test_unfinished_or_invalid_expected_names_are_refused_before_discovery(expected):
    fixture = article_case()
    fixture["expected"] = expected
    def forbidden(**kwargs):
        pytest.fail("Unfinished expectations must not be scored")
    with pytest.raises(ValueError, match="Expected"):
        audit_module.score_case(fixture, discover=forbidden)


def test_explicit_human_review_remains_metadata_and_does_not_qualify_a_fixture(tmp_path):
    fixture = {"schema_version": "variety-name-recall-v1", "scope": "Fictional article test only",
               "review_status": "not independently human-verified", "cases": [article_case()]}
    path = tmp_path / "article-fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    before = path.read_bytes()
    result = audit_module.audit(path)
    assert result["summary"]["name_recall"] == 1
    assert result["review_status"] == "not independently human-verified"
    assert path.read_bytes() == before
    assert not any(p.name != path.name for p in tmp_path.iterdir())


def test_cli_refuses_unfinished_article_expectations_without_writing_a_score(tmp_path):
    item = article_case()
    item["expected"] = None
    fixture = {"schema_version": "variety-name-recall-v1", "scope": "Unfinished fictional expectations",
               "review_status": "not independently human-verified", "cases": [item]}
    path, output = tmp_path / "fixture.json", tmp_path / "score.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    before = path.read_bytes()
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/audit_variety_name_recall.py"),
        "--fixture", str(path), "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode != 0 and "Expected-name list is unfinished" in completed.stderr
    assert not output.exists() and path.read_bytes() == before
