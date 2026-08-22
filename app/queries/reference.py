"""ReferenceQueryService (V2 Phase 2B.2).

Single-hop reverse-reference lookups that are not centered on one Entity
(see EntityIntelligenceQueryService for those): "which Facts cite this
Evidence", "which Relationships cite this Evidence", "which Evidence
answers this Strategic Question". Each mirrors an existing app/main.py
helper's exact filter logic (facts_for_evidence(), relationships_for_evidence(),
evidence_for_strategic_question()) -- behavior is unchanged, only the data
source moves from load_json_files() to a repository's list().
"""

from __future__ import annotations

from typing import Any


class ReferenceQueryService:
    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def facts_for_evidence(self, evidence_id: str) -> list[dict[str, Any]]:
        return [f for f in self._repos.facts.list() if evidence_id in (f.get("evidence_ids") or [])]

    def relationships_for_evidence(self, evidence_id: str) -> list[dict[str, Any]]:
        return [r for r in self._repos.relationships.list() if evidence_id in (r.get("evidence_ids") or [])]

    def evidence_for_strategic_question(self, sq_id: str) -> list[dict[str, Any]]:
        return [r for r in self._repos.evidence.list(status="published") if sq_id in (r.get("strategic_question_ids") or [])]
