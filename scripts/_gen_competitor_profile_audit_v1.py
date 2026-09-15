"""One-time generation script for Competitor Profile Data Service V1's
33-entry completeness audit artifact. Not part of the app runtime -- a
read-only report over `app.services.competitor_profile.build_competitor_profile`,
writing zero canonical data.

Run once from the worktree root:
    ../berry-intelligence-os/.venv/Scripts/python.exe scripts/_gen_competitor_profile_audit_v1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.composition import get_repositories
from app.repositories.paths import DEFAULT_DATA_DIR, SCHEMAS_DIR
from app.services.competitor_profile import build_competitor_profile
from app.services.competitor_registry import load_reconciliation_matrix

VERIFICATION_DATE = "2026-09-15"
OUTPUT_DIR = ROOT / "data" / "imports" / "competitor-profile-data-2026-09-15"


def main() -> None:
    repos = get_repositories(DEFAULT_DATA_DIR, SCHEMAS_DIR)
    entities = repos.entities.list()
    relationships = repos.relationships.list()
    sources = json.loads((DEFAULT_DATA_DIR / "configuration" / "sources.json").read_text(encoding="utf-8"))
    matrix = load_reconciliation_matrix(DEFAULT_DATA_DIR)
    assert matrix is not None and len(matrix["rows"]) == 33

    rows = []
    entity_types_seen = set()
    for row in matrix["rows"]:
        profile = build_competitor_profile(
            row["spreadsheet_label"], data_dir=DEFAULT_DATA_DIR, entities=entities,
            sources=sources, relationships=relationships,
        )
        assert profile is not None, row["spreadsheet_label"]
        entity_types_seen.add(profile["entity_type"])
        rows.append(
            {
                "row_number": row["row_number"],
                "spreadsheet_label": profile["spreadsheet_label"],
                "canonical_entity_id": profile["canonical_entity_id"],
                "entity_type": profile["entity_type"],
                "identity_status": profile["identity"]["status"],
                "identity_confidence": profile["identity"]["confidence"],
                "profile_url": profile["profile_url"],
                "completeness": profile["completeness"]["dimensions"],
                "present_count": profile["completeness"]["present_count"],
                "applicable_count": profile["completeness"]["applicable_count"],
                "missing_count": profile["completeness"]["missing_count"],
                "unresolved_data_gaps": profile["unresolved_data_gaps"],
                "genetics_as_company_count": len(profile["genetics"]["as_company"]),
                "genetics_as_provider_count": len(profile["genetics"]["as_provider"]),
                "verified_variety_role_count": sum(
                    len(v) for v in profile["verified_variety_relationships"]["roles"].values()
                ),
            }
        )

    complete_rows = [r for r in rows if r["missing_count"] == 0]
    gap_rows = [r for r in rows if r["missing_count"] > 0]

    payload = {
        "id": "competitor-profile-completeness-audit-2026-09-15",
        "verification_date": VERIFICATION_DATE,
        "row_count": len(rows),
        "entity_types_supported": sorted(entity_types_seen),
        "complete_profile_count": len(complete_rows),
        "profiles_with_explicit_gaps_count": len(gap_rows),
        "note": (
            "row_count reflects that all 33 roster entries returned a profile view model, not that all 33 "
            "are 'complete' -- completeness is dimension-by-dimension (see each row's `completeness`), never "
            "collapsed into one score. `missing_count` never counts a legitimately not_applicable dimension."
        ),
        "rows": rows,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "profile-completeness-audit.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote profile-completeness-audit.json: {len(rows)} rows, "
          f"{len(complete_rows)} complete, {len(gap_rows)} with explicit gaps, "
          f"entity types: {sorted(entity_types_seen)}")


if __name__ == "__main__":
    main()
