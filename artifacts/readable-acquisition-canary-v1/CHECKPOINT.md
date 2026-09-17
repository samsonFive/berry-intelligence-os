# Readable Acquisition Canary V1 — checkpoint (2026-09-15)

Branch: `fix/readable-acquisition-canary-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-readable-acquisition-canary-v1`,
based on `85a157233674ee5cd3d2e358ea02924d3ac04790`
(`integration/competitor-intelligence-wave2`). No merge, push, deploy, or
canonical-data change performed beyond what is listed below.

## Mission

Determine why the integrated published corpus contains zero readable
article bodies; persist useful acquisition failures; repair the
acquisition/extraction path; prove the repair with a tightly capped
canary. Full requirements in the mission brief (not reproduced here).

## What was found (see `ROOT-CAUSE-ANALYSIS.md` for the full trail)

The trusted corpus (`data/evidence/`, 1,272 records) has zero readable
bodies because:

1. Every one of those 1,272 records predates the article-acquisition
   pipeline (`app/services/article_acquisition.py` +
   `app/services/article_refresh.py`) or was captured through a mechanism
   that never fetches a full body.
2. The pipeline itself is correctly built and correctly wired into every
   production entry point (`scripts/run_collection.py`,
   `scripts/run_recent_batch.py`, `scripts/process_discovered_media.py
   --relevance-gate`), persists structured, redacted outcomes
   (`article_acquisition_outcomes.py`, built during the prior
   `astra-repair` mission for TD-114), and Source Health (`/sources`)
   already surfaces those outcomes per source.
3. No readable draft this pipeline has ever produced (in this mission, or
   the prior Wave 1 activation canary, or the `astra-repair` canary) has
   ever been promoted through publication review — a mandatory human gate
   that has simply never been exercised on a body-bearing draft.
4. Two of the five Wave 1 Sources (Oishii Press Feed; a majority of
   Fruitist Newsroom's own "news" items) have a genuine, confirmed,
   permanent, external content-availability limitation — not a bug, not a
   bot wall, not a JS-rendering gap.

**No defect was found in the extraction/acquisition code itself.**
Readable extraction was proven working, live, today, for two of the three
currently-runnable Wave 1 Sources (UF blueberrybreeding, Fruitist
Newsroom) via `fetch_article()` — the exact function the canary and
production collection both call.

## What was built/changed

1. **4 new focused tests** — `tests/test_article_acquisition.py` (+3):
   a real cookie/consent interstitial fixture at the `fetch_article()`
   layer (a real coverage gap — only tested previously via a synthetic
   error at the outcome-persistence layer), and two regression fixtures
   permanently encoding the two live failure patterns discovered against
   real Wave 1 sources (Oishii's headline-only press template; Fruitist's
   CMS-bound-empty rich-text items). `tests/test_article_refresh.py` (+1):
   a direct proof that a successful readable acquisition never creates a
   file under the trusted, canonical evidence store nor calls any
   publish/approve action.
2. **`data/imports/readable-acquisition-canary-2026-09-15/canary-audit.json`**
   — the noncanonical, review-required, redacted (no bodies/HTML) audit
   of this mission's capped canary plus its independent diagnostic
   verification.
3. **`artifacts/readable-acquisition-canary-v1/`** — this checkpoint,
   `ROOT-CAUSE-ANALYSIS.md`, `SOURCE-FUNNEL.md`, `CANARY-RESULTS.md`,
   `TEST-RESULTS.md`, `NEXT-AGENT-PROMPT.md`, plus `focused-tests.txt`,
   `record-validation.txt`, and `canary-raw-report.json` (the full,
   already-redacted per-item raw outcome objects behind
   `canary-audit.json`'s summary).

No file under `app/services/article_acquisition.py`,
`app/services/article_refresh.py`, `app/services/media_discovery.py`,
`app/services/article_acquisition_outcomes.py`, `app/services/source_body.py`,
`app/services/source_completeness.py`, or `data/configuration/sources.json`
was modified — every one of these was already correct, and this mission's
own verification confirmed that directly rather than assuming it.

## Verification

- Focused: 336 passed, 1 pre-existing/unrelated failure
  (`test_collection_status.py::test_live_source_repository_includes_all_onboarded_sources_generically`,
  confirmed to fail identically against the pristine, unmodified base
  commit — a stale hardcoded source-count assertion, not something this
  mission touched or caused). See `TEST-RESULTS.md`.
- `scripts/validate_records.py`: all validated records passed.
- Full suite was **not** run, per this mission's explicit scope.

## Capped canary

5 discovered items total (2 UF / 2 Fruitist / 1 Oishii), 3 acquisition
attempts, 0 readable within the capped sample, 3 metadata-only review-ready
drafts created, 0 published, 0 approved. Independent diagnostic
verification (outside the cap, no persistence) proved 8 readable bodies
across UF (2) and Fruitist (6), using the identical extraction code path.
Full detail in `CANARY-RESULTS.md`/`SOURCE-FUNNEL.md`.

## Required statements

**CAPPED CANARY ITEMS: 5**

**READABLE BODIES PRODUCED: 0 within the 5-item cap; 8 via independent,
non-persisted diagnostic verification of the same extraction code against
additional real URLs from the same sources**

**PUBLICATION REVIEWS AUTO-APPROVED: 0**

**TRUSTED EVIDENCE AUTO-CREATED: 0**

**CANONICAL RECORDS CHANGED: 0**

**LIVE CANARY RECORDS IMPORTED: 0**

## What is deliberately NOT done here

- No modification to `article_acquisition.py`, `article_refresh.py`,
  `media_discovery.py`, `article_acquisition_outcomes.py`, `source_body.py`,
  or `source_completeness.py` — none exhibited a defect.
- No modification to `data/configuration/sources.json` — the two
  `OPERATOR_ACTION_REQUIRED` Wave 1 sources (Ozblu, Wish Farms) were not
  re-enabled, retried, or bypassed, despite a fresh diagnostic fetch
  returning HTTP 200 for both today (recorded honestly, not acted on).
- No canonical entity, relationship, or Evidence record was created,
  modified, or deleted.
- No publication draft was approved, published, or auto-promoted.
- No UI, competitor-profile-completeness semantics, or design-system file
  was touched.
- No PR, merge, force-push, or deployment.

## Next concrete steps for a future mission

See `NEXT-AGENT-PROMPT.md`.
