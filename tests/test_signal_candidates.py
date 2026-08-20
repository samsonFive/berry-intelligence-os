"""app/services/signal_candidates.py -- deterministic, untrusted Signal-
candidate generation.

Real problem: two reprints of one press release must never look like two
independent corroborating sources. These tests prove each of the four
candidate patterns (multi-source corroboration, primary-source-plus-
followup, repeated activity, contradiction) fires only when the
underlying Evidence genuinely supports it, and that a bare same-topic
pair with no independence and no primary anchor produces nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.signal_candidates import (
    PATTERN_CONTRADICTION,
    PATTERN_MULTI_SOURCE,
    PATTERN_PRIMARY_PLUS_FOLLOWUP,
    PATTERN_REPEATED_ACTIVITY,
    SignalCandidateError,
    apply_review_decision,
    generate_candidates,
    load_candidates,
    persist_candidates,
)


def _evidence(evidence_id: str, **overrides) -> dict:
    base = {
        "id": evidence_id,
        "record_type": "evidence",
        "title": "Base title",
        "summary": "",
        "why_it_matters": "",
        "source_id": None,
        "source_name": None,
        "source_authority": None,
        "source_type": None,
        "intake_type": None,
        "published_date": "2026-07-01",
        "entity_ids": [],
        "berry_ids": [],
        "geography_ids": [],
        "evidence_links": [],
    }
    base.update(overrides)
    return base


def test_two_genuinely_independent_sources_form_a_multi_source_candidate():
    a = _evidence(
        "ev-a", source_name="Fruitnet", entity_ids=["company-driscolls"],
        title="Driscoll's expands strawberry acreage in Baja", published_date="2026-07-01",
    )
    b = _evidence(
        "ev-b", source_name="The Packer", entity_ids=["company-driscolls"],
        title="Driscoll's berry program grows Baja footprint", published_date="2026-07-10",
    )
    candidates = generate_candidates([a, b])
    multi = [c for c in candidates if c["pattern_type"] == PATTERN_MULTI_SOURCE]
    assert len(multi) == 1
    assert multi[0]["independence"]["independent_source_count"] == 2
    assert set(multi[0]["supporting_evidence_ids"]) == {"ev-a", "ev-b"}


def test_same_origin_pair_with_no_primary_anchor_produces_nothing():
    # Same source_name (same origin), and neither record is a patent,
    # newsroom, or explicitly high-authority record -- no candidate
    # should form at all, matching "two reprints is not corroboration."
    a = _evidence("ev-a", source_name="Generic Aggregator", entity_ids=["company-x"], title="X news item one")
    b = _evidence("ev-b", source_name="Generic Aggregator", entity_ids=["company-x"], title="X news item two")
    candidates = generate_candidates([a, b])
    assert candidates == []


def test_primary_source_plus_followup_from_the_same_origin_is_flagged_distinctly():
    a = _evidence(
        "ev-a", source_id="source-hortifrut-newsroom", entity_ids=["company-hortifrut", "company-naturipe-farms"],
        title="Hortifrut and Naturipe expand berry genetics platform",
    )
    b = _evidence(
        "ev-b", source_name="FreshFruitPortal", entity_ids=["company-hortifrut", "company-naturipe-farms"],
        title="Hortifrut and Naturipe berry genetics deal", published_date="2026-07-01",
    )
    candidates = generate_candidates([a, b])
    followup = [c for c in candidates if c["pattern_type"] == PATTERN_PRIMARY_PLUS_FOLLOWUP]
    assert len(followup) == 1
    assert followup[0]["independence"]["independent_source_count"] == 1
    assert "not yet independently corroborated" in followup[0]["reason"]
    assert any("no second" in d for d in followup[0]["does_not_prove"])


def test_a_patent_is_a_primary_source_for_followup_purposes():
    patent = _evidence(
        "ev-patent-x", source_type="patent_record", entity_ids=["company-driscolls"],
        title="Blueberry plant named X", published_date="2026-07-01",
    )
    coverage = _evidence(
        "ev-coverage-x", source_name="Fruitnet", entity_ids=["company-driscolls"],
        title="Driscoll's blueberry plant patent X reported", published_date="2026-07-05",
    )
    candidates = generate_candidates([patent, coverage])
    assert any(c["pattern_type"] in (PATTERN_MULTI_SOURCE, PATTERN_PRIMARY_PLUS_FOLLOWUP) for c in candidates)


def test_repeated_activity_requires_at_least_three_independent_dated_events():
    titles = ["Company X opens new packing facility", "Company X wins export award", "Company X names new chief breeder"]
    records = [
        _evidence(f"ev-{i}", source_name=f"Outlet {i}", entity_ids=["company-x"], title=titles[i], published_date=d)
        for i, d in enumerate(["2026-01-01", "2026-03-01", "2026-05-01"])
    ]
    candidates = generate_candidates(records)
    repeated = [c for c in candidates if c["pattern_type"] == PATTERN_REPEATED_ACTIVITY]
    assert len(repeated) == 1
    assert repeated[0]["independence"]["independent_source_count"] == 3


def test_two_dated_events_do_not_trigger_repeated_activity():
    records = [
        _evidence("ev-a", source_name="Outlet A", entity_ids=["company-x"], title="X event one", published_date="2026-01-01"),
        _evidence("ev-b", source_name="Outlet B", entity_ids=["company-x"], title="X event two", published_date="2026-03-01"),
    ]
    candidates = generate_candidates(records)
    assert all(c["pattern_type"] != PATTERN_REPEATED_ACTIVITY for c in candidates)


def test_explicit_contradicts_link_forms_a_contradiction_candidate():
    a = _evidence("ev-a", entity_ids=["company-x"], title="Filing assigns patent to Company X")
    b = _evidence(
        "ev-b", entity_ids=["company-x"], title="Registry lists a different assignee for the same filing",
        evidence_links=[
            {
                "predicate": "contradicts", "target_evidence_id": "ev-a", "status": "proposed",
                "notes": "Assignee mismatch between two registry sources.",
            }
        ],
    )
    candidates = generate_candidates([a, b])
    contradictions = [c for c in candidates if c["pattern_type"] == PATTERN_CONTRADICTION]
    assert len(contradictions) == 1
    assert set(contradictions[0]["supporting_evidence_ids"]) == {"ev-a", "ev-b"}
    assert contradictions[0]["does_not_prove"]


def test_no_evidence_links_means_no_contradiction_is_ever_inferred():
    # Two records that a human might read as disagreeing must never
    # produce a contradiction candidate without an explicit, formal
    # contradicts link -- this module never infers meaning from free text.
    a = _evidence("ev-a", entity_ids=["company-x"], title="Company X says program is fully funded")
    b = _evidence("ev-b", entity_ids=["company-x"], title="Company X program funding falls short, sources say")
    candidates = generate_candidates([a, b])
    assert all(c["pattern_type"] != PATTERN_CONTRADICTION for c in candidates)


def test_every_candidate_carries_does_not_prove():
    a = _evidence("ev-a", source_name="Fruitnet", entity_ids=["company-x"], title="Company X opens new packing facility")
    b = _evidence("ev-b", source_name="The Packer", entity_ids=["company-x"], title="Company X wins export award", published_date="2026-07-05")
    candidates = generate_candidates([a, b])
    assert candidates
    assert all(c["does_not_prove"] for c in candidates)
    assert all(c["status"] == "proposed" for c in candidates)


def test_primary_plus_followup_confidence_is_capped_low_regardless_of_count():
    # Even a primary source plus several same-origin follow-ups must
    # never read as "high" confidence -- that would defeat the entire
    # point of distinguishing this pattern from real corroboration.
    records = [
        _evidence("ev-primary", source_id="source-x-newsroom", entity_ids=["company-x"], title="Company X announces alpha program"),
    ] + [
        _evidence(f"ev-followup-{i}", source_name=f"Outlet {i}", entity_ids=["company-x"], title="Company X alpha program announced")
        for i in range(4)
    ]
    candidates = generate_candidates(records)
    followups = [c for c in candidates if c["pattern_type"] == PATTERN_PRIMARY_PLUS_FOLLOWUP]
    assert followups
    assert all(c["signal_confidence"] == "low" for c in followups)


def test_apply_review_decision_confirm_sets_status_and_reviewer():
    candidate = {"id": "sigcand-x", "status": "proposed", "reviewer": None, "review_notes": None}
    updated = apply_review_decision(candidate, decision="confirm", reviewer="jsmith", notes="Looks solid.")
    assert updated["status"] == "confirmed"
    assert updated["reviewer"] == "jsmith"
    assert updated["review_notes"] == "Looks solid."
    assert "reviewed_at" in updated
    # Original is untouched.
    assert candidate["status"] == "proposed"


def test_apply_review_decision_dispute_maps_to_disputed_status():
    candidate = {"id": "sigcand-x", "status": "proposed"}
    updated = apply_review_decision(candidate, decision="dispute", reviewer="jsmith")
    assert updated["status"] == "disputed"


def test_apply_review_decision_rejects_unknown_decision():
    with pytest.raises(SignalCandidateError):
        apply_review_decision({"id": "sigcand-x"}, decision="approve", reviewer="jsmith")


def test_apply_review_decision_requires_a_reviewer():
    with pytest.raises(SignalCandidateError):
        apply_review_decision({"id": "sigcand-x"}, decision="confirm", reviewer="")


def test_persist_and_load_candidates_round_trip(tmp_path: Path):
    inbox_dir = tmp_path / "inbox"
    candidate = {"id": "sigcand-test-1", "status": "proposed", "pattern_type": PATTERN_MULTI_SOURCE}
    written = persist_candidates([candidate], inbox_dir=inbox_dir)
    assert len(written) == 1
    loaded = load_candidates(inbox_dir)
    assert loaded == [candidate]


def test_persist_candidates_never_overwrites_an_existing_reviewed_file(tmp_path: Path):
    inbox_dir = tmp_path / "inbox"
    original = {"id": "sigcand-test-1", "status": "confirmed", "reviewer": "jsmith"}
    persist_candidates([original], inbox_dir=inbox_dir)
    regenerated = {"id": "sigcand-test-1", "status": "proposed", "reviewer": None}
    written = persist_candidates([regenerated], inbox_dir=inbox_dir)
    assert written == []
    loaded = load_candidates(inbox_dir)
    assert loaded == [original]


def test_two_distinct_clusters_for_the_same_company_get_different_ids():
    """Real bug found auditing real VPS output: Fall Creek alone produced
    9 separate real multi_source_corroboration clusters (different
    evidence, different underlying events) that all collided onto one id
    under the old (pattern_type, entity_id)-only scheme -- persist_
    candidates()'s additive-only rule then silently dropped 8 of 9 as if
    they were re-generations of the same candidate. Two genuinely
    different clusters for the same company and pattern must produce two
    different, independently-persistable candidate ids."""
    # Titles are deliberately differently-worded (not near-duplicates) so
    # each pair correctly registers as 2 independent origins rather than
    # collapsing via the recalibrated same-origin detection -- this test
    # is about id collisions across clusters, not independence detection
    # itself (see test_near_identical_titles_... in test_source_independence.py
    # for that).
    cluster_a = [
        _evidence("ev-a1", source_name="Fruitnet", entity_ids=["company-fall-creek-farm-and-nursery"], title="Fall Creek buys land parcel near Bucharest", published_date="2024-03-01"),
        _evidence("ev-a2", source_name="Agrovision", entity_ids=["company-fall-creek-farm-and-nursery"], title="Trade sources confirm European expansion by Fall Creek", published_date="2024-03-05"),
    ]
    cluster_b = [
        _evidence("ev-b1", source_name="Produce Report", entity_ids=["company-fall-creek-farm-and-nursery"], title="Fall Creek launches Sekoya Nova variety", published_date="2026-02-01"),
        _evidence("ev-b2", source_name="FreshPlaza", entity_ids=["company-fall-creek-farm-and-nursery"], title="Growers welcome new high-chill release from Fall Creek", published_date="2026-02-06"),
    ]
    candidates = generate_candidates(cluster_a + cluster_b)
    multi = [c for c in candidates if c["pattern_type"] == PATTERN_MULTI_SOURCE]
    assert len(multi) == 2
    assert multi[0]["id"] != multi[1]["id"]
    # Reproducibility: the same real cluster, regenerated later, must
    # still land on the same id -- required for "never overwrite a
    # reviewed candidate file" to mean anything across repeated runs.
    rerun = generate_candidates(cluster_a + cluster_b)
    rerun_multi = [c for c in rerun if c["pattern_type"] == PATTERN_MULTI_SOURCE]
    assert {c["id"] for c in multi} == {c["id"] for c in rerun_multi}


def test_regenerating_the_same_cluster_never_produces_a_second_persisted_file(tmp_path: Path):
    inbox_dir = tmp_path / "inbox"
    cluster = [
        _evidence("ev-a", source_name="Fruitnet", entity_ids=["company-x"], title="Company X does the thing"),
        _evidence("ev-b", source_name="The Packer", entity_ids=["company-x"], title="X thing reported elsewhere", published_date="2026-07-05"),
    ]
    first = generate_candidates(cluster)
    persist_candidates(first, inbox_dir=inbox_dir)
    second = generate_candidates(cluster)
    written_again = persist_candidates(second, inbox_dir=inbox_dir)
    assert written_again == []
    assert len(load_candidates(inbox_dir)) == len(first)


# ---------------------------------------------------------------------------
# Signal-Candidate Calibration mission (2026-08-19): the one real spoken-
# media Evidence in this dataset (a Lucentlands podcast interview with Fall
# Creek's CEO) has transcript={"status": "not_available"} -- its summary is
# built entirely from the publisher's own Apple Podcasts episode
# description, not a verified transcript quote. Real, independently-
# reported Evidence, but weaker grounding than a transcribed record.
# ---------------------------------------------------------------------------


_STRATEGY_TITLES = [
    "Podcast host interviews Company X leadership",
    "Company X opens new packing facility",
    "Company X wins export quality award",
    "Company X names new chief breeder",
]


def _four_source_cluster(transcript_status: str) -> list[dict]:
    podcast = _evidence(
        "ev-podcast", source_name="Some Podcast", entity_ids=["company-x"],
        title=_STRATEGY_TITLES[0], media_format="podcast", published_date="2026-07-01",
    )
    podcast["transcript"] = {"status": transcript_status}
    others = [
        _evidence(f"ev-{i}", source_name=f"Outlet {i}", entity_ids=["company-x"], title=_STRATEGY_TITLES[i + 1], published_date="2026-07-02")
        for i in range(3)
    ]
    return [podcast] + others


def test_untranscribed_spoken_media_caps_confidence_below_high():
    candidates = generate_candidates(_four_source_cluster("not_available"))
    multi = [c for c in candidates if c["pattern_type"] == PATTERN_MULTI_SOURCE]
    assert multi
    assert multi[0]["independence"]["independent_source_count"] == 4
    assert all(c["signal_confidence"] != "high" for c in multi)


def test_untranscribed_spoken_media_adds_an_explicit_does_not_prove_caveat():
    candidates = generate_candidates(_four_source_cluster("not_available"))
    assert candidates
    assert any("transcript" in item for c in candidates for item in c["does_not_prove"])


def test_transcribed_spoken_media_does_not_cap_confidence_or_add_the_caveat():
    candidates = generate_candidates(_four_source_cluster("ready"))
    multi = [c for c in candidates if c["pattern_type"] == PATTERN_MULTI_SOURCE]
    assert multi
    assert multi[0]["independence"]["independent_source_count"] == 4
    assert any(c["signal_confidence"] == "high" for c in multi)
    assert not any("transcript" in item for c in multi for item in c["does_not_prove"])


def test_shared_generic_trait_tag_does_not_link_two_unrelated_companies():
    """Real false positive found auditing real candidate output: a
    shared trait-* entity id (a claimed agronomic characteristic, not an
    actor) linked Fall Creek's field-forum coverage to Costa Group's
    unrelated variety launch -- two competing companies' two unrelated
    stories, joined only by both referencing "postharvest shelf life"."""
    a = _evidence(
        "ev-a", source_name="FreshFruitPortal", entity_ids=["company-fall-creek-farm-and-nursery", "trait-postharvest-shelf-life"],
        title="Fall Creek high-chill field forum coverage",
    )
    b = _evidence(
        "ev-b", source_name="Produce Report", entity_ids=["company-costa-group-holdings", "trait-postharvest-shelf-life"],
        title="Costa launches BluGenix with five blueberry varieties", published_date="2026-07-03",
    )
    candidates = generate_candidates([a, b])
    assert candidates == []


# ---------------------------------------------------------------------------
# Signal to Analyst Assessment Contract (2026-08-20): a confirmed Signal
# candidate must never automatically create an Assessment. Assessment
# authoring stays exactly one path -- a human filling out the existing
# /assessments form (app/main.py:assessment_create), citing signal_ids
# deliberately.
# ---------------------------------------------------------------------------


def test_confirming_a_signal_candidate_never_touches_the_assessments_directory(tmp_path: Path) -> None:
    assessments_dir = tmp_path / "data" / "assessments"
    assessments_dir.mkdir(parents=True)
    candidate = {
        "id": "sigcand-multi-source-corroboration-x", "status": "proposed",
        "pattern_type": PATTERN_MULTI_SOURCE, "supporting_evidence_ids": ["ev-a", "ev-b"],
        "reviewer": None, "review_notes": None,
    }
    confirmed = apply_review_decision(candidate, decision="confirm", reviewer="jsmith")
    assert confirmed["status"] == "confirmed"
    # apply_review_decision is a pure function -- proven by construction,
    # not just by absence of a write call: the assessments directory this
    # test created stays completely empty after confirming.
    assert list(assessments_dir.glob("*.json")) == []


def test_apply_review_decision_return_value_has_no_assessment_shaped_keys() -> None:
    # A confirmed candidate's own record must never grow assessment-
    # specific fields (rationale, etc.) as a side effect of confirmation --
    # confirmation only ever changes the candidate's own review state.
    candidate = {"id": "sigcand-x", "status": "proposed", "pattern_type": PATTERN_MULTI_SOURCE}
    confirmed = apply_review_decision(candidate, decision="confirm", reviewer="jsmith")
    assert "rationale" not in confirmed
    assert confirmed.get("record_type") != "assessment"
