"""Calendar determinism: injectable UTC clock and recency-window boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from app.services.clock import as_utc, resolve_now, utc_now, utc_today
from app.services.today import recency_band
from tests.clock_helpers import freeze_utc_now


FROZEN = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
PST = timezone(timedelta(hours=-7))


def test_utc_now_is_timezone_aware_utc() -> None:
    instant = utc_now()
    assert instant.tzinfo is not None
    assert instant.utcoffset() == timedelta(0)


def test_now_none_uses_injectable_utc_now(monkeypatch) -> None:
    freeze_utc_now(monkeypatch, FROZEN)
    assert resolve_now(None) == FROZEN
    assert utc_today(None) == date(2026, 9, 1)


def test_naive_datetime_is_treated_as_utc() -> None:
    naive = datetime(2026, 9, 1, 12, 0)
    assert as_utc(naive) == FROZEN
    assert resolve_now(naive) == FROZEN


def test_aware_datetime_converts_to_utc() -> None:
    pacific = datetime(2026, 9, 1, 5, 0, tzinfo=PST)
    assert resolve_now(pacific) == FROZEN


def test_repeated_resolve_now_is_identical_when_frozen(monkeypatch) -> None:
    freeze_utc_now(monkeypatch, FROZEN)
    first = resolve_now(None)
    second = resolve_now(None)
    assert first == second == FROZEN
    assert utc_today() == utc_today(None) == date(2026, 9, 1)


def test_fourteen_day_window_inside_cutoff_and_outside() -> None:
    when = datetime(2026, 8, 31, tzinfo=UTC)
    inside = recency_band(when, now=datetime(2026, 9, 13, 12, 0, tzinfo=UTC))
    cutoff = recency_band(when, now=datetime(2026, 9, 14, 12, 0, tzinfo=UTC))
    outside = recency_band(when, now=datetime(2026, 9, 15, 0, 0, tzinfo=UTC))
    assert inside == "last_14_days"
    assert cutoff == "last_14_days"
    assert outside is None
    assert (date(2026, 9, 14) - date(2026, 8, 31)).days == 14
    assert (date(2026, 9, 15) - date(2026, 8, 31)).days == 15


def test_utc_date_rollover_changes_the_14_day_band() -> None:
    when = datetime(2026, 8, 31, tzinfo=UTC)
    still_fourteenth = resolve_now(datetime(2026, 9, 14, 16, 0, tzinfo=PST))
    rolled = resolve_now(datetime(2026, 9, 14, 17, 0, tzinfo=PST))
    assert still_fourteenth == datetime(2026, 9, 14, 23, 0, tzinfo=UTC)
    assert rolled == datetime(2026, 9, 15, 0, 0, tzinfo=UTC)
    assert recency_band(when, now=still_fourteenth) == "last_14_days"
    assert recency_band(when, now=rolled) is None


def test_forty_five_day_triage_cutoff_is_inclusive() -> None:
    start = date(2026, 7, 30)
    assert (date(2026, 9, 13) - start).days == 45
    assert (date(2026, 9, 14) - start).days == 46


def test_build_front_page_now_none_matches_explicit_frozen_instant(monkeypatch, tmp_path) -> None:
    from app.services.front_page import build_front_page

    freeze_utc_now(monkeypatch, FROZEN)
    draft = {
        "id": "ev-clock-draft",
        "record_type": "evidence",
        "status": "draft",
        "evidence_role": "publication_artifact",
        "title": "Clock seam draft",
        "captured_date": "2026-09-01",
        "source_name": "Italian Berry",
        "source_type": "news_search",
        "source_url": "https://example.invalid/clock",
        "berry_ids": ["berry-blueberry"],
        "publisher_description": "Thin description.",
    }
    kwargs = dict(
        published=[],
        drafts=[draft],
        signals=[],
        assessments=[],
        sources=[],
        entities=[],
        relationships=[],
        inbox_dir=tmp_path / "inbox",
        data_dir=tmp_path / "data",
    )
    implicit = build_front_page(**kwargs, now=None)
    explicit = build_front_page(**kwargs, now=FROZEN)
    naive = build_front_page(**kwargs, now=datetime(2026, 9, 1, 12, 0))
    assert implicit["top_stories"][0]["id"] == explicit["top_stories"][0]["id"] == "ev-clock-draft"
    assert implicit["top_stories"][0]["trust_label"] == "FRESH / UNREVIEWED"
    assert [row["id"] for row in implicit["top_stories"]] == [row["id"] for row in naive["top_stories"]]
    second = build_front_page(**kwargs, now=None)
    assert [row["id"] for row in implicit["top_stories"]] == [row["id"] for row in second["top_stories"]]
