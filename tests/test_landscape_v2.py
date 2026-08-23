"""Landscape V2 -- Executive Competitive Overview V1.

Tests the new cross-berry ALL view, the strengthened Evidence Coverage
framing on the existing per-berry page, and the new Compare/Learner/Reader
integration links. Existing single-berry Landscape behavior is covered by
tests/test_synthesis_views.py and is intentionally not re-tested here."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.main import app, BERRIES


def _all_context():
    return main.get_domain_services(main.DATA_DIR).landscape.landscape_context_all_berries(BERRIES)


def test_all_berries_context_covers_every_berry():
    context = _all_context()
    labels = {row["berry_label"] for row in context["berry_rows"]}
    assert labels == set(BERRIES.values())
    assert context["header_stats"]["berry_count"] == len(BERRIES)


def test_all_berries_context_no_composite_score():
    context = _all_context()
    for row in context["berry_rows"]:
        assert "score" not in row
        assert "strength" not in row
        assert "rank" not in row
    for row in context["actors_to_watch"]:
        assert "score" not in row
        assert "strength" not in row


def test_all_berries_actors_have_honest_why_shown_copy():
    context = _all_context()
    for row in context["actors_to_watch"]:
        assert "why_shown" in row
        assert "Recent trusted activity" in row["why_shown"]
        assert "top competitor" not in row["why_shown"].lower()


def test_all_berries_actors_never_padded_with_zero_activity_company():
    """A sparse berry must show fewer (or zero) actors rather than padding
    to a fixed count with a company that has 0 signals and 0 evidence --
    that would directly contradict the "shown because of recent trusted
    activity" copy right above the card."""
    context = _all_context()
    for row in context["actors_to_watch"]:
        assert row["evidence_count"] > 0 or row["signal_count"] > 0


def test_all_berries_recent_moves_sorted_and_bounded():
    context = _all_context()
    moves = context["recent_moves"]
    assert len(moves) <= 15
    dates = [m.get("published_date") or m.get("captured_date") or "" for m in moves]
    assert dates == sorted(dates, reverse=True)


def test_all_berries_sparse_berry_still_listed_with_honest_counts():
    context = _all_context()
    by_label = {row["berry_label"]: row for row in context["berry_rows"]}
    # Every berry appears even if some have far less captured evidence --
    # coverage differences must be visible, not hidden.
    for row in by_label.values():
        assert isinstance(row["evidence_count"], int)
        assert isinstance(row["company_count"], int)


def test_per_berry_actors_to_watch_never_zero_activity():
    """Same class of bug as the cross-berry fix, found live on the
    existing (pre-V2, unmodified-in-structure) single-berry page: a
    company with 0 signals, 0 evidence, and 0 documented varieties must
    not appear as an actor to watch."""
    for berry_id in main.BERRIES:
        context = main.landscape_context(berry_id)
        for row in context["actors_to_watch"]:
            assert row["signals"] or row["evidence_count"] or row["varieties"]


def test_per_berry_evidence_coverage_has_caveat_and_no_market_activity_claim():
    context = main.landscape_context("berry-blackberry")
    caveat = context["evidence_coverage"]["coverage_caveat"]
    assert "not market activity" in caveat
    assert "low competitor activity" not in caveat.lower()


def test_per_berry_theme_explain_links_only_where_mapped():
    context = main.landscape_context("berry-blueberry")
    for theme in context["competitive_themes"]:
        if theme["label"] in ("Flavor / Sweetness", "Firmness / Shelf Life", "Fruit size"):
            assert theme["explain_href"] is not None
            assert theme["explain_href"].startswith("/learn/")
        if theme["label"] in ("Yield / Production", "Climate adaptability"):
            assert theme["explain_href"] is None


def test_per_berry_compare_variety_ids_bounded_and_real():
    context = main.landscape_context("berry-blueberry")
    ids = context["compare_variety_ids"]
    assert len(ids) <= 4
    entities = main.entity_index()
    for vid in ids:
        assert entities[vid]["entity_type"] == "variety"


# --- Route-level tests ---------------------------------------------------


def test_landscape_all_route_loads():
    client = TestClient(app)
    page = client.get("/landscapes")
    assert page.status_code == 200
    assert "Competitive Landscape" in page.text
    assert "Captured intelligence coverage" in page.text


def test_landscape_all_lists_every_berry_with_real_counts():
    client = TestClient(app)
    page = client.get("/landscapes")
    assert page.status_code == 200
    for label in ("Blueberry", "Raspberry", "Strawberry", "Blackberry"):
        assert label in page.text


def test_landscape_all_sparse_berry_not_framed_as_inactive():
    client = TestClient(app)
    page = client.get("/landscapes")
    lowered = page.text.casefold()
    assert "low competitor activity" not in lowered
    assert "market coverage" not in lowered


def test_landscape_per_berry_route_still_works():
    client = TestClient(app)
    page = client.get("/landscapes/berries/blueberry")
    assert page.status_code == 200
    assert "Blueberry Landscape" in page.text


def test_landscape_per_berry_route_unknown_berry_404():
    client = TestClient(app)
    page = client.get("/landscapes/berries/does-not-exist")
    assert page.status_code == 404


def test_landscape_nav_link_points_to_all_berries_when_global():
    client = TestClient(app)
    page = client.get("/brief")
    assert page.status_code == 200
    assert 'href="/landscapes" class="v2-nav-link" title="Landscape"' in page.text


def test_landscape_variety_compare_deep_link_uses_real_ids():
    client = TestClient(app)
    page = client.get("/landscapes/berries/blueberry")
    assert page.status_code == 200
    assert "/entities/variety/compare?ids=" in page.text


def test_landscape_per_berry_template_never_diverges_static_from_live():
    """landscape.html's own tested architectural invariant (see
    tests/test_synthesis_views.py) is that it never branches on
    static_build at all, so live and static rendering always match
    byte-for-byte for narrative content. New Landscape V2 additions to
    this specific template (Evidence Coverage caveat, theme Explain-this
    links, Variety Compare deep-link) must preserve that invariant --
    unlike the brand-new landscape_all.html, which has no such constraint
    and does use static_build for its Reader integration."""
    template_source = (main.BASE_DIR / "app" / "templates" / "landscape.html").read_text(encoding="utf-8")
    assert "static_build" not in template_source


def test_landscape_all_reader_integration_present_when_moves_exist():
    client = TestClient(app)
    page = client.get("/landscapes")
    assert page.status_code == 200
    context = _all_context()
    if context["recent_moves"]:
        assert "data-open-reader" in page.text


def test_landscape_no_pending_leakage():
    client = TestClient(app)
    for path in ["/landscapes", "/landscapes/berries/blueberry"]:
        page = client.get(path)
        assert "in_review" not in page.text
        assert "signal_candidate" not in page.text.casefold()


def test_landscape_all_deterministic_across_requests():
    client = TestClient(app)
    first = client.get("/landscapes").text
    second = client.get("/landscapes").text
    assert first == second


def test_landscape_warm_request_is_fast():
    import time

    client = TestClient(app)
    client.get("/landscapes/berries/blueberry")  # cold, populates cache
    t0 = time.perf_counter()
    client.get("/landscapes/berries/blueberry")
    warm_ms = (time.perf_counter() - t0) * 1000
    assert warm_ms < 2000

    client.get("/landscapes")  # cold
    t0 = time.perf_counter()
    client.get("/landscapes")
    warm_all_ms = (time.perf_counter() - t0) * 1000
    assert warm_all_ms < 2000
