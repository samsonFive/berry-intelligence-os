"""Intelligence Front Page V1 -- geography containment completion.

The Front Page mission requires a "By Region" section covering Americas,
Europe, Africa, and APAC. scripts/generate_geography_containment.py
(Geographic Intelligence Resolution V1) deliberately left every country
outside Europe/North America without a continent parent, because no
Africa/Americas/APAC Geography entity existed in the corpus yet and that
script's own charter was "do not invent a new Geography entity" -- see
its docstring. That gap is now a real blocker for the required section,
so this script closes it the same way: real canonical data, written once,
idempotent, validated, never inferred at query time.

It adds exactly three new continent-level Geography entities --
geography-africa, geography-americas, geography-apac -- and the part_of
Relationship records that connect existing country entities (and, for
Americas, the existing geography-north-america continent entity) to them.
geography-europe is left as a top-level region with no parent, matching
how the mission lists Europe as a parallel region to Americas/Africa/APAC
rather than nested under anything larger.

Two distinct evidence citations back these edges, because they rest on
two different kinds of authority and conflating them would misrepresent
the weaker one as a national-statistics standard:

  * Africa and Americas are real UN M49 regions (the same standard the
    prior script cited for Europe/Northern America), so their edges cite
    a new ev-un-m49-africa-americas-regions record.
  * "APAC" (Asia-Pacific) is NOT a UN M49 region -- UN M49 classifies
    Australia under Oceania and China under Asia as two separate regions.
    APAC is a widely used industry/market-research convention (the kind
    of grouping this application already uses informally, e.g. in
    business reporting) that combines them. Its edges cite a separate
    ev-apac-industry-region-grouping record that says exactly that,
    rather than borrowing the UN M49 record's authority for a claim it
    doesn't make.

For the Americas branch, Chile/Peru/Colombia/Mexico are parented directly
to geography-americas rather than through an intermediate "Latin America
and the Caribbean" or "South America" entity, since no such entity exists
in the corpus and this mission does not need that finer level -- they are
still correctly members of the Americas at the level UN M49 verifies.

Idempotent and safe to re-run, using the same validation as the prior
script: an edge is only written if both entities exist, the subject does
not already carry a different part_of parent, and adding the edge would
not create a cycle (general ancestor walk, not hardcoded to any depth --
this now matters for real, since geography-north-america gains a parent
of its own, giving the United States/Canada a 3-level ancestry).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

UN_M49_EVIDENCE_ID = "ev-un-m49-africa-americas-regions"
APAC_EVIDENCE_ID = "ev-apac-industry-region-grouping"

NEW_CONTINENTS: dict[str, str] = {
    "geography-africa": "Africa",
    "geography-americas": "Americas",
    "geography-apac": "APAC",
}

# subject (existing entity) -> (object continent, evidence id backing the edge)
REGION_EDGES: dict[str, tuple[str, str]] = {
    "geography-morocco": ("geography-africa", UN_M49_EVIDENCE_ID),
    "geography-south-africa": ("geography-africa", UN_M49_EVIDENCE_ID),
    "geography-zambia": ("geography-africa", UN_M49_EVIDENCE_ID),
    "geography-zimbabwe": ("geography-africa", UN_M49_EVIDENCE_ID),
    "geography-north-america": ("geography-americas", UN_M49_EVIDENCE_ID),
    "geography-chile": ("geography-americas", UN_M49_EVIDENCE_ID),
    "geography-peru": ("geography-americas", UN_M49_EVIDENCE_ID),
    "geography-colombia": ("geography-americas", UN_M49_EVIDENCE_ID),
    "geography-mexico": ("geography-americas", UN_M49_EVIDENCE_ID),
    "geography-australia": ("geography-apac", APAC_EVIDENCE_ID),
    "geography-china": ("geography-apac", APAC_EVIDENCE_ID),
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
    folder = data_dir / "relationships"
    edges: dict[str, str] = {}
    for path in folder.glob("*.json"):
        record = _read_json(path)
        if record.get("predicate") == "part_of" and record.get("status") == "active":
            edges[str(record.get("subject_id"))] = str(record.get("object_id"))
    return edges


def _would_cycle(subject: str, obj: str, edges: dict[str, str]) -> bool:
    node = obj
    seen: set[str] = set()
    while node in edges:
        if node == subject or node in seen:
            return True
        seen.add(node)
        node = edges[node]
    return node == subject


def _continent_entity(geography_id: str, name: str) -> dict[str, Any]:
    return {
        "id": geography_id,
        "record_type": "entity",
        "entity_type": "geography",
        "name": name,
        "aliases": [],
        "status": "active",
        "description": "",
        "roles": [],
        "berry_ids": [],
        "evidence_ids": [],
        "fact_ids": [],
        "relationship_ids": [],
        "attributes": {},
    }


def _relationship(subject_id: str, object_id: str, evidence_id: str) -> dict[str, Any]:
    subject_slug = subject_id.removeprefix("geography-")
    object_slug = object_id.removeprefix("geography-")
    note = (
        "UN M49 standard continental/regional grouping -- structural geographic containment, "
        "not a competitive-intelligence claim."
        if evidence_id == UN_M49_EVIDENCE_ID
        else (
            "APAC industry/market-research regional grouping (not a UN M49 standard region) -- "
            "structural geographic containment, not a competitive-intelligence claim."
        )
    )
    return {
        "id": f"rel-{subject_slug}-part-of-{object_slug}",
        "record_type": "relationship",
        "subject_id": subject_id,
        "predicate": "part_of",
        "object_id": object_id,
        "status": "active",
        "evidence_ids": [evidence_id],
        "effective_date": None,
        "confidence": "high",
        "notes": note + " Authored by scripts/generate_geography_regions_v2.py.",
    }


def _un_m49_evidence(entity_ids: list[str], relationship_ids: list[str]) -> dict[str, Any]:
    return {
        "id": UN_M49_EVIDENCE_ID,
        "record_type": "evidence",
        "status": "published",
        "source_type": "government_registry",
        "title": "UN M49 Standard Country or Area Codes for Statistical Use -- Africa and Americas Groupings",
        "source_name": "United Nations Statistics Division",
        "source_url": "https://unstats.un.org/unsd/methodology/m49/",
        "published_date": None,
        "captured_date": "2026-09-01",
        "summary": (
            "The UN M49 standard defines Africa and the Americas as standard continental/regional "
            "groupings, including Northern America (itself already covering the United States and "
            "Canada in this corpus) and the wider Americas region, and Africa covering Morocco, South "
            "Africa, Zambia, and Zimbabwe among the countries already tracked here."
        ),
        "why_it_matters": (
            "Provides an authoritative, non-inferred basis for expressing which trusted Geography "
            "entities already tracked in this corpus are contained within a broader Geography entity "
            "also already tracked here -- used only to source explicit part_of Relationship records "
            "between existing Geography entities, never to infer geography for any Company/Variety/"
            "Evidence record."
        ),
        "submitted_by": "migration/generate_geography_regions_v2.py",
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


def _apac_evidence(entity_ids: list[str], relationship_ids: list[str]) -> dict[str, Any]:
    return {
        "id": APAC_EVIDENCE_ID,
        "record_type": "evidence",
        "status": "published",
        "source_type": "other",
        "title": "APAC (Asia-Pacific) as an Industry/Market-Research Regional Grouping",
        "source_name": "Common industry and market-research convention",
        "published_date": None,
        "captured_date": "2026-09-01",
        "summary": (
            "\"APAC\" is a widely used industry and market-research regional grouping combining Asia "
            "and Oceania for business reporting purposes. It is explicitly NOT a UN M49 statistical "
            "region -- UN M49 classifies Australia under Oceania and China under Asia as two separate "
            "regions. This record documents that distinction and is cited only to source explicit "
            "part_of Relationship records grouping Australia and China under a geography-apac entity "
            "for editorial/reporting purposes."
        ),
        "why_it_matters": (
            "Lets the application offer an APAC regional view (as requested for the intelligence front "
            "page) without misrepresenting an editorial business grouping as a national-statistics "
            "standard, and without inferring geography membership at query time from free text."
        ),
        "submitted_by": "migration/generate_geography_regions_v2.py",
        "berry_ids": [],
        "geography_ids": entity_ids,
        "entity_ids": entity_ids,
        "fact_ids": [],
        "relationship_ids": relationship_ids,
        "strategic_question_ids": [],
        "tags": ["reference", "geography", "structural"],
        "priority": {
            "reading": {"level": "none", "rationale": "Structural reference data, not a competitive-intelligence development."},
            "testing": {"level": "none", "rationale": "Not applicable to a geographic reference convention."},
            "commercial_position": {"level": "none", "rationale": "Not applicable."},
            "monitoring": {"level": "none", "rationale": "A stable industry convention; not a recurring monitoring target."},
        },
    }


def _append_unique(values: list[Any], new_value: Any) -> list[Any]:
    return values if new_value in values else [*values, new_value]


def run(*, data_dir: Path, dry_run: bool) -> dict[str, Any]:
    geographies = _load_geographies(data_dir)
    existing_part_of = _load_existing_part_of(data_dir)

    new_continent_ids = [gid for gid in NEW_CONTINENTS if gid not in geographies]

    valid_pairs: list[tuple[str, str, str]] = []
    skipped_existing: list[tuple[str, str]] = []
    rejected_conflicting_parent: list[tuple[str, str, str]] = []
    rejected_cycle: list[tuple[str, str]] = []

    for subject, (obj, evidence_id) in REGION_EDGES.items():
        if subject not in geographies and subject not in new_continent_ids:
            raise SystemExit(f"unknown subject geography id: {subject}")
        if obj not in NEW_CONTINENTS:
            raise SystemExit(f"unknown target continent id: {obj}")
        current_parent = existing_part_of.get(subject)
        if current_parent == obj:
            skipped_existing.append((subject, obj))
            continue
        if current_parent is not None and current_parent != obj:
            rejected_conflicting_parent.append((subject, obj, current_parent))
            continue
        if _would_cycle(subject, obj, existing_part_of):
            rejected_cycle.append((subject, obj))
            continue
        valid_pairs.append((subject, obj, evidence_id))
        existing_part_of[subject] = obj

    if not dry_run:
        for continent_id in new_continent_ids:
            _write_json(
                data_dir / "entities" / "geographies" / f"{continent_id}.json",
                _continent_entity(continent_id, NEW_CONTINENTS[continent_id]),
            )

    un_m49_pairs = [(s, o) for s, o, e in valid_pairs if e == UN_M49_EVIDENCE_ID]
    apac_pairs = [(s, o) for s, o, e in valid_pairs if e == APAC_EVIDENCE_ID]

    relationships = [_relationship(s, o, e) for s, o, e in valid_pairs]

    if not dry_run:
        for relationship in relationships:
            rel_path = data_dir / "relationships" / f"{relationship['id']}.json"
            _write_json(rel_path, relationship)

        if un_m49_pairs:
            entity_ids = sorted({*(s for s, _o in un_m49_pairs), *(o for _s, o in un_m49_pairs)})
            relationship_ids = [f"rel-{s.removeprefix('geography-')}-part-of-{o.removeprefix('geography-')}" for s, o in un_m49_pairs]
            evidence_path = data_dir / "evidence" / f"{UN_M49_EVIDENCE_ID}.json"
            if evidence_path.is_file():
                existing_evidence = _read_json(evidence_path)
                for rid in relationship_ids:
                    existing_evidence["relationship_ids"] = _append_unique(existing_evidence.get("relationship_ids") or [], rid)
                for eid in entity_ids:
                    existing_evidence["entity_ids"] = _append_unique(existing_evidence.get("entity_ids") or [], eid)
                    existing_evidence["geography_ids"] = _append_unique(existing_evidence.get("geography_ids") or [], eid)
                _write_json(evidence_path, existing_evidence)
            else:
                _write_json(evidence_path, _un_m49_evidence(entity_ids, relationship_ids))

        if apac_pairs:
            entity_ids = sorted({*(s for s, _o in apac_pairs), *(o for _s, o in apac_pairs)})
            relationship_ids = [f"rel-{s.removeprefix('geography-')}-part-of-{o.removeprefix('geography-')}" for s, o in apac_pairs]
            evidence_path = data_dir / "evidence" / f"{APAC_EVIDENCE_ID}.json"
            if evidence_path.is_file():
                existing_evidence = _read_json(evidence_path)
                for rid in relationship_ids:
                    existing_evidence["relationship_ids"] = _append_unique(existing_evidence.get("relationship_ids") or [], rid)
                for eid in entity_ids:
                    existing_evidence["entity_ids"] = _append_unique(existing_evidence.get("entity_ids") or [], eid)
                    existing_evidence["geography_ids"] = _append_unique(existing_evidence.get("geography_ids") or [], eid)
                _write_json(evidence_path, existing_evidence)
            else:
                _write_json(evidence_path, _apac_evidence(entity_ids, relationship_ids))

        # Reload geography paths in case new continent entities were just written.
        geographies = _load_geographies(data_dir)
        for subject, obj, evidence_id in valid_pairs:
            rel_id = f"rel-{subject.removeprefix('geography-')}-part-of-{obj.removeprefix('geography-')}"
            for geography_id in (subject, obj):
                entity_path = geographies[geography_id]
                entity = _read_json(entity_path)
                entity["relationship_ids"] = _append_unique(entity.get("relationship_ids") or [], rel_id)
                entity["evidence_ids"] = _append_unique(entity.get("evidence_ids") or [], evidence_id)
                _write_json(entity_path, entity)

    return {
        "new_continent_entities": new_continent_ids,
        "written_relationships": [f"rel-{s.removeprefix('geography-')}-part-of-{o.removeprefix('geography-')}" for s, o, _e in valid_pairs],
        "skipped_existing": skipped_existing,
        "rejected_conflicting_parent": rejected_conflicting_parent,
        "rejected_cycle": rejected_cycle,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run(data_dir=args.data_dir, dry_run=args.dry_run)
    print(f"{'[dry-run] ' if args.dry_run else ''}new continent entities: {result['new_continent_entities']}")
    print(f"written relationships: {result['written_relationships']}")
    print(f"skipped (already present): {result['skipped_existing']}")
    print(f"rejected (conflicting existing parent): {result['rejected_conflicting_parent']}")
    print(f"rejected (would create a cycle): {result['rejected_cycle']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
