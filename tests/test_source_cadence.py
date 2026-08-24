from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from app.services.source_cadence import (
    berry_coverage,
    build_cadence_audit,
    cadence_seconds,
    maximum_safe_interval_seconds,
    request_attempts_per_day,
    select_due_sources,
    source_schedule_decision,
)


UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
POLICY = {
    "cadence_classes": {"HIGH_FREQUENCY": 21600, "NORMAL": 86400, "LOW_FREQUENCY": 604800},
    "cadence_by_update_cadence": {"realtime": 21600, "daily": 86400, "weekly": 604800, "event_driven": 604800},
    "discoverable_fallback_seconds": 604800,
    "retryable_failure_seconds": 86400,
    "source_overrides": {},
}


def source(
    source_id: str,
    *,
    cadence: str = "daily",
    adapter: str = "article_rss",
    berries: list[str] | None = None,
    item_limit: int | None = None,
) -> dict:
    discovery = {"adapter": adapter, "feed_url": f"https://example.invalid/{source_id}"}
    if item_limit is not None:
        discovery["item_limit"] = item_limit
    return {
        "id": source_id,
        "label": source_id,
        "update_cadence": cadence,
        "berry_ids": berries or ["berry-blueberry"],
        "entity_types": ["trade_press"],
        "region_coverage": ["global"],
        "discovery": discovery,
    }


def state(*, checked: str, success: str | None = None, status: str = "ok", error: str | None = None, found: int = 20) -> dict:
    return {
        "status": status,
        "last_checked_at": checked,
        "last_success_at": success,
        "error": error,
        "new": 0,
        "found": found,
    }


def test_cadence_calculation_and_explicit_high_frequency_override() -> None:
    policy = {**POLICY, "source_overrides": {"high": {"cadence_seconds": 21600, "cadence_class": "HIGH_FREQUENCY"}}}
    assert cadence_seconds(source("normal"), policy) == 86400
    assert cadence_seconds(source("high", cadence="daily"), policy) == 21600


def test_due_not_due_and_never_run_selection_is_deterministic() -> None:
    sources = [source("b"), source("a"), source("new")]
    states = {
        "a": state(checked="2026-08-24T10:00:00+00:00", success="2026-08-24T10:00:00+00:00"),
        "b": state(checked="2026-08-23T10:00:00+00:00", success="2026-08-23T10:00:00+00:00"),
        "new": None,
    }
    due, decisions = select_due_sources(sources, discovery_states=states, policy=POLICY, now=NOW)
    assert due == ["b", "new"]
    assert [row.source_id for row in decisions] == ["a", "b", "new"]
    assert decisions[0].next_due == "2026-08-25T10:00:00+00:00"


def test_quiet_healthy_source_obeys_low_frequency_cadence() -> None:
    decision = source_schedule_decision(
        source("quiet", cadence="weekly"),
        discovery_state=state(checked="2026-08-20T12:00:00+00:00", success="2026-08-20T12:00:00+00:00"),
        policy=POLICY,
        now=NOW,
    )
    assert decision.due is False
    assert decision.cadence_class == "LOW_FREQUENCY"
    assert decision.next_due == "2026-08-27T12:00:00+00:00"


def test_retryable_failure_uses_last_attempt_and_bounded_retry() -> None:
    decision = source_schedule_decision(
        source("retry", cadence="weekly"),
        discovery_state=state(
            checked="2026-08-23T11:00:00+00:00",
            success="2026-08-20T00:00:00+00:00",
            status="error",
            error="temporary timeout",
        ),
        policy=POLICY,
        now=NOW,
    )
    assert decision.due is True
    assert decision.cadence_class == "HEALTH_DEGRADED"
    assert decision.cadence_seconds == 86400


def test_blocked_source_reuses_source_health_and_is_not_polled() -> None:
    decision = source_schedule_decision(
        source("blocked"),
        discovery_state=state(
            checked="2026-08-01T00:00:00+00:00",
            status="error",
            error="403 Forbidden",
        ),
        policy=POLICY,
        now=NOW,
    )
    assert decision.health_state == "BLOCKED"
    assert decision.due is False
    assert decision.next_due is None


def test_feed_window_protection_uses_observed_velocity_not_capacity_alone() -> None:
    assert maximum_safe_interval_seconds(
        observed_new_items=50,
        observation_seconds=5 * 86400,
        feed_window_size=20,
    ) == 86400
    assert maximum_safe_interval_seconds(
        observed_new_items=0,
        observation_seconds=5 * 86400,
        feed_window_size=20,
    ) is None


def test_sitemap_uses_configured_cadence_without_rss_velocity_assumption() -> None:
    sitemap = source("map", cadence="weekly", adapter="sitemap_xml", item_limit=10)
    decision = source_schedule_decision(sitemap, discovery_state=None, policy=POLICY, now=NOW)
    assert decision.due is True
    assert decision.cadence_seconds == 604800
    assert maximum_safe_interval_seconds(
        observed_new_items=0, observation_seconds=0, feed_window_size=10,
    ) is None


def test_all_four_berry_coverage_is_volume_independent() -> None:
    sources = [
        source("blue", berries=["berry-blueberry"]),
        source("straw", berries=["berry-strawberry"]),
        source("cane", berries=["berry-raspberry", "berry-blackberry"]),
    ]
    _, decisions = select_due_sources(
        sources, discovery_states={row["id"]: None for row in sources}, policy=POLICY, now=NOW,
    )
    assert berry_coverage(sources, decisions) == {
        "berry-blueberry": 1,
        "berry-strawberry": 1,
        "berry-raspberry": 1,
        "berry-blackberry": 1,
    }


def test_request_estimate_counts_multi_feed_source() -> None:
    one = source("one")
    two = source("two", cadence="weekly")
    two["discovery"] = {"adapter": "youtube_feed", "feed_urls": ["https://a.invalid", "https://b.invalid"]}
    assert request_attempts_per_day([one, two], POLICY) == 1 + 2 / 7


def test_audit_covers_duplicate_heavy_rich_productive_and_failures() -> None:
    rich = source("rich", item_limit=20)
    runs = [
        {"started_at": "2026-08-20T00:00:00+00:00", "sources": [{"source_id": "rich", "status": "ok", "found": 20, "new": 20, "known": 0}]},
        {"started_at": "2026-08-21T00:00:00+00:00", "sources": [{"source_id": "rich", "status": "ok", "found": 20, "new": 0, "known": 20}]},
        {"started_at": "2026-08-22T00:00:00+00:00", "sources": [{"source_id": "rich", "status": "error", "found": 0, "new": 0, "known": 0}]},
        {"started_at": "2026-08-23T00:00:00+00:00", "sources": [{"source_id": "rich", "status": "ok", "found": 20, "new": 2, "known": 18}]},
    ]
    drafts = [
        {"source_id": "rich", "evidence_role": "publication_artifact", "source_completeness": {"class": "FULL_ARTICLE"}},
        {"source_id": "rich", "evidence_role": "publication_artifact", "source_completeness": {"class": "THIN_DESCRIPTION"}},
    ]
    payload = build_cadence_audit(
        sources=[rich],
        run_records=runs,
        drafts=drafts,
        discovery_states={"rich": state(checked="2026-08-23T00:00:00+00:00", success="2026-08-23T00:00:00+00:00", found=20)},
        policy=POLICY,
        now=NOW,
    )
    row = payload["sources"][0]
    assert row["evidence_sufficient"] is True
    assert row["new_items_excluding_initial_run"] == 2
    assert row["duplicate_only_repeat_run_rate"] == 0.667
    assert row["relevant_publication_drafts"] == 2
    assert row["rich_body"] == {"FULL_ARTICLE": 1, "THIN_DESCRIPTION": 1}
    assert row["failures"] == 1


def test_production_policy_keeps_measured_short_windows_inside_safety_ceiling() -> None:
    policy = json.loads((ROOT / "data" / "configuration" / "source_collection_cadence.json").read_text(encoding="utf-8"))
    expected_ceilings = {
        "source-20260819-blue-book-services": 83025,
        "source-20260819-hortidaily": 69385,
        "source-fruitnet-produce-plus": 31510,
    }
    for source_id, ceiling in expected_ceilings.items():
        assert policy["source_overrides"][source_id]["cadence_seconds"] <= ceiling
