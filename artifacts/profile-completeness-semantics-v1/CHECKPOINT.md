# Refine Profile Completeness Semantics V1 — checkpoint (2026-09-15)

Branch: `fix/profile-completeness-semantics-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-profile-completeness-semantics-v1`,
based on `516f1ee74a369fb59e0563341a0b9d75da6edf9e` (Competitor Profile Data
Service V1's published checkpoint). No merge, push, deploy, collection, or
canonical-data change performed beyond what is listed below.

## What was built

1. **`app/services/competitor_profile.py`** — refactored
   `profile_completeness()` from a flat 10-dimension present/missing/
   not_applicable model into 7 separated concerns: `record_integrity`,
   `classification_coverage`, `identity_verification`,
   `relationship_knowledge`, `monitoring_maturity`,
   `current_intelligence_coverage`, `actionable_gaps`, plus a `ui_flags`
   block and a new `profile_roster_summary()` function for the roster-level
   multidimensional summary. Added a small, explicit vocabulary
   (`INTEGRITY_STATES`, `IDENTITY_VERIFICATION_STATES`, `FIELD_STATES`,
   `GAP_CATEGORIES`, `GAP_SEVERITIES`) reusing existing repository
   conventions (entity `status` enum; `competitor_landscape`'s own
   `TIER_STATUS_VALUES`/`PRIORITY_VALUES`/`normalize_tier_status`/
   `normalize_priority`) wherever they already answered the question, and
   inventing new vocabulary only where nothing already modeled the
   concept. Also enriched `_identity_block()` with
   `verification_state`/`verification_state_reason`, reusing
   `app.services.entity_identity.load_identity_redirects/redirect_map/
   is_retired_entity/merged_into_id/audit_entity_identity` for duplicate/
   retired-reference detection rather than inventing a new mechanism.
   `build_competitor_profile()`'s own view-model shape is otherwise
   unchanged — every field Competitor Profile Data Service V1 established
   (`identity`, `classification`, `parent_brand_relationships`, `genetics`,
   `verified_variety_relationships`, `monitoring`, `unresolved_data_gaps`,
   `profile_url`, `filtered_landscape_urls`) still means exactly what it
   did before.
2. **`data/imports/profile-completeness-semantics-2026-09-15/profile-completeness-semantics-audit.json`**
   — all 33 roster entries re-audited under the refined model. The prior
   mission's `data/imports/competitor-profile-data-2026-09-15/profile-completeness-audit.json`
   is left untouched (new dated import directory, per this codebase's
   existing snapshot-history convention).
3. **`docs/v2/PROFILE-COMPLETENESS-SEMANTICS-V1.md`** — the full semantic
   contract for the refined model (new).
4. **`docs/v2/COMPETITOR-PROFILE-DATA-V1.md`** — §3 and §6 updated to point
   at the new doc; §§1-2, 4-5 (the base view-model contract) left
   unchanged since this mission did not touch that shape.
5. **`tests/test_competitor_profile_v1.py`** — 5 tests updated for the new
   `completeness` shape (old `COMPLETENESS_DIMENSIONS`/flat-dict tests
   replaced with equivalents against the new 7-concern shape); all other
   24 tests (roster resolution, genetics directionality, monitoring
   facets, URLs, aliases, etc.) unchanged and still passing against the
   unchanged view-model fields.
6. **`tests/test_profile_completeness_semantics_v1.py`** — 18 new focused
   tests proving every proof point this mission's own TESTS section
   requires (see §"Verification" below).
7. **`scripts/_gen_profile_completeness_semantics_v1.py`** — the kept,
   non-runtime generator that produced artifact 2 (supersedes, does not
   replace, `scripts/_gen_competitor_profile_audit_v1.py`, which still
   exists and still works against the old model for historical
   reproducibility).
8. This checkpoint, `NEXT-AGENT-PROMPT.md`, and `UI-CONSUMPTION-NOTES.md`.

## Verification

- Focused: `tests/test_competitor_profile_v1.py` (29) +
  `tests/test_profile_completeness_semantics_v1.py` (18, new) +
  `tests/test_competitor_registry_v1.py` +
  `tests/test_competitor_identity_genetics_verification_v1.py` +
  `tests/test_entity_identity_integrity.py` +
  `tests/test_competitor_landscape_v1.py`: **147 passed**
  (`focused-tests.txt`).
- `scripts/validate_records.py`: **all validated records passed**
  (`record-validation.txt`).
- Full suite was **not** run, per this mission's explicit scope.
- The new focused test file proves, concretely:
  - All 33 profiles still return (`test_all_33_profiles_still_return_under_the_refined_model`).
  - All four berry slots remain present as keys regardless of value
    (`test_all_four_berry_slots_remain_present_after_refinement`).
  - Unknown/Unassigned is never `missing_required`
    (`test_unknown_unassigned_berry_slot_is_not_missing_required`).
  - Not Applicable remains distinct from Unknown/Unassigned and from
    `missing_required` (`test_not_applicable_remains_distinct_from_unknown_unassigned_and_missing`).
  - An unassigned strategic priority is not malformed data
    (`test_unassigned_strategic_priority_is_not_malformed_data`).
  - A provisional identity remains explicit and never malformed
    (`test_provisional_identity_remains_explicit_and_never_malformed`).
  - Monitoring gaps remain separate from record integrity
    (`test_monitoring_gaps_remain_separate_from_record_integrity`).
  - Missing required data (a blank display name, a dropped berry key) is
    still detected and blocks display
    (`test_missing_display_name_is_detected_as_missing_required_data`,
    `test_missing_berry_slot_is_detected_as_missing_required_data`).
  - Invalid references (an unresolved entity, a dangling genetics
    relationship) still fail integrity and block display
    (`test_unresolved_entity_is_invalid_reference_and_blocks_display`,
    `test_dangling_genetics_reference_fails_integrity`).
  - Non-company entities (Ozblu/UC Davis) receive correct applicability —
    `structurally_valid` with no entity_type-driven check failure
    (`test_non_company_entity_types_get_correct_applicability`).
  - Structural rendering blockers are deterministic — the same input
    produces byte-identical integrity/gap output on repeat calls
    (`test_structural_rendering_blockers_are_deterministic`).
  - No canonical record changes, verified via `git status --porcelain`
    across every canonical data path
    (`test_no_canonical_record_changes_from_this_mission`).
  - Only genuine integrity errors ever set
    `blocks_stakeholder_display=True`
    (`test_only_integrity_failures_ever_block_stakeholder_display`).
  - The roster-level summary is multidimensional, never a single
    percentage (`test_roster_summary_never_collapses_to_a_single_percentage`).

## Required statements

**PROFILE ROSTER: 33/33**
**UNKNOWN/UNASSIGNED TREATED AS MALFORMED: NO**
**MONITORING GAP TREATED AS SCHEMA FAILURE: NO**
**CANONICAL DATA CHANGES: 0**

## Tallies (`profile_roster_summary()` across all 33)

- Profiles returned: 33/33.
- Structurally valid: 33/33.
- Missing required data: 0/33.
- Invalid reference: 0/33.
- Blocking profile defects: 0/33.
- Profiles with at least one unassigned internal classification: 32/33
  (honest — most entries legitimately lack most of their 4 berry tiers by
  spreadsheet design, and/or lack a strategic priority; never a defect).
- Provisional identities (`entity.status == "unverified"`): 9/33 —
  unchanged from the prior mission; this mission promoted none and
  demoted none.
- Profiles lacking genetics information: 18/33 (real, honestly reported —
  most of the roster simply has no genetics-provider relationship
  recorded yet).
- Profiles without a configured source: 25/33.
- Profiles without operational discovery: 33/33 (no linked Source has
  ever completed a successful run in this runtime, per the existing,
  unchanged monitoring-maturity facts — an operational gap, not a
  defect this mission introduced or hides).
- Profiles without readable coverage: 33/33.
- Profiles without current usable coverage: 33/33.

None of the operational/monitoring tallies above degrade
`structurally_valid`, which stays 33/33 — exactly the point of this
mission.

## What is deliberately NOT done here

- No UI, route, or template was built or modified.
- No modification to `app/services/competitor_landscape.py` (Grok's
  `/competitors` module) — only additional read-only imports
  (`normalize_tier_status`, `normalize_priority`) alongside the ones
  Competitor Profile Data Service V1 already used.
- No modification to acquisition code, Source records, Source Health
  presentation, Today/feed UI, or the Daily Intelligence Briefing
  prototype.
- No canonical entity, relationship, alias, tier, priority, region,
  genetics relationship, Source, acquisition-outcome, or application
  inbox record was created, modified, or deleted.
- No new Variety entity or relationship.
- No web research performed; every fact in every profile traces to
  already-committed data from the four prior missions in this chain.
- `AGENTS.md` was not modified — the base commit for this mission
  (Competitor Profile Data Service V1's own checkpoint) had not itself
  appended a durable-rules paragraph there, and this mission's own spec
  did not request one; the mission-1 paragraph (Company + Genetics
  Relationships V1) remains the most recent entry.

## Next concrete steps for a UI-adoption mission

See `UI-CONSUMPTION-NOTES.md` for the full breakdown. In short:

1. Read `docs/v2/PROFILE-COMPLETENESS-SEMANTICS-V1.md` in full before
   rendering any completeness-derived badge/section.
2. Use `completeness.ui_flags` for simple badge/icon logic rather than
   re-deriving those booleans independently.
3. Only ever treat a profile as non-renderable when
   `completeness.record_integrity.status != "structurally_valid"` —
   every other gap (`classification_coverage`, `identity_verification`,
   `relationship_knowledge`, `monitoring_maturity`,
   `current_intelligence_coverage`) is real and worth surfacing, but must
   render normally.
4. Use `profile_roster_summary()` for any roster-level dashboard number —
   never re-derive a single "X% complete" figure independently.
