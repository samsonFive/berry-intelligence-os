"""Geographic Intelligence Resolution V1 -- one-time bootstrap migration.

No explicit geography-to-geography containment relationship existed
anywhere in this corpus before this script ran (confirmed by a full
audit of schemas/relationship.schema.json's predicate enum and every
file in data/relationships/): not on the Geography entity schema, not
as a Relationship record. The "region" concept that did exist
(app/services/berries/geography.py's REGION_LOOKUP/REGIONS, and the
free-text attributes.region string present on some but not all
Geography entities) is a hardcoded, incomplete, taxonomy-inconsistent
name label -- explicitly NOT canonical hierarchy, and not reused here.

This script authors REAL canonical data once: a "part_of" Relationship
record for every (country, continent) pair where BOTH Geography
entities already exist in this corpus, using the UN M49 standard
(https://unstats.un.org/unsd/methodology/m49/) as the deterministic,
authoritative classification source -- never invented, never inferred
at runtime. It creates exactly one new reference Evidence record citing
that standard (every Relationship record in this system's schema
requires evidence_ids with minItems 1; this is real, authoritative,
citable structural reference material, not a fabricated source) and
one Relationship record per valid pair, each citing that Evidence.

It does NOT invent a new Geography entity for any continent/region not
already present in the corpus (only geography-europe and
geography-north-america exist as continent-level entities today; a
country whose true continent has no corresponding entity here -- e.g.
Morocco/South Africa/Zambia/Zimbabwe -> Africa, China -> Asia,
Australia -> Oceania, Chile/Peru/Colombia/Mexico -> Latin America --
is deliberately left without a containment edge rather than fabricating
a new entity or misclassifying it into the wrong existing one).

Idempotent and safe to re-run: existing Relationship/Evidence records
and entity relationship_ids/evidence_ids arrays are never duplicated or
overwritten. Validates before writing: the object of a new edge must be
an existing Geography entity, a subject may not already carry a
different part_of edge (single-parent containment in this flat, real
2-level hierarchy), and no edge may introduce a cycle (general
ancestor-walk check, not hardcoded to 2 levels, so this validation
still holds if a deeper hierarchy is authored later).

After this script runs, app/services/geography_hierarchy.py's resolver
reads ONLY the resulting stored "part_of" Relationship records --
nothing downstream ever re-derives hierarchy from ISO codes, entity
names, or attributes.region at query time.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REFERENCE_EVIDENCE_ID = "ev-un-m49-geographic-regions"

# UN M49 "Europe" and "Northern America" regional groupings, restricted to
# country Geography ids that already exist in data/entities/geographies/.
# subject (country) -> object (continent), both already-canonical ids.
COUNTRY_TO_CONTINENT: dict[str, str] = {
    "geography-spain": "geography-europe",
    "geography-portugal": "geography-europe",
    "geography-united-kingdom": "geography-europe",
    "geography-germany": "geography-europe",
    "geography-netherlands": "geography-europe",
    "geography-united-states": "geography-north-america",
    "geography-canada": "geography-north-america",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_geographies(data_dir: Path) -> dict[str, Path]:
    folder = data_dir / "entities" / "geographies"
    ids: dict[str, Path] = {}
    for path in sorted(folder.glob("*.json")):
        record = _read_json(path)
        if record.get("entity_type") == "geography" and record.get("id"):
            ids[str(record["id"])] = path
    return ids


def _load_existing_part_of(data_dir: Path) -> dict[str, str]:
    """subject_id -> object_id for every existing status=active part_of
    Relationship record, used for idempotency and single-parent validation."""
    folder = data_dir / "relationships"
    edges: dict[str, str] = {}
    for path in folder.glob("*.json"):
        record = _read_json(path)
        if record.get("predicate") == "part_of" and record.get("status") == "active":
            edges[str(record.get("subject_id"))] = str(record.get("object_id"))
    return edges


def _would_cycle(subject: str, obj: str, edges: dict[str, str]) -> bool:
    """True if adding subject->obj would make subject its own ancestor,
    walking the existing edge set generally rather than assuming exactly
    two levels."""
    node = obj
    seen: set[str] = set()
    while node in edges:
        if node == subject or node in seen:
            return True
        seen.add(node)
        node = edges[node]
    return node == subject


def _reference_evidence(entity_ids: list[str], relationship_ids: list[str]) -> dict[str, Any]:
    return {
        "id": REFERENCE_EVIDENCE_ID,
        "record_type": "evidence",
        "status": "published",
        "source_type": "government_registry",
        "title": "UN M49 Standard Country or Area Codes for Statistical Use -- Continental/Regional Groupings",
        "source_name": "United Nations Statistics Division",
        "source_url": "https://unstats.un.org/unsd/methodology/m49/",
        "published_date": None,
        "captured_date": "2026-09-01",
        "summary": (
            "The UN M49 standard defines the continental and regional groupings used to classify "
            "countries and areas for statistical purposes -- including Europe and Northern America as "
            "standard geographic regions with defined country memberships (Spain, Portugal, the United "
            "Kingdom, Germany, and the Netherlands under Europe; the United States and Canada under "
            "Northern America)."
        ),
        "why_it_matters": (
            "Provides an authoritative, non-inferred basis for expressing which trusted Geography "
            "entities already tracked in this corpus are contained within a broader Geography entity "
            "also already tracked here -- used only to source explicit part_of Relationship records "
            "between existing Geography entities, never to add a new Geography entity and never to "
            "infer geography for any Company/Variety/Evidence record."
        ),
        "submitted_by": "migration/generate_geography_containment.py",
        "berry_ids": [],
        "geography_ids": entity_ids,
        "entity_ids": entity_ids,
        "fact_ids": [],
        "relationship_ids": relationship_ids,
        "strategic_question_ids": [],
        "tags": ["reference", "geography", "structural"],
        "priority": {
            "reading": {"level": "none", "rationale": "Structural reference data, not a competitive-intelligence development."},
            "testing": {"level": "none", "rationale": "Not applicable to a geographic reference standard."},
            "commercial_position": {"level": "none", "rationale": "Not applicable."},
            "monitoring": {"level": "none", "rationale": "A stable international standard; not a recurring monitoring target."},
        },
    }


def _relationship(subject_id: str, object_id: str) -> dict[str, Any]:
    subject_slug = subject_id.removeprefix("geography-")
    object_slug = object_id.removeprefix("geography-")
    return {
        "id": f"rel-{subject_slug}-part-of-{object_slug}",
        "record_type": "relationship",
        "subject_id": subject_id,
        "predicate": "part_of",
        "object_id": object_id,
        "status": "active",
        "evidence_ids": [REFERENCE_EVIDENCE_ID],
        "effective_date": None,
        "confidence": "high",
        "notes": (
            "UN M49 standard continental/regional grouping -- structural geographic containment, "
            "not a competitive-intelligence claim. Authored by scripts/generate_geography_containment.py."
        ),
    }


def _append_unique(values: list[Any], new_value: Any) -> list[Any]:
    return values if new_value in values else [*values, new_value]


def run(*, data_dir: Path, dry_run: bool) -> dict[str, Any]:
    geographies = _load_geographies(data_dir)
    existing_part_of = _load_existing_part_of(data_dir)

    valid_pairs: list[tuple[str, str]] = []
    skipped_missing_entity: list[tuple[str, str]] = []
    skipped_existing: list[tuple[str, str]] = []
    rejected_conflicting_parent: list[tuple[str, str, str]] = []
    rejected_cycle: list[tuple[str, str]] = []

    for subject, obj in COUNTRY_TO_CONTINENT.items():
        if subject not in geographies or obj not in geographies:
            skipped_missing_entity.append((subject, obj))
            continue
        current_parent = existing_part_of.get(subject)
        if current_parent == obj:
            skipped_existing.append((subject, obj))
            continue
        if current_parent is not None and current_parent != obj:
            # Preserve any existing finer/conflicting explicit geography
            # data rather than overwriting it.
            rejected_conflicting_parent.append((subject, obj, current_parent))
            continue
        if _would_cycle(subject, obj, existing_part_of):
            rejected_cycle.append((subject, obj))
            continue
        valid_pairs.append((subject, obj))
        existing_part_of[subject] = obj  # so later pairs in this run see it too

    if not valid_pairs:
        return {
            "written_relationships": [],
            "skipped_missing_entity": skipped_missing_entity,
            "skipped_existing": skipped_existing,
            "rejected_conflicting_parent": rejected_conflicting_parent,
            "rejected_cycle": rejected_cycle,
            "reference_evidence_written": False,
        }

    relationships = [_relationship(subject, obj) for subject, obj in valid_pairs]
    involved_entity_ids = sorted({*(s for s, _o in valid_pairs), *(o for _s, o in valid_pairs)})
    relationship_ids = [r["id"] for r in relationships]

    evidence_path = data_dir / "evidence" / f"{REFERENCE_EVIDENCE_ID}.json"
    reference_evidence_written = not evidence_path.is_file()

    if not dry_run:
        if reference_evidence_written:
            _write_json(evidence_path, _reference_evidence(involved_entity_ids, relationship_ids))
        else:
            # Idempotent re-run: fold any newly-added relationship ids into
            # the existing reference Evidence record rather than skipping.
            existing_evidence = _read_json(evidence_path)
            for rid in relationship_ids:
                existing_evidence["relationship_ids"] = _append_unique(existing_evidence.get("relationship_ids") or [], rid)
            for eid in involved_entity_ids:
                existing_evidence["entity_ids"] = _append_unique(existing_evidence.get("entity_ids") or [], eid)
                existing_evidence["geography_ids"] = _append_unique(existing_evidence.get("geography_ids") or [], eid)
            _write_json(evidence_path, existing_evidence)

        for relationship in relationships:
            rel_path = data_dir / "relationships" / f"{relationship['id']}.json"
            _write_json(rel_path, relationship)

        for subject, obj in valid_pairs:
            for geography_id in (subject, obj):
                entity_path = geographies[geography_id]
                entity = _read_json(entity_path)
                entity["relationship_ids"] = _append_unique(
                    entity.get("relationship_ids") or [], f"rel-{subject.removeprefix('geography-')}-part-of-{obj.removeprefix('geography-')}"
                )
                entity["evidence_ids"] = _append_unique(entity.get("evidence_ids") or [], REFERENCE_EVIDENCE_ID)
                _write_json(entity_path, entity)

    return {
        "written_relationships": [r["id"] for r in relationships],
        "skipped_missing_entity": skipped_missing_entity,
        "skipped_existing": skipped_existing,
        "rejected_conflicting_parent": rejected_conflicting_parent,
        "rejected_cycle": rejected_cycle,
        "reference_evidence_written": reference_evidence_written,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run(data_dir=args.data_dir, dry_run=args.dry_run)
    print(f"{'[dry-run] ' if args.dry_run else ''}written relationships: {result['written_relationships']}")
    print(f"reference evidence written: {result['reference_evidence_written']}")
    print(f"skipped (already present): {result['skipped_existing']}")
    print(f"skipped (missing entity): {result['skipped_missing_entity']}")
    print(f"rejected (conflicting existing parent): {result['rejected_conflicting_parent']}")
    print(f"rejected (would create a cycle): {result['rejected_cycle']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
