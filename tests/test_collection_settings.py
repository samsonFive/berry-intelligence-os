import re

import pytest
from fastapi.testclient import TestClient

from app.services import collection_settings as settings
from app.repositories.json.sources import JsonSourceRepository


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    monkeypatch.setenv("BIOS_INBOX_DIR", str(inbox))
    return inbox


def save(inbox, key="", **kwargs):
    return settings.change(inbox, key=key, kind="query", group="pulse", action="save",
        revision=settings.fingerprint(settings.load(inbox)["entries"].get(key, {})),
        label="Fixture monitor", text="blueberry floricane fixture", **kwargs)


def test_query_edit_disable_remove_restore_and_custom_reach_real_generators(runtime):
    from app.services.industry_pulse.matrix import generate_pulse_queries
    from app.services.global_week import week_queries
    original = generate_pulse_queries()[0]
    save(runtime, original.id)
    assert next(q for q in generate_pulse_queries() if q.id == original.id).text == "blueberry floricane fixture"
    assert next(q for q in week_queries() if q.id == original.id).text == "blueberry floricane fixture"
    save(runtime, original.id, enabled=False)
    assert original.id not in {q.id for q in generate_pulse_queries()}
    for action in ("remove", "restore"):
        settings.change(runtime, key=original.id, kind="query", group="pulse", action=action,
            revision=settings.fingerprint(settings.load(runtime)["entries"][original.id]))
        assert (original.id in {q.id for q in generate_pulse_queries()}) == (action == "restore")
    key = save(runtime)
    assert key in {q.id for q in generate_pulse_queries()}
    assert key in {q.id for q in week_queries()}


@pytest.mark.parametrize("group,getter", [
    ("today_google", "app.services.feed_first_live:today_google_queries"),
    ("today_perplexity", "app.services.feed_first_live:today_perplexity_queries"),
    ("today_official", "app.services.feed_first_live:today_official_site_queries"),
    ("exa", "app.services.industry_pulse.exa_queries:week_unknown_unknown_queries"),
    ("radar_google", "app.services.emerging_radar.queries:radar_google_queries"),
    ("radar_semantic", "app.services.emerging_radar.queries:radar_semantic_queries"),
    ("radar_catchnet", "app.services.emerging_radar.queries:radar_catchnet_queries"),
])
def test_each_discovery_lane_reads_edits_and_preserves_date_window(runtime, group, getter):
    import importlib
    module, name = getter.split(":")
    function = getattr(importlib.import_module(module), name)
    original = function()[0]
    settings.change(runtime, key=original.id, kind="query", group=group, action="save", revision=settings.fingerprint({}),
                    label="Changed", text="new berry expression")
    changed = function()[0]
    assert changed.id == original.id and changed.text.startswith("new berry expression")
    assert changed.date_window == original.date_window
    if original.date_window:
        assert "when:" in changed.text


def test_catchall_runner_uses_configured_queries_without_network(runtime):
    from app.services.industry_pulse.catchall_recall import CATCHALL_RECALL_QUERIES, run_catchall_recall
    key = CATCHALL_RECALL_QUERIES[0].id
    settings.change(runtime, key=key, kind="query", group="catchall", action="remove", revision=settings.fingerprint({}))
    result = run_catchall_recall(inbox_dir=runtime, key="", prefetched_records=[])
    assert key not in result["queries"]


def test_specialist_feed_changes_reach_query_and_fetch(runtime):
    from app.services.industry_pulse.specialist_feeds import configured_feeds, week_specialist_feed_queries, feed_by_query_id
    row = configured_feeds()[0]
    settings.change(runtime, key=row["id"], kind="feed", group="specialist", action="save",
        revision=settings.fingerprint({}), label="Fixture feed", text="https://example.org/news.xml")
    assert feed_by_query_id(row["id"])["feed_url"] == "https://example.org/news.xml"
    assert next(q for q in week_specialist_feed_queries() if q.id == row["id"]).text == "https://example.org/news.xml"
    custom = settings.change(runtime, key="", kind="feed", group="specialist", action="save",
        revision="", label="Added publisher", text="https://example.net/feed")
    assert feed_by_query_id(custom)["adapter"] == "article_rss"
    settings.change(runtime, key=row["id"], kind="feed", group="specialist", action="remove",
        revision=settings.fingerprint(settings.load(runtime)["entries"][row["id"]]))
    assert feed_by_query_id(row["id"]) is None


def test_conflicts_corruption_and_bad_urls_do_not_overwrite(runtime):
    key = save(runtime)
    original = settings.settings_path(runtime).read_bytes()
    with pytest.raises(ValueError, match="changed since"):
        settings.change(runtime, key=key, kind="query", group="pulse", action="remove", revision="stale")
    for url in ("http://127.0.0.1/feed", "http://localhost/feed", "file:///private", "https://user:pass@example.org/feed"):
        with pytest.raises(ValueError):
            settings.change(runtime, key="", kind="feed", group="specialist", action="save", revision="", label="Invalid", text=url)
    assert settings.settings_path(runtime).read_bytes() == original
    settings.settings_path(runtime).write_text("broken")
    with pytest.raises(ValueError, match="not be read"):
        save(runtime)
    assert settings.settings_path(runtime).read_text() == "broken"


def test_source_changes_preserve_adapter_options_and_collected_history(runtime, tmp_path):
    repository = JsonSourceRepository(tmp_path / "data")
    row = {"id": "source-fixture", "type": "rss", "label": "Existing", "value": "https://example.org/feed",
           "enabled": True, "discovery": {"adapter": "article_rss", "feed_url": "https://example.org/feed", "item_limit": 12},
           "last_checked_at": "2026-10-26", "last_status": "ok", "berry_ids": ["berry-blueberry"]}
    repository.create(row)
    kwargs = dict(key=row["id"], label="Renamed", text="https://example.net/feed", enabled=True,
                  source_type="rss", priority="high", cadence="weekly")
    settings.change_source(repository, action="save", revision=settings.fingerprint(row), **kwargs)
    changed = repository.get(row["id"])
    assert changed["discovery"]["item_limit"] == 12
    assert changed["discovery"]["feed_url"] == "https://example.net/feed"
    assert changed["last_checked_at"] == row["last_checked_at"] and changed["berry_ids"] == row["berry_ids"]
    with pytest.raises(ValueError, match="changed since"):
        settings.change_source(repository, action="save", revision=settings.fingerprint(row), **kwargs)
    settings.change_source(repository, action="remove", revision=settings.fingerprint(changed), **kwargs)
    assert repository.get(row["id"])["enabled"] is False
    assert repository.get(row["id"])["last_status"] == "ok"
    settings.change_source(repository, action="restore", revision=settings.fingerprint(repository.get(row["id"])), **kwargs)
    assert repository.get(row["id"])["enabled"] is True


def test_added_keyword_has_real_discovery_config(runtime, tmp_path):
    repository = JsonSourceRepository(tmp_path / "data")
    key = settings.change_source(repository, key="", action="save", revision="", label="Fixture keyword",
        text='blackberry "new variety"', enabled=True, source_type="keyword", priority="", cadence="")
    row = repository.get(key)
    assert row["discovery"]["adapter"] == "news_search_rss"
    assert row["type"] == "reference"  # The legacy headline-only poller must skip it.
    from app.services.source_lifecycle import is_collection_eligible
    assert is_collection_eligible(row)
    from urllib.parse import parse_qs, urlsplit
    assert parse_qs(urlsplit(row["discovery"]["feed_url"]).query)["q"] == ['blackberry "new variety"']


def test_subject_names_and_dimensions_keep_technical_ids_out_of_alphabet(runtime, tmp_path):
    model = settings.view_model([], runtime, tmp_path / "data")
    rows = {row["id"]: row for row in model["queries"]}
    apac = rows["apac:en"]
    assert apac["label"] == "Harvest, markets and varieties"
    assert apac["region_labels"] == ["Asia-Pacific"]
    assert apac["workflow_labels"] == ["Weekly edition"]
    assert "Blueberry" in apac["berry_labels"]
    exa = rows["exa:uu:vaccinium-traits"]
    assert exa["label"] == "Cultivar traits"
    assert exa["berry_labels"] == ["Blueberry"] and exa["provider_labels"] == ["Exa"]
    language = rows["lang:africa:fr"]
    assert language["language_label"] == "French"
    assert language["region_labels"] == ["Africa"]
    assert language["label"] == "Regional industry developments"
    assert set(language["berry_labels"]) == {"Blackberry", "Blueberry", "Raspberry", "Strawberry"}
    shared = rows["pulse:blackberry:apac"]
    assert shared["label"] == "Industry developments"
    assert shared["berry_labels"] == ["Blackberry"]
    assert shared["workflow_labels"] == ["Industry discovery", "Weekly edition"]


def test_legacy_generated_names_upgrade_without_renaming_custom_monitors_or_queries(runtime, tmp_path):
    from app.services.industry_pulse.matrix import generate_pulse_queries
    original = generate_pulse_queries()[0]
    state = settings.load(runtime)
    state["entries"][original.id] = {"kind": "query", "group": "pulse", "enabled": True,
        "label": original.id.replace(":", " · ").replace("_", " ").title(), "text": original.text}
    settings._write(state, runtime)
    model = settings.view_model([], runtime, tmp_path / "data")
    assert next(row for row in model["queries"] if row["id"] == original.id)["label"] == "Industry developments"
    assert generate_pulse_queries()[0] == original
    state["entries"][original.id]["label"] = "My preferred berry monitor"
    settings._write(state, runtime)
    model = settings.view_model([], runtime, tmp_path / "data")
    assert next(row for row in model["queries"] if row["id"] == original.id)["label"] == "My preferred berry monitor"


def test_authenticated_ui_writes_are_guarded_and_do_not_run_collectors(runtime, tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", runtime)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "_feed_first_world", lambda: {"official_hosts": set()})
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    client = TestClient(main.app)
    page = client.get("/settings/collection")
    assert page.status_code == 200 and "Keyword Monitoring" in page.text
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
    payload = {"kind": "query", "label": "UI fixture", "text": "blueberry UI fixture", "group": "pulse", "enabled": "true"}
    assert client.post("/settings/collection", data=payload).status_code == 403
    payload["csrf_token"] = token
    result = client.post("/settings/collection", data=payload, follow_redirects=False)
    assert result.status_code == 303
    assert any(row["label"] == "UI fixture" for row in settings.load(runtime)["entries"].values())
    from app.services.pipeline_lock import pipeline_lock
    with pipeline_lock(runtime, "fixture-collector"):
        assert client.post("/settings/collection", data=payload).status_code == 409
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.post("/settings/collection", data=payload).status_code == 403
    readonly = client.get("/settings/collection").text
    assert 'id="collection-add"' not in readonly
    assert 'Read-only in this deployment.' in readonly
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "true")
    monkeypatch.setenv("BIOS_REVIEW_USERNAME", "fixture")
    monkeypatch.setenv("BIOS_REVIEW_PASSWORD", "fixture-pass")
    monkeypatch.setenv("BIOS_SESSION_SECRET", "fixture-collection-signing-secret-with-enough-characters")
    assert client.get("/settings/collection", follow_redirects=False).status_code == 302


def test_scoped_builder_persists_and_dispatches_crop_region_and_unexpanded_input(runtime, tmp_path):
    from app.services.industry_pulse.matrix import generate_pulse_queries, GEO_EDITIONS
    payload = dict(query_builder=True, query_input="Floricane, cultivar release", scope_berry="blackberry",
                   scope_region="europe", term_match="any")
    key = save(runtime, **payload)
    entry = settings.load(runtime)["entries"][key]
    query = next(q for q in generate_pulse_queries() if q.id == key)
    assert query.text == entry["text"]
    assert '(Floricane OR "cultivar release") AND (blackberry' in query.text
    assert GEO_EDITIONS["europe"]["terms"] in query.text
    assert (query.berry, query.geography, query.gl) == ("blackberry", "europe", "GB")
    save(runtime, key, **payload)
    assert settings.load(runtime)["entries"][key]["text"] == entry["text"]
    assert settings.load(runtime)["entries"][key]["query_input"] == payload["query_input"]
    row = next(r for r in settings.view_model([], runtime, tmp_path / "data")["queries"] if r["id"] == key)
    assert row["berry_labels"] == ["Blackberry"] and row["region_labels"] == ["Europe"]
    before = settings.settings_path(runtime).read_bytes()
    with pytest.raises(ValueError):
        save(runtime, key, query_builder=True, query_input="Floricane", scope_region="unsupported")
    assert settings.settings_path(runtime).read_bytes() == before


def test_builder_multiple_terms_modes_and_validation():
    compile = settings.compile_custom_query
    assert compile(query_input="Floricane\nPrimocane, Floricane", term_match="all")["query_terms"] == ["Floricane", "Primocane"]
    assert "(Floricane AND Primocane) AND" in compile(query_input="Floricane\nPrimocane", term_match="all")["text"]
    assert '(Floricane OR "cultivar release") AND' in compile(query_input='Floricane OR "cultivar release"', input_mode="advanced")["text"]
    for terms in ("", "Floricane OR Primocane", "-Floricane", "x" * 1201, ",".join(str(n) for n in range(21))):
        with pytest.raises(ValueError):
            compile(query_input=terms)


def test_local_preview_matches_saved_dispatched_query_without_writing(runtime, tmp_path, monkeypatch):
    import app.main as main
    from app.services.feed_first_live import today_google_queries
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "INBOX_DIR", runtime)
    monkeypatch.setattr(main, "AUTHORING_MODE", True)
    monkeypatch.setattr(main, "_feed_first_world", lambda: {"official_hosts": set()})
    monkeypatch.setenv("BIOS_REMOTE_INTERACTIVE", "false")
    client = TestClient(main.app)
    page = client.get("/settings/collection")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
    payload = dict(kind="query", label="Floricane developments", query_builder="true", query_input="Floricane",
                   scope_berry="blackberry", scope_region="global", group="today_google", enabled="true")
    endpoint = "/settings/collection/query-preview"
    assert client.post(endpoint, data=payload).status_code == 403
    payload["csrf_token"] = token
    preview = client.post(endpoint, data=payload)
    assert preview.status_code == 200
    assert not settings.settings_path(runtime).exists()
    assert client.post(endpoint, data={**payload, "scope_berry": "invalid"}).status_code == 400
    assert client.post(endpoint, data={**payload, "group": "today_official"}).status_code == 400
    assert client.post("/settings/collection", data=payload, follow_redirects=False).status_code == 303
    key, saved = next(iter(settings.load(runtime)["entries"].items()))
    assert preview.json()["expression"] == saved["text"]
    query = next(q for q in today_google_queries() if q.id.startswith(key))
    assert query.text == saved["text"] + " when:30d" and query.berry == "blackberry"
    settings.settings_path(runtime).write_text("broken")
    unavailable = client.get("/settings/collection")
    assert unavailable.status_code == 503 and "could not be read" in unavailable.text
    monkeypatch.setattr(main, "AUTHORING_MODE", False)
    assert client.post(endpoint, data=payload).status_code == 403
