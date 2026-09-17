# Company + Genetics Relationships V1 — checkpoint (2026-09-15)

Branch: `feature/company-genetics-relationships-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-company-genetics-v1`,
based on `bd96fca1231dc97ae4ec3fc316743b0a3f2e8427`. No merge, no push, no
deploy, no production writes performed.

## What was built

1. **33-row spreadsheet snapshot** transcribed from the operator-provided
   screenshot: `data/imports/competitor-registry-2026-09-15/snapshot.json`.
   Every roster label, competitor type, strategic priority, region list
   (verbatim internal codes DOTA/DOA_DANZ/DEMEA), and all four berry-tier
   values preserved, including the honest distinction between a blank cell
   (`"unassigned"`) and `"present"` (never coerced to `tier_3`).
2. **33-row reconciliation matrix**:
   `data/imports/competitor-registry-2026-09-15/reconciliation-matrix.json`.
   16 existing-entity matches (with 3 explicitly documented ambiguity
   resolutions: Costa → the group parent not the genetics subsidiary,
   Fruitist → the operating company Agrovision not a new entity, Ozblu →
   the existing multi-party brand entity), 17 newly-created entities
   (`status: "unverified"`), zero silently-dropped rows.
3. **Handwritten genetics transcription**:
   `data/imports/competitor-registry-2026-09-15/genetics-transcription.json`
   — 22 rows re-read directly from the 5 attached images (not just copied
   from the mission brief's own hint list, though it matches everywhere
   checkable). 3 rows seeded as real, pending-review Relationship records;
   19 withheld with a stated, specific reason each (self-mapping, explicit
   `??`/`???`, illegible name, public-genetics observation with no company
   to point at, or a name outside the mandatory 33-entry roster).
4. **Unresolved-mapping queue**: the 19 withheld rows in their own file for
   a human review pass, `unresolved-mapping-queue.json`.
5. **17 new entity records** under `data/entities/companies/`, all
   `status: "unverified"`, honest minimal descriptions (no fabricated
   company history), roles derived only from the spreadsheet's own
   Competitor Type column.
6. **2 provenance Evidence records** (`status: "in_review"`, never
   published): one for the spreadsheet import, one for the handwritten
   notes.
7. **3 genetics Relationship records** (`predicate: "partners_with"`,
   `status: "disputed"` == pending review, `confidence: "medium"`,
   citing the handwritten-notes Evidence): AgroBerries↔Mountain Blue
   Orchards, Agrovision(Fruitist)↔Fall Creek, California Giant↔Fall Creek.
8. **`app/services/competitor_registry.py`** — the read-only data-contract
   service: `unfiltered_competitor_registry()` (always 33 rows, live entity
   + monitoring resolution over frozen classification), `monitoring_state_for_entity()`
   (6-state honest vocabulary, no fabricated coverage), and bidirectional
   `genetics_relationships_for_company()` / `companies_for_genetics_provider()`.
9. **`docs/v2/COMPANY-GENETICS-RELATIONSHIPS-V1.md`** — the full data
   contract for whoever builds the visual Landscape page next (a
   different, already-existing branch — not touched here).
10. **One durable-rules paragraph appended to `AGENTS.md`** (established
    codebase convention — every mission of this shape gets one).
11. **35 new focused tests** in `tests/test_competitor_registry_v1.py`,
    all passing against the real committed data (not synthetic fixtures).
12. Small additive alias/role updates to 10 pre-existing entities (Costa
    Group Holdings, Hortifrut, brand-ozblu, Plant Sciences Genetics, Wish
    Farms, UC Davis Strawberry Breeding Program, Advanced Berry Breeding,
    BerryWorld, California Giant Berry Farms) — never removed or
    overwrote anything already on those records.
13. `scripts/_gen_competitor_registry_v1.py` — the (kept, documented,
    non-runtime) one-time generation script that produced 1–8 above,
    following this codebase's existing precedent
    (`scripts/generate_geography_regions_v2.py`) of keeping such scripts
    committed and idempotent rather than throwaway.

## Verification

- `scripts/validate_records.py`: **all validated records passed**
  (`artifacts/company-genetics-v1/record-validation.txt`).
- Focused: `tests/test_competitor_registry_v1.py`: **35 passed**
  (`focused-tests.txt`).
- Broader regression sweep (company compare/portfolio, landscape
  rendering, entity identity integrity, source coverage gap closure,
  report builder) to catch any side effect from the alias/role additions:
  **196 passed** (`regression-tests.txt`). No regressions found.
- Full suite was **not** run, per this mission's explicit scope
  ("Run focused tests and record validation. Do not run the full suite").

## Roster reconciliation

**ROSTER RECONCILIATION: 33/33 represented**
**MISSING ROSTER ROWS: 0**

## What is deliberately NOT done here

- No UI. `feature/competitor-landscape-v1` (excluded from this worktree)
  owns the visual Landscape surface; this mission only produced the data
  contract it should read.
- No promotion of any new entity, Evidence, or genetics relationship out
  of its unverified/in_review/disputed (pending-review) state. A human
  must review each before it becomes trusted.
- No web research beyond the two attached source materials — every
  monitoring state, alias, and relationship is either already in this
  graph or came directly from the spreadsheet/handwritten notes.
- No fix to the pre-existing `company-planasa` / `company-planasa-2` /
  `company-plantas-de-navarra` possible duplicate-identity issue spotted
  while reconciling row 23 — flagged in `reconciliation-matrix.json`'s
  ambiguity notes for the entity-identity-integrity workstream, not fixed
  here (out of this mission's scope).
- `company-costa-berry-international` (the genetics subsidiary) was not
  merged, relabeled, or otherwise touched — only cited as a documented
  ambiguity alongside the chosen canonical `company-costa-group-holdings`.

## Next concrete acceptance test for a follow-up session

1. Human spot-check the snapshot transcription against the actual source
   spreadsheet file (not just the screenshot) — the snapshot's own
   `transcription_caveat` field flags this as recommended, not yet done.
2. Human review of the 3 seeded `disputed` genetics relationships and the
   19-row unresolved queue — either promote (flip `status` to `"active"`
   with a real confirming source) or reject; neither should stay
   `disputed` indefinitely without a decision.
3. Whoever picks up `feature/competitor-landscape-v1` should read
   `docs/v2/COMPANY-GENETICS-RELATIONSHIPS-V1.md` §3 before wiring their
   page to `unfiltered_competitor_registry()`.
4. If deeper monitoring coverage for the 17 new + Cal Giant entities is
   wanted, that is real, separate acquisition/collection work (see
   `fix/astra-news-reader`'s own checkpoint for the general state of that
   pipeline) — not something to bolt onto this branch.
