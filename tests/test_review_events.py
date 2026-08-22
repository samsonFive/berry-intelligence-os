from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.services.analyst_queue import apply_action, load_state
from app.services.review_events import append_review_event, load_review_events, review_event_analytics
from app.services.runtime_backup import create_backup, restore_backup, verify_backup


def test_event_is_compact_append_only_and_idempotent(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    subject = {
        "id": "draft-1", "title": "private title", "summary": "private summary",
        "source_id": "source-1", "berry_ids": ["strawberry"],
        "discovery_provenance": {"run_id": "run-1", "first_seen_at": "2026-08-01T00:00:00+00:00"},
    }
    source = {"id": "source-1", "source_class": "trade", "discovery": {"adapter": "rss", "query_family": "market"}}
    first = append_review_event(
        inbox, workflow="publication_review", object_id="draft-1", object_type="publication_draft",
        action="reject", prior_state="pending", new_state="rejected", actor="analyst",
        subject=subject, source=source, reason_category="irrelevant",
        occurred_at="2026-08-21T12:00:00+00:00",
    )
    retry = append_review_event(
        inbox, workflow="publication_review", object_id="draft-1", object_type="publication_draft",
        action="reject", prior_state="pending", new_state="rejected", actor="analyst",
        subject=subject, source=source, reason_category="irrelevant",
        occurred_at="2026-08-21T12:01:00+00:00",
    )
    events = load_review_events(inbox)
    assert first.created is True and retry.created is False
    assert len(events) == 1
    assert events[0]["source_class"] == "trade" and events[0]["pipeline_run_id"] == "run-1"
    assert "title" not in events[0] and "summary" not in events[0]


def test_queue_transition_records_distinct_workflow_and_retry_is_noop(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    assert apply_action(inbox, dimension="testing", item_id="ev-1", action="pass", reviewer="analyst") == "pass"
    assert apply_action(inbox, dimension="testing", item_id="ev-1", action="pass", reviewer="analyst") == "pass"
    assert load_state(inbox)["testing"]["ev-1"]["state"] == "pass"
    events = load_review_events(inbox)
    assert [(event["workflow"], event["action"]) for event in events] == [("claim_testing", "pass")]


def test_real_defer_and_dismiss_actions_keep_distinct_meaning(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    apply_action(inbox, dimension="testing", item_id="ev-test", action="defer", reviewer="analyst")
    apply_action(inbox, dimension="reading", item_id="ev-read", action="dismiss", reviewer="analyst")
    apply_action(inbox, dimension="pending", item_id="draft-1", action="dismiss", reviewer="analyst")
    events = load_review_events(inbox)
    assert {(row["workflow"], row["action"]) for row in events} == {
        ("claim_testing", "defer"), ("reading_queue", "dismiss"), ("publication_triage", "dismiss")
    }


def test_analytics_do_not_infer_history_and_suppress_small_sample_rates(tmp_path: Path) -> None:
    analytics = review_event_analytics([], current_publication_drafts=[{"id": "draft-legacy", "review_state": "pending"}])
    assert analytics["total_observed_decisions"] == 0
    assert analytics["unreviewed_current_publication_objects"] == 1
    assert analytics["publish_rate"] is None and analytics["rates_measurable"] is False
    assert analytics["minimum_rate_sample"] == 30


def test_rates_require_thirty_dated_publication_decisions() -> None:
    events = [
        {
            "id": f"rev-{index}", "record_type": "review_event", "workflow": "publication_review",
            "object_id": f"draft-{index}", "action": "publish" if index < 18 else "reject",
            "occurred_at": f"2026-08-{20 + (index % 2):02d}T12:00:00+00:00",
            "source_id": "source-a", "source_class": "news_search", "query_family": "news_search_rss",
        }
        for index in range(30)
    ]
    analytics = review_event_analytics(events)
    assert analytics["rates_measurable"] is True
    assert analytics["publish_rate"] == 0.6 and analytics["reject_rate"] == 0.4
    assert analytics["counts_by_source"] == {"source-a": 30}
    assert analytics["counts_by_query_family"] == {"news_search_rss": 30}


def test_review_events_survive_verified_runtime_backup_restore(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    result = append_review_event(
        runtime / "inbox", workflow="reading_queue", object_id="ev-1", object_type="evidence",
        action="dismiss", prior_state="unread", new_state="dismissed", actor="private-analyst",
        occurred_at="2026-08-21T12:00:00+00:00",
    )
    (runtime / "data").mkdir(parents=True)
    archive = create_backup(runtime, tmp_path / "backups", now=datetime(2026, 8, 21, tzinfo=timezone.utc))
    manifest = verify_backup(archive)
    assert result.path.relative_to(runtime).as_posix() in {row["path"] for row in manifest["files"]}
    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert load_review_events(restored / "inbox")[0]["actor"] == "private-analyst"


def test_static_builder_has_no_review_event_dependency() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts" / "build_static.py").read_text(encoding="utf-8")
    assert "review_events" not in source
    assert "INBOX_DIR" not in source
