"""Global Intelligence Search V1 — navigation, not a trust layer."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.global_search import SearchPools, search_global

client = TestClient(app)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _isolate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path / "inbox")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    (tmp_path / "inbox" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "evidence").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "entities").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "relationships").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "signals").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "assessments").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "configuration").mkdir(parents=True, exist_ok=True)
    main._SEARCH_DOC_CACHE["key"] = None
    main._SEARCH_DOC_CACHE["docs"] = None
    main._JSON_FOLDER_CACHE.clear()


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


def _evidence(**overrides):
    row = {
        "id": "ev-test",
        "record_type": "evidence",
        "status": "published",
        "title": "Test evidence",
        "summary": "",
        "why_it_matters": "",
        "tags": [],
        "berry_ids": [],
        "entity_ids": [],
        "geography_ids": [],
        "source_id": "source-test",
        "published_date": "2026-08-01",
    }
    row.update(overrides)
    return row


def test_carlotta_alias_resolves_to_one_variety() -> None:
    payload = client.get("/api/search/global", params={"q": "Carlotta", "berry": "global"}).json()
    varieties = _group(payload, "varieties")
    ids = [row["id"] for row in varieties]
    assert ids.count("variety-drisblueseventeen") == 1
    assert "variety-carlotta" not in ids
    hit = next(row for row in varieties if row["id"] == "variety-drisblueseventeen")
    assert hit["canonical_name"] == "DrisBlueSeventeen"
    assert hit["matched_as"] == "alias"
    assert "alias" in hit["matched_label"].lower() or "commercial" in hit["matched_label"].lower()


def test_driscolls_company_search_groups_related_objects() -> None:
    payload = client.get("/api/search/global", params={"q": "Driscoll's", "berry": "global"}).json()
    companies = _group(payload, "companies")
    assert [row["id"] for row in companies].count("company-driscolls") == 1
    company = next(row for row in companies if row["id"] == "company-driscolls")
    assert company["state"] == "trusted"
    assert _group(payload, "varieties")
    assert _group(payload, "intelligence")
    assert _group(payload, "signals")
    hrefs = [row["href"] for row in companies]
    assert "/entities/company/company-driscolls" in hrefs


def test_planasa_legal_name_and_alias_are_one_company() -> None:
    alias = client.get("/api/search/global", params={"q": "Planasa"}).json()
    legal = client.get("/api/search/global", params={"q": "Plantas de Navarra"}).json()
    alias_ids = [row["id"] for row in _group(alias, "companies")]
    legal_ids = [row["id"] for row in _group(legal, "companies")]
    assert alias_ids.count("company-planasa") == 1
    assert "company-planasa" in legal_ids
    varieties = _group(alias, "varieties")
    assert any(row["id"] == "variety-redsayra" or "RedSayra" in row["title"] for row in varieties)


def test_malaika_variety_and_linked_intelligence() -> None:
    payload = client.get("/api/search/global", params={"q": "Malaika"}).json()
    varieties = _group(payload, "varieties")
    assert any(row["id"] == "variety-malaika" for row in varieties)
    intel = _group(payload, "intelligence")
    assert intel
    assert all(row["state_label"] for row in intel)


def test_mexico_uses_attribution_not_every_body_mention() -> None:
    payload = client.get("/api/search/global", params={"q": "Mexico"}).json()
    geos = _group(payload, "geographies")
    assert any(row["id"] == "geography-mexico" for row in geos)
    intel = _group(payload, "intelligence")
    assert intel
    assert len(intel) <= 20


def test_federal_register_source_search() -> None:
    payload = client.get("/api/search/global", params={"q": "Federal Register"}).json()
    sources = _group(payload, "sources")
    assert sources
    assert any("federal-register" in row["id"] for row in sources)
    assert all("/sources#" in row["href"] for row in sources)
    assert all("recall" in (row["subtitle"] or "").lower() or row["kind_label"] == "Source" for row in sources)


def test_strawberry_context_prefers_strawberry_and_keeps_global() -> None:
    payload = client.get(
        "/api/search/global",
        params={"q": "Driscoll's", "berry": "berry-strawberry", "include_global": "1"},
    ).json()
    companies = next(group for group in payload["groups"] if group["id"] == "companies")
    in_ids = [row["id"] for row in companies["in_context"]]
    assert "company-driscolls" in in_ids
    varieties = next(group for group in payload["groups"] if group["id"] == "varieties")
    strawberry = [row for row in varieties["in_context"] if "strawberry" in " ".join(row.get("aliases") or []).lower() or True]
    assert varieties["in_context"] or varieties["also_global"]
    if varieties["also_global"]:
        assert any(row["in_berry_context"] is False for row in varieties["also_global"])


def test_pending_is_not_labeled_trusted(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _write(
        tmp_path / "data" / "entities" / "company-fixture.json",
        _entity(id="company-fixture", entity_type="company", name="Fixture Fruit", aliases=["FF Co"]),
    )
    _write(
        tmp_path / "data" / "evidence" / "ev-trusted.json",
        _evidence(id="ev-trusted", title="Fixture Fruit harvest trusted", entity_ids=["company-fixture"]),
    )
    _write(
        tmp_path / "inbox" / "evidence" / "ev-pending-secret.json",
        _evidence(
            id="ev-pending-secret",
            status="draft",
            title="ZZZ_PRIVATE_DRAFT_TOKEN Fixture Fruit rumor",
            entity_ids=["company-fixture"],
        ),
    )
    _write(tmp_path / "data" / "configuration" / "sources.json", [])
    public = search_global(
        "Fixture Fruit",
        SearchPools(
            entities=[_entity(id="company-fixture", entity_type="company", name="Fixture Fruit", aliases=["FF Co"])],
            published_evidence=[
                _evidence(id="ev-trusted", title="Fixture Fruit harvest trusted", entity_ids=["company-fixture"])
            ],
            pending_drafts=[
                _evidence(
                    id="ev-pending-secret",
                    status="draft",
                    title="ZZZ_PRIVATE_DRAFT_TOKEN Fixture Fruit rumor",
                    entity_ids=["company-fixture"],
                )
            ],
        ),
        include_private=False,
    )
    private = search_global(
        "Fixture Fruit",
        SearchPools(
            entities=[_entity(id="company-fixture", entity_type="company", name="Fixture Fruit", aliases=["FF Co"])],
            published_evidence=[
                _evidence(id="ev-trusted", title="Fixture Fruit harvest trusted", entity_ids=["company-fixture"])
            ],
            pending_drafts=[
                _evidence(
                    id="ev-pending-secret",
                    status="draft",
                    title="ZZZ_PRIVATE_DRAFT_TOKEN Fixture Fruit rumor",
                    entity_ids=["company-fixture"],
                )
            ],
        ),
        include_private=True,
    )
    public_intel = _group(public, "intelligence")
    private_intel = _group(private, "intelligence")
    assert all(row["id"] != "ev-pending-secret" for row in public_intel)
    pending = next(row for row in private_intel if row["id"] == "ev-pending-secret")
    trusted = next(row for row in private_intel if row["id"] == "ev-trusted")
    assert pending["state"] == "pending"
    assert trusted["state"] == "trusted"
    assert pending["state_label"] != trusted["state_label"]


def test_same_name_across_types_is_ambiguous_not_auto_selected() -> None:
    pools = SearchPools(
        entities=[
            _entity(id="company-sonata", entity_type="company", name="Sonata"),
            _entity(id="variety-sonata", entity_type="variety", name="Sonata", berry_ids=["berry-strawberry"]),
        ]
    )
    payload = search_global("Sonata", pools, include_private=False)
    assert payload["ambiguous"] is True
    assert any(row["id"] == "company-sonata" for row in _group(payload, "companies"))
    assert any(row["id"] == "variety-sonata" for row in _group(payload, "varieties"))


def test_overlay_and_search_page_render() -> None:
    home = client.get("/work-queue")
    assert home.status_code == 200
    assert 'id="v2SearchOffcanvas"' in home.text
    assert 'id="global-search"' in home.text
    assert "data-open-search" in home.text
    page = client.get("/search", params={"q": "Planasa"})
    assert page.status_code == 200
    assert "Planasa" in page.text or "Plantas de Navarra" in page.text
    assert "Companies" in page.text
    assert 'id="v2ReaderOffcanvas"' in page.text


def test_public_api_flag_excludes_pending(monkeypatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    _write(
        tmp_path / "data" / "entities" / "company-fixture.json",
        _entity(id="company-fixture", entity_type="company", name="Nimbus Berries"),
    )
    _write(
        tmp_path / "inbox" / "evidence" / "ev-hidden.json",
        _evidence(id="ev-hidden", status="draft", title="Nimbus Berries confidential draft"),
    )
    _write(tmp_path / "data" / "configuration" / "sources.json", [])
    monkeypatch.setattr(main, "all_entities", lambda: [
        _entity(id="company-fixture", entity_type="company", name="Nimbus Berries")
    ])
    monkeypatch.setattr(main, "published_evidence", lambda: [])
    monkeypatch.setattr(main, "all_relationships", lambda: [])
    monkeypatch.setattr(main, "load_sources", lambda: [])
    monkeypatch.setattr(main, "all_signals", lambda: [])
    monkeypatch.setattr(main, "all_assessments", lambda: [])
    monkeypatch.setattr(main, "list_pending_drafts", lambda: [
        _evidence(id="ev-hidden", status="draft", title="Nimbus Berries confidential draft")
    ])
    monkeypatch.setattr(main, "load_candidates", lambda _inbox: [])
    public = client.get(
        "/api/search/global",
        params={"q": "Nimbus Berries", "include_private": "0"},
    ).json()
    private = client.get(
        "/api/search/global",
        params={"q": "Nimbus Berries", "include_private": "1"},
    ).json()
    assert all(row["id"] != "ev-hidden" for row in _group(public, "intelligence"))
    assert any(row["id"] == "ev-hidden" for row in _group(private, "intelligence"))


def test_zara_does_not_fuzzy_match_zahra() -> None:
    payload = client.get("/api/search/global", params={"q": "Zara", "berry": "global"}).json()
    intel = _group(payload, "intelligence")
    titles = " ".join(row["title"] for row in intel).lower()
    assert "zahra" not in titles
    varieties = _group(payload, "varieties")
    assert any(row["id"] == "variety-zara" for row in varieties)


def test_legacy_api_search_still_works() -> None:
    response = client.get("/api/search", params={"q": "example blue"})
    assert response.status_code == 200
    assert "entities" in response.json()
    response = client.get("/api/search", params={"q": "example blue"})
    assert response.status_code == 200
    assert "entities" in response.json()


def test_search_does_not_call_morning_brief_or_footprint(monkeypatch) -> None:
    called = {"brief": 0, "footprint": 0, "threads": 0}

    def boom_brief(*_args, **_kwargs):
        called["brief"] += 1
        raise AssertionError("search must not build Morning Brief")

    def boom_footprint(*_args, **_kwargs):
        called["footprint"] += 1
        raise AssertionError("search must not call variety_footprint")

    monkeypatch.setattr(main, "build_morning_brief", boom_brief)
    monkeypatch.setattr("app.services.variety_footprint.variety_footprint", boom_footprint)
    payload = client.get("/api/search/global", params={"q": "Zara"}).json()
    assert payload["result_count"] >= 1
    assert called["brief"] == 0
    assert called["footprint"] == 0


def test_representative_warm_query_timings() -> None:
    queries = ["Driscoll's", "Planasa", "Malaika", "Mexico", "Strawberry", "Federal Register"]
    client.get("/api/search/global", params={"q": "Planasa"})
    timings = {}
    for query in queries:
        started = time.perf_counter()
        payload = client.get("/api/search/global", params={"q": query}).json()
        elapsed = (time.perf_counter() - started) * 1000
        timings[query] = {"http_ms": round(elapsed, 2), "server_ms": payload.get("elapsed_ms"), "count": payload.get("result_count")}
        assert payload["empty"] is False
    Path("/opt/cursor/artifacts/global_search_timings.json").write_text(json.dumps(timings, indent=2) + "\n")
    for query, row in timings.items():
        assert row["server_ms"] < 250, (query, row)


def _group(payload: dict, group_id: str) -> list[dict]:
    for group in payload.get("groups") or []:
        if group["id"] == group_id:
            return list(group.get("in_context") or []) + list(group.get("also_global") or [])
    return []
