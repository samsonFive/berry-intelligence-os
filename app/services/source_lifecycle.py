"""Deterministic lifecycle rules for registered collection Sources.

Lifecycle is configuration, while BLOCKED/FAILING are observed runtime
health.  A retired or disabled Source remains in the registry for historical
lineage but is outside both collection and scheduled freshness coverage.  An
OPERATOR_ACTION_REQUIRED Source remains visible as degraded coverage while
automatic collection is paused.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

ACTIVE = "ACTIVE"
DISABLED = "DISABLED"
RETIRED = "RETIRED"
OPERATOR_ACTION_REQUIRED = "OPERATOR_ACTION_REQUIRED"

KNOWN_STATES = frozenset({ACTIVE, DISABLED, RETIRED, OPERATOR_ACTION_REQUIRED})


def lifecycle_state(source: dict[str, Any]) -> str:
    lifecycle = source.get("lifecycle") or {}
    configured = str(lifecycle.get("state") or "").strip().upper()
    if configured in KNOWN_STATES:
        return configured
    if configured:
        # Unknown lifecycle configuration must never resume collection by
        # accident.  Keep the gap visible for an operator to correct.
        return OPERATOR_ACTION_REQUIRED
    if source.get("enabled", True) is False:
        return DISABLED
    return ACTIVE


def lifecycle_reason(source: dict[str, Any]) -> str | None:
    lifecycle = source.get("lifecycle") or {}
    reason = lifecycle.get("reason")
    return reason.strip() if isinstance(reason, str) and reason.strip() else None


def has_discovery_configuration(source: dict[str, Any]) -> bool:
    discovery = source.get("discovery") or {}
    return bool(discovery.get("adapter") and (discovery.get("feed_url") or discovery.get("feed_urls")))


def is_collection_eligible(source: dict[str, Any]) -> bool:
    """Whether automatic or explicit collection may fetch this Source."""

    return lifecycle_state(source) == ACTIVE and has_discovery_configuration(source)


def is_scheduled_coverage(source: dict[str, Any]) -> bool:
    """Whether freshness must continue accounting for this Source.

    OPERATOR_ACTION_REQUIRED deliberately stays in the denominator: pausing
    retries must not turn a known coverage gap green.  RETIRED and DISABLED
    are intentional registry states and therefore are not scheduled coverage.
    """

    return lifecycle_state(source) in {ACTIVE, OPERATOR_ACTION_REQUIRED} and has_discovery_configuration(source)


def with_lifecycle(
    source: dict[str, Any],
    *,
    state: str,
    reason: str,
    changed_at: str,
    replacement_source_id: str | None = None,
) -> dict[str, Any]:
    """Return a lifecycle-updated Source without changing its identity/history."""

    normalized = state.strip().upper()
    if normalized not in KNOWN_STATES:
        raise ValueError(f"unknown Source lifecycle state: {state}")
    if not reason.strip():
        raise ValueError("Source lifecycle reason is required")
    try:
        timestamp = datetime.fromisoformat(changed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Source lifecycle changed_at must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError("Source lifecycle changed_at must include a timezone")

    updated = deepcopy(source)
    lifecycle = {
        "state": normalized,
        "reason": reason.strip(),
        "changed_at": changed_at,
    }
    if replacement_source_id and replacement_source_id.strip():
        lifecycle["replacement_source_id"] = replacement_source_id.strip()
    updated["lifecycle"] = lifecycle
    updated["enabled"] = normalized != DISABLED
    return updated
