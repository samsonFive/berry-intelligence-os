"""Versioned acquisition-state fingerprints for safe idempotency invalidation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def acquisition_signature(pipeline: str, version: int, configuration: Any) -> str:
    canonical = json.dumps(
        {"pipeline": pipeline, "version": version, "configuration": configuration},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def version_state(state: dict[str, Any], *, signature: str, seen_key: str) -> dict[str, Any]:
    """Reset derived seen state on meaning changes while retaining run history."""
    previous = state.get("acquisition_signature")
    if previous and previous != signature:
        state.setdefault("superseded_signatures", []).append(previous)
        state[seen_key] = []
    state["acquisition_signature"] = signature
    state["state_schema_version"] = 1
    return state
