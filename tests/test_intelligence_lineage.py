"""Referential integrity for the V2 Phase 1.5A intelligence objects
(docs/v2/10-BACKLOG.md BL-024/BL-025). scripts/validate_records.py only
checks JSON-Schema conformance per file -- it never confirms that an id an
object *references* (fact_ids, evidence_ids, assessment_ids, signal_ids,
entity_ids, strategic_question_ids) actually resolves to a live record. This
closes that gap for Signal, Assessment, and Recommendation: every reference
in the lineage chain (Recommendation -> Assessment/Signal -> Facts ->
Evidence -> Source, docs/v2/03-DOMAIN-MODEL.md) must point at something
real. Pure file/JSON checks -- no app.main import, no route/template
involvement, no PostgreSQL."""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_all(folder: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.rglob("*.json"))]


def _ids(folder: Path) -> set[str]:
    return {r["id"] for r in _load_all(folder) if r.get("id")}


def _signals() -> list[dict]:
    return _load_all(ROOT / "data" / "signals")


def _assessments() -> list[dict]:
    return _load_all(ROOT / "data" / "assessments")


def _recommendations() -> list[dict]:
    return _load_all(ROOT / "data" / "recommendations")


def _unresolved(record_ids: list[str] | None, universe: set[str]) -> list[str]:
    return [i for i in (record_ids or []) if i not in universe]


# ---------------------------------------------------------------------------
# Part A acceptance criteria: the six staged blueberry Signals are imported,
# unmodified in substance, with no duplicate ids.
# ---------------------------------------------------------------------------

EXPECTED_SIGNAL_IDS = {
    "sig-breeder-and-patent-attribution-drift-in-public-sources",
    "sig-breeding-programmes-becoming-consumer-platforms",
    "sig-financial-owners-taking-positions-in-berry-genetics",
    "sig-owner-published-quality-figures-exceed-independent-measurement",
    "sig-registry-participation-is-highly-uneven-between-breeders",
    "sig-southern-africa-as-licensing-and-enforcement-arena",
}


def test_all_six_staged_signals_are_imported() -> None:
    live_ids = {s["id"] for s in _signals()}
    assert EXPECTED_SIGNAL_IDS.issubset(live_ids), EXPECTED_SIGNAL_IDS - live_ids


def test_imported_signals_preserve_proposed_status_and_are_not_upgraded() -> None:
    for signal in _signals():
        if signal["id"] in EXPECTED_SIGNAL_IDS:
            assert signal.get("status") == "proposed", (signal["id"], signal.get("status"))
            assert signal.get("reviewer") is None, (signal["id"], signal.get("reviewer"))


def test_no_duplicate_signal_ids() -> None:
    ids = [s["id"] for s in _signals()]
    assert len(ids) == len(set(ids)), f"duplicate signal ids: {[i for i in ids if ids.count(i) > 1]}"


def test_no_duplicate_assessment_ids() -> None:
    ids = [a["id"] for a in _assessments()]
    assert len(ids) == len(set(ids)), f"duplicate assessment ids: {[i for i in ids if ids.count(i) > 1]}"


def test_no_duplicate_recommendation_ids() -> None:
    ids = [r["id"] for r in _recommendations()]
    assert len(ids) == len(set(ids)), f"duplicate recommendation ids: {[i for i in ids if ids.count(i) > 1]}"


# ---------------------------------------------------------------------------
# Signal reference resolution
# ---------------------------------------------------------------------------

def test_every_signal_evidence_id_resolves() -> None:
    evidence_ids = _ids(ROOT / "data" / "evidence")
    for signal in _signals():
        missing = _unresolved(signal.get("evidence_ids"), evidence_ids)
        assert not missing, f"{signal['id']}: unresolved evidence_ids {missing}"


def test_every_signal_entity_id_resolves() -> None:
    entity_ids = _ids(ROOT / "data" / "entities")
    for signal in _signals():
        missing = _unresolved(signal.get("entity_ids"), entity_ids)
        assert not missing, f"{signal['id']}: unresolved entity_ids {missing}"


def test_every_signal_strategic_question_id_resolves() -> None:
    sq_ids = _ids(ROOT / "data" / "strategic-questions")
    for signal in _signals():
        missing = _unresolved(signal.get("strategic_question_ids"), sq_ids)
        assert not missing, f"{signal['id']}: unresolved strategic_question_ids {missing}"


def test_every_signal_fact_id_resolves() -> None:
    fact_ids = _ids(ROOT / "data" / "facts")
    for signal in _signals():
        missing = _unresolved(signal.get("fact_ids"), fact_ids)
        assert not missing, f"{signal['id']}: unresolved fact_ids {missing}"


# ---------------------------------------------------------------------------
# Assessment reference resolution (Part B acceptance criteria)
# ---------------------------------------------------------------------------

def test_at_least_one_published_assessment_exists() -> None:
    assert len(_assessments()) >= 1


def test_every_assessment_fact_id_resolves() -> None:
    fact_ids = _ids(ROOT / "data" / "facts")
    for assessment in _assessments():
        missing = _unresolved(assessment.get("fact_ids"), fact_ids)
        assert not missing, f"{assessment['id']}: unresolved fact_ids {missing}"


def test_every_assessment_evidence_id_resolves() -> None:
    evidence_ids = _ids(ROOT / "data" / "evidence")
    for assessment in _assessments():
        missing = _unresolved(assessment.get("evidence_ids"), evidence_ids)
        assert not missing, f"{assessment['id']}: unresolved evidence_ids {missing}"


def test_every_assessment_entity_id_resolves() -> None:
    entity_ids = _ids(ROOT / "data" / "entities")
    for assessment in _assessments():
        missing = _unresolved(assessment.get("entity_ids"), entity_ids)
        assert not missing, f"{assessment['id']}: unresolved entity_ids {missing}"


def test_every_assessment_strategic_question_id_resolves() -> None:
    sq_ids = _ids(ROOT / "data" / "strategic-questions")
    for assessment in _assessments():
        missing = _unresolved(assessment.get("strategic_question_ids"), sq_ids)
        assert not missing, f"{assessment['id']}: unresolved strategic_question_ids {missing}"


def test_every_assessment_counterevidence_id_resolves() -> None:
    # counterevidence_ids may point at either a Fact or a piece of Evidence.
    universe = _ids(ROOT / "data" / "facts") | _ids(ROOT / "data" / "evidence")
    for assessment in _assessments():
        missing = _unresolved(assessment.get("counterevidence_ids"), universe)
        assert not missing, f"{assessment['id']}: unresolved counterevidence_ids {missing}"


def test_every_assessment_has_at_least_one_fact() -> None:
    # Structurally required by assessment.schema.json (fact_ids minItems 1)
    # -- re-asserted here against the live data, not just the schema.
    for assessment in _assessments():
        assert assessment.get("fact_ids"), f"{assessment['id']}: no supporting facts"


# ---------------------------------------------------------------------------
# Recommendation reference resolution (Part C acceptance criteria)
# ---------------------------------------------------------------------------

def test_at_least_one_published_recommendation_exists() -> None:
    assert len(_recommendations()) >= 1


def test_every_recommendation_assessment_id_resolves() -> None:
    assessment_ids = _ids(ROOT / "data" / "assessments")
    for rec in _recommendations():
        missing = _unresolved(rec.get("assessment_ids"), assessment_ids)
        assert not missing, f"{rec['id']}: unresolved assessment_ids {missing}"


def test_every_recommendation_signal_id_resolves() -> None:
    signal_ids = _ids(ROOT / "data" / "signals")
    for rec in _recommendations():
        missing = _unresolved(rec.get("signal_ids"), signal_ids)
        assert not missing, f"{rec['id']}: unresolved signal_ids {missing}"


def test_every_recommendation_fact_id_resolves() -> None:
    fact_ids = _ids(ROOT / "data" / "facts")
    for rec in _recommendations():
        missing = _unresolved(rec.get("fact_ids"), fact_ids)
        assert not missing, f"{rec['id']}: unresolved fact_ids {missing}"


def test_every_recommendation_evidence_id_resolves() -> None:
    evidence_ids = _ids(ROOT / "data" / "evidence")
    for rec in _recommendations():
        missing = _unresolved(rec.get("evidence_ids"), evidence_ids)
        assert not missing, f"{rec['id']}: unresolved evidence_ids {missing}"


def test_every_recommendation_entity_id_resolves() -> None:
    entity_ids = _ids(ROOT / "data" / "entities")
    for rec in _recommendations():
        missing = _unresolved(rec.get("entity_ids"), entity_ids)
        assert not missing, f"{rec['id']}: unresolved entity_ids {missing}"


def test_every_recommendation_strategic_question_id_resolves() -> None:
    sq_ids = _ids(ROOT / "data" / "strategic-questions")
    for rec in _recommendations():
        missing = _unresolved(rec.get("strategic_question_ids"), sq_ids)
        assert not missing, f"{rec['id']}: unresolved strategic_question_ids {missing}"


def test_every_recommendation_has_at_least_one_assessment_or_signal() -> None:
    # Structurally required by recommendation.schema.json's anyOf -- Part C's
    # "not a shortcut from bare evidence" rule, re-asserted against live data.
    for rec in _recommendations():
        assert rec.get("assessment_ids") or rec.get("signal_ids"), (
            f"{rec['id']}: no linked assessment or signal"
        )


# ---------------------------------------------------------------------------
# Full lineage: the one real Recommendation created for Part D traces all
# the way back to Evidence through an Assessment.
# ---------------------------------------------------------------------------

def test_the_real_recommendation_traces_full_lineage_to_evidence() -> None:
    recommendations = {r["id"]: r for r in _recommendations()}
    rec = recommendations.get("recommendation-treat-costa-driscolls-as-structurally-linked")
    assert rec is not None, "expected Part D recommendation not found"

    assessments = {a["id"]: a for a in _assessments()}
    linked_assessment_ids = rec.get("assessment_ids") or []
    assert linked_assessment_ids, "Part D recommendation has no linked assessment"
    for aid in linked_assessment_ids:
        assessment = assessments.get(aid)
        assert assessment is not None, f"linked assessment {aid} does not resolve"
        assert assessment.get("fact_ids"), f"{aid}: assessment has no supporting facts"
        assert assessment.get("evidence_ids"), f"{aid}: assessment has no supporting evidence"

    assert rec.get("evidence_ids"), "Part D recommendation cites no evidence of its own"
    evidence_ids = _ids(ROOT / "data" / "evidence")
    assert set(rec["evidence_ids"]).issubset(evidence_ids)


# ---------------------------------------------------------------------------
# Fail-loudly sanity check: the resolver helper actually catches an orphaned
# reference rather than silently passing everything.
# ---------------------------------------------------------------------------

def test_unresolved_helper_actually_detects_orphaned_references() -> None:
    universe = {"real-id-1", "real-id-2"}
    assert _unresolved(["real-id-1", "does-not-exist"], universe) == ["does-not-exist"]
    assert _unresolved(["real-id-1", "real-id-2"], universe) == []
    assert _unresolved(None, universe) == []
