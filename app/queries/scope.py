"""ScopeQueryService (V2 Phase 2B.2, D-012 -- docs/v2/08-DECISION-LOG.md).

D-012: explicit analytical scope and evidence provenance are separate
concepts. `domain_ids`/`market_ids`/`geography_ids` (Assessment,
Recommendation) and `domain_ids`/`geography_ids`/`berry_ids` (Signal) are
optional, additive scope fields a record's author may set explicitly.
Derived scope -- walking a record's own `entity_ids` outward to see what
they touch -- is a hint/convenience/enrichment only, never sole authority
once explicit scope exists, and must never be silently treated as
equivalent to it.

Existing records with no explicit scope field set continue behaving
according to the legacy/default rule every current caller already uses
(entity-id intersection, e.g. landscape_intelligence_objects() in V2
Phase 1.5B) -- this service does not change that behavior, it only gives
it one name and one implementation instead of leaving each caller to
reinvent it, and formalizes the corresponding explicit-scope check for
callers migrating onto D-012's new fields.
"""

from __future__ import annotations

from typing import Any


class ScopeQueryService:
    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def explicit_scope(self, record: dict[str, Any]) -> dict[str, list[str]] | None:
        """The record's own explicit analytical scope, or None if it
        declares none at all (the legacy/default case every pre-D-012
        record is in). Unifies Signal's `berry_ids` field with Assessment/
        Recommendation's `market_ids` field under one concept -- both mean
        "the record's own author says this is what market/domain it's
        about" -- without renaming either field on disk."""
        market_ids = list(record.get("market_ids") or record.get("berry_ids") or [])
        domain_ids = list(record.get("domain_ids") or [])
        geography_ids = list(record.get("geography_ids") or [])
        if not market_ids and not domain_ids and not geography_ids:
            return None
        return {"market_ids": market_ids, "domain_ids": domain_ids, "geography_ids": geography_ids}

    def has_explicit_scope(self, record: dict[str, Any]) -> bool:
        return self.explicit_scope(record) is not None

    def records_by_entity_intersection(
        self, records: list[dict[str, Any]], entity_ids: set[str]
    ) -> list[dict[str, Any]]:
        """The legacy/default derived-scope rule: a record counts as
        'about' a given entity set when its own entity_ids intersects that
        set. This is the exact transitive-derivation rule
        landscape_intelligence_objects() (V2 Phase 1.5B) used inline for
        Assessment/Recommendation, generalized here so it isn't
        reimplemented per caller -- always a derived/enrichment signal,
        never sole authority once a record declares explicit scope (D-012)."""
        return [r for r in records if entity_ids & set(r.get("entity_ids") or [])]

    def scope_disagreements(
        self, records: list[dict[str, Any]], entity_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Records that declare an explicit scope but whose own entity
        linkage does not intersect the given entity set at all -- i.e. the
        explicit and derived signals point in different directions. D-012
        requires this be surfaced, never silently resolved in either
        field's favor. A record with no explicit scope cannot disagree
        (there is nothing to compare the derived signal against)."""
        disagreements = []
        for record in records:
            if not self.has_explicit_scope(record):
                continue
            if not entity_ids & set(record.get("entity_ids") or []):
                disagreements.append(record)
        return disagreements
