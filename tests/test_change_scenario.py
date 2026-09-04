"""Change + scenario engine — before/now, coverage, market, grounding."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

from pathlib import Path

from app.repositories.json.market_observations import MarketObservationRepository
from app.services.change_scenario import (
    CHANGE_TYPES,
    build_change_scenario,
    change_question,
    change_scenario_for,
    classify_coverage_artifact,
    split_windows,
)
from app.services.market_reality.research_desk import market_context_for_research_scope
from app.services.research_desk import (
    ResearchScope,
    assemble_research_packet,
    compose_research_answer,
    interpret_research_scope,
)


TODAY = date(2026, 9, 3)


def _scope(**overrides) -> ResearchScope:
    values = {
        "question": "What changed around Hortifrut in the last 90 days?",
        "berry_id": "berry-blueberry",
        "geography_ids": (),
        "company_ids": ("company-hortifrut",),
        "variety_ids": (),
        "window_days": 90,
        "topics": (),
        "intelligence_type": "competitor",
        "comparison": False,
    }
    values.update(overrides)
    return ResearchScope(**values)


def _move(move_id: str, *, company: str, move_type: str, event: str, seen: str | None = None, title: str = "") -> dict:
    return {
        "id": move_id,
        "title": title or f"{company} {move_type}",
        "company_id": company,
        "move_type": move_type,
        "published_date": event,
        "event_date": event,
        "first_seen": seen or event,
        "latest_update": event,
        "trust_class": "LIVE / UNREVIEWED",
        "supporting_sources": [{"publisher": "Trade press", "published_date": event}],
    }


def _packet(**overrides) -> dict:
    moves = overrides.pop("competitive_moves", [
        _move("mv-old", company="company-hortifrut", move_type="VARIETY_LAUNCH", event="2026-06-20", title="Hortifrut named cultivar trial"),
        _move("mv-new-1", company="company-hortifrut", move_type="PARTNERSHIP", event="2026-08-12", title="Hortifrut platform partnership"),
        _move("mv-new-2", company="company-hortifrut", move_type="VARIETY_COMMERCIALIZATION", event="2026-08-20", title="Hortifrut commercialization program"),
    ])
    market = overrides.pop("market_context", [])
    companies = overrides.pop("companies", [
        {"id": "company-hortifrut", "name": "Hortifrut"},
        {"id": "company-planasa", "name": "Planasa"},
        {"id": "company-fall-creek", "name": "Fall Creek"},
    ])
    packet = {
        "scope": _scope().as_dict(),
        "companies": companies,
        "competitive_moves": moves,
        "radar_developments": [],
        "market_context": market,
        "evidence": [],
        "signals": [],
        "assessments": [],
        "rights_ip": [],
        "source_index": {row["id"]: row for row in [*moves, *market] if row.get("id")},
    }
    packet.update(overrides)
    return packet


def test_split_windows_halves_the_selected_range() -> None:
    start, mid, end = split_windows(90, today=TODAY)
    assert start == date(2026, 6, 5)
    assert mid == date(2026, 7, 20)
    assert end == TODAY


def test_before_now_uses_event_dates_not_capture() -> None:
    model = build_change_scenario(_scope(), _packet(), today=TODAY)
    types = {row["change_type"] for row in model["changes"]}
    assert "PARTNERSHIP_CHANGE" in types
    assert "COMMERCIALIZATION_CHANGE" in types
    partnership = next(row for row in model["changes"] if row["change_type"] == "PARTNERSHIP_CHANGE")
    assert "No dated items of this type in the earlier window" in partnership["before"]
    assert "platform partnership" in partnership["now"]
    assert "confidence" not in partnership["evidence_basis"].casefold() or "not a confidence" in partnership["evidence_basis"].casefold()


def test_timeline_is_chronological_and_readable() -> None:
    model = build_change_scenario(_scope(), _packet(), today=TODAY)
    dates = [row["date"] for row in model["timeline"]]
    assert dates == sorted(dates, reverse=True)
    assert model["timeline"][0]["trust_state"]
    assert model["timeline"][0]["source"]
    assert model["timeline"][0]["title"]


def test_source_published_date_beats_index_date() -> None:
    row = {
        "id": "mv-indexed-late",
        "title": "Hortifrut MBO platform",
        "company_id": "company-hortifrut",
        "move_type": "PARTNERSHIP",
        "date": "2026-09-02",
        "first_seen": "2026-09-02",
        "sources": [{"publisher": "The Packer", "published_date": "2026-08-03"}],
        "trust_class": "LIVE / UNREVIEWED MOVE",
    }
    model = build_change_scenario(_scope(), _packet(competitive_moves=[row]), today=TODAY)
    partnership = next(row for row in model["changes"] if row["change_type"] == "PARTNERSHIP_CHANGE")
    assert partnership["first_observed"] == "2026-08-03"
    assert all(row["change_type"] != "COVERAGE_CHANGE" for row in model["changes"])


def test_recent_latest_update_on_old_event_is_coverage_change() -> None:
    row = {
        "id": "mv-planasa-old",
        "title": "Planasa appoints Hans Liekens as Global Head of Innovation",
        "company_id": "company-planasa",
        "move_type": "LEADERSHIP",
        "event_date": "2025-01-15",
        "first_seen": "2025-01-15",
        "latest_update": "2026-09-02",
        "sources": [{"publisher": "Italian Berry", "published_date": "2025-01-15"}],
        "trust_class": "LIVE / UNREVIEWED MOVE",
    }
    model = build_change_scenario(
        _scope(question="What changed in Planasa competitive position?", company_ids=("company-planasa",)),
        _packet(competitive_moves=[row], companies=[{"id": "company-planasa", "name": "Planasa"}]),
        today=TODAY,
    )
    assert "COVERAGE_CHANGE" in {change["change_type"] for change in model["changes"]}
    assert "LEADERSHIP_CHANGE" not in {change["change_type"] for change in model["changes"]}


def test_index_date_on_old_source_is_coverage_change() -> None:
    row = {
        "id": "mv-old-source",
        "title": "Old Hortifrut partnership newly indexed",
        "company_id": "company-hortifrut",
        "move_type": "PARTNERSHIP",
        "date": "2026-08-28",
        "sources": [{"publisher": "Trade press", "published_date": "2025-11-01"}],
        "trust_class": "LIVE / UNREVIEWED MOVE",
    }
    model = build_change_scenario(_scope(), _packet(competitive_moves=[row]), today=TODAY)
    assert "COVERAGE_CHANGE" in {change["change_type"] for change in model["changes"]}
    assert "PARTNERSHIP_CHANGE" not in {change["change_type"] for change in model["changes"]}


def test_coverage_change_is_not_recent_competitor_activity() -> None:
    row = _move(
        "mv-old-indexed-late",
        company="company-hortifrut",
        move_type="PARTNERSHIP",
        event="2025-11-01",
        seen="2026-08-28",
        title="Old Hortifrut partnership newly indexed",
    )
    assert classify_coverage_artifact(row, mid=date(2026, 7, 20), today=TODAY) is True
    packet = _packet(competitive_moves=[row])
    model = build_change_scenario(_scope(), packet, today=TODAY)
    types = [change["change_type"] for change in model["changes"]]
    assert "COVERAGE_CHANGE" in types
    assert "PARTNERSHIP_CHANGE" not in types
    assert "coverage change" in model["changes"][0]["what_changed"].casefold()


def test_market_delta_becomes_supply_or_condition_change() -> None:
    market = [
        {
            "id": "mkt-peru-volume",
            "title": "Peru Fresh Blueberries -- Export Volume +32.2% (2024 -> 2025, 242000 -> 320000 MT)",
            "structured_kind": "MARKET OBSERVATION",
            "trust_class": "MARKET REALITY",
            "metric": "export_volume",
            "pct_change": 32.2,
            "direction": "up",
            "previous_period": "2024",
            "previous_value": 242000,
            "latest_period": "2025",
            "latest_value": 320000,
            "unit": "MT",
        },
        {
            "id": "mkt-peru-price",
            "title": "Peru Fresh Blueberries -- Export Price -16.0% (2024 -> 2025, 6.2 -> 5.2 USD/kg)",
            "structured_kind": "MARKET OBSERVATION",
            "trust_class": "MARKET REALITY",
            "metric": "export_price",
            "pct_change": -16.0,
            "direction": "down",
            "previous_period": "2024",
            "previous_value": 6.2,
            "latest_period": "2025",
            "latest_value": 5.2,
            "unit": "USD/kg",
        },
    ]
    model = build_change_scenario(
        _scope(question="What changed in Peru blueberries?", company_ids=(), geography_ids=("geography-peru",)),
        _packet(competitive_moves=[], market_context=market),
        today=TODAY,
    )
    types = {row["change_type"] for row in model["changes"]}
    assert "SUPPLY_CHANGE" in types
    assert "MARKET_CONDITION_CHANGE" in types
    volume = next(row for row in model["changes"] if row["change_type"] == "SUPPLY_CHANGE")
    assert "242000" in volume["before"]
    assert "320000" in volume["now"]
    assert model["scenarios"]
    assert all(row["source_ids"] for row in model["scenarios"])


def test_competitor_change_and_plausible_next_move_wording() -> None:
    model = build_change_scenario(_scope(), _packet(), today=TODAY)
    assert any(row["kind"] == "PLAUSIBLE NEXT MOVE" for row in model["competitor_next"])
    text = " ".join(row["text"] for row in model["competitor_next"]).casefold()
    assert "based on current observed activity" in text
    assert "hortifrut will" not in text


def test_unsupported_scenarios_are_rejected() -> None:
    model = build_change_scenario(_scope(), _packet(competitive_moves=[], market_context=[], companies=[{"id": "company-hortifrut", "name": "Hortifrut"}]), today=TODAY)
    assert model["scenarios"] == []
    assert model["competitor_next"] == []


def test_no_fake_probabilities() -> None:
    model = build_change_scenario(_scope(), _packet(), today=TODAY)
    claims = " ".join(
        str(row.get("what_changed") or row.get("text") or "")
        for row in [*model["changes"], *model["scenarios"], *model["competitor_next"]]
    ).casefold()
    assert "probability" not in claims
    assert "% likely" not in claims
    assert "forecast" not in claims
    assert "not forecasts" in model["method_note"]


def test_trust_states_stay_on_the_timeline() -> None:
    packet = _packet()
    packet["competitive_moves"][0]["trust_class"] = "TRUSTED EVIDENCE"
    packet["competitive_moves"][1]["trust_class"] = "LIVE / UNREVIEWED"
    model = build_change_scenario(_scope(), packet, today=TODAY)
    states = {row["trust_state"] for row in model["timeline"]}
    assert "TRUSTED EVIDENCE" in states
    assert "LIVE / UNREVIEWED" in states


def test_build_does_not_mutate_packet() -> None:
    packet = _packet()
    before = deepcopy(packet)
    build_change_scenario(_scope(), packet, today=TODAY)
    assert packet == before


def test_single_company_question_has_no_temporal_comparison() -> None:
    model = build_change_scenario(_scope(), _packet(), today=TODAY)
    assert model["temporal_differences"] == []


def test_temporal_differences_for_multi_company_packets() -> None:
    packet = _packet(
        competitive_moves=[
            _move("mv-p", company="company-planasa", move_type="LEADERSHIP", event="2026-08-10", title="Planasa leadership change"),
            _move("mv-f", company="company-fall-creek", move_type="VARIETY_COMMERCIALIZATION", event="2026-08-18", title="Fall Creek commercialization"),
            _move("mv-h", company="company-hortifrut", move_type="PARTNERSHIP", event="2026-08-22", title="Hortifrut partnership"),
        ]
    )
    model = build_change_scenario(
        _scope(comparison=True, company_ids=("company-planasa", "company-fall-creek", "company-hortifrut")),
        packet,
        today=TODAY,
    )
    texts = " ".join(row["text"] for row in model["temporal_differences"])
    assert "Planasa" in texts
    assert "Fall Creek" in texts
    assert "Hortifrut" in texts
    assert all(row["kind"] == "TEMPORAL DIFFERENCE" for row in model["temporal_differences"])


def test_generated_questions_are_labeled_and_not_canonical() -> None:
    model = build_change_scenario(_scope(), _packet(), today=TODAY)
    assert model["questions"]
    assert all(row["kind"] == "AI-GENERATED STRATEGIC QUESTION" for row in model["questions"])


def test_change_types_are_closed() -> None:
    model = build_change_scenario(_scope(), _packet(), today=TODAY)
    assert set(CHANGE_TYPES) >= {row["change_type"] for row in model["changes"]}


def test_interpret_change_questions_use_ninety_days_without_breaking_current() -> None:
    berries = {"berry-blueberry": "Blueberry"}
    entities = [
        {"id": "company-hortifrut", "entity_type": "company", "name": "Hortifrut", "aliases": []},
        {"id": "geography-peru", "entity_type": "geography", "name": "Peru", "aliases": []},
    ]
    changed = interpret_research_scope(
        "What changed in Peru blueberries?",
        berries=berries,
        entities=entities,
        questions=[],
        relationships=[],
    )
    assert changed.window_days == 90
    current = interpret_research_scope(
        "What is Hortifrut doing currently?",
        berries=berries,
        entities=entities,
        questions=[],
        relationships=[],
    )
    assert current.window_days == 7
    assert change_question("What scenarios should we watch next in Peru blueberries?")


def test_compose_passes_change_scenario_through() -> None:
    packet = assemble_research_packet(
        _scope(),
        entities={"company-hortifrut": {"id": "company-hortifrut", "name": "Hortifrut", "entity_type": "company"}},
        relationships=[],
        published_evidence=[],
        facts=[],
        signals=[],
        assessments=[],
        competitive_moves_provider=lambda _scope: [_move("mv-new-1", company="company-hortifrut", move_type="PARTNERSHIP", event="2026-08-12")],
        today=TODAY,
    )
    packet["change_scenario"] = build_change_scenario(_scope(), packet, today=TODAY)
    answer = compose_research_answer(packet)
    assert answer["change_scenario"]["changes"]
    assert "PARTNERSHIP_CHANGE" in {row["change_type"] for row in answer["change_scenario"]["changes"]}


def test_europe_blueberry_genetics_rejects_americas_and_raspberry_patent() -> None:
    europe = (
        "geography-europe",
        "geography-germany",
        "geography-spain",
        "geography-united-kingdom",
    )
    entities = {
        "company-hortifrut": {"id": "company-hortifrut", "name": "Hortifrut", "entity_type": "company"},
        "variety-example-red": {
            "id": "variety-example-red",
            "name": "Example Red",
            "entity_type": "variety",
            "berry_ids": ["berry-raspberry"],
        },
        "variety-eu-blue": {
            "id": "variety-eu-blue",
            "name": "Euro Blue",
            "entity_type": "variety",
            "berry_ids": ["berry-blueberry"],
        },
    }
    evidence = [
        {
            "id": "ev-hortifrut-mbo-genetics-2026",
            "title": "Naturipe Farms and Hortifrut expand berry genetics platform with Mountain Blue",
            "published_date": "2026-07-30",
            "entity_ids": ["company-hortifrut", "geography-united-states", "geography-mexico", "geography-peru"],
            "berry_ids": ["berry-blueberry"],
            "geography_ids": [],
        },
        {
            "id": "ev-sample-patent-published",
            "title": "Patent published for a late-ripening, high-yield raspberry genetics program",
            "published_date": "2026-07-15",
            "entity_ids": ["variety-example-red", "geography-europe"],
            "geography_ids": ["geography-europe"],
            "berry_ids": ["berry-raspberry"],
            "intake_type": "patent_filing",
            "patent_filing": {"application": "EP1"},
        },
        {
            "id": "ev-eu-blue-launch",
            "title": "Spanish blueberry breeding program names a new cultivar",
            "published_date": "2026-08-10",
            "entity_ids": ["variety-eu-blue", "geography-spain"],
            "geography_ids": ["geography-spain"],
            "berry_ids": ["berry-blueberry"],
        },
    ]
    packet = assemble_research_packet(
        _scope(
            question="What changed in European blueberry genetics?",
            company_ids=(),
            geography_ids=europe,
            topics=("genetics",),
        ),
        entities=entities,
        relationships=[],
        published_evidence=evidence,
        facts=[],
        signals=[],
        assessments=[],
        competitive_moves_provider=lambda _s: [
            {
                "id": "mv-mbo-americas",
                "title": "Hortifrut MBO Americas platform",
                "company_id": "company-hortifrut",
                "move_type": "VARIETY_COMMERCIALIZATION",
                "published_date": "2026-08-03",
                "event_date": "2026-08-03",
                "geography_ids": ["geography-peru", "geography-mexico", "geography-united-kingdom"],
                "berry_ids": ["berry-blueberry", "berry-raspberry"],
            },
            {
                "id": "mv-spain-genetics",
                "title": "Fall Creek names a Spanish blueberry selection",
                "company_id": "company-fall-creek",
                "move_type": "GENETICS_LAUNCH",
                "published_date": "2026-08-12",
                "event_date": "2026-08-12",
                "geography_ids": ["geography-spain"],
                "berry_ids": ["berry-blueberry"],
            },
        ],
        today=TODAY,
    )
    ids = {row["id"] for row in packet["evidence"]}
    assert "ev-eu-blue-launch" in ids
    assert "ev-hortifrut-mbo-genetics-2026" not in ids
    assert "ev-sample-patent-published" not in ids
    assert packet["rights_ip"] == []
    model = build_change_scenario(
        _scope(question="What changed in European blueberry genetics?", company_ids=(), geography_ids=europe, topics=("genetics",)),
        packet,
        today=TODAY,
    )
    blob = str(model).casefold()
    assert "mountain blue" not in blob
    assert "raspberry genetics program" not in blob
    assert "spanish blueberry" in blob or "spanish blueberry selection" in blob


def test_structured_market_reality_beats_article_language(tmp_path: Path) -> None:
    schemas = Path(__file__).resolve().parents[1] / "schemas"
    repo = MarketObservationRepository(data_dir=tmp_path, schemas_dir=schemas)
    base = {
        "record_type": "market_observation",
        "berry_id": "berry-blueberry",
        "source_commodity_label": "Fresh blueberries",
        "source_commodity_code": "BLUEBERRY",
        "form": "fresh",
        "source": "proarandanos",
        "source_dataset": "season-close",
        "source_url": "https://example.test/peru-blueberries",
        "captured_at": "2026-06-25T00:00:00+00:00",
        "berry_ids": ["berry-blueberry"],
        "geography_ids": ["geography-peru"],
        "period_type": "year",
    }
    for period, metric, geography, geography_id, unit, value, suffix in (
        ("2024/25", "EXPORT_VOLUME", "PE", "geography-peru", "MT", 319000.0, "vol-24"),
        ("2025/26", "EXPORT_VOLUME", "PE", "geography-peru", "MT", 382934.0, "vol-25"),
        ("2024/25", "PRICE", "PE", "geography-peru", "USD/kg", 6.61, "px-24"),
        ("2025/26", "PRICE", "PE", "geography-peru", "USD/kg", 5.55, "px-25"),
        ("2024/25", "EXPORT_VOLUME", "PE-to-US", "geography-peru", "MT", 155000.0, "us-24"),
        ("2025/26", "EXPORT_VOLUME", "PE-to-US", "geography-peru", "MT", 186000.0, "us-25"),
    ):
        repo.create({
            **base,
            "id": f"mkt-peru-{suffix}",
            "metric": metric,
            "geography": geography,
            "geography_id": geography_id,
            "period": period,
            "unit": unit,
            "value": value,
        })
    scope = _scope(
        question="What changed in Peru blueberries?",
        company_ids=(),
        geography_ids=("geography-peru",),
    )
    market_rows = market_context_for_research_scope(repo, scope, limit=6)
    assert market_rows
    packet = _packet(
        competitive_moves=[],
        market_context=market_rows,
        companies=[],
        evidence=[{
            "id": "ev-article-price",
            "title": "Overlapping supply windows pressure global blueberry prices - FreshPlaza",
            "published_date": "2026-08-01",
            "trust_class": "TRUSTED EVIDENCE",
        }],
    )
    model = build_change_scenario(scope, packet, today=TODAY)
    types = {row["change_type"] for row in model["changes"]}
    assert "SUPPLY_CHANGE" in types
    assert "MARKET_CONDITION_CHANGE" in types
    volume = next(row for row in model["changes"] if row["change_type"] == "SUPPLY_CHANGE")
    assert "319000" in volume["before"] or "319,000" in volume["what_changed"] or "319000" in volume["what_changed"]
    assert "382934" in volume["now"] or "382,934" in volume["what_changed"] or "32." in volume["what_changed"]
    assert all(not str(row.get("what_changed") or "").startswith("Overlapping supply") for row in model["changes"])
    assert model["scenarios"]
    for row in model["scenarios"]:
        assert row["source_ids"]
        assert row["why_plausible"]
        assert row["supporting_evidence"]
        assert row["would_confirm"]
        assert row["would_refute"]
        assert row["watch"]
        assert "will " not in row["text"].casefold()
        assert "%" not in row["text"] or "probability" not in row["text"].casefold()
    seam = change_scenario_for(scope, packet, today=TODAY)
    assert seam["what_changed"]
    assert seam["scenarios"][0]["would_confirm"]
    assert seam["scenarios"][0]["source_ids"]


def test_recently_observed_event_stays_real_change() -> None:
    row = _move(
        "mv-recent",
        company="company-hortifrut",
        move_type="PARTNERSHIP",
        event="2026-08-12",
        seen="2026-08-14",
        title="Hortifrut signs a new genetics counterpart",
    )
    row["latest_update"] = "2026-08-14"
    model = build_change_scenario(_scope(), _packet(competitive_moves=[row]), today=TODAY)
    types = {change["change_type"] for change in model["changes"]}
    assert "PARTNERSHIP_CHANGE" in types
    assert "COVERAGE_CHANGE" not in types
