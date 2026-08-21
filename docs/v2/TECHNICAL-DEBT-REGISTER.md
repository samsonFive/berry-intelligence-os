# Technical Debt Register

Living register for **current** Intelligence OS V2 debt. This is not a changelog.
Historical work that is already shipped stays out of ACTIVE unless it still
hurts operators or trust.

**How to update:** every source/domain expansion, V2 surface migration, or
performance finding that remains after the PR should add or close a row here.
Do not invent coverage in `INTELLIGENCE-COVERAGE-MATRIX.md` to hide a gap;
record the gap here if it is operational debt.

Status values: `active` · `limitation` · `resolved` · `monitoring`

Owner lanes: `platform` · `product` · `data` · `ops`

ID aliases from the expansion-guide session's withdrawn draft (do not reopen
these as Open UI-lane items):

| Withdrawn ID | This register |
|---|---|
| TD-UI-001 | TD-001 **resolved** (cold ranking closed as KL-011) |
| TD-UI-002 | TD-002 **resolved** (authoring gap closed as TD-012) |
| TD-UI-003 | TD-003 **resolved** |
| TD-UI-004 | TD-004 **resolved** |
| TD-ACQ-001 | TD-006 **active** |
| TD-THREAD-001 | **resolved** in PR #51 (`807e059`) |

Unique withdrawn-draft items below keep their original IDs.

---

## ACTIVE DEBT

### TD-005 — D-012 explicit scope not wired to Landscape routes

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data / landscape |
| **Date discovered** | 2026-08-14 (still current) |
| **Evidence** | `PROJECT-STATUS.md`: Landscape Assessment/Recommendation branch still uses derived entity intersection, not `ScopeQueryService.explicit_scope()`. |
| **Impact** | Multi-berry companies can pull blueberry-scoped assessments onto a strawberry Landscape. Related to TD-002. |
| **Workaround** | Read `market_ids` on the Assessment record itself. |
| **Recommended resolution** | Wire explicit scope when Landscape migrates with Variety / Retail / Registry expansion. Do not migrate Landscape in this batch. |
| **Status** | active |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `app/queries/scope.py`; Landscape tests when that surface migrates |

### TD-006 — Cross-pipeline article dedup gap

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection / data |
| **Date discovered** | 2026-08-18 (still current) |
| **Evidence** | Same as withdrawn TD-ACQ-001. `PROJECT-STATUS.md` / `app/services/article_dedup.py`: same story under Google-News redirect vs publisher RSS is different URL + `source_id` (recurring draft `ev-media-cec61845f15d790fd055`). Deterministic URL/title+source+date matching cannot merge them without fuzzy title matching (explicitly refused). **More precise root cause found by the Mainstream News + Regulatory Coverage Recall Benchmark V1 mission (2026-08-21):** `MediaOrchestrationService._cross_pipeline_duplicates()` (`app/services/media_orchestration.py:637-666`) filters its dedup candidate pool to `evidence_role == "publication_artifact"` before calling `find_duplicate_article()` -- a trusted record captured by the older `app/main.py` keyword/RSS auto-capture loop (pre-`evidence_role`, `submitted_by: "source-monitor:..."`) has `evidence_role: None` and is silently excluded from the candidate pool, so even an *exact canonical-URL match* against it is never checked. Reproduced directly: `source-news-search-driscolls`'s real run created a duplicate of the already-trusted `ev-20260806173540-993a-driscoll-s-filed-appeal-in-strawberry-pa.json` (`evidence_role: None`, `submitted_by: "source-monitor:Strawberry cultivar patent"`) via the identical `news.google.com` redirect URL. 9 such duplicates were produced by this mission's 3 new sources alone and removed as untracked-inbox cleanup. |
| **Impact** | Duplicate trusted or pending rows. Operators dismiss by hand. |
| **Workaround** | Inbox cleanup of known duplicates. |
| **Recommended resolution** | Keep deterministic matching. Optional later: publisher canonical-id when the Source record declares one. **Now that the exact line is known:** broaden `_cross_pipeline_duplicates()`'s candidate filter to include trusted records regardless of `evidence_role` (a missing `evidence_role` on an otherwise-evidence-shaped trusted record should be treated as implicitly `publication_artifact`-equivalent for dedup purposes only) -- a quick fix, not attempted in the recall-benchmark mission to keep that mission's changes scoped to discovery. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_article_dedup.py`. A real regression test (a trusted record with `evidence_role: None` should still be recognized as a duplicate by URL) would directly cover the newly-found root cause and does not yet exist. |

### TD-007 — Production store still JSON; Phase 3 PostgreSQL not started

| Field | Value |
|---|---|
| **Severity** | Medium (strategic) |
| **Area** | persistence |
| **Date discovered** | 2026-08-14 (still current) |
| **Evidence** | `PROJECT-STATUS.md`: PostgreSQL and Phase 3 remain not started. |
| **Impact** | No FK enforcement; `list_drafts()` still filesystem-direct. |
| **Workaround** | JSON repositories + `validate_records.py`. |
| **Recommended resolution** | Phase 3 when authorized. Not this batch. |
| **Status** | active |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `docs/v2/PHASE-2-REPOSITORY-REQUIREMENTS.md` |

### TD-008 — Continuous collection not scheduled on the VPS

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | ops |
| **Date discovered** | 2026-08-16 (still current) |
| **Evidence** | `docs/v2/CONTINUOUS-INTELLIGENCE-REFRESH.md`: implemented, not scheduled. |
| **Impact** | Discovery/review still operator-driven. |
| **Workaround** | `scripts/run_recent_batch.py` by hand. |
| **Recommended resolution** | systemd timer on the demo VPS when Johnny authorizes unattended runs. |
| **Status** | active |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `docs/v2/CONTINUOUS-INTELLIGENCE-REFRESH.md` |

### TD-009 — YouTube acquisition operational limits

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection |
| **Date discovered** | 2026-08-16 (still current) |
| **Evidence** | Bot-check (`retryable`); no in-repo cookie session; some publisher classes need a JS runtime; `yt-dlp` pin is maintenance-sensitive; YouTube feed ~15-item ceiling. |
| **Impact** | Tier-3 / some channels fail until re-run or environment change. |
| **Workaround** | Re-run later; captions path when available. |
| **Recommended resolution** | Documented in `RECURRING-COLLECTION-RUNNER.md`. Do not add auth-bypass. |
| **Status** | active |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `docs/v2/RECURRING-COLLECTION-RUNNER.md` |

### TD-010 — Seed fixtures mixed with live evidence

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data |
| **Date discovered** | 2026-08-14 (still current) |
| **Evidence** | `SEED_FIXTURE_*` in `app/services/berries/landscape.py`; raspberry “published patent” count includes `ev-sample-patent-published`. |
| **Impact** | Coverage matrix and Landscape can overstate a class unless fixtures are named. |
| **Workaround** | Landscape excludes the three named sample ids. Coverage matrix notes the seed patent. |
| **Recommended resolution** | Structural `seed`/`demo` flag before Postgres seed (R-12). |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `docs/v2/09-RISK-REGISTER.md` R-12 |

### TD-THREAD-002 — Live `/threads` universe is pending + one seed only

| Field | Value |
|---|---|
| **Severity** | Low–Medium |
| **Area** | story threads / routes |
| **Date discovered** | 2026-08-20 |
| **Evidence** | `story_thread_reader()` and `_intelligence_page_context()` build `universe` from `list_pending_drafts()` plus at most the currently viewed published record. Trusted-only clusters never thread in the live UI. |
| **Impact** | Published same-event coverage is not assembled as a thread unless a pending draft is also in the set. Product decision, not a silent matcher bug. |
| **Workaround** | Tests assemble a broader universe by hand. |
| **Recommended resolution** | Decide whether trusted-only clusters should surface in live UI; if yes, include recently published Evidence in `universe`. Do not loosen membership rules. |
| **Status** | active |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `app/main.py` thread routes; `tests/test_story_threads.py` |

### TD-ACQ-002 — Growing Produce berries feed returns 403

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / source health |
| **Date discovered** | 2026-08-20 |
| **Evidence** | `source-20260819-growing-produce-berries` returned HTTP 403 during Strawberry Vertical V1. Not scraped around. |
| **Impact** | That discoverable source fails until the publisher allows the feed again. |
| **Workaround** | Skip; do not add a brittle scraper. |
| **Recommended resolution** | Re-check periodically; if persistent, mark the source discovery block inactive. |
| **Status** | monitoring |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `data/configuration/sources.json` |

### TD-ACQ-003 — NARBA raspberry/blackberry RSS is well-formed but empty

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / source health |
| **Date discovered** | 2026-08-20 |
| **Evidence** | `raspberryblackberry.com/feed/` is live RSS 2.0 with zero `<item>` entries as of 2026-08-20. Not onboarded. |
| **Impact** | None currently. Highest-value not-yet-useful source for blackberry depth. |
| **Workaround** | Leave unregistered until items exist. |
| **Recommended resolution** | Re-check before blackberry depth work. |
| **Status** | monitoring |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-ACQ-004 — Non-English relevance verified for Spanish/Italian only

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection / relevance |
| **Date discovered** | 2026-08-20 |
| **Evidence** | `relevance_screen.py` `berry_identity` now has Spanish/Italian species names. Polish/Dutch/Portuguese titles exist in the corpus and were not given the same explicit test. |
| **Impact** | A Polish- or Dutch-language source may under-recall until those terms are verified. |
| **Workaround** | Do not assume the Spanish/Italian pattern holds for a third language. |
| **Recommended resolution** | Explicit language-term test before onboarding a Polish- or Dutch-language source. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `app/services/relevance_screen.py` |

### TD-ENT-001 — Domain-pack predicates wider than schema enum

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | domain model |
| **Date discovered** | 2026-08-20 |
| **Evidence** | `relationship-predicates.json` declares 16 predicates; `schemas/relationship.schema.json` enum accepts 10. Raspberry V1 could not use `administers_license_for` and fell back to `licenses`. |
| **Impact** | Documented extensions are unusable at validation time. |
| **Workaround** | Use one of the enforced 10 predicates. |
| **Recommended resolution** | Either extend the live schema enum or correct the domain-pack spec to the enforced set. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `schemas/relationship.schema.json`; `tests/test_domain_pack.py` |

### TD-ENT-002 — Allberry B.V. vs Advanced Berry Breeding B.V.

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | entity resolution |
| **Date discovered** | 2026-08-20 |
| **Evidence** | Raspberry patent drafts “ABB 135”/“ABB 136” assigned to Allberry B.V., not Advanced Berry Breeding B.V. Shared ABB naming + inventor Niels Arts is circumstantial only. Left unlinked. |
| **Impact** | Those drafts stay unresolved assignees. |
| **Workaround** | Do not force-alias. |
| **Recommended resolution** | Netherlands KVK (or equivalent) lookup before linking. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-ENT-003 — USDA-ARS assignee has no entity

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | entity resolution |
| **Date discovered** | 2026-08-20 |
| **Evidence** | Finnberry raspberry patent assigned to “The United States Of America, As Represented By The Secretary Of Agriculture” with no matching graph entity. |
| **Impact** | USDA-assigned filings stay permanently unresolved. |
| **Workaround** | Leave unresolved rather than invent an entity from a draft. |
| **Recommended resolution** | Add `company-usda-ars` or `breeding_program-usda-ars` with that exact assignee string as an alias. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-REVIEW-001 — Variety announcements waiting in untrusted drafts

| Field | Value |
|---|---|
| **Severity** | Low (backlog, not a bug) |
| **Area** | human review |
| **Date discovered** | 2026-08-20 |
| **Evidence** | Review-ready inbox drafts: Elyson and Rossetta (Nova Siri Genetics, strawberry); Pink Hudson (Planasa, raspberry); Demoiselle (Planasa, strawberry). |
| **Impact** | Variety graph lags live discovery until publication review. |
| **Workaround** | Promote through the existing human gate. Do not ground trusted entities on untrusted drafts. |
| **Recommended resolution** | Human publication review. No architecture change. |
| **Status** | active |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-TEST-001 — Morning Brief workload test hardcodes `/opt/cursor/artifacts`

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | tests |
| **Date discovered** | 2026-08-20 |
| **Evidence** | `tests/test_morning_brief.py::test_real_reading_queue_morning_workload_is_smaller_than_unresolved` writes `/opt/cursor/artifacts/morning_brief_workload.json`. Fails on Windows. Pre-existing on canonical. |
| **Impact** | Not a product bug. Windows dev machines fail this one test. |
| **Workaround** | Ignore on Windows; path exists in Cloud Agent VMs. |
| **Recommended resolution** | Configurable artifact path (`tmp_path` or env). |
| **Status** | active |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_morning_brief.py` |

---

## KNOWN LIMITATION / INTENTIONAL

| ID | Title | Why it is not debt |
|---|---|---|
| KL-001 | Human publication + atomic review gates | Trust model. AI never auto-publishes. |
| KL-002 | Signal candidate confirm ≠ trusted Signal and does not create an Assessment | Object model. Documented in `AGENTS.md`. |
| KL-003 | Story threads are organizational only | No “trust thread” action. |
| KL-004 | Landscape / Watches / Alerts / Sources / admin unmigrated | Deliberate stop gate. Landscape waits on Variety / Retail / Registry expansion. |
| KL-005 | Static GitHub Pages is a trusted snapshot | No inbox drafts, no review workbench. |
| KL-006 | Haiku enrichment is not extraction-qualified | Non-trusted publication enrichment only. |
| KL-007 | Analyst workflow state lives in gitignored `inbox/analyst_queue_state.json` | Runtime overlay; never mutates trusted `data/evidence`. |
| KL-008 | `market_ids` absent means scope undeclared, not “applies everywhere” | D-012. UI must label unscoped, not invent a berry. |
| KL-009 | ~120 reference sources have no automated discovery | Registry by design until a Source gets a `discovery` block. |

---

## RESOLVED

| ID | Title | Resolved | Notes |
|---|---|---|---|
| TD-THREAD-001 | Company-primary vs variety-primary false separation | 2026-08-20 PR #51 `807e059` | `_cross_subject_event_edge()` in `app/services/story_threads.py`. Tests in `tests/test_story_threads.py`. |
| TD-001b | Overlay Reader paid Morning Brief | 2026-08-21 prototype hardening | `/api/` paths skip nav Brief. Warm overlay ~18–20ms on the then-current runtime. |
| TD-001 | Global HTML nav rebuilt full Morning Brief presentation | 2026-08-21 decision-workflow | Function-level `mode=full` median 2772ms → `mode=nav` 2089ms. Overlay 20ms. Residual cold ranking closed as KL-011. Withdrawn draft ID: TD-UI-001 (was still Open there). |
| TD-002 | Company Bottom Line berry-scope unlabeled | 2026-08-21 decision-workflow | Classify from stored `market_ids` only; label unscoped vs berry-specific; do not hide. Authoring gap closed as TD-012. |
| TD-003 | Compact repeated kind + status marks | 2026-08-21 decision-workflow | Type stays on `.v2-card-line`. Footer marks are Direct / Watch / Pending\|Trusted / Story / Signal. |
| TD-004 | Landscape JS breadcrumb hardcoded Blueberry | 2026-08-21 decision-workflow | Reads `data-berry-label`. Landscape itself remains unmigrated (KL-004). |
| TD-011 | Reading Queue rebuilt full Morning Brief | 2026-08-21 decision-workflow | `/queues/reading` uses `mode="nav"` for its own page buckets. Nav badges no longer call Brief (KL-011). |
| TD-012 | Assessment authoring form cannot declare `market_ids` | 2026-08-21 PR #54 `b4ba0fb` | Root cause: schema already had optional `market_ids`; create form never wrote it, so new records were always unscoped. Solution: optional four-berry checkboxes on create/edit; empty omits the field (unscoped, not “all berries”); no prose inference. Timing: form GET/POST only. Tests: `tests/test_assessment_scope.py` (create one/multi/unscoped, edit round-trip, company labels stored scope). |
| KL-011 | Cold HTML nav ranked reading+pending for badges (~2.1s) | 2026-08-21 PR #54 `b4ba0fb` | Root cause: `_compute_nav_work_counts()` called `build_morning_brief(mode=nav)` on every cold HTML page. Ranked Review-now / top-priority are page concerns. Solution: cheap repository/state counts (open pending, reading_action, emerging candidate statuses, new-since-last-seen) + existing signature cache. Timing (this VM, cold cache-cleared): nav compute 2131ms → 35ms; Assessments 2144ms → 58ms; Company 2710ms → 635ms; Feed 2595ms → 519ms. Pending/Reading still pay their own page ranking (1387ms / 2307ms). Tests: `tests/test_ui_v2_shell.py` (`test_html_nav_does_not_rank_brief_for_unrelated_pages`, `test_cold_unrelated_html_nav_does_not_run_ranked_brief`). |

### TD-013 — Regulatory discovery is US-only

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection / geography |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Mainstream News + Regulatory Coverage Recall Benchmark V1 mission added 2 new `government_register_json` sources, both Federal Register (US). No EU (EUR-Lex), UK, Mexican (SENASICA/DOF), Peruvian (SENASA), Chilean (SAG), or Moroccan government source was added, despite all being named `government_regulatory`-type reference (KL-009) entries already. |
| **Impact** | A regulatory action originating outside the US (an EU MRL change, a Mexican phytosanitary rule) has zero automated discovery path even after this mission. |
| **Workaround** | None; registry-only (KL-009) for non-US regulatory sources. |
| **Recommended resolution** | Extend `government_register_json` (or a new adapter, if a target registry's API shape differs) to one non-US jurisdiction as the next regulatory-depth increment. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-014 — `news_search_rss` cannot reliably body-fetch borderline items

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection / access limitation |
| **Date discovered** | 2026-08-21 |
| **Evidence** | A Google News RSS entry's `<link>` is a `news.google.com/rss/articles/...` redirect wrapper, not the publisher's real URL. `app/services/article_acquisition.py`'s `fetch_article()` cannot extract readable content directly from that wrapper (live-verified: `"no extractable article body found at https://news.google.com/rss/articles/..."` on multiple real items). The mission's new metadata-only fallback (paired with `always_body_check`) only rescues items where Stage A already confirms relevance from title/description alone (`TIER_DIRECT`) -- a genuinely BORDERLINE `news_search_rss` item stays `retry_deferred` indefinitely, since the body it needs can never be fetched through this path. |
| **Impact** | Mainstream discovery via Google News search systematically under-recalls a "company name only, no berry word" headline -- exactly the class this mission set out to catch is the class most likely to stay unconfirmed. Measured directly: 44 of 191 processed items across this mission's 5 sources ended `article_acquisition_failed`/unconfirmed. |
| **Workaround** | None currently; relies on the item's own title/description already being Stage-A-confident. |
| **Recommended resolution** | Resolve the Google redirect to its real destination URL before calling `fetch_article()` (a plain HTTP HEAD/GET following redirects may already work where the direct-fetch of the wrapper page does not -- not verified in this mission). |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-015 — Generic-species-word ambiguity in broad topic search ("BlackBerry" phone)

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | relevance / precision |
| **Date discovered** | 2026-08-21 |
| **Evidence** | The mission's topic-scoped (not company-scoped) `source-news-search-berry-trade-remedy` real run surfaced "BlackBerry Bold 9780 now available from T-Mobile UK and Orange" (CrackBerry, a phone-industry outlet) as a passing, review-ready draft. `relevance_screen.py`'s `berry_identity` category matches the literal word "blackberry" with no brand/crop disambiguation. |
| **Impact** | Exactly one observed instance so far, in the one query design (broad topic, not company- or case-scoped) most exposed to it. |
| **Workaround** | Prefer company- or case-scoped `news_search_rss` queries over broad topic queries where possible. |
| **Recommended resolution** | A cheap, targeted regression test (`tests/test_relevance_screen.py`: a BlackBerry-phone headline should screen irrelevant) plus, if it recurs, an explicit negative-context check for "BlackBerry" capitalized as a single word (the phone brand) vs. "blackberry"/"blackberries" as the crop. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | None yet -- a good, cheap addition. |

### TD-016 — Company-name `news_search_rss` query can be dominated by stale historical results

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / discovery-query tuning |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `source-news-search-costa-group`'s real first run returned mostly 2016-2024 articles rather than 2026 news, even though real 2026 Costa Group/BluGenix coverage already exists in trusted Evidence (`ev-producereport-blugenix-2026`). Google News's relevance ranking for a bare company-name query does not reliably surface the newest items first. |
| **Impact** | A newly-registered company-name source may need query tuning (or simply patience/paging) to be useful without a human manually working through 40-100 historical results. |
| **Workaround** | Process a source's full staged item set, not just the first page, before judging it unproductive. |
| **Recommended resolution** | Investigate Google News RSS's recency/sort query parameters for a `news_search_rss` query. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-017 — Metadata-only paywall-fallback drafts have no `relevance_tier`

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | The normal `process_discovered_article()` path writes `draft["relevance_tier"]` ("direct"/"adjacent") after real body acquisition + enrichment; the mission's new metadata-only access-limitation fallback (`app/services/article_refresh.py`) returns via `orchestrator.process()` directly and never reaches that code. All 75 real drafts created by this mission's 5 new sources show `relevance_tier: null`. |
| **Impact** | Cosmetic/ranking only -- the live Morning Brief's "direct outranks adjacent" ordering can't distinguish these drafts from each other by tier. Trust/correctness is unaffected (Stage A already confirmed relevance before the fallback fires). |
| **Workaround** | None needed; low severity. |
| **Recommended resolution** | Write `winning_tier` onto the draft file in the fallback branch, mirroring the 2-line pattern the normal path already uses. |
| **Status** | active |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-THREAD-003 — Story Thread has no multi-month regulatory-case grouping

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | story threads |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `_strong_event_edge()` / `_cross_subject_event_edge()` (TD-THREAD-001, resolved PR #51) both gate on a 7-day date-proximity window, correctly designed for "same real-world moment, multiple outlets." A regulatory proceeding's own sequential documents (institution -> initiation -> determination -> extension) legitimately span months. Reproduced directly: the 5 real Mexico-strawberry-antidumping documents this mission discovered (spanning 2026-01-06 to 2026-08-06, all sharing `primary_subject: geography-mexico` and `berry-strawberry`) form 5 separate single-member "threads" under `group_story_threads()`, not one developing story. Full reproduction: `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md` Section 6. |
| **Impact** | A tracked regulatory/trade case cannot be presented as one organizational developing story with the current mechanism, even once all its documents are individually discovered and correctly tagged. |
| **Compounding risk** | Grows with every future regulatory/trade case this platform tracks -- each will individually fragment the same way. |
| **Workaround** | None; each document stands alone in the live UI. |
| **Recommended resolution** | A docket/case-number-keyed thread identity, distinct from date-proximity event matching (Federal Register's own metadata already carries the case number, e.g. A-201-869 / 731-TA-1770) -- its own scoped design/mission, not attempted here to avoid a rushed widening of the existing date window that could reintroduce false merges. |
| **Status** | active |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | None yet -- the finding was produced by an ad hoc reproduction script, not a committed test. |

Do not dump older Phase 2B attachment/UoW fixes here; they are already shipped.
