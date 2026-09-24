"""Feed-first golden-path regressions across the Berry OS shell."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROUTES = (
    ("/today", "data-feed-first-today"),
    ("/following", "data-feed-first-following"),
    ("/people", "data-feed-first-people"),
    ("/saved", "data-feed-first-saved"),
    ("/statements", "data-feed-first-statements"),
    ("/week?view=feed", "data-feed-first-week"),
    ("/landscapes?view=feed", "data-feed-first-landscapes"),
    ("/research-ops", "data-feed-first-ops"),
    ("/settings", "data-feed-first-settings"),
    ("/entities/company/company-fall-creek-farm-and-nursery", "data-feed-first-company"),
)


def test_golden_path_routes_render_berry_os_shell():
    client = TestClient(app)
    for path, marker in ROUTES:
        page = client.get(path)
        assert page.status_code == 200, path
        assert marker in page.text, path
        assert "Berry Intelligence OS" in page.text
        assert "data-feed-first" in page.text


def test_today_filter_query_restores_selected_controls():
    page = TestClient(app).get("/today?tier=tier1&crop=blueberry&state=unread&window=30d")
    assert page.status_code == 200
    assert "data-feed-first-today" in page.text
    assert 'value="tier1" selected' in page.text
    assert 'value="blueberry" selected' in page.text
    assert 'value="unread" selected' in page.text
    assert 'value="30d" selected' in page.text
    assert "data-facet-counts" in page.text
    assert "data-filter-chips" in page.text
    assert 'name="sort"' in page.text
    assert 'name="geography"' in page.text
    assert 'href="/settings"' in page.text
    assert "data-clear-filter" in page.text


def test_today_progressive_filters_and_async_reader_contract():
    page = TestClient(app).get(
        "/today?tier=tier1&crop=blueberry&state=saved&window=30d&source=podcast"
    )
    assert page.status_code == 200
    assert "data-progressive-filters" in page.text
    assert "<summary>" in page.text
    assert "More filters" in page.text
    assert "active secondary filters" in page.text
    assert "data-clear-all-filters" in page.text
    assert "Podcast" in page.text

    default_page = TestClient(app).get("/today")
    assert "data-open-feed-reader" in default_page.text
    assert "Open original evidence" in default_page.text

    script = Path("app/static/feed_first.js").read_text(encoding="utf-8")
    assert "openFeedReader" in script
    assert "window.history.pushState" in script
    assert 'window.addEventListener("popstate"' in script
    assert 'headers: { "X-Requested-With": "feed-first-reader" }' in script
    assert "window.location.assign(target)" in script


def test_selected_reader_precedes_feed_in_single_column_layout():
    css = Path("app/static/berry_os.css").read_text(encoding="utf-8")

    single_column = css.split("@media (max-width: 1100px)", 1)[1].split(
        "@media (max-width: 700px)", 1
    )[0]
    assert ".bos-shell.has-reader > .bos-inspector { grid-column: 1; grid-row: 2; }" in single_column
    assert ".bos-shell.has-reader > .bos-canvas { grid-row: 3; }" in single_column


def test_settings_stays_in_berry_os_and_keeps_legacy_guide():
    client = TestClient(app)
    settings = client.get("/settings")
    assert settings.status_code == 200
    assert "data-feed-first-settings" in settings.text
    assert "Research Ops" in settings.text
    assert "Secret values are never shown" in settings.text
    guide = client.get("/guide")
    assert guide.status_code == 200
    assert "data-feed-first-settings" not in guide.text


def test_research_ops_health_has_no_secret_values():
    page = TestClient(app).get("/research-ops")
    assert page.status_code == 200
    assert "data-watch-coverage" in page.text
    assert "data-cluster-stats" in page.text
    assert "data-lane-errors" in page.text
    assert "One story once" in page.text
    assert "Watch coverage" in page.text
    assert "Today noise dropped" in page.text
    lowered = page.text.casefold()
    assert "bearer " not in lowered
    assert "sk-" not in page.text
    assert "api_key=" not in lowered
    assert "catchall_api_key" not in lowered


def test_default_company_stays_berry_os_and_legacy_is_opt_in():
    client = TestClient(app)
    default = client.get("/entities/company/company-fall-creek-farm-and-nursery")
    assert "data-feed-first-company" in default.text
    assert "Create 90-day report" not in default.text
    assert "Learner context" in default.text
    assert 'href="/learn"' in default.text
    legacy = client.get("/entities/company/company-fall-creek-farm-and-nursery?view=legacy")
    assert "data-feed-first-company" not in legacy.text


def test_feed_nav_restores_full_landscape_and_learner_entry_points():
    client = TestClient(app)
    today = client.get("/today")
    assert 'href="/landscapes"' in today.text
    assert 'href="/learn"' in today.text
    assert 'href="/landscapes?view=feed"' not in today.text

    full = client.get("/landscapes")
    assert full.status_code == 200
    assert "Executive readout" in full.text
    assert "Actors to watch" in full.text
    assert 'href="/landscapes?view=feed"' in full.text

    briefs = client.get("/landscapes?view=feed")
    assert "data-feed-first-landscapes" in briefs.text
    assert "Open full competitive landscape" in briefs.text


def test_restored_surfaces_use_berry_os_shell_and_dense_collections():
    client = TestClient(app)
    learn = client.get("/learn")
    assert "data-berry-os-learn" in learn.text
    assert "bos-shell" in learn.text
    assert "balanced-card-grid" in learn.text

    concept = client.get("/learn/firmness")
    assert "data-berry-os-learn" in concept.text
    assert "v2-learn-concept" in concept.text
    assert "When you see this in intelligence" in concept.text

    landscape = client.get("/landscapes")
    assert "data-berry-os-landscape" in landscape.text
    assert "balanced-card-grid" in landscape.text
    blueberry = client.get("/landscapes/berries/blueberry")
    assert "data-berry-os-landscape" in blueberry.text
    assert "landscape-quick-nav" in blueberry.text

    for template in (
        "feed_first_statements.html",
        "feed_first_week.html",
        "feed_first_landscapes.html",
    ):
        source = Path("app/templates", template).read_text(encoding="utf-8")
        assert "bos-dense-grid" in source

    css = client.get("/static/berry_os.css").text
    assert ".bos-dense-grid" in css
    assert ".berry-os .bos-legacy-surface" in css
    assert "repeat(auto-fill, minmax(260px, 1fr))" in css
    assert "grid-template-columns: repeat(12, minmax(0, 1fr))" in css
    assert ".bos-canvas > section" in css
    assert ".bos-canvas > section > ul:not(.bos-dense-grid)" in css
    assert ".berry-os .bos-legacy-surface .entity-links" in css

    ops = client.get("/research-ops")
    assert ops.text.count("<section") >= 8
    settings = client.get("/settings")
    assert settings.text.count("<section") >= 3


def test_people_and_week_keep_honest_coverage_copy():
    client = TestClient(app)
    people = client.get("/people")
    assert "provider-unavailable" in people.text
    assert "discovery-only" in people.text
    week = client.get("/week")
    assert "data-feed-first-week" in week.text
    assert "Ask Berry OS" in week.text
    statements = client.get("/statements")
    assert "data-feed-first-statements" in statements.text
