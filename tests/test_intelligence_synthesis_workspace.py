"""Intelligence Synthesis Workspace V1 -- closes two real, schema-supported
gaps found in the already-substantial Signal/Assessment detail pages
(app/main.py's signal_detail()/assessment_detail(), already static-built
and already showing supporting Evidence/Facts/Entities/Strategic
Questions): a Signal detail page did not show which Assessments cite it
(the Signal -> Assessment half of the intelligence chain was invisible),
and an Assessment's `why_it_matters` field was silently dropped by its
own detail template despite being read by every other consumer
(Strategic Question Workspace, Brief Pack). Both fixes reuse existing
infrastructure (LineageQueryService, compose_brief_pack's /brief-pack
query params) -- no new persistence, no new trust route, no second
review queue."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.queries.lineage import LineageQueryService

client = TestClient(app)

REAL_SIGNAL_ID = "sig-financial-owners-taking-positions-in-berry-genetics"
REAL_ASSESSMENT_WITH_WHY = "assessment-financial-capital-entering-berry-genetics-ownership"
REAL_ASSESSMENT_WITHOUT_SIGNAL_IDS = "assessment-blueberry-genetics-commercialized-through-platforms"


class _FakeAssessmentRepo:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def list(self) -> list[dict]:
        return self._rows


class _FakeRepos:
    def __init__(self, assessments: list[dict]) -> None:
        self.assessments = _FakeAssessmentRepo(assessments)


# --- LineageQueryService.resolve_assessments_citing_signal (unit level) ---


def test_resolve_assessments_citing_signal_finds_direct_citation() -> None:
    repos = _FakeRepos([
        {"id": "assessment-a", "signal_ids": ["sig-target"]},
        {"id": "assessment-b", "signal_ids": ["sig-other"]},
    ])
    lineage = LineageQueryService(repos)
    result = lineage.resolve_assessments_citing_signal("sig-target")
    assert [a["id"] for a in result] == ["assessment-a"]


def test_resolve_assessments_citing_signal_sparse_signal_returns_empty_not_crash() -> None:
    repos = _FakeRepos([{"id": "assessment-a", "signal_ids": []}, {"id": "assessment-b"}])
    lineage = LineageQueryService(repos)
    assert lineage.resolve_assessments_citing_signal("sig-nobody-cites-me") == []


def test_resolve_assessments_citing_signal_no_assessments_at_all() -> None:
    lineage = LineageQueryService(_FakeRepos([]))
    assert lineage.resolve_assessments_citing_signal("sig-anything") == []


# --- signal_detail() route: citing_assessments wiring ----------------------


def test_signal_detail_shows_citing_assessments_section_with_ai_and_reviewed_badges(monkeypatch) -> None:
    class FakeLineage:
        def resolve_linked_evidence(self, ids):
            return []

        def resolve_linked_facts(self, ids):
            return []

        def resolve_linked_entities(self, ids, entities):
            return []

        def resolve_linked_strategic_questions(self, ids):
            return []

        def resolve_assessments_citing_signal(self, signal_id):
            return [
                {"id": "assessment-fixture-ai", "title": "Fixture AI-proposed reading", "ai_proposed": True},
                {"id": "assessment-fixture-reviewed", "title": "Fixture reviewed reading", "ai_proposed": False},
            ]

    class FakeQueryServices:
        lineage = FakeLineage()

    monkeypatch.setattr(main, "get_query_services", lambda *a, **k: FakeQueryServices())
    page = client.get(f"/signals/{REAL_SIGNAL_ID}")
    assert page.status_code == 200
    assert "What analysts think this means" in page.text
    assert "Fixture AI-proposed reading" in page.text
    assert "Fixture reviewed reading" in page.text
    assert "AI PROPOSED" in page.text
    assert "REVIEWED" in page.text
    assert 'href="/assessments/assessment-fixture-ai"' in page.text


def test_real_signal_with_no_citing_assessments_shows_honest_empty_state() -> None:
    # Real production data: zero Assessments currently populate signal_ids
    # (a genuine, honestly-reported data-completeness fact, not a bug --
    # see tests/test_intelligence_lineage.py's own comment on this).
    page = client.get(f"/signals/{REAL_SIGNAL_ID}")
    assert page.status_code == 200
    assert "No analyst assessment has cited this signal yet." in page.text


def test_signal_detail_404_for_unknown_id_never_crashes() -> None:
    resp = client.get("/signals/sig-does-not-exist-anywhere")
    assert resp.status_code == 404


def test_signal_detail_has_brief_pack_link_on_live_route() -> None:
    page = client.get(f"/signals/{REAL_SIGNAL_ID}")
    assert f"/brief-pack?signals={REAL_SIGNAL_ID}" in page.text


# --- assessment_detail() route: why_it_matters rendering --------------------


def test_real_assessment_with_why_it_matters_renders_it() -> None:
    page = client.get(f"/assessments/{REAL_ASSESSMENT_WITH_WHY}")
    assert page.status_code == 200
    assert "Why it matters" in page.text
    assert "Ownership links can change disclosure" in page.text


def test_assessment_without_why_it_matters_omits_section_not_crash(monkeypatch) -> None:
    class FakeLineage:
        def resolve_linked_facts(self, ids):
            return []

        def resolve_linked_signals(self, ids):
            return []

        def resolve_linked_evidence(self, ids):
            return []

        def resolve_linked_entities(self, ids, entities):
            return []

        def resolve_linked_strategic_questions(self, ids):
            return []

    class FakeQueryServices:
        lineage = FakeLineage()

    monkeypatch.setattr(main, "get_query_services", lambda *a, **k: FakeQueryServices())
    monkeypatch.setattr(
        main,
        "assessment_by_id",
        lambda aid: {
            "id": aid,
            "title": "Sparse fixture assessment",
            "status": "active",
            "rationale": "A bare rationale.",
            "confidence": "low",
            "reviewer": "analyst-x",
            "created_at": "2026-01-01",
            "ai_proposed": False,
        },
    )
    page = client.get("/assessments/assessment-sparse-fixture")
    assert page.status_code == 200
    assert "Why it matters" not in page.text
    assert "No signals linked." in page.text
    assert "No evidence linked." in page.text


def test_assessment_detail_has_brief_pack_link_on_live_route() -> None:
    page = client.get(f"/assessments/{REAL_ASSESSMENT_WITH_WHY}")
    assert f"/brief-pack?assessments={REAL_ASSESSMENT_WITH_WHY}" in page.text


def test_assessment_ai_proposed_vs_reviewed_badge_fidelity_unchanged() -> None:
    # Backward-compatible: the pre-existing badge logic must still work
    # exactly as before this mission touched the template.
    ai_page = client.get("/assessments/assessment-blueberry-genetics-commercialized-through-platforms")
    assert "AI PROPOSED" in ai_page.text


def test_assessment_detail_404_for_unknown_id_never_crashes() -> None:
    resp = client.get("/assessments/assessment-does-not-exist")
    assert resp.status_code == 404


# --- backward compatibility: existing content still renders -----------------


def test_signal_detail_still_shows_decision_test_and_evidence_table() -> None:
    page = client.get(f"/signals/{REAL_SIGNAL_ID}")
    assert "Decision test" in page.text
    assert 'class="brief-table evidence-link-table"' in page.text


def test_assessment_detail_still_shows_would_change_our_view_and_counterevidence() -> None:
    page = client.get(f"/assessments/{REAL_ASSESSMENT_WITH_WHY}")
    assert "Would change our view" in page.text
    assert "Counterevidence" in page.text


# --- no trust mutation on read; no body persistence --------------------------


def test_viewing_signal_and_assessment_pages_never_mutates_review_events(tmp_path, monkeypatch) -> None:
    from app.services.review_events import load_review_events

    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    before = len(load_review_events(tmp_path))
    client.get(f"/signals/{REAL_SIGNAL_ID}")
    client.get(f"/assessments/{REAL_ASSESSMENT_WITH_WHY}")
    client.get(f"/signals/{REAL_SIGNAL_ID}")
    after = len(load_review_events(tmp_path))
    assert before == after == 0


def test_signal_and_assessment_detail_never_write_to_inbox(tmp_path, monkeypatch) -> None:
    # This mission added zero new persistence. INBOX_DIR starts empty and
    # neither read-only detail route should create anything under it.
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    client.get(f"/signals/{REAL_SIGNAL_ID}")
    client.get(f"/assessments/{REAL_ASSESSMENT_WITH_WHY}")
    assert list(tmp_path.iterdir()) == []
