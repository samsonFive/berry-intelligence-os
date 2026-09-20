"""Feed-first golden-path regressions across the Berry OS shell."""

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
    assert 'href="/settings"' in page.text
    assert "data-clear-filter" in page.text


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
    legacy = client.get("/entities/company/company-fall-creek-farm-and-nursery?view=legacy")
    assert "data-feed-first-company" not in legacy.text


def test_people_and_week_keep_honest_coverage_copy():
    client = TestClient(app)
    people = client.get("/people")
    assert "provider-unavailable" in people.text
    assert "discovery-only" in people.text
    week = client.get("/week?view=feed")
    assert "data-feed-first-week" in week.text
    assert "stored August evidence" in week.text
    statements = client.get("/statements")
    assert "data-feed-first-statements" in statements.text
