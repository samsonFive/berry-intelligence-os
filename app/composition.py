"""The single composition boundary (V2 Phase 2B.2,
docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md Part 2).

Every repository, query service, and Berries domain service the running
application uses is built here, once per distinct data directory, and
nowhere else. `app/main.py`'s helper functions call `get_repositories()`/
`get_query_services()`/`get_domain_services()` instead of instantiating a
repository or service class directly -- the eventual PostgreSQL swap (or
any other backend swap) happens by changing what these three functions
build, not by touching every call site across the application.

## Why keyed by `data_dir`, not a single fixed singleton

`app/main.py`'s `DATA_DIR` module-level global is not actually constant --
`tests/test_build_static.py` (and several tests in `tests/test_app.py`)
`monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")` to redirect the
*entire application* at an isolated, temporary dataset for the duration of
one test, exactly the way the real application's `DATA_DIR` would change
if it were ever pointed at a different deployment's data. A composition
root that built its repositories once, at import time, against whatever
`DATA_DIR` happened to be at that moment, would silently keep reading the
*original* location even after a test (or a future config reload)
repointed `main.DATA_DIR` elsewhere -- exactly the kind of stale-singleton
bug this module exists to prevent.

Caching by `data_dir` instead solves this without giving up the
performance property `load_json_files()`'s own mtime-signature cache was
built for (documented at length in `app/main.py`): in production,
`DATA_DIR` never changes, so every call after the first returns the exact
same repository/service instances, with the exact same cross-call caching
benefit as today. In a test that monkeypatches `DATA_DIR` to a fresh
`tmp_path`, the first call for that new path builds fresh, correctly
isolated instances; nothing from a previous test's `tmp_path` leaks in,
and nothing from this test leaks back out.

This module deliberately does not import from `app.main` (that would be
circular -- `app.main` imports this module, not the other way around).
Callers pass their own `DATA_DIR`/`INBOX_DIR` in explicitly; this module
does not read any global itself.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.queries.coverage import CoverageQueryService
from app.queries.entity_intelligence import EntityIntelligenceQueryService
from app.queries.lineage import LineageQueryService
from app.queries.reference import ReferenceQueryService
from app.queries.scope import ScopeQueryService
from app.queries.search import SearchQueryService
from app.queries.timeline import TimelineQueryService
from app.repositories.json.assessments import AssessmentRepository
from app.repositories.json.entities import EntityRepository
from app.repositories.json.evidence import EvidenceRepository
from app.repositories.json.facts import FactRepository
from app.repositories.json.recommendations import RecommendationRepository
from app.repositories.json.relationships import RelationshipRepository
from app.repositories.json.signals import SignalRepository
from app.repositories.json.sources import JsonSourceRepository
from app.repositories.json.strategic_questions import StrategicQuestionRepository
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.repositories.unit_of_work import JsonUnitOfWork
from app.services.berries.landscape import BerriesLandscapeService
from app.services.berries.variety import BerriesVarietyService

Repositories = SimpleNamespace
QueryServices = SimpleNamespace
DomainServices = SimpleNamespace

_repository_cache: dict[tuple[Path, Path], Repositories] = {}
_query_service_cache: dict[tuple[Path, Path], QueryServices] = {}
_domain_service_cache: dict[tuple[Path, Path], DomainServices] = {}


def get_repositories(data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> Repositories:
    """The 9 record repositories, keyed by (data_dir, schemas_dir). See the
    module docstring for why this is cached-by-key rather than a plain
    module-level singleton."""
    key = (data_dir, schemas_dir)
    if key not in _repository_cache:
        _repository_cache[key] = SimpleNamespace(
            entities=EntityRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            evidence=EvidenceRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            facts=FactRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            relationships=RelationshipRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            signals=SignalRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            assessments=AssessmentRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            recommendations=RecommendationRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            strategic_questions=StrategicQuestionRepository(data_dir=data_dir, schemas_dir=schemas_dir),
            sources=JsonSourceRepository(data_dir=data_dir),
        )
    return _repository_cache[key]


def get_query_services(data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> QueryServices:
    """The 7 Core query services (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md
    Part 3.3), each built from the repository registry for the same
    data_dir -- never from a filesystem path directly."""
    key = (data_dir, schemas_dir)
    if key not in _query_service_cache:
        repos = get_repositories(data_dir, schemas_dir)
        _query_service_cache[key] = SimpleNamespace(
            entity_intelligence=EntityIntelligenceQueryService(repos),
            lineage=LineageQueryService(repos),
            timeline=TimelineQueryService(repos),
            scope=ScopeQueryService(repos),
            reference=ReferenceQueryService(repos),
            coverage=CoverageQueryService(repos),
            search=SearchQueryService(repos),
        )
    return _query_service_cache[key]


def get_domain_services(data_dir: Path = DEFAULT_DATA_DIR, schemas_dir: Path = SCHEMAS_DIR) -> DomainServices:
    """The Berries domain-service layer (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md
    Part 3.4), built from repositories and Core query services, never from
    a filesystem path directly. The one and only Domain Pack this
    deployment activates today -- a second Domain Pack would add a
    sibling module here, not modify this one (Phase 7's own test)."""
    key = (data_dir, schemas_dir)
    if key not in _domain_service_cache:
        repos = get_repositories(data_dir, schemas_dir)
        queries = get_query_services(data_dir, schemas_dir)
        _domain_service_cache[key] = SimpleNamespace(
            landscape=BerriesLandscapeService(repos, queries),
            variety=BerriesVarietyService(repos),
        )
    return _domain_service_cache[key]


def get_unit_of_work(
    data_dir: Path = DEFAULT_DATA_DIR,
    schemas_dir: Path = SCHEMAS_DIR,
    *repository_names: str,
) -> JsonUnitOfWork:
    """The transaction-boundary primitive for any caller with genuine
    multi-object transactional intent (docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md
    Part 1.3, W6 -- review/publish is the one real example today). Builds a
    fresh `JsonUnitOfWork` wrapping the named repositories from
    `get_repositories()` for this `(data_dir, schemas_dir)` -- never a new,
    independently-instantiated repository, and never a second
    dependency-wiring mechanism alongside this module.

        uow = get_unit_of_work(DATA_DIR, SCHEMAS_DIR, "entities", "facts", "relationships", "evidence")
        with uow:
            uow.entities.create(...)
            ...

    Returns a new `JsonUnitOfWork` instance on every call (unlike
    `get_repositories()`/`get_query_services()`/`get_domain_services()`,
    which cache) -- a unit of work is inherently one-shot, scoped to a
    single logical transaction, not a long-lived singleton. The
    repositories it wraps are still the cached, shared instances from
    `get_repositories()`. A future `PostgresUnitOfWork` replaces this
    function's body with one that opens a real `BEGIN`/`COMMIT`/`ROLLBACK`
    -- no caller of `get_unit_of_work()` changes."""
    repos = get_repositories(data_dir, schemas_dir)
    return JsonUnitOfWork(**{name: getattr(repos, name) for name in repository_names})
