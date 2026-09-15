# Continue Competitor Profile Data Service work — UI adoption

Work in `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-profile-data-v1`,
branch `feature/competitor-profile-data-v1`. Read
`artifacts/competitor-profile-data-v1/CHECKPOINT.md` and
`docs/v2/COMPETITOR-PROFILE-DATA-V1.md` first. This branch is the data
contract only — no UI exists yet for it.

## Settled facts — do not re-derive

1. `app.services.competitor_profile.build_competitor_profile()` returns a
   profile for all 33 roster entries, keyed by canonical_entity_id or
   spreadsheet_label. Verified for all three entity types present in the
   roster: `company`, `brand` (Ozblu), `breeding_program` (UC Davis).
2. `profile_completeness()` returns 10 fixed, independent dimensions —
   `present`/`missing`/`not_applicable`, never a blended score.
3. Genetics state is exactly as Competitor Identity and Genetics
   Verification V1 left it: 1 active/licensed, 2 pending/disputed, 19
   withheld. This mission changed none of it.
4. 94+ focused tests pass; `scripts/validate_records.py` passes; zero
   canonical files were touched (verified by a test that checks
   `git status --porcelain` on the relevant data directories).

## Integration notes for whoever builds the UI

- `competitor_profile.py` deliberately imports read-only from
  `competitor_landscape.py` (Grok's module) rather than duplicating its
  gap-detection or filter-query logic — if that module's shape changes,
  re-check `_data_gaps`, `selected_company_detail`, `LandscapeFilters`,
  and `filters_to_query` are still importable with the same signatures.
- `_company_portfolio_roles` (imported from `company_workspace.py`) is a
  private helper reused across modules already in this codebase — this is
  consistent with existing convention (see `variety_workspace.py`'s own
  cross-module private-helper reuse), not a new pattern.
- A profile's `profile_url` is derived to match
  `CompetitorLandscapeAdapter._row_from_entry`'s own derivation exactly —
  if that derivation ever changes, update `_profile_url_for()` in lockstep
  so a profile page and a landscape row never point to different URLs for
  the same entity.

## Next concrete steps, in order

1. Design and build the actual drill-down UI/route that calls
   `build_competitor_profile()` — out of this branch's scope entirely.
2. Decide where a profile page should live in navigation relative to the
   existing `/entities/{entity_type}/{entity_id}` generic profile and the
   `/competitors` landscape grid — this branch does not prescribe that.
3. If UI work surfaces a real field gap in the view model (something a
   designer needs that `build_competitor_profile()` doesn't return),
   extend the service function additively — do not fork a second profile
   builder.

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-profile-data-v1`
per command. `scripts/_gen_competitor_profile_audit_v1.py` is a kept,
non-runtime report generator — safe to re-run any time, always overwrites
its own single output file, touches nothing else.
