# Continue Berry Intelligence OS work — Profile Completeness UI adoption

Work in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-profile-completeness-semantics-v1`,
branch `fix/profile-completeness-semantics-v1`. Read
`artifacts/profile-completeness-semantics-v1/CHECKPOINT.md`,
`artifacts/profile-completeness-semantics-v1/UI-CONSUMPTION-NOTES.md`, and
`docs/v2/PROFILE-COMPLETENESS-SEMANTICS-V1.md` first. This branch is a
service/audit/test/documentation refinement only — no UI exists yet for
either the base profile view model or its refined completeness report.

## Settled facts — do not re-derive

1. `app.services.competitor_profile.build_competitor_profile()` still
   returns a profile for all 33 roster entries exactly as Competitor
   Profile Data Service V1 established — this mission did not change that
   shape.
2. `profile["completeness"]` is now a 7-concern report: `record_integrity`,
   `classification_coverage`, `identity_verification`,
   `relationship_knowledge`, `monitoring_maturity`,
   `current_intelligence_coverage`, `actionable_gaps`, plus `ui_flags`.
   **Only `record_integrity.status != "structurally_valid"` ever blocks
   stakeholder display.**
3. All 33 profiles are `structurally_valid` as of this audit (0 missing
   required data, 0 invalid references, 0 blocking defects) — the
   roster's real gaps (32 with unassigned classification, 9 provisional
   identities, 18 lacking genetics, 25 without a configured source, 33
   without current usable coverage) are honestly visible and do not
   affect that count.
4. `app.services.competitor_profile.profile_roster_summary(profiles)` is
   the new multidimensional roster-level summary — use it, never
   re-derive a single "X% complete" number.
5. 147 focused tests pass (`tests/test_competitor_profile_v1.py` +
   `tests/test_profile_completeness_semantics_v1.py` +ancestor registry/
   identity/landscape tests); `scripts/validate_records.py` passes; zero
   canonical files were touched (verified by a test that checks
   `git status --porcelain` on the relevant data directories).

## Integration notes for whoever builds the UI

- `_record_integrity`, `_classification_coverage`,
  `_identity_verification_state`, `_relationship_knowledge`,
  `_monitoring_maturity_concern`, `_current_intelligence_coverage_concern`,
  and `_actionable_gaps` are private, composed inside
  `profile_completeness()` — a UI should consume the public
  `profile["completeness"]` dict, not call these directly.
- `completeness.identity_verification.state`/`profile["identity"]
  ["verification_state"]` reuses `app.services.entity_identity`'s
  duplicate/retired-reference detection — if that module's redirect/audit
  shape ever changes, re-check `_identity_verification_state()` in
  lockstep.
- `classification_coverage.berry_positions[berry].display` reuses
  `competitor_landscape.normalize_tier_status` — if that normalizer's
  alias table changes (e.g. someone finally adds `"not_applicable"` with
  an underscore), re-verify
  `tests/test_profile_completeness_semantics_v1.py::test_not_applicable_remains_distinct_from_unknown_unassigned_and_missing`
  still passes with the spelling it uses today (`"n/a"`).
- A profile's `profile_url`/`filtered_landscape_urls` derivation is
  unchanged from Competitor Profile Data Service V1 — still mirrors
  `CompetitorLandscapeAdapter._row_from_entry`'s own derivation exactly.

## Next concrete steps, in order

1. Design and build the actual drill-down UI/route that calls
   `build_competitor_profile()` and renders `completeness` — out of this
   branch's scope entirely. Follow
   `artifacts/profile-completeness-semantics-v1/UI-CONSUMPTION-NOTES.md`'s
   section-by-section suggestions.
2. Decide where a profile page should live in navigation relative to the
   existing `/entities/{entity_type}/{entity_id}` generic profile and the
   `/competitors` landscape grid — this branch does not prescribe that
   (Competitor Profile Data Service V1 didn't either).
3. If UI work surfaces a real field gap in the view model or the
   completeness report, extend `competitor_profile.py` additively — do
   not fork a second profile builder or a second completeness function.
4. If a future mission promotes more provisional identities, resolves
   more duplicate-review findings, adds genetics relationships, or
   configures more sources, this service requires no code change — it
   reads current data at call time. Re-run
   `scripts/_gen_profile_completeness_semantics_v1.py` to refresh the
   audit artifact if a point-in-time snapshot is needed again (it writes
   a NEW dated directory each time it is meaningfully re-run with a
   different `VERIFICATION_DATE`; today's run reused `2026-09-15` since
   it happened the same day as this mission).

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-profile-completeness-semantics-v1`
per command. `scripts/_gen_profile_completeness_semantics_v1.py` and the
older `scripts/_gen_competitor_profile_audit_v1.py` are both kept,
non-runtime report generators — safe to re-run any time, each always
overwrites only its own single output file, touches nothing else.
