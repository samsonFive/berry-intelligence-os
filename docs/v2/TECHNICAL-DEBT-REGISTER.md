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

## Collection Runtime + Data Integrity V1 production proof (2026-08-22)

IDs TD-038 through TD-046 are owned by the qualitative-coverage and Global
Search missions. The runtime items therefore
use the next unclaimed IDs; the duplicate draft IDs are not aliases. IDs
TD-055 through TD-057 in this summary table are Production Collection
Operations V1's own (fixed-window scheduling, analyst throughput,
acquisition reliability) -- distinct from the full-entry TD-058 through
TD-061 below, which are Relevance Screen Boundary V1's (2026-08-23),
renumbered up from an initial draft TD-055/056/057/058 after a real,
confirmed collision with these same table rows. Claim Testing V2 originally
drafted TD-055 as well; that ID is reserved for Production Collection
Operations. Claim Testing debt is TD-062 (no first-class Claim object) and
TD-063 (queue warm latency). Review Capacity + Collection Backpressure V1
added TD-064 (no append-only review decision ledger). Unknown-Event
Discovery + Query Coverage V3 (2026-08-23) originally drafted TD-062
through TD-065, then TD-064 through TD-067 after the first real collision
(Claim Testing V2's own TD-062/TD-063 full entries), then renumbered a
second time to TD-065 through TD-068 after discovering Review Capacity +
Collection Backpressure V1 had concurrently landed its own TD-064.

| ID | Area | Finding / resolution | Severity | Status | Regression test |
|---|---|---|---|---|---|
| TD-047 | runtime backup | Deterministic checksummed `data/` + `inbox/` backup/restore is live-proven. Production proof found the first secret-name filter also dropped a legitimate Evidence filename containing the word `secret`; matching is now limited to exact secret-like path components/stems and the real-style filename is a regression case. | High | resolved | `tests/test_runtime_backup.py` |
| TD-048 | idempotency | Patent/CPVO/trade/weather seen state did not account for acquisition/configuration changes. Versioned configuration signatures now invalidate only derived seen indexes. | High | resolved | `tests/test_acquisition_state.py` plus monitor tests |
| TD-049 | runtime logs | Host cron logs defaulted to a worktree-local inbox rather than the deployed runtime bind mount. Default moved under `demo-runtime/inbox/operations`. | Medium | resolved | script inspection; VPS path proof |
| TD-050 | orchestration | One registry-driven dispatcher now gives article/news, spoken media, patent, CPVO, and backup independent cadences and persists `SUCCESS`/`PARTIAL`/`FAILED` outcomes. Useful partial Source runs no longer make systemd wholly red. Trade/weather remain evidence-based manual pilots. | Medium | resolved | `tests/test_pipeline_scheduler.py`; `tests/test_pipeline_health.py`; VPS systemd proof |
| TD-051 | retention | Daily on-host backup rotation now creates and verifies a new archive before retaining 14 valid archives; invalid archives are preserved and retention cannot drop below two. Off-host replication remains unresolved. | Medium | active | `tests/test_runtime_backup.py`; `docs/v2/PRODUCTION-COLLECTION-OPERATIONS-V1.md` |
| TD-052 | locking | Manual non-media monitors did not share the recurring runner lock. Every mutable collector CLI now uses one runtime lease; the deployed UID 1000 app user can write the persistent lock directory. | High | resolved | `tests/test_pipeline_lock.py`; VPS write probe |
| TD-053 | tests | Host-specific `/opt/cursor/artifacts` paths and fixed wall-clock assertions failed on Windows/constrained hosts. Performance artifacts now use `tmp_path`; direct call-path instrumentation guards forbidden expensive work. | Low | resolved | `tests/test_morning_brief.py`; `tests/test_global_search.py`; `tests/test_ui_v2_shell.py` |
| TD-054 | status diagnostics | Root cause was item-by-item orchestration with repeated broad trusted-Evidence/draft scans. Default status now reads persisted run/pipeline state and cheap current counts; the former deep audit is explicit via `--audit-items`. | Medium | resolved | `tests/test_collection_status.py`; VPS timing proof; `docs/v2/PRODUCTION-COLLECTION-OPERATIONS-V1.md` |
| TD-055 | fixed-window quantitative scheduling | Trade (72 fixed Comtrade requests) and weather (fixed historical comparison) do not yet advance a rolling release/window, so both correctly remain manual rather than repeatedly polling static history. | Medium | limitation | `data/configuration/collection_pipelines.json` |
| TD-056 | analyst throughput | Review Capacity + Collection Backpressure V1 now makes backlog growth, age, source/query load, exact duplicate pressure, and safe simulated deferral observable. Automatic throttling stays off because recorded review decisions are insufficient; capacity itself remains unresolved. | High | active (observability improved) | `scripts/review_capacity.py`; operator status review-capacity warning |
| TD-057 | acquisition reliability | Persisted failures are dominated by expected publisher/bot access and stale-or-blocked UK FSA alert URLs (403/410), plus isolated openFDA body extraction failures. Individual failures remain visible and isolated; no Source-specific content workaround was added. | Medium | monitoring | pipeline/source failure state; `docs/v2/PRODUCTION-COLLECTION-OPERATIONS-V1.md` |
| TD-076 | canonical promotion scope | Existing `sources.json` entries and non-JSON imports/reference files have no three-way baseline. Production bootstrap also surfaced 57 differing trusted records with no historical baseline; all correctly remain conflicts pending explicit reconciliation. | Medium | limitation | `tests/test_sync_trusted_data.py`; production dry-run; `docs/v2/CANONICAL-DATA-PROMOTION-RUNTIME-SYNC-V1.md` |
| TD-077 | text-article atomic locator | Atomic Evidence requires `artifact_locator.start_seconds`; no paragraph-index alternative exists for written sources. | Medium | active | `schemas/evidence.schema.json`; Atomic Evidence Gold Set V1 Section 15 |
| TD-078 | trusted transcript coverage | No real trusted spoken-word source currently persists transcript text, so real timestamp extraction cannot yet be qualified. | Medium | active | Atomic Evidence Gold Set V1 Section 10 |
| TD-079 | multilingual extraction coverage | No non-English trusted Evidence text exists from which to build a genuine multilingual qualification case. | Low | active | Atomic Evidence Gold Set V1 Section 2 |
| TD-080 | trusted structured registry coverage | No trusted Evidence record carries the structured `patent_filing` or `cpvo_filing` object. | Low | active | Atomic Evidence Gold Set V1 Section 9 |
| TD-081 | trusted publication dropped `article` | Publish now preserves `article` / `relevance_tier` / `does_not_prove` so Atomic extraction can receive paragraph text, not only the summary. | High | resolved | `tests/test_publication_review_source_fidelity.py` |
| TD-082 | no qualified article Atomic extractor | Web-article trait proposals still wait on a qualified extractor consuming `article.paragraphs`. Review shows a deterministic untrusted preview only. | High | limitation | `app/services/source_body.py::atomic_extraction_source_text` |
| TD-083 | Pending Review full-pool card/thread work | Private restart-safe metadata projection, compact exact classification, indexed Story Thread candidates, and post-slice card hydration keep conservative 1,500-record cold/warm renders at 3.436s/1.839s; 5,000 measured 1.476s/1.248s before host I/O contention. | Medium | resolved | `tests/test_pending_review_query.py`; `docs/v2/PENDING-REVIEW-QUERY-PERFORMANCE-V2.md` |
| TD-084 | qualification cost telemetry | Qualification records provider token telemetry and a nullable cost field, but adapters do not receive provider-authoritative billed cost and the repository has no versioned model-price table. Quality thresholds remain independent of cost. | Low | limitation | `tests/test_model_qualification.py`; `docs/v2/ATOMIC-EXTRACTION-QUALIFICATION-HARNESS-V2.md` |
| TD-091 | local vs production draft inbox | Local acquisition inboxes are not production review. Missing production drafts are delivered with operator-triggered `scripts/deliver_drafts.py`, not by scp of one JSON or by replacing `demo-runtime/inbox`. | High | resolved | `tests/test_draft_delivery.py`; `docs/v2/ACQUISITION-PRODUCTION-DRAFT-DELIVERY-V1.md` |
| TD-093 | trusted extraction source fidelity | PILOT-10 human review affirmed 7/8 staged artifacts and raised readiness 36 -> 43. Fresh PILOT-25 measured 15/25 identity-supported rich plus 6 ambiguous rich artifacts; 21 new private decisions are pending. Blackberry remains zero-ready and the historical corpus remains predominantly thin. | High | active (selective path proven; bulk repair not justified) | `scripts/reacquire_sources.py`; `docs/v2/SOURCE-FIDELITY-OUTCOME-AUDIT-AND-REACQUISITION-PILOT-25-V1.md` |
| TD-098 | production static leak diagnostic | A live-runtime static build stops when a private inbox draft ID/title collides with an already-published trusted page, even when no private Source Fidelity artifact appears in generated output. Canonical CI is green; production proof must distinguish true private-byte leakage from title/ID collision. | Medium | active | production build proof; pilot artifact-ID/hash scan |

ID aliases from the expansion-guide session's withdrawn draft (do not reopen
these as Open UI-lane items):

| Withdrawn ID | This register |
|---|---|
| TD-UI-001 | TD-001 **resolved** (cold ranking closed as KL-011) |
| TD-UI-002 | TD-002 **resolved** (authoring gap closed as TD-012) |
| TD-UI-003 | TD-003 **resolved** |
| TD-UI-004 | TD-004 **resolved** |
| TD-ACQ-001 | TD-006 **resolved** |
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

### TD-006 — Cross-pipeline article dedup gap (resolved)

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection / data |
| **Date discovered** | 2026-08-18 (still current) |
| **Evidence** | Same as withdrawn TD-ACQ-001. `PROJECT-STATUS.md` / `app/services/article_dedup.py`: same story under Google-News redirect vs publisher RSS is different URL + `source_id` (recurring draft `ev-media-cec61845f15d790fd055`). Deterministic URL/title+source+date matching cannot merge them without fuzzy title matching (explicitly refused). **More precise root cause found by the Mainstream News + Regulatory Coverage Recall Benchmark V1 mission (2026-08-21):** `MediaOrchestrationService._cross_pipeline_duplicates()` (`app/services/media_orchestration.py:637-666`) filters its dedup candidate pool to `evidence_role == "publication_artifact"` before calling `find_duplicate_article()` -- a trusted record captured by the older `app/main.py` keyword/RSS auto-capture loop (pre-`evidence_role`, `submitted_by: "source-monitor:..."`) has `evidence_role: None` and is silently excluded from the candidate pool, so even an *exact canonical-URL match* against it is never checked. Reproduced directly: `source-news-search-driscolls`'s real run created a duplicate of the already-trusted `ev-20260806173540-993a-driscoll-s-filed-appeal-in-strawberry-pa.json` (`evidence_role: None`, `submitted_by: "source-monitor:Strawberry cultivar patent"`) via the identical `news.google.com` redirect URL. 9 such duplicates were produced by this mission's 3 new sources alone and removed as untracked-inbox cleanup. |
| **Impact** | Duplicate trusted or pending rows. Operators dismiss by hand. |
| **Workaround** | Inbox cleanup of known duplicates. |
| **Recommended resolution** | Resolved in Collection Runtime + Data Integrity V1: legacy source-document-shaped trusted Evidence is included; exact origin publisher + title + date closes the observed Google News/publisher RSS case without fuzzy matching. |
| **Status** | resolved |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_article_dedup.py`; `tests/test_media_orchestration.py::test_cross_pipeline_dedup_includes_legacy_trusted_publication_without_role` |

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

### TD-008 — VPS collection timer installed but unattended runs are not healthy (resolved)

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | ops |
| **Date discovered** | 2026-08-16 (still current) |
| **Evidence** | Production Collection Operations V1 installs one 15-minute registry dispatcher with independent due times. Article/news, spoken, patent, CPVO, and backup are unattended. Useful runs with isolated Source failures persist `PARTIAL` and leave individual failures visible without making systemd report a total failure. |
| **Impact** | Resolved. Genuine zero-useful-work failures still fail the unit; degraded useful work remains observable. |
| **Workaround** | None. Use the fast `collection_status.py` operator view. |
| **Recommended resolution** | Completed in Production Collection Operations V1. |
| **Status** | resolved |
| **Owner lane** | ops |
| **PR/SHA when resolved** | PR #76 / `9b57f10`; see `docs/v2/PRODUCTION-COLLECTION-OPERATIONS-V1.md` |
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
| **Evidence** | Source Reliability Remediation V1 audited all 26 retained attempts (2026-08-19 through 2026-08-24): every direct berry-feed request returned HTTP 403 with no redirect or parse, while robots permits the path, the publication/archive still exists, and the broad publisher RSS returns 200. Classified `ROBOTS_OR_ACCESS_BLOCKED`. |
| **Impact** | The direct berry Source remains a real coverage gap in production; broad all-produce RSS is not a scope-safe substitute. |
| **Workaround** | Explicit `OPERATOR_ACTION_REQUIRED` lifecycle pauses collection while keeping the Source blocked in the freshness denominator. No scraper, access bypass, Google News fallback, or replacement was introduced. |
| **Recommended resolution** | Re-check only when the publisher or production egress changes; return to `ACTIVE` only with a supported berry-scoped mechanism and genuine successful probe. Retire explicitly if the publication/feed becomes permanently unavailable. |
| **Status** | mitigated / operator action required |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `app/services/source_lifecycle.py`; `tests/test_source_lifecycle.py`; `data/configuration/sources.json` |

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

### TD-TEST-001 — Performance tests depend on one host's paths and speed (resolved)

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | tests |
| **Date discovered** | 2026-08-20 |
| **Evidence** | `tests/test_morning_brief.py::test_real_reading_queue_morning_workload_is_smaller_than_unresolved` and the concurrently landed Global Search timing test wrote under `/opt/cursor/artifacts`. Both fail on Windows. The Search test also used a fixed 250ms assertion that failed on a constrained host despite direct instrumentation proving the forbidden expensive paths were not called. |
| **Impact** | Not a product bug. Windows dev machines fail this one test. |
| **Workaround** | Ignore on Windows; path exists in Cloud Agent VMs. |
| **Recommended resolution** | Resolved with pytest `tmp_path`. Search keeps reporting representative timings and validates the timing payload; direct call-path instrumentation, rather than machine wall time, guards the expensive-query regression. |
| **Status** | resolved |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_morning_brief.py`; `tests/test_global_search.py` |

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
| KL-004 | Landscape / Sources inventory-config admin / admin unmigrated | Deliberate stop gate. Monitor migrated 2026-08-21. Variety Intelligence UI migrated 2026-08-21 (`/entities/variety`). Global Intelligence Search migrated 2026-08-22 (`/search`, `#v2SearchOffcanvas`). Landscape waits on Trade / Retail / Registry expansion. |
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

### TD-038 — Cross-pipeline dedup collapsed distinct records sharing a path but differing only by query string (found and fixed)

| Field | Value |
|---|---|
| **Severity** | High (real, would have silenced almost all FDA recall coverage) |
| **Area** | data quality / bug |
| **Date discovered** | 2026-08-21 |
| **Evidence** | `article_dedup.normalize_canonical_url()` unconditionally stripped the query string from every URL. Every openFDA recall this project acquires shares the identical path (`api.fda.gov/food/enforcement.json`) and differs only by its `?search=recall_number:...` query string, so every distinct real FDA recall collapsed onto whichever one was processed first -- live-reproduced: processing a real E. coli O145:H28 blueberry recall and a real Listeria blueberry recall (two different, real, distinct events) both resolved to the SAME existing draft id instead of creating their own, silently discarding the second. |
| **Impact** | Without the fix, this mission's food-safety coverage mechanism (Section 4) would have captured only the first-processed FDA recall ever, no matter how many real distinct recalls exist -- a load-bearing failure for exactly the acceptance case this mission required. |
| **Workaround (fix applied)** | `normalize_canonical_url()` now preserves the query string (still ignores scheme/www/trailing-slash/fragment) -- strictly more conservative (fewer false-positive duplicate collapses), and no existing test asserted the old stripping behavior. See `tests/test_article_dedup.py::test_normalize_canonical_url_keeps_distinct_query_strings_distinct`. |
| **Recommended resolution** | Done -- fixed in place this mission, not duplicated as a workaround. |
| **Status** | fixed |
| **Owner lane** | data |
| **PR/SHA when resolved** | this mission's PR |
| **Regression-test reference** | `tests/test_article_dedup.py::test_normalize_canonical_url_keeps_distinct_query_strings_distinct`, `tests/test_fda_recall_adapter.py::test_normalize_fda_recall_entry_two_distinct_records_get_distinct_identity` |

### TD-039 — Google News RSS search results are not fully deterministic request-to-request

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data access / ops |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live-observed twice this mission: (1) the exact same UK-retailer query URL returned a real, populated result set on one request and a real, valid-but-empty (0 items) response minutes later on an identical repeat request; (2) NuBerry Farms' real investment story (BM-C-08) appeared in an ad hoc manual verification query but did not appear in this mission's actual persisted discovery run of the same query text. Not a bug in this project's own code -- a real characteristic of Google News' own backend result-set variability. |
| **Impact** | A single discovery run against a news_search_rss source is not guaranteed to surface every real, currently-indexed matching article; a recurring/repeated run (not yet scheduled -- TD-008) would very likely catch items missed on any one pass. |
| **Workaround** | None available client-side; simplifying overly complex boolean/quoted queries (this mission's own real fix for the UK-retailer source) reduced but did not eliminate the variability. |
| **Recommended resolution** | No project-side fix possible. Recurring collection (TD-008, owned outside this mission's scope) would naturally mitigate this by re-polling the same query over time. |
| **Status** | active (external, not fixable in this codebase) |
| **Owner lane** | ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-040 — Relevance screening rejects metadata-thin press-release-style items even when discovery succeeds

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | discovery / relevance-screen boundary |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Two real, confirmed cases this mission: 'UNIFRUTTI GROUP ACQUIRES BOMAREA AND AVOAMERICA PERU...' (PR Newswire, BM-C-04) and 'Mexican Workers Advance Trafficking Suit Against Michigan Farm' (Bloomberg Law News, BM-R-10) were both real, generically DISCOVERED (present in `inbox/discovered_media/`) but screened `skip` before any body fetch was attempted -- neither the title nor Google News' own (identical, shallow) description field contains a berry species word, even though the underlying real story is berry-relevant (Bomarea/AvoAmerica are real Peru blueberry companies; the Michigan farm is a real blueberry operation). |
| **Impact** | Discovery reaching an event is necessary but not sufficient for real end-to-end recall -- an unknown number of additional real events in this mission's ~823 still-unprocessed discovered items likely share this same pattern. |
| **Workaround** | Resolved for the direct case, partial for the general one -- see below. |
| **Recommended resolution** | Done, partially: Relevance Screen Boundary V1 (2026-08-23) added query-provenance corroboration (`app/services/relevance_screen.py::_query_corroboration_hit`) -- a Stage A zero-signal title that also names a registered Geography/Company entity plus a corporate-action verb is kept open for Stage B instead of confidently rejected; when the article body is genuinely unverifiable (see TD-059) this now creates an explicitly-labeled `TIER_UNCERTAIN` untrusted draft for human review rather than silently dropping the item. Real, direct proof: BM-C-04 (this debt's own cited Unifrutti/AvoAmerica case) is now `CAPTURED (draft, uncertain)`. The general case remains open (TD-058): a bare press release naming no registered entity is still confidently rejected. |
| **Status** | partially resolved |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | Relevance Screen Boundary V1 (2026-08-23), branch `feature/relevance-screen-boundary-v1` |
| **Regression-test reference** | `tests/test_relevance_screen.py` (query-corroboration cases), `tests/test_article_refresh.py` (TIER_UNCERTAIN fallback cases) |

### TD-041 — CFIA (Canada) recall data audited but not integrated

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data access |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Live-tested: `healthycanadians.gc.ca/recall-alert-rappel-avis/api/recent/food` is a real, keyless, working JSON endpoint, but only returns a fixed recent-window list (no working keyword/product search endpoint was found within this mission's bounded research time -- a `/api/search/food` guess returned an empty 200). BM-R-09 (Whole Foods organic frozen blackberries recalled, CFIA) remains uncaptured as a direct result. **Re-tested live, Unknown-Event Discovery + Query Coverage V3 (2026-08-23)**: the same "recent" endpoint now returns entries with `date_published: 1635465600` (2021-10-29) as its most recent items -- either stale/cached test data or a genuinely broken "recent" feed, not real current recalls. This is a *worse* finding than the original audit: even the fallback recent-window mechanism cannot be trusted for a "recent" claim, not just "no search capability." |
| **Impact** | Canadian food-safety recalls remain a real, undemonstrated gap; US recalls (openFDA) are covered. Integrating the recent-window endpoint as-is would create untrustworthy "recent" drafts dated years stale. |
| **Workaround** | None -- audited, not implemented, per the mission's own "high-value public sources only if accessible" instruction. Deliberately not integrated this round either, given the stale-data finding. |
| **Recommended resolution** | A future mission could investigate CFIA's real search capability further (its web UI clearly supports search; the underlying API for that UI was not found this mission) and separately re-verify whether the recent-window endpoint's staleness is transient (a bad response at time of testing) or structural before ever using it as a data source. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-042 — Query-generation stays one bounded Source per query, not a dynamic runtime layer

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | architecture (deliberate scope boundary) |
| **Date discovered** | 2026-08-21 |
| **Evidence** | The mission's own Section 8 explicitly asked whether `news_search_rss` should evolve into "a controlled query-generation layer" across companies/berries/geographies/risk-concepts. This mission deliberately chose NOT to build a dynamic runtime query generator -- doing so would be a real collector-infrastructure change (new cadence/dedup/health semantics for synthesized queries), squarely inside "Do NOT refactor collector infrastructure unless Codex identifies a shared blocker." Instead, 14 new bounded, individually-reviewable Source entries were added using the existing per-source mechanism, chosen via reusable query PATTERNS (geography+berry, risk-concept, retailer-class) rather than one Source per benchmark URL. |
| **Impact** | Extending coverage to a new geography/company/concept still requires adding a new Source entry by hand (a few minutes of real work), not an automatic runtime expansion. |
| **Workaround** | The pattern is well-documented and quick to repeat (see this mission's own 14 additions as a template). |
| **Recommended resolution** | If a genuine need for dynamic query generation emerges, design it jointly with Codex as a shared collector-infrastructure change, with the bounded-queries/dedup/cadence/source-health/query-provenance guardrails the mission brief itself specified. |
| **Status** | accepted (deliberate architectural decision, not a bug) |
| **Owner lane** | data / collection (joint) |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-043 — Global Search Story Threads are cheap pending clusters, not the full thread engine

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | product / search |
| **Date discovered** | 2026-08-22 |
| **Evidence** | `app/services/global_search.py` indexes Story Threads only as exact canonical-URL or exact normalized-title clusters of pending drafts. It deliberately does not call `group_story_threads()` on the published feed (TD-THREAD-002 / Morning Brief cost). Cloud runtimes with empty `inbox/` therefore show no Story Thread group. |
| **Impact** | Searching a company/variety will still reach Company Profile, Variety, Intelligence, and Signals. Developing-story cards appear in Search only when live pending drafts share URL/title. |
| **Workaround** | Open `/threads/{id}` from Feed / Brief when a thread already exists. |
| **Recommended resolution** | If Search must list trusted-only threads, persist a cheap thread index at review time rather than regrouping the corpus on each query. Do not add embeddings to close this. |
| **Status** | limitation |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_global_search.py` |

### TD-044 — Global Search index is process-local signature cache

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | platform / search |
| **Date discovered** | 2026-08-22 |
| **Evidence** | `_SEARCH_DOC_CACHE` in `app/main.py` rebuilds from folder signatures inside one process. Multiple uvicorn workers each hold their own index. Same-size same-mtime rewrites remain the known `load_json_files` blind spot. |
| **Impact** | A publish in worker A is visible to worker B on the next request because signatures are recomputed; cold rebuild cost is paid per worker. |
| **Workaround** | Single-process demo/VPS is fine. |
| **Recommended resolution** | Phase 3 Postgres search (existing `SearchQueryService` comment). Not this mission. |
| **Status** | limitation |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_global_search.py` |

### TD-045 — TD-040's relevance-screen boundary is partially, not reliably, mitigated by alternate-article coverage

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | discovery / relevance-screen boundary |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Global Qualitative Coverage Expansion V2 real-tested TD-040's own two cases directly: BM-R-10 (Bloomberg Law Michigan trafficking case) resolved this mission -- a *different* real article about the identical event (MLive's "Lawsuit accusing West Michigan blueberry farm of trafficking workers ends in settlement", which contains the word "blueberry" in its own title) was independently discovered by the same generic query and correctly passed relevance screening. BM-C-04 (Unifrutti/AvoAmerica Peru) did **not** resolve the same way: a real, better-titled alternate article exists ("Unifrutti buys two Peruvian suppliers to boost blueberry and avocado supply", Fruitnet, live-confirmed by hand) but this mission's generic Peru-investment queries do not reliably surface it -- it only appeared when searching for "Unifrutti" by name, which this mission deliberately does not register as a permanent Source per its own no-headline-hardcoding instruction. |
| **Impact** | TD-040's boundary is real but its actual impact varies per event, not uniform -- some events have a "rescuing" alternate article a generic query can find; others do not. This is not predictable in advance. |
| **Workaround** | Resolved for BM-C-04 specifically, by a different mechanism than the one this entry describes. |
| **Recommended resolution** | Done, via a different route than alternate-article coverage: Relevance Screen Boundary V1 (2026-08-23) resolved this entry's own still-open BM-C-04 case through query-provenance corroboration (TD-040), not through finding a better alternate article -- the original PR Newswire item itself now reaches an untrusted `TIER_UNCERTAIN` draft. The alternate-article-coverage mechanism this entry describes remains real and still unreliable on its own terms (unchanged), but is no longer the only path to resolving a TD-040 case. |
| **Status** | resolved (BM-C-04's own case; alternate-article coverage itself remains unreliable as a general mechanism, unchanged) |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | Relevance Screen Boundary V1 (2026-08-23), branch `feature/relevance-screen-boundary-v1` |
| **Regression-test reference** | `tests/test_relevance_screen.py::test_real_unifrutti_headline_is_kept_open_by_geography_plus_action_verb` |

### TD-046 — Cross-pipeline duplicate rate grows with repeated backlog re-processing at scale (mitigated concurrently by Codex)

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / dedup |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Global Qualitative Coverage Expansion V1 found 16 real cross-pipeline duplicates (drafts sharing an exact title with an already-trusted record, discovered under a different Source registration) out of ~180 processed items (~9%). Processing a much larger batch this mission (~600+ items, including most of Round 1's remaining backlog) found 57 such duplicates before the exact same fix landed -- confirming the absolute count grows with processing volume, not just a one-off Round 1 anomaly. **Resolved concurrently, independently, by Codex's Collection Runtime + Data Integrity V1 mission** (merged as this repo's PR #70, `cd107b9`, landing mid-way through this mission): `article_dedup.find_duplicate_article()` gained a new `_publisher_identity()` check (exact title + date + explicit origin publisher name/host) that catches precisely the Google-News-redirect-vs-publisher-RSS case this debt describes, without fuzzy title matching. This mission's own 57-item cleanup was performed by hand before Codex's fix was visible on canonical; a re-run of this mission's same batch against the now-current canonical would very likely require less manual cleanup, though this was not re-verified end-to-end given the mission's own scope boundary (do not duplicate or re-litigate Codex's work). |
| **Impact** | Manual duplicate cleanup was real, necessary work for this mission's own real batches; going forward, new batches should see a materially lower duplicate rate. |
| **Workaround** | Not needed going forward for the specific case Codex's fix covers; the general practice of spot-checking a sample after any large batch remains good discipline regardless. |
| **Recommended resolution** | Already done by Codex -- this entry is retained for institutional memory (why 57 duplicates were manually removed in this mission's own real run) rather than as an open action item. |
| **Status** | resolved (by Codex, concurrently, PR #70) |
| **Owner lane** | collection/runtime (Codex) |
| **PR/SHA when resolved** | `cd107b9` (Codex, concurrent) |
| **Regression-test reference** | `tests/test_article_dedup.py` (Codex's own additions) |

### TD-058 — Query-provenance corroboration only rescues a metadata-thin item that also names a registered entity

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | discovery / relevance-screen boundary |
| **Date discovered** | 2026-08-23 |
| **Evidence** | `_query_corroboration_hit()` (`app/services/relevance_screen.py`) requires a registered Geography or Company entity name plus a corporate-action verb in the title. A genuinely bare press-release title with zero recognizable entity name (e.g. a brand-new, not-yet-tracked company, or a place this platform has no Geography entity for) still hits Stage A's plain `score == 0` -> CONFIDENT-irrelevant exit, unchanged. Real measurement against the current `inbox/discovered_media/` backlog: of 309 zero-signal items from `news_search_rss` sources, only 16 (~5%) carried a registered-entity + action-verb corroboration; the rest remain confidently rejected exactly as before this mission. |
| **Impact** | This mission's fix closes the demonstrated case (BM-C-04) and generalizes to any similarly-shaped event, but does not claim to solve metadata-thin discovery in general -- a real, bounded improvement, not the full boundary. |
| **Workaround** | Adding a new company/geography to the entity graph (already required for any real competitive-intelligence use of that entity) automatically widens corroboration coverage for future items naming it -- no code change needed per new entity. |
| **Recommended resolution** | If this remains a real, recurring gap after operator observation, consider widening the action-verb vocabulary (`_CORPORATE_ACTION_RE`) cautiously, one real false-negative case at a time -- never broaden it speculatively, per this project's own no-headline-hardcoding discipline. |
| **Status** | active (accepted boundary, not a bug) |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_relevance_screen.py::test_action_verb_alone_without_geography_or_company_does_not_corroborate` |

### TD-059 — Google News RSS redirect URLs are not resolvable to a real article body without an undocumented decode step

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | discovery / article acquisition |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Live-tested against the real BM-C-04 canonical_url: `httpx.get(..., follow_redirects=True)` returns HTTP 200 with a ~580KB Google News single-page-application shell (real, server-rendered), but the actual target article URL is resolved only by client-side JavaScript -- no server-rendered link, embedded JSON payload, or `data-*` attribute carrying the real target URL was found in the response body. `article_acquisition.fetch_article()` correctly raises `empty_body` (trafilatura finds no extractable content). Measured: **100% of 309** real zero-signal `news_search_rss` items in the current backlog have a `news.google.com/rss/articles/...` canonical_url; Stage B body verification is therefore structurally unavailable for essentially this entire source class, not just an occasional failure. |
| **Impact** | Query-provenance corroboration's `TIER_UNCERTAIN` fallback (TD-040) is the only mitigation available for this source class -- items lacking a corroboration hit remain unresolved, not because Stage B rejected them, but because Stage B can never run. Real body-content verification (the strongest, most trustworthy signal) is available only for non-Google-News sources (Federal Register, openFDA, UK FSA, direct publisher `article_rss` feeds). |
| **Workaround** | None implemented. Community libraries exist that decode Google's redirect payload via an additional request to an undocumented internal Google endpoint -- deliberately not integrated: undocumented, has already changed encoding once (community tooling had to adapt), and sits uncomfortably against this project's own "respect access controls, never build around a wall" discipline even though it is not a paywall in the traditional sense. |
| **Recommended resolution** | If this becomes a priority, the safer fix is source-level: prefer direct publisher RSS/JSON feeds over Google News search queries wherever a given publisher (AgriMaroc, Fruitnet, FreshPlaza, etc.) already has one, rather than attempting to resolve Google's redirect. Not evaluated this mission -- would be a new source-configuration change, out of this mission's own "no broad source expansion" stop instruction. |
| **Status** | active |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_article_refresh.py::test_query_corroborated_zero_signal_item_becomes_uncertain_draft_when_body_unverifiable` |

### TD-060 — French blackberry species identity ("mûre"/"mûres") remains unrecognized

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | discovery / relevance-screen boundary / non-English |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Relevance Screen Boundary V1 added French "myrtille(s)"/"fraise(s)"/"framboise(s)" (blueberry/strawberry/raspberry) to `berry_identity`, unlocking 42 of 50 real items from `source-news-search-morocco-berry-fr`. French "mûre"/"mûres" (blackberry) was deliberately excluded -- it is also the ordinary French adjective for "ripe" ("une fraise mûre" = a ripe strawberry), an even higher false-positive collision risk than the already-excluded Italian "more", since it is itself common agricultural vocabulary rather than an unrelated common word. |
| **Impact** | French-language blackberry-specific discovery stays a real, undemonstrated gap -- symmetric with the platform's existing general blackberry-depth thinness (this project's own repeatedly-documented "blackberry stays shallow" finding). |
| **Workaround** | None -- the risk of a broad false-positive (matching ordinary ripeness language in any French agriculture article) was judged worse than the gap itself, per this module's own established precedent for Italian "more". |
| **Recommended resolution** | If real French blackberry discovery becomes a priority, a disambiguating pattern (e.g. requiring "mûre"/"mûres" directly adjacent to a fruit-noun rather than a bare adjective match) could be attempted and tested against a real corpus before adding -- not attempted this mission, since no real French blackberry false-negative was observed in this mission's own bounded testing to justify the added complexity. |
| **Status** | active (deliberate exclusion, not an oversight) |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_relevance_screen.py::test_french_mure_deliberately_excluded_stays_generic` |

### TD-061 — Two independently-evolved relevance-screening mechanisms coexist

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | architecture |
| **Date discovered** | 2026-08-23 |
| **Evidence** | `app/services/relevance_screen.py` (two-stage, berry-identity-gated, versioned "relevance-screen-v3", body-aware) and `app/services/relevance_screening.py` (`screen_discovered_item`, single-stage, score-threshold, metadata-only, no body-fetch capability at all) are two real, separately-built modules. Before this mission, `scripts/process_discovered_media.py` and `scripts/run_recent_batch.py` -- the actual documented, real-world operator workflow (`AGENTS.md`'s own "Operating path") -- exclusively used the older `relevance_screening.py` module for `web_article` items; the newer, more carefully anti-false-positive-engineered `relevance_screen.py` module was reachable only via `scripts/run_collection.py` (Codex's recurring pipeline) and `scripts/ingest_articles.py` (a little-used standalone CLI). This mission wired `web_article` items in both real-workflow scripts onto `relevance_screen.py` instead; `relevance_screening.py` remains in use for spoken-media (podcast/video) items in both scripts, where transcript acquisition already serves the "real body" role Stage B plays for articles. |
| **Impact** | Before this fix, every real `web_article` draft created via the documented operator workflow across this project's entire multi-mission history had zero body-verification and used the cruder, substring-matching, no-word-boundary scorer -- a real, previously-undocumented architectural gap now closed for the article path specifically. |
| **Workaround** | Not needed going forward for `web_article` items. `relevance_screening.py` remains appropriate for spoken media (no comparable "cheap metadata vs. real body" split exists there; the transcript itself is the eventual real content). |
| **Recommended resolution** | No further action recommended -- the split is now principled (article vs. spoken-media) rather than accidental (older vs. newer module reachable by different scripts for the same media type). Full consolidation into one module was judged out of this mission's own "do not rewrite runtime orchestration" boundary and not needed now that both paths are used for the media type they suit. |
| **Status** | monitoring |
| **Owner lane** | platform |
| **PR/SHA when resolved** | Relevance Screen Boundary V1 (2026-08-23), branch `feature/relevance-screen-boundary-v1` |
| **Regression-test reference** | `tests/test_article_refresh.py`, `tests/test_relevance_screen.py` |

### TD-062 — Claim Testing has no first-class Claim object

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | product / claim testing |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Canonical Claim Testing is published Evidence with `priority.testing.level != none` plus `inbox/analyst_queue_state.json` dispositions (`needs_testing` / `pass` / `fail` / `defer`). There is no Claim schema, no supporting/contradicting counts unless `evidence_links` already stores `corroborates` / `contradicts`, and Pass does not publish a Fact. V2 UI surfaces that limitation instead of inventing a science product. Originally drafted as TD-055; renumbered because Production Collection Operations V1 already owns TD-055. |
| **Impact** | Analysts can adjudicate tagged source claims, but cannot record a structured evidence chain unless those links already exist on the Evidence record. |
| **Workaround** | Use stored `evidence_links` and existing Fact publication when a Fact is actually warranted. |
| **Recommended resolution** | Only if product later authorizes a first-class Claim object. Do not treat this UI migration as that authorization. |
| **Status** | limitation |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_testing_workspace.py` |

### TD-063 — Claim Testing queue warm path lists the full published Evidence corpus

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | product / performance |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Warm `GET /queues/testing` measured ~2.9s locally. The route uses `queue_items("testing")` → `published_evidence()` (one list of published JSON), then enriches only the tagged subset (~65 records) via `related_indexes`. It does not call Morning Brief, Story Threads, Global Search indexing, `variety_footprint`, or relevance screening. No quadratic per-item corpus rescan was found. |
| **Impact** | Analyst wait is noticeable but bounded to corpus size, not an orchestration replay. |
| **Workaround** | None required for landing. |
| **Recommended resolution** | If this becomes operator-painful, cache published Evidence for the request or filter testing tags without a full sort of unpublished-excluded records. Do not rewrite the testing product to get that. |
| **Status** | limitation |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_testing_workspace.py::test_testing_queue_does_not_run_forbidden_work` |

### TD-064 — Publication review lacked an append-only decision-event ledger

| Field | Value |
|---|---|
| **Severity** | High |
| **Area** | analyst operations / measurement |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Review Outcome Instrumentation V1 writes compact append-only events for publication, triage, reading, Claim Testing, Signal Candidate, Signal alert, and recommendation-proposal actions under private `inbox/review_events/`. Analytics no longer infer historical events from current state. Verified runtime backup/restore coverage is regression-tested. |
| **Impact** | New decisions and latency are measurable from deployment forward. Pre-ledger history remains unknowable; Publication Save still conflates editing with possible Keep intent, and reason categories are not available on every dismiss/defer form. |
| **Workaround** | Counts are reported immediately, but rates remain `null` until 30 applicable decisions across at least two days (and 30 per Source/query cohort). Automatic throttling remains off. |
| **Recommended resolution** | Add a distinct explicit Publication Keep control if keep-rate is required, and bounded reason categories where they improve operations. Do not backfill inferred events. |
| **Status** | substantially resolved; explicit Keep/reason taxonomy limitation remains |
| **Owner lane** | platform / analyst operations |
| **PR/SHA when resolved** | PR #86; implementation `9bdc584`; deployed merge `4bf2cfa` |
| **Regression-test reference** | `tests/test_review_events.py`, `tests/test_review_capacity.py::test_unreviewed_backlog_never_becomes_fabricated_yield`, `tests/test_review_capacity.py::test_only_real_recorded_actions_are_observed` |

### TD-065 — A real, well-matched source can sit fully configured and never be run

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection / operational |
| **Date discovered** | 2026-08-23 |
| **Evidence** | `source-20260819-international-blueberry-organization` (a real, live-verified article_rss feed) was onboarded 2026-08-19, its own `why_it_matters` text explicitly names "import-duty policy across Chile/Peru/Morocco" -- directly matching BM-T-06 ("Chile/Peru/Morocco growers respond to US import duties"). `last_checked_at` was `null`. Unknown-Event Discovery + Query Coverage V3 (2026-08-23) ran `discover_media.py` against it for the first time, four days after onboarding, and found 10 items including the exact real BM-T-06 article ("Faced with steep US import duties, growers in Chile, Peru and Morocco prepare a response," 2026-08-14), which correctly became a `direct` draft on the very first real run. |
| **Impact** | A source can be correctly researched, correctly configured, and still contribute zero real recall until something actually invokes discovery against it -- onboarding is necessary but not sufficient. An unknown number of the platform's other configured-but-`last_checked_at: null` sources may carry similar unrealized recall. |
| **Workaround** | None systemic. This mission's own real fix was simply running `discover_media.py` against the one source it happened to inspect. |
| **Recommended resolution** | A cheap, generic operator report (`scripts/collection_status.py` or a new flag) listing sources with `last_checked_at: null` alongside their age since `created_at` would surface this class of gap without a new collector/scheduling mechanism -- explicitly out of this mission's own "do not refactor collection orchestration" scope, left for Codex's review-capacity/operational-backpressure lane to consider. |
| **Status** | active |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-066 — SEC EDGAR filing documents are not extractable, so relevance rests entirely on human review

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | discovery / article acquisition |
| **Date discovered** | 2026-08-23 |
| **Evidence** | SEC filing exhibits are served as raw SGML-wrapped documents (`<DOCUMENT><TYPE>...<TEXT>`), not a normal web page shape -- live-verified `fetch_article()` returns `empty_body` for every real Mission Produce 8-K exhibit tried. `always_body_check` + the `TIER_UNCERTAIN` fallback (TD-058/059) correctly create an untrusted, explicitly-labeled draft rather than dropping the item, but Stage B can never confirm relevance for this source class -- every SEC-sourced draft stays `uncertain` until a human opens the real, working `canonical_url` by hand. This mission manually confirmed one real match (BM-C-07: the 2026-03-12 filing's own text discusses "pre-production land development and blueberry plant cultivation in Peru" as a real capital-expenditure line item) by reading the raw document directly -- the system itself cannot make this confirmation algorithmically. |
| **Impact** | Real, valuable, primary-source signal (Corporate-class investment/expansion disclosure) that structurally cannot self-verify -- entirely dependent on human review economics (TD-056) to realize its value. A one-time historical backfill created 32 `uncertain` drafts (7+ years of quarterly filings for one company); ongoing cadence (weekly) will add only ~4-6 new filings per year per tracked company. |
| **Workaround** | None for automated verification. The constructed `canonical_url` (`sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}`) is always real and directly openable by a human reviewer. |
| **Recommended resolution** | If SEC EDGAR coverage expands to more tracked companies, consider a dedicated lightweight SGML-to-text extractor scoped to this one document shape (not a general trafilatura fix) before adding more CIKs, to avoid growing the `uncertain` backlog faster than review capacity absorbs it. |
| **Status** | active |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_sec_edgar_adapter.py`; `tests/test_article_refresh.py::test_always_body_check_source_zero_signal_item_becomes_uncertain_draft_when_body_unverifiable` |

### TD-067 — A newly-onboarded live RSS feed cannot retroactively reach a historical benchmark event

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | discovery / architecture (structural limitation, not a bug) |
| **Date discovered** | 2026-08-23 |
| **Evidence** | FreshPlaza's and Fruitnet's real, live-verified RSS feeds (`source-freshplaza-global`, `source-fruitnet-produce-plus`) return only their own current, recent item window at the moment of first poll (all 69 real FreshPlaza items discovered this mission share one single publication date, 2026-08-21) -- unlike Google News search (which has real historical reach) or SEC EDGAR's full-text search (which returns years of history), a plain publisher RSS feed is not an archive. Two real, confirmed benchmark events (BM-C-09 "The Summer Berry Company begins year-round British strawberry production," BM-G-02 "Plant Sciences Genetics expands global berry breeding with new raspberry varieties") were found by hand to have Fruitnet as their real, live, working publisher URL -- but neither is reachable through the newly-onboarded Fruitnet source, since both predate this mission's first poll and Fruitnet's feed does not expose them. |
| **Impact** | Onboarding a source-first, authoritative publisher feed (per this mission's own Section 5 guidance) is real and valuable for *future* unknown-event discovery, but must not be assumed to retroactively close a historical benchmark gap merely because the publisher is now monitored. Reported honestly: BM-C-09 and BM-G-02 remain MISSED this mission despite their real source now being live-monitored. |
| **Workaround** | None generic. A one-off `news_search_rss` query could reach either specific historical article, but adding one per already-known headline is exactly the "19 headline queries" anti-pattern this mission's own Section 2 instruction rules out. |
| **Recommended resolution** | None needed -- this is the correct, honest behavior of a live feed, not a defect. Worth remembering when evaluating a future mission's own "did recall improve" claims: a live source's real contribution is measured going forward, not by re-checking old benchmark misses against it. |
| **Status** | limitation (structural, not a bug) |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-068 — Real cross-publisher syndication produces a duplicate this project's dedup discipline correctly does not collapse

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / dedup |
| **Date discovered** | 2026-08-23 |
| **Evidence** | The identical real story ("USHBC President on Mexico's role in the North American blueberry industry...", 2026-08-04) was independently, legitimately published on both Fresh Fruit Portal (`freshfruitportal.com`, an already-onboarded source) and syndicated/re-published on IBO's own site (`internationalblueberry.org`, newly onboarded this mission) -- two real, different canonical URLs, two real, different explicit publisher identities. Codex's `_publisher_identity()` dedup check (TD-046) deliberately requires matching publisher name/host and does not, and should not, collapse two genuinely different real publishers' independent (even if textually identical) coverage -- this is not the Google-News-redirect-vs-direct-feed case that check targets. |
| **Impact** | A human reviewer sees two real drafts for the same underlying event from two real sources -- correct, conservative behavior (never fuzzy-merge across different real publishers per this project's own "deterministic identity only" rule), but adds one extra item to the review queue for this specific case. |
| **Workaround** | A reviewer approves one and rejects/dismisses the other -- ordinary duplicate-coverage handling, no different from any other real multi-source story. |
| **Recommended resolution** | None -- correct behavior, not a defect. Retained here for institutional memory the next time a real IBO/Fresh-Fruit-Portal (or similar trade-press syndication relationship) collision is found, so it isn't mistaken for a new dedup bug. |
| **Status** | limitation (correct behavior, not a bug) |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-069 — Major UK (and likely global) retailers are not registered as Company entities, disabling corroboration for the entire retailer-commercial event class

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | knowledge graph / entity coverage |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Regional Coverage V4's UK Live Recall Set tested a real, current headline -- "Sainsbury's signs five-year contracts with 62 UK berry farms" -- and found Stage A scored it only 1 (generic "berry" match, BORDERLINE, no corroboration eligible). `ls data/entities/companies/ \| grep -iE "sainsbury\|tesco\|asda\|co-?op\|marks"` returns empty: **no major UK grocery retailer is a registered Company entity at all**, confirmed by reading three real existing entity files (`company-costa-group-holdings.json`, `company-african-blue.json`, `company-agrovision.json`) to verify every current entity requires real, trusted `evidence_ids`/`fact_ids` backing before it exists. |
| **Impact** | `geography_corroboration_matchers()` / `matchers_from_entities()` (built Mission 2, `app/services/relevance_screen.py`, `app/services/deterministic_tagging.py`) can only corroborate a borderline item against a *registered* entity -- an entire class of real competitive events (retailer sourcing commitments, private-label moves, retailer sustainability/local-sourcing announcements) structurally cannot benefit from corroboration no matter how well-configured the source is, because the counterparty side of the relationship was never modeled. This is not UK-specific in principle -- it is untested for Costco, Walmart, Kroger, Aldi, Carrefour, etc., and likely has the same gap. |
| **Workaround** | None systemic. A human reviewer can still manually publish a captured item once discovered; this only affects the automated corroboration path, not final human trust review. |
| **Recommended resolution** | Do **not** create entities ad hoc from a single uncorroborated headline (would violate the established evidence-grounding discipline this mission deliberately upheld). Instead, a future mission should identify major retailers with *already-existing* trusted Evidence/Fact coverage in the corpus (there may already be enough real published retailer-relationship evidence to ground 3-5 initial UK retailer entities properly) and register only those, rather than force-creating ungrounded entities to close this one Sainsbury's gap. |
| **Status** | active |
| **Owner lane** | data / entities |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-070 — `article_rss` sources do not run Stage A relevance screening at discovery time, unlike `news_search_rss`

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / operational |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Regional Coverage V4 compared `relevance_screening` presence across all currently-discovered items for the three global trade-press sources. `news_search_rss` sources (e.g. `source-news-search-chile-blueberry-es`) carry a populated `relevance_screening` block (`score`, `decision`, `likely_berry_ids`, `matched_terms`) immediately after `discover_media.py` runs, before any `process_discovered_media.py` call. `article_rss` sources do not: of FreshPlaza's 69 currently-discovered items, only the 3 already run through `process_discovered_media.py` in a prior mission carry a `relevance_screening` value; the other 66 -- untouched since discovery -- have no screening field at all. IBO shows `process` on all 10 only because all 10 happen to already be fully processed, not because discovery itself screened them. |
| **Impact** | An operator scanning `article_rss` backlog cannot cheaply see which items are berry-relevant without either reading titles by hand (as this mission did for FreshPlaza, finding 4/69 real hits) or running the full, more expensive `process_discovered_media.py` pipeline on every item. For a low-precision firehose source like FreshPlaza (94% non-berry in the current window), this makes backlog triage manual rather than queryable. |
| **Workaround** | Manual title-scan (used successfully this mission) -- cheap for a 69-item window, would not scale to a much larger `article_rss` backlog. |
| **Recommended resolution** | Extend the same cheap, deterministic Stage A screener (`deterministic-relevance-v1`) that `news_search_rss` already runs at discovery time to the `article_rss` adapter path, so every discovered item gets a `process`/`skip` triage signal immediately, independent of whether/when a human later runs the full relevance-gate pipeline on it. Scoped, mechanical change; not attempted this mission (collection-orchestration changes are out of this mission's own stated scope). |
| **Status** | active |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-071 — ~45% of trusted Evidence carries no `berry_ids`, hiding real content (including real raspberry/blackberry stories) from every berry-scoped measurement

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data quality / measurement integrity |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Blackberry/Raspberry Vertical V1 found 574 of 1,266 trusted `data/evidence/*.json` records (45.3%) carry an empty/missing `berry_ids`. Checking those 574 records' own titles/summaries for species keywords found 27 mentioning a raspberry term and 21 mentioning a blackberry term. Two concrete, named, real instances were caught directly: `ev-20260806173853-c7ff-spanish-malaika-raspberry-plantings-expa` (a real, 2-source-corroborated Onubafruit Malaika raspberry story) and `ev-20260806173544-f46d-boosting-blackberries-nc-state-s-gina-fe` (a real NC State blackberry variety release) both have `berry_ids: []` despite being unambiguously about one named species in their own titles. This 574-untagged figure itself is not new (already noted in `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`'s Geography section as "574 untagged... real trusted Evidence, real volume") but had never been registered as a Technical Debt limitation with a concrete negative consequence before. |
| **Impact** | Every `berry_ids`-filtered count on the platform -- this mission's own canonical baseline audit, Regional Live Recall Set V1's berry-distribution tally, any future Coverage Matrix per-berry row, any berry-scoped UI filter -- silently undercounts real evidence for whichever berry the untagged record actually concerns. The undercounting is proportionally similar across all four berries (blueberry-mentioning untagged records number 187, the largest absolute count), so it does not reverse the overall blueberry-dominance finding, but it means every per-berry percentage reported anywhere in the platform should be read as a floor, not an exact figure. |
| **Workaround** | None systemic. A human reviewer publishing a new item can add `berry_ids` manually; the gap is in already-published historical records. |
| **Recommended resolution** | A bounded, additive backfill pass: run the existing `deterministic_tagging.BERRY_TERMS` matcher (already used for new-draft auto-tagging) against the title/summary of the 574 untagged trusted records and propose `berry_ids` for human confirmation -- do not auto-write trusted-record changes without review, since these are already-published records, not drafts. Out of scope for this mission (a dedicated data-quality pass, not a side effect of vertical-specific discovery work). |
| **Status** | **substantially resolved** (Evidence Berry Tagging Backfill V1, 2026-08-22) — the specific 574-record legacy batch this entry documented is now 299, all correctly untagged per manual sample verification (company/category-only mentions, off-topic scraping noise, no missed vocabulary term found). Traced to a single historical bulk-seed batch (`captured_date: 2026-08-06`), confirmed **not** an ongoing pipeline leak (0 of 3 trusted records captured since are untagged). Left `active`-adjacent rather than fully `resolved`: the *general* risk this entry names (a future bulk import could reintroduce untagged trusted records) is structural and permanent, not eliminated by backfilling one historical batch. See `docs/v2/EVIDENCE-BERRY-TAGGING-BACKFILL-V1.md` for the full mission report. |
| **Owner lane** | data |
| **PR/SHA when resolved** | feature/evidence-berry-tagging-backfill-v1 |
| **Regression-test reference** | `scripts/backfill_berry_tags.py` (dry-run/apply, idempotence proven twice) |

### TD-072 — `deterministic_tagging.py`'s berry auto-tagging vocabulary has zero French terms for any berry

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | discovery / tagging vocabulary |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Blackberry/Raspberry Vertical V1's terminology audit found `app/services/relevance_screen.py`'s `berry_identity` gate correctly recognizes French `myrtille(s)`/`fraise(s)`/`framboise(s)` (added in Relevance Screen Boundary V1) for the *relevance* decision, but `app/services/deterministic_tagging.py`'s `BERRY_TERMS` (a separate code path, used for auto-tagging `berry_ids` onto publication drafts/articles via `main.py`, `draft_attribution.py`, `publication_enrichment.py`) has **no French vocabulary at all, for any of the four berries** -- confirmed via direct grep, zero matches for `framboise`, `myrtille`, or `fraise` in that file. |
| **Impact** | A real French-language article can correctly pass the relevance screen (score high enough to become a draft) and then still fail to get auto-tagged with the correct `berry_ids`, leaving it in the same untagged-and-invisible state TD-071 describes, specifically for the platform's French-language sources (`source-news-search-morocco-berry-fr` and any future French source). This is symmetric across all four berries, not caneberry-specific, but was only surfaced while auditing caneberry terminology. |
| **Workaround** | None. Manual `berry_ids` correction during human publication review remains available. |
| **Recommended resolution** | Add the same French species vocabulary already proven in `relevance_screen.py` (`myrtille(s)`, `fraise(s)`, `framboise(s)`) to `deterministic_tagging.py`'s `BERRY_TERMS`, mirroring the pattern this mission used to add `zarzamora`/`caneberry`. French `mûre`/`mûres` (blackberry) should remain excluded here too, for the same "ripe" collision reason as TD-060. Small, additive, low-risk fix -- not done this mission to keep scope to the caneberry-specific gaps this mission set out to prove. |
| **Status** | **resolved** (Evidence Berry Tagging Backfill V1, 2026-08-22) — French `myrtille(s)`/`fraise(s)`/`framboise(s)` added for blueberry/strawberry/raspberry exactly as recommended; Italian `mirtillo`/`mirtilli`, `fragola`/`fragole`, `lampone`/`lamponi` added too (found the same gap existed for Italian, not scoped to French alone, while reconciling this file against `relevance_screen.py`). Blackberry's French `mûre`/`mûres` and Italian `more` remain deliberately excluded, per this entry's own recommendation. A real, separate, previously-undocumented bug was found and fixed in the same pass: `infer_berry_ids_from_text()` used plain substring matching, not word-boundary matching, causing "mora" to false-positive inside words like "morado"/"enamorado" -- fixed with the same `_word_present()` pattern `relevance_screen.py` already used. `tests/test_deterministic_tagging.py` added (this module had zero prior direct test coverage). |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | feature/evidence-berry-tagging-backfill-v1 |
| **Regression-test reference** | `tests/test_deterministic_tagging.py` |

### TD-073 — A future draft re-tagging pass would be poisoned by AI enrichment's own negation language

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | collection / tagging vocabulary (latent, not active) |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Evidence Berry Tagging Backfill V1 found 126 of 854 `inbox/evidence/*.json` draft records (14.8%) currently untagged. Re-running `deterministic_tagging.infer_berry_ids_from_text()` against those drafts' *current* summary text found 11 that would newly match -- every one a false positive from the AI enrichment step's own negative framing, e.g. a real summary reading "This article does not appear directly relevant to competitive intelligence on core berry crops (blueberry, strawberry, raspberry, blackberry)." naively text-matches as if the article named all four species. The real production path (`app/services/publication_enrichment.py::apply_deterministic_tags`, called from `enrich_publication_draft`) is safe today only because it runs *before* `apply_ai_payload` overwrites `summary` with AI-generated text later in the same function -- not because the matcher itself understands negation. Confirmed zero contamination in the trusted corpus this mission backfilled (all pre-AI-enrichment content). |
| **Impact** | None currently -- the live pipeline's call order avoids this. The risk is purely latent: any future tool (including a hypothetical draft-side sibling of this mission's own `scripts/backfill_berry_tags.py`) that naively re-runs deterministic tagging against a draft's *current*, already-AI-enriched summary would inject false multi-berry tags on genuinely irrelevant articles. |
| **Workaround** | None needed while the current call order holds. Any future draft re-tagging tool must use the original discovered-item title/description (or `publisher_description`), never the AI-generated `summary`/`ai_enrichment.concise_summary` fields, as its matching text. |
| **Recommended resolution** | If a draft-side backfill or re-tagging pass is ever built, source its matching text from `publisher_description`/the original discovered-item fields only. No fix needed to the current, already-safe production call order. |
| **Status** | active (latent risk, not a current bug) |
| **Owner lane** | collection/runtime |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | — |

### TD-074 — Commercial Positions V2 is tagged Evidence, not a Position object store

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | product / domain model |
| **Date discovered** | 2026-08-22 |
| **Evidence** | `/queues/commercial_position` still selects published Evidence with `priority.commercial_position.level != none`. Company grouping and linked Facts/Signals/Assessments are a view. There is no first-class Position record, no competitive score, and tag priority is not truth confidence. |
| **Impact** | Analysts can scan commercial-position thinking without a durable Position identity, merge, or lifecycle. Future Landscape “who we think we are vs them” work still cannot hang off this inventory as if it were a Position schema. |
| **Workaround** | Treat the page as tagged Evidence plus Recommendation proposals. Do not infer rankings from tag priority. |
| **Recommended resolution** | A later, explicitly scoped Position-object mission. Do not add a schema in a UI-only change. |
| **Status** | limitation |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_commercial_positions.py` |

### TD-075 — Commercial Positions V2 warm route is ~2.7s / ~354 KB locally

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | product / performance |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Warm `GET /queues/commercial_position` measured **2.701s / 354051 bytes**, then **1.733s / 354051 bytes** on a later warm hit. This is a latency/payload characteristic of the tagged-evidence workspace, not a trust or correctness defect. |
| **Impact** | Analyst wait is noticeable on a full local corpus. |
| **Workaround** | None required for landing. |
| **Recommended resolution** | If this becomes operator-painful, a later performance mission. Do not rewrite this surface in the same change. |
| **Status** | limitation |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_commercial_positions.py::test_commercial_positions_does_not_run_forbidden_work` |

### TD-076 — Existing Source entries and non-JSON seed files have no three-way promotion baseline

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | platform reliability / data ownership |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Canonical Data Promotion / Runtime Sync V1 found that trusted one-record JSON stores have stable relative paths and can safely use per-record baseline hashes. `configuration/sources.json` is a shared array whose existing IDs may contain runtime operator edits, while historical imports/reference artifacts include Markdown, CSV, and Python files without a common record identity contract. The first production bootstrap additionally found 57 already-differing promotable trusted records with no historical last-promoted baseline and 18 differing non-promotable import/reference files. The deployment preserved every byte and classified rather than overwrote them. |
| **Impact** | New Source IDs and new seed files continue to deploy automatically, but a legitimate canonical change to an existing Source entry or existing non-JSON reference file is intentionally not promoted. The 57 legacy trusted-record pairs also cannot become safe-update candidates until their ancestry is reconciled; guessing a baseline would erase the distinction between canonical repair and operator change. |
| **Workaround** | Reconcile each specific item explicitly after inspecting canonical, runtime, and available backup/Git history; only then establish a baseline. Do not repurpose trusted-record promotion to force an overwrite. The pipeline registry remains separately authoritative operational configuration. |
| **Recommended resolution** | Reconcile the 57 production conflicts as a bounded, separately reviewed data-ownership task. Add a per-ID baseline only if existing Source-entry migrations become a demonstrated operational need. Define explicit ownership per non-JSON class before adding update behavior; do not generalize one-record JSON policy blindly. |
| **Status** | limitation |
| **Owner lane** | platform / ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_sync_trusted_data.py`; production dry-run at `878dd8e`; `docs/v2/CANONICAL-DATA-PROMOTION-RUNTIME-SYNC-V1.md` |

### TD-077 — No schema path for a text-article atomic Evidence locator

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data model / atomic extraction |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Atomic Evidence Gold Set V1 mission. `evidence.schema.json`'s `allOf` conditional requires `artifact_locator.start_seconds` on every `evidence_role: "atomic_evidence"` record. `article.paragraphs[].index` is already documented in the same schema file as "the article's locator, the written-text equivalent of a transcript's segment index... a future qualified extraction step cites paragraph indexes, never an invented timestamp" — but no field in `artifact_locator` accepts a paragraph index, and `start_seconds` stays required regardless. |
| **Impact** | A future text-article (web_article/company newsroom/trade press) atomic Evidence proposal cannot validate against `evidence.schema.json` without either fabricating a `start_seconds` value it does not have, or the schema being extended first. |
| **Workaround** | None; text-article atomic extraction is correctly not attempted until this is resolved. |
| **Recommended resolution** | Extend `artifact_locator` with an optional `paragraph_index` alternative to `start_seconds` (mirroring how `article.paragraphs` already anticipates this), or make `start_seconds` conditionally required only when the parent's `media_format` implies timed media. Not attempted in this mission — documenting the gap, not building the fix, per this mission's own scope. |
| **Status** | active |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `schemas/evidence.schema.json`; `docs/v2/ATOMIC-EVIDENCE-GOLD-SET-V1.md` Section 15 |

### TD-078 — Zero real trusted spoken-word source has persisted transcript text

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | collection / atomic extraction |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Atomic Evidence Gold Set V1 mission. `ev-lucentlands-scaling-blueberry-industry-2025` is the only trusted `evidence_role: "publication_artifact"` / `media_format: "podcast"` record in the corpus; its `transcript.status` is `"not_available"`. A full-corpus scan found zero trusted records with `transcript.status: "available"` and populated `transcript.text`. |
| **Impact** | The real `atomic-ci-v1` extraction/qualification pipeline (`scripts/qualify_extraction_model.py`, `docs/v2/ATOMIC-CI-EVALUATION.md`) has only ever been evaluated against the synthetic `benchmarks/atomic-ci-v1.json` fixture -- no real-transcript qualification run is currently possible against trusted data. |
| **Workaround** | Continue using the synthetic benchmark for structural/behavioral evaluation, as already documented; do not treat a synthetic-only pass as equivalent to real-transcript qualification. |
| **Recommended resolution** | A future mission specifically targeting spoken-media transcript acquisition (captions, publisher-provided transcripts, or a transcription pipeline) against a real trusted podcast/video episode. Not attempted here -- out of this mission's scope. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `docs/v2/ATOMIC-EVIDENCE-GOLD-SET-V1.md` Section 10 |

### TD-079 — Zero non-English trusted Evidence text exists

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data coverage / atomic extraction |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Atomic Evidence Gold Set V1 mission. A full-corpus scan of `data/evidence/` for Spanish/French/Italian vocabulary found only English-language articles containing Spanish/Portuguese proper nouns (e.g. "Proarándanos," "El Niño") -- no record's `summary`/`why_it_matters`/body text is itself in a non-English language, despite live French/Spanish/Italian discovery and relevance-screening vocabulary already in production (TD-072, TD-ACQ-004). |
| **Impact** | No genuine multilingual atomic-extraction test case can be built from trusted data until a non-English source is actually captured and published; a benchmark claiming Spanish/French coverage today would have to fabricate it. |
| **Workaround** | None; Atomic Evidence Gold Set V1 reports this limitation rather than fabricating a non-English case. |
| **Recommended resolution** | No action required specifically for this debt; it will close naturally once any future mission publishes a real non-English trusted record, at which point it should be added to the gold set. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `docs/v2/ATOMIC-EVIDENCE-GOLD-SET-V1.md` Section 2 |

### TD-080 — No trusted Evidence carries the structured `patent_filing`/`cpvo_filing` object

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / registry intelligence |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Atomic Evidence Gold Set V1 mission. A full-corpus grep of `data/evidence/*.json` for `"patent_filing"` and `"cpvo_filing"` returned zero matches; every record with either object populated is a pending draft in `inbox/evidence/`. The 22 trusted `patent_record` and 8 trusted `plant_breeders_rights_record` files carry the same bibliographic facts (application/grant numbers, dates, assignee, parentage) only as prose inside `summary`/`why_it_matters`. |
| **Impact** | A registry-focused extraction test against trusted data must parse prose, not a structured object; `app/services/intelligence_feed.py`'s generic `patent_filing`/`does_not_prove` rendering has never been exercised against a real trusted record. |
| **Workaround** | None needed for this mission -- Section 9 of the gold set annotates the two richest trusted registry records from their prose directly. |
| **Recommended resolution** | When any pending `patent_filing`/`cpvo_filing`-bearing draft clears human publication review, confirm the structured object survives promotion intact and update this entry. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `docs/v2/ATOMIC-EVIDENCE-GOLD-SET-V1.md` Section 9 |

### TD-081 — Trusted publish dropped article body (resolved)

| Field | Value |
|---|---|
| **Severity** | High |
| **Area** | publication review / extraction contract |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Planasa draft `ev-media-069f07925d20b2d93743` stored full trafilatura paragraphs. `review_publish.py` did not copy `article`. |
| **Impact** | Analysts saw RSS/enrichment summary; Atomic extraction would not receive variety-level sentences after trust. |
| **Workaround** | None; body was on the draft only. |
| **Recommended resolution** | Preserve `article`, `relevance_tier`, `does_not_prove` on publish. |
| **Status** | resolved |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_publication_review_source_fidelity.py` |

### TD-082 — Qualified article Atomic extractor is not built

| Field | Value |
|---|---|
| **Severity** | High |
| **Area** | extraction |
| **Date discovered** | 2026-08-22 |
| **Evidence** | Collection extraction is transcript-oriented. `atomic_extraction_source_text()` now prefers `article.paragraphs`. No qualified article extractor writes Atomic Evidence. |
| **Impact** | Trait-level proposals remain a review aid until the extractor mission lands. |
| **Workaround** | Human reads the persisted body on `/review/{id}`. |
| **Recommended resolution** | Other agents' qualified extractor must consume preserved article text, not `summary`. Complements TD-077 (locator schema). |
| **Status** | limitation |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `app/services/source_body.py` |

### TD-083 — Pending Review first screen full-pool work

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | pending review / performance |
| **Date discovered** | 2026-08-22 |
| **Evidence** | V2 profiles separated inventory, filters, trusted/watch context, compact score/bucket classification, Story Threads, hydration, actions, and Jinja. A private incremental metadata projection removes article/transcript deserialization from list requests; exact counts use compact records; indexed candidate edges replace all-pairs threads; rich hydration occurs only after the 20/bucket slice. Conservative final cold restart/warm after heavy host I/O: 3.436s/1.839s at 1,500. The 5,000-record stress run measured 1.476s/1.248s before that contention. |
| **Impact** | Resolved for the JSON runtime at current and stress volumes without changing rank or trust semantics. |
| **Workaround** | None required. Prebuild the disposable index before traffic on first deployment. |
| **Recommended resolution** | Completed. A future storage backend should implement the same `PendingDraftSnapshotProvider` seam with native indexed counts/windows. |
| **Status** | resolved |
| **Owner lane** | product |
| **PR/SHA when resolved** | Pending Review Query Performance V2 feature PR (2026-08-23) |
| **Regression-test reference** | `tests/test_pending_review_query.py`; `tests/test_story_threads.py`; `tests/test_pending_triage.py` |

### TD-084 — Extraction qualification lacks provider-authoritative cost telemetry

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | platform / model operations |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Atomic Extraction Qualification Harness V2 persists per-source wall time, proposition count, failure rate, and input/output/total tokens when an adapter reports them. Neither the OpenAI-compatible nor Perplexity extraction response currently carries a provider-authoritative billed dollar amount, and maintaining an unversioned price guess inside the scorer would make historical comparisons non-reproducible. The artifact therefore records `estimated_cost_usd: null` rather than fabricating a cost. |
| **Impact** | Candidate quality and latency can be compared immediately; exact monetary cost must be calculated externally from the provider invoice or a separately versioned price table. This does not weaken qualification because cost never offsets a quality failure. |
| **Workaround** | Use recorded token counts with the provider's price sheet applicable at run time, and retain that external calculation with the operator review notes. |
| **Recommended resolution** | Prefer provider-returned billed-cost metadata if a supported endpoint adds it. Otherwise add an explicitly dated/versioned price catalog and record its version in the immutable evaluation artifact; never silently apply current prices to historical runs. |
| **Status** | limitation |
| **Owner lane** | platform / ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_model_qualification.py`; `app/services/atomic_qualification.py` |

### TD-085 — Trait-to-group mapping for Variety Intelligence is a small closed lookup, not schema-derived

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data model / presentation |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Variety Profile Intelligence V2 mission. `data/entities/traits/*.json` (13 real trait entities) has no `category` field distinguishing "product/sensory" from "postharvest/quality" from "production/agronomic" -- `TRAIT_TO_GROUP` in `app/services/variety_workspace.py` is a small, explicit, code-level mapping over the 13 known trait ids, chosen because the mission's own instruction forbids inventing brittle NLP-based grouping when no structured tag exists. |
| **Impact** | A future 14th trait entity is not silently mis-grouped -- it falls into "Other observations" -- but it also does not automatically join Product/sensory, Postharvest/quality, or Production/agronomic until someone deliberately extends `TRAIT_TO_GROUP`. |
| **Workaround** | None needed; "Other observations" is an accepted, honest fallback per the mission's own Section 10 instruction. |
| **Recommended resolution** | If trait entities grow meaningfully past ~13-15, consider adding a real `category` field to `trait.entity_type` records (a schema/data change, not a presentation one) rather than growing the code-level lookup indefinitely. Not attempted this mission -- no demonstrated need yet. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_variety_workspace.py::test_present_variety_intelligence_groups_by_real_trait_entity` |

### TD-086 — Product/performance trusted observations are 100% blueberry today

| Field | Value |
|---|---|
| **Severity** | Low (structural, not a bug) |
| **Area** | data coverage |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Variety Profile Intelligence V2 mission. Direct corpus measurement: 25 of 41 blueberry varieties have at least one trait-tagged Fact (a Fact whose `entity_ids` include both a Variety and a `trait-*` entity); 0 of 12 raspberry, 0 of 6 strawberry, and 0 of 5 blackberry varieties do. This is the same "blueberry public pilot" research batch (`research-agent/blueberry-public-pilot-2026-08-03`) already known to dominate the trusted Fact corpus (see Atomic Evidence Gold Set V1's Section 2 finding of the same skew at the Evidence level). |
| **Impact** | The new Variety Intelligence section will correctly show the honest empty state ("No trusted variety-level product or performance observations have been captured yet.") for every non-blueberry variety today. This is expected, truthful behavior per the mission's own "sparse truthful UI > fabricated density" instruction, not a defect in this feature. |
| **Workaround** | None needed. |
| **Recommended resolution** | A future data-depth mission (not this one) extending trait-tagged Fact coverage to raspberry/strawberry/blackberry, mirroring how the blueberry public pilot was built, would close this gap. Do not force it by loosening `present_variety_intelligence()`'s real trait-co-occurrence requirement. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_variety_workspace.py::test_detail_route_shows_honest_empty_state_when_no_trait_facts` |

### TD-087 — No structured attribution-role field distinguishes retailer/marketer/company-self-report feedback

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data model / attribution |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Variety Profile Intelligence V2 mission. `Evidence.source_type` (e.g. `company_press_release`, `trade_press`, `plant_breeders_rights_record`) is the only structured field available for attribution display (`SOURCE_TYPE_LABEL` in `variety_workspace.py` humanizes it); it does not distinguish "retailer feedback relayed by the breeder" from "marketer feedback" from "the company's own claim about itself" -- exactly the distinction the Planasa "arise the interest of major European retailers" pending source (Atomic Evidence Gold Set V1 Section 1a) shows matters for correct trust interpretation. |
| **Impact** | Today's Variety intelligence cards correctly show source name and humanized source_type, but cannot yet show a finer "retailer feedback" vs. "marketer feedback" attribution tag even where a human reader could tell the difference from the article text -- because no structured field carries that distinction and this mission does not infer it from free text (would be exactly the "brittle NLP classification" the mission instructs against). |
| **Workaround** | None needed; `source_type` plus the Fact's own `statement` text (which retains natural qualifiers like "reported," "claims," "according to") is the current honest ceiling. |
| **Recommended resolution** | If a future mission finds real cases needing this distinction at scale, add a structured field (e.g. `attribution_role` on Evidence or a per-claim annotation on Fact) rather than inferring it from text. Not attempted here -- no schema change made this mission. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-088 — Signal has no populated date field on any real record

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | data quality / temporal coverage |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Source / Entity Intelligence Timeline V1 mission. `schemas/signal.schema.json` has exactly two date-shaped fields (`first_seen`, `last_updated`, both optional). Checked all 6 real files in `data/signals/`: **0 of 6** have either populated. Every real Signal today falls back to its earliest linked Evidence's `published_date` for timeline placement (or `UNDATED / DATE NOT ESTABLISHED` if that Evidence isn't itself dated), never its own genuine "when was this pattern first detected/confirmed" date. |
| **Impact** | A Signal's real detection/confirmation history is not recoverable from current data. The Intelligence Timeline (and any future consumer needing a real Signal date) can only ever show the evidence-fallback date, flagged `is_fallback_date=True`, never a true Signal-authored date. |
| **Workaround** | `entity_intelligence_timeline()` and its `_signal_row()` helper (`app/queries/timeline.py`) already fall back to the earliest linked Evidence's `published_date` and mark the row as a fallback rather than silently presenting it as a genuine Signal date. |
| **Recommended resolution** | Populate `first_seen` at the point a Signal is first proposed/confirmed in the Signal-authoring workflow, going forward. Not attempted here -- Signal authoring/review is out of this mission's scope. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_entity_intelligence_timeline.py::test_signal_uses_first_seen_then_last_updated_then_evidence_fallback` |

### TD-089 — Fact.event_date and Relationship.effective_date are populated in a minority of real records

| Field | Value |
|---|---|
| **Severity** | Low (structural, already partially known) |
| **Area** | data quality / temporal coverage |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Source / Entity Intelligence Timeline V1 mission, full-corpus measurement: `Fact.event_date` populated in 45 of 186 real Facts (~24%); `Relationship.effective_date` populated in 27 of 234 real Relationships (~11.5%). The remaining majority fall back to `created_at` (Fact) or the earliest linked Evidence's `published_date` (both types), each explicitly flagged `is_fallback_date=True` by the new timeline layer rather than presented as an unqualified real-world date. |
| **Impact** | Most Fact/Relationship rows in any chronological view are dated by when they were recorded or reported, not necessarily when the underlying development actually happened -- an honest, already-disclosed approximation, not silently wrong, but a real coverage gap worth tracking. |
| **Workaround** | None needed; the fallback + explicit flag is the correct behavior per this mission's own Section 5 instruction, not a bug to fix. |
| **Recommended resolution** | Backfilling `event_date`/`effective_date` on existing real records (where the source text actually states a real-world date) would be a bounded, valuable future data-quality mission -- not attempted here since this mission is presentation/querying only. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_entity_intelligence_timeline.py::test_fact_prefers_event_date_over_created_at_and_flags_fallback`, `::test_relationship_uses_effective_date_then_evidence_fallback` |

### TD-090 — Alias-text recall can attribute an unrelated entity's Evidence via a place-name collision

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / entity linkage |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Entity Linking Precision V1 reproduced the exact match: canonical alias `Victoria` matched `summary` text `Geelong, Victoria` in unrelated blueberry `ev-costa-ownership-2024`. The same full-corpus audit found 54 additional likely false fallback pairs across substring, ordinary-word, person-name, longer-Variety, and incidental-comparison classes. The shared matcher now requires bounded, identity-class-specific deterministic grounding and preserves explicit IDs first. Victoria's real HortWeek blackberry Evidence remains; both Costa place-name records are absent. |
| **Impact** | Resolved for the shared live Company/Variety linkage path and every consumer of that linked set. The reviewed 38-pair sample improved from 65.79% to 100% estimated precision with 100% recall retained. |
| **Workaround** | None. Do not restore raw substring occurrence as grounding. |
| **Recommended resolution** | Complete. Keep `benchmarks/entity-linking-precision-v1.json` and the canonical-only audit in CI regression coverage. |
| **Status** | resolved 2026-08-23 |
| **Owner lane** | data |
| **PR/SHA when resolved** | Entity Linking Precision V1, PR #111, implementation `b43f8f0` |
| **Regression-test reference** | `tests/test_entity_alias_recall.py`; `tests/test_entity_intelligence_timeline.py::test_victoria_profile_retains_real_blackberry_evidence_without_costa_geography_collision`; `tests/test_audit_entity_linking.py` |

### TD-091 — Conservative text fallback intentionally omits body-only and unmodeled place-name recall

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / entity linkage recall |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Entity Linking Precision V1 traced the live fallback fields to title/headline/summary/excerpt/why-it-matters; publisher article bodies are not scanned. Canonical Geography has 19 broad records and does not model every state, province, city, or market name. The conservative matcher uses those real Geography identities plus syntax, berry compatibility, and Variety context; it deliberately returns no link rather than treating an ungrounded body occurrence as identity. |
| **Impact** | A legitimate Entity mention present only in a retained publisher body, or an unusually phrased unmodeled subnational place collision, may be missed. This is bounded recall debt; it does not create false trusted links. |
| **Workaround** | Explicit reviewed `entity_ids` remain authoritative. A human can add the structured link through normal trusted-data review when the Evidence truly grounds the Entity. |
| **Recommended resolution** | Expand only with a reviewed benchmark and deterministic evidence. Do not introduce a generic body scan, gazetteer guess, or AI entity classifier merely to increase recall. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `benchmarks/entity-linking-precision-v1.json`; `scripts/audit_entity_linking.py` |

### TD-092 — Local acquisition inbox is not the production review inbox

| Field | Value |
|---|---|
| **Severity** | High |
| **Area** | collection runtime / draft delivery |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Local acquisition clone created `ev-media-c8cdb7133db1cae0bf66`; production `/review/` 404. Intended operational collection writes VPS `demo-runtime/inbox` via systemd → `collection_cron.sh` → `run_due_pipelines.py`. `scripts/deliver_drafts.py` is the explicit operator path for exceptional promotion of off-runtime drafts. |
| **Impact** | Analysts cannot review locally collected operational drafts until they exist on the production inbox. |
| **Workaround** | Operator-triggered additive delivery; never replace `demo-runtime/inbox`. |
| **Recommended resolution** | Completed. Keep production collection on the VPS as the default path. Do not auto-sync local inboxes. |
| **Status** | resolved |
| **Owner lane** | product |
| **PR/SHA when resolved** | Acquisition → Production Draft Delivery V1 |
| **Regression-test reference** | `tests/test_draft_delivery.py` |

### TD-093 — Most trusted Evidence predates retained extraction source bodies

| Field | Value |
|---|---|
| **Severity** | High |
| **Area** | data quality / extraction readiness |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Atomic Extraction Backlog Readiness V1 found 36 ready registry records and 1,227 thin descriptions. PILOT-10 produced seven identity-supported rich artifacts, one ambiguous rich artifact, and two technical failures. Human review then affirmed seven, marked SEKOYA needs-investigation, and rejected none, raising real readiness 36 -> 43. A fresh, non-overlapping PILOT-25 produced 15 identity-supported rich artifacts, six ambiguous rich artifacts, one access block, and three thin PDF paths; all 21 captures remain private/pending. Combined technical yield is 22/35 (62.9% useful) and 29/35 (82.9% raw rich). |
| **Impact** | Seven affirmed overlays add five Blueberry, one Raspberry, and one Strawberry full-article source; Blackberry remains zero-ready. PILOT-25 adds 21 human decisions but no readiness until review. The results justify selective high-priority repair, not a bulk legacy crawl, and the remaining historical corpus is still predominantly thin. |
| **Workaround** | Keep every artifact private and extraction-ineligible until explicit Source Fidelity Review. Use exact-manifest or explicit-ID bounded execution under the shared collection lock. Never substitute pending artifacts for trusted source content, overwrite conflicts, or count ambiguous bodies as useful yield. |
| **Recommended resolution** | Human-review the 21 new PILOT-25 artifacts before any further historical batch. Continue historical repair only in small explainably prioritized cohorts; keep browser automation out and preserve failure/ambiguity classifications. Put primary engineering effort into rich forward acquisition and analyst review throughput. |
| **Status** | active (selective path proven; 21 decisions pending; historical corpus remains thin) |
| **Owner lane** | data / ops |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_source_fidelity_recovery.py`; `tests/test_source_reacquisition.py`; `tests/test_rich_source_acquisition.py`; `tests/test_extraction_backlog.py`; `tests/test_publication_review_source_fidelity.py` |

### TD-094 — Landscape V2's cold-cache request is still several seconds

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | performance |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Landscape V2 mission. Uncached, `landscape_context()` measured 1.9-3.7s per single-berry request and `landscape_context_all_berries()` measured 4-9s for the cross-berry ALL view, against real production-scale data (O(companies × evidence) + O(varieties × evidence) per berry, inside `app/services/berries/landscape.py`). A folder-signature-keyed cache (`_cached_landscape_context()`/`_cached_landscape_context_all()`, `app/main.py`, mirroring the existing `_NAV_WORK_CACHE` pattern) brings *warm* requests down to ~350-650ms, meeting the mission's ≤2s target -- but the *first* request after any data change (publish, promotion, Signal/Assessment change) still pays the full uncached cost. |
| **Impact** | The very first analyst (or the manager demo) to open a given Landscape view after a data change experiences a multi-second wait; every subsequent viewer until the next data change is fast. Not a correctness issue, purely a first-hit latency issue. |
| **Workaround** | None needed for the demo -- warm the cache with one request immediately after deployment/data changes if a specific view must be fast on first real view. |
| **Recommended resolution** | If this becomes a real problem, optimize the underlying O(companies × evidence) walk in `landscape_competitive_field()`/`landscape_variety_rollup()` (e.g. precompute an evidence-by-entity index once per request instead of calling `entity_regions()` per company/variety), or move cache population to a background warm-up on data-change rather than lazily on first request. Out of this mission's scope -- the existing single-berry aggregation logic was reused, not rewritten, per its own "do not redesign" precedent. |
| **Status** | active |
| **Owner lane** | performance |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_landscape_v2.py::test_landscape_warm_request_is_fast` (asserts only the warm path; does not assert a cold-path bound) |

### TD-095 — Landscape's Variety Compare deep-link is not static-safe

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | static/public safety (cosmetic) |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Landscape V2 mission. `landscape.html` has a load-bearing, tested architectural invariant (`tests/test_synthesis_views.py::test_landscape_static_and_live_rendering_share_one_context_pipeline`) that the template must never contain the literal string `static_build`, guaranteeing live and static rendering never diverge. The new "Compare this berry's most-covered varieties" deep-link into Variety Compare V1 (which is itself deliberately live-only, not wired into `build_static.py`) therefore had to render unconditionally rather than being hidden on the static build the way every other live-only-feature link in this codebase (Company/Variety Compare entry points elsewhere, Learner Mode's Explain-this in some cases) is hidden via `{% if not static_build %}`. |
| **Impact** | On the public static GitHub Pages mirror, this one link points to a page that does not exist there (404 if clicked). No data, trust, or privacy impact -- purely a dead link on an optional convenience feature. |
| **Workaround** | None needed -- the link still works correctly on the live app, which is where analysts actually use Compare. |
| **Recommended resolution** | Either statically pre-render Variety Compare for a bounded, curated set of ids (a larger architectural change, not attempted here), or thread a non-`static_build`-named flag (e.g. reusing/adding a distinctly-named context variable) through the static build path specifically for this one link without touching the protected invariant. Out of this mission's scope. |
| **Status** | active |
| **Owner lane** | product/UI |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_landscape_v2.py::test_landscape_per_berry_template_never_diverges_static_from_live` |

### TD-096 — Executive Readout's "What changed" has no independent Fact row-kind

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | presentation / trust-class completeness |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Executive Intelligence Readout V1 mission. `what_changed()` (`app/services/executive_readout.py`) surfaces Evidence/Signal/Assessment rows dated within a 14-day window, but not Fact as its own dated row-kind. This was a deliberate choice, not an oversight: TD-088/TD-089 (this session, Timeline V1) already measured `Fact.event_date` populated in only ~24% of real records, with `created_at` the only reliable fallback -- a "recently changed" feed built on that would mostly reflect ingestion timing, not real fact-emergence timing, for the majority of Facts. Facts remain traceable through the Assessment section's `supporting_fact_count` and through their parent Evidence's own What Changed row -- never hidden, just not an independently-dated feed item. |
| **Impact** | A Fact created/discovered outside any dated Evidence or Assessment window will not appear in "What changed" even if it is itself new -- an edge case, not the common path, since most Facts are directly evidence-linked. |
| **Workaround** | None needed -- Facts stay visible via Assessments and Evidence, just not double-counted as a third feed-item kind with an unreliable date. |
| **Recommended resolution** | If Fact-level "what changed" visibility becomes a real analyst need, revisit once TD-088/TD-089's underlying `Fact.event_date` population improves, rather than building a feed row on `created_at` alone. |
| **Status** | active |
| **Owner lane** | product/UI |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_executive_readout.py::test_what_changed_preserves_distinct_kinds` (proves the three kinds that do exist stay distinct; does not assert Fact absence directly) |

### TD-097 — Manager Brief Pack V1 has no server-side persistence

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | product/UI — deliberate scope cut |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Manager Brief Pack V1 mission. The mission brief itself explicitly permitted this cut ("If persistence introduces unnecessary scope: a URL-state V1 is acceptable, but document the tradeoff"). `/brief-pack`'s entire composition state (title, context note, berry, time window, selected company/variety/signal/assessment ids, Learner concept slugs) lives in the query string only -- there is no `data/brief_packs/` or `inbox/brief_packs/` record, no id, no `created_at`/`updated_at`. A pack is still fully deep-linkable today (the URL already encodes everything and resolves live against current trusted data), but there is no named, browsable list of "packs I've made," no way to rename/update a pack in place without constructing a new URL, and a very long selection (5 companies + 5 varieties + 5 signals + 5 assessments + 5 concepts, each a real canonical id) produces a correspondingly long URL. |
| **Impact** | An operator must keep/share the URL itself to reopen a specific brief; there is no "My Brief Packs" list. Geography-based selection and a "copyable plain-text/Markdown outline" export (both mentioned as optional in the mission brief) were also deferred in this V1 for the same reason -- scope, not difficulty. |
| **Workaround** | Bookmark or share the URL directly; it is already the complete, reproducible pack state. |
| **Recommended resolution** | If saved/named packs become a real analyst need, add a small `data/brief_packs/*.json` (or `inbox/`, if kept private/operator-scoped) record storing exactly the same fields already in the query string today (never full source bodies -- referenced ids only, resolved live) plus `id`/`created_at`/`updated_at`, and a `/brief-pack/{id}` route that loads those ids into the same existing `compose_brief_pack()` pipeline. The composition logic itself would not need to change. |
| **Status** | active |
| **Owner lane** | product/UI |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_brief_pack.py::test_brief_pack_deep_link_reload_stable` (proves the URL-state model works; does not test persistence, since none exists) |

### TD-098 — Production static leak check conflates published collisions with private leakage

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | static-public safety / production diagnostics |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Bounded Historical Reacquisition Pilot V1 production proof. Canonical Static Public Safety passed. A separate build inside the live container, intentionally pointed at the mounted production runtime, stopped because `generated/` contained trusted published IDs/titles that also exist among 1,556 retained inbox Evidence files. The checker reports any such lexical overlap as an unpublished-draft leak without first asking whether the generated row came from the published repository. The build exited nonzero and deployed nothing. A targeted scan of the same generated tree found zero matches for all eight private Source Fidelity artifact IDs, a private body hash, or any Source Fidelity runtime path. |
| **Impact** | Operators cannot use the current all-inbox title/ID scan as a decisive production-runtime leak proof when retained draft/history files overlap trusted published records. It fails safe, so there is no public exposure, but the diagnostic mixes true leakage with cross-pipeline duplicate/history collisions and prevents an otherwise useful live-runtime static verification. |
| **Workaround** | Keep canonical CI Static Public Safety mandatory. For production proofs, allow the build to fail closed, deploy nothing, and separately scan generated output for private artifact IDs/hashes/paths. Never dismiss a match without resolving it to the generated page's trusted record identity. |
| **Recommended resolution** | Make the checker identity-aware: exclude an inbox item from the forbidden set only when the same canonical Evidence ID is already published with an identity/hash contract proving the generated page is the trusted record. Keep different-ID exact-title collisions visible as warnings or failures until their lineage is resolved. Add a fixture for same-ID published history versus a genuinely unpublished body. |
| **Status** | active |
| **Owner lane** | platform |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | production build proof in `docs/v2/BOUNDED-HISTORICAL-REACQUISITION-PILOT-V1.md`; regression not yet implemented |

### TD-099 — Company profile's own "Varieties / genetics" section only shows the breeder (`develops`) role

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | presentation / relationship-role completeness |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Company Compare V1 mission, found while auditing existing Company infrastructure before building `app/services/company_workspace.py`. `company_profile_context()` in `app/main.py` filters `grouped_relationships` to `predicate == "develops"` only when building its `company_varieties` key, and `_company_profile.html`'s "Varieties / genetics" section hardcodes the word "develops" in its row copy (`<strong>{{ entity.name }}</strong> develops <a>...`). A company that is only a licensee, marketer, owner/rights-holder, grower, or distributor of a variety -- never its breeder -- shows no rows in this section on its own single Company profile page, even though the relationship is real and trusted. Company Compare V1's new `_company_portfolio_roles()` (`app/services/company_workspace.py`) deliberately does not reuse this hardcoded filter and instead walks all `ROLE_BUCKETS` roles, so the same company can now show a fuller, role-distinct portfolio in Compare than on its own profile page -- a real inconsistency between the two views of identical underlying data. |
| **Impact** | Cosmetic/completeness only, not a trust or data-integrity issue: the underlying Relationship records are unaffected and still surface correctly everywhere else (e.g. the profile's generic relationships list, if rendered elsewhere). A company whose only real variety relationships are e.g. licensee or marketer roles will look variety-less on its own profile page. |
| **Workaround** | None needed for this mission -- Company Compare was built to read all roles directly rather than propagate the single profile's narrower filter, so Compare itself does not inherit this gap. |
| **Recommended resolution** | Extend `company_profile_context()`'s `company_varieties` (and the profile template's row copy) to cover all `ROLE_BUCKETS` roles, matching the discipline already proven in `_company_portfolio_roles()`. Out of this mission's stated scope (Compare is additive/derived; the single Company profile page itself was not to be redesigned). |
| **Status** | active |
| **Owner lane** | product/UI |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

### TD-100 — Company berry portfolio is an authored field, not derived from trusted Relationships

| Field | Value |
|---|---|
| **Severity** | Low |
| **Area** | data quality / berry-portfolio completeness |
| **Date discovered** | 2026-08-23 |
| **Evidence** | Company Compare V1 mission. Both the existing single Company profile (`company_berry_portfolio()` in `app/main.py`) and the new Company Compare V1 (`app/services/company_workspace.py::present_company_compare()`, for consistency with the single profile) read a Company entity's berry chips directly from its own authored `berry_ids` attribute rather than deriving them from the berries of the varieties it holds a trusted Relationship to. If `berry_ids` is stale, incomplete, or never authored for a company that nonetheless has trusted breeder/marketer/etc. relationships to varieties of a given berry, that berry will not appear in either view. |
| **Impact** | A company's displayed berry portfolio can under-represent (or, less likely, over-represent) its real trusted-relationship footprint if `berry_ids` drifts from the relationship data. Not observed as an active discrepancy in the accepted Planasa/Costa Group/Fall Creek/SanLucar test set during this mission, but the two data sources are not reconciled by any validator. |
| **Workaround** | None needed for this mission -- reusing the same authored field as the existing single Company profile keeps both views consistent with each other, even though neither is derived from Relationships. |
| **Recommended resolution** | Either derive berry portfolio from trusted Relationship-to-Variety berry_ids as a cross-check, or add a validator that flags a Company's authored `berry_ids` diverging from its trusted varieties' berries. Out of this mission's scope (Compare reuses existing presentation conventions, does not redesign them). |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | none yet |

Do not dump older Phase 2B attachment/UoW fixes here; they are already shipped.
