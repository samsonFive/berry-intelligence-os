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


def test_victoria_search_keeps_weak_text_retrieval_separate_from_entity_grounding() -> None:
    payload = client.get("/api/search/global", params={"q": "Victoria", "berry": "global"}).json()
    victoria = next(row for row in _group(payload, "varieties") if row["id"] == "variety-victoria")
    costa = next(row for row in _group(payload, "intelligence") if row["id"] == "ev-costa-ownership-2024")

    assert victoria["matched_as"] == "canonical"
    assert costa["matched_as"] == "text"
    assert costa["rank"] < victoria["rank"]


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


def test_representative_warm_query_reports_timings(tmp_path: Path) -> None:
    queries = ["Driscoll's", "Planasa", "Malaika", "Mexico", "Strawberry", "Federal Register"]
    client.get("/api/search/global", params={"q": "Planasa"})
    timings = {}
    for query in queries:
        started = time.perf_counter()
        payload = client.get("/api/search/global", params={"q": query}).json()
        elapsed = (time.perf_counter() - started) * 1000
        timings[query] = {"http_ms": round(elapsed, 2), "server_ms": payload.get("elapsed_ms"), "count": payload.get("result_count")}
        assert payload["empty"] is False
    (tmp_path / "global_search_timings.json").write_text(json.dumps(timings, indent=2) + "\n")
    for query, row in timings.items():
        assert isinstance(row["server_ms"], (int, float)), (query, row)
        assert row["server_ms"] >= 0, (query, row)
        assert isinstance(row["count"], int), (query, row)


def _group(payload: dict, group_id: str) -> list[dict]:
    for group in payload.get("groups") or []:
        if group["id"] == group_id:
            return list(group.get("in_context") or []) + list(group.get("also_global") or [])
    return []


# --- Search Chronology & Recency Hardening V1 -------------------------------
# Date-fallback honesty: captured_date/created_at/proposed_at must never
# silently stand in for a real published_date (AGENTS.md durable rule).
# Default sort must be newest-reliable-date-first; undated last; relevance
# is opt-in only.


def _signal(**overrides):
    row = {
        "id": "signal-test",
        "record_type": "signal",
        "title": "Test signal",
        "status": "confirmed",
        "berry_ids": [],
        "entity_ids": [],
        "evidence_ids": [],
    }
    row.update(overrides)
    return row


def _assessment(**overrides):
    row = {
        "id": "assessment-test",
        "record_type": "assessment",
        "title": "Test assessment",
        "entity_ids": [],
        "created_at": "2026-08-10",
    }
    row.update(overrides)
    return row


def test_publication_with_published_date_shows_published_label() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono", entity_type="company", name="Chrono Farms")],
        published_evidence=[
            _evidence(id="ev-dated", title="Chrono Farms dated release", entity_ids=["company-chrono"], published_date="2026-08-15")
        ],
    )
    payload = search_global("Chrono Farms", pools, include_private=False)
    row = next(r for r in _group(payload, "intelligence") if r["id"] == "ev-dated")
    assert row["date"] == "2026-08-15"
    assert row["date_basis"] == "published_date"
    assert row["is_fallback_date"] is False
    assert row["date_display"] == "Published Aug 15, 2026"
    assert row["date_secondary"] == ""


def test_publication_with_only_captured_date_never_masquerades_as_published() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono2", entity_type="company", name="Chrono Ridge")],
        published_evidence=[
            _evidence(
                id="ev-captured-only",
                title="Chrono Ridge captured only",
                entity_ids=["company-chrono2"],
                published_date=None,
                captured_date="2026-08-20",
            )
        ],
    )
    payload = search_global("Chrono Ridge", pools, include_private=False)
    row = next(r for r in _group(payload, "intelligence") if r["id"] == "ev-captured-only")
    assert row["date"] == ""
    assert row["date_display"] == "Publication date unknown"
    assert row["date_secondary"] == "Captured Aug 20, 2026"
    assert "Aug 20, 2026" not in row["date_display"]


def test_publication_with_neither_date_shows_unknown_with_no_secondary() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono3", entity_type="company", name="Chrono Valley")],
        published_evidence=[
            _evidence(
                id="ev-no-dates",
                title="Chrono Valley no dates",
                entity_ids=["company-chrono3"],
                published_date=None,
                captured_date=None,
            )
        ],
    )
    payload = search_global("Chrono Valley", pools, include_private=False)
    row = next(r for r in _group(payload, "intelligence") if r["id"] == "ev-no-dates")
    assert row["date"] == ""
    assert row["date_display"] == "Publication date unknown"
    assert row["date_secondary"] == ""


def test_default_sort_is_newest_first_with_undated_last() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono4", entity_type="company", name="Chrono Bay")],
        published_evidence=[
            _evidence(id="ev-old", title="Chrono Bay old story", entity_ids=["company-chrono4"], published_date="2026-01-01"),
            _evidence(id="ev-new", title="Chrono Bay new story", entity_ids=["company-chrono4"], published_date="2026-08-01"),
            _evidence(id="ev-mid", title="Chrono Bay mid story", entity_ids=["company-chrono4"], published_date="2026-04-01"),
            _evidence(
                id="ev-undated",
                title="Chrono Bay undated story",
                entity_ids=["company-chrono4"],
                published_date=None,
                captured_date=None,
            ),
        ],
    )
    payload = search_global("Chrono Bay", pools, include_private=False)
    assert payload["sort"] == "newest"
    intel = _group(payload, "intelligence")
    ids_in_order = [r["id"] for r in intel if r["id"] in {"ev-old", "ev-new", "ev-mid", "ev-undated"}]
    assert ids_in_order == ["ev-new", "ev-mid", "ev-old", "ev-undated"]


def test_deterministic_tie_sort_is_stable_across_calls() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono5", entity_type="company", name="Chrono Delta")],
        published_evidence=[
            _evidence(id="ev-tie-b", title="Chrono Delta B story", entity_ids=["company-chrono5"], published_date="2026-05-01"),
            _evidence(id="ev-tie-a", title="Chrono Delta A story", entity_ids=["company-chrono5"], published_date="2026-05-01"),
        ],
    )
    first = search_global("Chrono Delta", pools, include_private=False)
    second = search_global("Chrono Delta", pools, include_private=False)
    order1 = [r["id"] for r in _group(first, "intelligence") if r["id"].startswith("ev-tie")]
    order2 = [r["id"] for r in _group(second, "intelligence") if r["id"].startswith("ev-tie")]
    assert order1 == order2
    assert set(order1) == {"ev-tie-a", "ev-tie-b"}


def test_commercial_observation_uses_observed_at_not_captured() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono6", entity_type="company", name="Chrono Retail")],
        published_evidence=[
            _evidence(
                id="ev-commercial",
                title="Chrono Retail retail listing",
                entity_ids=["company-chrono6"],
                intake_type="commercial_observation",
                commercial_observation={"observed_at": "2026-08-18", "retailer_name": "Test Retailer"},
                published_date="2026-08-01",
                captured_date="2026-08-19",
            )
        ],
    )
    payload = search_global("Chrono Retail", pools, include_private=False)
    row = next(r for r in _group(payload, "intelligence") if r["id"] == "ev-commercial")
    assert row["date"] == "2026-08-18"
    assert row["date_basis"] == "observed_at"
    assert row["is_fallback_date"] is False
    assert row["date_display"] == "Observed Aug 18, 2026"


def test_assessment_always_uses_created_at_label() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono7", entity_type="company", name="Chrono Peak")],
        assessments=[_assessment(id="assessment-chrono", title="Chrono Peak assessment", entity_ids=["company-chrono7"], created_at="2026-07-04")],
    )
    payload = search_global("Chrono Peak", pools, include_private=False)
    row = next(r for r in _group(payload, "assessments") if r["id"] == "assessment-chrono")
    assert row["date"] == "2026-07-04"
    assert row["date_basis"] == "created_at"
    assert row["is_fallback_date"] is False
    assert row["date_display"] == "Created Jul 4, 2026"


def test_signal_fallback_to_evidence_date_is_labeled_honestly() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono8", entity_type="company", name="Chrono Signal Co")],
        published_evidence=[
            _evidence(id="ev-for-signal", title="Chrono Signal Co coverage", entity_ids=["company-chrono8"], published_date="2026-06-01")
        ],
        signals=[
            _signal(
                id="signal-fallback",
                title="Chrono Signal Co momentum signal",
                entity_ids=["company-chrono8"],
                evidence_ids=["ev-for-signal"],
                first_seen=None,
                last_updated=None,
            )
        ],
    )
    payload = search_global("Chrono Signal Co", pools, include_private=False)
    row = next(r for r in _group(payload, "signals") if r["id"] == "signal-fallback")
    assert row["date"] == "2026-06-01"
    assert row["date_basis"] == "evidence_published_date"
    assert row["is_fallback_date"] is True


def test_signal_with_native_first_seen_is_not_flagged_as_fallback() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono9", entity_type="company", name="Chrono Native Co")],
        signals=[
            _signal(
                id="signal-native",
                title="Chrono Native Co native signal",
                entity_ids=["company-chrono9"],
                first_seen="2026-08-05",
            )
        ],
    )
    payload = search_global("Chrono Native Co", pools, include_private=False)
    row = next(r for r in _group(payload, "signals") if r["id"] == "signal-native")
    assert row["date"] == "2026-08-05"
    assert row["date_basis"] == "first_seen"
    assert row["is_fallback_date"] is False


def test_signal_with_no_date_anywhere_is_undated() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono10", entity_type="company", name="Chrono Blank Co")],
        signals=[
            _signal(
                id="signal-undated",
                title="Chrono Blank Co undated signal",
                entity_ids=["company-chrono10"],
                first_seen=None,
                last_updated=None,
                evidence_ids=[],
            )
        ],
    )
    payload = search_global("Chrono Blank Co", pools, include_private=False)
    row = next(r for r in _group(payload, "signals") if r["id"] == "signal-undated")
    assert row["date"] == ""
    assert row["date_display"] == "Date unknown"


def test_mixed_result_types_each_carry_honest_independent_dates() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono11", entity_type="company", name="Chrono Mixed Co")],
        published_evidence=[
            _evidence(id="ev-mixed", title="Chrono Mixed Co press coverage", entity_ids=["company-chrono11"], published_date="2026-03-01")
        ],
        signals=[_signal(id="signal-mixed", title="Chrono Mixed Co signal", entity_ids=["company-chrono11"], first_seen="2026-03-05")],
        assessments=[_assessment(id="assessment-mixed", title="Chrono Mixed Co assessment", entity_ids=["company-chrono11"], created_at="2026-03-10")],
    )
    payload = search_global("Chrono Mixed Co", pools, include_private=False)
    evidence_row = next(r for r in _group(payload, "intelligence") if r["id"] == "ev-mixed")
    signal_row = next(r for r in _group(payload, "signals") if r["id"] == "signal-mixed")
    assessment_row = next(r for r in _group(payload, "assessments") if r["id"] == "assessment-mixed")
    assert evidence_row["date_basis"] == "published_date"
    assert signal_row["date_basis"] == "first_seen"
    assert assessment_row["date_basis"] == "created_at"
    # Each result type is unambiguous about what kind of object it is.
    assert evidence_row["kind_label"] != signal_row["kind_label"] != assessment_row["kind_label"]


def test_explicit_relevance_sort_is_available_and_opt_in() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono12", entity_type="company", name="Chrono Relevance Co")],
        published_evidence=[
            _evidence(id="ev-rel-old", title="Chrono Relevance Co old", entity_ids=["company-chrono12"], published_date="2026-01-01"),
            _evidence(id="ev-rel-new", title="Chrono Relevance Co new", entity_ids=["company-chrono12"], published_date="2026-08-01"),
        ],
    )
    newest = search_global("Chrono Relevance Co", pools, include_private=False, sort="newest")
    relevance = search_global("Chrono Relevance Co", pools, include_private=False, sort="relevance")
    assert newest["sort"] == "newest"
    assert relevance["sort"] == "relevance"


def test_unknown_sort_value_falls_back_to_newest() -> None:
    pools = SearchPools(entities=[_entity(id="company-chrono13", entity_type="company", name="Chrono Fallback Co")])
    payload = search_global("Chrono Fallback Co", pools, include_private=False, sort="bogus")
    assert payload["sort"] == "newest"


def test_empty_query_results_have_no_dates_to_render() -> None:
    payload = search_global("Zzzznonexistentqueryxyz", SearchPools(), include_private=False)
    assert payload["empty"] is True
    assert payload["groups"] == []


def test_backward_compatible_search_url_without_sort_param_still_works() -> None:
    response = client.get("/api/search/global", params={"q": "Planasa"})
    assert response.status_code == 200
    assert response.json()["sort"] == "newest"


def test_search_page_get_is_read_only_and_renders_sort_control(monkeypatch) -> None:
    writes = {"count": 0}

    def boom_write(*_args, **_kwargs):
        writes["count"] += 1
        raise AssertionError("GET /search must never write")

    monkeypatch.setattr("pathlib.Path.write_text", boom_write)
    page = client.get("/search", params={"q": "Planasa", "sort": "newest"})
    assert page.status_code == 200
    assert writes["count"] == 0
    assert 'name="sort"' in page.text


def test_evidence_date_never_inherits_created_at_or_proposed_at() -> None:
    pools = SearchPools(
        entities=[_entity(id="company-chrono14", entity_type="company", name="Chrono No Leak Co")],
        published_evidence=[
            _evidence(
                id="ev-no-leak",
                title="Chrono No Leak Co story",
                entity_ids=["company-chrono14"],
                published_date=None,
                captured_date=None,
                created_at="2026-08-21",
                proposed_at="2026-08-22",
            )
        ],
    )
    payload = search_global("Chrono No Leak Co", pools, include_private=False)
    row = next(r for r in _group(payload, "intelligence") if r["id"] == "ev-no-leak")
    assert row["date"] == ""
    assert row["date_display"] == "Publication date unknown"
