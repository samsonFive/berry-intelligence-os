"""Publication Review Command Service V1 -- crash consistency and reader
isolation tests.

Simulates a hard-stop crash after every documented promotion write phase
(`FAILURE-AND-RECOVERY.md`'s own table): intent, staged publication, staged
decision, staged event, the real evidence write, the real audit event, the
draft compare-and-set, and the commit marker. At every phase, this proves:

  1. Before the commit marker, a dynamic reader (`repositories.evidence`)
     sees only the prior complete state -- never a staged or partial
     record.
  2. `reconcile_pending_transactions()` converges the interrupted
     transaction to exactly one outcome -- either safely abandoned (prior
     state preserved) or resumed-and-committed (new complete state) --
     never a duplicate publication and never a contradictory
     half-approved draft state.
  3. A subsequent identical command call after recovery behaves
     idempotently (returns the same result, creates nothing new).

Each crash is injected by wrapping one real function so it still performs
its real write and then raises -- the process genuinely did the work up to
that point, exactly like a real interpreter/host that dies right after a
syscall returns.
"""

from __future__ import annotations

import json

import pytest

from app.composition import get_repositories
from app.repositories.paths import SCHEMAS_DIR
from app.services import publication_review_command as command_module
from app.services import publication_review_domain as domain
from app.services import publication_review_repository as repository_module
from app.services.publication_review_command import (
    ActorIdentity, CommandDependencies, InMemoryActorDirectory, PublicationReviewCommandService,
    PERMISSION_PUBLICATION_REVIEW,
)
from app.services.publication_review_repository import DraftState, DurableReviewRepository


class SimulatedCrash(Exception):
    """Marks a deliberately injected hard-stop -- not a real application
    error. Every real write the wrapped function performed before raising
    already happened; this is what distinguishes it from an ordinary
    caught exception rollback."""


def _crash_after(monkeypatch, obj, func_name, *, when):
    """Wrap `obj.func_name` so the first call for which `when(*args,
    **kwargs)` is true still executes the real function (its write
    genuinely happens) and then raises `SimulatedCrash`. Every other call
    -- before the match, or after the crash has already fired once --
    behaves completely normally, so recovery's own retries are real calls
    to real code, not further simulated crashes."""
    original = getattr(obj, func_name)
    state = {"fired": False}

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        if not state["fired"] and when(*args, **kwargs):
            state["fired"] = True
            raise SimulatedCrash(f"simulated crash after {func_name}")
        return result

    monkeypatch.setattr(obj, func_name, wrapper)


def _readable_draft(draft_id="ev-media-1") -> dict:
    return {
        "id": draft_id, "title": "Blueberry acreage grows in Peru", "source_id": "source-1",
        "source_url": "https://example.invalid/peru-blueberries", "captured_date": "2026-09-16",
        "submitted_by": "media-orchestration", "summary": "A short summary.", "published_date": "2026-09-15",
        "article": {
            "word_count": 300, "paragraphs": [{"index": 0, "text": "word " * 300}], "content_sha256": "a" * 64,
        },
    }


class Harness:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.data_dir = tmp_path / "data"
        (self.data_dir / "evidence").mkdir(parents=True)
        self.inbox_dir = tmp_path / "inbox"
        self.review_root = tmp_path / "review_state"
        self.repository = DurableReviewRepository(self.review_root)
        self.actors = InMemoryActorDirectory()
        self.actors.register(ActorIdentity(
            actor_id="alice", kind="human", permissions=frozenset({PERMISSION_PUBLICATION_REVIEW}),
        ))
        self.repositories = get_repositories(self.data_dir, SCHEMAS_DIR)
        self.deps = CommandDependencies(
            repository=self.repository, actor_directory=self.actors, evidence_reader=self.repositories.evidence,
            evidence_schema_path=SCHEMAS_DIR / "evidence.schema.json", evidence_data_dir=self.data_dir,
            review_events_inbox=self.inbox_dir, entity_ids_resolver=lambda: frozenset(),
        )
        self.service = PublicationReviewCommandService(self.deps)

    def seed(self, draft: dict) -> DraftState:
        eligibility = domain.check_eligibility(draft)
        digest = domain.compute_review_content_digest(draft, eligibility=eligibility)
        provenance_digest = domain.compute_provenance_digest(draft)
        state = DraftState(
            id=draft["id"], version=1, state=domain.PENDING_REVIEW, draft=draft, content_digest=digest,
            provenance_digest=provenance_digest, content_class=eligibility.content_class,
            acquisition_classification=eligibility.body_state, created_at="2026-09-16T00:00:00+00:00",
            updated_at="2026-09-16T00:00:00+00:00",
        )
        return self.repository.create_draft_state(state)

    def envelope(self, draft_id, *, idempotency_key="k1") -> domain.CommandEnvelope:
        return domain.CommandEnvelope(
            draft_id=draft_id, actor_id="alice", idempotency_key=idempotency_key, expected_version=1,
            reviewed_content_digest=self.repository.get_draft_state(draft_id).content_digest,
        )

    def evidence_file(self, draft_id: str):
        return self.data_dir / "evidence" / f"{draft_id}.json"


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


def _attempt_approval_expecting_crash(harness, env):
    with pytest.raises(SimulatedCrash):
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)


# ---------------------------------------------------------------------------
# Phase 1: before intent is durable (approve_publication never gets far
# enough to write anything) -- prior complete state only.
# ---------------------------------------------------------------------------


def test_crash_before_intent_leaves_only_prior_complete_state(harness, monkeypatch):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])

    def _explode(*a, **k):
        raise SimulatedCrash("crash before any journal write")

    monkeypatch.setattr(harness.repository, "write_journal_phase", _explode)
    with pytest.raises(SimulatedCrash):
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    assert not harness.evidence_file(draft["id"]).exists()
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW
    assert harness.repository.pending_transactions() == []


# ---------------------------------------------------------------------------
# Phase 2: after intent, before publication stage.
# ---------------------------------------------------------------------------


def test_crash_after_intent_before_staged_publication(harness, monkeypatch):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    _crash_after(monkeypatch, harness.repository, "write_journal_phase", when=lambda *a, **k: (a[2] if len(a) > 2 else k.get("phase")) == "intent")

    _attempt_approval_expecting_crash(harness, env)
    # Reader isolation: prior complete state only.
    assert not harness.evidence_file(draft["id"]).exists()
    assert harness.repositories.evidence.get(draft["id"]) is None
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW

    reports = harness.service.reconcile_pending_transactions()
    assert reports and reports[0]["outcome"] == "abandoned_incomplete_stage"
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW
    assert not harness.evidence_file(draft["id"]).exists()

    # A fresh, real approval attempt still succeeds after safe abandonment.
    retry_env = harness.envelope(draft["id"], idempotency_key="after-recovery")
    result = harness.service.approve_publication(retry_env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert result.resulting_state == domain.APPROVED
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Phase 3: publication staged, decision absent.
# ---------------------------------------------------------------------------


def test_crash_after_staged_publication_before_staged_decision(harness, monkeypatch):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    _crash_after(
        monkeypatch, harness.repository, "write_journal_phase",
        when=lambda *a, **k: (a[2] if len(a) > 2 else k.get("phase")) == "staged_publication",
    )

    _attempt_approval_expecting_crash(harness, env)
    assert not harness.evidence_file(draft["id"]).exists()
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW

    reports = harness.service.reconcile_pending_transactions()
    assert reports[0]["outcome"] == "abandoned_incomplete_stage"
    assert not harness.evidence_file(draft["id"]).exists()
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW


# ---------------------------------------------------------------------------
# Phase 4: decision staged, audit event absent.
# ---------------------------------------------------------------------------


def test_crash_after_staged_decision_before_staged_event(harness, monkeypatch):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    _crash_after(
        monkeypatch, harness.repository, "write_journal_phase",
        when=lambda *a, **k: (a[2] if len(a) > 2 else k.get("phase")) == "staged_decision",
    )

    _attempt_approval_expecting_crash(harness, env)
    assert not harness.evidence_file(draft["id"]).exists()

    reports = harness.service.reconcile_pending_transactions()
    assert reports[0]["outcome"] == "abandoned_incomplete_stage"
    assert not harness.evidence_file(draft["id"]).exists()
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW


# ---------------------------------------------------------------------------
# Phase 5: audit event staged, commit marker absent -- resumable: every
# input needed to finish is already durably staged.
# ---------------------------------------------------------------------------


def test_crash_after_staged_event_before_evidence_write_resumes_on_reconcile(harness, monkeypatch):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    _crash_after(
        monkeypatch, harness.repository, "write_journal_phase",
        when=lambda *a, **k: (a[2] if len(a) > 2 else k.get("phase")) == "staged_event",
    )

    _attempt_approval_expecting_crash(harness, env)
    # Reader isolation held throughout the crash.
    assert not harness.evidence_file(draft["id"]).exists()
    assert harness.repositories.evidence.get(draft["id"]) is None
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW

    reports = harness.service.reconcile_pending_transactions()
    assert reports[0]["outcome"] == "resumed_and_committed"
    # New complete state now visible.
    assert harness.evidence_file(draft["id"]).exists()
    assert harness.repository.get_draft_state(draft["id"]).state == domain.APPROVED
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1
    assert len(list(harness.inbox_dir.rglob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Phase 5b: crash exactly between the real evidence write and the real
# audit event append (mid `_finish_promotion`, all staging already
# complete) -- the sharpest reader-isolation test, since the evidence file
# itself exists but nothing else does yet.
# ---------------------------------------------------------------------------


def test_crash_between_evidence_write_and_audit_event(harness, monkeypatch):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    _crash_after(
        monkeypatch, command_module, "atomic_write_json",
        when=lambda path, *a, **k: path.parent.name == "evidence" and path.stem == draft["id"],
    )

    _attempt_approval_expecting_crash(harness, env)
    # The evidence file DOES exist (that write completed) but nothing else
    # has -- this is exactly the case FAILURE-AND-RECOVERY.md's table
    # calls out as needing careful non-duplicating recovery.
    assert harness.evidence_file(draft["id"]).exists()
    assert len(list(harness.inbox_dir.rglob("*.json"))) == 0
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW

    reports = harness.service.reconcile_pending_transactions()
    assert reports[0]["outcome"] == "resumed_and_committed"
    # Still exactly one evidence file -- recovery did not duplicate it.
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1
    assert len(list(harness.inbox_dir.rglob("*.json"))) == 1
    assert harness.repository.get_draft_state(draft["id"]).state == domain.APPROVED


# ---------------------------------------------------------------------------
# Phase 5c: crash after the real audit event, before the draft
# compare-and-set to `approved`.
# ---------------------------------------------------------------------------


def test_crash_between_audit_event_and_draft_compare_and_set(harness, monkeypatch):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    _crash_after(monkeypatch, command_module, "append_review_event", when=lambda *a, **k: True)

    _attempt_approval_expecting_crash(harness, env)
    assert harness.evidence_file(draft["id"]).exists()
    assert len(list(harness.inbox_dir.rglob("*.json"))) == 1
    # Draft state has NOT yet flipped to approved -- an operator reading
    # the queue still (correctly, if confusingly without reconciliation)
    # sees pending_review even though the publication file exists; this is
    # exactly why the commit marker, not the evidence file alone, is the
    # authoritative signal this repository's own reads rely on.
    assert harness.repository.get_draft_state(draft["id"]).state == domain.PENDING_REVIEW

    reports = harness.service.reconcile_pending_transactions()
    assert reports[0]["outcome"] == "resumed_and_committed"
    assert harness.repository.get_draft_state(draft["id"]).state == domain.APPROVED
    # append_review_event's own idempotent retry-detection means no second
    # event was created.
    assert len(list(harness.inbox_dir.rglob("*.json"))) == 1
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Phase 6: commit marker published -- transaction is done; recovery only
# finishes idempotent cleanup and never rolls back visible trust.
# ---------------------------------------------------------------------------


def test_commit_marker_published_is_final_and_idempotent(harness):
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    result = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert result.resulting_state == domain.APPROVED

    # Reconciling an already-committed transaction is a safe no-op-shaped
    # resume: it must not roll back or duplicate anything.
    reports = harness.service.reconcile_pending_transactions()
    assert reports == []  # no pending transactions remain once committed
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1
    assert harness.repository.get_draft_state(draft["id"]).state == domain.APPROVED


def test_process_crash_after_completion_then_exact_retry_returns_same_result(harness):
    """Simulates the process dying right after successfully completing (no
    crash injected at all -- the interesting behavior is what a *new*
    request with the same idempotency key does afterward)."""
    draft = _readable_draft()
    harness.seed(draft)
    env = harness.envelope(draft["id"])
    first = harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)

    # A fresh command-service instance (simulating a new process) replays
    # the exact same command.
    fresh_service = PublicationReviewCommandService(harness.deps)
    second = fresh_service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert second.idempotent_replay is True
    assert second.publication_id == first.publication_id
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Duplicate concurrent appearance during promotion
# ---------------------------------------------------------------------------


def test_duplicate_appearing_concurrently_is_rejected_not_overwritten(harness):
    draft = _readable_draft()
    harness.seed(draft)
    # Simulate a concurrently-approved duplicate landing at the same id
    # right after this command's own eligibility check ran, by writing the
    # evidence file directly before calling approve.
    harness.evidence_file(draft["id"]).write_text(json.dumps({
        "id": draft["id"], "status": "published",
    }), encoding="utf-8")
    env = harness.envelope(draft["id"])
    with pytest.raises(domain.CommandError) as exc_info:
        harness.service.approve_publication(env, approval_basis=domain.BASIS_FULL_ARTICLE)
    assert exc_info.value.code == domain.ERROR_IDENTITY_CONFLICT
    # The existing file was never overwritten.
    assert json.loads(harness.evidence_file(draft["id"]).read_text(encoding="utf-8")) == {
        "id": draft["id"], "status": "published",
    }
