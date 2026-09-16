"""One-time generation script for Refine Profile Completeness Semantics
V1's 33-entry multidimensional completeness audit. Not part of the app
runtime -- a read-only report over
`app.services.competitor_profile.build_competitor_profile` and
`profile_roster_summary`, writing zero canonical data.

Supersedes (does not overwrite) the prior mission's
`data/imports/competitor-profile-data-2026-09-15/profile-completeness-audit.json`,
which used the old 10-dimension present/missing/not_applicable model. That
file is left untouched -- this mission's own dated import directory holds
the refined 7-concern audit, per this codebase's existing convention that a
re-run/re-model creates a NEW dated directory rather than overwriting
history (see `competitor_registry.load_latest_snapshot`'s own docstring).

Run once from the worktree root:
    ../berry-intelligence-os/.venv/Scripts/python.exe scripts/_gen_profile_completeness_semantics_v1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.competitor_profile import build_competitor_profile, profile_roster_summary
from app.services.competitor_registry import load_reconciliation_matrix

VERIFICATION_DATE = "2026-09-15"
OUTPUT_DIR = ROOT / "data" / "imports" / "profile-completeness-semantics-2026-09-15"


def main() -> None:
    repos = get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR)
    entities = repos.entities.list()
    relationships = repos.relationships.list()
    sources = json.loads((DEFAULT_DATA_DIR / "configuration" / "sources.json").read_text(encoding="utf-8"))
    matrix = load_reconciliation_matrix(DEFAULT_DATA_DIR)
    assert matrix is not None and len(matrix["rows"]) == 33

    profiles = []
    rows = []
    entity_types_seen = set()
    for row in matrix["rows"]:
        profile = build_competitor_profile(
            row["spreadsheet_label"], data_dir=DEFAULT_DATA_DIR, entities=entities,
            sources=sources, relationships=relationships,
        )
        assert profile is not None, row["spreadsheet_label"]
        profiles.append(profile)
        entity_types_seen.add(profile["entity_type"])
        completeness = profile["completeness"]
        rows.append(
            {
                "row_number": row["row_number"],
                "spreadsheet_label": profile["spreadsheet_label"],
                "canonical_entity_id": profile["canonical_entity_id"],
                "entity_type": profile["entity_type"],
                "profile_url": profile["profile_url"],
                "record_integrity": {
                    "status": completeness["record_integrity"]["status"],
                    "failed_checks": [c["check"] for c in completeness["record_integrity"]["failed_checks"]],
                },
                "classification_coverage": {
                    "berry_positions": {
                        berry: block["display"]
                        for berry, block in completeness["classification_coverage"]["berry_positions"].items()
                    },
                    "berry_summary": completeness["classification_coverage"]["berry_summary"],
                    "strategic_priority": completeness["classification_coverage"]["strategic_priority"]["display"],
                    "regions_state": completeness["classification_coverage"]["regions"]["state"],
                    "competitor_types_state": completeness["classification_coverage"]["competitor_types"]["state"],
                    "has_unassigned": completeness["classification_coverage"]["has_unassigned"],
                },
                "identity_verification": completeness["identity_verification"],
                "relationship_knowledge": {
                    "genetics_known": completeness["relationship_knowledge"]["genetics_known"],
                    "verified_variety_relationships_known": completeness["relationship_knowledge"][
                        "verified_variety_relationships_known"
                    ],
                    "parent_brand_relationships_known": completeness["relationship_knowledge"][
                        "parent_brand_relationships_known"
                    ],
                },
                "monitoring_maturity": {
                    "state": completeness["monitoring_maturity"]["state"],
                    "discovery_configured": completeness["monitoring_maturity"]["discovery_configured"],
                    "discovery_operational": completeness["monitoring_maturity"]["discovery_operational"],
                },
                "current_intelligence_coverage": {
                    "state": completeness["current_intelligence_coverage"]["state"],
                    "readable_content_acquired": completeness["current_intelligence_coverage"][
                        "readable_content_acquired"
                    ],
                    "current_coverage_available": completeness["current_intelligence_coverage"][
                        "current_coverage_available"
                    ],
                    "current_usable_coverage_count": completeness["current_intelligence_coverage"][
                        "current_usable_coverage_count"
                    ],
                },
                "actionable_gaps": completeness["actionable_gaps"],
                "ui_flags": completeness["ui_flags"],
            }
        )

    summary = profile_roster_summary(profiles)

    payload = {
        "id": "profile-completeness-semantics-audit-2026-09-15",
        "verification_date": VERIFICATION_DATE,
        "supersedes_model": "data/imports/competitor-profile-data-2026-09-15/profile-completeness-audit.json "
                             "(10-dimension present/missing/not_applicable model, left untouched)",
        "row_count": len(rows),
        "entity_types_supported": sorted(entity_types_seen),
        "roster_summary": summary,
        "note": (
            "Seven separated concerns per row -- record integrity, classification coverage, identity "
            "verification, relationship knowledge, monitoring maturity, current intelligence coverage, and "
            "actionable gaps -- never collapsed into one 'N/33 complete' percentage. Unknown/Unassigned "
            "classifications, provisional identities, and monitoring/coverage gaps are counted honestly in "
            "roster_summary but never treated as record defects; only "
            "roster_summary.missing_required_data/invalid_reference/blocking_profile_defects represent "
            "genuine structural problems."
        ),
        "rows": rows,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "profile-completeness-semantics-audit.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote profile-completeness-semantics-audit.json: {len(rows)} rows, "
        f"{summary['structurally_valid']} structurally valid, "
        f"{summary['missing_required_data']} missing_required_data, "
        f"{summary['invalid_reference']} invalid_reference, "
        f"{summary['blocking_profile_defects']} blocking_profile_defects, "
        f"entity types: {sorted(entity_types_seen)}"
    )


if __name__ == "__main__":
    main()
