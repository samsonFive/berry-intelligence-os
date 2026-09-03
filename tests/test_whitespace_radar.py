"""Strategic Whitespace Radar V1 — three-state discipline, no scores."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.whitespace_radar import (
    FORBIDDEN_CLAIMS,
    STATE_ACTIVE,
    STATE_LOW_ACTIVITY,
    STATE_LOW_COVERAGE,
    classify_cell,
    compose_whitespace_landscape,
    default_demo_scope,
    parse_id_list,
)

ENTITIES = {
    "berry-blueberry": {"id": "berry-blueberry", "entity_type": "berry", "name": "Blueberry"},
    "company-planasa": {"id": "company-planasa", "entity_type": "company", "name": "Planasa"},
    "company-fall-creek-farm-and-nursery": {
        "id": "company-fall-creek-farm-and-nursery",
        "entity_type": "company",
        "name": "Fall Creek Farm & Nursery, Inc.",
    },
    "company-hortifrut": {"id": "company-hortifrut", "entity_type": "company", "name": "Hortifrut S.A."},
    "geography-peru": {"id": "geography-peru", "entity_type": "geography", "name": "Peru"},
    "geography-europe": {"id": "geography-europe", "entity_type": "geography", "name": "Europe"},
    "geography-spain": {"id": "geography-spain", "entity_type": "geography", "name": "Spain"},
}

RELATIONSHIPS = [
    {
        "predicate": "part_of",
        "status": "active",
        "subject_id": "geography-spain",
        "object_id": "geography-europe",
    }
]


class _MarketRepo:
    def latest_by_key(self, **filters):
        if filters.get("berry_id") not in {None, "berry-blueberry"}:
            return []
        return [
            {
                "metric": "export_volume",
                "source_commodity_code": "BLUEBERRY",
                "source_commodity_label": "blueberries",
                "form": "fresh",
                "geography": "PE",
                "geography_id": "geography-peru",
                "period": "2024",
                "value": 100.0,
                "unit": "tonnes",
                "source": "Trade sample",
                "source_dataset": "demo",
                "source_url": "https://example.test/peru-exports",
                "captured_at": "2026-08-01T00:00:00+00:00",
            },
            {
                "metric": "export_volume",
                "source_commodity_code": "BLUEBERRY",
                "source_commodity_label": "blueberries",
                "form": "fresh",
                "geography": "PE",
                "geography_id": "geography-peru",
                "period": "2025",
                "value": 132.2,
                "unit": "tonnes",
                "source": "Trade sample",
                "source_dataset": "demo",
                "source_url": "https://example.test/peru-exports",
                "captured_at": "2026-08-01T00:00:00+00:00",
            },
        ]


def _move(company_id: str, geography_id: str, move_type: str, title: str) -> dict:
    return {
        "company_id": company_id,
        "company_name": ENTITIES[company_id]["name"],
        "move_type": move_type,
        "title": title,
        "what_happened": title,
        "geography_ids": [geography_id],
        "geography_labels": [ENTITIES[geography_id]["name"]],
        "berry_ids": ["berry-blueberry"],
        "berry_labels": ["Blueberry"],
        "variety_names": ["Sekoya"],
        "supporting_sources": [{"url": f"https://example.test/{company_id}", "publisher": "Example"}],
    }


def _landscape(**overrides):
    values = dict(
        berry_id="berry-blueberry",
        company_ids=list(default_demo_scope()["company_ids"]),
        geography_ids=["geography-peru", "geography-europe"],
        window_days=30,
        entities=ENTITIES,
        relationships=RELATIONSHIPS,
        published_evidence=[
            {
                "id": "ev-peru-1",
                "title": "Peru blueberry harvest",
                "entity_ids": ["geography-peru"],
                "geography_ids": ["geography-peru"],
                "berry_ids": ["berry-blueberry"],
            },
            {
                "id": "ev-spain-1",
                "title": "Spain blueberry harvest",
                "entity_ids": ["geography-spain"],
                "geography_ids": ["geography-spain"],
                "berry_ids": ["berry-blueberry"],
            },
        ],
        moves=[
            _move("company-planasa", "geography-spain", "GENETICS_LAUNCH", "Planasa launches in Spain"),
            _move("company-hortifrut", "geography-peru", "EXPANSION", "Hortifrut expands packing"),
            _move("company-hortifrut", "geography-peru", "GENETICS_LAUNCH", "Hortifrut genetics program"),
            _move("company-fall-creek-farm-and-nursery", "geography-peru", "GENETICS_LAUNCH", "Fall Creek genetics in Peru"),
            _move("company-fall-creek-farm-and-nursery", "geography-peru", "LICENSING", "Fall Creek licenses in Peru"),
        ],
        market_repo=_MarketRepo(),
    )
    values.update(overrides)
    return compose_whitespace_landscape(**values)


def test_classify_cell_judges_coverage_first() -> None:
    assert classify_cell(move_count=9, actor_count=4, coverage_adequate=False) == STATE_LOW_COVERAGE
    assert classify_cell(move_count=2, actor_count=1, coverage_adequate=True) == STATE_ACTIVE
    assert classify_cell(move_count=0, actor_count=0, coverage_adequate=True) == STATE_LOW_ACTIVITY


def test_europe_includes_spain_descendant() -> None:
    page = _landscape()
    cell = page["company_geo_lookup"]["company-planasa|geography-europe"]
    assert cell["move_count"] == 1
    assert cell["coverage_failure"]
    fall = page["company_geo_lookup"]["company-fall-creek-farm-and-nursery|geography-peru"]
    assert fall["move_count"] >= 1
    assert fall["state"] in {STATE_ACTIVE, STATE_LOW_ACTIVITY}


def test_peru_overlap_and_concentration() -> None:
    page = _landscape()
    assert any(row["geography_id"] == "geography-peru" for row in page["overlap"])
    genetics = page["geo_activity_lookup"]["geography-peru|genetics"]
    assert genetics["state"] == STATE_ACTIVE
    assert "Hortifrut S.A." in genetics["actor_names"]


def test_low_coverage_is_not_opportunity() -> None:
    page = _landscape(
        published_evidence=[],
        moves=[],
        market_repo=_EmptyRepo(),
    )
    europe = page["company_geo_lookup"]["company-planasa|geography-europe"]
    assert europe["state"] == STATE_LOW_COVERAGE
    joined = " ".join(item["text"] for item in page["coverage_gaps"]).casefold()
    assert "not opportunity" in joined
    assert "opportunity" in joined
    assert all("opportunity" not in item["text"].casefold() or "not" in item["text"].casefold() for item in page["investigate"])


def test_market_context_stays_separate_and_unallocated() -> None:
    page = _landscape()
    peru = page["geo_coverage"]["geography-peru"]
    assert peru["market"]
    assert "+32.2%" in peru["market"][0]["title"]
    for card in page["footprints"]:
        assert "32.2" not in str(card)
        assert "strength" not in str(card).casefold()


def test_ask_and_brief_handoffs() -> None:
    page = _landscape()
    assert page["company_geo"][0]["ask_href"].startswith("/research?")
    assert "Strategic whitespace landscape" in page["brief_focus_notes"]
    blob = str(page).casefold()
    for phrase in FORBIDDEN_CLAIMS:
        assert phrase not in blob
    assert "or a competitive score" in page["method_note"].casefold()


def test_manual_challenge_reclassifies_planasa_peru_as_coverage_failure() -> None:
    page = _landscape()
    cell = page["company_geo_lookup"]["company-planasa|geography-peru"]
    assert cell["state"] == STATE_LOW_COVERAGE
    assert cell["coverage_failure"]
    assert "coverage failure" in cell["coverage_failure"].casefold()
    assert any("Planasa's Peru" in item["text"] for item in page["coverage_gaps"])


def test_parse_id_list_falls_back() -> None:
    assert parse_id_list("", ("a", "b")) == ["a", "b"]
    assert parse_id_list("x, y", ("a",)) == ["x", "y"]


class _EmptyRepo:
    def latest_by_key(self, **filters):
        return []


def test_whitespace_page_renders(monkeypatch) -> None:
    page_model = _landscape()
    monkeypatch.setattr("app.main.compose_moves_board", lambda inbox_dir=None: type("B", (), {"moves": []})())
    monkeypatch.setattr("app.main.competitive_moves_for", lambda **kwargs: page_model["company_geo"])
    monkeypatch.setattr("app.main.compose_whitespace_landscape", lambda **kwargs: page_model)
    monkeypatch.setattr("app.main.entity_index", lambda: ENTITIES)
    monkeypatch.setattr("app.main.all_relationships", lambda: RELATIONSHIPS)
    monkeypatch.setattr("app.main.published_evidence", lambda: [])
    response = TestClient(app).get(
        "/whitespace?berry=berry-blueberry"
        "&companies=company-planasa,company-fall-creek-farm-and-nursery,company-hortifrut"
        "&geographies=geography-peru,geography-europe"
    )
    assert response.status_code == 200
    html = response.text
    assert "concentration vs whitespace" in html
    assert "LOW COVERAGE / UNKNOWN" in html
    assert "Create leadership brief" in html
    assert "Ask Berry OS about this" in html
    assert "Whitespace" in html
    for phrase in FORBIDDEN_CLAIMS:
        assert phrase not in html.casefold()
