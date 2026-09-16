"""Validator-owned acceptance checks for Publication Review Command V1.

These checks use only tmp_path stores and exercise the public command boundary.
They intentionally do not add workflow behavior or call live/canonical stores.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.services import publication_review_domain as domain
from app.services.publication_review_command import PublicationReviewCommandService
from app.services.publication_review_repository import DurableReviewRepository
from tests.test_publication_review_command import Harness, _readable_draft


def _tree_digest(root):
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_approval_replay_after_service_reconstruction_is_idempotent(tmp_path):
    harness = Harness(tmp_path)
    draft = _readable_draft()
    harness.seed(draft)
    envelope = harness.envelope(draft["id"], idempotency_key="double-click")

    first = harness.service.approve_publication(envelope, approval_basis=domain.BASIS_FULL_ARTICLE)
    restarted_deps = replace(
        harness.deps,
        repository=DurableReviewRepository(harness.review_root),
    )
    restarted = PublicationReviewCommandService(restarted_deps)
    replay = restarted.approve_publication(envelope, approval_basis=domain.BASIS_FULL_ARTICLE)

    assert replay == replace(first, idempotent_replay=True)
    assert len(list((harness.data_dir / "evidence").glob("*.json"))) == 1
    assert len(restarted.decision_history(draft["id"])) == 1


@pytest.mark.parametrize("actor_id", ["ai-bot", "scheduler-service", "does-not-exist"])
def test_non_human_or_missing_actor_cannot_mutate_any_store(tmp_path, actor_id):
    harness = Harness(tmp_path)
    draft = _readable_draft()
    harness.seed(draft)
    before = (_tree_digest(harness.review_root), _tree_digest(harness.data_dir), _tree_digest(harness.inbox_dir))

    with pytest.raises(domain.CommandError):
        harness.service.approve_publication(
            harness.envelope(draft["id"], actor_id=actor_id, idempotency_key=f"actor-{actor_id}"),
            approval_basis=domain.BASIS_FULL_ARTICLE,
        )

    assert before == (_tree_digest(harness.review_root), _tree_digest(harness.data_dir), _tree_digest(harness.inbox_dir))


def test_stale_content_digest_fails_closed_without_publication(tmp_path):
    harness = Harness(tmp_path)
    draft = _readable_draft()
    harness.seed(draft)
    envelope = harness.envelope(draft["id"])
    harness.service.revise_publication_draft(
        harness.envelope(draft["id"], idempotency_key="revision"),
        patch={"summary": "Human-reviewed correction."},
    )
    before = _tree_digest(harness.data_dir)

    with pytest.raises(domain.CommandError) as error:
        harness.service.approve_publication(envelope, approval_basis=domain.BASIS_FULL_ARTICLE)

    assert error.value.code == domain.ERROR_STALE_REVIEW
    assert not harness.evidence_file(draft["id"]).exists()
    assert _tree_digest(harness.data_dir) == before


def test_approval_creates_only_one_publication_and_no_trusted_side_effects(tmp_path):
    harness = Harness(tmp_path)
    draft = _readable_draft()
    harness.seed(draft)
    result = harness.service.approve_publication(
        harness.envelope(draft["id"]), approval_basis=domain.BASIS_FULL_ARTICLE
    )
    record = harness.evidence_file(draft["id"]).read_text(encoding="utf-8")

    assert result.publication_id == draft["id"]
    assert record.count('"fact_ids": []') == 1
    assert record.count('"relationship_ids": []') == 1
    assert not list((harness.data_dir / "entities").glob("*.json"))
    assert not list((harness.data_dir / "facts").glob("*.json"))
    assert not list((harness.data_dir / "relationships").glob("*.json"))
    assert not list((harness.data_dir / "signals").glob("*.json"))
    assert not list((harness.data_dir / "assessments").glob("*.json"))
    assert not list((harness.data_dir / "recommendations").glob("*.json"))
