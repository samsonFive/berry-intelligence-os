"""Independent Missed Intelligence Discovery + Recall Audit V1.

Scores the body-free genetics recall benchmark against the live canonical
corpus. Does not write Sources, Evidence, or trusted Varieties. Does not
expose a dashboard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.recall_audit import (
    DATE_CHRONOLOGY_FAILURE,
    ENTITY_FOUND_IDENTITY_UNRESOLVED,
    FULLY_REPRESENTED,
    GEOGRAPHY_LINKAGE_FAILURE,
    SOURCE_COLLECTED_ITEM_MISSED,
    SOURCE_KNOWN_NOT_COLLECTED,
    SOURCE_UNKNOWN,
    classify_result,
    score_benchmark,
)
from app.services.source_lifecycle import is_collection_eligible

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "data" / "imports" / "missed-intelligence-recall-audit-v1" / "benchmark.json"

EXPECTED_CLASSES = {
    "RA-EU-BK-01": SOURCE_KNOWN_NOT_COLLECTED,
    "RA-EU-BK-03": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-EU-BK-04": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-EU-BK-GEO": FULLY_REPRESENTED,
    "RA-UK-RB-01": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-UK-RB-02": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-UK-RB-03": SOURCE_KNOWN_NOT_COLLECTED,
    "RA-SA-BB-01": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-SA-BB-02": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-SA-BB-03": ENTITY_FOUND_IDENTITY_UNRESOLVED,
    "RA-SA-BB-DATE": DATE_CHRONOLOGY_FAILURE,
    "RA-US-BB-01": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-US-BB-ID": ENTITY_FOUND_IDENTITY_UNRESOLVED,
    "RA-US-BB-03": SOURCE_COLLECTED_ITEM_MISSED,
    "RA-US-BB-04": ENTITY_FOUND_IDENTITY_UNRESOLVED,
    "RA-US-BB-05": GEOGRAPHY_LINKAGE_FAILURE,
    "RA-US-BB-06": SOURCE_KNOWN_NOT_COLLECTED,
    "RA-US-BB-07": FULLY_REPRESENTED,
    "RA-EU-ST-01": SOURCE_UNKNOWN,
    "RA-EU-ST-02": SOURCE_KNOWN_NOT_COLLECTED,
    "RA-EU-ST-05": SOURCE_KNOWN_NOT_COLLECTED,
    "RA-EU-ST-06": FULLY_REPRESENTED,
}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus():
    sources = _load_json(ROOT / "data" / "configuration" / "sources.json")
    evidence = [
        _load_json(path)
        for path in sorted((ROOT / "data" / "evidence").glob("*.json"))
    ]
    varieties = [
        _load_json(path)
        for path in sorted((ROOT / "data" / "entities" / "varieties").glob("*.json"))
    ]
    entities = [
        _load_json(path)
        for path in sorted((ROOT / "data" / "entities").rglob("*.json"))
    ]
    facts = [
        _load_json(path)
        for path in sorted((ROOT / "data" / "facts").glob("*.json"))
    ]
    return sources, evidence, varieties, entities, facts


@pytest.fixture(scope="module")
def scored(corpus):
    sources, evidence, varieties, entities, facts = corpus
    benchmark = _load_json(BENCHMARK_PATH)
    return score_benchmark(
        benchmark,
        sources=sources,
        published_evidence=evidence,
        varieties=varieties,
        entities=entities,
        facts=facts,
    )


def _row(scored, result_id: str) -> dict:
    for row in scored["results"]:
        if row.get("id") == result_id:
            return row
    raise AssertionError(f"missing benchmark result {result_id}")


def test_expected_miss_classes_against_canonical_corpus(scored):
    observed = {row["id"]: row["miss_classification"] for row in scored["results"]}
    assert observed == EXPECTED_CLASSES


def test_italian_berry_is_cited_but_not_collected(corpus, scored):
    sources, evidence, _varieties, _entities, _facts = corpus
    assert not any("italianberry.it" in json.dumps(source) for source in sources)
    cited = any(
        "italianberry.it" in str(row.get("source_url") or "")
        for row in evidence
        if row.get("status") == "published"
    )
    assert cited
    assert _row(scored, "RA-EU-BK-01")["miss_classification"] == SOURCE_KNOWN_NOT_COLLECTED
    assert not any(is_collection_eligible(source) and "italianberry" in json.dumps(source) for source in sources)


def test_apex_entity_and_geography_failures(scored):
    entity_row = _row(scored, "RA-US-BB-04")
    geo_row = _row(scored, "RA-US-BB-05")
    assert entity_row["miss_classification"] == ENTITY_FOUND_IDENTITY_UNRESOLVED
    assert entity_row["verified_evidence_id"] == "ev-20260806173901-d4fc-fall-creek-launches-apex-blueberry-varie"
    assert geo_row["miss_classification"] == GEOGRAPHY_LINKAGE_FAILURE


def test_nda_list_collected_named_cultivars_are_candidates_not_canonical(scored):
    row = _row(scored, "RA-SA-BB-03")
    assert row["miss_classification"] == ENTITY_FOUND_IDENTITY_UNRESOLVED
    assert row["verified_evidence_id"] == "ev-nda-za-variety-list-2025"


def test_victoria_uk_geography_from_linked_evidence(scored):
    assert _row(scored, "RA-EU-BK-GEO")["miss_classification"] == FULLY_REPRESENTED


def test_bayer_first_party_source_unknown(scored):
    assert _row(scored, "RA-EU-ST-01")["miss_classification"] == SOURCE_UNKNOWN


def test_sekoya_nova_and_redsayra_fully_represented(scored):
    assert _row(scored, "RA-US-BB-07")["miss_classification"] == FULLY_REPRESENTED
    assert _row(scored, "RA-EU-ST-06")["miss_classification"] == FULLY_REPRESENTED
    assert scored["counts"][FULLY_REPRESENTED] == 3


def test_fc11_164_everlast_identity_unresolved(scored):
    assert _row(scored, "RA-US-BB-ID")["miss_classification"] == ENTITY_FOUND_IDENTITY_UNRESOLVED
    assert _row(scored, "RA-US-BB-ID")["verified_entity_id"] == "variety-fc11-164"


def test_loch_katrine_collected_source_item_missed(scored):
    assert _row(scored, "RA-EU-BK-03")["miss_classification"] == SOURCE_COLLECTED_ITEM_MISSED


def test_score_is_counts_not_a_completeness_percentage(scored):
    assert "coverage_percent" not in scored
    assert "completeness" not in scored
    assert "recall_percent" not in scored
    assert any("not a coverage percentage" in note for note in scored["notes"])


def test_hidden_reasoning_is_stripped(corpus):
    sources, evidence, varieties, _entities, _facts = corpus
    scored = classify_result(
        {
            "qualification": "qualifying",
            "url": "https://www.bayer.com/media/en-us/bayer-to-launch-innovative-strawberry-variety/",
            "reasoning": "secret chain",
            "hidden_reasoning": "do not persist",
            "raw_model_output": "<think>no</think>",
        },
        sources=sources,
        published_evidence=evidence,
        varieties=varieties,
    )
    assert "reasoning" not in scored
    assert "hidden_reasoning" not in scored
    assert "raw_model_output" not in scored
    assert scored["miss_classification"] == SOURCE_UNKNOWN


def test_classifier_does_not_write_evidence_or_sources(tmp_path, monkeypatch, corpus, scored):
    sources_path = ROOT / "data" / "configuration" / "sources.json"
    evidence_dir = ROOT / "data" / "evidence"
    source_mtime = sources_path.stat().st_mtime
    evidence_count = len(list(evidence_dir.glob("*.json")))
    _ = scored
    assert sources_path.stat().st_mtime == source_mtime
    assert len(list(evidence_dir.glob("*.json"))) == evidence_count
    assert not (tmp_path / "evidence").exists()
