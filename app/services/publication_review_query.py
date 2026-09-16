"""Publication Review Durable Read Model V1 -- read/query seam (read-only).

Translates `app.services.publication_review_repository.DraftState` records
into the queue, detail, status, decision-history, and correction-history
shapes a future publication-review UI needs. This module never mutates
the durable repository, never calls
`app.services.publication_review_command.PublicationReviewCommandService`'s
decision methods, and never calls `ReviewPublishService.publish()`.

Design notes (see `artifacts/publication-review-durable-read-model-v1/`
for the full rationale):

- Reuses `app.services.publication_review_domain`'s own eligibility,
  transition, and identity functions verbatim -- this module adds no
  second state machine, no second content classifier, no second
  duplicate-detection rule. "Do not create a second competing review
  contract" is satisfied by projecting the *existing* domain/repository
  contract, not inventing a new one.
- Full acquired article/transcript bodies are never included in the
  standard queue/detail views. `hydrated_excerpt()` is a small, separately
  named function returning a bounded excerpt only -- matching the
  contract's own "a separately authorized content locator or hydrated
  body" language (`COMMAND-CONTRACTS.md`'s `get_publication_review`
  description) and this mission's own "does not expose full acquired
  article bodies" requirement literally, for every view this module
  produces.
- Staged, uncommitted promotion transactions are surfaced honestly
  (`promotion_status()`) and are never reported as an approved/committed
  state -- a draft's own `DraftState.state` is the only field this module
  ever calls "the review state," and it is read as-is from durable
  storage, never inferred from journal presence alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol

from app.services import publication_review_domain as domain
from app.services.publication_review_repository import DraftState, DurableReviewRepository

EXCERPT_MAX_CHARS = 500

# The subset of a decision-history entry this module ever serializes.
# Anything else a future field addition puts on an event (e.g. a raw
# idempotency key) is deliberately excluded -- the "actor redaction /
# serialization boundary" this mission's own test list names.
_DECISION_EVENT_FIELDS = (
    "command", "actor_id", "occurred_at", "reason_category", "comment",
    "resulting_state", "resulting_version", "event_id",
)

# Commands that represent a correction-cycle step, for correction_history_view().
_CORRECTION_COMMANDS = frozenset({domain.CMD_REQUEST_CORRECTION, domain.CMD_SUBMIT_CORRECTION})


class EvidenceReaderPort(Protocol):
    """Optional dependency used only to *verify* a stored publication
    binding still resolves -- never to fetch or expose its body. Passing
    `None` to any function below simply skips verification; the read
    model never treats an unverifiable binding as false, only as
    unverified."""

    def get(self, record_id: str) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# Serialization boundaries
# ---------------------------------------------------------------------------


def _serialize_decision_event(event: dict[str, Any]) -> dict[str, Any]:
    """Whitelist exactly the fields a reader may see for one decision-
    history entry. `actor_id` is passed through as-is (it is already an
    opaque identity string in this codebase, never a credential or
    session token) but nothing beyond the named fields ever crosses this
    boundary, even if a future write path adds a new key to the stored
    event."""
    return {field_name: event.get(field_name) for field_name in _DECISION_EVENT_FIELDS}


def _parse_supersession(reason_category: str | None) -> dict[str, str] | None:
    """`supersede_publication_duplicate`'s own reason_category is written
    as `survivor=<id>:<identity_basis>` (see
    `PublicationReviewCommandService.supersede_publication_duplicate`).
    Parsed here, once, rather than asking every caller to know that
    encoding."""
    if not reason_category or not reason_category.startswith("survivor="):
        return None
    remainder = reason_category[len("survivor="):]
    survivor_id, _, identity_basis = remainder.partition(":")
    return {"survivor_id": survivor_id, "identity_basis": identity_basis or "unknown"}


def _is_legacy_import(draft_state: DraftState) -> bool:
    """Best-effort signal that this durable record originated from
    `publication_review_migration.import_inbox_draft()` rather than a
    record created natively through this contract: an inbox-shaped draft
    still carries its original `record_type`/`status`/`review_state`
    fields (`evidence`/`draft`/`in_review`) verbatim inside `draft`, and a
    freshly-imported record has never had a decision applied. Both
    conditions must hold -- an old import that has since been decided is
    no longer meaningfully "legacy," it is simply a normal reviewed
    record with imported provenance."""
    inner = draft_state.draft
    looks_inbox_shaped = (
        inner.get("record_type") == "evidence"
        and inner.get("status") == "draft"
        and inner.get("review_state") == "in_review"
    )
    return looks_inbox_shaped and not draft_state.decision_history


# ---------------------------------------------------------------------------
# Promotion/transaction visibility -- never report staged as committed
# ---------------------------------------------------------------------------


def promotion_status(repository: DurableReviewRepository, draft_id: str) -> dict[str, Any]:
    """Whether an approval transaction for this draft is mid-flight,
    resumable, or absent -- read directly from the journal, never
    inferred from `DraftState.state` alone. A transaction whose journal
    has every staged phase but no `commit_marker` is real, durable,
    *uncommitted* work: this function calls it `resumable`, never
    `approved`, no matter how complete the staging looks."""
    pending = [txn for (did, txn) in repository.pending_transactions() if did == draft_id]
    transactions = []
    for transaction_id in pending:
        phases = repository.journal_phases_present(draft_id, transaction_id)
        resumable = {"staged_publication", "staged_decision", "staged_event"} <= phases
        transactions.append({
            "transaction_id": transaction_id,
            "phases_present": sorted(phases),
            "resumable": resumable,
            "committed": False,  # by construction: pending_transactions() excludes committed ones
        })
    return {
        "has_pending_transaction": bool(transactions),
        "pending_transactions": transactions,
    }


# ---------------------------------------------------------------------------
# Queue view
# ---------------------------------------------------------------------------


def queue_item_view(
    draft_state: DraftState, *, repository: DurableReviewRepository,
) -> dict[str, Any]:
    """One body-free queue row. Never includes `draft["article"]`/
    `draft["transcript"]` paragraph/segment text -- only the already-
    computed content classification."""
    inner = draft_state.draft
    eligibility = domain.check_eligibility(inner)
    promotion = promotion_status(repository, draft_state.id)
    return {
        "draft_id": draft_state.id,
        "id": draft_state.id,
        "title": inner.get("title") or draft_state.id,
        "source_id": inner.get("source_id"),
        "source_name": inner.get("source_name") or inner.get("source_id") or "Unknown source",
        "publication_date": inner.get("published_date"),
        "captured_at": inner.get("captured_date"),
        "review_state": draft_state.state,
        "version": draft_state.version,
        "review_version": draft_state.version,
        "created_at": draft_state.created_at,
        "updated_at": draft_state.updated_at,
        "content_class": draft_state.content_class,
        "acquisition_classification": draft_state.acquisition_classification,
        "eligibility_result": eligibility.result,
        "warnings": list(eligibility.warnings),
        "blockers": list(eligibility.blockers),
        "duplicate_of": eligibility.duplicate_of,
        "permitted_commands": list(domain.permitted_commands(draft_state.state)),
        "has_pending_transaction": promotion["has_pending_transaction"],
        "is_legacy_import": _is_legacy_import(draft_state),
        "publication_id": (draft_state.publication_binding or {}).get("publication_id"),
    }


@dataclass(frozen=True)
class QueuePage:
    items: tuple[dict[str, Any], ...]
    total_matching: int
    next_cursor: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "items": list(self.items),
            "total_matching": self.total_matching,
            "next_cursor": self.next_cursor,
        }


def _sort_key(draft_state: DraftState) -> tuple[str, str]:
    """Deterministic, stable ordering: most recently updated first, id as
    a tiebreaker so two records with an identical timestamp never
    reorder between reads."""
    return (draft_state.updated_at, draft_state.id)


def list_queue(
    repository: DurableReviewRepository,
    *,
    state: str | None = None,
    content_class: str | None = None,
    page_size: int = 50,
    cursor: str | None = None,
) -> QueuePage:
    """Stable-ordered, filterable, paginated queue -- the seam a future
    `GET /api/publication-reviews` route would call directly. `cursor` is
    an opaque `"<updated_at>\x1f<id>"` continuation token; passing back a
    prior page's `next_cursor` resumes exactly where it left off even if
    new records were added in between, because the sort key is stable and
    the cursor is a real position in it, not an offset count."""
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    rows = repository.list_draft_states(state=state)
    if content_class is not None:
        rows = [row for row in rows if row.content_class == content_class]
    rows.sort(key=_sort_key, reverse=True)

    start_index = 0
    if cursor:
        cursor_updated_at, _, cursor_id = cursor.partition("\x1f")
        for index, row in enumerate(rows):
            if (row.updated_at, row.id) == (cursor_updated_at, cursor_id):
                start_index = index + 1
                break

    page_rows = rows[start_index:start_index + page_size]
    next_cursor = None
    if start_index + page_size < len(rows) and page_rows:
        last = page_rows[-1]
        next_cursor = f"{last.updated_at}\x1f{last.id}"

    items = tuple(queue_item_view(row, repository=repository) for row in page_rows)
    return QueuePage(items=items, total_matching=len(rows), next_cursor=next_cursor)


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------


def decision_history_view(draft_state: DraftState) -> list[dict[str, Any]]:
    """The full append-only decision history, redacted per
    `_serialize_decision_event`, in the order it was recorded (oldest
    first -- the same order `DraftState.decision_history` itself already
    guarantees, since every command appends to the end)."""
    return [_serialize_decision_event(event) for event in draft_state.decision_history]


def correction_history_view(draft_state: DraftState) -> list[dict[str, Any]]:
    """Only the correction-cycle steps (`request_publication_correction`/
    `submit_publication_correction`) from the full decision history --
    the "correction requests/submissions" this mission's own scope names
    as a distinct required shape, not merely folded into the generic
    history."""
    return [
        _serialize_decision_event(event) for event in draft_state.decision_history
        if event.get("command") in _CORRECTION_COMMANDS
    ]


def hydrated_excerpt(draft_state: DraftState) -> dict[str, Any]:
    """A bounded, non-full-body excerpt only -- never the complete
    acquired article/transcript text. Matches the contract's own
    recommended default ("public metadata plus an approved excerpt/link;
    full body redistribution requires a separate legal/product
    decision") and this mission's explicit "does not expose full acquired
    article bodies" requirement, applied here to every reader of this
    read model, not only the public static build. A future,
    separately-authorized reviewer-detail surface that genuinely needs
    the complete text should read it directly from the durable
    repository's own `DraftState.draft`, not through this function."""
    inner = draft_state.draft
    article = inner.get("article") if isinstance(inner.get("article"), dict) else {}
    transcript = inner.get("transcript") if isinstance(inner.get("transcript"), dict) else {}

    full_text = None
    kind = None
    if article.get("paragraphs"):
        full_text = "\n\n".join(
            str(p.get("text") or "") for p in article["paragraphs"] if isinstance(p, dict)
        )
        kind = "article"
    elif transcript.get("segments"):
        full_text = "\n\n".join(
            str(s.get("text") or "") for s in transcript["segments"] if isinstance(s, dict)
        )
        kind = "transcript"

    if not full_text:
        return {"kind": None, "excerpt": None, "word_count": 0, "truncated": False, "full_body_available": False}

    excerpt = full_text[:EXCERPT_MAX_CHARS]
    return {
        "kind": kind,
        "excerpt": excerpt,
        "word_count": len(full_text.split()),
        "truncated": len(full_text) > EXCERPT_MAX_CHARS,
        "full_body_available": True,
    }


def get_detail(
    repository: DurableReviewRepository, draft_id: str, *, evidence_reader: EvidenceReaderPort | None = None,
) -> dict[str, Any] | None:
    """The full detail view. Returns `None` if no durable draft exists at
    this id -- callers must not distinguish "never existed" from "existed
    but was purged" beyond that; this module keeps no tombstone record of
    its own (the durable repository's own archive under
    `drafts_archive/<id>/` is the append-only history of a *known*
    draft's prior versions, not a record of ids that never existed)."""
    draft_state = repository.get_draft_state(draft_id)
    if draft_state is None:
        return None

    inner = draft_state.draft
    eligibility = domain.check_eligibility(inner)
    promotion = promotion_status(repository, draft_id)
    publication_binding = draft_state.publication_binding
    publication_verified: bool | None = None
    if publication_binding and evidence_reader is not None:
        publication_verified = evidence_reader.get(publication_binding["publication_id"]) is not None

    supersession = None
    if draft_state.state == domain.SUPERSEDED_DUPLICATE and draft_state.decision_history:
        supersession = _parse_supersession(draft_state.decision_history[-1].get("reason_category"))

    return {
        **queue_item_view(draft_state, repository=repository),
        "source_url": inner.get("source_url"),
        "source_type": inner.get("source_type"),
        "media_format": inner.get("media_format"),
        "summary": inner.get("summary"),
        "why_it_matters": inner.get("why_it_matters"),
        "entity_ids": list(inner.get("entity_ids") or []),
        "berry_ids": list(inner.get("berry_ids") or []),
        "geography_ids": list(inner.get("geography_ids") or []),
        "content_digest": draft_state.content_digest,
        "provenance_digest": draft_state.provenance_digest,
        "review_content_digest": draft_state.content_digest,
        "decision_history": decision_history_view(draft_state),
        "correction_history": correction_history_view(draft_state),
        "publication_binding": publication_binding,
        "publication_verified": publication_verified,
        "supersession": supersession,
        "promotion_status": promotion,
        "excerpt": hydrated_excerpt(draft_state),
        "ai_enrichment_present": bool(inner.get("ai_enrichment")),
    }


# ---------------------------------------------------------------------------
# Status summary
# ---------------------------------------------------------------------------


def status_summary(repository: DurableReviewRepository) -> dict[str, Any]:
    rows = repository.list_draft_states()
    counts: dict[str, int] = {name: 0 for name in domain.REVIEW_STATES}
    pending_transactions = 0
    for row in rows:
        counts[row.state] = counts.get(row.state, 0) + 1
        if promotion_status(repository, row.id)["has_pending_transaction"]:
            pending_transactions += 1
    return {
        "total": len(rows),
        "by_state": counts,
        "drafts_with_pending_transaction": pending_transactions,
    }


# ---------------------------------------------------------------------------
# Read-only-UI compatibility alias layer
#
# `feature/publication-review-readonly-ui-v1` (frozen, inspected but never
# imported or merged here) defines `project_queue_item()`/`project_detail()`
# in app/services/publication_review_readonly.py, expecting a generic
# "draft" dict shaped by a superset of field-name guesses (`queue_state`
# or `status`, `draft_id` or `id`, `version` or `review_version`, etc.).
# This function derives, from this module's own canonical view, a dict
# using exactly the field names that adapter already reads first --
# it does not import or depend on that file (it is on an unmerged branch),
# and it changes nothing about this module's own canonical shape above;
# it is a pure, additive projection for later wiring convenience. See
# artifacts/publication-review-durable-read-model-v1/CONTRACT-MAPPING.md
# for the exact field-by-field mapping and every documented gap.
# ---------------------------------------------------------------------------


def to_readonly_ui_compatible(view: dict[str, Any]) -> dict[str, Any]:
    """Given a `queue_item_view()` or `get_detail()` result, return a dict
    using the field names `publication_review_readonly.py`'s own
    `project_queue_item()`/`project_detail()` read first (`queue_state`,
    `draft_id`, `version`, `duplicate_of`, `entity_ids`, `article`,
    `transcript`, `source_completeness`) -- never the full body, per this
    module's own rule."""
    compatible = dict(view)
    compatible["queue_state"] = view.get("review_state")
    compatible["draft_id"] = view.get("draft_id") or view.get("id")
    compatible["version"] = view.get("version")
    compatible["headline"] = view.get("title")
    compatible["published_date"] = view.get("publication_date")
    compatible["captured_date"] = view.get("captured_at")
    compatible["source_completeness"] = {"class": view.get("content_class")}
    if "provenance_warnings" not in compatible:
        compatible["provenance_warnings"] = [
            {"code": code, "message": code.replace("_", " ").capitalize() + ".", "level": "warn"}
            for code in view.get("warnings", [])
        ]
    if "blocking_warnings" not in compatible:
        compatible["blocking_warnings"] = [
            {"code": code, "message": code.replace("_", " ").capitalize() + ".", "level": "block"}
            for code in view.get("blockers", [])
        ]
    return compatible
