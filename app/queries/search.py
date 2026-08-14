"""SearchQueryService (V2 Phase 2B.2, Part 7).

Phase 3 ultimately replaces the live app's in-memory scan with Postgres
search; this task does not build a new search engine or change ranking,
typo-tolerance, or alias behavior (app/main.py's text_matches()/
filter_evidence() stay exactly as they are and remain the single source
of truth for matching logic). This service only removes the one remaining
piece of direct storage access from the live search path: handing the
record pools to search over -- published Evidence, all Entities -- to
api_search()/home()'s existing matching code, instead of api_search()
calling published_evidence()/all_entities() (which, after this phase,
already delegate to repositories themselves; this service exists so the
search *path* is documented as consuming repository data by name, not by
accident of what all_evidence() happens to do today).
"""

from __future__ import annotations

from typing import Any


class SearchQueryService:
    def __init__(self, repos: Any) -> None:
        self._repos = repos

    def published_evidence(self) -> list[dict[str, Any]]:
        return self._repos.evidence.list(status="published")

    def all_entities(self) -> list[dict[str, Any]]:
        return self._repos.entities.list()
