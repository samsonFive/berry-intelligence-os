"""Review is metadata, never an eligibility gate for report/research sources."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import json

from app.services.report_builder.packet import build_report_packet
from app.services.report_builder.scope import ResolvedScope
from app.services.report_builder.synthesis import _public_evidence_line
from app.services.report_builder.topic_report import attach_topic_research
from app.services.research_desk import ResearchScope, assemble_research_packet, compose_research_answer


ENTITIES = {
    "company-a": {"id": "company-a", "name": "Alpha Berries", "entity_type": "company", "aliases": [], "berry_ids": ["berry-blueberry"]},
}


def source(record_id, **changes):
    return {
        "id": record_id, "title": "Alpha Berries opens a blueberry nursery",
        "status": "draft", "evidence_role": "publication_artifact",
        "source_name": "Publisher", "source_type": "trade_press",
        "source_url": f"https://example.com/{record_id}", "published_date": "2026-11-12",
        "entity_ids": ["company-a"], "berry_ids": ["berry-blueberry"],
        **changes,
    }


def test_company_report_includes_unreviewed_sources_without_topic_query():
    records = [source("reviewed", status="published", confidence="high")]
    drafts = [source("unreviewed", confidence="low"), source("reviewed", title="Stale draft copy")]
    original = deepcopy((records, drafts))
    scope = ResolvedScope(
        report_type="market_landscape", berry_id="berry-blueberry", geography_ids=(),
        company_ids=("company-a",), variety_ids=(), strategic_question_id=None,
        date_window_days=None, focus_notes="",
    )
    packet = build_report_packet(
        scope, entities=ENTITIES, relationships=[], published_evidence=records,
        pending_publications=drafts, facts=[], signals=[], assessments=[],
        strategic_questions=[], recommendations=[], variety_candidates=[], berry_labels={},
    )
    sources = {row["id"]: row for row in packet["source_trace"]}
    assert set(sources) == {"reviewed", "unreviewed"}
    assert sources["reviewed"]["title"] != "Stale draft copy"
    assert sources["unreviewed"]["information"]["review_status"] == "unreviewed"
    assert sources["unreviewed"]["information"]["confidence"] == "low"
    assert sources["unreviewed"]["href"] == "/intelligence/unreviewed"
    assert (records, drafts) == original
    digest = _public_evidence_line(next(row for row in packet["recent_developments"] if row["id"] == "unreviewed"))
    assert "review: unreviewed" in digest
    assert "confidence:" in digest


def test_research_combines_saved_and_fresh_sources_by_date_with_item_flags():
    scope = ResearchScope(
        question="Alpha Berries nursery", berry_id="berry-blueberry", geography_ids=(),
        company_ids=("company-a",), variety_ids=(), window_days=30, topics=(),
        intelligence_type="competitor", comparison=False,
    )
    packet = assemble_research_packet(
        scope, entities=ENTITIES, relationships=[],
        published_evidence=[source("unreviewed"), source("reviewed", status="published", published_date="2026-11-10")],
        facts=[], signals=[], assessments=[], today=date(2026, 11, 13),
    )
    rows = {row["id"]: row for row in packet["evidence"]}
    assert rows["unreviewed"]["trust_class"] == "UNREVIEWED SOURCE"
    assert rows["unreviewed"]["information"]["confidence_label"] == "Not assessed"
    assert packet["facts"] == []
    answer = compose_research_answer(packet, live={
        "coverage_as_of": "2026-11-13", "items": [{
            "id": "fresh", "title": "Fresh source", "source_name": "Publisher",
            "date": "2026-11-13", "trust_class": "LIVE / UNREVIEWED", "url": "https://example.com/fresh",
        }],
    })
    assert [row["id"] for row in answer["current_developments"]] == ["fresh", "unreviewed", "reviewed"]
    assert {row["id"] for row in answer["sources"]} == {"fresh", "unreviewed", "reviewed"}


def test_topic_report_finds_intake_body_only_match_and_keeps_only_selected_excerpt(tmp_path):
    preview = source("intake", title="Technical note", summary="Experimental findings")
    full = {**preview, "article": {"paragraphs": [
        {"text": "A blueberry waxseal trial introduced a new waxseal treatment for fruit."},
        {"text": "PRIVATE_UNMATCHED_DOCUMENT_BODY " * 100},
    ]}}
    calls = []

    def load_record(record_id):
        calls.append(record_id)
        return full

    scope = ResolvedScope(
        report_type="market_landscape", berry_id="berry-blueberry", geography_ids=(),
        company_ids=("company-a",), variety_ids=(), strategic_question_id=None,
        date_window_days=None, focus_notes="", research_query="blueberry waxseal",
        source_scope="collected",
    )
    args = dict(
        entities=ENTITIES, relationships=[], published_evidence=[source("canonical", status="published")],
        pending_publications=[preview], facts=[], signals=[], assessments=[],
        strategic_questions=[], recommendations=[], variety_candidates=[], berry_labels={}, load_record=load_record,
    )
    packet = build_report_packet(scope, **args)
    assert calls == ["intake"]
    assert [row["id"] for row in packet["topic_matches"]] == ["intake"]
    matched = packet["topic_matches"][0]
    assert "waxseal" in matched["passage"]
    assert matched["passage_locator"].startswith("article:")
    assert matched["source_version"]
    assert "article" not in matched
    assert "PRIVATE_UNMATCHED_DOCUMENT_BODY" not in json.dumps(packet, default=list)
    version = matched["source_version"]
    attach_topic_research(packet, scope, entities=ENTITIES, inbox_dir=tmp_path)
    assert packet["topic_research"]["local"][0]["source_version"] == version
    calls.clear()
    build_report_packet(replace(scope, research_query=""), **args)
    assert calls == []


def test_research_cane_query_inspects_intake_body_without_returning_it():
    scope = ResearchScope(
        question="Blackberry floricane", berry_id="berry-blackberry", geography_ids=(),
        company_ids=("company-a",), variety_ids=(), window_days=30, topics=(),
        intelligence_type="competitor", comparison=False,
    )
    preview = source("cane", title="Technical note", summary="Experimental findings",
                     berry_ids=["berry-blackberry"], _catalog_origin="inbox")
    body = "A blackberry floricane trial introduced a new cultivar for growers."
    calls = []

    def load_record(record_id):
        calls.append(record_id)
        return {**preview, "article": {"paragraphs": [{"text": body}]}}

    packet = assemble_research_packet(
        scope, entities=ENTITIES, relationships=[], published_evidence=[preview],
        facts=[], signals=[], assessments=[], today=date(2026, 11, 13), load_record=load_record,
    )
    assert calls == ["cane"]
    assert [row["id"] for row in packet["evidence"]] == ["cane"]
    assert body not in json.dumps(packet, default=list)
