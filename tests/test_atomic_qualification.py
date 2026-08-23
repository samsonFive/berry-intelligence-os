"""Offline qualification scoring against the Gold Set V1 contract."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from app.services.atomic_qualification import (
    GoldSetContractError,
    load_atomic_gold_set,
    score_gold_case,
    score_gold_set,
)


FIXTURE = Path(__file__).parent / "fixtures" / "atomic-evidence-gold-set-contract-v1.json"
ROOT = Path(__file__).resolve().parents[1]
CANONICAL_FIXTURE = ROOT / "benchmarks" / "atomic-evidence-gold-set-v1.json"
CANONICAL_DOCUMENT = ROOT / "docs" / "v2" / "ATOMIC-EVIDENCE-GOLD-SET-V1.md"


@pytest.fixture
def gold_set():
    return load_atomic_gold_set(FIXTURE)


@pytest.fixture
def perfect_proposals():
    return [
        {
            "normalized_statement": "In the Kent trial, Zara maintained shelf life for 10 days.",
            "transcript_excerpt": "In the Kent trial, Zara maintained shelf life for 10 days.",
            "entity_ids": ["variety-zara"], "geography_ids": [], "berry_ids": [],
        },
        {
            "normalized_statement": "A UK retailer expressed interest in another trial and made no purchase commitment.",
            "transcript_excerpt": "A UK retailer expressed interest in another trial but made no purchase commitment.",
            "entity_ids": [], "geography_ids": [], "berry_ids": [],
        },
    ]


def test_gold_set_contract_supports_rich_expected_fields(gold_set):
    case = gold_set.cases[0]
    assert gold_set.gold_set_id == "atomic-evidence-test-gold-v1"
    assert len(case.expected_propositions) == 2
    assert case.expected_propositions[0].claim_type == "trial_result"
    assert case.expected_propositions[0].exact_excerpts[0].startswith("In the Kent trial")
    assert case.expected_propositions[0].start_seconds == 0
    assert case.forbidden_propositions[0].severity == "critical"


def test_perfect_output_scores_correctly(gold_set, perfect_proposals):
    report = score_gold_set(gold_set, {gold_set.cases[0].case_id: perfect_proposals})
    assert report["passed"] is True
    assert all(value == 1.0 for value in report["metrics"].values())


def test_missing_proposition_reduces_recall(gold_set, perfect_proposals):
    score = score_gold_case(gold_set.cases[0], perfect_proposals[:1])
    assert score["metrics"]["recall"] == 0.5
    assert score["unmatched_expected_ids"] == ["retailer-interest"]


def test_unsupported_proposition_reduces_precision(gold_set, perfect_proposals):
    proposals = perfect_proposals + [{
        "normalized_statement": "The retailer signed a nationwide supply agreement.",
        "transcript_excerpt": perfect_proposals[1]["transcript_excerpt"],
        "entity_ids": [], "geography_ids": [], "berry_ids": [],
    }]
    score = score_gold_case(gold_set.cases[0], proposals)
    assert score["metrics"]["precision"] == pytest.approx(2 / 3, abs=1e-6)
    assert score["unmatched_proposal_indexes"] == [2]


def test_combined_summary_claim_hurts_atomicity_and_recall(gold_set, perfect_proposals):
    proposal = {
        "normalized_statement": "Zara had 10 days of shelf life in a Kent trial and a UK retailer expressed interest in another trial.",
        "transcript_excerpt": "\n".join(item["transcript_excerpt"] for item in perfect_proposals),
        "entity_ids": ["variety-zara"], "geography_ids": [], "berry_ids": [],
    }
    score = score_gold_case(gold_set.cases[0], [proposal])
    assert score["metrics"]["atomicity"] == 0.0
    assert score["metrics"]["recall"] == 0.5
    assert score["combined_claims"][0]["expected_ids"] == ["trial-shelf-life", "retailer-interest"]


def test_wrong_excerpt_hurts_grounding(gold_set, perfect_proposals):
    proposals = deepcopy(perfect_proposals)
    proposals[0]["transcript_excerpt"] = "This excerpt does not occur in the source."
    score = score_gold_case(gold_set.cases[0], proposals)
    assert score["metrics"]["grounding"] == 0.5


def test_wrong_entity_hurts_entity_resolution(gold_set, perfect_proposals):
    proposals = deepcopy(perfect_proposals)
    proposals[0]["entity_ids"] = ["company-wrong"]
    score = score_gold_case(gold_set.cases[0], proposals)
    assert score["metrics"]["entity_resolution"] == 0.5


def test_missing_scope_hurts_scope_preservation(gold_set, perfect_proposals):
    proposals = deepcopy(perfect_proposals)
    proposals[0]["normalized_statement"] = "Zara maintained shelf life for 10 days."
    score = score_gold_case(gold_set.cases[0], proposals)
    assert score["metrics"]["scope_preservation"] == 0.5


def test_duplicate_claim_is_penalized(gold_set, perfect_proposals):
    proposals = perfect_proposals + [deepcopy(perfect_proposals[0])]
    score = score_gold_case(gold_set.cases[0], proposals)
    assert score["metrics"]["duplication"] < 1.0
    assert score["duplicate_pairs"] == [[0, 2]]


def test_forbidden_inference_is_a_hard_failure(gold_set, perfect_proposals):
    proposals = deepcopy(perfect_proposals)
    proposals[1]["normalized_statement"] = "The UK retailer committed to purchase Zara after the trial."
    score = score_gold_case(gold_set.cases[0], proposals)
    assert score["critical_overreach"] is True
    assert score["metrics"]["overreach"] == 0.5
    assert score["forbidden_hits"][0]["rule_id"] == "purchase-commitment"


@pytest.mark.parametrize(
    "statement,rule_id",
    [
        ("Company A owns the breeder.", "unsupported-ownership"),
        ("The filing caused the yield increase.", "unsupported-causality"),
        ("The registry filing proves commercialization.", "registry-commercialization"),
        ("The award proves consumers prefer Zara.", "award-consumer-preference"),
        ("The marketing claim is independently verified.", "marketing-independent-verification"),
        ("Zara always maintains shelf life for 10 days.", "universal-trait"),
    ],
)
def test_named_overreach_classes_are_critical(gold_set, perfect_proposals, statement, rule_id):
    proposal = deepcopy(perfect_proposals[0])
    proposal["normalized_statement"] = statement
    score = score_gold_case(gold_set.cases[0], [proposal])
    assert score["critical_overreach"] is True
    assert any(hit["rule_id"] == rule_id for hit in score["forbidden_hits"])


def test_unknown_contract_fields_fail_closed(tmp_path):
    payload = FIXTURE.read_text(encoding="utf-8").replace('"description":', '"mystery": true, "description":', 1)
    path = tmp_path / "bad.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(GoldSetContractError, match="unsupported fields"):
        load_atomic_gold_set(path)


def test_canonical_gold_set_is_sha_bound_and_complete():
    gold = load_atomic_gold_set(CANONICAL_FIXTURE)
    normalized_document = CANONICAL_DOCUMENT.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    document_sha = hashlib.sha256(normalized_document.encode("utf-8")).hexdigest()
    assert gold.gold_set_id == "atomic-evidence-gold-set-v1"
    assert gold.source_document == "docs/v2/ATOMIC-EVIDENCE-GOLD-SET-V1.md"
    assert gold.source_document_sha256 == document_sha
    assert len(gold.cases) == 16
    assert sum(len(case.expected_propositions) for case in gold.cases) == 54
    assert all(case.source_artifact["locator_kind"] == "written_text" for case in gold.cases)
    assert all(
        segment["start_seconds"] is None and segment.get("source_location") in {"summary", "why_it_matters"}
        for case in gold.cases for segment in case.source_artifact["segments"]
    )
    source_ids = {case.source_artifact["id"] for case in gold.cases}
    assert "ev-media-069f07925d20b2d93743" not in source_ids
    assert "ev-lucentlands-scaling-blueberry-industry-2025" not in source_ids


def test_canonical_gold_set_carries_every_strict_overreach_rule():
    gold = load_atomic_gold_set(CANONICAL_FIXTURE)
    expected = {
        "ownership-implies-control",
        "unsupported-causality",
        "registry-implies-commercialization",
        "interest-implies-commitment",
        "award-implies-general-preference",
        "local-trial-implies-universal-trait",
        "marketing-implies-independent-verification",
    }
    assert all({rule.rule_id for rule in case.forbidden_propositions} == expected for case in gold.cases)


def test_materialized_fixture_matches_reviewed_document():
    from scripts.materialize_atomic_gold_set import materialize

    expected = materialize(CANONICAL_DOCUMENT)
    actual = json.loads(CANONICAL_FIXTURE.read_text(encoding="utf-8"))
    assert actual == expected
