"""Tests for app/services/source_freshness.py's cadence-aware classification.

Real distinction under test: "no new stories since we last checked" (CURRENT
or DUE, depending on cadence) must never be confused with "we haven't
actually managed to check this source lately" (STALE or FAILING) -- both can
look identical from a bare headline count, but call for very different
operator action.
"""

from __future__ import annotations

from datetime import date

from app.services.source_freshness import (
    CURRENT,
    DUE,
    FAILING,
    MANUAL,
    STALE,
    classify_source_freshness,
    is_discoverable,
    latest_item_dates,
)


def _source(**overrides):
    base = {"id": "source-x", "update_cadence": "weekly", "discovery": {"adapter": "article_rss", "feed_url": "https://example.com/feed"}}
    base.update(overrides)
    return base


def test_manual_source_has_no_discovery_adapter():
    source = {"id": "source-manual", "update_cadence": "quarterly"}
    result = classify_source_freshness(source, discovery_state=None)
    assert result.state == MANUAL
    assert not is_discoverable(source)


def test_never_run_discoverable_source_is_stale():
    source = _source()
    result = classify_source_freshness(source, discovery_state=None)
    assert result.state == STALE
    assert "no discovery run" in result.reason.casefold()


def test_most_recent_attempt_failed_is_failing_even_with_a_past_success():
    source = _source()
    state = {
        "status": "error",
        "error": "feed unreachable: 503",
        "last_checked_at": "2026-08-18T00:00:00+00:00",
        "last_success_at": "2026-08-10T00:00:00+00:00",
    }
    result = classify_source_freshness(source, discovery_state=state, today=date(2026, 8, 18))
    assert result.state == FAILING
    assert result.last_success_at == "2026-08-10T00:00:00+00:00"


def test_checked_but_never_succeeded_is_stale_not_current():
    source = _source()
    state = {"status": "ok", "last_checked_at": "2026-08-18T00:00:00+00:00", "last_success_at": None}
    result = classify_source_freshness(source, discovery_state=state, today=date(2026, 8, 18))
    assert result.state == STALE


def test_weekly_source_checked_yesterday_is_current_not_stale():
    """The task's own example: a weekly publication is not stale after one
    quiet day."""
    source = _source(update_cadence="weekly")
    state = {"status": "ok", "last_checked_at": "2026-08-17T00:00:00+00:00", "last_success_at": "2026-08-17T00:00:00+00:00"}
    result = classify_source_freshness(source, discovery_state=state, today=date(2026, 8, 18))
    assert result.state == CURRENT


def test_weekly_source_past_cadence_window_is_due_not_stale():
    # Last success 2026-08-10 -> due 2026-08-17 -> "today" 2026-08-18 is
    # 1 day overdue, well inside one extra weekly cycle -- DUE, not STALE.
    source = _source(update_cadence="weekly")
    state = {"status": "ok", "last_checked_at": "2026-08-10T00:00:00+00:00", "last_success_at": "2026-08-10T00:00:00+00:00"}
    result = classify_source_freshness(source, discovery_state=state, today=date(2026, 8, 18))
    assert result.state == DUE


def test_weekly_source_overdue_by_more_than_a_full_cycle_is_stale():
    source = _source(update_cadence="weekly")
    state = {"status": "ok", "last_checked_at": "2026-07-01T00:00:00+00:00", "last_success_at": "2026-07-01T00:00:00+00:00"}
    result = classify_source_freshness(source, discovery_state=state, today=date(2026, 8, 18))
    assert result.state == STALE


def test_quarterly_source_is_not_stale_after_one_quiet_month():
    """A quarterly data release must not read as stale after a single quiet
    month, unlike a weekly source under the same absolute gap."""
    source = _source(update_cadence="quarterly")
    state = {"status": "ok", "last_checked_at": "2026-07-01T00:00:00+00:00", "last_success_at": "2026-07-01T00:00:00+00:00"}
    result = classify_source_freshness(source, discovery_state=state, today=date(2026, 8, 18))
    assert result.state == CURRENT


def test_event_driven_source_with_success_is_current_with_no_due_date():
    source = _source(update_cadence="event_driven")
    state = {"status": "ok", "last_checked_at": "2020-01-01T00:00:00+00:00", "last_success_at": "2020-01-01T00:00:00+00:00"}
    result = classify_source_freshness(source, discovery_state=state, today=date(2026, 8, 18))
    assert result.state == CURRENT
    assert result.next_check_due is None


def test_latest_item_dates_prefers_published_date_over_captured():
    discovered_items = [
        {"source_id": "source-x", "published_date": "2026-08-17", "first_seen_at": "2026-08-18T00:00:00Z"},
        {"source_id": "source-x", "published_date": "2026-08-10", "first_seen_at": "2026-08-11T00:00:00Z"},
        {"source_id": "source-other", "published_date": "2026-08-18", "first_seen_at": "2026-08-18T00:00:00Z"},
    ]
    published, captured = latest_item_dates(discovered_items=discovered_items, published_evidence=[], source_id="source-x")
    assert published == "2026-08-17"
    assert captured == "2026-08-18T00:00:00Z"


def test_latest_item_dates_includes_trusted_published_evidence():
    published_evidence = [
        {"source_id": "source-x", "published_date": "2026-08-06", "captured_date": "2026-08-06"},
    ]
    published, captured = latest_item_dates(discovered_items=[], published_evidence=published_evidence, source_id="source-x")
    assert published == "2026-08-06"
    assert captured == "2026-08-06"


def test_as_dict_is_json_serializable_shape():
    result = classify_source_freshness({"id": "source-manual"}, discovery_state=None)
    payload = result.as_dict()
    assert payload["state"] == MANUAL
    assert "reason" in payload
