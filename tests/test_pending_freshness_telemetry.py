"""Trusted Freshness Recovery + Review Triage V1 -- the compact analyst
freshness surface on /pending. Every field is a real, directly computed
count/date; this module never renders on stakeholder Today."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.morning_brief import pending_freshness_telemetry


def _write_event(inbox_dir: Path, event_id: str, **overrides) -> None:
    folder = inbox_dir / "review_events" / "publication_review"
    folder.mkdir(parents=True, exist_ok=True)
    event = {
        "id": event_id,
        "record_type": "review_event",
        "workflow": "publication_review",
        "action": "publish",
        "object_id": f"ev-{event_id}",
        "object_type": "publication_draft",
        "occurred_at": "2026-09-01T10:00:00+00:00",
    }
    event.update(overrides)
    (folder / f"{event_id}.json").write_text(json.dumps(event), encoding="utf-8")


def test_pending_freshness_telemetry_computes_real_fields(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    _write_event(inbox_dir, "rev-today-1", occurred_at="2026-09-01T09:00:00+00:00")
    _write_event(inbox_dir, "rev-today-2", occurred_at="2026-09-01T14:00:00+00:00")
    _write_event(inbox_dir, "rev-yesterday", occurred_at="2026-08-31T09:00:00+00:00")
    _write_event(inbox_dir, "rev-reject-today", action="reject", occurred_at="2026-09-01T11:00:00+00:00")

    published = [
        {"id": "ev-a", "published_date": "2026-08-06"},
        {"id": "ev-b", "published_date": "2026-07-01"},
    ]
    pending_triage = {
        "counts": {"review_now": 2, "structured_registry": 1, "review_soon": 5, "older_backlog": 100},
        "buckets": [
            {
                "key": "review_now",
                "entries": [
                    {"id": "d1", "date": "2026-08-30", "captured_date": "2026-08-25"},
                    {"id": "d2", "date": "2026-08-28", "captured_date": "2026-08-20"},
                ],
            },
            {
                "key": "structured_registry",
                "entries": [{"id": "d3", "published_date": "2019-01-01", "captured_date": "2026-08-22"}],
            },
            {"key": "review_soon", "entries": []},
        ],
    }

    result = pending_freshness_telemetry(
        published=published,
        pending_triage=pending_triage,
        inbox_dir=inbox_dir,
        now=datetime(2026, 9, 1, 18, 0, tzinfo=timezone.utc),
    )

    assert result["newest_trusted_source_date"] == "2026-08-06"
    assert result["current_priority_pending"] == 3
    assert result["oldest_current_priority_published_date"] == "2019-01-01"
    assert result["publications_approved_today"] == 2
    assert result["evidence_approved_today"] == 2
    assert result["queue_age_days"] == 12  # oldest captured_date 2026-08-20 -> 12 days as of 2026-09-01


def test_pending_freshness_telemetry_handles_empty_state(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "inbox"
    result = pending_freshness_telemetry(
        published=[],
        pending_triage={"counts": {}, "buckets": []},
        inbox_dir=inbox_dir,
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    assert result["newest_trusted_source_date"] is None
    assert result["current_priority_pending"] == 0
    assert result["oldest_current_priority_published_date"] is None
    assert result["publications_approved_today"] == 0
    assert result["evidence_approved_today"] == 0
    assert result["queue_age_days"] is None
