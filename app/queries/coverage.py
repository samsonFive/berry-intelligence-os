"""CoverageQueryService (V2 Phase 2B.2).

Domain-neutral coverage calculations only: how many records of each kind
exist, broken down by a caller-supplied classification (source type,
confidence, dispute status). This service never turns a count into a
ranking or a "who's ahead" comparison -- that judgment, if made at all, is
a Berries domain-service concern (see app/services/berries/landscape.py's
landscape_evidence_coverage(), which adds Berries-specific thin-coverage
labeling on top of these domain-neutral numbers).
"""

from __future__ import annotations

from collections import Counter
from typing import Any


class CoverageQueryService:
    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def evidence_source_breakdown(
        self, evidence: list[dict[str, Any]], primary_source_types: set[str]
    ) -> tuple[Counter, int]:
        source_type_counts = Counter(r.get("source_type") for r in evidence)
        primary_count = sum(c for t, c in source_type_counts.items() if t in primary_source_types)
        return source_type_counts, primary_count

    def fact_confidence_and_disputes(self, entity_ids: set[str]) -> tuple[Counter, list[dict[str, Any]]]:
        relevant_facts = [f for f in self._repos.facts.list() if entity_ids & set(f.get("entity_ids") or [])]
        confidence_counts = Counter(f.get("confidence") for f in relevant_facts)
        disputed_facts = [f for f in relevant_facts if f.get("status") == "disputed"]
        return confidence_counts, disputed_facts

    def disputed_relationships(self, entity_ids: set[str]) -> list[dict[str, Any]]:
        relevant_rels = [
            r
            for r in self._repos.relationships.list()
            if r.get("subject_id") in entity_ids or r.get("object_id") in entity_ids
        ]
        return [r for r in relevant_rels if r.get("status") == "disputed"]

    def active_strategic_questions(self) -> list[dict[str, Any]]:
        return [sq for sq in self._repos.strategic_questions.list() if sq.get("status") == "active"]
