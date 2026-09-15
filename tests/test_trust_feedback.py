from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.services.review_events import load_review_events
from app.services.trust_feedback import (
    FeedbackActor,
    FeedbackRequest,
    IdempotencyConflict,
    InvalidUndo,
    PromotionOutcome,
    STATE_APPROVED_SOURCE,
    STATE_EXCLUDED,
    STATE_PENDING_PROMOTION,
    STATE_TRUSTED,
    StaleFeedbackVersion,
    TrustFeedbackService,
    check_eligibility,
)


def _record(record_id: str = "ev-feedback-1", **overrides: object) -> dict:
    record = {
        "id": record_id,
        "record_type": "evidence",
        "status": "draft",
        "review_state": "in_review",
        "evidence_role": "publication_artifact",
        "source_id": "source-fixture",
        "source_name": "Fixture newsroom",
        "source_url": f"https://example.invalid/{record_id}",
        "published_date": date.today().isoformat(),
        "captured_date": date.today().isoformat(),
        "article": {
            "paragraphs": [{"index": 0, "text": "Readable source text. " * 40}],
            "word_count": 120,
        },
        "summary": "A source-backed summary.",
        "discovery_provenance": {"run_id": "run-fixture"},
    }
    record.update(overrides)
    return record


def _actor(*permissions: str, actor_id: str = "analyst-fixture") -> FeedbackActor:
    return FeedbackActor(actor_id, frozenset(permissions or ("submit_feedback",)))


def _request(action: str, *, key: str, expected: int = 0, **overrides: object) -> FeedbackRequest:
    values = {
        "action": action,
        "object_id": "ev-feedback-1",
        "object_type": "evidence",
        "actor": _actor("submit_feedback"),
        "idempotency_key": key,
        "expected_version": expected,
        "source_surface": "today",
        "intent": "retain_for_review" if action == "promote" else None,
    }
    values.update(overrides)
    return FeedbackRequest(**values)


def test_readable_record_promotes_only_through_governed_handler(tmp_path: Path) -> None:
    calls = []

    def approve(record, actor):
        calls.append((record["id"], actor.actor_id))
        return PromotionOutcome(True, STATE_TRUSTED, record["id"])

    service = TrustFeedbackService(tmp_path / "inbox", promotion_handler=approve)
    request = _request(
        "promote",
        key="promote-1",
        intent="governed_promotion",
        actor=_actor("submit_feedback", "promote_evidence"),
    )
    result = service.apply(request, _record())
    assert result.state == STATE_TRUSTED
    assert result.projection["eligible_for_trusted_feed"] is True
    assert result.projection["approved"] is True and result.projection["trusted"] is True
    assert calls == [("ev-feedback-1", "analyst-fixture")]


def test_approved_source_does_not_impersonate_trusted_intelligence(tmp_path: Path) -> None:
    service = TrustFeedbackService(
        tmp_path / "inbox",
        promotion_handler=lambda record, actor: PromotionOutcome(
            True, STATE_APPROVED_SOURCE, record["id"]
        ),
    )
    result = service.apply(
        _request(
            "promote",
            key="source-only",
            intent="governed_promotion",
            actor=_actor("submit_feedback", "promote_evidence"),
        ),
        _record(),
    )
    assert result.state == STATE_APPROVED_SOURCE
    assert result.projection["approved"] is True
    assert result.projection["trusted"] is False
    assert result.projection["eligible_for_trusted_feed"] is False


def test_typed_endorsement_and_defer_are_working_state_only(tmp_path: Path) -> None:
    service = TrustFeedbackService(tmp_path / "inbox")
    retained = service.apply(
        _request("promote", key="retain", intent="relevant"), _record()
    )
    assert retained.state == "retained"
    assert retained.projection["approved"] is False
    deferred = service.apply(
        _request("defer", key="defer", expected=1), _record()
    )
    assert deferred.state == "deferred"
    assert deferred.projection["deferred"] is True
    assert deferred.projection["eligible_for_trusted_feed"] is False


@pytest.mark.parametrize(
    "outcome",
    [
        "cookie_or_consent_page",
        "bot_wall",
        "empty_page",
        "navigation_only_shell",
        "unsupported_source",
    ],
)
def test_unusable_acquisition_never_reaches_promotion_handler(tmp_path: Path, outcome: str) -> None:
    called = False

    def approve(record, actor):
        nonlocal called
        called = True
        return PromotionOutcome(True, STATE_TRUSTED, record["id"])

    service = TrustFeedbackService(tmp_path / "inbox", promotion_handler=approve)
    record = _record(article={"paragraphs": []}, summary="")
    result = service.apply(
        _request(
            "promote",
            key=f"blocked-{outcome}",
            intent="governed_promotion",
            actor=_actor("submit_feedback", "promote_evidence"),
        ),
        record,
        acquisition_outcome={"outcome_category": outcome},
    )
    assert result.state == STATE_PENDING_PROMOTION
    assert any(value.startswith("unusable_acquisition:") for value in result.blockers)
    assert called is False


def test_missing_authority_and_existing_approval_gate_stay_effective(tmp_path: Path) -> None:
    service = TrustFeedbackService(
        tmp_path / "no-authority",
        promotion_handler=lambda record, actor: PromotionOutcome(True, STATE_TRUSTED, record["id"]),
    )
    blocked = service.apply(
        _request("promote", key="no-authority", intent="governed_promotion"),
        _record(),
    )
    assert blocked.state == STATE_PENDING_PROMOTION
    assert "review_authority_required" in blocked.blockers

    gated = TrustFeedbackService(
        tmp_path / "existing-gate",
        promotion_handler=lambda record, actor: PromotionOutcome(
            False, blockers=("existing_publication_gate_rejected",)
        ),
    ).apply(
        _request(
            "promote",
            key="gate-reject",
            intent="governed_promotion",
            actor=_actor("submit_feedback", "promote_evidence"),
        ),
        _record(),
    )
    assert gated.state == STATE_PENDING_PROMOTION
    assert gated.blockers == ("existing_publication_gate_rejected",)


def test_feedback_cannot_confirm_signal_or_promote_assessment(tmp_path: Path) -> None:
    called = False

    def approve(record, actor):
        nonlocal called
        called = True
        return PromotionOutcome(True, STATE_TRUSTED, record["id"])

    service = TrustFeedbackService(tmp_path / "inbox", promotion_handler=approve)
    signal = _record(record_id="sig-1", record_type="signal")
    result = service.apply(
        _request(
            "promote",
            key="signal-promote",
            object_id="sig-1",
            object_type="signal",
            intent="governed_promotion",
            actor=_actor("submit_feedback", "promote_evidence"),
        ),
        signal,
    )
    assert result.state == STATE_PENDING_PROMOTION
    assert result.blockers == ("governed_promotion_not_supported_for_object_type",)
    assert called is False


def test_exclude_preserves_record_and_reason_then_undo_restores_prior_state(tmp_path: Path) -> None:
    record = _record(status="published", review_state="published", fact_ids=["fact-1"])
    original = copy.deepcopy(record)
    service = TrustFeedbackService(tmp_path / "inbox")
    excluded = service.apply(
        _request("exclude", key="exclude-1", reason="wrong_entity"), record
    )
    assert excluded.state == STATE_EXCLUDED
    assert excluded.projection["excluded_from_trusted_feed"] is True
    assert excluded.projection["eligible_for_trusted_feed"] is False
    assert excluded.projection["exclusion_reason"] == "wrong_entity"
    assert record == original

    restored = service.apply(
        _request(
            "undo",
            key="undo-1",
            expected=1,
            original_event_id=excluded.event["id"],
        ),
        record,
    )
    assert restored.state == STATE_TRUSTED
    assert restored.projection["eligible_for_trusted_feed"] is True
    events = load_review_events(tmp_path / "inbox", workflow="trust_feedback")
    assert [event["action"] for event in events] == ["exclude", "undo"]
    assert events[-1]["undoes_event_id"] == excluded.event["id"]


def test_duplicate_click_is_idempotent_and_key_reuse_conflicts(tmp_path: Path) -> None:
    service = TrustFeedbackService(tmp_path / "inbox")
    request = _request("exclude", key="same-click", reason="duplicate")
    first = service.apply(request, _record())
    replay = service.apply(request, _record())
    assert first.event_created is True
    assert replay.idempotent_replay is True and replay.event_created is False
    assert len(load_review_events(tmp_path / "inbox", workflow="trust_feedback")) == 1
    with pytest.raises(IdempotencyConflict):
        service.apply(_request("defer", key="same-click", expected=1), _record())


def test_stale_version_and_superseded_undo_fail_without_new_events(tmp_path: Path) -> None:
    service = TrustFeedbackService(tmp_path / "inbox")
    first = service.apply(_request("exclude", key="v1", reason="irrelevant"), _record())
    with pytest.raises(StaleFeedbackVersion):
        service.apply(_request("defer", key="stale", expected=0), _record())
    service.apply(_request("defer", key="v2", expected=1), _record())
    with pytest.raises(InvalidUndo, match="superseded"):
        service.apply(
            _request(
                "undo", key="late-undo", expected=2, original_event_id=first.event["id"]
            ),
            _record(),
        )
    assert len(load_review_events(tmp_path / "inbox", workflow="trust_feedback")) == 2


def test_event_records_actor_timestamp_versions_surface_and_valid_contract(tmp_path: Path) -> None:
    service = TrustFeedbackService(tmp_path / "inbox")
    result = service.apply(
        _request("exclude", key="audit-1", reason="misleading_extraction"), _record()
    )
    event = dict(result.event)
    assert event["actor"] == "analyst-fixture"
    assert event["occurred_at"] and event["source_surface"] == "today"
    assert event["prior_state"] == "unreviewed" and event["resulting_state"] == "excluded"
    assert event["expected_version"] == 0 and event["state_version"] == 1
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "trust-feedback-event.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(event)) == []


def test_historical_and_unknown_dates_keep_explicit_limitations() -> None:
    historical = check_eligibility(
        _record(published_date="2020-01-01"), today=date(2026, 9, 15)
    )
    assert historical.eligible is True
    assert historical.current_news_eligible is False
    assert historical.date_class == "historical"
    assert "historical_context_only" in historical.limitations

    unknown = check_eligibility(_record(published_date=None), today=date(2026, 9, 15))
    assert unknown.eligible is True
    assert unknown.current_news_eligible is False
    assert unknown.date_class == "unknown"
    assert "publication_date_unknown" in unknown.limitations


def test_required_provenance_is_explained_and_never_deleted(tmp_path: Path) -> None:
    record = _record(source_url="", source_id=None, source_name="", captured_date="")
    original = copy.deepcopy(record)
    result = TrustFeedbackService(tmp_path / "inbox").apply(
        _request(
            "promote",
            key="missing-provenance",
            intent="governed_promotion",
            actor=_actor("submit_feedback", "promote_evidence"),
        ),
        record,
    )
    assert result.state == STATE_PENDING_PROMOTION
    assert set(result.blockers) >= {
        "missing_provenance:source_url",
        "missing_provenance:source_identity",
        "missing_provenance:captured_date",
    }
    assert record == original


def test_static_builder_has_no_private_feedback_dependency() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "build_static.py"
    ).read_text(encoding="utf-8")
    assert "trust_feedback" not in source
    assert "analyst_queue_state" not in source
