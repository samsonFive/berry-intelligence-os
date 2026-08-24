"""Freshness Assurance V1 deterministic backend contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from app.services import freshness_assurance as freshness_module
from app.services.freshness_assurance import (
    BLOCKED,
    CURRENT_ACTIVE,
    CURRENT_QUIET,
    DUE,
    FAILING,
    INSUFFICIENT_HISTORY,
    NEVER_RUN,
    OVERDUE,
    RETRYING,
    SYSTEM_CURRENT,
    SYSTEM_DEGRADED,
    build_freshness_assurance,
    build_runtime_freshness,
    clear_freshness_cache,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)
POLICY = {
    "cadence_by_update_cadence": {"realtime": 21600, "daily": 86400, "weekly": 604800},
    "discoverable_fallback_seconds": 604800,
    "retryable_failure_seconds": 86400,
}


def _source(source_id: str = "source-a", **overrides):
    row = {
        "id": source_id,
        "label": source_id,
        "update_cadence": "daily",
        "berry_ids": ["berry-blueberry"],
        "region_coverage": ["north_america"],
        "entity_types": ["trade_press"],
        "linked_competitor_ids": [],
        "discovery": {"adapter": "article_rss", "feed_url": "https://example.com/feed", "item_limit": 20},
    }
    row.update(overrides)
    return row


def _state(*, status="ok", checked="2026-08-24T06:00:00+00:00", success="2026-08-24T06:00:00+00:00", new=1, error=None):
    return {
        "status": status,
        "last_checked_at": checked,
        "last_success_at": success,
        "new": new,
        "found": 20,
        "error": error,
    }


def _run(at: str, source_id="source-a", *, status="ok", new=1, historical=0):
    return {
        "started_at": at,
        "completed_at": at,
        "sources": [{"source_id": source_id, "status": status, "new": new, "historical_backlog": historical}],
    }


def _build(*, sources=None, states=None, runs=None, discovered=None, drafts=None, scheduler=None):
    sources = sources or [_source()]
    return build_freshness_assurance(
        sources=sources,
        discovery_states=states if states is not None else {"source-a": _state()},
        run_records=runs if runs is not None else [_run("2026-08-24T06:00:00+00:00")],
        discovered_items=discovered or [],
        drafts=drafts or [],
        scheduler_runs=scheduler or [],
        policy=POLICY,
        now=NOW,
    )


def _row(payload, source_id="source-a"):
    return next(row for row in payload["sources"] if row["source_id"] == source_id)


def test_current_active_source_and_three_clocks():
    payload = _build(discovered=[{
        "source_id": "source-a", "first_seen_at": "2026-08-24T05:55:00+00:00", "published_date": "2026-08-23",
    }])
    row = _row(payload)
    assert row["state"] == CURRENT_ACTIVE
    assert row["last_collection_attempt"] == "2026-08-24T06:00:00+00:00"
    assert row["last_successful_collection"] == "2026-08-24T06:00:00+00:00"
    assert row["last_new_intelligence"] == "2026-08-24T05:55:00+00:00"


def test_current_quiet_and_duplicate_only_does_not_advance_last_new():
    payload = _build(
        states={"source-a": _state(new=0)},
        runs=[_run("2026-08-23T06:00:00+00:00", new=2), _run("2026-08-24T06:00:00+00:00", new=0)],
        discovered=[{"source_id": "source-a", "first_seen_at": "2026-08-23T05:59:00+00:00"}],
    )
    assert _row(payload)["state"] == CURRENT_QUIET
    assert payload["last_new_intelligence"] == "2026-08-23T05:59:00+00:00"
    assert payload["last_successful_collection"] == "2026-08-24T06:00:00+00:00"


def test_due_then_overdue_uses_exact_cadence_plus_one_cycle_grace():
    due = _build(
        states={"source-a": _state(checked="2026-08-23T06:00:00+00:00", success="2026-08-23T06:00:00+00:00")},
        runs=[_run("2026-08-23T06:00:00+00:00")],
    )
    assert _row(due)["state"] == DUE
    overdue = _build(
        states={"source-a": _state(checked="2026-08-22T05:59:59+00:00", success="2026-08-22T05:59:59+00:00")},
        runs=[_run("2026-08-22T05:59:59+00:00")],
    )
    assert _row(overdue)["state"] == OVERDUE
    assert any(alert["code"] == "SOURCE_OVERDUE" for alert in overdue["alerts"])


def test_weekly_quiet_source_is_not_falsely_stale():
    source = _source(update_cadence="weekly")
    payload = _build(
        sources=[source], states={"source-a": _state(new=0)}, runs=[_run("2026-08-24T06:00:00+00:00", new=0)],
    )
    assert _row(payload)["state"] == CURRENT_QUIET


def test_one_retryable_failure_is_retrying_not_quiet_or_failing():
    payload = _build(
        states={"source-a": _state(status="error", checked="2026-08-24T11:00:00+00:00", success="2026-08-24T06:00:00+00:00", error="timeout")},
        runs=[_run("2026-08-24T06:00:00+00:00"), _run("2026-08-24T11:00:00+00:00", status="error", new=0)],
    )
    assert _row(payload)["state"] == RETRYING


def test_multiple_failures_are_failing_and_alerted():
    payload = _build(
        states={"source-a": _state(status="error", checked="2026-08-24T11:00:00+00:00", success="2026-08-23T06:00:00+00:00", error="503")},
        runs=[
            _run("2026-08-23T06:00:00+00:00"),
            _run("2026-08-24T10:00:00+00:00", status="error", new=0),
            _run("2026-08-24T11:00:00+00:00", status="error", new=0),
        ],
    )
    assert _row(payload)["state"] == FAILING
    assert any(alert["code"] == "MULTIPLE_CONSECUTIVE_FAILURES" for alert in payload["alerts"])


def test_failed_source_can_also_be_overdue_without_masquerading_as_quiet():
    payload = _build(
        states={"source-a": _state(status="error", checked="2026-08-24T11:00:00+00:00", success="2026-08-20T06:00:00+00:00", error="503")},
        runs=[
            _run("2026-08-20T06:00:00+00:00"),
            _run("2026-08-24T10:00:00+00:00", status="error", new=0),
            _run("2026-08-24T11:00:00+00:00", status="error", new=0),
        ],
    )
    assert _row(payload)["state"] == FAILING
    assert _row(payload)["overdue"] is True
    assert payload["counts"]["overdue"] == 1
    assert payload["counts"]["failing"] == 1
    assert any(alert["code"] == "SOURCE_OVERDUE" for alert in payload["alerts"])


def test_blocked_source_reuses_source_health_semantics():
    payload = _build(
        states={"source-a": _state(status="error", success=None, error="403 Forbidden")},
        runs=[_run("2026-08-24T06:00:00+00:00", status="error", new=0)],
    )
    assert _row(payload)["state"] == BLOCKED


def test_never_run_and_legacy_success_without_run_history_are_distinct():
    never = _build(states={"source-a": None}, runs=[])
    assert _row(never)["state"] == NEVER_RUN
    legacy = _build(states={"source-a": _state()}, runs=[])
    assert _row(legacy)["state"] == INSUFFICIENT_HISTORY


def test_historical_reacquisition_cannot_advance_last_new_intelligence():
    payload = _build(discovered=[
        {"source_id": "source-a", "first_seen_at": "2026-08-20T10:00:00+00:00"},
        {"source_id": "source-a", "first_seen_at": "2026-08-24T11:59:00+00:00", "historical_backlog": True},
    ])
    assert payload["last_new_intelligence"] == "2026-08-20T10:00:00+00:00"


def test_review_only_change_cannot_advance_last_new_intelligence():
    payload = _build(
        discovered=[{"source_id": "source-a", "first_seen_at": "2026-08-20T10:00:00+00:00"}],
        drafts=[{
            "id": "draft-new-review-change", "source_id": "source-a", "evidence_role": "publication_artifact",
            "created_at": "2026-08-24T11:59:00+00:00", "reviewed_at": "2026-08-24T12:00:00+00:00",
            "source_completeness": {"class": "FULL_ARTICLE"},
        }],
    )
    assert payload["last_new_intelligence"] == "2026-08-20T10:00:00+00:00"
    assert payload["last_new_rich_draft"] == "2026-08-24T11:59:00+00:00"


def test_feed_window_risk_uses_observed_velocity_and_visible_depth():
    source = _source(discovery={"adapter": "article_rss", "feed_url": "https://example.com", "item_limit": 2})
    payload = _build(
        sources=[source],
        states={"source-a": _state(checked="2026-08-24T06:00:00+00:00", success="2026-08-24T06:00:00+00:00", new=1)},
        runs=[
            _run("2026-08-23T18:00:00+00:00", new=2),
            _run("2026-08-24T00:00:00+00:00", new=1),
            _run("2026-08-24T06:00:00+00:00", new=1),
        ],
    )
    assert _row(payload)["feed_window_risk"] is True
    assert any(alert["code"] == "FEED_WINDOW_RISK" for alert in payload["alerts"])


def test_zero_new_yield_drift_does_not_claim_market_inactivity():
    payload = _build(runs=[
        _run("2026-08-18T06:00:00+00:00", new=4),
        _run("2026-08-19T06:00:00+00:00", new=2),
        _run("2026-08-20T06:00:00+00:00", new=1),
        _run("2026-08-21T06:00:00+00:00", new=0),
        _run("2026-08-22T06:00:00+00:00", new=0),
        _run("2026-08-24T06:00:00+00:00", new=0),
    ], states={"source-a": _state(new=0)})
    alert = next(alert for alert in payload["alerts"] if alert["code"] == "NEW_ITEM_YIELD_DEGRADED")
    assert "acquisition yield changed" in alert["reason"]


def test_one_bootstrap_productive_run_does_not_create_yield_drift_noise():
    payload = _build(runs=[
        _run("2026-08-20T06:00:00+00:00", new=20),
        _run("2026-08-21T06:00:00+00:00", new=0),
        _run("2026-08-22T06:00:00+00:00", new=0),
        _run("2026-08-24T06:00:00+00:00", new=0),
    ], states={"source-a": _state(new=0)})
    assert not any(alert["code"] == "NEW_ITEM_YIELD_DEGRADED" for alert in payload["alerts"])


def test_rich_body_yield_drift_requires_explicit_repeated_thin_outcomes():
    drafts = []
    for index in range(3):
        drafts.append({
            "source_id": "source-a", "evidence_role": "publication_artifact", "created_at": f"2026-08-{10+index:02d}T00:00:00+00:00",
            "source_completeness": {"class": "FULL_ARTICLE"},
        })
    for index in range(3):
        drafts.append({
            "source_id": "source-a", "evidence_role": "publication_artifact", "created_at": f"2026-08-{20+index:02d}T00:00:00+00:00",
            "source_completeness": {"class": "THIN_DESCRIPTION"},
        })
    payload = _build(drafts=drafts)
    assert any(alert["code"] == "RICH_BODY_YIELD_DEGRADED" for alert in payload["alerts"])


def test_berry_geography_actor_and_source_type_summaries_use_explicit_metadata():
    source = _source(
        berry_ids=["berry-raspberry", "berry-blackberry"],
        region_coverage=["europe"],
        linked_competitor_ids=["company-a"],
        entity_types=["genetics_company"],
        label="Company A Newsroom",
    )
    payload = _build(sources=[source])
    assert payload["berry_coverage"]["berry-raspberry"]["scheduled_sources"] == 1
    assert payload["berry_coverage"]["berry-blackberry"]["current"] == 1
    assert payload["geography_coverage"]["europe"]["current"] == 1
    assert payload["actor_coverage"]["company-a"]["direct_monitoring_gap"] is False
    assert payload["source_type_coverage"]["company_newsroom"]["scheduled_sources"] == 1


def test_system_current_and_current_through_come_from_successful_operation():
    payload = _build(
        runs=[_run("2026-08-24T06:00:00+00:00")],
        scheduler=[{"generated_at": "2026-08-24T06:01:00+00:00"}],
    )
    assert payload["system_state"] == SYSTEM_CURRENT
    assert payload["can_claim_current"] is True
    assert payload["current_through"] == "2026-08-24T06:00:00+00:00"
    assert payload["last_scheduler_run"] == "2026-08-24T06:01:00+00:00"
    assert payload["overdue_count"] == 0
    assert payload["failing_count"] == 0
    assert payload["blocked_count"] == 0


def test_system_degraded_and_no_successful_run_conditions_are_honest():
    payload = _build(states={"source-a": None}, runs=[])
    assert payload["system_state"] == SYSTEM_DEGRADED
    assert payload["can_claim_current"] is False
    assert payload["current_through"] is None
    assert any(alert["code"] == "NO_SUCCESSFUL_COLLECTION_RUN" for alert in payload["alerts"])


def test_timestamp_behavior_is_deterministic_and_json_contract_has_no_bodies():
    first = _build(discovered=[{"source_id": "source-a", "first_seen_at": "2026-08-24T05:00:00+00:00", "body": "PRIVATE"}])
    second = _build(discovered=[{"source_id": "source-a", "first_seen_at": "2026-08-24T05:00:00+00:00", "body": "PRIVATE"}])
    assert first == second
    assert "PRIVATE" not in json.dumps(first)


def test_runtime_adapter_reads_bounded_private_metadata_without_mutation(tmp_path):
    data_dir = tmp_path / "data"
    inbox_dir = tmp_path / "inbox"
    (data_dir / "configuration").mkdir(parents=True)
    (inbox_dir / "operations" / "runs").mkdir(parents=True)
    (inbox_dir / "operations" / "cron-logs").mkdir(parents=True)
    (inbox_dir / "discovered_media").mkdir(parents=True)
    (inbox_dir / "discovered_media" / "_state").mkdir(parents=True)
    (inbox_dir / "evidence").mkdir(parents=True)
    (data_dir / "configuration" / "source_collection_cadence.json").write_text(json.dumps(POLICY), encoding="utf-8")
    (inbox_dir / "discovered_media" / "_state" / "source-a.json").write_text(json.dumps(_state()), encoding="utf-8")
    (inbox_dir / "operations" / "runs" / "run.json").write_text(
        json.dumps(_run("2026-08-24T06:00:00+00:00")), encoding="utf-8"
    )
    (inbox_dir / "discovered_media" / "item.json").write_text(json.dumps({
        "source_id": "source-a", "first_seen_at": "2026-08-24T05:59:00+00:00", "body": "PRIVATE BODY",
    }), encoding="utf-8")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    payload = build_runtime_freshness(
        data_dir=data_dir, inbox_dir=inbox_dir, sources=[_source()], history_limit=10, now=NOW, use_cache=False,
    )
    after = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert payload["last_new_intelligence"] == "2026-08-24T05:59:00+00:00"
    assert "PRIVATE BODY" not in json.dumps(payload)
    assert before == after


def test_runtime_adapter_uses_signature_cache_and_returns_defensive_copy(tmp_path):
    data_dir = tmp_path / "data"
    inbox_dir = tmp_path / "inbox"
    (data_dir / "configuration").mkdir(parents=True)
    (inbox_dir / "discovered_media" / "_state").mkdir(parents=True)
    (data_dir / "configuration" / "source_collection_cadence.json").write_text(json.dumps(POLICY), encoding="utf-8")
    clear_freshness_cache()
    first = build_runtime_freshness(data_dir=data_dir, inbox_dir=inbox_dir, sources=[_source()])
    misses = freshness_module._cached_runtime_freshness.cache_info().misses
    first["system_state"] = "MUTATED BY CALLER"
    second = build_runtime_freshness(data_dir=data_dir, inbox_dir=inbox_dir, sources=[_source()])
    info = freshness_module._cached_runtime_freshness.cache_info()
    assert info.misses == misses
    assert info.hits >= 1
    assert second["system_state"] != "MUTATED BY CALLER"
