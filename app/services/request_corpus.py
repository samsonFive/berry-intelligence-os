"""Request-scoped lazy corpus + inverted entity indices.

Process-level JSON caches already avoid re-parsing unchanged folders.
The remaining cost is repeated request-level all_*/filter/sort/reverse
scans and full-list comprehensions per entity id. This module memoizes
trusted corpus lists once per HTTP request and builds inverted indices
lazily when a route actually needs them.

Lightweight paths (/login, /healthz, /static) never create a corpus.
Outside a request (CLI, tests without middleware) helpers fall through
to the repository layer unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_corpus_var: ContextVar["RequestCorpus | None"] = ContextVar("bios_request_corpus", default=None)

# Paths that must not trigger corpus construction.
SKIP_CORPUS_PREFIXES = ("/static",)
SKIP_CORPUS_PATHS = frozenset({"/login", "/healthz", "/favicon.ico"})


def should_skip_corpus(path: str) -> bool:
    if path in SKIP_CORPUS_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in SKIP_CORPUS_PREFIXES)


def get_request_corpus() -> RequestCorpus | None:
    return _corpus_var.get()


def bind_request_corpus(corpus: RequestCorpus | None) -> Token:
    return _corpus_var.set(corpus)


def reset_request_corpus(token: Token) -> None:
    _corpus_var.reset(token)


def _index_by_entity_ids(
    records: list[dict[str, Any]],
    *,
    id_fields: tuple[str, ...] = ("entity_ids",),
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        seen: set[str] = set()
        for field_name in id_fields:
            for entity_id in record.get(field_name) or []:
                text = str(entity_id or "")
                if not text or text in seen:
                    continue
                seen.add(text)
                index[text].append(record)
    return index


def _index_relationships(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        seen: set[str] = set()
        for key in ("subject_id", "object_id"):
            entity_id = str(record.get(key) or "")
            if not entity_id or entity_id in seen:
                continue
            seen.add(entity_id)
            index[entity_id].append(record)
    return index


@dataclass
class RequestCorpus:
    """Lazy per-request views over trusted data/ (and optional inbox)."""

    data_dir: Path
    schemas_dir: Path
    inbox_dir: Path | None = None
    _repos: Any = field(default=None, repr=False)
    _evidence: list[dict[str, Any]] | None = field(default=None, repr=False)
    _published: list[dict[str, Any]] | None = field(default=None, repr=False)
    _entities: list[dict[str, Any]] | None = field(default=None, repr=False)
    _facts: list[dict[str, Any]] | None = field(default=None, repr=False)
    _relationships: list[dict[str, Any]] | None = field(default=None, repr=False)
    _signals: list[dict[str, Any]] | None = field(default=None, repr=False)
    _assessments: list[dict[str, Any]] | None = field(default=None, repr=False)
    _recommendations: list[dict[str, Any]] | None = field(default=None, repr=False)
    _strategic_questions: list[dict[str, Any]] | None = field(default=None, repr=False)
    _sources: list[dict[str, Any]] | None = field(default=None, repr=False)
    _entity_index: dict[str, dict[str, Any]] | None = field(default=None, repr=False)
    _evidence_by_entity: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _facts_by_entity: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _signals_by_entity: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _assessments_by_entity: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _recommendations_by_entity: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _relationships_by_entity: dict[str, list[dict[str, Any]]] | None = field(default=None, repr=False)
    _drafts: list[dict[str, Any]] | None = field(default=None, repr=False)
    _drafts_metadata: list[dict[str, Any]] | None = field(default=None, repr=False)

    def repos(self) -> Any:
        if self._repos is None:
            from app.composition import get_repositories

            self._repos = get_repositories(self.data_dir, self.schemas_dir)
        return self._repos

    def _list(self, attr: str, loader: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
        cached = getattr(self, attr)
        if cached is None:
            cached = loader()
            setattr(self, attr, cached)
        return cached

    @property
    def evidence(self) -> list[dict[str, Any]]:
        return self._list("_evidence", lambda: self.repos().evidence.list())

    @property
    def published_evidence(self) -> list[dict[str, Any]]:
        if self._published is None:
            records = [r for r in self.evidence if r.get("status") == "published"]
            self._published = sorted(
                records,
                key=lambda r: r.get("published_date") or r.get("captured_date", ""),
                reverse=True,
            )
        return self._published

    @property
    def entities(self) -> list[dict[str, Any]]:
        return self._list("_entities", lambda: self.repos().entities.list())

    @property
    def entity_index(self) -> dict[str, dict[str, Any]]:
        if self._entity_index is None:
            self._entity_index = {e["id"]: e for e in self.entities if e.get("id")}
        return self._entity_index

    @property
    def facts(self) -> list[dict[str, Any]]:
        return self._list("_facts", lambda: self.repos().facts.list())

    @property
    def relationships(self) -> list[dict[str, Any]]:
        return self._list("_relationships", lambda: self.repos().relationships.list())

    @property
    def signals(self) -> list[dict[str, Any]]:
        return self._list("_signals", lambda: self.repos().signals.list())

    @property
    def assessments(self) -> list[dict[str, Any]]:
        return self._list("_assessments", lambda: self.repos().assessments.list())

    @property
    def recommendations(self) -> list[dict[str, Any]]:
        return self._list("_recommendations", lambda: self.repos().recommendations.list())

    @property
    def strategic_questions(self) -> list[dict[str, Any]]:
        return self._list("_strategic_questions", lambda: self.repos().strategic_questions.list())

    @property
    def sources(self) -> list[dict[str, Any]]:
        return self._list("_sources", lambda: self.repos().sources.list())

    @property
    def evidence_by_entity(self) -> dict[str, list[dict[str, Any]]]:
        """Published evidence indexed by entity_ids and geography_ids."""
        if self._evidence_by_entity is None:
            self._evidence_by_entity = _index_by_entity_ids(
                self.published_evidence,
                id_fields=("entity_ids", "geography_ids"),
            )
        return self._evidence_by_entity

    @property
    def facts_by_entity(self) -> dict[str, list[dict[str, Any]]]:
        if self._facts_by_entity is None:
            self._facts_by_entity = _index_by_entity_ids(self.facts)
        return self._facts_by_entity

    @property
    def signals_by_entity(self) -> dict[str, list[dict[str, Any]]]:
        if self._signals_by_entity is None:
            self._signals_by_entity = _index_by_entity_ids(self.signals)
        return self._signals_by_entity

    @property
    def assessments_by_entity(self) -> dict[str, list[dict[str, Any]]]:
        if self._assessments_by_entity is None:
            self._assessments_by_entity = _index_by_entity_ids(self.assessments)
        return self._assessments_by_entity

    @property
    def recommendations_by_entity(self) -> dict[str, list[dict[str, Any]]]:
        if self._recommendations_by_entity is None:
            self._recommendations_by_entity = _index_by_entity_ids(self.recommendations)
        return self._recommendations_by_entity

    @property
    def relationships_by_entity(self) -> dict[str, list[dict[str, Any]]]:
        if self._relationships_by_entity is None:
            self._relationships_by_entity = _index_relationships(self.relationships)
        return self._relationships_by_entity

    def evidence_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return list(self.evidence_by_entity.get(entity_id, ()))

    def facts_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return list(self.facts_by_entity.get(entity_id, ()))

    def signals_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return list(self.signals_by_entity.get(entity_id, ()))

    def assessments_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return list(self.assessments_by_entity.get(entity_id, ()))

    def recommendations_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return list(self.recommendations_by_entity.get(entity_id, ()))

    def relationships_for_entity(self, entity_id: str) -> list[dict[str, Any]]:
        return list(self.relationships_by_entity.get(entity_id, ()))
