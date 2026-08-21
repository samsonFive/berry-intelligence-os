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
| **Evidence** | `relationship-predicates.json` declares 16 predicates; `schemas/relationship.schema.json` enum accepted 10 (now 11). Raspberry V1 could not use `administers_license_for` and fell back to `licenses`. **Variety Intelligence Backbone V1 mission (2026-08-21) closed one of the six**: `markets` was added to the schema enum after finding a real, already-live, explicitly-disclaimed substitution (`rel-berryworld-sells-eureka.json`'s own `notes`: *"Substituted predicate: 'sells' stands in for 'markets', which the schema does not provide"*) -- that record was corrected to the real predicate, and two new real `markets` relationships were added (`rel-driscolls-markets-zara`, `rel-driscolls-markets-victoria`). The remaining five (`exhibits_claimed_trait`, `protects`, `offers`, `administers_license_for`, `subsidiary_of`) are still declared-only/unenforced -- none had a real, live substitution case found this mission, so none were added speculatively (same discipline: schema changes only follow demonstrated need). |
| **Impact** | 5 of 6 documented extensions remain unusable at validation time. |
| **Workaround** | Use one of the enforced 11 predicates. |
| **Recommended resolution** | Add the remaining 5 only if/when a real relationship needs one and has to substitute, mirroring exactly how `markets` was resolved this mission -- do not add speculatively. |
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
| **Evidence** | Raspberry patent drafts “ABB 135”/“ABB 136” assigned to Allberry B.V., not Advanced Berry Breeding B.V. Shared ABB naming + inventor Niels Arts is circumstantial only. Left unlinked. **Further real corroboration found by the Variety Intelligence Backbone V1 mission (2026-08-21)**: CPVO's public register independently shows real raspberry varieties Shani, Rafiki, and Sarafina (all already tracked as Advanced Berry Breeding varieties) registered with applicant "Allberry B.V.", not "Advanced Berry Breeding B.V." -- the same identity question, now with 3 more real data points, still not resolved to a confirmed link (see `docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md` Part 5/13). |
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

### TD-018 — Trait-evidence linkage is a JSON convention, not schema-enforced

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / domain model |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `attributes.traits[]` entries on a Variety carry per-claim `evidence_ids`, but `entity.schema.json`'s `attributes` field is untyped -- a trait claim with an empty or missing `evidence_ids` would still pass schema validation. No `exhibits_claimed_trait` Variety->Trait relationship exists in live data (declared, `live_count: 0`). |
| **Impact** | Nothing currently exploits this gap (every real trait entry sampled does carry evidence), but the platform has no structural guarantee against a future unevidenced trait claim. |
| **Workaround** | Manual review discipline; `app/services/berries/variety.py`'s `variety_trait_profile()` already surfaces `provenance` so a reviewer can judge claim strength. |
| **Recommended resolution** | A lint/validation script checking `attributes.traits[].evidence_ids` is non-empty on every live Variety record; do not add `exhibits_claimed_trait` as a real relationship type until a real case needs Variety->Trait to be a first-class queryable edge rather than an embedded array entry. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-019 — CPVO public register `species`/`specieId` query params do not filter server-side

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / registry integration |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live-tested against `online.plantvarieties.eu/api/publicSearch/v3/publicSearch`: `?specieId=FRA01` and `?species=FRA01` both return the same unfiltered default result set as no species filter at all. Only `denomination`(`+denominationSearchType`) and `breedersReference` were confirmed to actually filter. `app/services/cpvo_registry.py` works around this by client-side filtering every result's `speciesName` against `CPVO_SPECIES_TO_BERRY` after the fact. |
| **Impact** | None currently (client-side filtering is correct and tested), but it means CPVO cannot be queried "give me everything in Fragaria x ananassa" directly -- only by denomination/breeder-reference, which is why this integration is query-per-known-variety-name rather than a browsable crawl. |
| **Workaround** | Client-side species filtering (already implemented). |
| **Recommended resolution** | Re-test if CPVO's API changes; the UI's own species dropdown may use a different, undiscovered parameter name this mission's live testing did not find. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_cpvo_registry.py::test_berry_id_for_species_maps_real_cpvo_species_strings` covers the workaround, not the upstream limitation itself. |

### TD-020 — No confirmed stable per-record CPVO permalink

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / provenance |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `normalize_cpvo_register_row()` sets `source_url` to the equivalent search query URL (`https://online.plantvarieties.eu/publicSearch?denomination=X&denominationSearchType=equals`), not a per-record deep link -- no stable permalink pattern was confirmed working during this mission's live testing. |
| **Impact** | A reviewer clicking the source_url gets a fresh search for the same denomination, not necessarily the exact single record, if a denomination has multiple real filings (see the real "Cargo"/"Blue Ribbon" two-filings-per-denomination case, `docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md` Part 13). |
| **Workaround** | The draft's `cpvo_filing` object carries the real `application_number`/`grant_number`/`exam_office_name`, sufficient for a human to disambiguate manually. |
| **Recommended resolution** | Investigate whether CPVO's SPA supports an `?applicationNumber=X`-style deep link (not attempted this mission -- time-bounded). |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none |

### TD-021 — Open Food Facts search endpoint instability

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / UK retail research |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Both `world.openfoodfacts.org/api/v2/search` and the legacy `/cgi/search.pl` endpoint returned HTTP 503 consistently throughout this mission's research window; the individual-product endpoint (`/api/v2/product/{barcode}.json`) worked reliably throughout. |
| **Impact** | The UK retail observation pilot (`docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md` Part 9) had to source real product barcodes via targeted web search rather than a direct category/country search query -- more manual, harder to fully automate. |
| **Workaround** | Web-search-then-individual-fetch, as done this mission. |
| **Recommended resolution** | Re-test the search endpoint before building any recurring/automated UK observation collector; if still unstable, consider a maintained curated barcode list instead of live search. |
| **Status** | monitoring |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none (external service issue, not this project's code) |

### TD-022 — UK retail variety-name exposure is genuinely rare

| Field | Value |
|---|---|
| **Severity** | Low (structural, not a bug) |
| **Area** | data availability |
| **Date discovered** | 2026-08-21 |
| **Evidence** | 16 of 18 real UK observations gathered this mission correctly recorded `variety_entity_id: null` -- the retailer listing genuinely did not name a cultivar. Only premium/named lines (Driscoll's Zara, Driscoll's Victoria) exposed a real variety name. |
| **Impact** | Future UK-observation volume will structurally skew toward "brand/origin known, variety unknown" rather than fully variety-identified competitive intelligence, unless a wider set of premium/named product lines is specifically targeted. |
| **Workaround** | None needed -- `commercial_observation.variety_entity_id: null` is an explicitly supported, expected state, not an error. |
| **Recommended resolution** | If UK retail observation continues, prioritize premium/branded lines (Driscoll's, other named-variety marketers) over generic own-label for variety-identification yield. |
| **Status** | accepted (real market characteristic, not something to "fix") |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none |

### TD-023 — Registry-matched varieties and observed varieties are currently disjoint

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data coverage |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `varieties_with_ip_activity_and_commercial_observation()` (`app/services/variety_footprint.py`), run against the real dataset, returns an empty list -- the 28 CPVO-matched varieties and the 2 variety-identified UK observations (Zara, Victoria) do not currently overlap. |
| **Impact** | The mission's Section 11 "which varieties have both IP activity and commercial observations" query works correctly but has nothing real to show yet -- an honest current-state gap, not a broken query (`docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md` Part 11/16 report this directly rather than omitting the null result). |
| **Workaround** | None needed; the query is correct and will surface real overlap as soon as either data source grows to include a shared variety. |
| **Recommended resolution** | A future mission expanding either registry coverage or retail-observation breadth should re-run this query and expect (eventually) a real non-empty result. |
| **Status** | accepted |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_variety_footprint.py::test_ip_and_commercial_overlap_requires_both_sides` (fixture-based positive case; the real-data empty result is reported in the mission doc, not asserted in a test, since it is expected to change). |

### TD-ENT-004 — Breeding-program entity and its parent company show identical variety lists

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | entity resolution / presentation |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `competing_varieties_in_berry_market(berry_id="berry-blueberry")`'s real output lists "Fall Creek Blueberry Breeding Program" and "Fall Creek Farm & Nursery, Inc." as two separate rows with identical variety lists -- both entities carry real, independent `develops` relationships to the same varieties. |
| **Impact** | Correct data modeling (a breeding program and its parent company are legitimately distinct real entities), but could read as a duplicate/redundant pair in a future UI without explanatory context. |
| **Workaround** | None needed at the data layer; a future UI should decide whether to visually group a breeding program with its parent company. |
| **Recommended resolution** | Cursor's UI-layer decision, not a backend fix -- flagged here so it is not rediscovered as a "bug" later. |
| **Status** | accepted |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none |

---

## KNOWN LIMITATION / INTENTIONAL

| ID | Title | Why it is not debt |
|---|---|---|
| KL-001 | Human publication + atomic review gates | Trust model. AI never auto-publishes. |
| KL-002 | Signal candidate confirm ≠ trusted Signal and does not create an Assessment | Object model. Documented in `AGENTS.md`. |
| KL-003 | Story threads are organizational only | No “trust thread” action. |
| KL-004 | Landscape / Sources inventory-config admin / admin unmigrated | Deliberate stop gate. Monitor migrated 2026-08-21. Variety Intelligence UI migrated 2026-08-21 (`/entities/variety`). Landscape waits on Trade / Retail / Registry expansion. |
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

### TD-024 — HS codes cannot separate raspberry/blackberry, or blueberry/cranberry

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data quality / trade intelligence |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live-verified against UN Comtrade's H6 (HS 2022) classification: HS 081020/081120 (fresh/frozen) combine raspberries, blackberries, mulberries, and loganberries into one code; HS 081040 (fresh blueberry) combines blueberries with cranberries and other *Vaccinium* species; HS 081190 (frozen blueberry) is a generic "other fruit, frozen" basket, not blueberry-specific at all at 6 digits. Only the US's own 10-digit HTS extension (0811.90.20) isolates frozen blueberries, and this mission's adapter (UN Comtrade) reports at 6 digits. Full detail: `docs/v2/TRADE-INTELLIGENCE-V1.md` Part 2, `data/configuration/trade_hs_taxonomy.json`. |
| **Impact** | Any raspberry- or blackberry-specific quantity/value claim from this pilot's `081020`/`081120` lane is not defensible without independent corroboration; frozen blueberry figures from `081190` are directional at best. Every affected draft's `trade_observation.berry_code_purity` is set to `multi_berry_combined` and `does_not_prove` states the limitation directly, so this is surfaced on every record, not just in this register. |
| **Workaround** | Use fresh strawberry (081010) and frozen strawberry (081110) with full confidence; treat every other code's figures as directional/combined. |
| **Recommended resolution** | A national 10-digit source (US HTS via Census, once TD-025's key gap is resolved) would separate frozen blueberry; no researched source separates raspberry from blackberry at any digit depth found this mission -- may be a genuine, permanent limit of official HS-based trade statistics for these two crops specifically. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_trade_intelligence.py::test_build_review_draft_never_auto_trusts_and_flags_combined_hs_code` |

### TD-025 — US Census International Trade API requires a key this session could not self-provision

| Field | Value |
|---|---|
| **Severity** | Low (real, but a credential-provisioning gap, not a research gap) |
| **Area** | collection / access |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live-tested `api.census.gov/data/timeseries/intltrade/imports/hs`: returns an HTML "Missing Key" page without a registered API key. Census keys are free, self-service, email-registration-based -- but registering one requires a human with an email inbox, which this mission's agent session does not have. |
| **Impact** | This mission used UN Comtrade instead (Part 1/4 of `docs/v2/TRADE-INTELLIGENCE-V1.md`), which is real and sufficient for the pilot's own required test cases, but Census would provide 10-digit HTS granularity (resolving part of TD-024's frozen-blueberry problem) that Comtrade's 6-digit H6 classification cannot. |
| **Workaround** | UN Comtrade for 6-digit-level analysis (current state). |
| **Recommended resolution** | A human operator registers a free Census API key (https://api.census.gov/data/key_signup.html) and provisions it as an environment variable; a Census adapter mirroring `trade_intelligence.py`'s shape would then be a small addition, not a redesign. |
| **Status** | active |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-026 — UN Comtrade preview endpoint has an undocumented rate limit

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / reliability |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Real, live-observed HTTP 429 responses during both this mission's manual research testing and the real pilot run (4 of 72 period-requests failed with 429 on the first run; 4 more on a deliberate second idempotency-proof run). No published rate-limit number was found for the keyless preview endpoint. A 1-second delay was added between period requests within one lane (`COMTRADE_REQUEST_DELAY_SECONDS`), but **no delay exists between the last request of one lane and the first request of the next lane** -- a real, un-fixed gap in the current implementation, not yet closed. |
| **Impact** | A handful of periods per pilot run are genuinely missing (not wrong, just absent) -- 3 of 6 lanes in the real pilot have fewer than 12 of their 12 requested periods purely due to this. |
| **Workaround** | Re-run the monitor; already-captured periods are correctly skipped as duplicates (idempotent), so a re-run only needs to backfill genuine gaps. |
| **Recommended resolution** | Apply the same inter-request delay between lanes, not only within a lane; consider exponential backoff on a 429 specifically rather than treating it identically to any other request failure. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-027 — No revision/resubmission handling for "final" trade periods

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | A reporting country can revise an already-published month's trade figures after the fact (a real, well-known characteristic of official trade statistics generally). `trade_intelligence.py`'s dedup state is keyed on `(lane_id, sorted periods present)` -- once a period is captured and marked `release_status: "final"`, a later re-run will never re-fetch or diff it against a possible revision, even if the source's own figure changed. |
| **Impact** | A trusted-eventually trade observation could silently go stale relative to the source's own later-revised number. Not observed this mission (no real revision was caught in the act), but a real, structural gap. |
| **Workaround** | None; a human reviewer would need to manually re-query a specific period if a revision is suspected. |
| **Recommended resolution** | Periodically re-fetch the most recent 2-3 already-captured periods (revisions are typically issued soon after initial release) and diff against the stored figure, flagging (not silently overwriting) a detected change. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-028 — Trade geography lookup covers only 7 countries

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data coverage |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `COMTRADE_COUNTRY_CODES` in `app/services/trade_intelligence.py` hard-codes 7 UN M49/Comtrade reporter codes (US, Mexico, Peru, Chile, UK, Morocco, South Africa) -- exactly this mission's own required pilot geographies, not a general lookup. A lane request for any other country silently fails with "unknown geography" rather than resolving. |
| **Impact** | Expected and scoped -- this mission was explicitly bounded, not a general customs warehouse. A future mission adding a new country pair needs to extend this dict first. |
| **Workaround** | Add the real UN M49 code for a new geography before building a new lane. |
| **Recommended resolution** | If trade-source breadth becomes the next mission (not this mission's own recommendation -- see `docs/v2/TRADE-INTELLIGENCE-V1.md` Part 15), expand this table alongside it. |
| **Status** | accepted (deliberately scoped, not a bug) |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-029 — CIF/FOB value basis is carried but not yet surfaced in any derived metric

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `normalize_series_row()` correctly tags each period `value_basis: "CIF"` (imports) or `"FOB"` (exports) -- real, live-confirmed UN Comtrade convention (import value includes cost/insurance/freight, export value does not). `year_over_year_change()`/`partner_flow_changes()` compare quantity and value within the SAME lane (always the same flow direction, so always the same basis) -- safe today -- but neither function checks or asserts this, so a future caller comparing an import lane's value against an export lane's value for "the same" flow would silently mix bases without any guard rejecting it. |
| **Impact** | None observed this mission (no real caller does this yet). A real latent correctness risk for a future derived-metric extension. |
| **Workaround** | Manual reviewer discipline; the `value_basis` field is present on every series entry for exactly this reason. |
| **Recommended resolution** | Add an explicit assertion/guard in any future derived-metric function that compares `trade_value` across two records, requiring matching `value_basis`. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-030 — Weather observation spatial resolution is a single ~50km grid point, not the full named production region

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | NASA POWER's own documented native grid is ~0.5 degrees (~50km). Every production region in `data/configuration/weather_production_regions.json` is queried at one representative centroid, but real named regions (e.g. "Maule Region, Chile") span a much larger area than one grid cell. This is carried on every draft as `spatial_resolution_note`/`coverage_caveat`, not hidden, but is not otherwise mitigated. |
| **Impact** | A real, local weather event (e.g. a frost pocket in one valley) can be entirely missed or diluted by a single coarse point; conversely a point-level anomaly may not reflect the whole region's real production footprint. |
| **Workaround** | `does_not_prove` and `spatial_resolution_note` make this explicit on every record; a human reviewer is expected to treat this as coarse context, not field-level ground truth. |
| **Recommended resolution** | If a future mission needs finer resolution, NASA POWER's `regional` (not `point`) endpoint returns a bounding-box grid rather than one centroid -- a real, not-yet-explored option -- or a higher-resolution reanalysis product (ERA5, credential-gated, see TD-036). |
| **Status** | accepted (deliberately scoped for this pilot) |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-031 — Production-region centroids are a pragmatic mapping choice, not independently verified against grower footprint data

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Each entry in `weather_production_regions.json` cites a real, publicly-known agricultural region (e.g. Maule for Chilean blueberries, La Libertad for Peruvian blueberries) with a `source` note, but the exact centroid coordinate was chosen by this mission's own judgment, not sourced from a grower-density map, USDA FAS GAIN report coordinate, or satellite land-cover product. |
| **Impact** | Two reasonable analysts could pick different representative points for the same named region, producing different anomaly readings for the identical real event. |
| **Workaround** | `source`/`coverage_caveat` fields on every region entry make the basis for the choice auditable and correctable. |
| **Recommended resolution** | If a future mission needs stronger grounding, cross-reference centroids against a real production-density dataset (e.g. USDA FAS GAIN report maps, or a satellite-derived land-cover product -- see the Global Trade / Customs mission's own Workstream G.4 satellite note) rather than analyst judgment alone. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-032 — Baseline period (2015-2024) is a pilot choice, not a peer-reviewed climate normal

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `weather_pilot_regions.json` uses a fixed 2015-01-01..2024-12-31 (10-year) window as every region's climatological baseline. The World Meteorological Organization's own standard climate normal is a 30-year window; this pilot's shorter window was chosen for a bounded, fast real pilot, not for climatological rigor. |
| **Impact** | Anomaly magnitudes (e.g. "+7.18C above baseline") are somewhat sensitive to which 10-year window is chosen; a different baseline window could shift the computed deviation, though not the underlying raw readings. |
| **Workaround** | `baseline_period` is recorded explicitly on every draft, so the choice is auditable, not hidden. |
| **Recommended resolution** | If anomaly precision becomes load-bearing for a future mission, extend the baseline query to a full 30-year (1994-2023 or similar) window -- a single extra NASA POWER request per region, cheap to do. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-033 — NASA POWER's upstream model (MERRA2 vs GEOSIT) is recorded per-query, not verified per-day, and can change on reprocessing

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live-confirmed 2026-08-21: a query for very recent dates (within ~3 weeks of "today") returns `sources: ["GEOSIT", "POWER"]` (a near-real-time product); the same date range queried again once older reports `sources: ["MERRA2", "POWER"]` (NASA's own final reanalysis) -- i.e. NASA reprocesses recent days from GEOSIT into MERRA2 over time. This mission's `source_model` field is set once per HTTP response (the query-level `sources` list), not independently verified per calendar day, so a query spanning the reprocessing boundary reports one model for the whole range even if some of those days have already been revised. |
| **Impact** | A day's exact reading can change slightly between an early (GEOSIT) pull and a later (MERRA2) pull of the same date -- a real, live-observed revision risk, structurally similar to Trade Intelligence V1's TD-027 (no revision/resubmission handling), not yet mitigated here either. |
| **Workaround** | `source_model` is carried on every series entry so the provenance is at least visible, not silently assumed constant. |
| **Recommended resolution** | If revision-sensitivity becomes load-bearing, re-query and diff already-drafted recent-window dates on a delay (e.g. 30+ days later) the same way a future trade-revision fix (TD-027) would. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-034 — Near-real-time NASA POWER data has a ~2-3 day release latency with no automatic backfill

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live-confirmed 2026-08-21: a query for the most recent ~3 calendar days returned NASA POWER's own documented fill value (-999.0) for those dates, correctly recorded as `is_provisional: true` with the metric set to `null`, never as a real zero. |
| **Impact** | A weather observation drafted near "today" will always have a small provisional tail; nothing currently re-runs the acquisition once those specific dates are released to backfill them onto the existing draft. |
| **Workaround** | The idempotency signature is keyed on the requested comparison-range window, not on individual dates, so a plain re-run does not create a duplicate draft -- but it also does not update the existing one with the now-available days. |
| **Recommended resolution** | A future recurring-collection integration (mirroring the existing patent/CPVO/trade monitor cadence) would re-fetch and merge newly-released provisional dates into the existing draft rather than leaving them permanently null. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_weather_intelligence.py::test_data_not_yet_released_is_not_treated_as_a_failure` |

### TD-035 — `unusual_temperature_window()`'s bidirectional consecutive-run check has low real-world specificity at default thresholds

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data quality / interpretation risk |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Real, live-computed finding: at the function's own default thresholds (3.0C deviation, 3+ consecutive days, either direction), `unusual_temperature_window()` returned `flagged: true` for all 7 of this mission's real trade-anomaly test windows -- including Peru's two real growth cases (BM-M-style +10.3%/+33.1% YoY) and the Mexico strawberry control case that already has a clean regulatory explanation. A run can average a small deviation (e.g. 0.66C) while still satisfying the per-day absolute-value threshold, because the function allows sign to flip within one run. |
| **Impact** | If used uncritically, this specific function would make nearly every real window look "weather-explained," undermining the mission's own explicit instruction not to inflate correlation into causation. This mission's own completion report does not feature `unusual_temperature_window` flags as meaningful evidence for exactly this reason -- `extreme_heat_event` (same-direction runs only) and `precipitation_deficit`/`precipitation_excess` proved far more discriminating (flagged in only 3 of 7 real cases, correctly absent for the Mexico control). |
| **Workaround** | Treat `unusual_temperature_window` as a broad screening signal only, never as standalone corroboration; prefer the unidirectional/magnitude-specific functions for anything proposed as an `evidence_links` entry. |
| **Recommended resolution** | Require same-sign deviation across the whole run (like `extreme_heat_event` already does) before calling `unusual_temperature_window` "flagged," or raise its default threshold/consecutive-day requirement based on a real false-positive-rate study across more historical windows. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_weather_intelligence.py::test_unusual_temperature_window_is_bidirectional` |

### TD-036 — NOAA Climate Data Online and ERA5/Copernicus CDS both require a self-registered API key this session could not provision

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data access / ops |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live web research (not assumed): NOAA CDO requires an email-registered token (5 req/sec, 10,000 req/day limit once issued); ERA5/Copernicus CDS requires a free account plus a personal access token stored in `~/.cdsapirc`. Both are real, credential-gated barriers this mission's agent session could not self-provision, the same pattern as Trade Intelligence V1's TD-025 (US Census). |
| **Impact** | US-specific higher-resolution NOAA station data and ERA5's finer reanalysis grid remain unavailable; NASA POWER's coarser ~50km grid is the only weather source this mission could integrate. |
| **Workaround** | None needed for this pilot's real test cases -- NASA POWER answered all of them. |
| **Recommended resolution** | A real, low-effort follow-up for whoever holds operator credentials: register a NOAA CDO token and/or a CDS account, then add either as a second, higher-resolution regional adapter alongside NASA POWER (not a replacement). |
| **Status** | active |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-037 — Weather production-region mapping is config-only, not a first-class sub-national Geography entity

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data model |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `data/configuration/weather_production_regions.json` associates a production region with a country-level Geography entity id (`geography_id`), but the region itself ("Maule Region, Chile") has no corresponding Entity record -- it exists only as config, the same pattern already used for `trade_hs_taxonomy.json`. This mission deliberately did not create new Geography entities or touch Landscape/Variety UI, per its own explicit scope. |
| **Impact** | A future UI surface wanting to browse/filter by sub-national production region (rather than country) would need real entity-model work this mission did not do. |
| **Workaround** | The config file is the single source of truth for the region->geography mapping; any future consumer can read it directly. |
| **Recommended resolution** | If a future mission needs sub-national geography as a first-class, queryable entity (not just weather-specific config), design it as a generic Geography sub-type, not a weather-specific one -- likely a Landscape/UI-adjacent decision, out of scope for a backend-only pilot. |
| **Status** | accepted (deliberately scoped, not a bug) |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

Do not dump older Phase 2B attachment/UoW fixes here; they are already shipped.
