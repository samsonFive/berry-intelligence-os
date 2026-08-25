"""Source lifecycle reliability and freshness-denominator tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json

from app.services.freshness_assurance import (
    BLOCKED,
    CURRENT_ACTIVE,
    SYSTEM_CURRENT,
    SYSTEM_DEGRADED,
    build_freshness_assurance,
)
from app.services.source_cadence import source_schedule_decision
from app.services.source_lifecycle import (
    ACTIVE,
    DISABLED,
    OPERATOR_ACTION_REQUIRED,
    RETIRED,
    is_collection_eligible,
    is_scheduled_coverage,
    lifecycle_state,
    with_lifecycle,
)
from scripts.set_source_lifecycle import main as set_lifecycle_main


UTC = timezone.utc
NOW = datetime(2026, 8, 25, 3, 30, tzinfo=UTC)
POLICY = {"cadence_by_update_cadence": {"daily": 86400}}


def _source(source_id: str = "source-a", *, state: str | None = None) -> dict:
    source = {
        "id": source_id,
        "label": source_id,
        "enabled": True,
        "update_cadence": "daily",
        "berry_ids": ["berry-blueberry"],
        "entity_types": ["trade_press"],
        "discovery": {"adapter": "article_rss", "feed_url": "https://example.invalid/feed"},
    }
    if state:
        source["lifecycle"] = {
            "state": state,
            "reason": f"{state} fixture reason",
            "changed_at": "2026-08-25T03:00:00Z",
        }
    return source


def _state(*, status: str = "ok", success: str | None = "2026-08-25T03:00:00+00:00", error: str | None = None) -> dict:
    return {
        "status": status,
        "last_checked_at": "2026-08-25T03:00:00+00:00",
        "last_success_at": success,
        "new": 1 if status == "ok" else 0,
        "found": 10 if status == "ok" else 0,
        "error": error,
    }


def _run(*, status: str = "ok") -> dict:
    return {
        "started_at": "2026-08-25T03:00:00+00:00",
        "completed_at": "2026-08-25T03:00:00+00:00",
        "sources": [{"source_id": "source-a", "status": status, "new": 1 if status == "ok" else 0}],
    }


def _build(source: dict, state: dict, runs: list[dict]) -> dict:
    return build_freshness_assurance(
        sources=[source],
        discovery_states={"source-a": state},
        run_records=runs,
        discovered_items=[],
        drafts=[],
        scheduler_runs=[],
        policy=POLICY,
        now=NOW,
    )


def test_active_disabled_retired_and_operator_action_contract():
    active = _source()
    disabled = _source(state=DISABLED)
    retired = _source(state=RETIRED)
    operator = _source(state=OPERATOR_ACTION_REQUIRED)

    assert lifecycle_state(active) == ACTIVE
    assert is_collection_eligible(active)
    assert is_scheduled_coverage(active)
    assert not is_collection_eligible(disabled)
    assert not is_scheduled_coverage(disabled)
    assert not is_collection_eligible(retired)
    assert not is_scheduled_coverage(retired)
    assert not is_collection_eligible(operator)
    assert is_scheduled_coverage(operator)


def test_legacy_enabled_false_is_disabled_without_new_metadata():
    source = _source()
    source["enabled"] = False
    assert lifecycle_state(source) == DISABLED
    assert not is_collection_eligible(source)
    assert not is_scheduled_coverage(source)


def test_retired_source_is_unscheduled_and_excluded_from_freshness_denominator():
    retired = _source(state=RETIRED)
    decision = source_schedule_decision(retired, discovery_state=None, policy=POLICY, now=NOW)
    assert decision.due is False
    assert decision.cadence_class == "UNSCHEDULED"

    payload = _build(retired, _state(status="error", success=None, error="gone"), [_run(status="error")])
    assert payload["counts"]["scheduled_sources"] == 0
    assert payload["sources"] == []


def test_operator_action_required_remains_blocked_and_cannot_create_false_green():
    source = _source(state=OPERATOR_ACTION_REQUIRED)
    payload = _build(source, _state(), [_run()])
    assert payload["sources"][0]["state"] == BLOCKED
    assert payload["system_state"] == SYSTEM_DEGRADED
    assert payload["can_claim_current"] is False


def test_blocked_source_returns_current_only_after_config_repair_and_genuine_success():
    blocked = _source(state=OPERATOR_ACTION_REQUIRED)
    failure = _state(status="error", success=None, error="403 Forbidden")
    degraded = _build(blocked, failure, [_run(status="error")])
    assert degraded["system_state"] == SYSTEM_DEGRADED

    repaired = _source()
    still_failing = _build(repaired, failure, [_run(status="error")])
    assert still_failing["system_state"] == SYSTEM_DEGRADED

    successful = _build(
        repaired,
        _state(),
        [_run(status="error"), _run(status="error"), _run(status="ok")],
    )
    assert successful["sources"][0]["state"] == CURRENT_ACTIVE
    assert successful["sources"][0]["consecutive_failures"] == 0
    assert successful["system_state"] == SYSTEM_CURRENT


def test_lifecycle_is_non_destructive_and_preserves_optional_replacement_relation():
    source = _source(state=RETIRED)
    source["lifecycle"]["replacement_source_id"] = "source-b"
    evidence = {"id": "ev-historical", "source_id": source["id"], "status": "published"}
    before_source = deepcopy(source)
    before_evidence = deepcopy(evidence)

    assert lifecycle_state(source) == RETIRED
    assert source["lifecycle"]["replacement_source_id"] == "source-b"
    assert source == before_source
    assert evidence == before_evidence
    assert evidence["source_id"] == source["id"]


def test_transition_requires_reason_and_preserves_every_non_lifecycle_field():
    source = _source()
    updated = with_lifecycle(
        source,
        state=RETIRED,
        reason="Official feed was permanently removed.",
        changed_at="2026-08-25T03:00:00+00:00",
        replacement_source_id="source-b",
    )
    assert source.get("lifecycle") is None
    assert updated["id"] == source["id"]
    assert updated["discovery"] == source["discovery"]
    assert updated["lifecycle"]["replacement_source_id"] == "source-b"


def test_unknown_configured_lifecycle_fails_closed_for_collection():
    source = _source()
    source["lifecycle"] = {"state": "TYPO"}
    assert lifecycle_state(source) == OPERATOR_ACTION_REQUIRED
    assert not is_collection_eligible(source)
    assert is_scheduled_coverage(source)


def test_operator_cli_is_dry_run_by_default_and_applies_only_when_explicit(tmp_path):
    data_dir = tmp_path / "data"
    source_file = data_dir / "configuration" / "sources.json"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(json.dumps([_source()]), encoding="utf-8")
    args = [
        "--data-dir", str(data_dir),
        "--source", "source-a",
        "--state", RETIRED,
        "--reason", "Official feed permanently removed.",
        "--changed-at", "2026-08-25T03:00:00Z",
        "--source-url", "https://example.invalid/current-archive/",
    ]
    before = source_file.read_bytes()
    assert set_lifecycle_main(args) == 0
    assert source_file.read_bytes() == before

    assert set_lifecycle_main([*args, "--apply"]) == 0
    stored = json.loads(source_file.read_text(encoding="utf-8"))[0]
    assert stored["id"] == "source-a"
    assert stored["lifecycle"]["state"] == RETIRED
    assert stored["url"] == "https://example.invalid/current-archive/"
