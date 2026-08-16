"""Domain Pack validation (V2 Phase 1B, docs/v2/10-BACKLOG.md BL-018 - BL-023).
Pure file/JSON checks -- no app.main import, no route/template/UI involvement,
no PostgreSQL, no collector execution. Implements the 10 deterministic checks
this task's own 'Validation tooling' section specifies, in place of manual
inspection."""
from __future__ import annotations

import glob
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "domain-packs" / "berries"


def _load(relative: str) -> dict:
    return json.loads((PACK_DIR / relative).read_text(encoding="utf-8"))


def _manifest() -> dict:
    return _load("manifest.json")


# ---------------------------------------------------------------------------
# 1. manifest.json validates against domain-pack.schema.json
# ---------------------------------------------------------------------------

def test_manifest_validates_against_domain_pack_schema() -> None:
    schema = json.loads((ROOT / "schemas" / "domain-pack.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(_manifest()))
    assert errors == [], [e.message for e in errors]


def test_domain_pack_schema_rejects_an_incomplete_manifest() -> None:
    schema = json.loads((ROOT / "schemas" / "domain-pack.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    incomplete = {"id": "example", "version": "1.0.0", "display_name": "Example", "files": {}}
    assert list(validator.iter_errors(incomplete)) != []


def _strip_comments(node):
    """Recursively drop every $comment key -- those are prose annotations
    (which legitimately reference Berries as the worked example), not schema
    structure. What must stay generic is the structure: property names,
    enums, consts -- not explanatory text about them."""
    if isinstance(node, dict):
        return {k: _strip_comments(v) for k, v in node.items() if k != "$comment"}
    if isinstance(node, list):
        return [_strip_comments(v) for v in node]
    return node


def test_domain_pack_schema_contains_no_berry_specific_content() -> None:
    # The schema's STRUCTURE (property names, enums, consts) must stay
    # generic (docs/v2/04-DOMAIN-PACK-SPEC.md) -- it must validate an
    # unrelated second industry's pack equally well. $comment prose is
    # allowed to reference Berries as the worked example; checked separately
    # by stripping it out first.
    schema = json.loads((ROOT / "schemas" / "domain-pack.schema.json").read_text(encoding="utf-8"))
    structure_only = json.dumps(_strip_comments(schema)).lower()
    for forbidden in ("berry", "blueberry", "variety", "cultivar", "breeding_program"):
        assert forbidden not in structure_only


def test_domain_pack_schema_does_not_require_report_templates_filters_or_viz() -> None:
    # Explicit Phase 1 scope narrowing (D-007, docs/v2/08-DECISION-LOG.md).
    schema = json.loads((ROOT / "schemas" / "domain-pack.schema.json").read_text(encoding="utf-8"))
    required = set(schema["properties"]["files"].get("required", []))
    assert "report_templates_dir" not in required
    assert "filters_file" not in required
    assert "visualization_config_file" not in required


# ---------------------------------------------------------------------------
# 2. every referenced Domain Pack file exists
# ---------------------------------------------------------------------------

def test_every_manifest_referenced_file_exists() -> None:
    manifest = _manifest()
    files = manifest["files"]
    checked = []
    for key, value in files.items():
        if key == "taxonomies":
            for _, path in value.items():
                checked.append(path)
        elif value:
            checked.append(value)
    assert checked, "manifest declared no files at all"
    for relative_path in checked:
        assert (PACK_DIR / relative_path).exists(), f"missing referenced file: {relative_path}"


# ---------------------------------------------------------------------------
# 3-5. IDs unique within each file
# ---------------------------------------------------------------------------

def test_entity_type_ids_are_unique() -> None:
    data = _load("entity-types.json")
    ids = [t["id"] for t in data["entity_types"]]
    assert len(ids) == len(set(ids))


def test_relationship_predicate_ids_are_unique() -> None:
    data = _load("relationship-predicates.json")
    ids = [p["id"] for p in data["relationship_predicates"]]
    assert len(ids) == len(set(ids))


def test_taxonomy_ids_are_unique_within_each_taxonomy() -> None:
    roles = _load("taxonomies/entity-role-vocabulary.json")
    role_ids = [r["id"] for r in roles["entity_roles"]]
    assert len(role_ids) == len(set(role_ids))

    traits = _load("taxonomies/trait-vocabulary.json")
    trait_ids = [t["id"] for t in traits["traits"]]
    assert len(trait_ids) == len(set(trait_ids))


def test_strategic_question_template_ids_are_unique() -> None:
    data = _load("strategic-question-templates.json")
    ids = [t["template_id"] for t in data["strategic_question_templates"]]
    assert len(ids) == len(set(ids))


def test_collector_template_ids_are_unique() -> None:
    data = _load("collector-templates.json")
    ids = [t["id"] for t in data["collector_templates"]]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 6. every current live entity type is represented
# ---------------------------------------------------------------------------

def test_every_live_entity_type_is_declared() -> None:
    declared = {t["id"] for t in _load("entity-types.json")["entity_types"]}
    live = set()
    for f in glob.glob(str(ROOT / "data" / "entities" / "*" / "*.json")):
        record = json.loads(Path(f).read_text(encoding="utf-8"))
        live.add(record.get("entity_type"))
    assert live, "no live entities found -- test fixture problem, not a pack problem"
    assert live.issubset(declared), f"undeclared live entity types: {live - declared}"


def test_every_live_entity_resolves_to_a_declared_type() -> None:
    # BL-019's own stated acceptance criterion, checked per-entity, not just
    # per-distinct-type.
    declared = {t["id"] for t in _load("entity-types.json")["entity_types"]}
    total = 0
    for f in glob.glob(str(ROOT / "data" / "entities" / "*" / "*.json")):
        record = json.loads(Path(f).read_text(encoding="utf-8"))
        assert record.get("entity_type") in declared, f"{f}: entity_type {record.get('entity_type')!r} not declared"
        total += 1
    assert total == 162, f"expected 162 live entities, found {total}"


# ---------------------------------------------------------------------------
# 7. every current live relationship predicate is represented
# ---------------------------------------------------------------------------

def test_every_live_relationship_resolves_to_a_declared_predicate() -> None:
    declared = {p["id"] for p in _load("relationship-predicates.json")["relationship_predicates"]}
    total = 0
    for f in glob.glob(str(ROOT / "data" / "relationships" / "*.json")):
        record = json.loads(Path(f).read_text(encoding="utf-8"))
        assert record.get("predicate") in declared, f"{f}: predicate {record.get('predicate')!r} not declared"
        total += 1
    assert total == 204, f"expected 204 live relationships, found {total}"


def test_all_ten_v1_predicates_and_six_extensions_present() -> None:
    declared = {p["id"] for p in _load("relationship-predicates.json")["relationship_predicates"]}
    v1_ten = {
        "owns", "develops", "licenses", "distributes", "grows",
        "trials", "sells", "carries", "partners_with", "operates_in",
    }
    extensions_six = {
        "exhibits_claimed_trait", "protects", "markets",
        "offers", "administers_license_for", "subsidiary_of",
    }
    assert v1_ten.issubset(declared)
    assert extensions_six.issubset(declared)
    assert len(declared) == 16


# ---------------------------------------------------------------------------
# 8. all 9 strategic questions are represented
# ---------------------------------------------------------------------------

def test_all_nine_strategic_questions_represented_exactly_once() -> None:
    declared_ids = [t["template_id"] for t in _load("strategic-question-templates.json")["strategic_question_templates"]]
    live_ids = []
    for f in glob.glob(str(ROOT / "data" / "strategic-questions" / "*.json")):
        live_ids.append(json.loads(Path(f).read_text(encoding="utf-8"))["id"])
    assert len(live_ids) == 9
    assert sorted(declared_ids) == sorted(live_ids)
    assert len(declared_ids) == len(set(declared_ids))


def test_strategic_question_template_content_preserved() -> None:
    templates_by_id = {
        t["template_id"]: t
        for t in _load("strategic-question-templates.json")["strategic_question_templates"]
    }
    for f in glob.glob(str(ROOT / "data" / "strategic-questions" / "*.json")):
        record = json.loads(Path(f).read_text(encoding="utf-8"))
        template = templates_by_id[record["id"]]
        assert template["title"] == record["title"]
        assert template["description"] == record.get("description", "")


def test_live_strategic_question_records_untouched() -> None:
    # This task must not migrate or modify the live records themselves.
    for f in glob.glob(str(ROOT / "data" / "strategic-questions" / "*.json")):
        record = json.loads(Path(f).read_text(encoding="utf-8"))
        assert record["status"] == "active"
        assert record["record_type"] == "strategic_question"


# ---------------------------------------------------------------------------
# 9. all live source-registry entries are accounted for
# ---------------------------------------------------------------------------

def test_all_live_sources_accounted_for() -> None:
    data = _load("collector-templates.json")
    templates = data["collector_templates"]
    excluded = data.get("excluded", [])
    sources = json.loads((ROOT / "data" / "configuration" / "sources.json").read_text(encoding="utf-8"))
    assert len(sources) == 125

    represented_ids = {t["id"] for t in templates}
    excluded_ids = {e["id"] for e in excluded}
    source_ids = {s["id"] for s in sources}

    # Every source is either templated or explicitly excluded with a reason --
    # never silently dropped.
    accounted_for = represented_ids | excluded_ids
    assert accounted_for == source_ids
    assert represented_ids.isdisjoint(excluded_ids)
    for e in excluded:
        assert e.get("reason"), f"excluded source {e['id']} has no documented reason"


def test_collector_templates_separate_platform_type_from_source_config() -> None:
    # The task's explicit distinction: PLATFORM COLLECTOR TYPE vs.
    # BERRIES-SPECIFIC SOURCE/QUERY CONFIGURATION.
    templates = _load("collector-templates.json")["collector_templates"]
    types_seen = {t["collector_type"] for t in templates}
    assert types_seen == {"rss", "keyword_search", "reference_manual"}
    for t in templates:
        assert t["query_or_url"], f"{t['id']} has no query/URL configuration"


# ---------------------------------------------------------------------------
# 10. no executable code exists in the Domain Pack
# ---------------------------------------------------------------------------

def test_domain_pack_contains_no_executable_code() -> None:
    executable_extensions = {
        ".py", ".pyc", ".js", ".mjs", ".ts", ".sh", ".bash", ".ps1",
        ".exe", ".bat", ".cmd", ".rb", ".pl", ".php",
    }
    offenders = []
    for path in PACK_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in executable_extensions:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"executable files found in domain-packs/berries/: {offenders}"


def test_domain_pack_is_declarative_json_only() -> None:
    non_json_files = [
        str(p.relative_to(ROOT))
        for p in PACK_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() != ".json"
    ]
    assert non_json_files == [], f"non-JSON files found: {non_json_files}"
