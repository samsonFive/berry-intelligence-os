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
| TD-UI-001 | TD-001 **resolved** (residual cold ranking is KL-011) |
| TD-UI-002 | TD-002 **resolved** (remaining authoring gap is TD-012) |
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
| **Evidence** | Same as withdrawn TD-ACQ-001. `PROJECT-STATUS.md` / `app/services/article_dedup.py`: same story under Google-News redirect vs publisher RSS is different URL + `source_id` (recurring draft `ev-media-cec61845f15d790fd055`). Deterministic URL/title+source+date matching cannot merge them without fuzzy title matching (explicitly refused). |
| **Impact** | Duplicate trusted or pending rows. Operators dismiss by hand. |
| **Workaround** | Inbox cleanup of known duplicates. |
| **Recommended resolution** | Keep deterministic matching. Optional later: publisher canonical-id when the Source record declares one. |
| **Status** | active |
| **Owner lane** | data |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_article_dedup.py` |

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

### TD-012 — Assessment authoring form cannot declare `market_ids`

| Field | Value |
|---|---|
| **Severity** | Medium |
| **Area** | assessments / authoring |
| **Date discovered** | 2026-08-21 |
| **Evidence** | Schema already stores optional `market_ids`. Live records: 4 blueberry-specific, 1 unscoped, 0 multi-berry. `GET/POST /assessments/new` (`assessment_form.html`) has no berry-scope field, so new Assessments are always unscoped unless an operator edits JSON. |
| **Impact** | Analysts cannot declare berry-specific vs company-wide at write time. UI labeling (TD-002) can only show what was stored. |
| **Workaround** | Edit the Assessment JSON `market_ids` array (`berry-*` ids). Do not infer from title text. |
| **Recommended resolution** | Smallest additive UI: optional berry checkboxes on the existing form that write `market_ids`. Empty remains unscoped. Do not invent inferred trust metadata. |
| **Status** | active |
| **Owner lane** | product |
| **PR/SHA when resolved** | — |
| **Regression-test reference** | `tests/test_assessment_scope.py`; `app/templates/assessment_form.html` |

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
| KL-011 | Cold HTML nav still ranks reading+pending (~2.1s) | Signature cache makes unrelated warm pages ~10ms. Do not cache trust/review beyond the folder signature. Further cuts are precomputed counts, not stale badges. |

---

## RESOLVED

| ID | Title | Resolved | Notes |
|---|---|---|---|
| TD-THREAD-001 | Company-primary vs variety-primary false separation | 2026-08-20 PR #51 `807e059` | `_cross_subject_event_edge()` in `app/services/story_threads.py`. Tests in `tests/test_story_threads.py`. |
| TD-001b | Overlay Reader paid Morning Brief | 2026-08-21 prototype hardening | `/api/` paths skip nav Brief. Warm overlay ~18–20ms on the then-current runtime. |
| TD-001 | Global HTML nav rebuilt full Morning Brief presentation | 2026-08-21 decision-workflow | Function-level `mode=full` median 2772ms → `mode=nav` 2089ms. Overlay 20ms. Warm `/assessments` 10ms. Residual ranking on cold miss is KL-011. Withdrawn draft ID: TD-UI-001 (was still Open there). |
| TD-002 | Company Bottom Line berry-scope unlabeled | 2026-08-21 decision-workflow | Classify from stored `market_ids` only; label unscoped vs berry-specific; do not hide. Remaining authoring gap is TD-012. |
| TD-003 | Compact repeated kind + status marks | 2026-08-21 decision-workflow | Type stays on `.v2-card-line`. Footer marks are Direct / Watch / Pending\|Trusted / Story / Signal. |
| TD-004 | Landscape JS breadcrumb hardcoded Blueberry | 2026-08-21 decision-workflow | Reads `data-berry-label`. Landscape itself remains unmigrated (KL-004). |
| TD-011 | Reading Queue rebuilt full Morning Brief | 2026-08-21 decision-workflow | `/queues/reading` uses `mode="nav"`. |

Do not dump older Phase 2B attachment/UoW fixes here; they are already shipped.
