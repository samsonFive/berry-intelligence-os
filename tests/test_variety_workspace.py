"""Variety Intelligence UI V1 — presentation over Variety Backbone queries."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services import variety_footprint as footprint_mod
from app.services.variety_workspace import (
    identity_fields,
    present_competition,
    present_observation,
    present_observation_workspace,
    present_variety_index,
    uk_pilot_summary,
)

BERRY_LABELS = {
    "berry-blueberry": "Blueberry",
    "berry-strawberry": "Strawberry",
    "berry-raspberry": "Raspberry",
    "berry-blackberry": "Blackberry",
}

RETAILERS = (
    ("retailer-tesco", "Tesco"),
    ("retailer-sainsburys", "Sainsbury's"),
    ("retailer-waitrose", "Waitrose"),
    ("retailer-asda", "Asda"),
)
BERRIES = (
    "berry-strawberry",
    "berry-blueberry",
    "berry-raspberry",
    "berry-blackberry",
)


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "evidence").mkdir(parents=True, exist_ok=True)


def _entity(**overrides):
    row = {
        "record_type": "entity",
        "status": "active",
        "aliases": [],
        "description": "",
        "roles": [],
        "berry_ids": [],
        "evidence_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "attributes": {},
    }
    row.update(overrides)
    return row


def _uk_pilot_entities():
    rows = [
        _entity(id="company-driscolls", entity_type="company", name="Driscoll's, Inc."),
        _entity(
            id="variety-zara",
            entity_type="variety",
            name="Zara",
            aliases=["Driscoll's Zara"],
            berry_ids=["berry-strawberry"],
            attributes={"commercial_name": "Zara"},
        ),
        _entity(
            id="variety-victoria",
            entity_type="variety",
            name="Victoria",
            aliases=["Driscoll's Victoria"],
            berry_ids=["berry-blackberry"],
            attributes={"commercial_name": "Victoria"},
        ),
        _entity(
            id="variety-drisblueseventeen",
            entity_type="variety",
            name="DrisBlueSeventeen",
            aliases=["Carlotta", "Drisblueseventeen"],
            berry_ids=["berry-blueberry"],
            attributes={"trade_name": "Carlotta", "denomination": "DrisBlueSeventeen"},
        ),
        _entity(id="geography-united-kingdom", entity_type="geography", name="United Kingdom"),
    ]
    for retailer_id, name in RETAILERS:
        rows.append(_entity(id=retailer_id, entity_type="retailer", name=name))
    return rows


def _uk_pilot_observations():
    """18 UK listings: 2 named (Zara, Victoria) + 16 unnamed. Four berries, several retailers."""
    named = [
        {
            "id": "ev-uk-zara",
            "record_type": "evidence",
            "status": "draft",
            "review_state": "in_review",
            "source_type": "field_observation",
            "intake_type": "commercial_observation",
            "source_name": "Open Food Facts",
            "title": "Tesco British Zara strawberries",
            "captured_date": "2026-06-01",
            "berry_ids": ["berry-strawberry"],
            "geography_ids": ["geography-united-kingdom"],
            "entity_ids": ["variety-zara", "retailer-tesco"],
            "does_not_prove": "A listing is not proof of market share.",
            "commercial_observation": {
                "retailer_entity_id": "retailer-tesco",
                "retailer_name": "Tesco",
                "channel": "supermarket",
                "variety_entity_id": "variety-zara",
                "market_country": "United Kingdom",
                "observed_at": "2026-06-01",
                "brand": "Driscoll's",
                "price": "2.50",
                "currency": "GBP",
                "pack_size": "400g",
                "claims": ["British strawberries"],
            },
        },
        {
            "id": "ev-uk-victoria",
            "record_type": "evidence",
            "status": "draft",
            "review_state": "in_review",
            "source_type": "field_observation",
            "intake_type": "commercial_observation",
            "source_name": "Open Food Facts",
            "title": "Waitrose Victoria blackberries",
            "captured_date": "2026-06-02",
            "berry_ids": ["berry-blackberry"],
            "geography_ids": ["geography-united-kingdom"],
            "entity_ids": ["variety-victoria", "retailer-waitrose"],
            "does_not_prove": "A listing is not proof of market share.",
            "commercial_observation": {
                "retailer_entity_id": "retailer-waitrose",
                "retailer_name": "Waitrose",
                "channel": "supermarket",
                "variety_entity_id": "variety-victoria",
                "market_country": "United Kingdom",
                "observed_at": "2026-06-02",
                "brand": "Driscoll's",
            },
        },
    ]
    unnamed = []
    for index in range(16):
        berry = BERRIES[index % 4]
        retailer_id, retailer_name = RETAILERS[index % 4]
        unnamed.append(
            {
                "id": f"ev-uk-unnamed-{index:02d}",
                "record_type": "evidence",
                "status": "draft",
                "review_state": "in_review",
                "source_type": "field_observation",
                "intake_type": "commercial_observation",
                "source_name": "Open Food Facts",
                "title": f"{retailer_name} own-label berries {index}",
                "captured_date": f"2026-06-{10 + index:02d}",
                "berry_ids": [berry],
                "geography_ids": ["geography-united-kingdom"],
                "entity_ids": [retailer_id],
                "does_not_prove": "No cultivar name on the listing does not mean the variety is unknown globally.",
                "commercial_observation": {
                    "retailer_entity_id": retailer_id,
                    "retailer_name": retailer_name,
                    "channel": "supermarket",
                    "variety_entity_id": None,
                    "market_country": "United Kingdom",
                    "observed_at": f"2026-06-{10 + index:02d}",
                },
            }
        )
    return named + unnamed


def test_identity_keeps_canonical_commercial_and_alias_distinct() -> None:
    identity = identity_fields(
        {
            "id": "variety-drisblueseventeen",
            "name": "DrisBlueSeventeen",
            "aliases": ["Carlotta", "Drisblueseventeen"],
            "attributes": {"trade_name": "Carlotta", "denomination": "DrisBlueSeventeen", "selection_code": "X17"},
        }
    )
    assert identity["canonical_name"] == "DrisBlueSeventeen"
    assert identity["commercial_names"] == ["Carlotta"]
    assert "Carlotta" not in identity["aliases"]
    assert "Drisblueseventeen" not in identity["aliases"]
    assert identity["denomination"] == ""
    assert identity["breeder_code"] == "X17"


def test_uk_pilot_empty_runtime_is_honest() -> None:
    summary = uk_pilot_summary([], entities={"variety-zara": {"id": "variety-zara", "name": "Zara", "entity_type": "variety"}})
    assert summary["expected_total"] == 18
    assert summary["expected_named"] == 2
    assert summary["runtime_total"] == 0
    assert "not loaded in this runtime" in summary["honest_copy"]
    assert "not fabricated" in summary["honest_copy"]
    assert "16 of 18" in summary["honest_copy"]


def test_uk_pilot_fixture_is_eighteen_with_two_named() -> None:
    entities = {row["id"]: row for row in _uk_pilot_entities()}
    rows = [
        present_observation(record, entities=entities, trust="draft (pending review)")
        for record in _uk_pilot_observations()
    ]
    summary = uk_pilot_summary(rows, entities=entities)
    assert summary["runtime_total"] == 18
    assert summary["runtime_named"] == 2
    assert summary["runtime_unnamed"] == 16
    assert set(summary["berries"]) == set(BERRIES)
    assert "Tesco" in summary["retailers"]
    assert "Waitrose" in summary["retailers"]
    assert "2 of 18 UK listings name a cultivar" in summary["honest_copy"]
    unnamed = [row for row in rows if row["variety_unknown"]]
    assert all("No named variety" not in (row.get("title") or "") for row in unnamed)
    assert unnamed[0]["variety_named"] is False
    assert "not trusted Facts" not in unnamed[0]["title"]
    presented = present_observation_workspace(
        entities=list(entities.values()),
        published_evidence=[],
        inbox_drafts=_uk_pilot_observations(),
        berry_labels=BERRY_LABELS,
    )
    assert presented["named_count"] == 2
    assert presented["unnamed_count"] == 16
    zara = next(row for row in presented["observation_rows"] if row["id"] == "ev-uk-zara")
    assert zara["is_draft"] is True
    assert zara["price_label"] == "GBP 2.50"
    assert zara["claims"] == ["British strawberries"]
    assert zara["does_not_prove"]


def test_index_does_not_call_variety_footprint(monkeypatch) -> None:
    calls = {"n": 0}
    original = footprint_mod.variety_footprint

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(footprint_mod, "variety_footprint", wrapped)
    monkeypatch.setattr("app.services.variety_workspace.variety_footprint", wrapped)
    present_variety_index(
        varieties=[row for row in _uk_pilot_entities() if row["entity_type"] == "variety"],
        entities=_uk_pilot_entities(),
        relationships=[],
        published_evidence=[],
        berry_labels=BERRY_LABELS,
        inbox_drafts=_uk_pilot_observations(),
    )
    assert calls["n"] == 0


def test_index_route_does_not_call_footprint_or_compete(monkeypatch) -> None:
    calls = {"footprint": 0, "compete": 0}
    original_fp = footprint_mod.variety_footprint
    original_compete = footprint_mod.competing_varieties_in_berry_market

    def wrap_fp(*args, **kwargs):
        calls["footprint"] += 1
        return original_fp(*args, **kwargs)

    def wrap_compete(*args, **kwargs):
        calls["compete"] += 1
        return original_compete(*args, **kwargs)

    monkeypatch.setattr("app.services.variety_workspace.variety_footprint", wrap_fp)
    monkeypatch.setattr("app.services.variety_workspace.competing_varieties_in_berry_market", wrap_compete)
    monkeypatch.setattr(footprint_mod, "variety_footprint", wrap_fp)
    monkeypatch.setattr(footprint_mod, "competing_varieties_in_berry_market", wrap_compete)
    client = TestClient(app)
    page = client.get("/entities/variety")
    assert page.status_code == 200
    assert calls["footprint"] == 0
    assert calls["compete"] == 0
    assert "Variety Intelligence" in page.text
    assert "not a cultivar catalog" in page.text.casefold()
    assert "v2-variety-card" in page.text
    assert "Zara" in page.text
    assert "Victoria" in page.text
    assert "DrisBlueSeventeen" in page.text
    # Real, current count as of Caneberry Variety + Actor Expansion V1
    # (2026-08-22): blackberry has 5 tracked varieties (Victoria, Ervin,
    # Ponca, Ouachita, BK 6-13), so "(thin)" (the berry_inventory() <=1
    # threshold) no longer applies -- was "Blackberry 1 (thin)".
    assert "Blackberry 5" in page.text
    assert "(thin)" not in page.text


def test_detail_calls_footprint_once() -> None:
    client = TestClient(app)
    page = client.get("/entities/variety/variety-drisblueseventeen")
    assert page.status_code == 200
    html = page.text
    assert "DrisBlueSeventeen" in html
    assert "Carlotta" in html
    assert "Breeder" in html
    assert "Owner / rights holder" in html
    assert "Marketer" in html
    assert "Licensee" in html
    assert html.count("Driscoll") >= 2
    assert "Who is involved" in html
    assert "Commercial footprint" in html
    assert "id=\"v2ReaderOffcanvas\"" in html
    assert "data-open-reader" in html
    assert "variety-specific reader" not in html.casefold()


def test_zara_and_victoria_are_named_pilot_cases() -> None:
    client = TestClient(app)
    zara = client.get("/entities/variety/variety-zara")
    victoria = client.get("/entities/variety/variety-victoria")
    assert zara.status_code == 200
    assert victoria.status_code == 200
    assert "UK retail pilot named-variety case" in zara.text
    assert "UK retail pilot named-variety case" in victoria.text
    assert "Driscoll" in zara.text
    assert "Zara" in zara.text
    assert "Aliases:" in zara.text
    assert "Victoria" in victoria.text
    assert "Aliases:" in victoria.text
    assert "Marketer" in zara.text
    assert "Do not create separate pages" not in zara.text
    assert "Victoria" in victoria.text
    assert "Aliases:" in victoria.text


def test_observations_runtime_without_inbox_is_honest(monkeypatch, tmp_path: Path) -> None:
    isolated_inbox = tmp_path / "inbox"
    isolated_inbox.mkdir()
    monkeypatch.setattr(main, "INBOX_DIR", isolated_inbox)
    client = TestClient(app)
    page = client.get("/entities/variety?view=observations")
    assert page.status_code == 200
    assert "UK retail observation pilot" in page.text
    assert "not loaded in this runtime" in page.text
    assert "not fabricated" in page.text
    assert "variety-zara" in page.text
    assert "variety-victoria" in page.text
    assert "ev-sample-retail-placement" not in page.text or "is not the UK pilot" in page.text


def test_competition_needs_a_berry_and_blackberry_thin_is_count_driven() -> None:
    client = TestClient(app)
    global_page = client.get("/entities/variety?view=compete")
    assert global_page.status_code == 200
    assert "Select a berry" in global_page.text
    assert "No competitive-intensity score" in global_page.text or "No competitive-intensity score" in global_page.text.replace("—", "-")
    blueberry = client.get("/entities/variety", params={"view": "compete", "berry": "berry-blueberry"})
    assert blueberry.status_code == 200
    assert "Driscoll" in blueberry.text
    assert "competitive-intensity" not in blueberry.text or "none exists" in blueberry.text
    blackberry = client.get("/entities/variety", params={"view": "compete", "berry": "berry-blackberry"})
    assert blackberry.status_code == 200
    # Real, current state as of Caneberry Variety + Actor Expansion V1
    # (2026-08-22): blackberry_thin is now count-driven (<=1 varieties),
    # matching berry_inventory()'s own "thin" threshold, not hardcoded to
    # `berry_id == "berry-blackberry"`. Blackberry has 5 real varieties
    # now, so the "Blackberry is honestly thin" copy correctly does not
    # render -- it would still render if the real count ever dropped to
    # <=1 again, since the flag is genuinely data-driven.
    assert "Blackberry is honestly thin" not in blackberry.text
    assert "Victoria" in blackberry.text
    assert "Ervin" in blackberry.text
    assert "Ponca" in blackberry.text
    assert "Ouachita" in blackberry.text
    overlap = client.get(
        "/entities/variety",
        params={"view": "compete", "berry": "berry-blueberry", "ip_and_observation": "1"},
    )
    assert overlap.status_code == 200
    assert "TD-023" in overlap.text or "No variety currently has both IP activity" in overlap.text


def test_context_bar_filters_variety_index() -> None:
    client = TestClient(app)
    client.cookies.set("bios_berry", "berry-strawberry")
    page = client.get("/entities/variety")
    assert page.status_code == 200
    assert "Zara" in page.text
    assert "DrisBlueSeventeen" not in page.text
    raspberry = TestClient(app)
    raspberry.cookies.set("bios_berry", "berry-raspberry")
    page = raspberry.get("/entities/variety")
    assert "Zara" not in page.text
    blackberry = TestClient(app)
    blackberry.cookies.set("bios_berry", "berry-blackberry")
    page = blackberry.get("/entities/variety")
    assert "Victoria" in page.text
    assert "Ervin" in page.text
    # Real, current count as of Caneberry Variety + Actor Expansion V1
    # (2026-08-22): blackberry has 5 varieties, no berry is at the
    # berry_inventory() <=1 "thin" threshold -- was "(thin)" present.
    assert "(thin)" not in page.text


def test_variety_pages_do_not_rank_brief(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    main.save_entity(
        _entity(
            id="variety-fixture",
            entity_type="variety",
            name="Fixture Variety",
            berry_ids=["berry-blueberry"],
        )
    )
    modes: list[str] = []
    original = main.build_morning_brief
    original_discovered = main.list_discovered_items
    discovered: list[str] = []

    def wrapped(*args, **kwargs):
        modes.append(str(kwargs.get("mode") or "full"))
        return original(*args, **kwargs)

    def wrapped_discovered(*args, **kwargs):
        discovered.append("called")
        return original_discovered(*args, **kwargs)

    monkeypatch.setattr(main, "build_morning_brief", wrapped)
    monkeypatch.setattr(main, "list_discovered_items", wrapped_discovered)
    main._NAV_WORK_CACHE["key"] = None
    main._NAV_WORK_CACHE["value"] = None
    client = TestClient(app)
    assert client.get("/entities/variety").status_code == 200
    assert client.get("/entities/variety?view=compete").status_code == 200
    assert client.get("/entities/variety?view=observations").status_code == 200
    assert client.get("/entities/variety/variety-fixture").status_code == 200
    assert modes == []
    assert discovered == []


def test_competition_presenter_does_not_invent_a_score() -> None:
    groups = present_competition(
        berry_id="berry-blueberry",
        country_geo_id=None,
        entities=_uk_pilot_entities(),
        relationships=[
            {
                "id": "rel-driscolls-develops-x17",
                "subject_id": "company-driscolls",
                "predicate": "develops",
                "object_id": "variety-drisblueseventeen",
            }
        ],
        published_evidence=[],
        berry_labels=BERRY_LABELS,
    )
    assert groups["needs_berry"] is False
    assert "score" not in groups
    assert groups["ip_overlap_empty"] is True
    blackberry = present_competition(
        berry_id="berry-blackberry",
        country_geo_id=None,
        entities=_uk_pilot_entities(),
        relationships=[],
        published_evidence=[],
        berry_labels=BERRY_LABELS,
    )
    assert blackberry["blackberry_thin"] is True
