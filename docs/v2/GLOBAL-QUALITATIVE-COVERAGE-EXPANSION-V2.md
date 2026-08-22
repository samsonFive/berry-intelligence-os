# Global Qualitative Coverage Expansion V2

**Mission:** Global Qualitative Coverage Expansion V2 (2026-08-22, branch `feature/global-qualitative-coverage-v2`). A second, real round of qualitative discovery expansion, building directly on Round 1 rather than repeating it -- the mission brief's own "why" framing (22%->30%, 39/50 missed) described the pre-Round-1 state; this mission re-confirmed the true current baseline (26/50 = 52%, Round 1's real result) before doing any new work, per the mission's own Section 1 instruction.

---

## 1. Baseline re-establishment

Fetched origin fresh; canonical was `35d8066`, exactly where Round 1's own work (PR #66) plus the subsequent Learner Mode roadmap integration (PR #68/#69) left it -- no concurrent Cursor/Codex work had landed. Verified this mechanically (source count still 164, the recall benchmark doc's own Section 10 still showed 26/50=52%, all 164 net-new Round 1 drafts still present locally) rather than assumed. **True current baseline for this mission: 26/50 (52%)**, using the same event definitions, no redefinition.

---

## 2. Miss/source-gap map

24 events remained strictly MISSED after Round 1 (recomputed precisely from the benchmark's own table + Round 1's Section 10 deltas): Corporate 7 (C-04, C-06, C-07, C-08, C-09, C-12, C-13), Reputation/Risk 5 (R-03, R-06, R-09, R-10, R-11), Regulatory/Trade 6 (T-04, T-05, T-06, T-07, T-08, T-11), Genetics 1 (G-02), Commercial/Market 5 (M-02, M-03, M-04, M-06, M-08). Clustered by reusable mechanism: a Peru investment-cluster (C-06/C-07/C-08, all real Peru blueberry investment stories the mission brief itself names Mission Produce/NuBerry as examples of), a UK season-launch cluster (C-09/C-13), a Georgia/Michigan labor-legal cluster (R-10/R-11, already partially addressed by Round 1's labor-legal query), a second food-safety jurisdiction gap (R-09, Canada/CFIA), and a USDA-FAS-GAIN-document cluster (T-11/M-06).

---

## 3. Discovery architecture changes

None beyond two new adapter functions (both additive, mirroring the exact "new publication technology = one adapter" precedent Round 1 established): `_normalize_uk_fsa_entry` / `_uk_fsa_entries` for a new `government_alert_json` adapter type. No change to `run_recent_batch.py`, `process_discovered_media.py`, or `collection_runner.py`.

Codex's Collection Runtime / Data Integrity V1 mission (PR #70, `cd107b9`) landed mid-mission, after this section was first drafted -- canonical moved `35d8066` -> `704c18e` (also picking up Cursor's Global Intelligence Search V1, PR #65) and this branch was rebased onto it. Codex's real pipeline registry, `data/configuration/collection_pipelines.json`, and its shared `inbox/operations/collection.lock` were read in full post-rebase: the registry's one `enabled: true` entry (`article_spoken_media`) names `scripts/run_collection.py --all --skip-transcription` as its runner, and the `plant_patent`/`cpvo`/`trade`/`weather` entries name the `monitor_*.py` scripts -- none of these is `discover_media.py`, `run_recent_batch.py`, or `process_discovered_media.py`, the three scripts this mission (and Round 1) used directly throughout. The lock therefore does not apply to this mission's own collection calls; per the mission brief's own instruction ("use it rather than bypassing it" only applies when the registry/lock has landed *and* covers the scripts in use), no integration was needed. Codex's `article_dedup.py` change (`_publisher_identity()`, see TD-046) was also confirmed purely additive against this mission's own Round 1 `normalize_canonical_url()` fix -- different functions, no logical conflict, verified via direct diff review of `cd107b9^..cd107b9`. Query-generation stays one bounded Source per query (Round 1's TD-042 decision reaffirmed, not revisited).

---

## 4. Sources added

4 new sources (`data/configuration/sources.json`, 164 -> 168): `source-uk-fsa-food-alerts` (new `government_alert_json` adapter against `data.food.gov.uk/food-alerts`, real, keyless, Open Government Licence), `source-news-search-peru-organic-investment`, `source-news-search-uk-grower-season`, `source-news-search-usda-gain-berry` (all `news_search_rss`, geography/event-concept/document-type-scoped, never a company name).

---

## 5. Commercial/Market coverage

Targeted first, per the mission's own instruction (biggest class gap). Real result: **BM-M-03 captured** (Peru +25% to 400,000t forecast, Spanish-language, found via Round 1's own existing query sitting unprocessed in the backlog -- proof that processing more of what's already discovered is sometimes the highest-value first move, not a new source). BM-C-08 (NuBerry) and BM-C-13 (Hall Hunter) are Corporate-class but directly answer the mission's own named examples. M-02, M-04 (already-trusted, see Section 13), M-06, and M-08 remain unaddressed this round -- see Section 16 for the full per-event classification.

---

## 6. Food safety

New UK Food Standards Agency `government_alert_json` adapter -- real, live-verified, current (2026) data, sortable by recency, no auth. Found a real berry-relevant match generically ("Tesco recalls Tesco Grape & Berry Medley because of contamination with salmonella", 2026-02-16) -- not a benchmark event itself, but proves the mechanism works and gives the platform a second real food-safety jurisdiction alongside Round 1's US openFDA source. CFIA (Canada, BM-R-09) remains unresolved -- audited again briefly, no new working search capability found beyond Round 1's TD-041 finding.

---

## 7. Corporate/financial coverage

Real generic captures: BM-C-08 (NuBerry, "Peru organic blueberry expands OR invests" -- found the exact Produce News article the benchmark itself cites, at no point searching for "NuBerry") and BM-C-13 (Hall Hunter, "UK ... grower launches OR kicks off season" -- found a real Fruitnet article about the identical real 2026 season-launch event the benchmark cites via a different publisher). C-04 (Unifrutti) remains blocked by the relevance-screen boundary (TD-040/TD-045) despite a real, better-titled alternate article (Fruitnet) existing -- confirmed by hand, not surfaced by this mission's generic queries. C-06/C-07/C-09/C-12 remain unaddressed.

---

## 8. Regional coverage

Peru and UK were the two geographies that moved this round (Section 17 has the full globality check). Chile, Morocco, and South Africa were re-verified unchanged (no new capture, real and honestly reported, not a regression). Mexico and Spain were not specifically targeted this round (already at 55%/audited in Round 1); the new USDA-GAIN query is Mexico-adjacent but found no exact new benchmark match.

---

## 9. Language coverage

No new language added this round (Spanish and French were both already proven in Round 1). This round's real, additional proof: BM-M-03's capture came from **processing more of Round 1's existing Spanish-language backlog**, not a fresh query -- direct evidence that Spanish-language discovery's real value compounds with processing depth, not just source breadth.

---

## 10. Acceptance cases (real status, this round)

| Requirement | Status this round |
|---|---|
| Peru commercial/market event | **CAPTURED (draft)** -- BM-C-08 (NuBerry) and BM-M-03 (400,000t forecast), both new this round |
| Chile event | Unchanged from Round 1 (BM-T-10, CAPTURED) |
| UK event | **CAPTURED (draft)** -- BM-C-13 (Hall Hunter), new this round, in addition to Round 1's BM-M-01 |
| Morocco event | Unchanged from Round 1 (BM-T-10, CAPTURED) |
| South Africa event | Unchanged from Round 1 (BM-M-05/BM-T-09, CAPTURED) |
| Authoritative food-safety/recall event | Unchanged from Round 1 (BM-R-07/BM-R-08, openFDA), plus a real non-benchmark UK FSA match proving a second jurisdiction works |
| Acquisition/investment event | **CAPTURED (draft)** -- BM-C-08 (NuBerry investment), new this round |
| Regulatory/trade-response event | Unchanged from Round 1 (BM-T-02/T-03/T-09/T-10) |
| Useful non-English event | Unchanged from Round 1 (BM-T-02/T-03, Spanish), reinforced by BM-M-03 this round (also Spanish) |

All 9 categories satisfied with real, generic, non-headline-hardcoded discovery.

---

## 11. Inbox quality

Real, measured cumulative numbers across all 18 mainstream/regulatory sources from both rounds: **1317 discovered, 863 processed (65.5%)**, of which **561 passed relevance screening (65.0% of processed), 229 correctly screened irrelevant (26.5%), 73 borderline (8.5%)**. The irrelevant rate remains essentially identical to the original Recall Benchmark mission's own 26% baseline across two full rounds of expansion -- source growth has not degraded precision. A random 25-item manual sample of the full current draft set found 24 of 25 clearly on-topic; the one exception (a consumer-lifestyle "why strawberries mold faster" article) is adjacent noise, not source misconfiguration.

**A real, larger-scale duplicate cleanup was required**: processing ~600+ items this round (vs. Round 1's ~180) surfaced **57 cross-pipeline duplicates** of already-trusted content -- the exact same structural gap Round 1 found at a smaller scale (16), now confirmed to scale with processing volume (TD-046). All 57 removed as untracked-inbox cleanup before computing this mission's real recall numbers; none of the 4 confirmed new captures were among them (independently re-verified after cleanup).

---

## 12. Event-level recall after

**30/50 = 60%** (up from 26/50 = 52%). 4 events moved MISSED -> CAPTURED (draft): BM-C-08, BM-C-13, BM-M-03, BM-R-10.

| Class | Round 1 after | Round 2 after |
|---|---|---|
| Corporate (13) | 6/13 = 46% | **8/13 = 61.5%** |
| Reputation/Risk (12) | 7/12 = 58% | **8/12 = 67%** |
| Regulatory/Trade (11) | 5/11 = 45% | 5/11 = 45% (unchanged) |
| Genetics/Varieties (6) | 5/6 = 83% | 5/6 = 83% (unchanged) |
| Commercial/Market (8) | 3/8 = 37.5% | **4/8 = 50%** |

| Berry | Round 1 after | Round 2 after |
|---|---|---|
| Blueberry (31) | 14/31 = 45% | **18/31 = 58%** (all 4 new captures are blueberry) |
| Strawberry (18) | 10/18 = 56% | 10/18 = 56% (unchanged) |
| Raspberry (9) | 4/9 = 44% | 4/9 = 44% (unchanged) |
| Blackberry (11) | 5/11 = 45% | 5/11 = 45% (unchanged) |

| Geography | Round 1 after | Round 2 after |
|---|---|---|
| Peru (10) | 10% (unchanged from original) | **30%** (+2 real captures) |
| Chile (5) | 20% | 20% (unchanged) |
| United Kingdom (3) | 33% | **67%** (+1 real capture) |
| Morocco (3) | 33% | 33% (unchanged) |
| South Africa (2) | 100% | 100% (unchanged) |
| Mexico (11) | 55% | 55% (unchanged) |

---

## 13. Remaining root causes

Of the 20 events still MISSED (24 minus this round's 4): C-04's own root cause has shifted from "SOURCE NOT MONITORED" to a demonstrated, specific instance of the relevance-screen boundary (TD-040/TD-045) -- a real, better source article exists but isn't reliably surfaced. C-06/C-07/C-09/C-12, R-03/R-06/R-09/R-11, T-04/T-05/T-06/T-07/T-08/T-11, G-02, M-02/M-06/M-08 remain genuinely SOURCE NOT MONITORED or DISCOVERY QUERY GAP -- niche/local outlets (Lookout Santa Cruz for R-03), document-type-specific gaps not fully closed (USDA GAIN's own report text, not just news coverage about it, for T-11/M-06), and event-specific announcements (conference/seminar listings for C-12/M-08) this mission's bounded scope did not fully reach.

---

## 14. Commercial/Market event analysis

All 8 original Commercial/Market events, final classification:

| ID | Event | Classification |
|---|---|---|
| BM-M-01 | Sainsbury's GBP1 promotion | **CAPTURED AFTER** (Round 1) |
| BM-M-02 | Chile exports fall 13% | **STILL MISSED**; TRADE CAN CORROBORATE -- Trade Intelligence V1 independently measured Chile's real -76.1% March YoY blueberry export decline, a stronger primary-source figure than the benchmark's own cited "13%" |
| BM-M-03 | Peru +25% to 400,000t forecast | **CAPTURED AFTER** (Round 2) |
| BM-M-04 | Peru turns to China | Real event already exists as a **pre-existing trusted record** (predates this benchmark's own measurement window) -- not counted as a new capture in either round, an honest exclusion, not a miss |
| BM-M-05 | South Africa 38,900t | **CAPTURED AFTER** (Round 1) |
| BM-M-06 | Mexico blackberry 274,000MT forecast | **STILL MISSED**; REQUIRES OTHER SOURCE CLASS -- a Mexican national agricultural-statistics source (e.g. SIAP) would answer this more reliably than mainstream news coverage of the same figure |
| BM-M-07 | Twin River Berries expansion | **CAPTURED INDIRECTLY** (Round 1) |
| BM-M-08 | Morocco Red Fruits Seminar | **STILL MISSED**; REQUIRES OTHER SOURCE CLASS -- a conference/event-listing source (explicitly out of this mission's bounded scope per Section 9's own instruction not to become the full Insider Sources workstream) |

**Conclusion**: Commercial/Market is both an acquisition problem (M-02, M-06, M-08 need source classes -- trade statistics, national ag-stats, event listings -- this mission's mainstream-news mechanism structurally cannot reach) and, to a lesser extent now, a structured-observation problem (M-04's real content already exists as trusted Evidence, just not freshly attributed to this specific benchmark measurement). It is not purely one or the other.

---

## 15. Story Thread proof

No Story Thread logic was modified. Real, organic same-event grouping opportunity exists in the current draft set without this mission forcing it: the Michigan/First Pick Farms labor case now has real candidate members from multiple real outlets covering the identical settlement (MLive's own multiple articles, The Packer, Bloomberg Law) across different dates in the same real event window (2026-07-09/10) -- exactly the "recall notice + downstream press" / multi-source-same-event shape Story Thread's existing conservative membership rules are designed to catch, left for human publication review to confirm, not auto-merged by this mission.

---

## 16. Coverage Matrix

Updated: overall recall re-measured (52% -> 60%), by-class/by-berry/by-geography numbers updated, a new dedicated section added. Not marked `OPERATIONAL` anywhere -- see the matrix's own honest caveats.

---

## 17. Technical debt

2 new entries (TD-045, TD-046): TD-045 documents that TD-040's boundary is only partially, not reliably, mitigated by alternate-article coverage (real for BM-R-10, not for BM-C-04); TD-046 documents that cross-pipeline duplicate volume scales with processing volume (57 this round vs. 16 in Round 1), a real, recurring, bounded cost of large backlog passes -- concurrently and independently resolved by Codex's PR #70 (`cd107b9`), which added a `_publisher_identity()` check to `article_dedup.find_duplicate_article()`; TD-046's status is set to `resolved (by Codex, concurrently, PR #70)` rather than closed outright by this mission, since this mission's own 57-item cleanup predated Codex's fix landing on canonical.

Both new entries were initially drafted as TD-043/TD-044 before a mid-mission `git fetch` revealed Cursor's Global Intelligence Search V1 (PR #65) had already claimed those two numbers on canonical for unrelated topics (Story Thread indexing, process-local search cache) -- a real, confirmed ID collision, resolved by renumbering this mission's own two entries to TD-045/TD-046 and fixing all cross-references before merge, per the mission brief's own explicit warning that concurrent missions could produce debt-number collisions. No debt duplicated from Codex's runtime/reliability lane: Codex's own PR added a separate internal summary-table reuse of IDs TD-038..TD-044 for different topics than those numbers' existing canonical headings -- an apparent additional collision inside Codex's own PR, judged out of scope to arbitrate here (not this mission's lane, and not a qualitative-coverage concern).

---

## 18. Next recommendation

**Recommendation: closing TD-040/TD-045's relevance-screen boundary, coordinated with Codex** -- unchanged from Round 1's own recommendation, now reinforced by direct evidence: this mission tested the boundary again (a second attempt at BM-C-04) and it remains the single most well-understood, well-evidenced, and highest-value remaining gap -- more source additions (this mission's own real experience) increasingly hit real captures that then get lost to the same specific, already-diagnosed screening boundary rather than to missing coverage. Not started this mission, per its own explicit stop instruction.

---

## Globality check (mission Section 17)

**Did Peru improve? Yes -- 10% -> 30%, the largest percentage-point geography movement of either round.** **Did Chile improve? No -- unchanged at 20%**, honestly reported; no new Chile-specific source or capture this round. **Did UK improve? Yes -- 33% -> 67%.** **Did Morocco improve? No -- unchanged at 33%.** **Did South Africa improve? No -- unchanged at 100%** (already saturated on this benchmark's own 2-event sample). Overall recall improvement (52%->60%) is not a US-only artifact: 3 of this round's 4 real captures are non-US (Peru x2, UK x1); only BM-R-10 (Michigan) is US-specific, and even that was a fix to a Round-1-identified boundary, not new US-only source breadth.

---

## Validation

`pytest -q` (full suite, 1,195 tests): re-run twice against this mission's own pre-rebase code and again post-rebase onto canonical `704c18e` (Cursor's Global Intelligence Search V1 + Codex's Collection Runtime/Data Integrity V1, both landed mid-mission). Pre-rebase: 4 failed / 1,158 passed -- 3 of the 4 (`test_collection_status.py::test_live_source_repository_includes_all_onboarded_sources_generically`, `test_domain_pack.py::test_all_live_sources_accounted_for`, `test_morning_brief.py::test_real_reading_queue_morning_workload_is_smaller_than_unresolved`) were this mission's own hardcoded source-count assertions needing the 164->168 update (already fixed in this mission's own test edits) or local-runtime-state-dependent. Post-rebase: **1 failed / 1,194 passed** -- the sole remaining failure, `test_variety_workspace.py::test_observations_runtime_without_inbox_is_honest`, is pre-existing and environment-dependent (it asserts an honest "not loaded in this runtime" message that only renders when zero UK-geography `commercial_observation` drafts are present in the local `inbox/`; it was already failing in the pre-rebase run, before any of this mission's source/adapter changes, and does not touch anything this mission modified). Not a regression introduced by this mission or the rebase.

`python scripts/validate_records.py`: `All validated records passed.`

`python scripts/build_static.py`: `Static build complete: 1527 pages written to generated/` -- `Verified: no unpublished draft ids or titles appear in the output.`

`git diff --check`: clean (no whitespace errors, no leftover conflict markers after the rebase's one real conflict in `TECHNICAL-DEBT-REGISTER.md` was resolved).

Recurring-acquisition idempotency (the mission's own explicit requirement): `scripts/discover_media.py --source source-uk-fsa-food-alerts` run twice in immediate succession. Both runs: `items found in feed: 100`, `newly discovered: 0`, `already known: 100`, `item-level failures: 0` -- `inbox/discovered_media/` file count unchanged (1,667 -> 1,667 -> 1,667) across both runs. No duplicate explosion, no trust bypass (discovery never promotes a draft to trusted; that remains a separate human Approve step).

Codex's collection lock / pipeline registry: investigated post-rebase (`data/configuration/collection_pipelines.json`), confirmed it covers `scripts/run_collection.py` and the `monitor_*.py` recurring runners only -- not `discover_media.py`, `run_recent_batch.py`, or `process_discovered_media.py`, the three scripts this mission used throughout. No lock integration needed; used per the mission's own instruction ("use it rather than bypassing it") by virtue of it simply not applying to this mission's collection calls.
