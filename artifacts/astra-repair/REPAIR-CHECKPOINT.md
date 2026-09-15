# Article acquisition failure repair checkpoint — 2026-09-15

Branch: `fix/article-acquisition-failures-v1`
Base: `bd96fca1231dc97ae4ec3fc316743b0a3f2e8427`
Worktree: `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-article-acquisition-failures-v1`

## Completed

- Added an immutable operational ledger for every attempted article-body request in forward collection and bounded historical reacquisition, including attempts that create no draft. Records preserve identifiers, a redacted URL, timestamps, stage, normalized outcome, HTTP status, retryability, attempt count, content quality, versions, optional article date, and a scrubbed diagnostic. Response bodies and wall HTML are never stored.
- Propagated acquisition outcomes through standalone article refresh and the recurring collection runner. Run summaries now count body attempts, readable bodies, blocked/unusable outcomes, and retryable failures separately.
- Kept discovery records for diagnosis while existing source-completeness and source-body gates continue to exclude unusable captures from readable evidence, summaries, Today, company coverage, and reports.
- Updated Source Health to separate source freshness, discovery execution, article-body acquisition, and readable-content success. A successful feed run no longer looks like proof of readable evidence.
- Extended the read-only source execution audit with per-source acquisition results.
- Added a read-only five-level audit for the required 33-company roster. It accepts a later canonical roster file and does not create entities or classifications.

## Canary

Five sources were run independently with `--max-items 2`, transcription skipped, extraction disabled, and a private worktree inbox:

1. `source-freshplaza-global`: 70 discoveries, 2 processed, 2 readable bodies, both rejected as irrelevant.
2. `source-20260824-perishable-news-produce`: 10 discoveries, 2 processed, 1 readable body rejected as irrelevant; the other item was rejected before body acquisition.
3. `source-20260819-blue-book-services`: 10 discoveries, 2 processed, 1 HTTP 403 persisted as `bot_wall`, non-retryable, manual acquisition required; the other item was rejected before body acquisition.
4. `source-20260824-berryworld-newsroom`: 10 discoveries, 2 processed, 1 readable direct item staged as private draft `ev-media-d0d76be2f0c6c09a3d96`; the other item was rejected before body acquisition.
5. `source-news-search-costa-group`: 50 discoveries, 2 processed, both rejected before body acquisition.

Totals: 150 discoveries, 10 processed items, 5 body attempts, 4 readable outcomes, 1 blocked/unusable outcome, 0 retryable outcomes, and 1 private unapproved draft. No current California Giant item appeared in the processed trade-source window. The official Cal Giant restriction was not bypassed.

Exact isolated application-data mutations under this worktree's ignored `inbox/`: 150 discovered-item files, 5 discovery-state files, 10 operation-item files, 5 run files, 5 acquisition-outcome files, and 1 private evidence draft. No published or approved records were written.

## Roster audit

11 of 33 roster labels resolve uniquely in this base; 22 are reported unresolved for the entity owner. California Giant is maturity 1 of 5: represented, with no explicitly linked Source and no current usable published coverage. BerryWorld reaches maturity 4 from the readable canary body but has no current usable published coverage. No entity, tier, relationship, landscape, or Radar data changed.

## Validation

- Affected acquisition, orchestration, runner, Source Health, freshness, and historical-reacquisition tests: 86 passed. The focused historical subset: 16 passed.
- Downstream honesty tests covering company news, Today/front-page selection, and publication portability: 49 passed.
- Python compilation and diff whitespace validation passed.
- Browser verification passed on `/sources`; screenshots show the aggregate separation and the Blue Book discovery-success/body-bot-wall case.
- Fast record validation is recorded in `record-validation.txt`.
- Full suite was not run.

## Remaining issues

- California Giant still has no compliant runnable source linked to its canonical entity. Its official newsroom remains HTTP 403 to the approved Python client. Closing current coverage requires a supported discovery route or a legitimate publisher-access change.
- Twenty-two roster labels await Claude's entity-resolution work. The audit is ready to consume that canonical roster later.
- Automatic collection remains off. This checkpoint validates five sources only and does not authorize broad activation.
- The canary's one BerryWorld draft is historical (published 2025-08-29) and remains private and unapproved.

## Artifacts

- `acquisition-outcome-audit.json`
- `acquisition-canary-results.json`
- `competitor-source-coverage.json`
- `competitor-source-coverage-summary.md`
- `acquisition-outcome-tests.txt`
- `downstream-honesty-tests.txt`
- `reacquisition-outcome-tests.txt`
- `record-validation.txt`
- `screenshots/article-acquisition-source-health.png`
- `screenshots/blue-book-acquisition-outcome.png`

---
# Berry OS repair checkpoint — 2026-09-11 (continuation session)

Branch: `fix/astra-news-reader` in `C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-astra-repair`. No merge, production deployment, production writes, or model calls performed in this or the prior checkpoint. Previous checkpoints: bdb4c69, 759ed42, bfbf77a. Use `git log -5 --oneline` for the newest repair commit.

## 2026-09-12 source-execution checkpoint

- Commit `e8b3efb215889fee5dea1ddf08eea28c6a0869c2` adds a read-only discovery-execution projection to Source Health. Each Source is now classified as successfully run, never run, blocked, retryable failure, invalid/incomplete, manual, or disabled. The UI deliberately calls this **discovery execution** and warns that a successful discovery run does not prove readable article bodies or complete recall.
- The reproducible local audit (`scripts/audit_source_execution.py`) reports 201 Sources: 76 configured and runnable, 3 successfully run, 73 never run, 1 blocked, 0 retryable failures, 0 invalid/incomplete, 123 manual, and 1 disabled. Snapshot: `artifacts/astra-repair/source-execution-snapshot.json`.
- A no-network/no-write collection dry run planned all 76 runnable Sources successfully and processed zero items. It establishes the execution boundary, not safe live volume. Because discovery and resulting review-queue volume are unknown, this checkpoint did not launch the full live run. Plan: `artifacts/astra-repair/collection-dry-run.json`.
- Browser verification passed at `/sources`; screenshot: `artifacts/astra-repair/screenshots/source-execution-desktop.png`. Focused source tests: **50 passed**. Record validation: **passed**. The full suite was intentionally not repeated; the preceding checkpoint's full suite was 2639 passed.
- Remaining blind spot: discovery success is persisted per Source, but failed article-body acquisitions that produce no draft are not durably summarized per Source. Blue Book can therefore read “successfully run” at discovery level while every attempted article body was blocked. Persisting and exposing that downstream outcome is the next bounded repair.

## Completed in this continuation session

- **Root-cause fix for "old stories shown as current"**: `app/services/media_orchestration.py`'s `_draft_from_item` set a new draft's *top-level* `published_date` (the field every date-based view actually reads: news homepage windows, company 90-day coverage, report generation) straight from the discovery feed's signal (RSS `pubDate`, or worse, a sitemap `lastmod`) and never reconciled it against the real date `trafilatura` already extracts from the fetched article page moments later (`ArticleBody.published_date` / `published_date_basis` existed but were dead -- computed, never read anywhere downstream). Added `_reconcile_published_date()` in `app/services/article_refresh.py`, wired in at the one place a fresh draft's article body is attached: when the body's own date is present and passes `_valid_iso_date`'s sanity check (real calendar date, 2000-01-01 through today+2 days), it now overrides the discovery-stage guess; the original feed-derived date is preserved under `discovery_provenance.discovery_published_date` for audit, and a new `published_date_basis` field (`"article_body"` or `"discovery_feed"`) records which one won, honestly, on every new draft. Confirmed live and necessary against a real case, not a hypothetical: calgiant.com's own Yoast sitemap stamps `lastmod=2026-07-14T17:1x` on roughly a dozen unrelated historical posts (2018-2023 originals) because of a single bulk site-migration/republish event -- wiring that sitemap in naively (the originally-tempting fix) would have reproduced this exact defect on a new source instead of fixing it.
  - New/extended tests in `tests/test_article_refresh.py`: `test_stale_feed_date_is_overridden_by_the_articles_own_published_date` (reproduces the calgiant.com-shaped failure with a fake feed pubDate of 2026-08-18 vs. a fake article page's `article:published_time` meta tag of 2021-12-14) and an added assertion on the existing `test_relevant_article_produces_a_review_ready_draft_with_real_body` (no extractable body date -> discovery date kept, `published_date_basis == "discovery_feed"`).
  - Removed ~40 lines of confirmed-unreachable dead code in `media_orchestration.py`'s `_draft_from_item` (a duplicate draft-construction block sitting after the function's own `return`, impossible to execute, noticed while editing the surrounding code for this fix).
- **Precisely diagnosed the calgiant.com acquisition block** (did not attempt to bypass it, per instructions): `robots.txt` explicitly permits all crawling (`Disallow:` empty) and declares a working Yoast sitemap at `https://www.calgiant.com/sitemap_index.xml`; its `cpt_cg_news-sitemap.xml` sub-sitemap lists real newsroom URLs matching every previously-identified coverage gap (Back-to-School Label Aug 3 2026, IFPA Foodservice and Organic Produce Summit pieces, PNW blueberry season, plus others not previously known: a B Corp certification announcement, an SEPC Southern Exposure / "Belli Berries" launch teaser, a probiotic-blueberries IFPA debut). But **both** the sitemap and individual `/newsroom/` article pages return **HTTP 403 to this project's `httpx`-based fetcher while the identical URL and User-Agent string succeed via `curl`** -- an A/B-confirmed TLS/HTTP-client fingerprint block (Cloudflare bot management), not a robots.txt or credential restriction, and not something `h2`/header changes fixed (`h2` isn't even installed; httpx was already HTTP/1.1). Documented directly in both Cal Giant entries in `data/configuration/sources.json` so the next agent doesn't have to rediscover this.
- **Larger, previously-unknown finding**: of this local snapshot's 201 configured sources, 76 are fully collection-eligible (`ACTIVE` lifecycle + valid `discovery.adapter`/`feed_url`) -- including three already "live-verified" syndicators independently known to carry real historical Cal Giant content (FreshPlaza global feed, Blue Book Services, Perishable News - Produce) -- but **every one of the 76 has `last_checked_at: null`**: none has ever actually been run in this snapshot. No cron/scheduled workflow triggers collection anywhere in this repo (`.github/workflows/` only has `deploy-pages.yml` and `pr-validation.yml`) -- collection here is purely operator-invoked. This, not any single publisher's bot-wall, looks like the dominant reason this local snapshot shows no recent coverage of anything, Cal Giant included. (Caveat, per the standing instruction: this is a fact about *this local dev snapshot*, not necessarily about the hosted production app's own scheduling infrastructure, which lives outside this checkout.)
- **Proved the pipeline works correctly, live, end-to-end, with real network calls (no LLM enrichment -- `PERPLEXITY_API_KEY` explicitly unset for these runs)**: ran `scripts/ingest_articles.py` against three of the 76 never-run sources.
  - `source-freshplaza-global`: 71 discovered, 40 processed (cap), 3 confirmed-relevant items acquired with real bodies and staged as genuine review-ready drafts (`ev-media-6f7cd6a6dc738c8b2e5a`, `ev-media-50bce762f87e36fd5434`, `ev-media-f65822a83e7957e23723` -- India/US strawberry trade case, UC Davis varieties in Peru, Australian thrips pest; none are Cal Giant, this window's most-recent items simply weren't), 0 acquisition failures, 0 fabricated content.
  - `source-20260824-perishable-news-produce`: 10 discovered, 4 real bodies acquired, all correctly screened irrelevant (general produce feed, no berry hits in this window) -- 0 acquisition failures.
  - `source-20260819-blue-book-services`: 10 discovered, 5 reached acquisition and **all 5 correctly, honestly reported `category=blocked` (HTTP 403)** -- proof the honesty discipline (never fabricate, never silently substitute an interstitial as content) holds under a real, live block, not just in unit tests.
  - None of these three runs' *current* RSS windows happened to contain a new Cal Giant story today -- RSS discovery is forward-only from whenever a source starts being polled; it does not retroactively backfill the missing Jun 14 - Sep 11, 2026 window, and this session did not fabricate one to fill that gap.
  - Real side effects, entirely private: `inbox/discovered_media/` grew to 91 items (was fewer before this session), 3 new files in `inbox/evidence/` as ordinary un-reviewed drafts, state files written under `inbox/discovered_media/_state/` for the three sources. Nothing published, nothing auto-approved, nothing touched in `data/configuration/sources.json`'s `last_checked_at`/`last_status` (that bookkeeping belongs to a different, higher-level script than `ingest_articles.py` -- every `last_status` in the checked-in file is `null`, so no existing convention was available to imitate; left alone rather than guessed at).
- Updated both Cal Giant entries in `data/configuration/sources.json` (`...-6b33-...-28` and `...-5f03-...-pa-19`) with the precise 2026-09-11 Cloudflare/TLS-fingerprint diagnosis above, including an explicit warning against ever trusting calgiant.com sitemap `lastmod` as a publication date if acquisition is restored later.

## Completed in the prior checkpoint (unchanged, carried forward)

- Company coverage service: inclusive last 90 calendar days by publication date; separate undated/history; pending status and readable-text counts; duplicate IDs counted once; no stored evidence mutations.
- Cal Giant company page: current coverage, direct report handoff with company name and window, archive links, collapsed full history, clearer archive labels. Existing canonical identity/alias repair remains on the branch.
- Company reports: complete article inventory beyond the top-15 synthesis cap, opening excerpts where text exists, explicit blocked/missing text, separate pending/undated items, no pending inventory in trusted model grounding. Unrelated variety candidates no longer inflate company coverage.
- Reports/PDF: working-report review marker replaces false automatic analyst-review claim; readable company name and publication window in PDF scope.
- Company timelines suppress consent/access-page summaries without modifying original evidence. Evidence reader hides empty metadata; reader subject attribution no longer incorrectly describes published evidence as pending.
- Source references now link the official Cal Giant newsroom, retaining manual/reference status. Read-only `scripts/audit_company_coverage.py` reproduces local coverage counts.
- TD-113 and Coverage Matrix document the unresolved acquisition gap.

## Verification (this continuation session)

- Focused: `tests/test_article_refresh.py` + `tests/test_media_orchestration.py`: **35 passed** (includes the 2 new/extended published_date-reconciliation tests).
- Broader focused: `test_media_discovery.py` + `test_media_discovery_source_expansion.py` + `test_company_news_coverage.py` + `test_article_ingestion_pipeline.py`: **65 passed**.
- `scripts/validate_records.py`: all validated records passed, after the `sources.json` edits.
- Full suite (`artifacts/astra-repair/full-tests-after-published-date-fix.txt`): **1 failed, 2639 passed, 3795 warnings in 913.29s (0:15:13)**. The single failure, `tests/exports/test_intelligence_package.py::test_export_round_trips_all_supported_content_through_fresh_repositories`, is a **confirmed self-inflicted race, not a regression**: this session's `Edit` to `data/configuration/sources.json` (the Cal Giant diagnosis notes) landed on disk while this exact full-suite run was already reading that file mid-flight -- the same category of flake the prior checkpoint already documented for a different concurrent edit ("Package export mismatch arose while the canonical company description changed during the run"). Re-ran `tests/exports/test_intelligence_package.py` alone afterward, against the now-stable file: **6 passed in 112.58s, 0 failed**. No known-failing test remains on this branch.
- `scripts/audit_company_coverage.py company-california-giant-berry-farms --as-of 2026-09-11` re-run after the fix: unchanged (20 matching / 9 access-screen / 0 current, `artifacts/astra-repair/calgiant-coverage-audit-after-fix.json`) -- correct and expected, since the audit only reads *published* `data/evidence/`, and this session's 3 real new drafts are private, unreviewed `inbox/` items by design ("pending items stay private"). The fix changes date assignment for *future* new drafts; it does not and must not retroactively rewrite already-published historical records.

## Verification (prior checkpoint, unchanged, carried forward)

- `fix-tests.txt`: 128 passed.
- `report-final-tests.txt`: 92 passed.
- `last-focused-tests.txt`: 112 passed, including package export round-trip, company reports, shared-reader integration, attribution, and UI shell tests.
- First full suite: **2634 passed / 5 failed**, in 714.89 seconds (`final-tests.txt`). Three obsolete heading assertions were updated; empty-report test was isolated from local runtime. Package export mismatch arose while the canonical company description changed during the run; unchanged-data export round-trip passed in the subsequent focused run.
- **Fresh full suite completed clean after handoff:** `2639 passed, 0 failed, 3795 warnings in 560.27s` (`artifacts/astra-repair/clean-full-tests.txt`). This supersedes the earlier `2634 passed / 5 failed` run — the 5 failures were the obsolete-heading/empty-report issues already fixed before this rerun. No known-failing tests remain on this branch as of commit bfbf77a.
- `scripts/validate_records.py`: all validated records passed (`record-validation.txt`).
- `scripts/build_static.py`: 1630 pages, Pagefind built, no unpublished draft IDs or titles leaked (`static-build.txt`).
- Local report creation and PDF export returned 200 using an explicit no-model verification process. PDF text checked and first page rendered/visually inspected. `verify_local_report.py` reproduces this; it writes only this worktree's private inbox. Do not run it during full-suite tests.
- Actual browser checks: Cal Giant search returns canonical company; company → named 90-day report → scope preview works; report shows zero unrelated variety candidates; blocked source text becomes a notice; archive shared reader next-story URL changes and Escape clears story URL/restores focus after close animation. Desktop 1280 and mobile 390 viewport checks found no document overflow. Screenshots are in `screenshots/`; desktop captures are soft due to browser capture scaling, mobile capture is clearer. No screenshot content was inserted.

## Remaining issues / do not overclaim

**Freshness/acquisition for Cal Giant specifically is STILL NOT fixed** -- `scripts/audit_company_coverage.py` still reports 0 current (Jun 14 - Sep 11, 2026) published articles locally, unchanged by this session, and that is correct/expected (see Verification above: this session's real new drafts are private `inbox/` items, not yet reviewed/published, by design). The Jun-Aug 2026 historical backfill gap for Cal Giant remains open: this session did not find a compliant way to acquire it (calgiant.com direct is TLS-fingerprint-blocked; the three working syndicators' *current* RSS windows didn't happen to contain a Cal Giant item today; RSS discovery is forward-only and does not backfill). Do not fabricate a fix for this gap -- it needs either (a) a real historical-backfill mechanism through the existing acquire/screen/review pipeline pointed at each syndicator's own site-search or archive pages for "California Giant"/"Cal Giant" (not just their most-recent-N RSS feed), or (b) waiting for forward collection to accumulate coverage now that eligible sources are proven to work, or (c) resolving the TLS-fingerprint block through a legitimate means this session did not find (adopting a different HTTP client is the obvious next idea but risks crossing from "diagnose honestly" into "evade bot detection" -- think carefully, don't just reach for `curl_cffi`/browser-fingerprint spoofing without deciding that's actually the right line to draw).

**What this session actually fixed is more general and arguably higher-leverage than Cal Giant alone**: the published_date reconciliation bug affects every future article acquired through this pipeline from any source whose feed date and page date can diverge (very common for sitemap-based discovery, plausible for any RSS feed too) -- this was previously silently wrong for potentially many sources, not just a hypothetical Cal Giant one. The 76-never-run-eligible-sources finding is also general: whoever operates this app should schedule/run `scripts/run_collection.py` (or equivalent) against them, not just Cal Giant's two blocked reference entries.

Next priority, in order: (1) decide whether to actually invoke full collection (`scripts/run_collection.py`, not just the narrower `ingest_articles.py` this session used) across all 76 eligible sources -- bounded, operator-supervised, review-gated, and NOT done this session (out of scope/budget; only 3 sources were proven as a bounded proof-of-concept); (2) design a compliant historical-backfill path for Cal Giant specifically if the user still wants that gap closed; (3) only then revisit the wider build guide.

Existing reports re-resolve source packets against current data when reopened while edited prose is preserved (from the prior checkpoint -- still true, untouched this session). Consider this live-packet behavior when assessing report reproducibility; do not silently turn saved drafts into frozen evidence snapshots.

The local preview server was last started on port 8018, PID 25144; still running and verified alive at the end of this session (`tasklist`/`netstat` both confirm). Verify process command before stopping only that owned server. Two private verification reports exist in this worktree's ignored inbox from the prior checkpoint (latest: `/reports/rp-b47f7fc0948be290`); this session added 3 more private, unreviewed evidence drafts to `inbox/evidence/` (ids in Verification above) plus 91 total items now in `inbox/discovered_media/` -- none of this is published or reviewed, all of it is exactly where "pending items stay private" says it should sit pending a human.

## Resume economically

Give the next agent `NEXT-AGENT-PROMPT.md`. The full suite is confirmed clean (2639 passed, 0 real failures -- see Verification above for the one confirmed self-inflicted race and its clean isolated re-run) as of the commit this checkpoint is attached to; no need to rerun it again without a reason. Do not rerun `scripts/audit_company_coverage.py` or the historical-backfill investigation from scratch -- the finding (0 current, gap is real, three working non-Cal-Giant-specific syndicators identified, calgiant.com direct is TLS-blocked) is settled; act on it or make a deliberate, documented decision not to. No usage-reset credit was consumed this session.
