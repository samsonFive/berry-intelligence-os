"""Publication Review Command Service V1 -- development inbox import adapter.

Provides exactly one explicit, single-item import path from a gitignored
`inbox/evidence/<id>.json`-shaped draft into the durable review repository
(`app.services.publication_review_repository`). This module never scans a
directory, never bulk-imports, and is never called automatically -- an
operator or test names one draft dict explicitly, every time.

Per this mission's own scope: "Do not import current live records during
this mission." Nothing in this module is called against real `inbox/` or
`data/` in this codebase change; it exists so a future, explicitly
authorized migration (or a test fixture built from a realistic shape) has
a safe, tested entry point rather than ad hoc code duplicating the digest/
eligibility rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.services import publication_review_domain as domain
from app.services.publication_review_repository import DraftState, DurableReviewRepository


@dataclass(frozen=True)
class ImportOutcome:
    draft_id: str
    created: bool
    provenance_drifted: bool
    eligibility: domain.EligibilityResult


def import_inbox_draft(
    repository: DurableReviewRepository,
    inbox_draft: dict[str, Any],
    *,
    resolvable_entity_ids: frozenset[str] = frozenset(),
    now: datetime | None = None,
) -> ImportOutcome:
    """Import exactly one already-loaded inbox draft dict as a durable
    `pending_review` draft state. `inbox_draft` must already be a plain
    dict (the caller reads the file; this function never touches a
    filesystem path itself, local `inbox/` included).

    If a durable draft with the same id already exists, this function
    never silently overwrites it -- it recomputes the current provenance
    digest from `inbox_draft` and compares it against the stored one,
    reporting `provenance_drifted=True` rather than mutating anything.
    Reconciling a drift is a deliberate `revise_publication_draft`/
    `submit_publication_correction` command, not an import side effect."""
    draft_id = str(inbox_draft.get("id") or "")
    if not draft_id:
        raise ValueError("inbox_draft has no 'id' field")

    eligibility = domain.check_eligibility(inbox_draft, resolvable_entity_ids=resolvable_entity_ids)
    content_digest = domain.compute_review_content_digest(inbox_draft, eligibility=eligibility)
    provenance_digest = domain.compute_provenance_digest(inbox_draft)

    existing = repository.get_draft_state(draft_id)
    if existing is not None:
        drifted = existing.provenance_digest != provenance_digest
        return ImportOutcome(draft_id=draft_id, created=False, provenance_drifted=drifted, eligibility=eligibility)

    timestamp = (now or datetime.now(UTC)).isoformat(timespec="microseconds")
    draft_state = DraftState(
        id=draft_id,
        version=1,
        state=domain.PENDING_REVIEW,
        draft=dict(inbox_draft),
        content_digest=content_digest,
        provenance_digest=provenance_digest,
        content_class=eligibility.content_class,
        acquisition_classification=eligibility.body_state,
        created_at=timestamp,
        updated_at=timestamp,
    )
    repository.create_draft_state(draft_state)
    return ImportOutcome(draft_id=draft_id, created=True, provenance_drifted=False, eligibility=eligibility)
