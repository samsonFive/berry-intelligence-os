"""Minimal JSON Intelligence Package exporter (BL-035).

Core records enter through repository interfaces. Filesystem knowledge is
limited to the package boundary: serializing, validating, and re-importing the
portable artifact itself.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

PACKAGE_VERSION = "1.0.0"
INTELLIGENCE_OS_VERSION = "0.1.0"
SEED_ENTITY_IDS = {"company-example-genetics", "company-example-nursery", "retailer-example-market", "variety-example-blue", "variety-example-red"}
SEED_EVIDENCE_IDS = {"ev-sample-patent-published", "ev-sample-retail-placement", "ev-sample-variety-launch"}
FAMILIES = ("entities", "evidence", "facts", "relationships", "assessments", "signals", "recommendations", "strategic_questions", "sources")
FOLDERS = {"strategic_questions": "strategic-questions", **{name: name for name in FAMILIES if name != "strategic_questions"}}
SINGULAR = {"entities": "entity", "evidence": "evidence", "facts": "fact", "relationships": "relationship", "assessments": "assessment", "signals": "signal", "recommendations": "recommendation", "strategic_questions": "strategic_question", "sources": "source"}
SCHEMAS = {name: f"{name.rstrip('s')}.schema.json" for name in FAMILIES if name != "sources"}
SCHEMAS.update({"entities": "entity.schema.json", "evidence": "evidence.schema.json", "strategic_questions": "strategic-question.schema.json"})
DEPTHS = {"entities": 0, "evidence": 0, "facts": 1, "relationships": 1, "signals": 2, "assessments": 2, "recommendations": 3, "strategic_questions": 0, "sources": 0}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()


def _clean(record: dict[str, Any]) -> dict[str, Any]:
    return {k: deepcopy(v) for k, v in record.items() if k not in {"_package_ref", "_lineage_depth"}}


def canonical_records(records: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {family: sorted((_clean(r) for r in values), key=lambda r: r["id"]) for family, values in records.items()}


class IntelligencePackageExporter:
    def __init__(self, repositories: Any, schemas_dir: Path, *, generated_on: str | None = None) -> None:
        self.repositories = repositories
        self.schemas_dir = schemas_dir
        self.generated_on = generated_on or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def collect(self) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        records = {name: sorted(getattr(self.repositories, name).list(), key=lambda r: r["id"]) for name in FAMILIES}
        records["entities"] = [r for r in records["entities"] if r["id"] not in SEED_ENTITY_IDS]
        records["evidence"] = [r for r in records["evidence"] if r["id"] not in SEED_EVIDENCE_IDS and r.get("status") == "published"]
        exclusions = {
            "entity": {"count": len(SEED_ENTITY_IDS), "ids": sorted(SEED_ENTITY_IDS), "reason": "known fictional V1 seed/demo records"},
            "evidence": {"count": len(SEED_EVIDENCE_IDS), "ids": sorted(SEED_EVIDENCE_IDS), "reason": "known fictional V1 seed/demo records"},
        }
        return records, exclusions

    def export(self, output: Path, *, overwrite: bool = False) -> dict[str, Any]:
        if output.exists() and any(output.iterdir()):
            if not overwrite:
                raise FileExistsError(f"output directory is not empty: {output}")
            raise FileExistsError("refusing destructive overwrite of a non-empty package directory")
        output.mkdir(parents=True, exist_ok=True)
        records, exclusions = self.collect()
        exported: dict[str, list[dict[str, Any]]] = {}
        for family, values in records.items():
            exported[family] = []
            for record in values:
                item = {**deepcopy(record), "_package_ref": record["id"], "_lineage_depth": DEPTHS[family]}
                exported[family].append(item)
                folder = output / FOLDERS[family]
                if family == "entities":
                    folder /= record["entity_type"]
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{record['id']}.json").write_bytes(_json_bytes(item))
        claims = [r for r in exported["facts"] if r.get("classification") == "claim"]
        (output / "claims").mkdir(exist_ok=True)
        for record in claims:
            (output / "claims" / f"{record['id']}.json").write_bytes(_json_bytes(record))
        lineage = build_lineage(records)
        (output / "source-lineage.json").write_bytes(_json_bytes(lineage))
        content_hash = hashlib.sha256(_json_bytes({"records": exported, "claims": claims, "lineage": lineage})).hexdigest()
        counts = {SINGULAR[family]: len(values) for family, values in exported.items()}
        counts["claim"] = len(claims)
        manifest = {
            "package_id": f"intelligence-os-v2-export-{self.generated_on[:10]}", "package_version": PACKAGE_VERSION,
            "intelligence_os_version": INTELLIGENCE_OS_VERSION, "domain_pack": {"id": "berries", "version": "1.0.0"},
            "generated_on": self.generated_on, "generated_by": {"type": "system", "id": "minimal-exporter"},
            "workspace_id": "workspace-berries-global-compatibility", "scope": {"description": "Published Evidence plus current non-Evidence operational records; known V1 fictional seed/demo records excluded.", "filter": {"evidence_status": ["published"], "non_evidence_status": "preserved"}},
            "format": "json", "counts": counts, "content_hash": f"sha256:{content_hash}",
            "schema_versions": {SINGULAR[family]: "current" for family in FAMILIES if family != "sources"},
            "provenance_completeness": "full", "review_state_included": ["published", "proposed"], "exclusions": exclusions,
            "notes": "Minimal BL-035 export. Evidence is published-only; six legacy Signals retain proposed status so all operational families round-trip honestly. Workspace id is compatibility metadata; no persisted Workspace record exists. Sources are a JSON-format extension. Attachments are not included.",
        }
        (output / "manifest.json").write_bytes(_json_bytes(manifest))
        errors = validate_package(output, self.schemas_dir)
        if errors:
            raise ValueError("package validation failed: " + "; ".join(errors))
        return manifest


def build_lineage(records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_family = {name: {r["id"]: r for r in values} for name, values in records.items()}
    orphan = {"facts_without_evidence": [], "relationships_without_evidence": [], "assessments_without_facts": [], "dangling_references": []}
    for fact in records["facts"]:
        if not fact.get("evidence_ids"): orphan["facts_without_evidence"].append(fact["id"])
    for rel in records["relationships"]:
        if not rel.get("evidence_ids"): orphan["relationships_without_evidence"].append(rel["id"])
    for assessment in records["assessments"]:
        if not assessment.get("fact_ids"): orphan["assessments_without_facts"].append(assessment["id"])
    reference_fields = {"entity_ids": "entities", "evidence_ids": "evidence", "fact_ids": "facts", "signal_ids": "signals", "assessment_ids": "assessments", "strategic_question_ids": "strategic_questions"}
    for family, values in records.items():
        for record in values:
            for field, target in reference_fields.items():
                for ref in record.get(field, []):
                    if ref not in by_family[target] and ref not in SEED_ENTITY_IDS | SEED_EVIDENCE_IDS:
                        orphan["dangling_references"].append(f"{family}:{record['id']}:{field}:{ref}")
            if family == "relationships":
                for field in ("subject_id", "object_id"):
                    if record.get(field) not in by_family["entities"]: orphan["dangling_references"].append(f"relationships:{record['id']}:{field}:{record.get(field)}")
    chains = []
    for recommendation in records["recommendations"]:
        linked_ids = recommendation.get("assessment_or_signal_ids", []) + recommendation.get("assessment_ids", []) + recommendation.get("signal_ids", [])
        linked = [by_family["assessments"].get(x) or by_family["signals"].get(x) for x in linked_ids]
        fact_ids = sorted(set(recommendation.get("fact_ids", []) + [x for item in linked if item for x in item.get("fact_ids", [])]))
        evidence_ids = sorted(set(recommendation.get("evidence_ids", []) + [x for fid in fact_ids for x in by_family["facts"].get(fid, {}).get("evidence_ids", [])]))
        source_ids = sorted({by_family["evidence"][eid].get("source_id") for eid in evidence_ids if eid in by_family["evidence"] and by_family["evidence"][eid].get("source_id")})
        chains.append({"recommendation_id": recommendation["id"], "assessment_or_signal_ids": sorted(set(linked_ids)), "fact_ids": fact_ids, "evidence_ids": evidence_ids, "source_ids": source_ids})
    for values in orphan.values(): values.sort()
    return {"chains": chains, "orphan_check": orphan}


def load_package_records(package: Path) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for family in FAMILIES:
        folder = package / FOLDERS[family]
        result[family] = [_clean(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(folder.rglob("*.json"))] if folder.exists() else []
    return canonical_records(result)


def validate_package(package: Path, schemas_dir: Path) -> list[str]:
    errors: list[str] = []
    for required in ("manifest.json", "source-lineage.json"):
        if not (package / required).is_file(): errors.append(f"missing {required}")
    if errors: return errors
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    for field in ("package_id", "package_version", "generated_on", "generated_by", "workspace_id", "scope", "format", "counts", "content_hash", "schema_versions", "provenance_completeness", "review_state_included"):
        if field not in manifest: errors.append(f"manifest missing {field}")
    records = load_package_records(package)
    def strings(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values(): yield from strings(child)
        elif isinstance(value, list):
            for child in value: yield from strings(child)
    if any((len(value) > 2 and value[1:3] == ":\\") or value.startswith(("/tmp/", "/var/tmp/")) for value in strings(records)):
        errors.append("package embeds an internal filesystem path")
    claims = [_clean(json.loads(path.read_text(encoding="utf-8"))) for path in sorted((package / "claims").glob("*.json"))] if (package / "claims").exists() else []
    expected_claims = [record for record in records["facts"] if record.get("classification") == "claim"]
    if claims != expected_claims:
        errors.append("claims materialization does not match claim-classified facts")
    for family, values in records.items():
        ids = [r["id"] for r in values]
        if len(ids) != len(set(ids)): errors.append(f"duplicate id in {family}")
        schema_name = SCHEMAS.get(family)
        if schema_name:
            validator = Draft202012Validator(json.loads((schemas_dir / schema_name).read_text()), format_checker=FormatChecker())
            for record in values:
                errors.extend(f"{family}:{record['id']}: {e.message}" for e in validator.iter_errors(record))
    lineage = build_lineage(records)
    stored = json.loads((package / "source-lineage.json").read_text())
    if stored != lineage: errors.append("source-lineage.json does not match package records")
    if any(lineage["orphan_check"].values()): errors.append("orphan_check is not empty")
    exported = {family: [{**r, "_package_ref": r["id"], "_lineage_depth": DEPTHS[family]} for r in values] for family, values in records.items()}
    exported_claims = [r for r in exported["facts"] if r.get("classification") == "claim"]
    digest = hashlib.sha256(_json_bytes({"records": exported, "claims": exported_claims, "lineage": lineage})).hexdigest()
    if manifest.get("content_hash") != f"sha256:{digest}": errors.append("content_hash mismatch")
    expected_counts = {SINGULAR[family]: len(values) for family, values in records.items()}
    expected_counts["claim"] = len(expected_claims)
    if manifest.get("counts") != expected_counts: errors.append("manifest counts do not match package records")
    return errors


def import_package(package: Path, repositories: Any) -> None:
    records = load_package_records(package)
    for family in FAMILIES:
        repository = getattr(repositories, family)
        if hasattr(repository, "create_many"):
            repository.create_many(records[family])
        else:
            for record in records[family]:
                repository.create(record)
