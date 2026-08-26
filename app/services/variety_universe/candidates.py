"""Inbox-only Variety candidates. Never writes data/. GET is read-only."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.services.variety_universe.identity import (
    HUMAN_STATES,
    LABELS,
    STATE_CONFIRMED_SAME,
    STATE_REJECTED,
)

CANDIDATE_RECORD_TYPE = "variety_candidate"


class VarietyCandidateError(ValueError):
    pass


def candidates_dir(inbox_dir: Path) -> Path:
    return inbox_dir / "variety_candidates"


def load_variety_candidates(inbox_dir: Path) -> list[dict[str, Any]]:
    target = candidates_dir(inbox_dir)
    if not target.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(target.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("id"):
            rows.append(payload)
    return rows


def persist_variety_candidates(
    candidates: list[dict[str, Any]],
    *,
    inbox_dir: Path,
    overwrite: bool = False,
) -> list[Path]:
    """Additive by default: existing files (which may carry a human decision)
    are not overwritten by a later import."""
    target = candidates_dir(inbox_dir)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "").strip()
        if not candidate_id:
            raise VarietyCandidateError("variety candidate is missing id")
        path = target / f"{candidate_id}.json"
        if path.is_file() and not overwrite:
            continue
        path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def candidate_by_id(inbox_dir: Path, candidate_id: str) -> dict[str, Any] | None:
    path = candidates_dir(inbox_dir) / f"{candidate_id}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def apply_identity_decision(
    candidate: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    notes: str = "",
) -> dict[str, Any]:
    if decision not in HUMAN_STATES:
        raise VarietyCandidateError(f"unknown identity decision: {decision!r}")
    if not (reviewer or "").strip():
        raise VarietyCandidateError("reviewer is required for any identity decision")
    updated = {**candidate}
    updated["identity_state"] = decision
    updated["identity_label"] = LABELS[decision]
    updated["reviewer"] = reviewer.strip()
    updated["review_notes"] = (notes or "").strip() or None
    updated["reviewed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated["human_gated"] = True
    if decision == STATE_CONFIRMED_SAME and not updated.get("candidate_canonical_match"):
        raise VarietyCandidateError("CONFIRMED SAME requires an existing canonical match to confirm against")
    if decision == STATE_REJECTED:
        updated["status"] = "rejected"
    else:
        updated["status"] = "reviewed"
    return updated


def identity_issues_for_variety(
    variety_id: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Unresolved candidate identity issues that mention this canonical variety."""
    open_states = {"possible_alias", "unknown"}
    issues: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("status") == "rejected":
            continue
        state = candidate.get("identity_state")
        match_id = candidate.get("candidate_canonical_match")
        match_ids = {match_id} if match_id else set()
        for match in candidate.get("matches") or []:
            if match.get("variety_id"):
                match_ids.add(match["variety_id"])
        if variety_id not in match_ids:
            continue
        if state not in open_states and state != "confirmed_same":
            continue
        issues.append(
            {
                "id": candidate.get("id"),
                "candidate_name": candidate.get("candidate_name"),
                "identity_state": state,
                "identity_label": candidate.get("identity_label") or LABELS.get(state, state),
                "source_label": candidate.get("source_label") or candidate.get("source_id"),
                "jurisdiction": candidate.get("jurisdiction"),
                "match_reason": candidate.get("match_reason"),
            }
        )
    return issues
