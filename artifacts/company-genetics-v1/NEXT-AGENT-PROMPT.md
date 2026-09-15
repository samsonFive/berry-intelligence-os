# Continue Company + Genetics Relationships work

Work in `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-company-genetics-v1`,
branch `feature/company-genetics-relationships-v1`. Read
`artifacts/company-genetics-v1/CHECKPOINT.md` first. Do not restart the
reconciliation from scratch — it is settled (33/33 represented, 0 missing).

Do not merge, deploy, push, or change production data without explicit
authorization. Do not build the visual Landscape UI here —
`feature/competitor-landscape-v1` (a separate, existing branch) owns that
surface; this branch is data-layer only and should stay that way.

## Settled facts — do not re-derive

1. 33/33 roster labels resolve to a canonical entity (16 existing, 17 new,
   all documented in `data/imports/competitor-registry-2026-09-15/reconciliation-matrix.json`).
2. 3 genetics relationships seeded as pending review (`status: "disputed"`);
   19 handwritten rows deliberately withheld with a stated reason each —
   see `genetics-transcription.json` and `unresolved-mapping-queue.json`.
3. `app/services/competitor_registry.py` is the read contract:
   `unfiltered_competitor_registry()` always returns all 33, distinct from
   Landscape's own filtered "Actors to Watch."
4. 35 focused tests pass (`tests/test_competitor_registry_v1.py`); a
   196-test regression sweep across company/landscape/entity-identity/
   source-coverage tests found no side effects from this mission's alias/
   role additions. `scripts/validate_records.py` passes. Full suite not run
   (out of this mission's stated scope).
5. One known, pre-existing, NOT-fixed-here issue: possible identity
   duplication among `company-planasa` / `company-planasa-2` /
   `company-plantas-de-navarra` — noted in the reconciliation matrix, not
   resolved (belongs to entity-identity-integrity work, a different
   mission scope).

## Next concrete steps, in order

1. Human review pass: spot-check `snapshot.json` against the actual source
   spreadsheet file (only a screenshot was available to the mission that
   built this); review the 3 `disputed` genetics relationships and the
   19-row unresolved queue and make explicit promote/reject decisions —
   do not leave them `disputed` indefinitely by default.
2. If `feature/competitor-landscape-v1` is ready to consume this, read
   `docs/v2/COMPANY-GENETICS-RELATIONSHIPS-V1.md` in full before wiring
   any page to `unfiltered_competitor_registry()`.
3. Do not add new roster entries or genetics relationships without a real
   source (spreadsheet update or new handwritten/photographed notes) — do
   not fabricate to fill gaps in the unresolved queue.
4. If broader monitoring/source coverage for these 33 companies is wanted,
   treat it as acquisition/collection work — see the separate
   `fix/astra-news-reader` branch's own checkpoint for that pipeline's
   general state (76 eligible-but-never-run sources exist across the
   whole registry, of which 8 already link to entities in this roster).

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-company-genetics-v1`
per command. Re-running `scripts/_gen_competitor_registry_v1.py` is
idempotent for existing-entity updates (it only adds missing aliases/roles,
never removes) but will error on `write_json` collisions if new-entity
files already exist from a prior run — read it before re-running.
