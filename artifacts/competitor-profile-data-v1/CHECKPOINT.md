# Competitor Profile Data Service V1 — checkpoint (2026-09-15)

Branch: `feature/competitor-profile-data-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-profile-data-v1`,
based on `4bff239967036542a5a4ee67d39d1d86d43d1ee6` (Competitor Identity
and Genetics Verification V1's published checkpoint). No merge, push,
deploy, collection, or canonical-data change performed.

## What was built

1. **`app/services/competitor_profile.py`** — `build_competitor_profile()`,
   the one reusable profile view model, plus `profile_completeness()`.
   Pure composition: reuses `competitor_registry.py` (classification,
   monitoring maturity, bidirectional genetics), `competitor_landscape.py`
   (`_data_gaps`/`selected_company_detail`/`LandscapeFilters`/
   `filters_to_query` — read-only imports, that module itself untouched),
   and `company_workspace._company_portfolio_roles` (verified Variety
   relationships). Zero new discovery, zero new canonical writes.
2. **`data/imports/competitor-profile-data-2026-09-15/profile-completeness-audit.json`**
   — all 33 roster entries, each with its 10-dimension completeness map,
   unresolved gaps, and genetics/variety counts.
3. **`docs/v2/COMPETITOR-PROFILE-DATA-V1.md`** — the full contract for a
   future UI-adoption mission.
4. **`tests/test_competitor_profile_v1.py`** — 29 focused tests.
5. This checkpoint and `NEXT-AGENT-PROMPT.md`.
6. `scripts/_gen_competitor_profile_audit_v1.py` — the kept, non-runtime
   generator that produced artifact 2.

## Verification

- Focused: `tests/test_competitor_profile_v1.py` (29) +
  `tests/test_competitor_registry_v1.py` +
  `tests/test_competitor_identity_genetics_verification_v1.py`: **94
  passed** (`focused-tests.txt`). A broader sweep also run for safety
  (`test_entity_identity_integrity.py`, `test_competitor_landscape_v1.py`):
  129 passed combined, no regressions.
- `scripts/validate_records.py`: **all validated records passed**
  (`record-validation.txt`).
- Full suite was **not** run, per this mission's explicit scope.
- `test_service_never_mutates_canonical_data` (in the new test file)
  confirms via `git status --porcelain` that `data/entities/`,
  `data/relationships/`, `data/evidence/`, and
  `data/configuration/sources.json` are untouched by this mission.

## Required statements

**PROFILE ROSTER: 33/33**
**NON-COMPANY ENTITIES SUPPORTED: YES** (brand — Ozblu; breeding_program —
UC Davis; both verified with correct routes and populated
genetics/monitoring/completeness sections)
**NEW CANONICAL FACTS INVENTED: 0**

## Tallies

- Profiles returned: 33/33.
- Entity types supported: `company`, `brand`, `breeding_program`.
- Complete profiles (all applicable dimensions `present`): 0/33 — an
  honest reflection of the underlying data (most entries legitimately
  lack 3 of 4 berry tiers, many lack strategic priority), not a defect.
- Profiles with at least one explicit gap: 33/33, each gap traceable to
  `competitor_landscape._data_gaps`'s own real detection logic.
- Provisional identities (status `unverified`): 9, unchanged from the
  prior mission — this mission promoted none and demoted none.
- Genetics relationships: 1 active/licensed (AgroBerries↔Mountain Blue
  Orchards), 2 pending/disputed (Fruitist/Agrovision↔Fall Creek,
  California Giant↔Fall Creek), all correctly resolved bidirectionally
  and with review state/confidence intact in every profile that touches
  them.
- Monitoring facets: 5 independent booleans per profile
  (`entity_represented`, `discovery_configured`, `discovery_operational`,
  `readable_content_acquired`, `current_coverage_available`), verified
  never collapsed into one flag.
- Canonical data changed: 0 files under `data/entities/`,
  `data/relationships/`, `data/evidence/`, or
  `data/configuration/sources.json`.
- Application-data mutations: 0 (no `inbox/` writes; no Source run; no
  static build performed or required by this mission).

## What is deliberately NOT done here

- No UI, route, or template was built or modified.
- No modification to `app/services/competitor_landscape.py` (Grok's
  `/competitors` module) — only read-only imports of its pure functions.
- No modification to acquisition code, Source records, Source Health
  presentation, Today/feed UI, or the Daily Intelligence Briefing
  prototype.
- No new Variety entity or relationship — `verified_variety_relationships`
  only surfaces what already exists via the real, pre-existing role-bucket
  relationships.
- No web research performed; every fact in every profile traces to
  already-committed data from the two prior missions in this chain.

## Next concrete steps for a UI-adoption mission

1. Read `docs/v2/COMPETITOR-PROFILE-DATA-V1.md` in full before wiring any
   route/template to `build_competitor_profile()`.
2. Render the profile's sections as visually distinct (identity vs.
   classification vs. genetics vs. verified varieties vs. monitoring vs.
   completeness) — do not collapse any two into one badge.
3. Reuse `filtered_landscape_urls` for "see in context" links rather than
   constructing `/competitors` query strings independently.
4. If a future mission adds more provider-level genetics relationships or
   promotes more provisional identities, this service requires no code
   change — it reads current data at call time.
