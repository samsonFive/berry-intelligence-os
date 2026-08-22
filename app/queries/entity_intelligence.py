"""EntityIntelligenceQueryService (V2 Phase 2B.2).

Everything domain-neutral that touches one Entity: its Facts, its
published Evidence, and the Signals/Assessments/Recommendations/Strategic
Questions that name it. This service does not decide what constitutes a
"competitor portfolio" or any other Berries-shaped grouping -- it only
answers "what does the record set say touches this entity id", the same
question app/main.py's facts_for_entity()/signals_for_entity()/
assessments_for_entity()/recommendations_for_entity()/
strategic_questions_for_entity() already asked, just against a repository
instead of load_json_files().
"""

from __future__ import annotations

from typing import Any


class EntityIntelligenceQueryService:
    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def evidence_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return [r for r in self._repos.evidence.list(status="published") if entity_id in (r.get("entity_ids") or [])]

    def facts_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return [f for f in self._repos.facts.list() if entity_id in (f.get("entity_ids") or [])]

    def signals_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return [s for s in self._repos.signals.list() if entity_id in (s.get("entity_ids") or [])]

    def assessments_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return [a for a in self._repos.assessments.list() if entity_id in (a.get("entity_ids") or [])]

    def recommendations_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return [r for r in self._repos.recommendations.list() if entity_id in (r.get("entity_ids") or [])]

    def strategic_questions_for_entity(
        self,
        linked_evidence: list[dict[str, Any]],
        entity_signals: list[dict[str, Any]],
        entity_assessments: list[dict[str, Any]],
        entity_recommendations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Strategic Questions this entity actually bears on -- the union of
        SQs named on its own linked Evidence and on any Signal/Assessment/
        Recommendation that touches it. Identical logic to app/main.py's
        strategic_questions_for_entity(), which callers keep using under
        that name; this is what it now delegates to."""
        sq_ids: set[str] = set()
        for record in [*linked_evidence, *entity_signals, *entity_assessments, *entity_recommendations]:
            sq_ids.update(record.get("strategic_question_ids") or [])
        return [sq for sq in self._repos.strategic_questions.list() if sq.get("id") in sq_ids]
