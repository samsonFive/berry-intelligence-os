# Blueberry social intelligence review — 2026-10-07

## Updated review: compact UI and $0 bake-off

The [bake-off report](SOCIAL-MONITORING-BAKEOFF.md) supersedes the initial collection snapshot below:93unique actual news-feed titles were ingested in a separate evaluation store; zero live consumer-social records were obtained. Two saved Bluesky live-tail connections succeeded without blueberry matches; keyword search remains403-blocked and YouTube key absent. No purchase, merge, deployment or scheduled collection occurred. Live social-image/retailer/comment proof and independent multilingual acceptance remain unmet.

Current UI: **Sample posts** means made-up examples, explained in the header. Posts is the default compact sheet, showing full original text, available translation, images, aspects, retailer relations and separate purchase/origin/author fields together. Routine dates use MM/DD/YY, raw timestamps remain in source details/tooltips and sorting uses ISO values. English originals do not repeat a same-language synthetic gloss. Language/name/type filters use friendly labels and preserve original query values. Coverage groups15platforms instead of75repeated rows, with country-specific details accessible. Visual selection/shareability and the shared drawer remain intact.

Current screenshots: `artifacts/social-blueberry/dense-posts.jpg`, `dense-drawer.jpg`, `dense-phrases.jpg`, `dense-heatmap.jpg`, `dense-atlas.jpg`, `dense-momentum.jpg`, `dense-coverage.jpg`, `dense-mobile.jpg`. The actual news-only screenshot is private at `inbox/social-bakeoff/news-combined-2026-10-07/preview-news.jpg` and in the delivered local outputs; source titles are not redistributed in public git. Older screenshots below show the previous UI. Default preview remains localhost18343; the separate news-only evaluation is localhost18344 via `scripts/preview_social_bakeoff.py`. News is labeled as a title-only feed, not consumer conversation.

Updated five-minute review: minute1read/sort Posts with full wording and translations; minute2select a phrase or attribute and open Details; minute3compare Costco Found at/Kroger Wants stocked at and text/packaging cultivar bases; minute4check unknown geography, qualified momentum and grouped country health; minute5review the bake-off counts/unmet targets and prioritized free-account checklist. Initial implementation/migration notes below remain applicable. Recent validation results are recorded with the PR review receipt; historical counts below describe the original checkpoint, not the new exact HEAD.

Updated local checks:71social service/route/bake-off tests passed (55.82s); after the final vendor guard/title-repair,36route/bake-off checks passed (31.50s). Canonical record validation, both JavaScript syntax checks and whitespace checks passed. Browser checks verified chronological date sorting, five-post phrase drilldown/shareable IDs, drawer,15grouped platform rows and390pxmobile containment (page375px;1080pxsheet scrolls internally). A broad run overlapping edits reported4,031passed/9skipped/2failed in870.90s because it loaded old vendor tests before their new guard inputs/URL requirements were added; the final targeted suite passes. Exact committed-HEAD PR CI is authoritative and is recorded in the delivered receipt.

## Review outcome

Initial checkpoint: implemented a private, reviewable blueberry vertical slice. **The gate is presented for feedback, not certified complete.** Two real adapter paths were tested, but zero live records were collected at that checkpoint: public Bluesky search returned HTTP403, and `BIOS_SOCIAL_YOUTUBE_KEY` was absent. See the updated bake-off above. No subscription, paid collection, access application, merge or deployment was performed.

Canonical branch is `v2/intelligence-os` at `7962ac04dd05855985f51596f3f8070f19990a75`; GitHub's default `master` is not canonical. This change is stacked on related Landscape Explorer PR #313, branch `feature/landscape-explorer`, base `bd6b4a390e73582aad317eaec12bd5c27c6fad7a`. The branch is `feature/social-blueberry-review`. Landscape boundaries, canonical identities, Glasshouse navigation and the shared evidence drawer are reused. No parallel trusted graph or registry is created. The isolated checkout had no unrelated modifications.

## Changed areas and contracts

- Private SQLite acquisition index and media objects under the configured inbox; canonical Evidence remains the existing reviewed JSON corpus. Stable identity is SHA-256 of platform, provenance mode and native source ID. Page writes and checkpoints commit together. Source corrections preserve analyst review data.
- Strict `schemas/social-intake.schema.json`, generated from the Pydantic model: original wording/language, optional translation provenance, separate geography objects, timestamps, parent native IDs, content roles, engagement snapshots and media states. HTTPS references are validated; arbitrary source URLs are never fetched. Imports cannot claim live provenance or inject internal media object paths.
- EN/ES/PT/ZH/JA literal concept/aspect rules, original spans, conservative canonical links, retailer relation proposals, explicit media-label basis and candidate ambiguity. No model output writes Entities, Relationships, Facts or Assessments.
- Bounded Bluesky search/thread/image-reference and YouTube search/comment-thread/reply/thumbnail adapters. Transport timeouts, response-size limits, retry/request budgets and shared collection lock. Comment collection is sampled, not exhaustive. No transcript/media downloader or web scraping fallback.
- Private `/social` workspace, API, manual capture/import, printable briefing and selected snapshot export. Five visual views use one versioned filter bundle, exact evidence IDs, mode isolation and shared drawer behavior. Cloud includes sortable table fallback; map includes unknown-location grouping and coverage overlay; timeline suppresses unsupported growth claims.
- Dossier and market-snapshot navigation links; opt-in ResearchScope context-provider seam; non-fixture handoff creates an existing unverified inbox Evidence draft and retains minimal `social_observation` metadata on human publication. It does not automatically promote observations or inject private source text into model packets.
- Disabled, unscheduled collection-pipeline registration. Watch-profile suggestions use canonical entities and bounded queries; they cannot self-enable. Suggestions are currently a service contract, not a persisted analyst editor.

## Acceptance ledger

| Brief check | Result and evidence |
|---|---|
| Duplicate source IDs; safe restart | Pass in deterministic tests: one durable row; atomic page cursor resumes on a new Store instance. |
| Outage versus zero | Pass: failed observations have unknown volume, never zero; coverage displays last success, blocker and query change. |
| Four provenance modes; fixture isolation | Pass: mode forms identity/filter boundary; fixture handoff forbidden; import cannot impersonate live. |
| Five-language original + translation inspection | Pass for synthetic fixtures. Translation service and independent native-speaker QA remain unmet. |
| BlackBerry phone; ambiguous cultivar | Pass in labeled cases/tests; phone excluded; ambiguous Breeze stays a candidate. |
| Text versus packaging label; no visual cultivar inference | Pass for supplied literals. Four synthetic comment labels use a synthetic human-label basis. Automatic OCR/vision is not implemented. |
| Mixed flavor/texture sentiment and spans | Pass for explicit literals, including crunchy texture with bland flavor. Five negation challenges remain uncertain instead of the expected negative. |
| Costco found-at versus Kroger wish | Pass in all five QA languages. Retailer names do not locate purchases or create canonical retailers. |
| Purchase / origin / author geography separation | Pass: explicit supplied evidence only; search market separate; unsupported values unknown. Automated geography extraction is not implemented. |
| Comment image independent of post image | Pass for permitted local synthetic bytes and mocked real Bluesky thread normalization. Live retrieval not demonstrated. |
| Unavailable/restricted/deleted and propagation | Partial: private derived proposals, visual counts, bytes and pending handoff drafts are invalidated; tombstones survive replay. Already-published Evidence summaries and downstream trusted Facts/briefings are **not** automatically retracted. Provider deletion polling is absent. |
| Visual counts reproduce drilldowns | Pass in service/route tests and browser inspection: each cloud/cell/country/day exposes exact retained IDs; zero selections remain empty. |
| Sparse/collection-change trend qualification | Pass by suppression; no rising/global sentiment claim is issued. Comparable live-window growth remains unimplemented. |
| Dossier and briefing hooks | Partial: existing navigation/drawer, printable social briefing, draft handoff and opt-in provider seam work. Automatic inclusion in existing dossier/briefing/snapshot assembly is not wired. |
| Keyboard/mobile/empty/error/loading | Browser inspected at 390×844, source-link Enter, shared drawer Escape, sortable fallback, empty live state and comment image; route tests cover invalid filters, missing media and escaped untrusted content. Automated assistive-technology audit remains pending. |
| Repository checks; meaningful tests | See validation results below and exact-HEAD PR checks. |
| Two functioning automated adapters | **Unmet live criterion**. Both real code paths have mocked contract/failure/restart coverage; HTTP403 and missing key remain blockers. |

## Measured evaluation

Dataset: `benchmarks/social-blueberry-fixtures.json`; measured output: `artifacts/social-blueberry/evaluation.json`. All 31 cases are explicitly synthetic, with expected relevance, entity and retailer links, selected aspect sentiment and separate geography. Synthetic entity ambiguity is evaluation-only, never added to the registry.

| Language | Cases | Correct / field checks | Exact field accuracy | Errors |
|---|---:|---:|---:|---|
| EN | 7 | 46 / 47 | 97.87% | Negated sweet → uncertain, expected negative |
| ES | 6 | 39 / 40 | 97.50% | Same conservative negation error |
| PT | 6 | 39 / 40 | 97.50% | Same conservative negation error |
| ZH | 6 | 39 / 40 | 97.50% | Same conservative negation error |
| JA | 6 | 39 / 40 | 97.50% | Same conservative negation error |

These are 202/207 exact field checks, not entity F1 or an independent benchmark. Unknown geography checks contribute to the denominator; the small developer-authored fixture set is optimistic and not globally representative. Translations are synthetic glosses, not human-validated translations. **Live sample: 0; performance unavailable.** Reproduce with `python scripts/evaluate_social_blueberry.py`.

## Preview and five-minute walkthrough

Use the repository's normal Python environment (`requirements-dev.txt`), then run `python scripts/preview_social_blueberry.py`. Open `http://127.0.0.1:18343/social?mode=fixture`. It binds localhost only, disables background polling and uses isolated `inbox/social-blueberry-preview`. No production deployment is needed. Do not expose this local authoring preview publicly; remote hosting requires the established session-auth configuration.

1. **0:00–1:00:** Phrases → sort the accessible table → select Costco/crunchy; evidence count and shareable URL reproduce the selection.
2. **1:00–2:00:** Open a source in the shared drawer. Inspect original wording, synthetic translation and separate flavor/texture spans. In Map & retail open the Spanish comment `Arándanos con esta etiqueta.`; inspect its independent image and literal packaging label/parent ID.
3. **2:00–3:00:** Compare Costco `found-at` with Kroger `wishes-stocked-by`; text SEKOYA Crunch versus packaging-label basis; unlabeled imagery cannot establish variety. Attributes shows denominators and insufficient-evidence cells.
4. **3:00–4:00:** Map & retail shows explicit synthetic purchases and 25 unknown-location records. The Spain/Peru/Japan example separates purchase/origin/author. Momentum shows publication counts, sparse-data suppression and actual blocked collection events. Coverage exposes all 15 platforms × five targets; switch Live to see zero retained records with unknown coverage.
5. **4:00–5:00:** Follow Landscape and a company/variety's private Social Listening link. Return to printable briefing/export. Manual capture stores supplied permitted text without crawling; import validates the same schema. Non-fixtures can enter existing human review; fixtures cannot. Expand the after-gate contract preview; no dead graph navigation is offered.

Screenshots are in `artifacts/social-blueberry/`: desktop phrases, evidence, heatmap, atlas, momentum, coverage, live-blocked, mobile atlas and mobile comment-media. Every demo view is labeled FIXTURE / SYNTHETIC DEMO. The synthetic package diagram is explicitly not a photograph.

## Operations, budgets and costs

`BIOS_INBOX_DIR` selects the private persistent runtime. The new pipeline is `enabled:false`, `scheduled:false`. Collection requires an explicit `--enable`; maximum 1–3 pages, 1–60 requested records, 12 HTTP requests including retries, bounded sampled comments, 20-second request timeout, 2 MB streamed responses and 5 MB permitted image attachments. Use `python scripts/social_intelligence.py status` before collection. `collect --source youtube` reads only `BIOS_SOCIAL_YOUTUBE_KEY`; never commit it. Neither adapter provisions accounts, buys credits or activates subscriptions. Do not enable sources before reviewing access/retention obligations.

Pilot monetary spend: $0 activated. Bluesky probe made one unsuccessful request; YouTube missing-key check made zero. YouTube quota usage depends on the current Google project allocation; official docs now describe a separate search allocation, so no stale 100-units-per-search pricing is assumed. X's current publicly documented read prices are recorded in the dated matrix, but no X adapter or paid collection is enabled. Infrastructure/storage cost is operator-specific, not estimated as a vendor quote. Jobs record calls, status, last success, checkpoint and unknown-versus-zero volume; there is no monetary ledger or provider billing reconciliation yet. Rate limits are safeguards, not proof of entitlement.

Retention default is a conservative 30-day private-store limit via explicit `expire`; provider-specific refresh/deletion schedules are not automated. Do not enable unattended live collection until source-specific retention and published-dependency retraction are implemented.

## Migration and rollback

SQLite `user_version=1` creates new acquisition tables (observations, jobs, audit, media tombstones) and WAL storage below inbox. No existing canonical data is rewritten. Evidence schema gains an optional minimal metadata object; `review_publish` preserves it after existing human gates. Intake contract is separate and versioned. Disabled pipeline registration is the only configuration addition.

Before future rollout, back up persistent inbox/data using a SQLite consistent backup or stop collectors/server before copying database + WAL; verify restoration in isolation. Revert this feature commit to remove routes/navigation/config while leaving runtime bytes intact. Old readers ignore optional social metadata; retain a backup if removing that field is later required. Never delete production inbox or overwrite trusted records as rollback. No production migration has been executed.

## Ordered continuation backlog and review decisions

1. Resolve legitimate Bluesky access and an existing authorized YouTube project/key; review budgets, terms, sampling and retention. Obtain two successful bounded live runs and a separate live evaluation. Do not purchase/apply automatically.
2. Implement provider deletion/refresh tasks and audited published Evidence/dependent summary retraction; validate restart/removal across trusted dependencies before enabling unattended jobs.
3. Independent native-language evaluation, translation provenance/QA, negation/irony/context, geography extraction, near-duplicate/repost/campaign grouping that preserves independent consumers. Persist reviewed watch profiles and query history; add monetary budget/queue observability.
4. Authorize and implement OCR/transcript/vision hooks for packaging fields and visible-condition proposals, with actual media capability and terms. Do not infer cultivar or food safety from appearance.
5. Wire opt-in social context through established dossier/briefing/snapshot assembly without fixture/private leakage or trust bypass; add verified retailer entity mappings through existing review.
6. Extend country vocabulary and coverage beyond the five QA targets, then audit raspberry/strawberry/blackberry individually. Common contracts already accommodate all four berries; their UI rollout remains gated.
7. Review each platform in the matrix: Instagram, TikTok, Facebook Pages, Threads, X, Reddit, YouTube, Bluesky, LinkedIn, Pinterest, Weibo, Douyin, RED/Xiaohongshu, Bilibili, public forums/retail. Unsupported/unapproved sources stay blocked; imports are not live monitoring.
8. After feedback, build compatible entity networks, retailer deep dives and wider analyst views on shared Landscape contracts. Add comparable-window momentum only after sufficient healthy observations.

Decisions needed: accept the stacked Landscape dependency and private fixture preview; choose authorized access owners and collection budgets; prioritize published-removal safety and multilingual/vision providers; agree which partial checks must close before live operation. **Stop here for blueberry feedback; do not merge or deploy.**

## Initial checkpoint validation history

Final focused social tests: **48 passed** (40.40s). Existing Landscape focused tests: **44 passed**. Canonical record validation and JavaScript syntax checks passed. Static build: **1,755 pages**, private-draft leakage validation passed. A broad run made during final edits reported 3,998 passed / 9 skipped / 2 failed: the existing clean-working-tree assertion saw the intended uncommitted pipeline configuration, and a loaded old aggregation module encountered the newly edited momentum template. Final focused tests pass; exact committed-HEAD CI remains the authoritative full-suite result. No merge/deploy follows those checks.

The advanced Landscape dependency was incorporated locally with both debt entries preserved (social is TD-117). After committing the intended configuration, the clean-state guard plus all social route tests passed: **16 passed**. Final focused social suite remains48 passed.

Updated Landscape plus canonical promotion tests: **61 passed** (45.65s). CI detected trailing blank lines in new test files; corrected before final validation. Final commit/CI identifiers are recorded in the PR and delivered review receipt.

Two additional targeted checks passed for fixture-excluded canonical dossier/context links and literal media-field locator/removal behavior. Total social coverage:48 earlier focused checks +2 new targeted checks; final CI covers all50 together.

Final browser regression: a zero-count heatmap cell now encodes `drill=none`; reload preserves0 visible records instead of restoring all. JavaScript syntax passed after this correction.


## October 7 follow-up: translation-first UI and actual SociaVault trial

The [multi-platform measured trial](SOCIAL-SOCIAVAULT-MULTIPLATFORM-TRIAL.md) supersedes earlier statements that no SociaVault key/account or live social sample was available. Actual bounded discovery returned content from six platforms; 24 one-time free credits consumed, 26 remaining, $0 paid. LinkedIn is blocked and two TikTok responses exceeded the byte ceiling. Original images can be loaded explicitly; translation-first text keeps original wording on hover/focus/tap. Production scheduling, source-specific retention/redisplay permission, independent accuracy/global coverage, automatic dossier/briefing assembly and published dependency retraction remain unproven or unmet. The isolated preview is localhost18345; public git contains counts/manifests and invented demo screenshots, not real raw posts. No merge/deployment occurred.


## Visual reader and successful LinkedIn follow-up — October7

See [the current reader/LinkedIn report](SOCIAL-VISUAL-READER-LINKEDIN.md): public company retrieval, two independently located named-variety posts and broader undated keyword search all succeeded.21 retained rows added19 unique records; total isolated records171. Four additional free credits used; total28 consumed,22 remaining,$0 paid. Earlier404 failures remain recorded with unresolved cause. Public native LinkedIn embedding rendered without a LinkedIn login. The reader now leads with native video players/photos and compact supporting detail. No ongoing collection, rights/accuracy qualification, merge or deploy.
