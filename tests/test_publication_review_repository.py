"""Publication Review Command Service V1 -- durable repository tests (Slice 2).

Uses only `tmp_path`-rooted `DurableReviewRepository` instances. Never
touches the real `inbox/` or `data/`.
"""

from __future__ import annotations

import time

import pytest

from app.services.publication_review_repository import (
    DraftNotFound,
    DraftState,
    DurableReviewRepository,
    LockUnavailable,
    StaleVersion,
    resolve_review_state_dir,
)


def _draft_state(draft_id="d1", version=1, state="pending_review") -> DraftState:
    return DraftState(
        id=draft_id, version=version, state=state, draft={"id": draft_id, "title": "t"},
        content_digest="digest-a", provenance_digest="prov-a", content_class="FULL_ARTICLE",
        acquisition_classification="body_available", created_at="2026-09-16T00:00:00+00:00",
        updated_at="2026-09-16T00:00:00+00:00",
    )


def test_create_and_get_round_trips(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.create_draft_state(_draft_state())
    fetched = repo.get_draft_state("d1")
    assert fetched is not None
    assert fetched.version == 1
    assert fetched.state == "pending_review"


def test_get_missing_draft_returns_none(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    assert repo.get_draft_state("nope") is None


def test_creating_a_duplicate_draft_id_raises(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.create_draft_state(_draft_state())
    with pytest.raises(Exception):
        repo.create_draft_state(_draft_state())


# ---------------------------------------------------------------------------
# Durability across "restart" / "new checkout" -- the candidate-pack finding
# ---------------------------------------------------------------------------


def test_state_survives_a_fresh_repository_instance_pointed_at_the_same_root(tmp_path):
    """A brand-new DurableReviewRepository object simulates a new process
    (restart) or a new worker/checkout reading the same persistent root --
    exactly the durability property `inbox/` (gitignored, worktree-local)
    could not provide, per the candidate pack's own finding."""
    root = tmp_path / "review_state"
    first = DurableReviewRepository(root)
    first.create_draft_state(_draft_state())

    second = DurableReviewRepository(root)  # a fresh instance, no shared Python state
    fetched = second.get_draft_state("d1")
    assert fetched is not None
    assert fetched.version == 1


def test_deleting_a_local_inbox_projection_does_not_delete_durable_work(tmp_path):
    """The durable root and a separate local inbox/ directory are entirely
    independent -- removing the latter must never affect the former."""
    root = tmp_path / "review_state"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "evidence").mkdir()
    (inbox / "evidence" / "d1.json").write_text("{}", encoding="utf-8")

    repo = DurableReviewRepository(root)
    repo.create_draft_state(_draft_state())

    import shutil
    shutil.rmtree(inbox)

    assert repo.get_draft_state("d1") is not None


def test_local_dev_default_is_repo_relative_and_distinct_from_inbox(tmp_path, monkeypatch):
    monkeypatch.delenv("BIOS_REVIEW_STATE_DIR", raising=False)
    monkeypatch.delenv("BIOS_RUNTIME_DIR", raising=False)
    resolved = resolve_review_state_dir(tmp_path)
    assert resolved == tmp_path / "review_state"
    assert resolved.name != "inbox"


def test_runtime_dir_env_var_relocates_the_review_state_root(tmp_path, monkeypatch):
    persistent = tmp_path / "persistent-mount"
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(persistent))
    monkeypatch.delenv("BIOS_REVIEW_STATE_DIR", raising=False)
    resolved = resolve_review_state_dir(tmp_path)
    assert resolved == persistent / "review_state"


def test_explicit_review_state_dir_env_var_wins_over_runtime_dir(tmp_path, monkeypatch):
    explicit = tmp_path / "explicit-review-root"
    monkeypatch.setenv("BIOS_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("BIOS_REVIEW_STATE_DIR", str(explicit))
    resolved = resolve_review_state_dir(tmp_path)
    assert resolved == explicit


# ---------------------------------------------------------------------------
# Optimistic concurrency: compare-and-set
# ---------------------------------------------------------------------------


def test_compare_and_set_with_correct_version_succeeds(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.create_draft_state(_draft_state())

    def _bump(current):
        current.version += 1
        current.state = "approved"
        return current

    updated = repo.compare_and_set("d1", 1, _bump)
    assert updated.version == 2
    assert updated.state == "approved"


def test_compare_and_set_with_stale_version_raises_and_writes_nothing(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.create_draft_state(_draft_state())

    def _bump(current):
        current.version += 1
        return current

    with pytest.raises(StaleVersion):
        repo.compare_and_set("d1", 99, _bump)
    # No mutation occurred.
    assert repo.get_draft_state("d1").version == 1


def test_compare_and_set_on_missing_draft_raises_draft_not_found(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    with pytest.raises(DraftNotFound):
        repo.compare_and_set("nope", 1, lambda s: s)


def test_compare_and_set_archives_the_prior_version(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.create_draft_state(_draft_state())
    repo.compare_and_set("d1", 1, lambda s: (setattr(s, "version", 2), s)[1])
    archive_dir = tmp_path / "review_state" / "drafts_archive" / "d1"
    assert archive_dir.is_dir()
    assert len(list(archive_dir.glob("*.json"))) == 1


# ---------------------------------------------------------------------------
# Per-draft locking
# ---------------------------------------------------------------------------


def test_lock_is_exclusive_within_the_process(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    with repo.lock_draft("d1"):
        with pytest.raises(LockUnavailable):
            with repo.lock_draft("d1", timeout_seconds=0.05):
                pass


def test_lock_is_released_after_the_context_exits(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    with repo.lock_draft("d1"):
        pass
    with repo.lock_draft("d1", timeout_seconds=0.05):
        pass  # must not raise -- lock was released


def test_stale_lock_is_reclaimed_after_the_staleness_window(tmp_path, monkeypatch):
    from app.services import publication_review_repository as module

    monkeypatch.setattr(module, "LOCK_STALE_SECONDS", 0.05)
    repo = DurableReviewRepository(tmp_path / "review_state")
    lock_path = repo._lock_path("d1")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("{}", encoding="utf-8")
    old_time = time.time() - 10
    import os

    os.utime(lock_path, (old_time, old_time))
    with repo.lock_draft("d1", timeout_seconds=1.0):
        pass  # succeeds because the stale lock was reclaimed


def test_locks_for_different_drafts_do_not_contend(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    with repo.lock_draft("d1"):
        with repo.lock_draft("d2", timeout_seconds=0.05):
            pass  # different draft id, no contention


# ---------------------------------------------------------------------------
# Idempotency receipts
# ---------------------------------------------------------------------------


def test_idempotency_receipt_round_trips(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    assert repo.get_idempotency_receipt("alice", "key-1") is None
    repo.put_idempotency_receipt("alice", "key-1", payload_hash="h1", result={"ok": True})
    receipt = repo.get_idempotency_receipt("alice", "key-1")
    assert receipt["payload_hash"] == "h1"
    assert receipt["result"] == {"ok": True}


def test_idempotency_receipts_are_scoped_per_actor(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.put_idempotency_receipt("alice", "shared-key", payload_hash="h1", result={"who": "alice"})
    repo.put_idempotency_receipt("bob", "shared-key", payload_hash="h2", result={"who": "bob"})
    assert repo.get_idempotency_receipt("alice", "shared-key")["result"]["who"] == "alice"
    assert repo.get_idempotency_receipt("bob", "shared-key")["result"]["who"] == "bob"


# ---------------------------------------------------------------------------
# Staged promotion journal
# ---------------------------------------------------------------------------


def test_journal_phase_round_trips(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.write_journal_phase("d1", "txn-1", "intent", {"a": 1})
    assert repo.read_journal_phase("d1", "txn-1", "intent") == {"a": 1}
    assert repo.read_journal_phase("d1", "txn-1", "commit_marker") is None


def test_journal_phases_present_reflects_exactly_what_was_written(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.write_journal_phase("d1", "txn-1", "intent", {})
    repo.write_journal_phase("d1", "txn-1", "staged_publication", {})
    assert repo.journal_phases_present("d1", "txn-1") == {"intent", "staged_publication"}


def test_pending_transactions_excludes_committed_ones(tmp_path):
    repo = DurableReviewRepository(tmp_path / "review_state")
    repo.write_journal_phase("d1", "txn-1", "intent", {})
    repo.write_journal_phase("d2", "txn-2", "intent", {})
    repo.write_journal_phase("d2", "txn-2", "commit_marker", {})
    pending = repo.pending_transactions()
    assert ("d1", "txn-1") in pending
    assert ("d2", "txn-2") not in pending
