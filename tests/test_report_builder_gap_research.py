"""Report Quality & Public Gap Research V1.

Deterministic AVAILABLE/PARTIAL/MISSING coverage dimensions
(app.services.report_builder.coverage_dimensions), the explicit
per-gap "Research missing public information" workflow, external
finding review/inclusion, and the "Send to Evidence Review" promotion
path. External research must never silently become trusted canonical
Evidence, must never leak private packet content (Assessment rationale,
Signal observation, report prose) to the provider, and a report must
work fine with no research ever run.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.services.ai_gateway.results import ResearchCitation, ResearchResponse, NormalizedUsage
from app.services.report_builder.coverage import report_coverage
from app.services.report_builder.coverage_dimensions import (
    AVAILABLE,
    MISSING,
    PARTIAL,
    report_coverage_dimensions,
)
from app.services.report_builder.packet import build_report_packet
from app.services.report_builder.perplexity_gap_research import (
    DEFAULT_RESEARCH_MODEL,
    PublicQueryContext,
    research_public_gaps,
)
from app.services.report_builder.reports_store import (
    append_research_batch,
    create_report,
    find_research_finding,
    load_report,
    update_research_finding,
)
from app.services.report_builder.research_evidence_draft import build_perplexity_research_draft
from app.services.report_builder.scope import ResolvedScope


def _entity(**overrides):
    row = {"record_type": "entity", "status": "active", "aliases": [], "berry_ids": [], "attributes": {}}
    row.update(overrides)
    return row


def _evidence(**overrides):
    row = {
        "id": "ev-1",
        "record_type": "evidence",
        "status": "published",
        "title": "An article",
        "source_name": "Some Source",
        "source_type": "trade_press",
        "published_date": "2026-06-01",
        "berry_ids": ["berry-blueberry"],
        "entity_ids": [],
        "tags": [],
    }
    row.update(overrides)
    return row


BERRIES = {"berry-blueberry": "Blueberry"}


def _entities():
    return {
        "company-fallcreek": _entity(id="company-fallcreek", entity_type="company", name="Fall Creek", berry_ids=["berry-blueberry"]),
    }


def _scope(**overrides):
    base = dict(
        report_type="market_landscape",
        berry_id="berry-blueberry",
        geography_ids=(),
        company_ids=(),
        variety_ids=(),
        strategic_question_id=None,
        date_window_days=None,
        focus_notes="",
    )
    base.update(overrides)
    return ResolvedScope(**base)


def _packet(evidence, **scope_overrides):
    return build_report_packet(
        _scope(**scope_overrides),
        entities=_entities(),
        relationships=[],
        published_evidence=evidence,
        facts=[],
        signals=[],
        assessments=[],
        strategic_questions=[],
        recommendations=[],
        variety_candidates=[],
        berry_labels=BERRIES,
    )


# --- 1. Deterministic AVAILABLE/PARTIAL/MISSING states ----------------------


def test_dimension_missing_when_zero_partial_when_thin_available_when_three_plus():
    zero = _packet([])
    one = _packet([_evidence(id="ev-a", tags=["Berry acreage expansion"])])
    three = _packet([
        _evidence(id="ev-a", tags=["Berry acreage expansion"]),
        _evidence(id="ev-b", tags=["Mexico berry production"]),
        _evidence(id="ev-c", tags=["Berry harvest forecast"]),
    ])
    dims_zero = {d["key"]: d for d in report_coverage_dimensions(zero, report_type="market_landscape", counts={})}
    dims_one = {d["key"]: d for d in report_coverage_dimensions(one, report_type="market_landscape", counts={})}
    dims_three = {d["key"]: d for d in report_coverage_dimensions(three, report_type="market_landscape", counts={})}
    assert dims_zero["production_acreage"]["status"] == MISSING
    assert dims_one["production_acreage"]["status"] == PARTIAL
    assert dims_three["production_acreage"]["status"] == AVAILABLE
    for d in (dims_zero, dims_one, dims_three):
        assert d["production_acreage"]["explanation"]  # every status is explainable


def test_every_dimension_status_is_one_of_three_fixed_states():
    packet = _packet([_evidence(id="ev-a", tags=["Berry export volume"])])
    for report_type in ("market_landscape", "competitive_landscape", "competitor_comparison", "variety_genetics_landscape", "strategic_question_brief"):
        for dim in report_coverage_dimensions(packet, report_type=report_type, counts={}):
            assert dim["status"] in (AVAILABLE, PARTIAL, MISSING)


# --- 2. No LLM involvement in gap classification -----------------------------


def test_coverage_dimensions_module_imports_no_ai_gateway():
    import app.services.report_builder.coverage_dimensions as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "ai_gateway" not in source
    assert "completer" not in source.lower()


def test_gap_classification_is_deterministic_across_repeated_calls():
    packet = _packet([_evidence(id="ev-a", tags=["Berry tariff"])])
    first = report_coverage_dimensions(packet, report_type="market_landscape", counts={})
    second = report_coverage_dimensions(packet, report_type="market_landscape", counts={})
    assert first == second


# --- 5. Proprietary marker strings never reach the classifier/provider ------


def test_evidence_topic_signals_never_carry_summary_or_rationale_text():
    evidence = [_evidence(id="ev-a", tags=["Berry export volume"], summary="SECRET_MARKER_internal_strategy", why_it_matters="PRIVATE_MARKER")]
    packet = _packet(evidence)
    for row in packet["evidence_topic_signals"]:
        assert "SECRET_MARKER" not in json.dumps(row)
        assert "PRIVATE_MARKER" not in json.dumps(row)
    dims = report_coverage_dimensions(packet, report_type="market_landscape", counts={})
    assert "SECRET_MARKER" not in json.dumps(dims)
    assert "PRIVATE_MARKER" not in json.dumps(dims)


def test_research_question_contains_only_public_scope_labels():
    packet = _packet([], geography_ids=())
    dims = {d["key"]: d for d in report_coverage_dimensions(packet, report_type="market_landscape", counts={}, berry_label="Blueberry", geography_labels=("Spain",))}
    q = dims["trade_import_export"]["research_question"]
    assert "Blueberry" in q and "Spain" in q
    assert "SECRET" not in q


# --- 6/7. External finding must have a source; invalid citations rejected ---


class _FakeClient:
    def __init__(self, citations, content="Some public summary text.", provider="perplexity"):
        self._citations = citations
        self._content = content
        self._provider = provider

    def research(self, query, *, model, web_enabled=True, citations=True):
        return ResearchResponse(
            provider=self._provider,
            model=model,
            content=self._content,
            citations=self._citations,
            web_enabled=web_enabled,
            usage=NormalizedUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            latency_seconds=0.1,
        )


def test_every_returned_finding_has_a_nonempty_source_url():
    context = PublicQueryContext(berry_label="Blueberry", geography_labels=(), company_names=(), variety_names=(), question="q")
    proposals, _msg = research_public_gaps(
        context,
        research_client_factory=lambda: _FakeClient((ResearchCitation(url="https://example.test/a", title="A"),)),
        gap_key="trade_import_export",
        gap_label="Trade / import-export data",
    )
    assert len(proposals) == 1
    assert proposals[0].url == "https://example.test/a"


def test_citations_with_empty_url_are_rejected():
    context = PublicQueryContext(berry_label="Blueberry", geography_labels=(), company_names=(), variety_names=(), question="q")
    proposals, _msg = research_public_gaps(
        context,
        research_client_factory=lambda: _FakeClient(
            (ResearchCitation(url="", title="Bad"), ResearchCitation(url="https://example.test/b", title="Good"))
        ),
        gap_key="trade_import_export",
        gap_label="Trade / import-export data",
    )
    assert len(proposals) == 1
    assert proposals[0].url == "https://example.test/b"


def test_default_research_model_is_provider_prefixed_for_the_live_agent_endpoint():
    # A bare "sonar" 400s against the real Perplexity Agent endpoint
    # (GET /v1/models requires the provider-prefixed form, e.g. the
    # already-used "anthropic/claude-haiku-4-5" convention). Regression
    # guard for a genuine production-blocking bug caught during Report
    # Quality & Public Gap Research V1's live acceptance run.
    assert "/" in DEFAULT_RESEARCH_MODEL
    assert DEFAULT_RESEARCH_MODEL.startswith("perplexity/")


# --- 15. Sparse/no-result research handling ----------------------------------


def test_zero_citations_returns_empty_with_explanatory_status():
    context = PublicQueryContext(berry_label="Blueberry", geography_labels=(), company_names=(), variety_names=(), question="q")
    proposals, msg = research_public_gaps(
        context, research_client_factory=lambda: _FakeClient(()), gap_key="production_acreage", gap_label="Production volume & acreage",
    )
    assert proposals == []
    assert "No citable public sources" in msg


# --- 16. Provider failure handling -------------------------------------------


def test_provider_exception_degrades_to_status_message_not_a_raise():
    class _Boom:
        def research(self, *a, **k):
            raise RuntimeError("network exploded")

    context = PublicQueryContext(berry_label="Blueberry", geography_labels=(), company_names=(), variety_names=(), question="q")
    proposals, msg = research_public_gaps(context, research_client_factory=_Boom, gap_key="k", gap_label="L")
    assert proposals == []
    assert "Public gap research failed" in msg


def test_no_provider_credential_degrades_cleanly():
    context = PublicQueryContext(berry_label="Blueberry", geography_labels=(), company_names=(), variety_names=(), question="q")
    proposals, msg = research_public_gaps(context, research_client_factory=None)
    assert proposals == []
    assert "no provider credential" in msg


# --- 8/9/10. Unreviewed by default; include/exclude; batch history persists -


def test_appended_batch_findings_default_unreviewed_and_excluded(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(inbox, title="R", report_type="market_landscape", scope={}, sections=[])
    append_research_batch(
        inbox,
        record["id"],
        gap_keys=["production_acreage"],
        entries=[{"title": "T", "url": "https://example.test/a", "snippet": "s", "source": "perplexity_public_research", "provider": "perplexity", "retrieved_at": "2026-09-01T00:00:00+00:00", "gap_key": "production_acreage", "gap_label": "Production volume & acreage"}],
        status_messages={"production_acreage": "Found 1 public source(s)."},
    )
    reloaded = load_report(inbox, record["id"])
    finding = reloaded["external_research_appendix"][0]
    assert finding["reviewed"] is False
    assert finding["included_in_report"] is False
    assert finding["sent_to_review_draft_id"] is None
    assert reloaded["research_batches"][0]["gap_keys"] == ["production_acreage"]
    assert reloaded["research_batches"][0]["finding_count"] == 1


def test_include_exclude_toggle_only_affects_the_targeted_finding(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(inbox, title="R", report_type="market_landscape", scope={}, sections=[])
    append_research_batch(
        inbox, record["id"], gap_keys=["k"],
        entries=[
            {"title": "A", "url": "https://example.test/a", "snippet": "s"},
            {"title": "B", "url": "https://example.test/b", "snippet": "s"},
        ],
        status_messages={"k": "ok"},
    )
    reloaded = load_report(inbox, record["id"])
    first_id = reloaded["external_research_appendix"][0]["id"]
    update_research_finding(inbox, record["id"], first_id, included_in_report=True, reviewed=True)
    reloaded = load_report(inbox, record["id"])
    a, b = reloaded["external_research_appendix"]
    assert a["included_in_report"] is True and a["reviewed"] is True
    assert b["included_in_report"] is False and b["reviewed"] is False


def test_research_again_appends_a_new_batch_never_overwrites_prior(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(inbox, title="R", report_type="market_landscape", scope={}, sections=[])
    append_research_batch(inbox, record["id"], gap_keys=["k1"], entries=[{"title": "A", "url": "https://example.test/a", "snippet": "s"}], status_messages={"k1": "ok"})
    append_research_batch(inbox, record["id"], gap_keys=["k2"], entries=[{"title": "B", "url": "https://example.test/b", "snippet": "s"}], status_messages={"k2": "ok"})
    reloaded = load_report(inbox, record["id"])
    assert len(reloaded["research_batches"]) == 2
    assert len(reloaded["external_research_appendix"]) == 2
    assert reloaded["research_batches"][0]["id"] != reloaded["research_batches"][1]["id"]


# --- 3/11. Explicit analyst action only; reopen never silently re-queries ---


def test_route_get_reports_never_triggers_research(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    record = create_report(tmp_path / "inbox", title="R", report_type="market_landscape", scope={}, sections=[])

    def _boom(*args, **kwargs):
        raise AssertionError("research_public_gaps must never be called on a GET")

    monkeypatch.setattr(main, "research_public_gaps", _boom)
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "all_facts", lambda: [])
    monkeypatch.setattr(main, "all_recommendations", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    monkeypatch.setattr(main, "load_strategic_questions", lambda: [])
    monkeypatch.setattr(main, "entity_index", lambda: {})
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))
    response = TestClient(main.app).get(f"/reports/{record['id']}")
    assert response.status_code == 200


def test_route_research_gaps_with_no_selection_is_a_noop(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    record = create_report(tmp_path / "inbox", title="R", report_type="market_landscape", scope={}, sections=[])

    def _boom(*args, **kwargs):
        raise AssertionError("research_public_gaps must never be called with no gap selected")

    monkeypatch.setattr(main, "research_public_gaps", _boom)
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "all_facts", lambda: [])
    monkeypatch.setattr(main, "all_recommendations", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    monkeypatch.setattr(main, "load_strategic_questions", lambda: [])
    monkeypatch.setattr(main, "entity_index", lambda: {})
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))
    response = TestClient(main.app).post(f"/reports/{record['id']}/research-gaps", data={}, follow_redirects=False)
    assert response.status_code == 303
    reloaded = load_report(tmp_path / "inbox", record["id"])
    assert reloaded["external_research_appendix"] == []
    assert reloaded["research_batches"] == []


def test_route_research_gaps_only_accepts_researchable_selected_keys(monkeypatch, tmp_path: Path):
    """A tampered form posting a non-researchable dimension key (e.g.
    'signals') must never trigger a provider call for it."""
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    record = create_report(tmp_path / "inbox", title="R", report_type="market_landscape", scope={}, sections=[])
    called_with = []

    def _fake_research(context, *, research_client_factory, gap_key="", gap_label="", **kw):
        called_with.append(gap_key)
        return [], "no-op"

    monkeypatch.setattr(main, "research_public_gaps", _fake_research)
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "all_facts", lambda: [])
    monkeypatch.setattr(main, "all_recommendations", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    monkeypatch.setattr(main, "load_strategic_questions", lambda: [])
    monkeypatch.setattr(main, "entity_index", lambda: {})
    monkeypatch.setattr(main, "variety_candidate_universe", lambda: ([], [], {}))
    response = TestClient(main.app).post(
        f"/reports/{record['id']}/research-gaps",
        data={"gap_keys": ["signals", "production_acreage"]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert called_with == ["production_acreage"]


def test_route_finding_state_toggles_include_and_reviewed(monkeypatch, tmp_path: Path):
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    record = create_report(inbox, title="R", report_type="market_landscape", scope={}, sections=[])
    append_research_batch(
        inbox, record["id"], gap_keys=["k"],
        entries=[{"title": "Finding", "url": "https://example.test/a", "snippet": "s"}],
        status_messages={"k": "ok"},
    )
    finding_id = load_report(inbox, record["id"])["external_research_appendix"][0]["id"]
    response = TestClient(main.app).post(
        f"/reports/{record['id']}/research/{finding_id}/state",
        data={"reviewed": "true", "included_in_report": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    reloaded = load_report(inbox, record["id"])
    finding = reloaded["external_research_appendix"][0]
    assert finding["reviewed"] is True
    assert finding["included_in_report"] is True
    # Toggling never merges the finding into sections.
    assert reloaded["sections"] == []


# --- 12. PDF labels external research ----------------------------------------


def test_pdf_renders_only_included_findings_and_labels_them_external():
    from app.services.report_builder.pdf_export import render_report_pdf

    report = {
        "id": "rp-x",
        "title": "R",
        "report_type": "market_landscape",
        "scope": {},
        "sections": [],
        "external_research_appendix": [
            {"title": "Included finding", "url": "https://example.test/a", "gap_label": "Trade", "provider": "perplexity", "retrieved_at": "2026-09-01T00:00:00+00:00", "included_in_report": True},
            {"title": "Excluded finding", "url": "https://example.test/b", "included_in_report": False},
        ],
    }
    packet = _packet([])
    coverage = report_coverage(packet)
    pdf_bytes = render_report_pdf(report, packet, coverage)
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_renders_fine_with_zero_research_ever_run():
    from app.services.report_builder.pdf_export import render_report_pdf

    report = {"id": "rp-x", "title": "R", "report_type": "market_landscape", "scope": {}, "sections": [], "external_research_appendix": []}
    packet = _packet([])
    coverage = report_coverage(packet)
    pdf_bytes = render_report_pdf(report, packet, coverage)
    assert pdf_bytes.startswith(b"%PDF")


# --- 13/14. Trust path: promotion draft is a draft, not canonical -----------


def test_promoted_draft_is_unpublished_and_never_duplicates_article_body():
    finding = {
        "title": "US blueberry acreage report",
        "url": "https://example.test/report",
        "snippet": "Public snippet text.",
        "provider": "perplexity",
        "gap_key": "production_acreage",
        "gap_label": "Production volume & acreage",
    }
    draft = build_perplexity_research_draft(
        finding, berry_id="berry-blueberry", geography_ids=("geography-united-states",), entity_ids=(), captured_date="2026-09-01",
    )
    assert draft["status"] == "draft"
    assert draft["review_state"] == "in_review"
    assert draft["verification_state"] == "unverified"
    assert draft["does_not_prove"]
    assert "article" not in draft
    assert "transcript" not in draft
    assert draft["source_url"] == finding["url"]
    assert draft["record_type"] == "evidence"


def test_route_send_to_review_writes_draft_via_existing_review_queue(monkeypatch, tmp_path: Path):
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    record = create_report(inbox, title="R", report_type="market_landscape", scope={"berry_id": "berry-blueberry"}, sections=[])
    append_research_batch(
        inbox, record["id"], gap_keys=["production_acreage"],
        entries=[{"title": "Finding", "url": "https://example.test/a", "snippet": "s", "gap_key": "production_acreage", "gap_label": "Production volume & acreage"}],
        status_messages={"production_acreage": "ok"},
    )
    reloaded = load_report(inbox, record["id"])
    finding_id = reloaded["external_research_appendix"][0]["id"]
    response = TestClient(main.app).post(f"/reports/{record['id']}/research/{finding_id}/send-to-review", follow_redirects=False)
    assert response.status_code == 303
    reloaded = load_report(inbox, record["id"])
    draft_id = reloaded["external_research_appendix"][0]["sent_to_review_draft_id"]
    assert draft_id is not None
    draft_path = inbox / "evidence" / f"{draft_id}.json"
    assert draft_path.is_file()
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["status"] == "draft"
    # No canonical trust mutation: nothing was written to published Evidence.
    assert not (tmp_path / "data" / "evidence" / f"{draft_id}.json").exists()


def test_route_send_to_review_is_idempotent_per_finding(monkeypatch, tmp_path: Path):
    inbox = tmp_path / "inbox"
    monkeypatch.setattr(main, "INBOX_DIR", inbox)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    record = create_report(inbox, title="R", report_type="market_landscape", scope={}, sections=[])
    append_research_batch(
        inbox, record["id"], gap_keys=["k"],
        entries=[{"title": "Finding", "url": "https://example.test/a", "snippet": "s"}],
        status_messages={"k": "ok"},
    )
    finding_id = load_report(inbox, record["id"])["external_research_appendix"][0]["id"]
    client = TestClient(main.app)
    client.post(f"/reports/{record['id']}/research/{finding_id}/send-to-review")
    first_draft_id = load_report(inbox, record["id"])["external_research_appendix"][0]["sent_to_review_draft_id"]
    client.post(f"/reports/{record['id']}/research/{finding_id}/send-to-review")
    second_draft_id = load_report(inbox, record["id"])["external_research_appendix"][0]["sent_to_review_draft_id"]
    assert first_draft_id == second_draft_id
    assert len(list((inbox / "evidence").glob("*.json"))) == 1


def test_find_research_finding_returns_none_for_unknown_id(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(inbox, title="R", report_type="market_landscape", scope={}, sections=[])
    assert find_research_finding(record, "rf-does-not-exist") is None


# --- 18. Static/private boundary ---------------------------------------------


def test_new_research_routes_not_registered_in_build_static():
    source = Path("scripts/build_static.py").read_text(encoding="utf-8")
    assert "/research-gaps" not in source
    assert "send-to-review" not in source
