"""LineageQueryService (V2 Phase 2B.2).

Resolves the id-linkage fields every intelligence object (Signal,
Assessment, Recommendation) carries against the record it's linking to --
the mechanism that lets a reader walk the Recommendation -> Assessment/
Signal -> Facts -> Evidence chain (docs/v2/03-DOMAIN-MODEL.md's lineage
model) one level at a time, from any point in it. Not dependent on Jinja
or any presentation structure -- callers get back plain record lists.

Direction is not inferred beyond simple id-membership: a record is
"linked" because the source record's own *_ids field names it, nothing
more. This directly replaces three near-identical inline list-
comprehensions in app/main.py's signal_detail(), assessment_detail(), and
recommendation_detail() routes, which is genuine reuse (three real call
sites), not synthesis added merely for migration convenience.

Reverse lookups (citing Signal/Assessment for an Evidence id, citing
Assessment for a Signal id) scan the citing side's *_ids fields only.
When a request-scoped RequestCorpus is bound, membership indexes avoid
repeated full-list scans. Outside a request (CLI, unit fixtures) the
service falls through to repository list scans -- same semantics.
"""

from __future__ import annotations

from typing import Any


class LineageQueryService:
    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def resolve_linked_evidence(self, evidence_ids: list[str] | None) -> list[dict[str, Any]]:
        ids = set(evidence_ids or [])
        return [r for r in self._repos.evidence.list(status="published") if r["id"] in ids]

    def resolve_linked_facts(self, fact_ids: list[str] | None) -> list[dict[str, Any]]:
        ids = set(fact_ids or [])
        return [f for f in self._repos.facts.list() if f["id"] in ids]

    def resolve_linked_signals(self, signal_ids: list[str] | None) -> list[dict[str, Any]]:
        ids = set(signal_ids or [])
        return [s for s in self._repos.signals.list() if s["id"] in ids]

    def resolve_linked_assessments(self, assessment_ids: list[str] | None) -> list[dict[str, Any]]:
        ids = set(assessment_ids or [])
        return [a for a in self._repos.assessments.list() if a["id"] in ids]

    def resolve_assessments_citing_signal(self, signal_id: str) -> list[dict[str, Any]]:
        """Reverse lookup: Evidence/Signal/Assessment link in one
        direction only (the citing record names the cited one via its own
        *_ids field), so an Assessment that cites a Signal is found by
        scanning Assessment.signal_ids for this id -- there is no stored
        back-reference on the Signal itself to keep in sync."""
        from app.services.request_corpus import get_request_corpus

        corpus = get_request_corpus()
        if corpus is not None:
            return list(corpus.assessments_by_signal.get(signal_id, ()))
        return [a for a in self._repos.assessments.list() if signal_id in (a.get("signal_ids") or [])]

    def resolve_signals_citing_evidence(self, evidence_id: str) -> list[dict[str, Any]]:
        """Reverse of Signal.evidence_ids -- Signals that explicitly name
        this Evidence. Empty list when none cite it (sparse honesty)."""
        from app.services.request_corpus import get_request_corpus

        corpus = get_request_corpus()
        if corpus is not None:
            return list(corpus.signals_by_evidence.get(evidence_id, ()))
        return [
            s for s in self._repos.signals.list() if evidence_id in (s.get("evidence_ids") or [])
        ]

    def resolve_assessments_citing_evidence(self, evidence_id: str) -> list[dict[str, Any]]:
        """Reverse of Assessment.evidence_ids -- Assessments that explicitly
        name this Evidence. Does not infer via Signal intermediates."""
        from app.services.request_corpus import get_request_corpus

        corpus = get_request_corpus()
        if corpus is not None:
            return list(corpus.assessments_by_evidence.get(evidence_id, ()))
        return [
            a for a in self._repos.assessments.list() if evidence_id in (a.get("evidence_ids") or [])
        ]

    def resolve_linked_strategic_questions(self, sq_ids: list[str] | None) -> list[dict[str, Any]]:
        ids = set(sq_ids or [])
        return [sq for sq in self._repos.strategic_questions.list() if sq["id"] in ids]

    def resolve_linked_entities(
        self, entity_ids: list[str] | None, entities: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [entities[e] for e in (entity_ids or []) if e in entities]
