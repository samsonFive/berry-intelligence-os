"""Ask Berry OS V1 -- scope, packet, trust, live, and stakeholder workflow."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.industry_pulse.models import DiscoveryHit
from app.services.industry_pulse.providers import MemoryProvider
from app.services.research_desk import (
    ResearchScope,
    assemble_research_packet,
    compose_research_answer,
    interpret_research_scope,
    run_live_research,
)


def _entities() -> list[dict]:
    return [
        {"id": "company-planasa", "entity_type": "company", "name": "Planasa", "aliases": []},
        {"id": "company-fall-creek", "entity_type": "company", "name": "Fall Creek Farm & Nursery", "aliases": ["Fall Creek"]},
        {"id": "geography-peru", "entity_type": "geography", "name": "Peru", "aliases": []},
        {"id": "geography-europe", "entity_type": "geography", "name": "Europe", "aliases": []},
        {"id": "variety-a", "entity_type": "variety", "name": "Blue One", "aliases": []},
    ]


def _scope(**overrides) -> ResearchScope:
    values = {
        "question": "What has Planasa done in the last 30 days?",
        "berry_id": None,
        "geography_ids": (),
        "company_ids": ("company-planasa",),
        "variety_ids": (),
        "window_days": 30,
        "topics": (),
        "intelligence_type": "competitor",
        "comparison": False,
    }
    values.update(overrides)
    return ResearchScope(**values)


def test_change_questions_default_to_ninety_days() -> None:
    scope = interpret_research_scope(
        "What changed in Peru blueberries?",
        berries={"berry-blueberry": "Blueberry"},
        entities=_entities(),
        questions=[],
        relationships=[],
    )
    assert scope.window_days == 90
    assert scope.geography_ids == ("geography-peru",)
    assert scope.berry_id == "berry-blueberry"


def test_interprets_scope_and_never_silently_guesses_identity() -> None:
    scope = interpret_research_scope(
        "Compare Planasa and Fall Creek in Peru over the last 30 days",
        berries={"berry-blueberry": "Blueberry"},
        entities=_entities(),
        questions=[],
        relationships=[],
    )
    assert scope.company_ids == ("company-planasa", "company-fall-creek")
    assert scope.geography_ids == ("geography-peru",)
    assert scope.window_days == 30
    assert scope.comparison is True

    unresolved = interpret_research_scope(
        "What is Mystery Genetics doing?",
        berries={"berry-blueberry": "Blueberry"},
        entities=_entities(),
        questions=[],
        relationships=[],
    )
    assert not unresolved.company_ids


def test_follow_up_carries_prior_scope_and_replaces_topic() -> None:
    previous = _scope(topics=("commercial",), window_days=7)
    scope = interpret_research_scope(
        "Only show genetics in Europe",
        berries={"berry-blueberry": "Blueberry"},
        entities=_entities(),
        questions=[],
        relationships=[],
        previous=previous,
    )
    assert scope.company_ids == previous.company_ids
    assert scope.geography_ids == ("geography-europe",)
    assert scope.topics == ("genetics",)
    assert scope.window_days == 7


def test_browser_scope_state_handles_invalid_window_without_error() -> None:
    scope = ResearchScope.from_dict({"question": "What changed?", "window_days": "not-a-number"})
    assert scope.window_days == 30


def test_topic_interpretation_does_not_match_substrings_inside_words() -> None:
    scope = interpret_research_scope(
        "What are the important emerging developments in blackberry?",
        berries={"berry-blackberry": "Blackberry"},
        entities=_entities(),
        questions=[],
        relationships=[],
    )
    assert "supply" not in scope.topics


def test_packet_preserves_trust_classes_structured_records_and_input_immutability() -> None:
    entities = {row["id"]: row for row in _entities()}
    evidence = [
        {
            "id": "ev-approved", "title": "Planasa source", "source_name": "Publisher",
            "published_date": "2026-08-25", "entity_ids": ["company-planasa"],
            "evidence_role": "publication_artifact", "fact_ids": [],
        },
        {
            "id": "ev-patent", "title": "Planasa plant patent", "source_name": "USPTO",
            "published_date": "2026-08-28", "entity_ids": ["company-planasa"],
            "evidence_role": "publication_artifact", "fact_ids": ["fact-1"],
            "intake_type": "patent_filing", "patent_filing": {"application": "US1"},
        },
    ]
    facts = [{"id": "fact-1", "statement": "A patent filing was recorded.", "entity_ids": ["company-planasa"], "evidence_ids": ["ev-patent"]}]
    relationships = [{"id": "rel-1", "subject_id": "company-planasa", "predicate": "develops", "object_id": "variety-a", "evidence_ids": ["ev-patent"]}]
    before = deepcopy((entities, evidence, facts, relationships))
    packet = assemble_research_packet(
        _scope(topics=("rights_ip",)),
        entities=entities,
        relationships=relationships,
        published_evidence=evidence,
        facts=facts,
        signals=[],
        assessments=[],
        today=date(2026, 9, 1),
    )
    labels = {row["id"]: row["trust_class"] for row in packet["evidence"]}
    assert labels["ev-approved"] == "APPROVED SOURCE"
    assert labels["ev-patent"] == "TRUSTED EVIDENCE"
    assert packet["rights_ip"][0]["structured_kind"] == "PATENT"
    assert packet["relationships"][0]["predicate"] == "develops"
    assert (entities, evidence, facts, relationships) == before


def test_live_research_is_provider_neutral_and_keeps_live_separate() -> None:
    hit = DiscoveryHit(
        title="Planasa expands strawberry breeding program",
        url="https://example.com/planasa",
        source_domain="example.com",
        published_date="2026-08-30",
        snippet="Planasa announced a strawberry genetics expansion.",
        query_id="fixture",
        query_text="fixture",
        geography="global",
        berry="strawberry",
        topic="genetics",
        provider="fixture",
    )
    provider = MemoryProvider(name="memory", hits=[hit])
    entities = {row["id"]: row for row in _entities()}
    result = run_live_research(
        _scope(berry_id="berry-strawberry", topics=("genetics",)),
        providers=[provider],
        entities=entities,
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    assert result["items"]
    assert result["items"][0]["trust_class"] == "LIVE / UNREVIEWED"
    assert result["telemetry"]["memory"]["queries"] == 1


def test_live_berry_scope_rejects_same_name_stock_noise() -> None:
    hit = DiscoveryHit(
        title="BlackBerry stock price prediction",
        url="https://example.com/stock",
        source_domain="example.com",
        published_date="2026-08-30",
        snippet="BlackBerry Limited software shares trade on the market.",
        query_id="fixture", query_text="fixture", geography="global",
        berry="blackberry", topic="research_desk", provider="fixture",
    )
    result = run_live_research(
        _scope(question="Blackberry developments", berry_id="berry-blackberry", company_ids=()),
        providers=[MemoryProvider(name="memory", hits=[hit])],
        entities={row["id"]: row for row in _entities()},
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    assert result["items"] == []


def test_generated_claims_without_packet_citations_are_dropped_and_private_text_is_not_sent() -> None:
    packet = {
        "evidence": [{"id": "ev-1", "title": "Public title", "source_name": "Public source", "date": "2026-08-30", "href": "/evidence/ev-1", "trust_class": "TRUSTED EVIDENCE"}],
        "facts": [], "companies": [], "relationships": [], "rights_ip": [], "market_context": [],
        "signals": [], "assessments": [{"id": "assessment-1", "title": "Internal title", "rationale": "PRIVATE STRATEGY", "source_ids": []}],
        "coverage_gaps": [], "source_index": {"ev-1": {"id": "ev-1", "title": "Public title", "source_name": "Public source", "date": "2026-08-30", "href": "/evidence/ev-1", "trust_class": "TRUSTED EVIDENCE"}},
    }
    prompts = []

    class Result:
        parsed = {
            "findings": [{"text": "Unsupported", "source_ids": ["made-up"]}],
            "implications": [{"text": "Grounded possibility", "source_ids": ["ev-1"]}],
        }

    def completer(prompt, **_kwargs):
        prompts.append(prompt)
        return Result()

    answer = compose_research_answer(packet, completer=completer)
    assert all(row["text"] != "Unsupported" for row in answer["findings"])
    assert answer["implications"][0]["source_ids"] == ["ev-1"]
    assert "PRIVATE STRATEGY" not in prompts[0]


def test_research_desk_stakeholder_surface_and_brief_handoff() -> None:
    client = TestClient(app)
    landing = client.get("/research")
    assert landing.status_code == 200
    assert "Ask Berry OS" in landing.text
    assert "chat" not in landing.text.casefold()
    page = client.post("/research", data={"question": "Compare Planasa and Fall Creek."})
    assert page.status_code == 200
    assert "Interpreted scope" in page.text
    assert "Strategic comparison" in page.text
    assert "Current positioning snapshot" in page.text
    assert "Observed activity vs coverage depth" in page.text
    assert "What should a strategy team watch next?" in page.text
    assert "LIVE / UNREVIEWED" in page.text
    assert "TRUSTED" in page.text or "APPROVED SOURCE" in page.text
    assert 'action="/reports/new"' in page.text
    assert "Create leadership brief" in page.text
    preview = client.post(
        "/reports/new",
        data={
            "step": "preview", "report_type": "competitor_comparison",
            "company_ids": "company-planasa,company-fall-creek-farm-and-nursery",
            "date_window_days": "30", "focus_notes": "Compare Planasa and Fall Creek.",
        },
    )
    assert preview.status_code == 200
    assert "Research question:" in preview.text
    assert "PRESELECTED SOURCE-BACKED FINDINGS" in preview.text
    assert 'name="focus_notes"' in preview.text


def test_change_scenario_section_renders_on_research_desk() -> None:
    page = TestClient(app).post("/research", data={"question": "What changed around Hortifrut in the last 90 days?"})
    assert page.status_code == 200
    assert "What changed" in page.text
    assert "NOT A FORECAST" in page.text
    assert "AI-generated strategic questions" in page.text or "No dated before/now delta" in page.text


def test_live_endpoint_uses_structured_selection_state(monkeypatch) -> None:
    monkeypatch.setattr("app.main._pulse_providers", lambda: [])
    monkeypatch.setattr("app.main.maybe_untrusted_completer", lambda: None)
    payload = {"scope": _scope().as_dict(), "first_content_ms": 25}
    response = TestClient(app).post("/api/research/live", json=payload)
    assert response.status_code == 200
    assert "Research complete" in response.text
    assert "Time to first content" in response.text


# --- Overnight Flagship Integration V1: Market Reality + Radar seams ---


def test_market_context_provider_populates_packet_and_answer() -> None:
    def fake_market_provider(scope):
        return [{
            "id": "mkt-fake-1", "title": "Peru Fresh Blueberries -- Export Volume +32.2%",
            "source_name": "usda_fas", "date": "2026-09-02", "href": "https://example.invalid/fas.pdf",
            "trust_class": "MARKET REALITY", "structured_kind": "MARKET OBSERVATION",
            "entity_ids": [], "geography_ids": [],
        }]

    packet = assemble_research_packet(
        _scope(topics=("supply",)),
        entities={row["id"]: row for row in _entities()},
        relationships=[],
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        market_context_provider=fake_market_provider,
        today=date(2026, 9, 1),
    )
    assert packet["market_context"][0]["title"] == "Peru Fresh Blueberries -- Export Volume +32.2%"
    assert "MARKET_REALITY" in packet["requested_layers"]

    answer = compose_research_answer(packet)
    assert answer["market_context"][0]["structured_kind"] == "MARKET OBSERVATION"


def test_developments_provider_populates_packet_and_answer_bounded() -> None:
    def fake_developments_provider(scope):
        return [
            {"id": f"dev-{i}", "title": f"Development {i}", "event_type": "PRODUCTION_EXPANSION"}
            for i in range(10)
        ]

    packet = assemble_research_packet(
        _scope(),
        entities={row["id"]: row for row in _entities()},
        relationships=[],
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        developments_provider=fake_developments_provider,
        today=date(2026, 9, 1),
    )
    assert len(packet["radar_developments"]) == 6  # bounded, never every cached item
    assert "EMERGING_RADAR" in packet["requested_layers"]

    answer = compose_research_answer(packet)
    assert len(answer["radar_developments"]) == 6
    assert answer["radar_developments"][0]["title"] == "Development 0"


def test_no_providers_means_no_market_or_radar_rows_not_an_error() -> None:
    packet = assemble_research_packet(
        _scope(),
        entities={row["id"]: row for row in _entities()},
        relationships=[],
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        today=date(2026, 9, 1),
    )
    assert packet["market_context"] == []
    assert packet["radar_developments"] == []
    assert "MARKET_REALITY" not in packet["requested_layers"]
    assert "EMERGING_RADAR" not in packet["requested_layers"]


def test_research_desk_get_prefills_question_from_handoff_query_param() -> None:
    page = TestClient(app).get("/research?q=What+should+I+know+about%3A+Hortifrut")
    assert page.status_code == 200
    assert "What should I know about: Hortifrut" in page.text


def test_research_desk_get_without_q_has_no_prefill() -> None:
    page = TestClient(app).get("/research")
    assert page.status_code == 200
    assert '<textarea id="rd-question" name="question" rows="2" autofocus required placeholder="What is Planasa doing in strawberries right now?"></textarea>' in page.text
