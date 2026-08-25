"""Strategic Question Decision Workspace V1 -- canonical audit found the
Strategic Question workspace nearly fully built already (Strategic
Question + Decision Workspace V1: What we know / What we think / What
we are watching / What we don't know / Watchlist toggle, all live and
static-built). This mission closes three real gaps: an explicit,
schema-supported Tensions/Contradictions section (Assessment
counterevidence_ids + accepted Evidence-to-Evidence "contradicts"
links -- never inferred), a supporting-evidence count on each Signal
row, and a "sensible route into Saved Brief Packs" link. No new trust
route, no new persistence, no semantic-similarity inference, no
auto-resolution of the Question."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.strategic_question_workspace import strategic_question_detail

client = TestClient(app)

REAL_SQ_RICH = "sq-global-genetics-reach"
REAL_SQ_SPARSE = "sq-premium-flavor"
REAL_SQ_WITH_COUNTEREVIDENCE = "sq-competitor-expansion"


def _entity(**overrides):
    row = {"record_type": "entity", "status": "active", "aliases": [], "berry_ids": [], "attributes": {}}
    row.update(overrides)
    return row


def _entities():
    return {"company-a": _entity(id="company-a", entity_type="company", name="Company A", berry_ids=["berry-blueberry"])}


def _sq(**overrides):
    row = {"id": "sq-fixture", "record_type": "strategic_question", "title": "Fixture question", "status": "active", "berry_ids": []}
    row.update(overrides)
    return row


def _detail(**kwargs):
    defaults = dict(
        sq_id="sq-fixture",
        questions=[_sq()],
        entities=_entities(),
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        recommendations=[],
        berry_labels={},
    )
    defaults.update(kwargs)
    return strategic_question_detail(**defaults)


# --- Signal evidence_count -------------------------------------------------


def test_signal_row_carries_supporting_evidence_count() -> None:
    signal = {"id": "sig-x", "title": "A signal", "strategic_question_ids": ["sq-fixture"], "evidence_ids": ["ev-1", "ev-2"]}
    detail = _detail(signals=[signal])
    assert detail["signals"][0]["evidence_count"] == 2


def test_signal_row_evidence_count_zero_when_unpopulated() -> None:
    signal = {"id": "sig-x", "title": "A signal", "strategic_question_ids": ["sq-fixture"]}
    detail = _detail(signals=[signal])
    assert detail["signals"][0]["evidence_count"] == 0


# --- Tensions / Contradictions: Assessment counterevidence -----------------


def test_assessment_counterevidence_resolves_fact_and_evidence_dual_reference() -> None:
    fact = {"id": "fact-1", "statement": "A counter fact.", "strategic_question_ids": []}
    evidence = {"id": "ev-counter", "title": "Counter evidence title", "strategic_question_ids": []}
    assessment = {
        "id": "assessment-x",
        "title": "An assessment",
        "strategic_question_ids": ["sq-fixture"],
        "fact_ids": ["fact-1"],
        "counterevidence_ids": ["fact-1", "ev-counter"],
    }
    detail = _detail(assessments=[assessment], facts=[fact], published_evidence=[evidence])
    rows = detail["assessment_counterevidence"]
    assert len(rows) == 1
    kinds = {item["kind"] for item in rows[0]["counterevidence_items"]}
    assert kinds == {"fact", "evidence"}


def test_assessment_without_counterevidence_produces_no_row() -> None:
    assessment = {"id": "assessment-x", "title": "An assessment", "strategic_question_ids": ["sq-fixture"], "fact_ids": []}
    detail = _detail(assessments=[assessment])
    assert detail["assessment_counterevidence"] == []


def test_assessment_counterevidence_id_that_resolves_nowhere_is_silently_excluded() -> None:
    # A dangling counterevidence_ids reference (missing linked object) must
    # never crash rendering -- just be absent, matching every other
    # lineage resolver's graceful behavior in this codebase.
    assessment = {
        "id": "assessment-x",
        "title": "An assessment",
        "strategic_question_ids": ["sq-fixture"],
        "fact_ids": [],
        "counterevidence_ids": ["fact-does-not-exist-anywhere"],
    }
    detail = _detail(assessments=[assessment])
    assert detail["assessment_counterevidence"] == []


# --- Tensions / Contradictions: Evidence-to-Evidence contradicts links -----


def test_evidence_contradiction_only_counts_accepted_status() -> None:
    ev_a = {
        "id": "ev-a", "title": "Evidence A", "strategic_question_ids": ["sq-fixture"],
        "evidence_links": [{"predicate": "contradicts", "target_evidence_id": "ev-b", "status": "accepted"}],
    }
    ev_b = {"id": "ev-b", "title": "Evidence B", "strategic_question_ids": []}
    detail = _detail(published_evidence=[ev_a, ev_b])
    rows = detail["evidence_contradictions"]
    assert len(rows) == 1
    assert rows[0]["evidence_id"] == "ev-a"
    assert rows[0]["target_id"] == "ev-b"
    assert rows[0]["target_title"] == "Evidence B"


def test_evidence_contradiction_proposed_status_not_counted() -> None:
    ev_a = {
        "id": "ev-a", "title": "Evidence A", "strategic_question_ids": ["sq-fixture"],
        "evidence_links": [{"predicate": "contradicts", "target_evidence_id": "ev-b", "status": "proposed"}],
    }
    detail = _detail(published_evidence=[ev_a])
    assert detail["evidence_contradictions"] == []


def test_evidence_contradiction_other_predicates_not_counted() -> None:
    ev_a = {
        "id": "ev-a", "title": "Evidence A", "strategic_question_ids": ["sq-fixture"],
        "evidence_links": [{"predicate": "corroborates", "target_evidence_id": "ev-b", "status": "accepted"}],
    }
    detail = _detail(published_evidence=[ev_a])
    assert detail["evidence_contradictions"] == []


def test_evidence_contradiction_missing_target_never_crashes() -> None:
    ev_a = {
        "id": "ev-a", "title": "Evidence A", "strategic_question_ids": ["sq-fixture"],
        "evidence_links": [{"predicate": "contradicts", "target_evidence_id": "ev-does-not-exist", "status": "accepted"}],
    }
    detail = _detail(published_evidence=[ev_a])
    rows = detail["evidence_contradictions"]
    assert len(rows) == 1
    assert rows[0]["target_href"] is None
    assert rows[0]["target_title"] == "ev-does-not-exist"


def test_no_tensions_at_all_is_a_clean_empty_state() -> None:
    detail = _detail()
    assert detail["assessment_counterevidence"] == []
    assert detail["evidence_contradictions"] == []


# --- No inference: semantic similarity must never populate tensions --------


def test_similarly_worded_assessments_never_produce_a_tension_without_explicit_link() -> None:
    # Two Assessments that plainly disagree in prose, with zero explicit
    # counterevidence_ids -- the mission explicitly forbids inferring
    # disagreement from wording/similarity, so this must stay empty.
    a1 = {"id": "assessment-1", "title": "Prices are rising", "strategic_question_ids": ["sq-fixture"], "fact_ids": []}
    a2 = {"id": "assessment-2", "title": "Prices are not rising", "strategic_question_ids": ["sq-fixture"], "fact_ids": []}
    detail = _detail(assessments=[a1, a2])
    assert detail["assessment_counterevidence"] == []


# --- Real production data: rich, sparse, and counterevidence questions -----


def test_real_rich_question_renders_all_sections():
    page = client.get(f"/strategic-questions/{REAL_SQ_RICH}")
    assert page.status_code == 200
    assert "What we know" in page.text
    assert "What we think" in page.text
    assert "What we are watching" in page.text
    assert "Tensions / contradictions" in page.text
    assert "What we don't know" in page.text
    assert "supporting evidence" in page.text


def test_real_sparse_question_renders_honest_empty_states():
    page = client.get(f"/strategic-questions/{REAL_SQ_SPARSE}")
    assert page.status_code == 200
    assert "No explicit counterevidence or contradiction recorded for this question yet." in page.text


def test_real_question_with_counterevidence_shows_it():
    page = client.get(f"/strategic-questions/{REAL_SQ_WITH_COUNTEREVIDENCE}")
    assert page.status_code == 200
    assert "Assessment counterevidence" in page.text
    assert "COUNTEREVIDENCE" in page.text


def test_real_question_shows_mixed_ai_proposed_and_reviewed_assessments():
    # sq-competitor-expansion carries one AI-proposed and one reviewed
    # Assessment in real production data -- both badges must appear
    # distinctly on the same page, neither upgraded nor downgraded.
    page = client.get(f"/strategic-questions/{REAL_SQ_WITH_COUNTEREVIDENCE}")
    assert page.status_code == 200
    assert "AI PROPOSED" in page.text
    assert "REVIEWED" in page.text


def test_strategic_question_detail_404_for_unknown_id_never_crashes():
    resp = client.get("/strategic-questions/sq-does-not-exist-acceptance-check")
    assert resp.status_code == 404


# --- Brief Pack decision-pack link ------------------------------------------


def test_brief_pack_link_present_when_question_has_signals_or_assessments():
    page = client.get(f"/strategic-questions/{REAL_SQ_RICH}")
    assert "/brief-pack?title=" in page.text
    assert "Add to Brief Pack" in page.text


def test_brief_pack_link_and_watch_toggle_absent_when_static_build_true():
    # static_build gates the whole action block (same pattern as the
    # pre-existing Watch/Unwatch toggle) -- proven by rendering the real
    # template directly with static_build=True, the same context shape
    # build_static.py actually uses.
    from scripts.build_static import render as static_render

    detail = _detail(
        sq_id="sq-fixture",
        signals=[{"id": "sig-x", "title": "S", "strategic_question_ids": ["sq-fixture"]}],
        assessments=[{"id": "assessment-x", "title": "A", "strategic_question_ids": ["sq-fixture"], "fact_ids": []}],
    )
    body = static_render(
        "strategic_question_detail.html",
        "/strategic-questions/sq-fixture",
        {"sq": detail, "authoring_mode": False},
    )
    assert "Add to Brief Pack" not in body
    assert "Add to watchlist" not in body


# --- No trust mutation on GET; Watchlist mark-seen discipline --------------


def test_viewing_strategic_question_never_mutates_review_events(tmp_path, monkeypatch) -> None:
    from app import main
    from app.services.review_events import load_review_events

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    before = len(load_review_events(tmp_path))
    client.get(f"/strategic-questions/{REAL_SQ_RICH}")
    client.get(f"/strategic-questions/{REAL_SQ_WITH_COUNTEREVIDENCE}")
    after = len(load_review_events(tmp_path))
    assert before == after == 0


def test_viewing_strategic_question_does_not_mark_any_watch_seen(tmp_path, monkeypatch) -> None:
    from app import main
    from app.services.watchlist import add_watch, load_watches

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    add_watch(tmp_path, "strategic_question", REAL_SQ_RICH)
    client.get(f"/strategic-questions/{REAL_SQ_RICH}")
    watch = load_watches(tmp_path)[0]
    assert watch["last_seen_at"] is None  # only /watches/open marks seen, never a direct page render


def test_strategic_question_page_never_writes_to_inbox(tmp_path, monkeypatch) -> None:
    from app import main

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client.get(f"/strategic-questions/{REAL_SQ_RICH}")
    assert list(tmp_path.iterdir()) == []


# --- No new persistence / no duplicated body -------------------------------


def test_tensions_never_copy_full_statement_bodies_beyond_what_fact_detail_already_shows() -> None:
    # The counterevidence item carries the Fact's own statement text (the
    # same short field Fact records already expose everywhere else in
    # this app, e.g. strategic_question_detail's own "What we know"
    # section) -- not a full article/transcript body. No new field beyond
    # what the existing Fact/Evidence schema already authors.
    fact = {"id": "fact-1", "statement": "A short factual statement.", "strategic_question_ids": []}
    assessment = {
        "id": "assessment-x", "title": "An assessment", "strategic_question_ids": ["sq-fixture"],
        "fact_ids": ["fact-1"], "counterevidence_ids": ["fact-1"],
    }
    detail = _detail(assessments=[assessment], facts=[fact])
    item = detail["assessment_counterevidence"][0]["counterevidence_items"][0]
    assert item["statement"] == "A short factual statement."
    assert set(item.keys()) == {"id", "kind", "statement", "href"}
