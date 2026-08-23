"""ReviewPublishService (V2 Phase 2B.3).

Extracts review/publish's persistence orchestration out of the HTTP route
handler (`app/main.py`'s `review_publish()`) into its own workflow
service, per this phase's explicit instruction: "Do not leave a large
multi-object transaction embedded directly in the route handler."

This service knows nothing about HTTP requests, redirects, or Jinja
templates -- it receives already-parsed, already-form-validated input
(`PublishRequest`) and returns a plain `PublishResult` the route
translates into a response. It receives its repository/unit-of-work
dependencies through `app.composition` (`get_repositories()`/
`get_unit_of_work()`), never instantiating a concrete JSON repository
itself.

## Why the Draft-lifecycle callables are injected, not imported

Drafts have no repository (Phase 2B.1 explicitly scoped only 9 object
types; Drafts live in `inbox/`, not `data/`) -- `get_draft()`/
`move_draft_attachments()`/`delete_draft()` stay defined in `app/main.py`
as documented filesystem exceptions. This module cannot import them
directly: `app/main.py` imports this module, so the reverse import would
be circular. The route passes its own current function references in
at call time instead -- this also means `unittest.mock`/`monkeypatch`
patches applied to `app.main.delete_draft` before a request are honored,
since the route looks the name up fresh from the module namespace on
every call rather than binding it once at import time.

## The attachment/rollback interaction this phase's audit found

`move_draft_attachments()` physically moves files out of `inbox/` before
the structured-data transaction begins (evidence attachments must be
known before the Evidence record can be schema-validated and created).
If a later step in the same publish attempt fails and the transaction
rolls back, those files must move back to `inbox/` too -- otherwise a
retry's own `move_draft_attachments()` call finds nothing to move (its
source directory is already empty) and silently produces an Evidence
record with no attachments, even though the original draft had some.
`restore_draft_attachments` (injected the same way) reverses the move on
rollback so a retry behaves exactly as if the failed attempt never
happened.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from app.repositories.base import DuplicateRecord
from app.services.review_events import EventAppendResult, append_review_event, remove_created_event

PUBLICATION_IDENTITY_FIELDS = (
    "title",
    "source_url",
    "source_id",
    "published_date",
    "source_type",
    "evidence_role",
    "discovered_item_id",
)


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def normalize_article_for_trust(article: Any) -> dict[str, Any] | None:
    if not isinstance(article, dict):
        return None
    normalized = deepcopy(article)
    paragraphs = []
    for offset, row in enumerate(normalized.get("paragraphs") or []):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        index = row.get("index")
        if not isinstance(index, int):
            index = offset
        paragraphs.append({"index": index, "text": text})
    if paragraphs:
        normalized["paragraphs"] = paragraphs
    elif "paragraphs" in normalized:
        del normalized["paragraphs"]
    return normalized


def trusted_publication_conflicts(existing: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    """Return human-readable identity conflicts between a trusted record and a draft.

    Summary, why_it_matters, tags, and berry/entity suggestions are not identity.
    A later human review of the same publication must not overwrite trusted data.
    """

    conflicts: list[str] = []
    existing_status = existing.get("status")
    existing_review = existing.get("review_state", existing_status)
    if existing_status != "published" or existing_review not in {None, "published"}:
        conflicts.append(
            f"existing record is {existing_status}/{existing_review}, not a trusted published publication"
        )
    for field_name in PUBLICATION_IDENTITY_FIELDS:
        left = _norm(existing.get(field_name))
        right = _norm(proposed.get(field_name))
        if left and right and left != right:
            conflicts.append(f"{field_name}: trusted={left!r} draft={right!r}")
    return conflicts


@dataclass
class PublishRequest:
    """Already-parsed, already-form-validated input for one publish
    attempt. Everything here is a plain value -- no Request, no Form, no
    template concerns."""

    draft: dict[str, Any]
    draft_id: str
    title: str
    source_type: str
    source_name: str
    source_url: str
    published_date: str | None
    captured_date: str
    summary: str
    why_it_matters: str
    tags: list[str]
    selected_berries: list[str]
    all_entity_names_by_type: dict[str, list[str]]
    facts_input: list[dict[str, str]]
    relationships_input: list[dict[str, Any]]
    priority: dict[str, dict[str, str]]
    strategic_question_text: list[str]
    reviewer: str
    existing_entity_ids: list[str] = field(default_factory=list)


@dataclass
class PublishResult:
    """Created and already-published are success outcomes. Conflict and
    schema errors are controlled failures. Never both success and errors."""

    evidence_id: str | None = None
    schema_errors: list[str] = field(default_factory=list)
    outcome: str = "created"
    conflicts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.outcome in {"created", "already_published"} and not self.schema_errors and not self.conflicts


class ReviewPublishService:
    def __init__(
        self,
        repositories: Any,
        unit_of_work_factory: Callable[[], Any],
        get_validator: Callable[[str], Any],
        unique_entity_id: Callable[[str, str, set[str]], str],
        append_unique: Callable[[list[str], str], list[str]],
        move_draft_attachments: Callable[[str, str, list[dict[str, str]]], list[dict[str, str]]],
        restore_draft_attachments: Callable[[str, str, list[dict[str, str]]], None],
        delete_draft: Callable[[str], None],
        review_events_inbox: Path | None = None,
    ) -> None:
        self._repos = repositories
        self._unit_of_work_factory = unit_of_work_factory
        self._get_validator = get_validator
        self._unique_entity_id = unique_entity_id
        self._append_unique = append_unique
        self._move_draft_attachments = move_draft_attachments
        self._restore_draft_attachments = restore_draft_attachments
        self._delete_draft = delete_draft
        self._review_events_inbox = review_events_inbox

    def publish(self, request: PublishRequest) -> PublishResult:
        # --- entity match-or-create -----------------------------------
        entities_idx = {e["id"]: e for e in self._repos.entities.list() if e.get("id")}
        by_name_type = {
            (e.get("name", "").strip().lower(), e.get("entity_type")): e for e in entities_idx.values()
        }
        existing_ids = set(entities_idx.keys())
        entity_ids: list[str] = []
        new_entity_ids: set[str] = set()
        name_to_id: dict[str, str] = {}
        entities_by_id: dict[str, dict[str, Any]] = deepcopy(entities_idx)

        missing_existing_ids = [value for value in request.existing_entity_ids if value not in entities_idx]
        if missing_existing_ids:
            return PublishResult(schema_errors=[
                "Linked entity IDs no longer resolve: " + ", ".join(sorted(missing_existing_ids))
            ])
        entity_ids.extend(request.existing_entity_ids)

        for entity_type, names in request.all_entity_names_by_type.items():
            for name in names:
                key = (name.strip().lower(), entity_type)
                existing = by_name_type.get(key)
                if existing:
                    name_to_id[name] = existing["id"]
                    entity_ids.append(existing["id"])
                    continue
                entity_id = self._unique_entity_id(entity_type, name, existing_ids)
                existing_ids.add(entity_id)
                new_entity = {
                    "id": entity_id,
                    "record_type": "entity",
                    "entity_type": entity_type,
                    "name": name,
                    "aliases": [],
                    "status": "unverified",
                    "description": "",
                    "roles": [],
                    "berry_ids": list(request.selected_berries),
                    "evidence_ids": [],
                    "fact_ids": [],
                    "relationship_ids": [],
                    "attributes": {},
                }
                by_name_type[key] = new_entity
                entities_by_id[entity_id] = new_entity
                new_entity_ids.add(entity_id)
                name_to_id[name] = entity_id
                entity_ids.append(entity_id)

        evidence_id = request.draft_id

        # --- Facts ------------------------------------------------------
        fact_ids: list[str] = []
        facts_to_save: list[dict[str, Any]] = []
        for i, fact_input in enumerate(request.facts_input, start=1):
            fact_id = f"fact-{evidence_id[3:]}-{i}"
            facts_to_save.append(
                {
                    "id": fact_id,
                    "record_type": "fact",
                    "statement": fact_input["statement"],
                    "classification": fact_input["classification"],
                    "confidence": fact_input["confidence"],
                    "status": "active",
                    "reviewer": request.reviewer,
                    "created_at": date.today().isoformat(),
                    "evidence_ids": [evidence_id],
                    "entity_ids": list(entity_ids),
                }
            )
            fact_ids.append(fact_id)

        # --- Relationships ------------------------------------------------
        relationship_ids: list[str] = []
        relationships_to_save: list[dict[str, Any]] = []
        for i, rel_input in enumerate(request.relationships_input, start=1):
            rel_id = f"rel-{evidence_id[3:]}-{i}"
            relationships_to_save.append(
                {
                    "id": rel_id,
                    "record_type": "relationship",
                    "subject_id": name_to_id[rel_input["subject"]],
                    "predicate": rel_input["predicate"],
                    "object_id": name_to_id[rel_input["object"]],
                    "status": "active",
                    "evidence_ids": [evidence_id],
                    "effective_date": rel_input["effective_date"],
                    "notes": "",
                }
            )
            relationship_ids.append(rel_id)

        # --- Strategic Questions ------------------------------------------
        strategic_questions = self._repos.strategic_questions.list()
        sq_ids: list[str] = []
        for text in request.strategic_question_text:
            needle = text.strip().lower()
            for sq in strategic_questions:
                if sq.get("id", "").lower() == needle or sq.get("title", "").lower() == needle:
                    sq_ids.append(sq["id"])
                    break

        # --- Evidence -------------------------------------------------
        entity_ids = list(dict.fromkeys(entity_ids))
        evidence_record = {
            "id": evidence_id,
            "record_type": "evidence",
            "status": "published",
            "source_type": request.source_type,
            "title": request.title,
            "source_name": request.source_name,
            "source_url": request.source_url,
            "published_date": request.published_date,
            "captured_date": request.captured_date,
            "summary": request.summary,
            "why_it_matters": request.why_it_matters,
            "submitted_by": request.draft.get("submitted_by", ""),
            "berry_ids": list(request.selected_berries),
            "geography_ids": [eid for eid in entity_ids if entities_by_id[eid]["entity_type"] == "geography"],
            "entity_ids": entity_ids,
            "fact_ids": fact_ids,
            "relationship_ids": relationship_ids,
            "strategic_question_ids": sq_ids,
            "tags": request.tags,
            "attachments": [],
            "priority": request.priority,
            "review_state": "published",
            "reviewed_by": request.reviewer,
            "reviewed_at": date.today().isoformat(),
        }

        # Intake drafts may carry optional, schema-supported publication
        # metadata that the general review form does not edit. Preserve it
        # through the same human-review transaction instead of dropping it.
        # This is format-neutral: legacy text drafts simply omit these keys.
        for field_name in (
            "source_id",
            "media_format",
            "transcript",
            "evidence_role",
            "parent_evidence_id",
            "artifact_locator",
            "extraction_provenance",
            "transcript_provenance",
            "transcript_excerpt",
            "discovered_item_id",
            "discovery_provenance",
            "publisher_description",
            "article",
            "relevance_tier",
            "does_not_prove",
        ):
            if field_name not in request.draft:
                continue
            value = deepcopy(request.draft[field_name])
            if field_name == "article":
                value = normalize_article_for_trust(value)
                if value is None:
                    continue
            evidence_record[field_name] = value

        existing_trusted = self._repos.evidence.get(evidence_id)
        if existing_trusted is not None:
            conflicts = trusted_publication_conflicts(existing_trusted, evidence_record)
            if conflicts:
                return PublishResult(
                    evidence_id=evidence_id,
                    outcome="conflict",
                    conflicts=conflicts,
                    schema_errors=[],
                )
            self._delete_draft(request.draft_id)
            return PublishResult(evidence_id=evidence_id, outcome="already_published")

        if request.draft.get("evidence_role") == "atomic_evidence":
            original_statement = request.draft.get("summary") or request.draft.get("title") or ""
            evidence_record["review_outcome"] = {
                "decision": "approved",
                "edited_before_approval": (
                    request.title != request.draft.get("title")
                    or request.summary != request.draft.get("summary")
                ),
                "original_normalized_statement": original_statement,
            }

        schema_errors = [e.message for e in self._get_validator("evidence.schema.json").iter_errors(evidence_record)]
        if schema_errors:
            return PublishResult(schema_errors=schema_errors)

        # All validation passed: link entities to this evidence/facts/
        # relationships, then persist everything together so a failed
        # publish leaves no orphans.
        moved_attachments = self._move_draft_attachments(
            request.draft_id, evidence_id, request.draft.get("attachments", [])
        )
        evidence_record["attachments"] = moved_attachments
        new_entity_ids_frozen = frozenset(new_entity_ids)
        uow = self._unit_of_work_factory()
        review_event: EventAppendResult | None = None
        try:
            with uow:
                for entity_id in set(entity_ids):
                    entity = entities_by_id[entity_id]
                    entity["evidence_ids"] = self._append_unique(entity.get("evidence_ids", []), evidence_id)
                    entity["fact_ids"] = list(dict.fromkeys([*entity.get("fact_ids", []), *fact_ids]))
                    related_rel_ids = [
                        r["id"]
                        for r in relationships_to_save
                        if r["subject_id"] == entity_id or r["object_id"] == entity_id
                    ]
                    entity["relationship_ids"] = list(
                        dict.fromkeys([*entity.get("relationship_ids", []), *related_rel_ids])
                    )
                    if entity_id in new_entity_ids_frozen:
                        uow.entities.create(entity)
                    else:
                        uow.entities.update(entity_id, entity)
                for fact in facts_to_save:
                    uow.facts.create(fact)
                for relationship in relationships_to_save:
                    uow.relationships.create(relationship)
                uow.evidence.create(evidence_record)
                if self._review_events_inbox is not None:
                    source = self._repos.sources.get(request.draft.get("source_id")) if request.draft.get("source_id") else None
                    review_event = append_review_event(
                        self._review_events_inbox,
                        workflow="atomic_evidence_review" if request.draft.get("evidence_role") == "atomic_evidence" else "publication_review",
                        object_id=request.draft_id,
                        object_type="atomic_evidence_draft" if request.draft.get("evidence_role") == "atomic_evidence" else "publication_draft",
                        action="publish", prior_state=str(request.draft.get("review_state") or request.draft.get("status") or "pending"),
                        new_state="published", actor=request.reviewer, subject=request.draft, source=source,
                    )
                # Draft removal is the final publish operation. Keeping it
                # inside the unit of work means an unlink failure
                # compensates every structured write and leaves the draft
                # safely retryable instead of stranded beside a committed
                # Evidence record with the same deterministic id.
                self._delete_draft(request.draft_id)
        except DuplicateRecord:
            if review_event:
                remove_created_event(review_event)
            if moved_attachments:
                self._restore_draft_attachments(request.draft_id, evidence_id, moved_attachments)
            raced = self._repos.evidence.get(evidence_id)
            if raced is None:
                raise
            conflicts = trusted_publication_conflicts(raced, evidence_record)
            if conflicts:
                return PublishResult(
                    evidence_id=evidence_id,
                    outcome="conflict",
                    conflicts=conflicts,
                )
            self._delete_draft(request.draft_id)
            return PublishResult(evidence_id=evidence_id, outcome="already_published")
        except Exception:
            # The structured-data transaction rolled back (or never
            # committed) -- undo the one side effect the unit of work
            # cannot see or compensate itself: the attachment files moved
            # out of inbox/ before the transaction began. Without this, a
            # retry's own move_draft_attachments() call would find its
            # source directory already empty and silently publish with no
            # attachments.
            if moved_attachments:
                self._restore_draft_attachments(request.draft_id, evidence_id, moved_attachments)
            if review_event:
                remove_created_event(review_event)
            raise

        return PublishResult(evidence_id=evidence_id, outcome="created")
