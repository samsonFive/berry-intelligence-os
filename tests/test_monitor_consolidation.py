"""State, privacy and handoff checks for consolidated monitoring and operations."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import main
from app.services import watchlist
from app.services.watchtower.store import apply_alert_action, load_alert_state, STATE_RELATIVE


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    return tmp_path, TestClient(main.app)


def test_damaged_watch_store_is_never_replaced(tmp_path):
    path = watchlist.state_path(tmp_path)
    path.write_text('{"watches": "damaged"}', encoding="utf-8")
    before = path.read_bytes()
    for action in (watchlist.add_watch, watchlist.remove_watch, watchlist.mark_watch_seen):
        with pytest.raises(ValueError, match="left unchanged"):
            action(tmp_path, "company", "company-planasa")
        assert path.read_bytes() == before


def test_watch_writes_keep_metadata_and_other_concurrent_watches(tmp_path):
    path = watchlist.state_path(tmp_path)
    path.write_text(json.dumps({"watches": [], "migration_notes": "Keep me"}), encoding="utf-8")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda key: watchlist.add_watch(tmp_path, "company", key), ["a", "b", "c", "d"]))
    assert {row["object_id"] for row in watchlist.load_watches(tmp_path)} == {"a", "b", "c", "d"}
    assert json.loads(path.read_text())["migration_notes"] == "Keep me"


def test_alert_decisions_retain_history_and_fail_closed_on_damaged_store(tmp_path):
    apply_alert_action(tmp_path, "alert-1", "mark_read")
    apply_alert_action(tmp_path, "alert-1", "dismiss")
    row = load_alert_state(tmp_path)["alert-1"]
    assert row["state"] == "dismissed" and row["history"][0]["state"] == "read"
    path = tmp_path / STATE_RELATIVE
    path.write_text("{ damaged", encoding="utf-8")
    with pytest.raises(ValueError, match="left unchanged"):
        apply_alert_action(tmp_path, "alert-2", "mark_read")
    assert path.read_text() == "{ damaged"


@pytest.mark.parametrize("kind,key,target", [("berry", "berry-blueberry", "/today?berry=berry-blueberry"), ("move_type", "GENETICS_LAUNCH", "/moves")])
def test_open_berry_and_move_watch_routes_to_the_right_surface(workspace, kind, key, target):
    inbox, client = workspace
    watchlist.add_watch(inbox, kind, key)
    before = watchlist.load_watches(inbox)[0]
    assert before["last_seen_at"] is None
    response = client.get("/watches/open", params={"watch_type": kind, "object_id": key}, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == target
    assert watchlist.load_watches(inbox)[0]["last_seen_at"]


def test_stale_watch_is_visible_and_open_does_not_mark_it_seen(workspace):
    inbox, client = workspace
    watchlist.add_watch(inbox, "company", "company-no-longer-resolves")
    page = client.get("/monitor")
    assert page.status_code == 200 and "watches need an identity check" in page.text
    assert "Unavailable subject" in page.text
    response = client.get("/watches/open?watch_type=company&object_id=company-no-longer-resolves")
    assert response.status_code == 404
    assert watchlist.load_watches(inbox)[0]["last_seen_at"] is None


def test_monitor_browse_never_changes_user_state_or_calls_collection(workspace, monkeypatch):
    inbox, client = workspace
    watchlist.add_watch(inbox, "company", "company-planasa")
    before = {path.relative_to(inbox): path.read_bytes() for path in inbox.rglob("*") if path.is_file()}
    def forbidden(*args, **kwargs):
        raise AssertionError("Browse must not run collection or persist alert content")
    monkeypatch.setattr(main, "trigger_bounded_run", forbidden)
    monkeypatch.setattr("app.services.watchtower.compose.persist_alerts", forbidden)
    for route in ("/monitor", "/monitor?view=alerts", "/monitor?view=activity", "/operations"):
        page = client.get(route)
        assert page.status_code == 200, page.text[:300]
        assert 'class="glass-header"' in page.text
    after = {path.relative_to(inbox): path.read_bytes() for path in inbox.rglob("*") if path.is_file()}
    # The existing publication query service maintains a derived metadata index.
    # No watch, alert, review decision or underlying source may change.
    assert set(after) - set(before) <= {Path("indexes/pending-review-v2.json")}
    assert {key: after[key] for key in before} == before


def test_new_monitor_filters_fail_instead_of_broadening_scope(workspace):
    _, client = workspace
    assert client.get("/monitor?list=missing-list").status_code == 422
    assert client.get("/monitor?company=missing-company").status_code == 422
    assert client.get("/monitor?view=unknown").status_code == 422
    assert client.get("/monitor?sort=unknown").status_code == 422
    assert client.get("/monitor?new=typo").status_code == 422
    assert client.get("/monitor?berry=berry-blueberry,missing-berry").status_code == 422


def test_monitor_multi_berry_scope_survives_tabs(workspace):
    inbox, client = workspace
    for berry in ("berry-blueberry", "berry-raspberry", "berry-strawberry"):
        watchlist.add_watch(inbox, "berry", berry)
    page = client.get("/monitor?type=berry&berry=berry-blueberry&berry=berry-raspberry")
    assert page.status_code == 200
    assert 'class="workspace-subject" href="/watches/open?watch_type=berry&amp;object_id=berry-blueberry"' in page.text
    assert 'class="workspace-subject" href="/watches/open?watch_type=berry&amp;object_id=berry-raspberry"' in page.text
    assert 'class="workspace-subject" href="/watches/open?watch_type=berry&amp;object_id=berry-strawberry"' not in page.text
    assert "berry-blueberry%2Cberry-raspberry" in page.text


def test_malformed_alert_history_is_retained(tmp_path):
    path = tmp_path / STATE_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"state": {"alert-1": {"state": "read", "history": "damaged"}}}), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="left unchanged"):
        apply_alert_action(tmp_path, "alert-1", "dismiss")
    assert path.read_bytes() == before


def test_damaged_watches_show_recovery_without_overwrite_on_new_and_old_routes(workspace):
    inbox, client = workspace
    path = watchlist.state_path(inbox)
    path.write_text('{"watches": "damaged"}', encoding="utf-8")
    before = path.read_bytes()
    assert "left unchanged" in client.get("/monitor").text
    assert client.get("/watches").status_code == 422
    profile = client.get("/entities/company/company-planasa")
    assert profile.status_code == 200 and "left unchanged" in profile.text
    assert path.read_bytes() == before


def test_company_watch_and_marks_are_separate_and_return_to_the_profile_tab(workspace):
    from app.services import company_directory, feed_first
    inbox, client = workspace
    company_directory.mark(inbox, entity_id="company-planasa", action="favorite", value="1", allowed={"company-planasa"})
    before = feed_first.state_path(inbox).read_bytes()
    assert "Watch this company" in client.get("/entities/company/company-planasa?tab=news").text
    target = "/entities/company/company-planasa?tab=news"
    added = client.post("/watches/toggle", data={"watch_type":"company", "object_id":"company-planasa", "action":"add", "return_to":target}, follow_redirects=False)
    assert added.status_code == 303 and added.headers["location"] == target
    assert "Remove subject watch" in client.get(target).text
    assert "Plantas de Navarra" in client.get("/monitor?favorites=1&company=company-planasa").text
    assert feed_first.state_path(inbox).read_bytes() == before


def test_variety_combined_marks_must_match_the_same_company(workspace, monkeypatch):
    from app.services import company_directory, personal_digest
    inbox, client = workspace
    entities = {key: {"id":key,"name":key,"entity_type":"company"} for key in ("company-a", "company-b")}
    entities["variety-shared"] = {"id":"variety-shared", "name":"Shared variety", "entity_type":"variety"}
    monkeypatch.setattr(main, "entity_index", lambda: entities)
    monkeypatch.setattr(main, "all_relationships", lambda: [{"subject_id":key,"object_id":"variety-shared","predicate":"grows","status":"active"} for key in ("company-a", "company-b")])
    monkeypatch.setattr(company_directory.seed_roster, "build_roster", lambda _: [])
    company_directory.mark(inbox, entity_id="company-a", action="favorite", value="1", allowed=set(entities))
    company_directory.mark(inbox, entity_id="company-b", action="tier", value="tier1", allowed=set(entities))
    group = personal_digest.edit_list(inbox, action="create", name="Company B", company_ids=["company-b"], allowed_companies=set(entities))
    watchlist.add_watch(inbox, "variety", "variety-shared")
    for query in ("favorites=1", "tier=tier1", "list="+group):
        assert "Shared variety" in client.get("/monitor?"+query).text
    assert "Shared variety" not in client.get("/monitor?favorites=1&tier=tier1&list="+group).text
    company_directory.mark(inbox, entity_id="company-b", action="favorite", value="1", allowed=set(entities))
    assert "Shared variety" in client.get("/monitor?favorites=1&tier=tier1&list="+group).text


def test_monitoring_action_preserves_scoped_return_and_rejects_cross_origin(workspace, monkeypatch):
    inbox, client = workspace
    subject = {"id":"ev-plan", "title":"Plan source", "source_id":"source-plan"}
    monkeypatch.setattr(main, "queue_items", lambda _: [subject])
    captured = []
    monkeypatch.setattr(main, "apply_queue_action", lambda *a, **kw: captured.append(kw))
    data = {"action":"pause", "return_to":"/monitor?view=activity&favorites=1"}
    result = client.post("/queues/monitoring/ev-plan", data=data, follow_redirects=False)
    assert result.status_code == 303 and result.headers["location"] == data["return_to"]
    assert captured[0]["action"] == "pause" and captured[0]["subject"] == subject
    assert client.post("/queues/monitoring/ev-plan", data=data, headers={"origin":"https://other.example"}).status_code == 403
    assert len(captured) == 1


def test_private_monitor_and_operations_do_not_leak_in_readonly_mode(workspace, monkeypatch):
    _, client = workspace
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    for route in ("/monitor", "/operations", "/watches", "/watchtower", "/queues/monitoring", "/review-ops", "/collection-ops", "/coverage-assurance"):
        assert client.get(route).status_code == 403, route


def test_cross_origin_cannot_change_watch_or_notification(workspace):
    inbox, client = workspace
    headers = {"origin": "https://elsewhere.example"}
    assert client.post("/watches/toggle", headers=headers, data={"watch_type":"company", "object_id":"company-planasa", "action":"add"}).status_code == 403
    assert client.post("/watchtower/alert-1/action", headers=headers, data={"action":"mark_read"}).status_code == 403
    assert not list(inbox.rglob("*.json"))


def test_operations_uses_actual_review_workloads_and_keeps_distinct_routes(workspace):
    _, client = workspace
    page = client.get("/operations")
    assert page.status_code == 200
    for route in ('href="/pending"', 'href="/review?kind=atomic"', 'href="/source-fidelity"', 'href="/varieties/candidates"', 'href="/collection-ops"'):
        assert route in page.text
    assert "Passing one step never silently passes another" in page.text
    assert client.get("/review-ops").status_code == 200
    assert client.get("/collection-ops").status_code == 200
