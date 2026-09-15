# Competitor Profile Data Service V1

**Status:** Service/composition layer only. No UI was built — this module
is the reusable data contract a future company/competitor "drill-down"
surface should call, not a route or template of its own.

**Branch:** `feature/competitor-profile-data-v1`
**Base:** `4bff239967036542a5a4ee67d39d1d86d43d1ee6` (Competitor Identity and
Genetics Verification V1's completed, published checkpoint)
**Verification date:** 2026-09-15

## 1. What this is and is not

- **Is:** one function, `app.services.competitor_profile.build_competitor_profile()`,
  that returns a single, coherent view model for one of the 33 roster
  entities — regardless of whether it is a company, a brand, a breeding
  program, or a still-provisional identity.
- **Is not:** a new database, a new UI, a new discovery/collection engine,
  or a new source of canonical truth. Every field is composed from
  already-existing, already-tested services:
  - `app.services.competitor_registry` — classification (frozen
    snapshot), monitoring maturity, bidirectional genetics lookups.
  - `app.services.competitor_landscape` — per-row data-gap detection
    (`_data_gaps`/`selected_company_detail`) and the exact filter-query
    builder the `/competitors` page itself uses
    (`LandscapeFilters`/`filters_to_query`), reused so a profile's links
    can never diverge from that page's own behavior.
  - `app.services.company_workspace._company_portfolio_roles` — the
    existing owns/develops/licenses/markets/grows/distributes role-bucket
    walk, reused for verified Company/Brand/Program-to-Variety
    relationships (works for any subject entity id, not just
    entity_type `company`, despite the module's name).

No new web research, no new canonical entity, relationship, Variety, or
Source record was created by this mission.

## 2. The view model

```python
from pathlib import Path
from app.services.competitor_profile import build_competitor_profile

profile = build_competitor_profile(
    "California Giant",  # or a canonical_entity_id -- both resolve identically
    data_dir=Path("data"),
    entities=all_entities, sources=all_sources, relationships=all_relationships,
)
```

Returns `None` only if the identifier matches no roster row at all. A
roster row whose entity is otherwise unresolved, provisional, or
non-company still returns a full profile — that state is represented
*honestly inside* the profile (`identity.entity_found`, `identity.status`),
never by returning nothing.

Top-level shape (each dimension kept structurally separate, per the
mission's explicit "do not collapse" rule):

| Field | Source | Never confused with |
|---|---|---|
| `canonical_entity_id`, `display_name`, `spreadsheet_label`, `aliases`, `entity_type` | entity record + reconciliation row | — |
| `identity` (`status`, `confidence`, `verdict`, `reason`, `evidence_urls`, `verification_date`) | `attributes.identity_verification_<date>` (Competitor Identity and Genetics Verification V1), falling back to `resolution_status` | `classification` (internal, never externally verified) |
| `classification` (`competitor_type`, `strategic_priority`, `regions`, `berry_tier`, `snapshot_date`) | frozen `snapshot.json` via the reconciliation matrix — **read-only, never modified** | `identity` (externally verified facts) |
| `parent_brand_relationships` | real `owns`/`part_of`/`partners_with` Relationship records | `genetics` (provider-level, not corporate-structure) |
| `genetics` (`as_company`, `as_provider`) | `genetics_relationships_for_company`/`companies_for_genetics_provider`, bidirectional | `verified_variety_relationships` (never the same edge) |
| `verified_variety_relationships` | `_company_portfolio_roles` — real, already-trusted Company/Brand/Program→Variety edges | `genetics` (pending, provider-level assertions) |
| `monitoring.maturity` | `monitoring_maturity_for_entity` — 5 independent booleans + counts | `completeness` (a different, profile-specific audit) |
| `unresolved_data_gaps` | `competitor_landscape.selected_company_detail`'s own `_data_gaps` | — |
| `completeness` | this module's own `profile_completeness()`, see §3 | never a single score |
| `profile_url` | mirrors `CompetitorLandscapeAdapter._row_from_entry`'s own derivation exactly | — |
| `filtered_landscape_urls` | one `/competitors?...` link per berry, built with the landscape page's own `LandscapeFilters`/`filters_to_query` | — |

## 3. Profile completeness — dimension-by-dimension, never a score

`profile_completeness()` reports exactly 10 fixed dimensions
(`COMPLETENESS_DIMENSIONS`): `identity`, `aliases`, `classifications`,
`berry_positions`, `regions`, `genetics`, `source_configuration`,
`operational_discovery`, `readable_content`, `current_coverage`. Each is
independently `present`, `missing`, or `not_applicable` — **the latter two
are never conflated**: `not_applicable` means the dimension legitimately
does not apply yet (e.g. no genetics assertion exists either way for this
company, and no other gap was found either), while `missing` means a real,
addressable gap. There is no blended score, no "strategic completeness
index," and no ranking across competitors — per the mission's explicit
prohibition on inventing one.

Audited across all 33 roster entries at
`data/imports/competitor-profile-data-2026-09-15/profile-completeness-audit.json`:
0 of 33 are fully complete on every applicable dimension — an honest
reflection of the underlying data (most entries are missing 3 of 4 berry
tiers by design, since the spreadsheet only ever populated the berries
relevant to that company), not a defect in this service.

## 4. Non-company support

All 33 roster entries return a profile. Verified this mission for the two
non-company entity types actually present in the roster:

- **Ozblu** (`entity_type: "brand"`) → `/entities/brand/brand-ozblu`,
  correct route, genetics/monitoring/completeness all populate normally.
- **UC Davis** (`entity_type: "breeding_program"`) →
  `/entities/breeding_program/breeding_program-uc-davis-strawberry`,
  same.
- **University of Arkansas / University of Florida** remain
  `entity_type: "company"` (a pre-existing convention from before this
  mission, not changed here) and profile identically to any other company.

No part of `build_competitor_profile()` requires `entity_type == "company"`
— every underlying call (`monitoring_maturity_for_entity`,
`genetics_relationships_for_company`, `_company_portfolio_roles`) accepts
any entity id regardless of type.

## 5. Genetics preserved exactly as verified

- **AgroBerries ↔ Mountain Blue Orchards**: `licenses` / `active` / `high`
  confidence, both directions resolve (`as_company` on AgroBerries'
  profile, `as_provider` on Mountain Blue's).
- **Fruitist/Agrovision ↔ Fall Creek** and **California Giant ↔ Fall
  Creek**: `partners_with` / `disputed` / `medium` confidence, unchanged.
- All 19 withheld handwritten mappings remain withheld — this service
  reads relationships as they exist; it creates none.
- `genetics` (provider-level) and `verified_variety_relationships`
  (Variety-level) are structurally separate dict keys on every profile —
  confirmed by test that the AgroBerries↔MBO company-to-company edge never
  appears inside `verified_variety_relationships`.

## 6. What a future UI-adoption mission should do

- Call `build_competitor_profile()` from whatever route/template renders a
  competitor drill-down; do not re-derive any of its fields independently.
- Render `identity`, `classification`, `genetics`,
  `verified_variety_relationships`, `monitoring`, and `completeness` as
  visually distinct sections — collapsing any two into one badge/label
  would violate this mission's (and the underlying data's) trust
  separation.
- Use `filtered_landscape_urls` for "see this company in context" links
  rather than constructing `/competitors` query strings independently.
- Treat `completeness.dimensions` as a checklist, never as a score to sort
  or rank competitors by.
