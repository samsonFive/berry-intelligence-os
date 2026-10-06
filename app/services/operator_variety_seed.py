"""Photo-supplied variety leads: additive candidates, never trusted identities or roles."""
from pathlib import Path
import json

from app.services.analyst_state_io import serialized_write
from app.services.variety_universe.candidates import load_variety_candidates
from app.services.variety_universe.identity import fold_identity
from app.services.variety_universe.registry_import import build_candidate, import_registry_rows

SOURCE_ID = "operator-variety-registry-2026-09-30"
FIXTURE = "imports/variety-operator-seed-2026-09-30/rows.json"


def fixture(data_dir: Path):
    return json.loads((data_dir / FIXTURE).read_text(encoding="utf-8"))


def seed_rows(data_dir: Path, entities: dict):
    grouped = {}
    for row in fixture(data_dir)["rows"]:
        if not row["company_ids"] or any(key not in entities for key in row["company_ids"]):
            raise ValueError("Resolve missing company entries before importing variety seeds")
        key = (fold_identity(row["candidate_name"]), row["berry_id"])
        if key not in grouped:
            grouped[key] = {
                "candidate_name": row["candidate_name"], "berry_id": row["berry_id"],
                "source_id": SOURCE_ID, "source_label": "Your variety spreadsheet photos · 30 Sep 2026",
                "source_type": "operator_registry", "source_tier": "weak_noncanonical_lead",
                "knowledge": {"company_associations": [], "photo_mentions": [],
                              "association_status": "pending_review", "relationship_role": "unspecified",
                              "transcription_status": "Needs confirmation against the supplied photos"},
            }
        knowledge = grouped[key]["knowledge"]
        for company_id in row["company_ids"]:
            association = {"entity_id": company_id, "name": entities[company_id]["name"],
                           "entity_type": entities[company_id]["entity_type"],
                           "registry_label": row["company_label"], "role": "unspecified", "status": "pending_review"}
            if association not in knowledge["company_associations"]:
                knowledge["company_associations"].append(association)
        knowledge["photo_mentions"].append({"image_number": row["image_number"], "company_label": row["company_label"]})
    return list(grouped.values())


@serialized_write
def install(inbox_dir: Path, data_dir: Path, entities: dict):
    return import_registry_rows(seed_rows(data_dir, entities),
                               varieties=[row for row in entities.values() if row.get("entity_type") == "variety"],
                               inbox_dir=inbox_dir)


def workspace(inbox_dir: Path, data_dir: Path, entities: dict, *, company="", berry="", letter="", q=""):
    source = fixture(data_dir)
    persisted = {row["id"]: row for row in load_variety_candidates(inbox_dir)}
    varieties = [row for row in entities.values() if row.get("entity_type") == "variety"]
    built = [build_candidate(row, varieties=varieties, discovered_at="2026-09-30T00:00:00Z") for row in seed_rows(data_dir, entities)]
    choices = {item["entity_id"]: item["name"] for row in built for item in row["knowledge"]["company_associations"]}
    result = []
    for row in built:
        saved = persisted.get(row["id"])
        row = {**row, **(saved or {}), "persisted": bool(saved)}
        associations = row["knowledge"]["company_associations"]
        if company and company not in {item["entity_id"] for item in associations}:
            continue
        if berry and row["berry_id"] != berry:
            continue
        if letter and not row["candidate_name"].upper().startswith(letter):
            continue
        if q and q.casefold() not in " ".join([row["candidate_name"], *(item["name"] for item in associations)]).casefold():
            continue
        result.append(row)
    labels = {key: entities.get(key, {}).get("name", key.removeprefix("berry-").title()) for key in {row["berry_id"] for row in built}}
    company_labels = {row["company_label"] for row in source["rows"] if company in row["company_ids"]}
    exceptions = [row for row in source["exceptions"] if (not company or row["company_label"] in company_labels)
                  and (not berry or row["berry"] == berry.removeprefix("berry-"))]
    return {"rows": sorted(result, key=lambda row: row["candidate_name"].casefold()),
            "company_choices": sorted(choices.items(), key=lambda item: item[1].casefold()), "berry_choices": sorted(labels.items()),
            "exceptions": exceptions, "total": len(built), "associations": len(source["rows"]),
            "installed": sum(row["id"] in persisted for row in built),
            "filters": {"company": company, "berry": berry, "letter": letter, "q": q}}


def company_seed_count(data_dir: Path, company_id: str):
    if not (data_dir / FIXTURE).exists():
        return 0
    return len({(fold_identity(row["candidate_name"]), row["berry_id"]) for row in fixture(data_dir)["rows"] if company_id in row["company_ids"]})
