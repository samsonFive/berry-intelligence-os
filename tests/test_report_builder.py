"""AI-Assisted Report Builder V1.

Report prose is report output, not canonical intelligence: nothing in
this feature writes Evidence/Signal/Assessment/Strategic Question/
trusted Variety data. These tests mostly exercise the deterministic
(no AI credential) path for reliability; a handful use a fake completer
to prove the citation-validation and grounding-digest behavior without
a real network call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.ai_gateway.untrusted_complete import UntrustedJsonResult
from app.services.report_builder.coverage import report_coverage
from app.services.report_builder.packet import build_report_packet
from app.services.report_builder.pdf_export import render_report_pdf
from app.services.report_builder.perplexity_gap_research import PublicQueryContext, build_public_query
from app.services.report_builder.reports_store import (
    archive_report,
    create_report,
    load_report,
    replace_section,
    save_report_edits,
)
from app.services.report_builder.scope import (
    ResolvedScope,
    interpret_scope_text,
    resolve_entity_names,
    resolve_geography_text,
    resolve_scope,
)
from app.services.report_builder.synthesis import INSUFFICIENT, UNAVAILABLE, generate_report_sections


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
    }
    row.update(overrides)
    return row


BERRIES = {"berry-blueberry": "Blueberry", "berry-strawberry": "Strawberry"}


def _base_entities():
    rows = [
        _entity(id="company-fallcreek", entity_type="company", name="Fall Creek", berry_ids=["berry-blueberry"]),
        _entity(id="company-driscolls", entity_type="company", name="Driscoll's", berry_ids=["berry-blueberry", "berry-strawberry"]),
        _entity(id="company-sonata-a", entity_type="company", name="Sonata"),
        _entity(id="company-sonata-b", entity_type="company", name="Sonata"),
        _entity(id="variety-alpha", entity_type="variety", name="Alpha", berry_ids=["berry-blueberry"]),
        _entity(id="geography-spain", entity_type="geography", name="Spain"),
        _entity(id="geography-usa", entity_type="geography", name="United States"),
    ]
    return {row["id"]: row for row in rows}


# --- 1/2. Scope interpretation (keyword fallback, no AI credential) -------


def test_us_blueberry_market_request_parses_correctly():
    proposal = interpret_scope_text(
        "Build me a report on the U.S. blueberry market.", berries=BERRIES, completer=None
    )
    assert proposal.report_type == "market_landscape"
    assert proposal.berry_text == "Blueberry"
    assert proposal.source == "keyword_fallback"


def test_european_competitive_landscape_request_parses_correctly():
    proposal = interpret_scope_text(
        "Give me a competitive landscape for blueberry genetics in Europe.", berries=BERRIES, completer=None
    )
    assert proposal.report_type in {"competitive_landscape", "variety_genetics_landscape"}
    assert proposal.berry_text == "Blueberry"


# --- 3/4. Entity resolution -------------------------------------------------


def test_multi_competitor_comparison_resolves_companies():
    entities = list(_base_entities().values())
    results = resolve_entity_names(["Fall Creek", "Driscoll's"], entities=entities, entity_type="company")
    resolved_ids = {r.resolved_id for r in results}
    assert resolved_ids == {"company-fallcreek", "company-driscolls"}


def test_ambiguous_company_requires_resolution():
    entities = list(_base_entities().values())
    results = resolve_entity_names(["Sonata"], entities=entities, entity_type="company")
    assert len(results) == 1
    assert results[0].resolved_id is None
    assert set(results[0].ambiguous_ids) == {"company-sonata-a", "company-sonata-b"}


def test_unresolved_company_name_is_never_silently_dropped_or_guessed():
    entities = list(_base_entities().values())
    proposal_names = ["Fall Creek", "Berry Genetics"]
    results = resolve_entity_names(proposal_names, entities=entities, entity_type="company")
    unresolved = [r.query for r in results if not r.resolved_id and not r.ambiguous_ids]
    assert unresolved == ["Berry Genetics"]


def test_geography_region_resolves_to_member_countries():
    entities = list(_base_entities().values())
    resolution = resolve_geography_text("Europe", entities=entities)
    assert resolution.matched_as == "region"
    assert "geography-spain" in resolution.geography_ids
    assert "geography-usa" not in resolution.geography_ids


def test_unresolved_geography_text_is_honest_not_guessed():
    entities = list(_base_entities().values())
    resolution = resolve_geography_text("Narnia", entities=entities)
    assert resolution.matched_as == "unresolved"
    assert resolution.geography_ids == ()


# --- 5. Strategic Question report packet ------------------------------------


def test_strategic_question_report_packet():
    entities = _base_entities()
    sq = {"id": "sq-1", "title": "Is genetics ownership consolidating?", "berry_ids": ["berry-blueberry"]}
    evidence = [_evidence(id="ev-sq", entity_ids=["company-fallcreek"], strategic_question_ids=["sq-1"])]
    scope = ResolvedScope(
        report_type="strategic_question_brief",
        berry_id=None,
        geography_ids=(),
        company_ids=(),
        variety_ids=(),
        strategic_question_id="sq-1",
        date_window_days=None,
        focus_notes="",
    )
    packet = build_report_packet(
        scope,
        entities=entities,
        relationships=[],
        published_evidence=evidence,
        facts=[],
        signals=[],
        assessments=[],
        strategic_questions=[sq],
        recommendations=[],
        variety_candidates=[],
        berry_labels=BERRIES,
    )
    assert packet["strategic_question"] is not None
    assert packet["strategic_question"]["id"] == "sq-1"
    assert packet["companies"] == []


# --- 6. Date-window handling -------------------------------------------------


def test_date_window_excludes_old_evidence_but_keeps_undated():
    entities = _base_entities()
    evidence = [
        _evidence(id="ev-recent", published_date="2026-08-20", entity_ids=["company-fallcreek"]),
        _evidence(id="ev-old", published_date="2020-01-01", entity_ids=["company-fallcreek"]),
        _evidence(id="ev-undated", published_date=None, entity_ids=["company-fallcreek"]),
    ]
    scope = ResolvedScope(
        report_type="market_landscape",
        berry_id="berry-blueberry",
        geography_ids=(),
        company_ids=("company-fallcreek",),
        variety_ids=(),
        strategic_question_id=None,
        date_window_days=14,
        focus_notes="",
    )
    packet = build_report_packet(
        scope,
        entities=entities,
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
    trace_ids = {row["id"] for row in packet["source_trace"]}
    assert "ev-old" not in trace_ids
    assert "ev-undated" in trace_ids


# --- 7. Provenance preservation ----------------------------------------------


def test_packet_preserves_provenance_per_item():
    entities = _base_entities()
    evidence = [_evidence(id="ev-prov", published_date="2026-05-01", entity_ids=["company-fallcreek"])]
    scope = ResolvedScope(
        report_type="market_landscape",
        berry_id="berry-blueberry",
        geography_ids=(),
        company_ids=("company-fallcreek",),
        variety_ids=(),
        strategic_question_id=None,
        date_window_days=None,
        focus_notes="",
    )
    packet = build_report_packet(
        scope,
        entities=entities,
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
    row = next(r for r in packet["recent_developments"] if r["id"] == "ev-prov")
    assert row["date"] == "2026-05-01"
    assert row["date_basis"] == "published"
    assert row["href"] == "/evidence/ev-prov"
    assert row["trust"] == "trusted"


# --- 8/9. Grounded synthesis + citation validation --------------------------


class _FakeCompleter:
    def __init__(self, response: dict, provider="fake", model="fake-model"):
        self.response = response
        self.provider = provider
        self.model = model
        self.calls = 0

    def __call__(self, prompt, **kwargs):
        self.calls += 1
        return UntrustedJsonResult(parsed=self.response, model=self.model, provider=self.provider)


def _minimal_packet():
    return {
        "report_type": "market_landscape",
        "strategic_question": None,
        "companies": [{"id": "company-fallcreek", "name": "Fall Creek"}],
        "varieties": [],
        "variety_candidates": [],
        "recent_developments": [{"id": "ev-1", "title": "News", "date": "2026-06-01"}],
        "signals": [],
        "assessments": [],
        "source_trace": [{"id": "ev-1", "title": "News"}],
        "known_ids": {"ev-1", "company-fallcreek"},
    }


def test_ai_cannot_cite_nonexistent_evidence():
    packet = _minimal_packet()
    fake = _FakeCompleter({"prose": "Fall Creek expanded.", "citation_ids": ["ev-does-not-exist"]})
    drafts = generate_report_sections(packet, report_type="market_landscape", completer=fake)
    market_context = next(d for d in drafts if d.section_id == "market_context")
    assert market_context.status == "unsupported"
    assert market_context.prose == INSUFFICIENT
    assert market_context.citation_ids == ()


def test_ai_grounded_section_with_valid_citation_is_kept():
    packet = _minimal_packet()
    fake = _FakeCompleter({"prose": "Fall Creek expanded.", "citation_ids": ["ev-1"]})
    drafts = generate_report_sections(packet, report_type="market_landscape", completer=fake)
    market_context = next(d for d in drafts if d.section_id == "market_context")
    assert market_context.status == "ai_draft"
    assert market_context.citation_ids == ("ev-1",)
    assert market_context.provider == "fake"


def test_unsupported_section_stays_explicitly_unsupported_without_calling_model():
    packet = _minimal_packet()
    packet["signals"] = []  # zero coverage for the "signals" section
    fake = _FakeCompleter({"prose": "should not be used", "citation_ids": ["ev-1"]})
    drafts = generate_report_sections(packet, report_type="market_landscape", completer=fake)
    signals_section = next(d for d in drafts if d.section_id == "signals")
    # If the zero-coverage short-circuit had NOT fired, the fake completer
    # would have returned a validly-cited "should not be used" draft
    # (status "ai_draft") -- getting "unsupported" with the fixed
    # INSUFFICIENT phrase instead proves the model was never consulted for
    # this section, without needing to isolate a global call count across
    # every other section in the same report_type.
    assert signals_section.status == "unsupported"
    assert signals_section.prose == INSUFFICIENT
    assert signals_section.citation_ids == ()


def test_no_ai_credential_marks_sections_unavailable_not_fabricated():
    packet = _minimal_packet()
    drafts = generate_report_sections(packet, report_type="market_landscape", completer=None)
    market_context = next(d for d in drafts if d.section_id == "market_context")
    assert market_context.status == "unavailable"
    assert market_context.prose == UNAVAILABLE


def test_structured_sections_never_call_the_model():
    packet = _minimal_packet()
    fake = _FakeCompleter({"prose": "x", "citation_ids": ["ev-1"]})
    generate_report_sections(packet, report_type="market_landscape", completer=fake)
    # sources/known_gaps/scope_method are structured -- only narrative
    # sections with nonzero coverage ever call the fake completer.
    assert fake.calls <= 4


# --- 10. AI output cannot mutate canonical intelligence ----------------------


def test_ai_output_does_not_mutate_canonical_intelligence():
    packet = _minimal_packet()
    original_companies = list(packet["companies"])
    fake = _FakeCompleter({"prose": "Fall Creek expanded.", "citation_ids": ["ev-1"]})
    generate_report_sections(packet, report_type="market_landscape", completer=fake)
    assert packet["companies"] == original_companies  # unchanged by synthesis


# --- 11/12/16. Persistence -----------------------------------------------


def test_saved_report_persists_analyst_edits(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(
        inbox,
        title="Test report",
        report_type="market_landscape",
        scope={"berry_id": "berry-blueberry"},
        sections=[{"section_id": "executive_summary", "title": "Executive Summary", "generated_prose": "Draft.", "edited_prose": None, "citation_ids": [], "status": "ai_draft"}],
    )
    sections = record["sections"]
    sections[0]["edited_prose"] = "Analyst-edited text."
    save_report_edits(inbox, record["id"], sections=sections)
    reloaded = load_report(inbox, record["id"])
    assert reloaded["sections"][0]["edited_prose"] == "Analyst-edited text."
    assert reloaded["sections"][0]["generated_prose"] == "Draft."


def test_regenerate_section_only_replaces_that_section(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(
        inbox,
        title="Test report",
        report_type="market_landscape",
        scope={},
        sections=[
            {"section_id": "executive_summary", "title": "Executive Summary", "generated_prose": "A", "edited_prose": "A-edited", "citation_ids": [], "status": "ai_draft"},
            {"section_id": "market_context", "title": "Market Context", "generated_prose": "B", "edited_prose": None, "citation_ids": [], "status": "ai_draft"},
        ],
    )
    replace_section(
        inbox, record["id"], "market_context",
        generated_prose="B-regenerated", citation_ids=["ev-1"], status="ai_draft", provider="fake", model="fake-model",
    )
    reloaded = load_report(inbox, record["id"])
    exec_summary = next(s for s in reloaded["sections"] if s["section_id"] == "executive_summary")
    market_context = next(s for s in reloaded["sections"] if s["section_id"] == "market_context")
    assert exec_summary["edited_prose"] == "A-edited"  # untouched
    assert market_context["generated_prose"] == "B-regenerated"
    assert market_context["citation_ids"] == ["ev-1"]


def test_saved_report_stores_no_resolved_evidence_body(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(
        inbox,
        title="Test report",
        report_type="market_landscape",
        scope={"company_ids": ["company-fallcreek"]},
        sections=[],
    )
    forbidden_keys = {"published_evidence", "companies", "varieties", "signals", "assessments", "source_trace"}
    assert forbidden_keys.isdisjoint(record.keys())
    assert forbidden_keys.isdisjoint(record["scope"].keys())


def test_archive_report(tmp_path: Path):
    inbox = tmp_path / "inbox"
    record = create_report(inbox, title="Old report", report_type="market_landscape", scope={}, sections=[])
    archived = archive_report(inbox, record["id"])
    assert archived["status"] == "archived"


# --- 13/14/15. PDF export ----------------------------------------------------


def test_pdf_export_succeeds():
    packet = _minimal_packet()
    coverage = report_coverage(packet)
    report = {
        "id": "rp-test",
        "title": "Test Report",
        "report_type": "market_landscape",
        "scope": {"berry_id": "berry-blueberry", "geography_ids": [], "company_ids": ["company-fallcreek"], "variety_ids": []},
        "sections": [
            {"section_id": "executive_summary", "title": "Executive Summary", "generated_prose": "Fall Creek expanded.", "edited_prose": None, "citation_ids": ["ev-1"], "status": "ai_draft"},
        ],
        "external_research_appendix": [],
    }
    pdf_bytes = render_report_pdf(report, packet, coverage)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_pdf_export_handles_sparse_report_with_no_sections():
    packet = {"report_type": "market_landscape", "strategic_question": None, "companies": [], "varieties": [], "variety_candidates": [], "recent_developments": [], "signals": [], "assessments": [], "source_trace": [], "known_ids": set()}
    coverage = report_coverage(packet)
    report = {"id": "rp-sparse", "title": "Sparse Report", "report_type": "market_landscape", "scope": {}, "sections": [], "external_research_appendix": []}
    pdf_bytes = render_report_pdf(report, packet, coverage)
    assert pdf_bytes.startswith(b"%PDF")


# --- 17. Private/static boundary --------------------------------------------


def test_reports_routes_are_not_registered_in_build_static():
    source = Path("scripts/build_static.py").read_text(encoding="utf-8")
    assert '"/reports"' not in source
    assert "/reports/" not in source


# --- 18/19. Perplexity public/private boundary -------------------------------


def test_public_query_only_contains_public_labels():
    context = PublicQueryContext(
        berry_label="Blueberry",
        geography_labels=("Spain",),
        company_names=("Fall Creek",),
        variety_names=(),
        question="recent production volume",
    )
    query = build_public_query(context)
    assert "Blueberry" in query
    assert "Spain" in query
    assert "Fall Creek" in query
    assert "recent production volume" in query


def test_public_query_context_has_no_field_for_private_content():
    # Structural guarantee: PublicQueryContext's dataclass fields are a
    # fixed allow-list of public labels -- there is no field through
    # which Evidence/Assessment/Signal text or report prose could reach
    # build_public_query at all.
    assert set(PublicQueryContext.__dataclass_fields__.keys()) == {
        "berry_label", "geography_labels", "company_names", "variety_names", "question",
    }


def test_perplexity_findings_remain_unreviewed_proposals(tmp_path: Path):
    from app.services.report_builder.reports_store import append_research_appendix

    inbox = tmp_path / "inbox"
    record = create_report(inbox, title="R", report_type="market_landscape", scope={}, sections=[{"section_id": "executive_summary", "title": "Executive Summary", "generated_prose": "x", "edited_prose": None, "citation_ids": [], "status": "ai_draft"}])
    append_research_appendix(inbox, record["id"], [{"title": "Public article", "url": "https://example.test/a", "snippet": "...", "source": "perplexity_public_research", "reviewed": False}])
    reloaded = load_report(inbox, record["id"])
    assert reloaded["external_research_appendix"][0]["reviewed"] is False
    # Never merged into sections.
    assert all("Public article" not in (s.get("generated_prose") or "") for s in reloaded["sections"])


# --- 20. Sparse report ------------------------------------------------------


def test_sparse_report_with_limited_evidence_shows_gaps():
    entities = _base_entities()
    scope = ResolvedScope(
        report_type="market_landscape",
        berry_id="berry-strawberry",
        geography_ids=(),
        company_ids=(),
        variety_ids=(),
        strategic_question_id=None,
        date_window_days=None,
        focus_notes="",
    )
    packet = build_report_packet(
        scope,
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        strategic_questions=[],
        recommendations=[],
        variety_candidates=[],
        berry_labels=BERRIES,
    )
    coverage = report_coverage(packet)
    assert coverage["counts"]["evidence_count"] == 0
    assert "No trusted Evidence captured for this scope yet." in coverage["gaps"]


# --- 21. Canonical vs candidate Variety trust distinction --------------------


def test_trusted_and_candidate_varieties_stay_in_separate_buckets():
    entities = _base_entities()
    scope = ResolvedScope(
        report_type="variety_genetics_landscape",
        berry_id="berry-blueberry",
        geography_ids=(),
        company_ids=(),
        variety_ids=("variety-alpha",),
        strategic_question_id=None,
        date_window_days=None,
        focus_notes="",
    )
    candidates = [{"id": "vcand-1", "candidate_name": "Beta", "berry_id": "berry-blueberry", "identity_state": "distinct"}]
    packet = build_report_packet(
        scope,
        entities=entities,
        relationships=[],
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        strategic_questions=[],
        recommendations=[],
        variety_candidates=candidates,
        berry_labels=BERRIES,
    )
    trusted_ids = {v["id"] for v in packet["varieties"]}
    candidate_ids = {c["id"] for c in packet["variety_candidates"]}
    assert trusted_ids == {"variety-alpha"}
    assert candidate_ids == {"vcand-1"}
    assert trusted_ids.isdisjoint(candidate_ids)
