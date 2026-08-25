"""Intelligence Lineage & Provenance Navigation V1.

Closes the Evidence-detail reverse-lineage gap: Signals and Assessments
already show supporting Evidence forward, but Evidence pages were dead ends
for walking back up the chain. Reuses LineageQueryService (+ RequestCorpus
membership indexes when bound). Does not invent edges, mutate trust on GET,
duplicate article/transcript bodies, or reverse-query Saved Brief Packs
(private inbox; forward Add-to-Brief-Pack links from PR #180 remain).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.queries.lineage import LineageQueryService
from app.services.request_corpus import RequestCorpus, bind_request_corpus, reset_request_corpus

client = TestClient(app)

ROOT = Path(__file__).resolve().parents[1]

# Evidence cited by both a Signal and an Assessment (explicit ids).
EVIDENCE_WITH_DOWNSTREAM = "ev-cfia-blueberry-index"
# Evidence with no Signal/Assessment citations in seed data.
EVIDENCE_SPARSE = "ev-20260806173538-5271-breeding-better-blueberries-nc-state-uni"
# Signal that cites EVIDENCE_WITH_DOWNSTREAM (or another known cite).
REAL_SIGNAL_ID = "sig-financial-owners-taking-positions-in-berry-genetics"
REAL_ASSESSMENT_AI = "assessment-blueberry-genetics-commercialized-through-platforms"


class _FakeSignalRepo:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def list(self) -> list[dict]:
        return self._rows


class _FakeAssessmentRepo:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def list(self) -> list[dict]:
        return self._rows


class _FakeRepos:
    def __init__(self, *, signals: list[dict] | None = None, assessments: list[dict] | None = None) -> None:
        self.signals = _FakeSignalRepo(signals or [])
        self.assessments = _FakeAssessmentRepo(assessments or [])


# --- LineageQueryService reverse helpers (unit) ----------------------------


def test_resolve_signals_citing_evidence_finds_direct_citation() -> None:
    repos = _FakeRepos(
        signals=[
            {"id": "sig-a", "evidence_ids": ["ev-target"]},
            {"id": "sig-b", "evidence_ids": ["ev-other"]},
        ]
    )
    lineage = LineageQueryService(repos)
    assert [s["id"] for s in lineage.resolve_signals_citing_evidence("ev-target")] == ["sig-a"]


def test_resolve_assessments_citing_evidence_finds_direct_citation() -> None:
    repos = _FakeRepos(
        assessments=[
            {"id": "assessment-a", "evidence_ids": ["ev-target"], "ai_proposed": True},
            {"id": "assessment-b", "evidence_ids": ["ev-other"]},
        ]
    )
    lineage = LineageQueryService(repos)
    result = lineage.resolve_assessments_citing_evidence("ev-target")
    assert [a["id"] for a in result] == ["assessment-a"]
    assert result[0]["ai_proposed"] is True


def test_sparse_evidence_reverse_lookups_return_empty_not_crash() -> None:
    lineage = LineageQueryService(
        _FakeRepos(
            signals=[{"id": "sig-a", "evidence_ids": ["ev-other"]}],
            assessments=[{"id": "assessment-a", "evidence_ids": []}],
        )
    )
    assert lineage.resolve_signals_citing_evidence("ev-nobody") == []
    assert lineage.resolve_assessments_citing_evidence("ev-nobody") == []


def test_stale_signal_id_on_assessment_does_not_fabricate_evidence_edge() -> None:
    """Assessments that cite a Signal do not count as citing that Signal's Evidence."""
    lineage = LineageQueryService(
        _FakeRepos(
            signals=[{"id": "sig-a", "evidence_ids": ["ev-real"]}],
            assessments=[{"id": "assessment-a", "signal_ids": ["sig-a"], "evidence_ids": []}],
        )
    )
    assert lineage.resolve_assessments_citing_evidence("ev-real") == []


def test_request_corpus_membership_index_matches_repo_scan() -> None:
    corpus = RequestCorpus(data_dir=ROOT / "data", schemas_dir=ROOT / "schemas")
    token = bind_request_corpus(corpus)
    try:
        lineage = LineageQueryService(corpus.repos())
        via_index = lineage.resolve_signals_citing_evidence(EVIDENCE_WITH_DOWNSTREAM)
        via_scan = [
            s
            for s in corpus.signals
            if EVIDENCE_WITH_DOWNSTREAM in (s.get("evidence_ids") or [])
        ]
        assert [s["id"] for s in via_index] == [s["id"] for s in via_scan]
        assert via_index  # seed must actually cite this Evidence
    finally:
        reset_request_corpus(token)


# --- Evidence detail route wiring ------------------------------------------


def test_evidence_detail_shows_citing_signals_and_assessments() -> None:
    page = client.get(f"/evidence/{EVIDENCE_WITH_DOWNSTREAM}")
    assert page.status_code == 200
    assert "Signals that cite this evidence" in page.text
    assert "Assessments that cite this evidence" in page.text
    assert 'href="/signals/' in page.text
    assert 'href="/assessments/' in page.text
    # Upstream provenance already present (Source / parent / transcript fields).
    assert "Source" in page.text


def test_sparse_evidence_shows_honest_empty_downstream_states() -> None:
    page = client.get(f"/evidence/{EVIDENCE_SPARSE}")
    assert page.status_code == 200
    assert "No signal has cited this evidence yet." in page.text
    assert "No assessment has cited this evidence yet." in page.text


def test_evidence_detail_preserves_ai_proposed_badge_on_citing_assessment(monkeypatch) -> None:
    real_qs = main.get_query_services(main.DATA_DIR, main.SCHEMAS_DIR)

    class FakeLineage:
        def resolve_signals_citing_evidence(self, evidence_id):
            return [{"id": "sig-fixture", "title": "Fixture signal", "status": "proposed"}]

        def resolve_assessments_citing_evidence(self, evidence_id):
            return [
                {
                    "id": "assessment-fixture-ai",
                    "title": "Fixture AI reading",
                    "ai_proposed": True,
                }
            ]

        def resolve_linked_strategic_questions(self, ids):
            return []

    class FakeQueryServices:
        lineage = FakeLineage()
        reference = real_qs.reference

    monkeypatch.setattr(main, "get_query_services", lambda *a, **k: FakeQueryServices())
    page = client.get(f"/evidence/{EVIDENCE_SPARSE}")
    assert page.status_code == 200
    assert "Fixture signal" in page.text
    assert "PROPOSED" in page.text
    assert "Fixture AI reading" in page.text
    assert "AI PROPOSED" in page.text
    assert "Lineage is not endorsement" in page.text


def test_evidence_detail_404_unknown_id() -> None:
    assert client.get("/evidence/ev-does-not-exist-anywhere").status_code == 404


def test_evidence_get_does_not_mutate_trusted_record() -> None:
    path = next((ROOT / "data" / "evidence").rglob(f"{EVIDENCE_WITH_DOWNSTREAM}*.json"), None)
    if path is None:
        path = ROOT / "data" / "evidence" / f"{EVIDENCE_WITH_DOWNSTREAM}.json"
    assert path.is_file()
    before = path.read_bytes()
    mtime_before = path.stat().st_mtime_ns
    assert client.get(f"/evidence/{EVIDENCE_WITH_DOWNSTREAM}").status_code == 200
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == mtime_before


def test_evidence_detail_does_not_duplicate_source_article_body_as_lineage_payload() -> None:
    page = client.get(f"/evidence/{EVIDENCE_WITH_DOWNSTREAM}")
    assert page.status_code == 200
    # Lineage sections are link lists — not a second copy of transcript/body storage.
    assert "Signals that cite this evidence" in page.text
    assert "transcript_body" not in page.text
    assert "full_text" not in page.text


def test_brief_pack_inclusion_not_shown_as_trust_upgrade_on_evidence() -> None:
    """V1 deliberately omits Saved Brief Pack reverse on Evidence (private)."""
    page = client.get(f"/evidence/{EVIDENCE_WITH_DOWNSTREAM}")
    assert page.status_code == 200
    assert "used in saved packs" not in page.text.lower()
    assert "Brief Pack inclusion" not in page.text
    # Nav still lists Saved Brief Packs globally; that must not appear as a
    # trust claim inside the Evidence lineage sections.
    lineage_idx = page.text.index("Signals that cite this evidence")
    lineage_chunk = page.text[lineage_idx : lineage_idx + 2500]
    assert "Saved Brief Pack" not in lineage_chunk
    assert "Lineage is not endorsement" in lineage_chunk


# --- PR #180 surfaces preserved --------------------------------------------


def test_signal_detail_citing_assessments_and_brief_pack_link_still_present() -> None:
    page = client.get(f"/signals/{REAL_SIGNAL_ID}")
    assert page.status_code == 200
    assert "What analysts think this means" in page.text
    assert f"/brief-pack?signals={REAL_SIGNAL_ID}" in page.text


def test_assessment_detail_why_it_matters_and_brief_pack_link_still_present() -> None:
    page = client.get(f"/assessments/{REAL_ASSESSMENT_AI}")
    assert page.status_code == 200
    # Real AI-proposed assessment still badges correctly.
    assert "AI PROPOSED" in page.text
    assert f"/brief-pack?assessments={REAL_ASSESSMENT_AI}" in page.text


def test_signal_assessment_evidence_cross_nav_links_exist_where_explicit() -> None:
    # Forward: signal still links supporting evidence.
    sig_page = client.get(f"/signals/{REAL_SIGNAL_ID}")
    assert 'href="/evidence/' in sig_page.text
    # Reverse: evidence that cites into signals links back.
    ev = json.loads((ROOT / "data" / "signals" / f"{REAL_SIGNAL_ID}.json").read_text())
    evidence_ids = ev.get("evidence_ids") or []
    assert evidence_ids
    ev_page = client.get(f"/evidence/{evidence_ids[0]}")
    assert ev_page.status_code == 200
    assert f'href="/signals/{REAL_SIGNAL_ID}"' in ev_page.text
