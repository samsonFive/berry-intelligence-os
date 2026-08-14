from __future__ import annotations

from pathlib import Path

from app.composition import get_repositories
from app.exports import IntelligencePackageExporter, validate_package
from app.queries.entity_intelligence import EntityIntelligenceQueryService
from app.queries.lineage import LineageQueryService
from app.queries.reference import ReferenceQueryService
from app.queries.scope import ScopeQueryService
from app.repositories.json.entities import EntityRepository
from app.repositories.memory import get_memory_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.berries.variety import BerriesVarietyService
from tests.repositories.test_json_repository_contract import (
    _entity_record, _evidence_record, _fact_record, _strategic_question_record,
)
from tests.repositories.test_source_repository import _source


def seeded_memory():
    repos = get_memory_repositories()
    entity = {**_entity_record("a"), "berry_ids": ["berry-blueberry"], "attributes": {"traits": [{"trait": "trait-a", "value": "firm", "provenance": "unresolved"}]}}
    trait = {**_entity_record("trait"), "id": "trait-a", "entity_type": "trait", "name": "Firmness"}
    evidence = {**_evidence_record("a"), "entity_ids": [entity["id"]], "strategic_question_ids": ["sq-contract-test-a"], "source_id": "source-test-a"}
    fact = {**_fact_record("a"), "evidence_ids": [evidence["id"]], "entity_ids": [entity["id"]]}
    repos.entities.create_many([entity, trait])
    repos.evidence.create(evidence)
    repos.facts.create(fact)
    repos.strategic_questions.create(_strategic_question_record("a"))
    repos.sources.create(_source("a"))
    return repos, entity, evidence, fact


def test_core_query_services_run_unchanged_against_memory() -> None:
    repos, entity, evidence, fact = seeded_memory()
    assert ReferenceQueryService(repos).facts_for_evidence(evidence["id"]) == [fact]
    assert EntityIntelligenceQueryService(repos).evidence_for_entity(entity["id"]) == [evidence]
    assert LineageQueryService(repos).resolve_linked_facts([fact["id"]]) == [fact]
    scoped = {"id": "x", "market_ids": ["berry-blueberry"], "entity_ids": [entity["id"]]}
    assert ScopeQueryService(repos).explicit_scope(scoped)["market_ids"] == ["berry-blueberry"]


def test_berries_variety_service_runs_unchanged_against_memory() -> None:
    repos, entity, _evidence, _fact = seeded_memory()
    rows = BerriesVarietyService(repos).variety_trait_profile(entity, {r["id"]: r for r in repos.entities.list()})
    assert rows[0]["trait_name"] == "Firmness"


def test_intelligence_package_exporter_runs_unchanged_against_memory(tmp_path: Path) -> None:
    repos, _entity, _evidence, _fact = seeded_memory()
    output = tmp_path / "memory-package"
    manifest = IntelligencePackageExporter(repos, SCHEMAS_DIR, generated_on="2026-08-14T12:00:00Z").export(output)
    assert manifest["counts"]["entity"] == 2
    assert manifest["counts"]["source"] == 1
    assert validate_package(output, SCHEMAS_DIR) == []


def test_production_composition_remains_json_backed() -> None:
    assert isinstance(get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR).entities, EntityRepository)
