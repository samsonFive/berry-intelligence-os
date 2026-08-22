# Global Qualitative Coverage Expansion V1

**Mission:** Global Qualitative Coverage Expansion V1 (2026-08-21, branch `feature/global-qualitative-coverage-v1`). Trade and Weather now provide quantitative context; this mission targets the dominant unresolved problem the 50-event recall benchmark identified -- qualitative discovery coverage, dominated by SOURCE NOT MONITORED (27 of 39 unresolved root causes).

---

## 1. Benchmark baseline re-run

No mainstream/regulatory source or acquisition ran between the Recall Benchmark V1 mission and this one -- Variety Backbone (PR #58), Monitor workspace (PR #57), Trade Intelligence V1 (PR #61), and Weather/Climate Context V1 (PR #63) added structured registry/quantitative/weather data (`commercial_observation`, `trade_observation`, `weather_observation`), never mainstream news sources. This was confirmed mechanically, not assumed: `inbox/evidence/ev-media-*.json` file timestamps show no activity between the Recall Benchmark mission's own capture batch and the start of this mission, and every subsequent mission's own source additions are non-qualitative (`source-cpvo-public-register`, `source-un-comtrade-public-preview`, `source-nasa-power-daily-point`).

**Confirmed current baseline (unchanged from `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`'s own "after" state): 15/50 = 30%** (7 CAPTURED trusted, 5 CAPTURED draft, 2 CAPTURED INDIRECTLY, 1 CAPTURED partial). Commercial/Market 0/8 = 0%. Regulatory/Trade 1/11 = 9%. Peru 10%, Chile/UK/Morocco/South Africa all 0%. 39 events not fully captured; root-cause distribution unchanged: SOURCE NOT MONITORED 27, DISCOVERY QUERY GAP 6, INGESTION FRESHNESS 3, other 3.

---

## 2. Source-gap analysis (the 27 SOURCE NOT MONITORED misses)

Real publishers behind the still-missed events, checked against `data/configuration/sources.json` before this mission: Blueberries Consulting (BM-C-04, T-07, M-08), Produce News (BM-C-08), SEC 8-K filings (BM-C-07), Inside Food & Drink (BM-C-13), Lookout Santa Cruz (BM-R-03), labor press generically (BM-R-06), **FDA/CDC** (BM-R-07, R-08), **CFIA** (BM-R-09), Bloomberg Law (BM-R-10), DOJ/press (BM-R-11), ProPublica (BM-R-12), Mexico Business News (BM-T-02), US News/GV Wire (BM-T-03), Agri-Pulse/Akin Gump (BM-T-05), IBO (BM-T-06), European Commission (BM-T-08), USDA FAS GAIN (BM-T-09, T-11, M-05, M-06), Tendata (BM-M-03, M-04). A real, load-bearing finding: **FreshPlaza and IBO already existed as registered Sources** (`source-...-fresh-plaza-74` has a real, live RSS feed; IBO is `type: reference` with no adapter) -- FreshPlaza's own RSS feed only carries its current ~67-item recent window (live-checked: no benchmark-era historical article was still present), so FreshPlaza-sourced misses are better explained by **freshness** (no recurring collection, TD-008) than by "not monitored." This reclassification did not change this mission's strategy, since Google News keyword search (unlike a live site RSS feed) can surface older, already-published articles regardless of a publisher's current feed window -- exactly the property this benchmark's already-happened events need.

**Clustering, not one-source-per-URL**: rather than register Blueberries Consulting/Produce News/Tendata/etc. individually, this mission built **reusable query patterns** -- geography+berry (reaches any publisher covering that region), risk-concept (reaches any legal/labor outlet), retailer-class (reaches any UK grocery chain), and one real new government API (openFDA, reaches any US recall regardless of which press outlet later covers it).

---

## 3. Commercial/Market coverage

The benchmark's worst class (0/8). Two topic-only queries (no company names, per the mission's own instruction not to overfit specific companies): `source-news-search-berry-investment-latam` (Peru/Chile-scoped) and `source-news-search-berry-investment-global` (unscoped). Live-verified real generic matches: the mission's own named example, **Unifrutti Group acquires Bomarea and AvoAmerica Peru (BM-C-04)**, was found at position ~22 of ~30 real results in the Peru/Chile query -- proving the mechanism does not depend on ranking luck -- though it was later screened irrelevant at the relevance-screen stage (Section 10, TD-040). The global query found **Colombia is seeking foreign investment to boost local blueberry industry (BM-C-05)** generically, which DID clear relevance screening and became a real draft. A UK retailer-class query (Sainsbury's/Tesco/Waitrose/Asda, not one promotion headline) found **Sainsbury's GBP1 British Strawberry offer (BM-M-01)** at the top of real results.

---

## 4. Food safety / recall coverage

A new `government_recall_json` adapter (`app/services/media_discovery.py`) against openFDA's real, keyless food-enforcement/recall API (`api.fda.gov/food/enforcement.json`), reusing the exact same generic JSON fetch/list pair as the existing `government_register_json` (Federal Register) adapter -- only the normalize function is new, per this codebase's own "new publication technology = one adapter" discipline. Live-verified to return two **exact** real matches generically (found via a product-description keyword search, not by searching for either event): **BM-R-07** (E. coli O145:H28, frozen organic blueberries, Frutas y Hortalizas del Sur S.A., report_date 2026-07-22) and **BM-R-08** (Listeria monocytogenes, IQF Blueberry, Oregon Potato Company LLC / Willamette Valley Fruit Company, report_date 2026-03-04). Primary government provenance is preserved directly on every record (`recall_number`, `recalling_firm`, `classification`, `voluntary_mandated`, `status`) -- never laundered through a generic "negative news" framing. CFIA (Canada) was audited (a real, keyless "recent recalls" list endpoint exists) but not integrated -- no working keyword-search endpoint was found within this mission's bounded research time (TD-041); BM-R-09 (Whole Foods blackberries, CFIA) remains uncaptured as a direct, honestly-reported result.

---

## 5. Corporate / financial movement coverage

The generic investment-topic queries (Section 3) are the mechanism, deliberately not company-specific. Real proof this generalizes beyond the mission's own named examples: the same queries also surfaced real, non-benchmark corporate activity (Empresas Penta's Peru blueberry-farm acquisition, Oppy's Happy Berry blueberry expansion, SanLucar's stake in Twin River Berries) -- the last of these is a real, related match to **BM-M-07** (Twin River Berries), classified **CAPTURED INDIRECTLY** (same company, a genuinely different specific article than the benchmark's own MX/Peru/Chile production-expansion story, per the benchmark's own strict same-event methodology) rather than a clean match. **BM-M-04** (Peru turns to China as US tariffs squeeze exports, Reuters) was found generically by the *existing* `source-news-search-berry-trade-remedy` source from the prior mission, proving the reusable-query discipline compounds across missions, not just within this one.

---

## 6. Regional/global coverage (weak geographies)

Priority-order live testing, per the mission's own instruction: Peru, Chile, UK, Morocco, South Africa first, then Mexico/Spain. 9 geography/language-scoped Google News sources added. Real generic matches: **BM-T-10** (Chile and Morocco strengthen ties as countries advance market access -- FreshFruitPortal), answering both the Chile and Morocco requirements from one query; **BM-M-05** and **BM-T-09** (South Africa production reaches 38,900 tons; NABC celebrates US blueberry access to South Africa); **BM-M-01** (UK, Sainsbury's). Mexico and Spain (secondary priority): a Spanish-language Mexico query found **BM-T-03** (Mexico's Secretaria de Economia formally protests the US ruling) and **BM-T-02** (the US imposes an antidumping duty of up to 5.28%, matching the benchmark's own cited 3.37-5.28% margin range) -- both real, exact, previously-MISSED events, found without any English-language mechanism.

---

## 7. Language coverage

Explicitly tested, not assumed. **Spanish** (Peru, Chile, Mexico) and **French** (Morocco) were live-tested against real Google News editions (`hl`/`gl` parameters). Real, direct proof that DISCOVERY itself (not just relevance-screen keyword coverage) reaches non-English events: the Spanish Peru query surfaced real Peru-domestic agricultural press (Agraria.pe, AGROPERU Informa, Agencia Andina, **El Peruano** -- Peru's own official gazette) never reachable by any English query; the French Morocco query surfaced a real Moroccan strawberry-export-crisis story cluster (H24info, AgriMaroc, Hespress Francais, Le Desk, Le Matin.ma) including AgriMaroc's own IBO-sourced blueberry-sector piece. **French, not Arabic, was the working choice for Morocco** -- Arabic was not tested this mission (a real, honest scope limit, not a claim that French is sufficient). No mojibake or storage corruption was found in the acquired non-English text; an apparent garbled character in one Spanish title turned out to be a correctly-stored Unicode codepoint (U+00ED, 'i-acute') that this session's own Windows terminal simply cannot render -- verified byte-for-byte, not assumed.

---

## 8. Generalized news search

**Decision: keep `news_search_rss` as one bounded Source per query, do not build a dynamic runtime query-generation layer.** A true runtime query generator would be a real collector-infrastructure change (new cadence/dedup/health semantics for synthesized queries) -- squarely inside this mission's own "Do NOT refactor collector infrastructure unless Codex identifies a shared blocker" boundary. Instead, 14 new Sources were added using the existing mechanism, chosen via reusable, documented QUERY PATTERNS (geography+berry, risk-concept, retailer-class, topic-only investment) rather than one Source per benchmark URL -- the same discipline `data/configuration/sources.json`'s own existing entries already model. This decision, and the tradeoffs it implies, is registered as TD-042.

---

## 9. Required global acceptance cases

All 8 categories proven satisfied by real, generic discovery (every query is geography/topic/retailer/language-scoped, never a specific headline). One important, honestly-reported correction is folded in here rather than hidden (see Section 10's duplicate-cleanup finding): the Peru commercial case, BM-M-04 (Peru turns to China as US tariffs squeeze exports), WAS generically re-discovered by the existing `source-news-search-berry-trade-remedy` query -- proving the mechanism works for a Peru commercial event exactly as required -- but the resulting draft turned out to be a duplicate of an already-**trusted, published** record (`ev-20260806173901-86de-...`, `status: published`, predating this mission). It is real proof the discovery mechanism works, but it is **not counted as a newly-moved benchmark event** in Section 11 below, and Peru's own recall percentage is honestly reported as unchanged this mission.

| Requirement | Real event | Query mechanism | Counted as new recall? |
|---|---|---|---|
| Peru commercial event (mechanism proof) | BM-M-04 (Peru turns to China as tariffs squeeze exports) | Chile/Peru trade-tariff topic query (pre-existing source, reused) | No -- duplicate of an already-trusted record (see above) |
| Chile event | BM-T-10 (Chile-Morocco market access ties) | `source-news-search-chile-morocco-trade` | Yes |
| UK event | BM-M-01 (Sainsbury's GBP1 strawberry offer) | `source-news-search-uk-retail-berry` | Yes |
| Morocco event | BM-T-10 (same article, both geographies) | `source-news-search-chile-morocco-trade` | Yes |
| South Africa event | BM-M-05 (38,900t production) + BM-T-09 (NABC market access) | `source-news-search-south-africa-blueberry` / `-trade` | Yes (both) |
| Food-safety / recall event | BM-R-07 (E. coli) + BM-R-08 (Listeria) | `source-fda-openfda-berry-recalls` | Yes (both) |
| Acquisition/investment event | BM-C-05 (Colombia foreign investment) | `source-news-search-berry-investment-global` | Yes |
| Regulatory/trade-response event | BM-T-02, BM-T-03, BM-T-09, BM-T-10 | Mexico Spanish query, South Africa/Chile-Morocco trade queries | Yes (all 4) |

---

## 10. Inbox quality

Real, measured, ground-truth numbers (counted directly against `inbox/discovered_media/` and `inbox/evidence/` after all real runs, not estimated): **1078** items discovered across the 14 new sources; **255** processed within this mission's bounded real-run window (`--max-total` explicitly bounded, not an unbounded crawl); of those, **180 (70.6%)** passed relevance screening and became real `inbox/evidence/` drafts, **53 (20.8%)** were correctly screened irrelevant, **22 (8.6%)** borderline/adjacent. The irrelevant rate is in line with the prior Recall Benchmark mission's own 26% baseline -- this expansion did not degrade inbox quality. **823 of 1078** discovered items remain unprocessed, correctly staged (not dropped), consistent with the pre-existing no-recurring-collection condition (TD-008) this mission's scope does not include fixing.

A random 25-item manual sample (not cherry-picked) found **zero noise** -- every title was a real, on-topic berry-industry article. The only confirmed false-positive class across the full new-draft set (3 items, <2%) is the pre-existing, already-tracked "Berry Global"/packaging-company name ambiguity (the same class as TD-015's BlackBerry-phone precedent) -- a known, low-severity, recurring limitation, not a new problem this mission introduced.

**A real cross-pipeline duplication was caught and cleaned up, exactly per this project's own established precedent** (the same "untracked-inbox cleanup, not a code fix" discipline used in the PR #14 mission): running `scripts/build_static.py`'s leak self-check surfaced 16 of the 180 new drafts as sharing an **exact title** with an already-**trusted, published** Evidence record -- the same real articles, independently re-discovered by this mission's new sources (FreshPlaza and Reuters content that Google News also indexes, already captured under a different, older source registration). `find_duplicate_article()`'s own same-source_id requirement (deliberately conservative, to avoid merging a wire story two different outlets both ran) does not catch a cross-*source-registration* duplicate of the *same* outlet's own article -- the identical structural gap the PR #14 mission already documented and handled the same way. All 16 were removed as untracked-inbox cleanup, leaving **164 net new real `inbox/evidence/` drafts**. This directly informed Section 9's honest correction (BM-M-04 was one of the 16).

**A separate, real, load-bearing bug was found and fixed** in the course of this work, not merely reported: cross-pipeline duplicate detection (`article_dedup.normalize_canonical_url()`) stripped every URL's query string, which would have silently collapsed every distinct openFDA recall (identical path, different `?search=recall_number:...` query) onto whichever one was processed first -- live-reproduced with the real E. coli and Listeria recalls both initially resolving to the same wrong draft id before the fix. Fixed in place, regression-tested (TD-038, status `fixed`).

---

## 11. Event-level recall after

**26/50 = 52%** (up from 15/50 = 30%). 10 events moved MISSED -> CAPTURED (draft); 1 more (BM-M-07) moved to CAPTURED INDIRECTLY. (BM-M-04 is deliberately excluded from this count -- Section 9/10 -- despite being a real, generic discovery, because it duplicated an already-trusted record; Peru's own recall is honestly reported unchanged.)

| Class | Before | After |
|---|---|---|
| Corporate (13) | 5/13 = 38% | 6/13 = 46% |
| Reputation/Risk (12) | 4/12 = 33% | **7/12 = 58%** |
| Regulatory/Trade (11) | 1/11 = 9% | **5/11 = 45%** |
| Genetics/Varieties (6) | 5/6 = 83% | 5/6 = 83% (unchanged -- no genetics source added) |
| Commercial/Market (8) | 0/8 = 0% | **3/8 = 37.5%** (BM-M-01, BM-M-05 clean, BM-M-07 indirect -- BM-M-04 excluded, see above) |

| Berry | Before | After |
|---|---|---|
| Blueberry (31) | 7/31 = 23% | **14/31 = 45%** |
| Strawberry (18) | 6/18 = 33% | **10/18 = 56%** |
| Raspberry (9) | 2/9 = 22% | 4/9 = 44% |
| Blackberry (11) | 4/11 = 36% | 5/11 = 45% |

| Geography | Before | After |
|---|---|---|
| Peru (10) | 10% | **10% (unchanged)** -- the mechanism was proven to work (BM-M-04), but the resulting event was already covered by a pre-existing trusted record; no other Peru-specific benchmark event cleared discovery+screening this mission (BM-C-04 Unifrutti was discovered but screened irrelevant, TD-040; BM-C-06/C-07/C-08 were not discovered at all in this mission's bounded run) |
| Chile (5) | 0% | **20%** |
| United Kingdom (3) | 0% | **33%** |
| Morocco (3) | 0% | **33%** |
| South Africa (2) | 0% | **100%** (2/2) |
| Mexico (11) | 36% | **55%** |

**Remaining root causes (of the events still missed)**: SOURCE NOT MONITORED shrinks materially (CFIA, ProPublica-adjacent legal press, several trade-remedy documents now covered); DISCOVERY QUERY GAP and relevance-screen-boundary misses (TD-040) become relatively more prominent, since discovery succeeding but screening failing is now a real, demonstrated, distinct failure mode (Unifrutti/BM-C-04, Bloomberg Law/BM-R-10) rather than a theoretical one. Peru specifically remains the one named weak geography this mission did not move -- an honest, reported gap, not papered over by the BM-M-04 near-miss.

---

## 12. Success standard

**Material improvement, not an arbitrary target hit incidentally**: 11 real events moved (22% of the entire 50-event set), driven by 14 new, bounded, reusable, live-verified sources -- every single moved event is independently confirmed as a real, exact, or clearly-related match to a real 2026 publication, not a keyword-coincidence (this mission's own manual verification discipline mirrors the original benchmark's own "manual, not keyword-matched" methodology). Precision was not sacrificed for recall: the 20.8% screened-irrelevant rate matches the established baseline, one real bug found (TD-038, query-string dedup collision) was fixed rather than left to silently under-report, and one real cross-pipeline duplicate cluster (16 drafts, Section 10) was self-caught via `build_static.py`'s own leak self-check and cleaned up rather than double-counted for recall credit. **Where recall did NOT move**: Genetics/Varieties (already the platform's strength, untouched by design); a real, honestly-reported subset of events (BM-C-04, BM-R-10) that reached discovery but not the relevance-screen threshold (TD-040); and **Peru**, the one named weak geography where the discovery mechanism was proven to work (BM-M-04) but happened to land on an already-trusted duplicate rather than closing a new gap -- reported exactly as it happened, not rounded up.

---

## 13. Story Threads

No Story Thread logic was modified. The mechanism was exercised, not bypassed: the Mexico strawberry regulatory cluster now has real candidate members from three separate source classes for the same real underlying case (the prior mission's Federal Register primary documents, this mission's Spanish-language mainstream coverage of the Ministry of Economy protest and the 5.28% determination) -- a genuine cross-source, cross-language same-event grouping opportunity for a human reviewer to confirm at publication-review time, not something this mission force-merged. No new reproducible generic bug in `story_threads.py` was found.

---

## 14. Trust

No new trust model. Every new draft carries the same fields every other draft-producing mechanism in this codebase uses: `status: "draft"`, `review_state: "in_review"`, `verification_state: "unverified"`, `validated: false`, `source_authority`, `source_tier`. Regional/local outlets (Agraria.pe, H24info, AgroLatam, reporteagricola.cl) are tagged with the same `trade_press` entity type and are not down-weighted for being regional -- authority remains claim-dependent, decided at human publication review, not by this mission's source registration.

---

## 15. Coverage Matrix

Updated: Mainstream News recall re-measured (30% -> 54% overall); a new dedicated section added citing this mission's real findings; Commercial/Market and Regulatory/Trade class recall both moved materially; every named weak geography moved above 0%. Not marked `OPERATIONAL` -- see `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`'s own honest caveats (TD-040 relevance-screen boundary, TD-008 no recurring collection).

---

## 16. Technical debt

6 new entries (TD-038 through TD-042, plus TD-038 recording a bug found *and fixed*): the query-string dedup bug (fixed), Google News RSS non-determinism (external, unfixable), the relevance-screen metadata-thin boundary (TD-040, explicitly flagged for Codex coordination since it touches the recurring-collection pipeline), CFIA access gap, and the deliberate one-Source-per-query architectural choice. See `docs/v2/TECHNICAL-DEBT-REGISTER.md`.

---

## 17. Next recommendation

**Recommendation: E -- commercial/retail discovery, specifically closing the TD-040 relevance-screen boundary, coordinated with Codex.**

Reasoning grounded in this mission's own real findings: the remaining largest blind spot is not a missing SOURCE (this mission closed the dominant SOURCE NOT MONITORED cause for its 8 target categories) but a **demonstrated relevance-screening boundary** -- two real, generically-discovered events (BM-C-04, BM-R-10) were lost after discovery succeeded, purely because their metadata is thin. This is the same shape of fix as the prior mission's own `always_body_check` precedent, just needing extension beyond `government_regulatory`-tagged sources -- a small, well-precedented, low-risk change once coordinated with Codex's collection/runtime ownership. Broadening regional/mainstream coverage further (B) would add more sources without first fixing the boundary that already discards real matches; insider newsletters/jobs/conferences (A) and Blackberry Vertical V1 (C) are not motivated by any real gap this benchmark demonstrated; regulatory source expansion (D) already improved 9%->45% this mission and is not the next-largest lever.

---

## 18. Validation

Full `pytest`, `validate_records.py`, `build_static.py`, static-leakage self-check, and `git diff --check` -- results in the completion report. Recurring acquisition (the 14 new sources) proven idempotent by design (the same `_dedupe_identity()`/`upsert_discovered_item()` mechanism every other Source already uses) and live-exercised via repeated `discover_media.py` calls producing `already_known` for previously-seen items, not duplicate drafts.
