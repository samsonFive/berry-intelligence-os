"""Existing assigned marks remain distinct from watches and imported crop tiers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.services import feed_first, investigation_api as api, investigation_tiers as tiers
from app.services.watchlist import add_watch


@pytest.fixture
def roster(tmp_path, monkeypatch):
    from app.services import competitor_registry
    main = SimpleNamespace(INBOX_DIR=tmp_path / "inbox", load_sources=lambda: [], all_facts=lambda: [],
                           all_signals=lambda: [], all_assessments=lambda: [])
    entities = {f"company-{index:02}": {"id": f"company-{index:02}", "name": f"Company {45-index:02}",
        "entity_type": "company", "status": "active", "aliases": ["Rare alias"] if index in {0, 44} else [],
        "attributes": {"tiers_by_berry": {"blueberry": "tier1"}}} for index in range(45)}
    assignments = {f"company-{index:02}": "tier1" if index < 11 else "tier2" if index < 19 else "tier3" for index in range(24)}
    assignments.update({"company-24": "watch", "company-25": "muted", "company-26": "old-custom-tier"})
    world = api.World(main, entities, [], [], {"entity_tiers": assignments})
    bundle = {"nodes": {"company-00": {"id": "company-00", "type": "company"}}, "edges": []}
    calls = []
    monkeypatch.setattr(competitor_registry, "monitoring_state_for_entity", lambda key, **kwargs: calls.append(key) or {"state": "no_supported_source", "detail": "No linked source"})
    return world, bundle, calls


def test_full_universe_groups_before_pagination_counts_and_legacy_values_remain_exact(roster):
    world, bundle, calls = roster
    ctx = api.normalize_context({})[0]
    first = api.monitoring_data(world, ctx, bundle, limit=10)
    second = api.monitoring_data(world, ctx, bundle, limit=10, offset=10)
    assert all(row["assigned_tier"] == "tier1" for row in first["companies"])
    assert [row["assigned_tier"] for row in second["companies"]] == ["tier1", *(["tier2"] * 8), "tier3"]
    assert len(calls) == 20, "Only the returned pages may compute collection health"
    groups = first["tier_groups"]
    assert [row["tier"] for row in groups] == ["tier1", "tier2", "tier3", "untiered", "watch", "muted", "other_legacy"]
    assert [row["count"] for row in groups] == [11, 8, 5, 18, 1, 1, 1]
    assert groups == second["tier_groups"]
    full = api.monitoring_data(world, ctx, bundle, limit=100)
    by_id = {row["id"]: row for row in full["companies"]}
    assert by_id["company-24"]["assigned_tier"] == "watch" and by_id["company-24"]["assigned_tier_label"] == "Legacy watch"
    assert by_id["company-25"]["assigned_tier"] == "muted"
    assert by_id["company-26"]["assigned_tier"] == "old-custom-tier"
    assert by_id["company-44"]["assigned_tier"] == "untiered", "Per-berry metadata cannot auto-assign shared tiers"
    assert len(by_id) == 45 and not world.main.INBOX_DIR.exists()


def test_search_and_watched_set_counts_are_distinct_from_page_counts(roster):
    world, bundle, _calls = roster
    ctx = api.normalize_context({"q": "Rare alias", "q_scope": "catalog"})[0]
    catalog = api.monitoring_data(world, ctx, bundle, limit=1)
    assert catalog["universe_count"] == 45 and catalog["matching_count"] == 2
    assert sum(row["count"] for row in catalog["tier_groups"]) == 45
    assert sum(row["matching_count"] for row in catalog["tier_groups"]) == 2
    scoped = api.monitoring_data(world, {**ctx, "q_scope": "scope"}, bundle)
    assert scoped["matching_count"] == 1 and scoped["companies"][0]["id"] == "company-00"
    for key in ("company-00", "company-24", "company-44"):
        add_watch(world.main.INBOX_DIR, "company", key)
    watched = api.monitoring_data(world, {**ctx, "q": "", "company_set": "watched"}, bundle)
    assert watched["universe_count"] == 3
    assert [row["assigned_tier"] for row in watched["companies"]] == ["tier1", "untiered", "watch"]
    assert sum(row["count"] for row in watched["tier_groups"]) == 3
    assert "independent of per-berry" in watched["tier_basis"]


def test_edit_reuses_existing_marks_and_history_and_preserves_other_state(tmp_path):
    state = feed_first.empty_state()
    state.update(entity_tiers={"company-a": "watch", "company-b": "muted", "company-c": "old-custom"},
                 entity_favorites={"company-a": True}, decisions={"ev-a": {"saved": True, "reaction": "up"}})
    feed_first.save_state(tmp_path, state)
    result = tiers.assign(tmp_path, entity_id="company-a", tier="tier2", expected_tier="watch", allowed={"company-a"})
    assert result == {"id": "company-a", "assigned_tier": "tier2", "assigned_tier_label": "Tier 2", "changed": True}
    reloaded = feed_first.load_state(tmp_path)
    assert reloaded["entity_tiers"] == {"company-a": "tier2", "company-b": "muted", "company-c": "old-custom"}
    assert reloaded["decisions"] == state["decisions"] and reloaded["entity_favorites"] == state["entity_favorites"]
    assert reloaded["entity_mark_history"][-1]["before"] == {"favorite": True, "tier": "watch"}
    assert reloaded["entity_mark_history"][-1]["action"] == "tier"
    snapshot = feed_first.state_path(tmp_path).read_bytes()
    for key, value in (("company-b", "muted"), ("company-c", "old-custom")):
        assert not tiers.assign(tmp_path, entity_id=key, tier=value, expected_tier=value, allowed={key})["changed"]
    assert feed_first.state_path(tmp_path).read_bytes() == snapshot
    with pytest.raises(ValueError, match="existing legacy"):
        tiers.assign(tmp_path, entity_id="company-a", tier="watch", allowed={"company-a"})


def test_expected_tier_compare_and_existing_writer_share_one_runtime_lock(tmp_path):
    barrier = Barrier(2)
    def change(value):
        barrier.wait()
        try:
            return tiers.assign(tmp_path, entity_id="company-a", tier=value, expected_tier="untiered", allowed={"company-a"})
        except tiers.TierConflict as error:
            return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(change, ["tier1", "tier2"]))
    assert sum(isinstance(value, tiers.TierConflict) for value in outcomes) == 1
    persisted = feed_first.load_state(tmp_path)
    assert len(persisted["entity_mark_history"]) == 1
    assert persisted["entity_tiers"]["company-a"] in {"tier1", "tier2"}


def test_invalid_existing_marks_are_never_reset_or_overwritten(tmp_path):
    path = feed_first.state_path(tmp_path)
    path.write_text('{"entity_tiers":[],"entity_mark_history":[]}', encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        tiers.assign(tmp_path, entity_id="company-a", tier="tier1", allowed={"company-a"})
    assert path.read_bytes() == before
    with pytest.raises(ValueError):
        tiers.assigned_tier({"entity_tiers": []}, "company-a")


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import main
    main_stub = SimpleNamespace(INBOX_DIR=tmp_path / "inbox", load_sources=lambda: [],
                               all_facts=lambda: [], all_signals=lambda: [], all_assessments=lambda: [])
    entities = {"company-a": {"id": "company-a", "name": "Company A", "entity_type": "company", "status": "active"},
                "variety-a": {"id": "variety-a", "name": "Variety A", "entity_type": "variety", "status": "active"}}
    world = api.World(main_stub, entities, [], [], {})
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", main_stub.INBOX_DIR)
    monkeypatch.setattr(api, "load_catalog_world", lambda: world)
    from app.landscape_explorer_routes import company_state
    monkeypatch.setattr(api, "load_world", lambda: api.World(main_stub, entities, [], [], company_state(main_stub.INBOX_DIR)))
    return TestClient(main.app, follow_redirects=False), main_stub


def test_json_adapter_confirmed_durable_reload_and_optimistic_conflict(client):
    http, main = client
    path = "/api/investigations/v1/companies/company-a/tier"
    response = http.post(path, json={"tier": "tier1", "expected_tier": "untiered"}, headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"})
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    assert response.json()["data"]["assigned_tier"] == "tier1"
    assert feed_first.load_state(main.INBOX_DIR)["entity_tiers"]["company-a"] == "tier1"
    reopened = http.get("/api/investigations/v1/monitoring")
    assert reopened.status_code == 200
    assert reopened.json()["data"]["companies"][0]["assigned_tier"] == "tier1"
    before = feed_first.state_path(main.INBOX_DIR).read_bytes()
    conflict = http.post(path, json={"tier": "tier2", "expected_tier": "untiered"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "tier_conflict"
    assert conflict.json()["detail"]["assigned_tier"] == "tier1"
    assert feed_first.state_path(main.INBOX_DIR).read_bytes() == before


@pytest.mark.parametrize("payload", [{}, {"tier": "watch"}, {"tier": "tier9"}, {"tier": None}, {"tier": True},
    {"tier": "tier1", "expected_tier": None}, {"tier": "tier1", "extra": "forbidden"}])
def test_json_adapter_invalid_values_fail_without_creating_state(client, payload):
    http, main = client
    assert http.post("/api/investigations/v1/companies/company-a/tier", json=payload).status_code == 422
    assert not feed_first.state_path(main.INBOX_DIR).exists()


def test_json_adapter_rejects_ambiguous_body_wrong_entity_and_cross_origin(client):
    http, main = client
    path = "/api/investigations/v1/companies/company-a/tier"
    assert http.post(path, content='{"tier":"tier1","tier":"tier2"}', headers={"Content-Type": "application/json"}).status_code == 422
    assert http.post(path, data={"tier": "tier1"}).status_code == 415
    assert http.post(path, content="x" * 2049, headers={"Content-Type": "application/json"}).status_code == 413
    assert http.post(path, json={"tier": "tier1"}, headers={"Origin": "https://external.example"}).status_code == 403
    assert http.post(path, json={"tier": "tier1"}, headers={"Sec-Fetch-Site": "same-site"}).status_code == 403
    for key in ("company-missing", "variety-a"):
        assert http.post(f"/api/investigations/v1/companies/{key}/tier", json={"tier": "tier1"}).status_code == 404
    assert not feed_first.state_path(main.INBOX_DIR).exists()


def test_remote_anonymous_and_public_only_cannot_assign(client, monkeypatch):
    from app import main
    http, stub = client
    path = "/api/investigations/v1/companies/company-a/tier"
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "fixture-operator")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "fixture-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "fixture-session-secret-long-enough")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    assert http.post(path, json={"tier": "tier1"}).status_code == 302
    assert not feed_first.state_path(stub.INBOX_DIR).exists()
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert http.post(path, json={"tier": "tier1"}).status_code == 403
    assert not feed_first.state_path(stub.INBOX_DIR).exists()


def test_signed_in_remote_session_can_assign_through_existing_auth_boundary(client, monkeypatch):
    from app import main
    _http, stub = client
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "fixture-tier-operator")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "fixture-tier-password")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "fixture-tier-session-secret-long-enough")
    monkeypatch.delenv("BIOS_BASIC_AUTH", raising=False)
    http = TestClient(main.app, base_url="https://testserver", follow_redirects=False)
    login = http.post("/login", data={"username": "fixture-tier-operator", "password": "fixture-tier-password", "next": "/app/landscape"})
    assert login.status_code == 303
    response = http.post("/api/investigations/v1/companies/company-a/tier",
        json={"tier": "tier3", "expected_tier": "untiered"}, headers={"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"})
    assert response.status_code == 200 and response.json()["data"]["assigned_tier"] == "tier3"
    assert feed_first.load_state(stub.INBOX_DIR)["entity_tiers"]["company-a"] == "tier3"


def test_demo_namespaces_remain_separate_and_strict():
    ctx, _issues = api.normalize_context({"demo_specimens": "demo-specimen-one,demo-brand-one"})
    assert ctx["demo_specimens"] == "demo-specimen-one,demo-brand-one"
    for key in ("demo-brand-", "demo-specimen-", "company-a", "brand-a", "demo-brand-x:wrong"):
        with pytest.raises(ValueError):
            api.normalize_context({"demo_specimens": key})
