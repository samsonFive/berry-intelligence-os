# Relevance Screen Boundary V1

**Mission:** Relevance Screen Boundary V1 (2026-08-23, branch `feature/relevance-screen-boundary-v1`). Global Qualitative Coverage Expansion V2 established that the dominant remaining miss cause is no longer a missing source but the relevance-screen/metadata-thin boundary (TD-040/TD-045). This mission fixes that gate generically -- discovery to useful review -- without adding source volume.

---

## 1. Canonical

Fetched origin fresh at mission start: `e1ae5d0` (merge of PR #74, "Collection Runtime + Data Integrity V1 production proof"), moved from the last-known `902daff`. Read current `AGENTS.md`, `PROJECT-STATUS.md`, `docs/v2/TECHNICAL-DEBT-REGISTER.md`, `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`, `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`, `docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V2.md`, `docs/v2/COLLECTION-RUNTIME-DATA-INTEGRITY.md` before starting. Highest occupied Technical Debt ID confirmed as TD-054 (Codex's own production-proof mission claimed TD-047 through TD-054); this mission's new entries initially drafted at TD-055 through TD-058.

Canonical moved mid-mission -- `e1ae5d0` -> `9991171` (Codex's Production Collection Operations V1, PR #76/#77) -- discovered on the mandatory pre-merge re-fetch. Rebased cleanly (`scripts/run_collection.py` and `docs/v2/TECHNICAL-DEBT-REGISTER.md` auto-merged with zero real conflicts, since the two missions' edits landed in disjoint regions of both files; only `PROJECT-STATUS.md` needed manual reconciliation). The re-fetch also surfaced a real Technical Debt Register ID collision: Codex's own concurrent mission independently claimed TD-055/TD-056/TD-057 (as compact summary-table rows, not full entries) for unrelated production-operations topics (fixed-window quantitative scheduling, analyst review-throughput backlog, acquisition reliability). This mission's own four new entries were renumbered up to **TD-058 through TD-061** to avoid the collision, all cross-references fixed across this doc, `docs/v2/TECHNICAL-DEBT-REGISTER.md`, `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`, and `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`.

---

## 2. Relevance pipeline audit

Traced the real code paths, not inferred from planning docs, per the mission's own explicit instruction. Found two separately-built, real relevance mechanisms coexisting:

- `app/services/relevance_screen.py` (versioned `relevance-screen-v3`): two-stage, berry-identity-gated, body-aware. Stage A (title/description only): a direct berry/company name is CONFIDENT-relevant; **zero category signal at all is CONFIDENT-irrelevant with no path to reconsideration**; anything in between is BORDERLINE and needs a real article-body check. Stage B (body-aware, only reached from a Stage A BORDERLINE): requires species recurrence across >=2 paragraphs, a company name, or a single mention plus an adjacent-topic signal.
- `app/services/relevance_screening.py` (`screen_discovered_item`, unversioned, older): single-stage, metadata-only, substring-matching (no word-boundary enforcement), score-threshold decision (`process`/`skip`/`borderline`). **No body-fetch capability of any kind.**

The real, previously-undocumented finding: `app/services/article_acquisition.fetch_article()` -- the only function in the codebase that fetches a real article body -- was called from exactly one place, `app/services/article_refresh.process_discovered_article()`, itself called from exactly two places: `scripts/run_collection.py` (Codex's recurring pipeline) and `scripts/ingest_articles.py` (a little-used standalone CLI). **`scripts/process_discovered_media.py` and `scripts/run_recent_batch.py` -- the actual, documented, real-world operator workflow (`AGENTS.md`'s own "Operating path") -- never called `process_discovered_article()` at all.** They used `MediaOrchestrationService.process()`, which screens `web_article` items with the cruder `relevance_screening.py` module and never fetches a body. Verified directly: every real `web_article` draft ever created via this project's own documented workflow across its entire multi-mission history has `article: null` -- confirmed on two known real captures (BM-C-13/Hall Hunter, and the pre-existing BM-C-08-adjacent Agroberries draft).

This means the two-stage screen's own Stage B -- carefully engineered against real false positives (onion/apple/fig/pear-solar stories) across prior missions -- was effectively dead code from the real operator's perspective, reachable only via the recurring pipeline and a rarely-invoked CLI.

---

## 3. Real failure corpus

Reproduced the exact TD-040/TD-045 case directly against real, live data: the discovered `discovered-source-news-search-berry-investment-latam-...` item, title `"UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU TO FURTHER STRENGTHEN ITS GLOBAL MULTI-FRUIT PLATFORM - PR Newswire"`. Ran through both real screening modules:

- `relevance_screen.screen_relevance()`: score 0 (title contains zero category terms of any kind, not even generic agriculture vocabulary) -> `CONFIDENT irrelevant`, `tier=irrelevant`, no body check ever attempted.
- `relevance_screening.screen_discovered_item()` (the module the real workflow actually used): score 2 (only "peru" matched, a MEDIUM_WEIGHT_TERM) -> `decision="skip"` (skip_threshold=3), also no body check (this module has none).

Measured the real scale of this pattern across the current `inbox/discovered_media/` backlog: of 1,384 `web_article` items from the 19 `news_search_rss` (Google News query) sources, **309 (22%) score literally zero at Stage A metadata**. Sampled these directly rather than assuming the pattern: mostly genuine non-berry noise (a `MarshBerry` insurance-industry acquisition, Alaska Airlines expansion, a Cleveland Browns "investment" story), but a real, bounded, checkable subset carries genuine berry-industry corroboration.

---

## 4. Root cause

Two distinct, compounding causes, both real:

1. **Architecture gap**: the real operator workflow never invoked the two-stage, body-aware screen for `web_article` items at all (Section 2).
2. **Logic gap inside the better module**: even when reached, a zero-signal Stage A metadata screen had a hard CONFIDENT-irrelevant exit with no reconsideration path -- correct for the general web (most zero-signal items really are unrelated, per the sampled noise above), but wrong for items discovered by a source whose own query is already berry/company/geography-scoped.

---

## 5. Implementation

**Fix 1 -- wire the real workflow to the real two-stage screen.** `scripts/process_discovered_media.py` (under `--relevance-gate`) and `scripts/run_recent_batch.py` now route `web_article` items through `article_refresh.process_discovered_article()` instead of `MediaOrchestrationService.process()`'s metadata-only path. `relevance_screening.py` remains in use for spoken media (podcast/video) in both scripts, where transcript acquisition already plays the "real body" role Stage B plays for articles -- a deliberate, principled split, not an oversight (TD-061).

**Fix 2 -- query-provenance corroboration** (`app/services/relevance_screen.py::_query_corroboration_hit`). When Stage A scores zero, before confidently rejecting, check whether the title also names a **registered** Geography or Company entity (`app/services/deterministic_tagging.py`'s own canonical matcher, no second alias system, per the mission's explicit Section 7 instruction) alongside a narrow corporate-action verb (acquire/invest/expand/launch/partner/merger/buys/stake/acquisition). A hit keeps Stage A at BORDERLINE (reopens Stage B) instead of CONFIDENT-irrelevant. **This never grants relevance by itself** -- it only reopens the real check; Stage B's existing, unchanged berry-identity gate remains the sole arbiter of DIRECT/ADJACENT/IRRELEVANT when the body is fetchable.

Continent-level Geography entities (`geography-europe`, `geography-north-america`) are deliberately excluded from the corroboration matcher -- real regression found "Plastic Ingenuity makes first acquisition in Europe" (a packaging company, zero berry connection) would otherwise corroborate on "Europe" alone.

**Fix 3 -- the `TIER_UNCERTAIN` fallback.** When query-provenance corroboration keeps Stage A open but the article body is genuinely unverifiable (the dominant real case: a Google News redirect page with no server-rendered content, `empty_body`), the system now creates an explicitly-labeled `TIER_UNCERTAIN` untrusted draft for human review instead of either (a) silently dropping the item or (b) forcing a confident DIRECT claim query provenance alone cannot support. The draft's own `relevance_tier` field is persisted onto the stored file (a real, small companion fix: the pre-existing metadata-only-fallback branches never wrote `relevance_tier` onto the persisted draft at all, only onto the transient in-memory result -- fixed for both the existing TIER_DIRECT fallback and the new TIER_UNCERTAIN one).

**Fix 4 -- French species vocabulary.** Added `myrtille(s)`/`fraise(s)`/`framboise(s)` (blueberry/strawberry/raspberry) to the `berry_identity` category, and `fruits rouges` (a French collective term for red berries, no named species) to the non-auto-triggering `generic_berry_mention` category, mirroring the exact treatment English `berry`/`berries` already has. French `mûre`/`mûres` (blackberry) deliberately excluded -- it is also the ordinary French adjective for "ripe" ("une fraise mûre"), a collision risk even higher than the already-excluded Italian "more" (TD-060).

---

## 6. Query provenance handling

Per the mission's own explicit example ("query: 'Peru blueberry investment' / article: 'Company announces $40m expansion in Ica'" -- query terms justify inspection, never alone justify "this is a blueberry investment"): the corroboration mechanism never sets `relevant=True` or a confident tier by itself. It only flips `confidence` from `CONFIDENT` to `BORDERLINE`, which routes the item to a real body check (Stage B) when the body is fetchable, or to the explicitly-uncertain fallback when it is not. Real proof this boundary holds: `test_real_unifrutti_headline_is_kept_open_by_geography_plus_action_verb` asserts `relevant is False` even on the corroboration hit itself; `test_query_corroborated_item_still_lets_stage_b_decide_when_body_is_fetchable` proves that when a body IS fetchable, real content -- not the corroboration hint -- decides the final tier.

---

## 7. Metadata-thin handling

Evidence sources actually used, all real and already-retrieved (never fabricated): title, description, canonical URL (to detect the Google News redirect pattern), publisher identity (`raw_metadata.origin_publisher_name`), the discovering source's own registered `berry_ids`/`entity_types` (considered but found too broad -- 144 of 168 sources carry non-empty `berry_ids`; see Section 9), and the platform's own already-registered Geography/Company entity graph. No new alias system, no LLM call, no fabricated relevance.

---

## 8. Non-English proof

Re-tested Spanish (already covered by an earlier mission) and French (previously assumed to work end-to-end because *discovery* succeeded, but relevance screening was never separately verified) directly against a live source. Real finding: `source-news-search-morocco-berry-fr` (French-language Morocco source, onboarded in an earlier mission) had **zero French berry-species vocabulary** in the relevance screen -- 45 of its 50 real discovered items scored 0 and were confidently, permanently rejected despite genuinely covering Moroccan blueberry/strawberry/raspberry trade news (AgriMaroc, Le360, Bladi.net, Hespress). The gap was specifically **berry vocabulary**, not discovery, extraction, or normalization -- the titles were already correctly stored as clean UTF-8 (verified directly, bypassing a Windows-console display artifact that initially looked like mojibake but was purely a terminal encoding issue, not a data-integrity one). Fixed with 6 new terms; real re-processing of the full 50-item backlog: **45 of 50 (90%) now produce real, review-ready drafts**, up from a small handful that happened to also carry generic agriculture terms. The remaining 5 are all bare "fruits rouges" headlines with no other signal -- correctly left unresolved (access-limited, Google redirect) rather than force-promoted.

Blackberry-specific French identity ("mûre") remains a real, deliberately-undemonstrated gap (TD-060) -- not attempted, given the collision risk with ordinary French ripeness vocabulary and no real French blackberry false-negative observed in this mission's own bounded testing.

---

## 9. Trust boundary

No change to publication review, Atomic Evidence review, or any trust gate. Every draft this mission's mechanism creates -- `TIER_UNCERTAIN` included -- is written with `status: "draft"`, `review_state: "in_review"`, exactly like every other publication draft; verified directly on the real Unifrutti draft (`ev-media-95a9ba13f6c56e5a7379`). `TIER_UNCERTAIN`'s entire purpose is to make an *unconfirmed* relevance decision honestly visible rather than either hiding it (silent drop) or overstating it (a false DIRECT claim) -- the draft's own reason text says explicitly "relevance not confirmed by article body." Query-provenance corroboration was deliberately scoped away from the broad "any source with non-empty `berry_ids`" signal (144/168 sources) precisely because that would have been too close to trusting the query alone; the final design requires a real, inspectable title-level fact (a registered entity name) independent of which source discovered it.

---

## 10. Performance

Cheap path (Stage A metadata, the overwhelming majority of items): unchanged, microseconds, no network call, no regression -- confirmed by the full pytest suite's runtime being dominated by unrelated slower integration tests, not this module. Uncertain/richer path (Stage B body fetch, now reachable from the real workflow): one bounded `fetch_article()` call per item that reaches BORDERLINE, exactly as `run_collection.py` already budgeted for the recurring pipeline; no new unbounded fetching was added -- corroboration narrows candidates to a small, real subset (16 of 309 real zero-signal items measured, ~5%) rather than attempting Stage B on all 309. Never placed on an unrelated synchronous page request -- this is a batch/CLI-only concern, `app/main.py` request handlers are untouched.

---

## 11. Precision/review load

Real, measured, not estimated. Across the full real reprocessing this mission performed (French Morocco batch of 50 + 19 individually-verified corroboration candidates from the Costa Group/Driscoll's/African Blue/Naturipe/TSBC clusters):

| Category | Count |
|---|---|
| Items reconsidered (French vocabulary fix) | 50 |
| Items reconsidered (query-provenance corroboration, individually verified) | 19 |
| New real review-ready drafts created (French) | 44 `direct` (of 45 "review-ready" reported by the batch, 1 was a pre-existing draft from before this mission) |
| New real review-ready drafts created (corroboration) | 17 (`direct`: 3 -- African Blue/FreshPlaza, a Spanish antidumping-risk story, South African MSC coverage, each already carrying a recognized species/company term; `uncertain`: 14 -- Unifrutti plus the Costa Group/Driscoll's/African Blue-stake/fashion-capsule/hunger-strike/COO-appointment/Mainland-dumping/Naturipe cluster) |
| Total new drafts this mission | 61 (47 `direct`, 14 `uncertain`) |
| True useful matches (manually inspected) | Unifrutti (BM-C-04, the target case); a real 5-article Driscoll's/Costa Group stake-acquisition cluster; Agroberries/BerryWorld Asia; African Blue (Morocco) acquisition/expansion coverage; Naturipe Farms expansion -- all real, genuine berry-industry corporate events |
| False positives (manually inspected) | 0 confirmed among the created drafts; 1 pre-existing (not new) false positive incidentally found in the review queue from before this mission ("Mandarines..." mis-tagged by the older screener) -- noted, not fixed, out of this mission's own scope |
| Access-limited (correctly left unresolved, not force-promoted) | 5 (bare "fruits rouges" French headlines with no other signal) |
| Still uncertain (query-corroborated, body unverifiable) | 14 `TIER_UNCERTAIN` drafts -- explicitly labeled, not counted as confident |

This mission does not flood the review queue: query-provenance corroboration fires on ~5% of the real zero-signal backlog (16 of 309 measured items carry a real corroboration hit), not on volume for volume's sake.

---

## 12. Benchmark before

30/50 (60%) -- Global Qualitative Coverage Expansion V2's own final state, re-confirmed via `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md` Section 11 and `docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V2.md`.

---

## 13. Benchmark after

**31/50 (62%).** By class: Corporate 8/13 (62%) -> 9/13 (69%); Reputation/Risk unchanged 8/12 (67%); Regulatory/Trade unchanged 5/11 (45%); Genetics/Varieties unchanged 5/6 (83%); Commercial/Market unchanged 4/8 (50%). By berry: Blueberry 19/30 (63%) -> 20/30 (67%); others unchanged. By geography: Peru 3/9 (33%) -> 4/9 (44%); others unchanged.

---

## 14. Events recovered

**1**: BM-C-04 (Unifrutti Group acquires Bomarea + AvoAmerica Peru), MISSED -> CAPTURED (draft, `uncertain`). Resolved via query-provenance corroboration (title names "Peru", a registered Geography entity, alongside "acquires"), not via an alternate article -- a genuinely different mechanism than the one TD-045 previously documented as unreliable.

---

## 15. Remaining misses

19 of the fixed 50 events remain MISSED. Honest, class-grouped assessment of why, per the mission's own root-cause discipline:

- **Genuinely not yet discovered** (SOURCE NOT MONITORED, unchanged by this mission -- it targets the discovery-to-review gate, not source coverage): BM-C-06, BM-C-07, BM-C-09, BM-C-12, BM-R-03, BM-R-06, BM-R-09, BM-R-11, BM-T-04, BM-T-05, BM-T-06, BM-T-07, BM-T-08, BM-T-11, BM-G-02, BM-M-02, BM-M-04, BM-M-06, BM-M-08.
- **Relevance-screen-boundary cases specifically targeted by this mission**: only BM-C-04 was a confirmed, reproducible instance in the current backlog. The mechanism is now real and generic, but this benchmark's own remaining 19 misses are predominantly items never discovered at all, not items discovered-then-lost at screening -- the dominant remaining cause is shifting back toward source/query coverage for the *specific* fixed 50 events, even though the relevance-screen mechanism itself now generalizes well (Section 11's broader real captures).

---

## 16. Coverage Matrix

Updated only where measured recall changed: overall 30/50->31/50, Corporate class, blueberry berry, Peru geography. No `OPERATIONAL` claims added. See `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`'s new "Relevance Screen Boundary V1" section.

---

## 17. Technical debt

TD-040 updated to `partially resolved` (the demonstrated case is fixed; the general "any bare press release" case is not, tracked as TD-058). TD-045 updated to `resolved` for its own cited BM-C-04 case (via a different mechanism than alternate-article coverage, which remains unreliable on its own terms, unchanged). 4 new entries: TD-058 (corroboration only rescues entity-named titles), TD-059 (Google News redirect structurally unverifiable, the dominant real constraint), TD-060 (French "mûre" deliberately excluded), TD-061 (the two-relevance-module architecture, now principled rather than accidental).

---

## 18. Next recommendation

Not started, per this mission's own explicit stop instruction. Candidate for a future mission: prefer direct publisher RSS/JSON feeds over Google News search queries where a given publisher already has one (would sidestep TD-059's redirect problem at the source-configuration level) -- evaluate only as a separate, explicitly-scoped mission, not as source-volume expansion for its own sake.

---

## Validation

`pytest -q` (full suite): 1,208 passed, 1 failed -- `tests/test_variety_workspace.py::test_observations_runtime_without_inbox_is_honest`, the same pre-existing, environment-dependent failure documented in every prior mission on this shared dev machine (depends on zero UK-geography `commercial_observation` drafts being loaded locally, which has not been true since the Variety Backbone V1 mission), unrelated to any file this mission touched.

`python scripts/validate_records.py`: `All validated records passed.`

`python scripts/build_static.py`: `Static build complete: 1527 pages written to generated/` -- `Verified: no unpublished draft ids or titles appear in the output.`

`git diff --check`: clean.

Idempotency (recurring acquisition mechanism, run twice): `scripts/discover_media.py --source source-news-search-morocco-berry-fr` -- both runs: `items found in feed: 50`; second run: `newly discovered: 0`, `already known: 50`, `item-level failures: 0`; `inbox/discovered_media/` count unchanged across the re-run. `scripts/process_discovered_media.py --item <unifrutti-id> --relevance-gate` re-run: idempotent short-circuit (`orchestrator.resolve_publication_artifact()` finds the existing draft, no duplicate created, `inbox/evidence/` count unchanged before/after). No cross-pipeline duplicate titles found between this mission's new drafts and any already-trusted `data/evidence/` record (checked directly, 0 collisions). No trust bypass: every new draft remains `status: "draft"`, `review_state: "in_review"`.

---

## Direct answers

1. **How much did recall increase?** 30/50 (60%) -> 31/50 (62%), +1 event, on the same fixed 50-event benchmark with no redefinition.
2. **How many events were already discovered but previously lost at relevance screening?** 1 confirmed, reproducible case in the current benchmark (BM-C-04). The mechanism itself is real and generic (measured against 309 real zero-signal items backlog-wide, with 16 real corroboration hits and 44 more real captures via the separate French-vocabulary fix), but only one directly maps onto one of the fixed 50 benchmark IDs.
3. **Did review precision remain acceptable?** Yes -- 0 confirmed false positives among this mission's newly-created drafts (manually inspected); query-provenance corroboration fired on ~5% of the real zero-signal backlog, not a flood; every new draft stays untrusted pending human review.
4. **Does the system now handle metadata-thin search results generically?** Partially and honestly bounded: yes for items whose title also names a registered entity (query provenance + real-entity corroboration), no for a genuinely bare press release naming nothing the platform already tracks (TD-058) -- a real, principled boundary, not a full solve.
5. **Did non-English metadata-thin items improve?** Yes, substantially for French (45/50 -> real review-ready drafts from a single source, up from a small handful) -- the root cause was missing berry vocabulary specifically, not discovery, extraction, or normalization. Spanish was already covered by an earlier mission; not re-broken, re-verified working.
6. **Was richer body inspection necessary?** Yes for the general architecture fix (wiring the real workflow to real Stage B body-fetch capability it never had), but the dominant real case (Google News redirect pages) makes body inspection structurally unavailable regardless -- query-provenance corroboration plus an honest `TIER_UNCERTAIN` label was the necessary complement, not a substitute philosophy.
7. **Did any relevance mechanism weaken trust semantics?** No. Every new/changed code path only ever creates an untrusted draft, same publication-review gate as before; `TIER_UNCERTAIN` makes an unconfirmed decision more honest, not less trustworthy.
8. **What is the largest remaining recall blocker?** For the fixed 50-event benchmark specifically: source/query coverage for the 19 remaining misses (predominantly never-discovered, not discovered-then-lost). For the relevance-screen boundary itself, now that the demonstrated case is fixed: the structural Google News redirect limitation (TD-059), which caps how much of `TIER_UNCERTAIN`'s real value can convert into body-confirmed DIRECT relevance rather than staying explicitly uncertain pending human review.
