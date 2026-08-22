# Intelligence Recall Benchmark

**Mission:** Mainstream News + Regulatory Coverage Recall Benchmark V1 (2026-08-21, branch `feature/mainstream-regulatory-recall-benchmark`).
**Purpose:** A durable, repeatable event set for measuring "what important competitive intelligence should the OS have seen, and how much did it actually capture" -- reused by future source-expansion missions, not a one-time report.

This is a living artifact. Re-running the classification (Part 3) against a later canonical is the intended way to track recall over time; the event set (Part 2) should be extended, not replaced, as later missions add more strata.

---

## 1. Methodology

- Events were discovered via live external web research (WebSearch), **not** selected because the OS already contained them -- several events below were deliberately chosen from categories/geographies the platform's own domain-pack coverage was weakest in, to avoid survivorship bias.
- Every event has a real publisher, date, and URL captured at research time (2026-08-20/21).
- Classification against the OS is **manual, not keyword-matched**. An earlier automated pass (crude title/summary keyword co-occurrence against `data/evidence/`) produced a 58-60% "recall" figure; manually reading the actual matched records found most of those matches were topically-adjacent, not the same event (e.g. a generic "Colombia's blueberry boom" article matched a specific "Colombia seeks foreign investment" event on `colombia`+`blueberry` alone). The keyword pass is not reported as a result -- it is reported here as a finding in itself: **naive keyword matching against this corpus overstates recall by roughly 3x**, which is exactly the inflation risk this benchmark was commissioned to avoid.
- Five classification states are used, per the mission brief:
  - **CAPTURED** -- a specific, verified matching record exists as trusted/published Evidence.
  - **CAPTURED (draft/pending review)** -- a specific, verified matching record exists as an untrusted `inbox/evidence/` draft (discovered, not yet human-reviewed). Never counted as "captured" in the trust-gate sense; reported separately.
  - **CAPTURED INDIRECTLY/RELATED** -- the OS has real coverage of the same underlying story cluster (e.g. a company's own response article) but not the specific triggering event/document.
  - **MISSED** -- no matching record found, direct or indirect.
  - **OUT OF SCOPE** -- not used below; every event in this set was judged genuinely in-scope for a berry CI platform.
- "Same event" requires matching subject **and** a plausible date/content correspondence, not just shared keywords -- e.g. a 2023 evergreen "Big Changes on the Horizon for the Blackberry Market" article was rejected as a match for a 2026 production-forecast statistic that happens to share the same headline text (same page, updated over time; the *cited figure* was not verifiably present in the 2023-dated record).

## 2. Benchmark event set (50 events)

Stratified across 5 intelligence classes and all 4 berries, per the mission brief. Full machine-readable event list (with keywords used for matching) is preserved in this mission's working notes; the table below is the durable, human-reviewable record. IDs are stable across future re-runs of this benchmark.

**By class:** CORPORATE 13 · REPUTATION/RISK 12 · REGULATORY/TRADE 11 · GENETICS/VARIETIES 6 · COMMERCIAL/MARKET 8
**By berry** (an event may name more than one): Blueberry 31 · Strawberry 18 · Blackberry 11 · Raspberry 9 -- reflects real-world mainstream/trade coverage volume (blueberry dominates global berry trade press), not a benchmark-construction bias.
**Required acceptance cases:** 10 (marked `**`), all naming Driscoll's reputational coverage or the Mexico strawberry antidumping proceeding, per the mission's explicit requirement.

| ID | Class | Berry | Event | Publisher / Date | Before | After |
|---|---|---|---|---|---|---|
| BM-C-01 | Corporate | Blueberry | Naturipe/Hortifrut/Mountain Blue Orchards breeding partnership | The Packer, 2026 | CAPTURED | CAPTURED |
| BM-C-02 | Corporate | Blueberry | AgroBerries Group expands via Mountain Blue Orchards licensing | FreshFruitPortal, 2026-06-24 | CAPTURED | CAPTURED |
| BM-C-03 | Corporate | Blueberry | Alpine Fresh invests in ABB Growers (Netherlands) | The Packer, 2026 | CAPTURED | CAPTURED |
| BM-C-04 | Corporate | Blueberry | Unifrutti Group acquires Bomarea + AvoAmerica Peru | Blueberries Consulting, 2026 | MISSED | MISSED |
| BM-C-05 | Corporate | Blueberry | Colombia seeks foreign blueberry investment | FreshFruitPortal, 2026-08-20 | MISSED | MISSED |
| BM-C-06 | Corporate | Blueberry | Peruvian blueberry project $60M investment | FreshFruitPortal, 2026 | MISSED | MISSED |
| BM-C-07 | Corporate | Blueberry | Mission Produce expands Peru blueberry acreage | SEC 8-K, 2026 | MISSED | MISSED |
| BM-C-08 | Corporate | Blueberry | NuBerry Farms organic blueberry investment, Peru | Produce News, 2026 | MISSED | MISSED |
| BM-C-09 | Corporate | Strawberry | Summer Berry Co. first year-round UK strawberries | Fruitnet, 2026 | MISSED | MISSED |
| BM-C-10 `**` | Corporate | All 4 | **NYT: "Why Are Berries Everywhere, in Every Season? Driscoll's."** (Julia Moskin) | NYT Dining, 2026-07-07 | MISSED | **CAPTURED (draft)** |
| BM-C-11 | Corporate | Blueberry | Costa Group launches BluGenix; Yunnan/Laos investment | Produce Report, 2026 | CAPTURED (partial -- older Yunnan article found, not the 2026 BluGenix launch specifically) | unchanged |
| BM-C-12 | Corporate | All 4 | Driscoll's Mexico presents at World Agri-Tech Mexico 2026 | conference site, 2026 | MISSED | MISSED |
| BM-C-13 | Corporate | Blueberry | Hall Hunter Partnership launches 2026 UK season | Inside Food & Drink, 2026 | MISSED | MISSED |
| BM-R-01 `**` | Reputation | Strawberry | **Driscoll's PFAS/pesticide class-action lawsuit** (filed 2026-06-26) | Insurance Journal / ClaimDepot | MISSED | **CAPTURED (draft)** |
| BM-R-02 `**` | Reputation | Strawberry | **Driscoll's greenwashing lawsuit** | Insurance Journal, 2026-07-21 | MISSED | **CAPTURED (draft)** |
| BM-R-03 `**` | Reputation | Strawberry | **Driscoll's whistleblower suit** (David Harada) | Lookout Santa Cruz, 2026 | MISSED | MISSED |
| BM-R-04 `**` | Reputation | Strawberry | **Mamavation independent testing finds PFAS/pesticide residue** | Mamavation, 2026-05 | MISSED | **CAPTURED (draft)** |
| BM-R-05 `**` | Reputation | Strawberry | **Driscoll's delisted from Chinese supermarkets** | Global Times, 2026-07 | CAPTURED INDIRECTLY (Driscoll's own China-market response article, Produce Report) | unchanged |
| BM-R-06 `**` | Reputation | Strawberry | **International boycott campaign against Driscoll's** | labor press | MISSED | MISSED |
| BM-R-07 | Reputation | Blueberry | FDA/CDC E. coli O145:H28 frozen blueberries outbreak | FDA/CDC, 2026-07 | MISSED | MISSED |
| BM-R-08 | Reputation | Blueberry | Listeria recall, Oregon Potato Co. frozen blueberries | FDA, 2026 | MISSED | MISSED |
| BM-R-09 | Reputation | Blackberry | Whole Foods organic frozen blackberries recalled | CFIA, 2026 | MISSED | MISSED |
| BM-R-10 | Reputation | Blueberry | First Pick Farms MI forced-labor lawsuit settled | Bloomberg Law, 2026-07 | MISSED | MISSED |
| BM-R-11 | Reputation | Blueberry | Georgia forced-labor prosecution (onion+blueberry) concludes | DOJ/press, 2026-06 | MISSED (false-positive on generic Georgia-blueberry coverage) | MISSED |
| BM-R-12 | Reputation | Blueberry | ProPublica: "Do My Grocery Store Blueberries..." investigation | ProPublica, 2026 | MISSED | MISSED |
| BM-T-01 `**` | Regulatory | Strawberry | **Commerce initiates antidumping investigation, Mexico strawberries (A-201-869)** | trade.gov, 2026-01 | CAPTURED (draft, weak trade-press match) | **CAPTURED (draft, 2 real Federal Register primary documents)** |
| BM-T-02 `**` | Regulatory | Strawberry | **Commerce preliminary determination, margins 3.37-5.28%** | Mexico Business News, 2026-08 | MISSED | MISSED (mechanism now exists; document not yet indexed by Federal Register's API as of this run) |
| BM-T-03 `**` | Regulatory | Strawberry | **Mexico's Ministry of Economy formally protests ruling** | US News/GV Wire, 2026-08-19 | MISSED | MISSED |
| BM-T-04 | Regulatory | Strawberry | US Senator urges faster antidumping review | FreshPlaza | MISSED | MISSED |
| BM-T-05 | Regulatory | Strawberry | Original antidumping petition filed (2025-12-31) | Agri-Pulse/Akin Gump | MISSED | MISSED |
| BM-T-06 | Regulatory | Blueberry | Chile/Peru/Morocco growers respond to US import duties | IBO, 2026-08-14 | MISSED | MISSED |
| BM-T-07 | Regulatory | Blueberry | Peru tariff exemption excludes blueberries | Blueberries Consulting | MISSED | MISSED |
| BM-T-08 | Regulatory | Blueberry | EU Reg 2026/215 -- ethephon MRL tightened for blueberries | European Commission | MISSED (false positive: different, Australian MRL story) | MISSED |
| BM-T-09 | Regulatory | Blueberry | South Africa granted US blueberry market access | FreshPlaza/USDA FAS | MISSED | MISSED |
| BM-T-10 | Regulatory | All 4 | Chile-Morocco market-access ties strengthen | FreshFruitPortal, 2026-08-18 | MISSED | MISSED |
| BM-T-11 | Regulatory | All 4 | USDA FAS GAIN "Berry Annual Voluntary" (Mexico) | USDA FAS | MISSED | MISSED |
| BM-G-01 | Genetics | Blackberry | PSG launches 'Rejoice' blackberry at Aneberries Congress | Fruitnet, 2026 | CAPTURED | CAPTURED |
| BM-G-02 | Genetics | Raspberry | PSG commercializes 2 new raspberry varieties, Europe/Africa | Fruitnet, 2026 | MISSED | MISSED |
| BM-G-03 | Genetics | Rasp./Black. | Wish Farms/Berry Sweet Research breeding trials (Carlos Fear) | The Packer, 2026 | CAPTURED | CAPTURED |
| BM-G-04 | Genetics | Blueberry | Costa BluGenix -- 5 Yunnan-suited varieties | Produce Report, 2026-05-29 | CAPTURED | CAPTURED |
| BM-G-05 | Genetics | Blueberry | Naturipe/Hortifrut/MBO breeding partnership (genetics angle) | The Packer, 2026 | CAPTURED | CAPTURED |
| BM-G-06 | Genetics | Blackberry | Driscoll's new blackberry varieties (Elvira/Rebecca/Laurita) | trade/USDA AMRC | CAPTURED INDIRECTLY (code-named patent drafts exist; not confirmed same 3 named varieties) | unchanged |
| BM-M-01 | Commercial | Straw./Blue. | Sainsbury's GBP1 British Strawberry promotion | Sainsbury's/FreshPlaza | MISSED | MISSED |
| BM-M-02 | Commercial | Blueberry | Chilean blueberry exports to US fall 13% | trade press | MISSED (false positive, generic export coverage) | MISSED |
| BM-M-03 | Commercial | Blueberry | Peru blueberry production +25% to 400,000t forecast | Tendata | MISSED (false positive) | MISSED |
| BM-M-04 | Commercial | Blueberry | Peru turns to China as US tariffs squeeze exports | Tendata | MISSED (false positive) | MISSED |
| BM-M-05 | Commercial | Blueberry | South Africa blueberry production reaches 38,900t | FreshPlaza/USDA FAS | MISSED (false positive) | MISSED |
| BM-M-06 | Commercial | Blackberry | Mexico blackberry production forecast 274,000 MT | USDA FAS/trade press | MISSED (matched record is a 2023-dated evergreen page, not this stat) | MISSED |
| BM-M-07 | Commercial | Raspberry | Twin River Berries expands MX/Peru/Chile raspberry production | trade press | MISSED | MISSED |
| BM-M-08 | Commercial | Straw./Rasp. | Morocco to host XLIII Intl. Seminar on Red Fruits 2026 | Blueberries Consulting | MISSED (false positive, generic Morocco export coverage) | MISSED |

## 3. Results

### 3.1 Overall recall

| Measure | Before this mission | After this mission |
|---|---|---|
| CAPTURED (trusted/published) | 8/50 = **16%** | 8/50 = **16%** (unchanged -- nothing new was promoted through human review; that gate is intentionally untouched) |
| + CAPTURED INDIRECTLY | 10/50 = 20% | 10/50 = 20% |
| + CAPTURED (draft, pending review) | 11/50 = 22% | **15/50 = 30%** |

The overall 50-event number moves only modestly, **on purpose**: per the mission's own closing instruction ("fix only the demonstrated acquisition gaps"), the new discovery layer is scoped to the two demonstrated gap clusters (Driscoll's reputational/mainstream coverage, and the Mexico strawberry antidumping proceeding), not a general-purpose mainstream crawler. The ~35 non-Driscoll's, non-antidumping misses in this set are honestly reported as still missed -- they were not this mission's target and closing them would need their own source/query work (see Section 8).

### 3.2 Recall by intelligence class

Recomputed directly from the event-level table above (script-verified, not hand-added) -- "captured" includes CAPTURED, CAPTURED (draft), and CAPTURED INDIRECTLY.

| Class | Before | After |
|---|---|---|
| Corporate (13) | 4/13 = 31% | 5/13 = 38% |
| Reputation/Risk (12) | 1/12 = 8% | **4/12 = 33%** |
| Regulatory/Trade (11) | 1/11 = 9% | **1/11 = 9%** (unchanged in count -- T-01 upgraded from a weak trade-press match to 4 real Federal Register primary documents, but T-02/T-03/T-04/T-05/T-06/T-07/T-08/T-09/T-10/T-11 still miss) |
| Genetics/Varieties (6) | 5/6 = 83% | 5/6 = 83% |
| Commercial/Market (8) | 0/8 = 0% | 0/8 = 0% |

**Worst-recall class: Commercial/Market (0%, unchanged), followed by Regulatory/Trade (9%, unchanged in rate despite the new Federal Register sources).** Genetics/Varieties recall is far ahead of every other class -- consistent with this platform's origin as a variety/patent-focused breeder-intelligence tool; the other four classes were never its design center.

### 3.3 Recall by berry

| Berry (taggings) | Before | After |
|---|---|---|
| Blueberry (31) | 6/31 = 19% | 7/31 = 23% |
| Strawberry (18) | 2/18 = 11% | **6/18 = 33%** |
| Blackberry (11) | 3/11 = 27% | 4/11 = 36% |
| Raspberry (9) | 1/9 = 11% | 2/9 = 22% |

Strawberry's jump is almost entirely the Driscoll's + antidumping work; it is not evidence of a general strawberry-coverage improvement. (An event may name more than one berry, so column totals exceed 50.)

### 3.4 Recall by geography

Only geographies named by 2+ benchmark events shown; the full per-event geography tags are in the machine-readable event list.

| Geography (taggings) | Before | After |
|---|---|---|
| United States (18) | 3/18 = 17% | **6/18 = 33%** |
| Mexico (11) | 4/11 = 36% | 4/11 = 36% (unchanged -- the new Federal Register capture upgrades an already-counted event, T-01, rather than adding a new one) |
| Peru (10) | 1/10 = 10% | 1/10 = 10% |
| Global (6) | 5/6 = 83% | 6/6 = 100% |
| Chile (5) | 0/5 = 0% | 0/5 = 0% |
| United Kingdom (3) | 0/3 = 0% | 0/3 = 0% |
| China (3) | 2/3 = 67% | 2/3 = 67% |
| Morocco (3) | 0/3 = 0% | 0/3 = 0% |
| Canada / Europe (2 each) | 1/2 = 50% each | 1/2 = 50% each |
| Australia (2) | 2/2 = 100% | 2/2 = 100% |
| South Africa (2) | 0/2 = 0% | 0/2 = 0% |

**US recall nearly doubled (17% -> 33%)** -- the direct, expected effect of adding US-scoped sources (Federal Register, and most Google News hits for two US-headquartered companies). **Peru, Chile, Morocco, South Africa, and the UK show zero movement** -- this mission built no source targeting any of those geographies specifically, so their recall is an honest, unmoved baseline, not an oversight hidden by the overall number.

### 3.5 Recall by source class (of the 15 captured/indirect events after this mission)

Trade press: 9 · Company self-report/newsroom: 2 · **Mainstream/general press: 4** (new) · **Government primary source: 1** (new, Federal Register, covers 4 of the events since one source contributed multiple documents to the same case) · Consumer-advocacy/legal press: 0 (Mamavation's own site was never itself onboarded as a source; FreshPlaza's and other outlets' reporting *about* the Mamavation findings was what got captured, via the Driscoll's mainstream search).

## 4. Root-cause distribution (39 events still MISSED)

| Cause | Count (of 39) | Notes |
|---|---|---|
| SOURCE NOT MONITORED | 27 | Dominant cause. No mainstream/legal-press/consumer-advocacy/regional-outlet source existed for most of these publishers before this mission (Bloomberg Law, ProPublica, CFIA, FDA/CDC, USDA FAS GAIN, Blueberries Consulting, IBO, various regional trade outlets). |
| DISCOVERY QUERY GAP | 6 | A source class now exists (news_search_rss / Federal Register) but the specific query didn't surface this event -- e.g. BM-R-03/R-06 need a labor/legal-press-scoped query distinct from the company-name query used; BM-T-02/T-03 need either a later Federal Register index refresh or a targeted news query. |
| INGESTION FRESHNESS / NO RECURRING COLLECTION | 3 | BM-T-02/T-03/T-06/T-10 postdate the ~2026-08-06 batch that most of this platform's evidence was captured in -- this is a scheduling gap (no recurring/unattended collection is running yet, confirmed pre-existing in PROJECT-STATUS.md), not a source-coverage gap. |
| DEDUP/ATTRIBUTION | 1 | BM-M-06's keyword match resolved to an evergreen 2023-dated page reused for a 2026 statistic -- a content-freshness/versioning gap in how a republished/updated trade article is dated, not a duplicate-detection bug per se. |
| REVIEW BACKLOG (not a discovery gap) | 1 (T-01, before this mission) | A real draft existed in `inbox/evidence/` from an earlier session but had never been promoted through human publication review -- discovery worked, review did not happen. Resolved for T-01 specifically by the new Federal Register documents landing as fresh drafts; the underlying "drafts can sit unreviewed indefinitely" condition is unchanged and not something this mission's scope covers.
| PAYWALL/ACCESS | 1 | The NYT feature itself remains unreadable in full (metadata/snippet only, by design -- see Section 7); its *existence* is now captured, its full text deliberately is not. |

This root-cause breakdown is the reason the fix built here targeted **source coverage** (new sources) over **relevance-screen tuning**: auditing `app/services/relevance_screen.py`'s Stage A gate found it was **not** the dominant failure mode for this benchmark -- most real headlines in the missed set already contain a berry species word or the generic `berry` term, which routes them to Stage B (body-aware) screening. The one real screen-level gap found and fixed (Section 5) is narrower: a *pre-scoped, source-trusted* item (a government-register search result) can have a docket-only title with zero berry words, and that specific case is now handled via `always_body_check`, not a global loosening of the public-web screen.

## 4a. Inbox quality (mainstream/regulatory discovery, real measured numbers)

Ground truth, not run-log estimates -- counted directly against `inbox/discovered_media/` and `inbox/evidence/` after all real collection runs and the duplicate cleanup in Section 5's dedup finding.

| Measure | Count | % of discovered |
|---|---|---|
| Discovered (staged, all 5 new sources) | 248 | 100% |
| Processed so far (some queries bounded by `--max-items` for this mission's real-run testing; the rest remain correctly staged, not dropped) | 191 | 77% |
| Became a review-ready draft (direct/adjacent, pre-dedup) | 84 | 34% of processed |
| **Removed as confirmed cross-pipeline duplicates of already-trusted Evidence** (see TD-DEDUP-001) | 9 | 4% of processed |
| **Net new real drafts in `inbox/evidence/` today** | **75** | 39% of processed |
| Screened irrelevant (Stage A or Stage B correctly rejected) | 50 | 26% of processed |
| Access-limited, unconfirmed (body fetch failed and either not `TIER_DIRECT` or a transient/retryable category -- correctly left unconfirmed rather than guessed) | 44 | 23% of processed |
| Still in retry backoff at time of writing | 12 | 6% of processed |
| Within-mission duplicates (same story found by two of this mission's own sources) | 0 | -- |

One confirmed real false positive was found and is registered as debt, not silently ignored: `source-news-search-berry-trade-remedy`'s broad topic query surfaced "BlackBerry Bold 9780 now available from T-Mobile UK and Orange" (a phone-industry article) as a passing draft -- `relevance_screen.py`'s `berry_identity` category matches the literal word "blackberry" with no brand/crop disambiguation (TD-ACQ-006). This is the concrete shape of the "general-news noise" risk Section 10 of the mission warned about; it appeared once, in the one query that was topic-scoped rather than company- or case-scoped, and not in the other 4 sources.

A separate, honest data-quality gap surfaced while compiling this table: drafts created through this mission's new metadata-only paywall fallback (Section 5.4) do not get a `relevance_tier` ("direct"/"adjacent") written onto the draft file the way the normal body-acquired path does -- all 75 currently show `relevance_tier: null`. This does not affect trust or correctness (the item was still confirmed relevant by Stage A before the fallback fires), only the live Morning Brief's direct-outranks-adjacent ranking cosmetics for these specific drafts. Registered as `TD-ACQ-009` in the debt register rather than silently left unmentioned.

## 4b. Required acceptance cases -- full detail

### 1. NYT Driscoll's feature (BM-C-10)

- **Existed before this mission:** No. Zero match of any kind against `data/evidence/` or `inbox/evidence/`.
- **Why missed:** SOURCE NOT MONITORED -- the New York Times had no source registration of any kind (no RSS, no keyword search) anywhere in `data/configuration/sources.json`'s 142 pre-mission entries.
- **How it is now discovered:** Generically, not by name -- `source-news-search-driscolls` (a company-name Google News search covering all 4 berries) surfaced it in its real, live run (title: "Why Are Berries Everywhere, in Every Season? Driscoll's.", published 2026-07-08 per the discovered item, byline Julia Moskin, NYT Dining). The mechanism would find any future NYT (or other mainstream outlet's) Driscoll's story the same way -- nothing about this run was NYT-specific or hardcoded to this headline.
- **Full text or metadata-only:** Metadata-only, by design. `nytimes.com` was never fetched by any part of this mission -- Claude Code's own tooling refuses that domain outright, and the discovery item itself only carries the title/description/date/URL Google News' feed legitimately provides. The draft (`ev-media-...` in `inbox/evidence/`) has no article body.
- **Story Thread behavior:** Not tested as part of a thread (a single mainstream feature, not one of several outlets covering the same event in a tight window) -- correctly stands alone.
- **Trust/source-authority handling:** Sits in `inbox/evidence/` as an untrusted, unreviewed draft (`review_state: "in_review"`, `status: "draft"`). No auto-promotion, no AI-asserted trust. A human must run publication review before it becomes trusted Evidence, exactly like every other draft this platform has ever produced.

### 2. Driscoll's negative/reputational press (BM-R-01, R-02, R-04; R-03/R-06 still missed; R-05 was already indirectly covered)

- **Existed before this mission:** No for the PFAS lawsuit (R-01), greenwashing lawsuit (R-02), or Mamavation report (R-04). R-05 (China delisting) had indirect coverage already (Driscoll's own "Responds to U.S. Lawsuits Amid China Market Concerns" article, trade press). R-03 (whistleblower) and R-06 (boycott) remain fully missed after this mission.
- **Why missed:** SOURCE NOT MONITORED for all of them -- Insurance Journal, ClaimDepot, Law360, Mamavation, Lookout Santa Cruz, and general labor/advocacy press had zero source presence.
- **How it is now discovered:** The same generic `source-news-search-driscolls` source, real run: "Mamavation Finds PFAS-Laden Pesticides in Driscoll's Strawberries" (2026-05-12), "Driscoll's accused of failing to disclose PFAS in its strawberries in new class action lawsuit" (Claim Depot, 2026-07-02), "Driscoll's Greenwashes PFAS-Laden Strawberries, Suit Says" (Law360, 2026-07-09), "Berry Producer Driscoll's Sued Over Alleged Greenwashing, Use of Forever Chemicals" (Insurance Journal, 2026-07-21), plus 6 more independent outlets covering the same story cluster (SFGATE, Yahoo x2, inc.com, The Cool Down, AgNet West) -- 10 real articles total on this one reputational cluster. R-03 (whistleblower) and R-06 (boycott) did **not** surface in this query's real ~100-result page -- a concrete, honest limitation: one broad company query does not guarantee every future story type; a labor/legal-press-scoped secondary query would likely be needed (registered as a `DISCOVERY QUERY GAP` in Section 4, not silently assumed solved).
- **Full text or metadata-only:** Metadata-only for every one of the 10 -- none of these outlets' pages were fetched in full; each draft carries only title/publisher/date/URL/description as the discovery feed itself provided.
- **Story Thread behavior:** Tested directly (Section 6) -- 11 real articles across this cluster, all correctly `primary_subject`-resolved to `company-driscolls`, produce **2 genuine same-day multi-source threads** (2026-07-15 pair, 2026-07-27 pair) and **zero false merges** on full manual inspection of all resulting groupings. The 7-day date-proximity window correctly keeps most of the 25-day news cycle separate rather than over-merging an entire multi-week story into one thread -- the conservative behavior the prior Story Thread mission was built to produce.
- **Trust/source-authority handling:** All untrusted drafts, `source_type` inherited from the discovery mechanism (mainstream news search, distinct from `trade_press`/`government_regulatory`/company-newsroom classes already in the source registry -- see the Coverage Matrix). No claim from any of these articles is treated as fact; the existing `does_not_prove`/human-review discipline is unmodified. Mamavation's own lab-testing claims specifically are one step removed -- what's captured is mainstream reporting *about* Mamavation's findings, not a direct feed from Mamavation itself (Mamavation was never onboarded as a source).

### 3. Mexico strawberry antidumping proceeding (BM-T-01 upgraded; T-02/T-03/T-04/T-05 still missed)

- **Existed before this mission:** Partially. One weak trade-press draft already existed (`ev-media-8cc69d52045f750290f7`, "Mexican strawberry industry calls for caution amid US antidumping probe," Fresh Fruit Portal, 2026-08-06) but had never been promoted through review -- a REVIEW BACKLOG condition, not a discovery gap. Zero primary-government-source coverage existed at all (confirmed: zero matches for "antidumping" anywhere in `data/`).
- **Why missed:** No US trade-remedy government source (Federal Register, USITC, Commerce) existed in the registry; the one trade-press draft that did exist sat unreviewed.
- **How it is now discovered:** `source-federal-register-strawberry-antidumping` (new `government_register_json` adapter, Federal Register's real public `documents.json` search API) found 11 real documents and produced 4 real drafts covering the case's actual procedural timeline: Institution of Antidumping Duty Investigation (2026-01-06), Extension of the Adequacy Deadline (2026-01-23), Initiation of the Less-Than-Fair-Value Investigation (2026-02-13), and a Determination (2026-03-12). The August 2026 preliminary determination carrying the specific 3.37-5.28% margins reported in the news was **not** found in this run's Federal Register API results -- either not yet indexed there at run time, or requiring a follow-up query; reported honestly as still missing rather than assumed covered by the mechanism existing.
- **Full text or metadata-only:** Metadata-only for the news-search-found trade article (as above). For the 4 Federal Register documents specifically: title, publisher (agency), date, canonical URL, and the government's own `abstract` field (a real, legitimately-provided summary, not a scrape) -- `federalregister.gov`'s document HTML pages themselves returned a bot-wall to the standard fetch path (live-verified), so no full document text was stored; only what the API itself legitimately serves.
- **Story Thread behavior:** Tested directly and reported as a genuine, unresolved gap (Section 6) -- the 5 real documents (4 Federal Register + the 1 trade article) do **not** thread into one developing story under the current mechanism; they form 5 separate single-member threads, because `_strong_event_edge()`'s 7-day date-proximity window (correctly designed for "same moment, multiple outlets") cannot span this case's real multi-month procedural timeline (January-August 2026). This is registered as new technical debt (`TD-THREAD-003`), not silently claimed solved.
- **Trust/source-authority handling:** All 5 remain untrusted drafts. The 4 Federal Register documents are tagged with a `government_regulatory` source class (the platform's existing, highest-authority source-class distinction) -- the existing source-authority/verification-state model is used as-is; no new trust field or parallel confidence system was created for "government primary source" as a concept.

### 4. Primary government + mainstream/trade coverage relationship

- **What relationship exists today:** All 5 antidumping-related drafts (4 government, 1 trade press) are independently discoverable and correctly co-tagged `berry-strawberry` + `geography-mexico`, but are **not yet connected to each other** by Story Thread (see above) and are **not yet connected to the Driscoll's reputational cluster** either, despite Driscoll's being a real, major party in the US strawberry market this case directly affects -- no benchmark event or discovered draft in this mission established a documented, evidenced link between the antidumping proceeding and any specific named company (the real news coverage found genuinely centers on the Florida-grower petitioners and Mexican exporters generically, not Driscoll's by name, so no false connection was manufactured here).
- **Assessment:** The mission's Section 6 goal (primary documents + mainstream + trade + company entities + geography + berry + procedural status, connected as one relationship) is **partially met** -- entity/geography/berry tagging is real and correct on every individual document, but the cross-document *organizational* relationship (Story Thread) is the piece left open, honestly reported as such rather than asserted.

## 5. What was built (Mainstream News + Regulatory Discovery V1)

All additive; zero existing adapters, sources, or tests were modified in a way that changes prior behavior. Full technical detail: `docs/v2/TECHNICAL-DEBT-REGISTER.md` and the PR description.

1. **`government_register_json` adapter** (`app/services/media_discovery.py`) -- Federal Register's public `documents.json` search API. The **one genuinely new adapter** this mission adds. Federal Register's *RSS* search endpoint was live-verified to return a bot/access-gate HTML page to an ordinary client; the JSON API at the same path returns real results for an identical query and User-Agent, so RSS is not usable here even though it is for every other new source in this mission.
2. **`news_search_rss` adapter** -- Google News RSS search, ported from the existing (older, `app/main.py`-only) keyword-source mechanism into the modern discover -> screen -> acquire -> draft pipeline, so mainstream-press items get real body-aware relevance screening and a human review gate instead of an unreviewed direct write to `data/evidence/`. Recovers real publisher attribution from Google's own `<source>` tag on each entry, mirroring the existing `build_auto_evidence()` precedent exactly.
3. **`always_body_check` override** (`app/services/article_refresh.py`, opt-in per source, wired from `government_regulatory`-tagged sources in `scripts/run_collection.py`) -- a pre-scoped regulatory source's docket-only headline (no berry word) now still gets a real Stage B body read instead of being dropped by Stage A's generic-web metadata gate. Scoped to the source, not a global relevance-screen change.
4. **Paywall/access-limitation fallback** (`app/services/article_refresh.py`) -- when Stage A already independently confirms relevance from title/description alone (a real berry/cultivar name, `TIER_DIRECT`) but the full article body cannot be fetched (paywall, bot-wall, rate limit -- live-verified against `federalregister.gov`'s own document pages, which are JSON-API-accessible but HTML-page-blocked), a metadata-only draft is created instead of the item being dropped. This directly implements Section 9's paywall/copyright discipline generically, not as a Federal-Register-specific hack.
5. **5 new Sources** registered in `data/configuration/sources.json`: 2 Federal Register searches (Mexico strawberry antidumping case-scoped; general 4-berry trade-remedy/phytosanitary/pesticide-scoped), 3 Google News searches (Driscoll's -- generic company monitoring, proven to also require no story-specific hardcoding; Costa Group -- proves the mechanism generalizes to a second company; a topic-scoped "berry antidumping/tariff/trade remedy" query).

**Real discovery runs, not simulated:** all 5 sources were run for real against live networks. Results: Federal Register (antidumping-scoped) found 11 real documents, 4 became drafts (the rest are older/generic notices correctly left unconfirmed without a fetchable body); Federal Register (general) found 20, 1 became a draft; Driscoll's mainstream search found 100 real articles (Google's page cap), 60 became drafts including all 4 of the PFAS/greenwashing/Mamavation required cases and the NYT feature; Costa Group found 49, 12 became drafts; the topic query found 68, 7 became drafts.

## 6. Regulatory discovery V1 -- developing-story status (honest finding)

Section 6 of the mission required the Mexico strawberry antidumping case be represented as a **developing story**, not isolated articles. The discovery layer above successfully finds the real procedural documents (Institution 2026-01-06, Extension 2026-01-23, Initiation of LTFV Investigation 2026-02-13, Determination 2026-03-12, plus a pre-existing trade-press article from 2026-08-06) -- but running `story_threads.group_story_threads()` against all five (with `attribute_draft()`-computed `primary_subject`, exactly as the live app does) produces **five separate single-member threads, not one developing story.**

Root cause, verified by inspection: `_strong_event_edge()` (and the newly-fixed `_cross_subject_event_edge()`) both gate on a narrow date-proximity window (`DATE_PROXIMITY_EVENT_DAYS`, 7 days) designed for "the same real-world moment, reported by multiple outlets within days." A regulatory docket's documents are legitimately months apart (this one spans January-August 2026) -- a fundamentally different clustering shape than "same event, close in time." Widening the date window generically to accommodate this would risk exactly the false-merge regression the two prior Story Thread missions were built to prevent, so **this was not attempted** as part of this mission.

This is reported honestly as **not solved**, not silently claimed as solved: the Mexico strawberry case is discoverable in full (all its known procedural documents are now real drafts, tagged Mexico + Strawberry), but the platform does not yet present it as one organizational developing story. Registered as new technical debt (`TD-THREAD-003`, see the register) rather than buried in this report alone, with a concrete future direction: a docket/case-number-keyed thread identity (e.g. matching on the shared "A-201-869" / "731-TA-1770" case numbers Federal Register's own metadata already carries) is a distinct, narrower mechanism from date-proximity event matching and would need its own scoped mission.

As a contrasting, positive proof point: the Driscoll's PFAS/greenwashing reputational cluster (11 real mainstream articles, 2026-05-12 to 2026-07-27, all correctly `primary_subject`-resolved to `company-driscolls`) **is** the kind of story the existing date-proximity model handles well -- 2 genuine same-day multi-source threads formed (2026-07-15, 2026-07-19/07-15 window; 2026-07-27), zero false merges on manual inspection of all 10 resulting thread groupings, and the 7-day-window/title-overlap requirement correctly kept most of the 25-day span separate rather than over-merging an entire multi-week news cycle into one thread.

## 7. Paywall/copyright discipline

No paywall was bypassed. The NYT article was never fetched (Claude Code's own tooling refused the domain outright); its existence, title, author, date, and publication venue were confirmed only via third-party secondary reporting and search results, exactly the "metadata/discovery-only" posture Section 9 requires. Federal Register's document pages returned a bot-wall to the standard fetch path -- rather than working around that block, the fallback in Section 5.4 stores only the government API's own legitimately-provided title/abstract/date/URL, never a scraped or reconstructed full text. No full article text was stored for any paywalled or access-limited source in this mission.

## 8. Largest remaining coverage gap

**Commercial/Market intelligence (0% recall in this benchmark) and Regulatory/Trade beyond the one proceeding this mission targeted.** Every Commercial/Market miss in this set is a *specific statistic or promotion* (an export percentage, a production forecast, a retailer price point) rather than a named entity or company -- the kind of fact that lives in trade-data services (Tendata, USDA FAS, IndexBox) this platform doesn't yet ingest at all, distinct from the news-discovery mechanism built this mission. This lines up with the Expansion Build Guide's own Workstream G (Quantitative Corroboration / customs-trade data) as the next logical lane for this specific gap, rather than more news-source expansion.

## 9. Repeating this benchmark

To re-run: (1) refresh or extend the event set in Part 2 with newly-researched real events (do not remove old ones -- the set should grow, and old events becoming stale/resolved is itself a useful longitudinal signal); (2) re-run each event's keyword search against current `data/evidence/` and `inbox/evidence/`, then **manually verify every candidate match is the same event**, not the same topic (Section 1's finding on keyword-match inflation applies to any future re-run too); (3) recompute the tables in Part 3; (4) update the Coverage Matrix and Technical Debt Register with whatever the new root causes are.

## 10. Global Qualitative Coverage Expansion V1 re-run (2026-08-21)

Full detail: `docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V1.md`. This mission re-confirmed the baseline above was unchanged (no qualitative source ran between the two missions), then added 14 new bounded, reusable-query Sources (Spanish/French geography-scoped searches, a UK retailer-class query, topic-only investment/labor-risk queries, and a new `government_recall_json` adapter against openFDA) targeting exactly this benchmark's own weakest classes and geographies (Section 8's "largest remaining coverage gap" call-out, Commercial/Market, was directly targeted this time, unlike this mission's own prior scope note that it belonged to a future quantitative-data lane -- discovery-side coverage and quantitative trade-data coverage turned out to be complementary, not substitutes: Trade Intelligence V1 handles the *statistics*, this mission handles the *qualitative* corporate/promotion/regulatory-response stories Section 8 also named).

**Overall: 15/50 (30%) -> 26/50 (52%).** 10 events moved MISSED -> CAPTURED (draft), 1 more to CAPTURED INDIRECTLY:

| ID | Event | New "After" state |
|---|---|---|
| BM-C-05 | Colombia seeks foreign blueberry investment | CAPTURED (draft) |
| BM-M-01 | Sainsbury's GBP1 British Strawberry promotion | CAPTURED (draft) |
| BM-M-05 | South Africa blueberry production reaches 38,900t | CAPTURED (draft) |
| BM-M-07 | Twin River Berries expands MX/Peru/Chile raspberry production | CAPTURED INDIRECTLY (real SanLucar/Twin River stake-acquisition coverage found, not the identical MX/Peru/Chile production article) |
| BM-R-07 | FDA/CDC E. coli O145:H28 frozen blueberries outbreak | CAPTURED (draft) |
| BM-R-08 | Listeria recall, Oregon Potato Co. frozen blueberries | CAPTURED (draft) |
| BM-R-12 | ProPublica: "Do My Grocery Store Blueberries..." investigation | CAPTURED (draft) |
| BM-T-02 | Commerce preliminary determination, margins 3.37-5.28% | CAPTURED (draft) |
| BM-T-03 | Mexico's Ministry of Economy formally protests ruling | CAPTURED (draft) |
| BM-T-09 | South Africa granted US blueberry market access | CAPTURED (draft) |
| BM-T-10 | Chile-Morocco market-access ties strengthen | CAPTURED (draft) |

**BM-M-04** (Peru turns to China as US tariffs squeeze exports) stays classified **MISSED** despite real, generic re-discovery this mission (via the pre-existing `source-news-search-berry-trade-remedy` source) -- the resulting draft turned out to be an exact-title duplicate of an already-**trusted, published** record (`ev-20260806173901-86de-...`, predating this mission), one of 16 such duplicates `build_static.py`'s own leak self-check surfaced and this mission removed as untracked-inbox cleanup (the same precedent PR #14 established). It is real proof the discovery mechanism works for a Peru commercial event, but is not counted as newly-moved: Peru's own recall stays at its 10% baseline this mission, an honest result, not rounded up. Full detail: `docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V1.md` Sections 9-10.

Real, honest non-movers worth naming: BM-C-04 (Unifrutti/AvoAmerica Peru) and BM-R-10 (Bloomberg Law Michigan trafficking case) were both generically DISCOVERED by this mission's new sources but screened irrelevant before a body fetch -- their title/description metadata carries no berry species word even though the underlying story is berry-relevant. Registered as `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-040, not hidden inside the aggregate recall number.

## 11. Global Qualitative Coverage Expansion V2 re-run (2026-08-22)

Full detail: `docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V2.md`. This mission re-confirmed Round 1's own 26/50 (52%) baseline was unchanged (no qualitative source ran between the two missions -- Variety Intelligence UI V1 and the Learner Mode roadmap integration both touched product/documentation surfaces only), then processed a much larger share of Round 1's own real discovery backlog (823 items had remained unprocessed, correctly staged not dropped) alongside 4 new bounded, reusable-query sources (a new UK Food Standards Agency `government_alert_json` adapter, and 3 Google News queries -- Peru organic-investment, UK grower-season-launch, USDA-GAIN-report Mexico).

**Overall: 26/50 (52%) -> 30/50 (60%).** 4 more events moved MISSED -> CAPTURED (draft):

| ID | Event | New "After" state |
|---|---|---|
| BM-C-08 | NuBerry Farms organic blueberry investment, Peru | CAPTURED (draft) -- Produce News, the exact benchmark-cited publisher, found via a geography+topic query ("Peru organic blueberry expands OR invests"), never searching for "NuBerry" |
| BM-C-13 | Hall Hunter Partnership launches 2026 UK season | CAPTURED (draft) -- Fruitnet's "Hall Hunter kicks off British blueberry season" (2026-06-16), a different real publisher than the benchmark's own cited Inside Food & Drink, found via an event-concept query ("UK ... grower launches OR kicks off season"), never searching for "Hall Hunter" |
| BM-M-03 | Peru blueberry production +25% to 400,000t forecast | CAPTURED (draft) -- "Las exportaciones de arandanos superarian las 400,000 toneladas este ano" (Agencia Andina), found via the existing Round 1 Spanish-language Peru query, sitting unprocessed in the backlog |
| BM-R-10 | First Pick Farms MI forced-labor lawsuit settled | CAPTURED (draft) -- resolves Round 1's own TD-040 case: MLive's "Lawsuit accusing West Michigan blueberry farm of trafficking workers ends in settlement" (2026-07-09) contains the word "blueberry" in its own title, unlike the Bloomberg Law News version Round 1 found and lost to relevance screening; both are real coverage of the identical real settlement |

**BM-C-04** (Unifrutti/AvoAmerica Peru) stays classified **MISSED**, despite a real, better-titled alternate article existing ("Unifrutti buys two Peruvian suppliers to boost blueberry and avocado supply", Fruitnet, live-confirmed by hand) -- this mission's generic queries did not reliably surface that specific article, only the metadata-thin PR Newswire version already known from Round 1. Registered as `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-045 (a partial, not reliable, mitigation of TD-040).

**A real, larger-scale duplicate cleanup was required this round**: processing a much larger real batch (600+ items, spanning both the Round 1 backlog and the 4 new sources) surfaced 57 drafts whose title exact-matched an already-**trusted, published** record -- the same structural gap as Round 1's 16-item cleanup (`find_duplicate_article()`'s same-source_id requirement), now confirmed to scale with processing volume, not a one-off. All 57 removed as untracked-inbox cleanup before computing the numbers above; none of the 4 real captures above were among them. Registered as `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-046.
