# Intelligence Coverage Matrix

Living **coverage-control** document for
`docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`. Counts come from committed
records and `data/configuration/sources.json`. This is not marketing.

**Do not fabricate coverage.** If a class is empty, write `NONE`.
If a class is blueberry-only with a live pipeline elsewhere, write `PILOT`.
Update this file when sources, entities, or trusted evidence change.

**As-of:** 2026-08-26 · published Evidence `1,266` · Sources `198` · inbox
drafts are runtime-only and noted separately. Source-path counts were refreshed
by Direct Source Upgrade + Coverage Gap Closure V1; trusted Evidence maturity
cells were not promoted because that mission made no trust decisions.

Maturity labels (guide vocabulary):

| Label | Meaning |
|---|---|
| `NONE` | Zero trusted records and no dedicated source class in the corpus |
| `PILOT` | Few trusted records, one berry only, and/or unpublished pipeline only |
| `PARTIAL` | Real trusted records on more than one berry, still thin vs blueberry |
| `OPERATIONAL` | Material trusted corpus used in Live Intelligence / Company / Brief |
| `STRONG` | Not used yet. Requires a recall-benchmarked class, not volume alone |

Berry assignment uses **explicit `berry_ids`**. `299` published `news_search`
records have empty `berry_ids` (untagged mainstream news) as of Evidence
Berry Tagging Backfill V1 (2026-08-22), down from 574 -- 275 records were
deterministically backfilled from their own title/summary text using a
word-boundary-safe matcher (`app/services/deterministic_tagging.py`), never
fetching article bodies or touching trust/status. The remaining 299 are
correctly left untagged: their title/summary names no single species (a
company-wide/category mention, e.g. "Room for Berry Category Growth") or is
off-topic to the source's own "berry" bucket. They are counted in Mainstream
news as untagged, not invented into a berry. Full detail:
`docs/v2/EVIDENCE-BERRY-TAGGING-BACKFILL-V1.md`.

Seed fixtures (`ev-sample-patent-published`, `ev-sample-retail-placement`,
`ev-sample-variety-launch`) exist in `data/evidence/`. Landscape excludes them.
The raspberry published-patent cell notes the seed row.

---

## Entity depth (knowledge graph)

| Entity | Total | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|---:|
| Companies | 49 | 36 | 11 | 12 | 7 |
| Varieties | 60 | 41 | 6 | 12 | 1 |
| Breeding programs | 12 | 9 | 3 | 1 | 0 |
| Retailers | 8 | -- | -- | -- | -- |

Raspberry Vertical V1 (PR #49) added real raspberry companies/varieties
(Wish Farms, Global Plant Genetics, James Hutton Ltd, Chambers, Berrytech,
Cornell raspberry releases, Advanced Berry Breeding cultivars). Variety
Intelligence Backbone V1 (2026-08-21) added 2 real, multi-source-confirmed
varieties (Zara/strawberry, Victoria/blackberry -- **blackberry's first
variety entity**) and 6 real UK retailers (Tesco, Sainsbury's, Waitrose,
M&S, Morrisons, Asda) for the retail-observation pilot. Blackberry still
has **no breeding-program entity**.

Geography entities on disk (19): Australia, Canada, Chile, China, Colombia,
Europe, Germany, Mexico, Morocco, Netherlands, North America, Peru, Portugal,
South Africa, Spain, **United Kingdom** (added 2026-08-21 -- a real gap: the
platform's own first retail-observation pilot market had no Geography
entity until this mission), United States, Zambia, Zimbabwe.

---

## Trusted evidence by berry × intelligence class

Published `data/evidence/*.json` only. Multi-berry records increment each
tagged berry. Inbox drafts are **not** added to these cells.

| Class | Blueberry | Strawberry | Raspberry | Blackberry | Untagged | Maturity |
|---|---:|---:|---:|---:|---:|---|
| Company / breeder | 50 | 1 | 0 | 0 | 0 | OPERATIONAL (blue) / PILOT (strawberry) / NONE (rasp, black) |
| Trade press | 19 | 0 | 0 | 0 | 0 | PILOT |
| Mainstream news | 549 | 364 | 217 | 166 | 299 | **PARTIAL — now recall-benchmarked (see below); volume does not mean recall. Backfilled 2026-08-22, see Evidence Berry Tagging Backfill V1** |
| Association | 6 | 0 | 0 | 0 | 0 | PILOT |
| Regulatory / government | 1 | 0 | 0 | 0 | 0 | PILOT — 2 new sources added, still US-only, still not developing-story-threaded (TD-THREAD-003) |
| Patent | 23 | 1 | 1* | 0 | 0 | OPERATIONAL (blue) / PILOT (pipeline) |
| PVR / variety registry | 16 | 0 | 0 | 0 | 0 | PILOT -> **PARTIAL** — 28 real CPVO EU filings found (blue/straw/rasp), still all untrusted drafts pending review, not yet reflected in this published-only table (see below) |
| Podcast / video | 1 | 0 | 0 | 0 | 0 | PILOT |
| Insider newsletter | 3 | 0 | 0 | 0 | 0 | PILOT |
| Retail observation | 1 | 0 | 0 | 0 | 0 | PILOT — 18 real UK draft observations added (see below), still 1 published (the fictional seed; Landscape already excludes it) |
| Social | 0 | 0 | 0 | 0 | 0 | NONE |
| Careers / jobs | 0 | 0 | 0 | 0 | 0 | NONE |
| Conferences / events | 0 | 0 | 0 | 0 | 0 | NONE |
| Customs / trade | 0 | 0 | 0 | 0 | 0 | NONE -> **PILOT** -- 6 real quantitative trade-flow lanes (untrusted drafts, see below); published count stays 0 until human review |
| Weather | 0 | 0 | 0 | 0 | 0 | NONE -> **PILOT** -- 5 real production-region weather observations (untrusted drafts, see below); published count stays 0 until human review |
| Satellite | 0 | 0 | 0 | 0 | 0 | NONE |

\*Raspberry published Patent = `ev-sample-patent-published` (system seed).
**Zero real published raspberry patents.** Strawberry published Patent is the
Driscoll's v. CBC Federal Circuit order (`court_record`), not a plant patent grant.

Two published ownership-transaction records use
`private_equity_press_release` / `development_finance_press_release` and are
not in the class table (`ev-cinven-planasa-ew-group`, `ev-hortifrut-psp`
family). They support the unscoped capital Assessment; they are not a
coverage class.

Class mapping is from stored `source_type` / `media_format` (see
`app/services/intelligence_feed.py` kind rules and this matrix's inventory
script). `news_search` → Mainstream news. `patent_record` / `court_record` →
Patent. `plant_breeders_rights_record` / `government_registry` /
`licensing_body_website` → PVR. `field_observation` → Retail observation.
Company websites, catalogs, press releases, and research-program publications
→ Company / breeder.

---

## Inbox pipeline (unpublished, not coverage)

Runtime `inbox/evidence/` is gitignored. On the machine that last inventoried
it: patent-monitor drafts were the bulk of unpublished patents (strawberry +
raspberry), plus a handful of podcast drafts. **Do not treat inbox counts as
committed coverage.** They prove a collector class exists, not that the
vertical is production.

---

## Source configuration (intent, not corpus)

`data/configuration/sources.json`: **196** Sources as of Direct Source Upgrade
+ Coverage Gap Closure V1 (2026-08-25).

| `type` | Count |
|---|---:|
| `reference` | 131 |
| `keyword` | 33 |
| `rss` | 32 |

`discovery.adapter` is present on 75 Sources: `article_rss` 33,
`news_search_rss` 22, `podcast_rss` 8, `youtube_feed` 4, `sitemap_xml` 3,
`government_register_json` 2, and one each of `government_recall_json`,
`government_alert_json`, and `sec_edgar_search_json`. Growing Produce remains
configured but fetch-ineligible / `OPERATOR_ACTION_REQUIRED`, so 74 are
collection-eligible.

Keyword monitors (33, the older `app/main.py` pipeline) drive the Mainstream
news auto-capture that dominates strawberry / raspberry / blackberry
published counts. That is **keyword-news volume**, not company-page or PVR
coverage. The 3 new `news_search_rss` sources are a *different* mechanism
(same underlying Google News RSS technique, but run through the modern
discover -> screen -> acquire -> draft pipeline instead, so items get
body-aware relevance screening and sit in `inbox/evidence/` for human review
rather than writing straight to `data/evidence/` as `validated: false`).

---

## Mainstream News + Regulatory recall benchmark (2026-08-21)

The volume/maturity table above answers "how much mainstream-tagged
Evidence exists"; it does not answer "does the platform actually catch
important mainstream/regulatory stories." `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`
answers that directly, against a 50-event benchmark spanning all 4 berries
and 5 intelligence classes, built from live external research rather than
selected because the OS already contained the events.

**Overall event-level recall: 11/50 (22%) -> 15/50 (30%) -> 26/50 (52%) ->
30/50 (60%) after the Global Qualitative Coverage Expansion V2 mission
(2026-08-22) -> 31/50 (62%) after Relevance Screen Boundary V1
(2026-08-23) -> 33/50 (66%) after Unknown-Event Discovery + Query
Coverage V3 (2026-08-23)**, all newly-captured events sitting as untrusted drafts
pending human review (the trust gate is untouched by this mission). Recall
by class: Commercial/Market 0%->50% (4/8), Regulatory/Trade 9%->45% (5/11,
unchanged this round), Corporate 38%->61.5% (8/13), Reputation/Risk
33%->67% (8/12), Genetics/Varieties unchanged at 83% (no genetics-specific
source added). By berry: Blueberry 23%->58% (18/31 -- all 4 of this
round's real captures are blueberry events); Strawberry/Raspberry/
Blackberry unchanged this round. Of the weak geographies named in the
original mission brief: Chile 0%->20%, Morocco 0%->33%, South Africa
0%->100% (2/2) (all unchanged since Round 1); **UK 33%->67%** (Hall
Hunter's season-launch event, a real new capture); **Peru 10%->30%** (two
real new captures -- NuBerry's investment and the 400,000t export
forecast -- moving Peru for the first time since the original benchmark).
Full detail, the source-gap map, and honest inbox-quality accounting:
`docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V2.md` (Round 1:
`docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V1.md`).

**Per the maturity legend above, this is the real basis for marking
Mainstream News PARTIAL (not OPERATIONAL) and Regulatory/Government PILOT:
a large keyword-news corpus and government sources exist, and measured
event-level recall materially improved across two consecutive missions,
but real, self-identified limitations keep this below OPERATIONAL** -- (1)
discovery reaching an event does not guarantee relevance-screening
recognizes it (BM-C-04/Unifrutti remains blocked this way even after a
second attempt -- TD-040, TD-045); (2) most discovered items across both
missions' 18 sources remain unprocessed, correctly staged rather than
dropped, per the existing no-recurring-collection condition (TD-008); (3)
processing a real backlog at scale reliably surfaces cross-pipeline
duplicates of already-trusted content that must be found and removed by
hand before counting (57 in Round 2 alone, TD-046).

Full methodology, the event table, root-cause distribution, and the 4
required Driscoll's/antidumping acceptance cases' individual detail are in
`docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md` -- this section is a pointer and
summary, not a duplicate of it; update the benchmark doc first on any
future re-run and update this pointer's numbers to match.

---

## Geography (where evidence actually stores `geography_ids`)

| Class | Stored geography? | Notes |
|---|---|---|
| Mainstream news | Yes — 16 geography entities | Top tags include Mexico, Morocco, Peru, Spain, China, Chile, Netherlands |
| Company / breeder | Rare | Most records omit `geography_ids` |
| Patent / PVR / Trade press / Association | Rare or none | Source `region_coverage` is not copied onto Evidence |

Weather / customs / trade **stories** appear inside Mainstream news (for
example Morocco weather coverage). They are not a dedicated intelligence class.

---

## What this matrix does **not** claim

- Raspberry/blackberry company entities ≠ raspberry/blackberry Company-class
  Evidence. The graph is ahead of the corpus for those berries.
- Configuring a Source is not coverage until trusted Evidence exists.
- Signal candidates, Assessments (5 records, 4 blueberry-scoped, 1 unscoped),
  and Recommendations are interpretation objects, not source coverage.

Governing program: `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`.
Keep this file as the numeric control surface. Do not copy aspiration into
the cells. **Mainstream News + Regulatory Recall Benchmark V1 completed
2026-08-21** (`docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`); see that mission's
own report for its next-lane recommendation.

A withdrawn expansion-guide-session draft marked Mainstream news `NONE`
across all berries (treating keyword-news as a non-class). This file still
does **not** adopt that cell -- `574` untagged plus per-berry `news_search`
counts are real trusted Evidence, real volume. But the Recall Benchmark
mission (above) measured actual event-level recall against that volume for
the first time and found it well short of comprehensive (11/50 -> 15/50
across the full benchmark; 9%-38% by class excluding Genetics) -- the
correct, now-evidenced label is `PARTIAL`, not `OPERATIONAL`, until a
future re-run of that benchmark shows otherwise.

---

## Source berry tags (configuration intent)

`data/configuration/sources.json` (196 Sources as of Direct Source Upgrade +
Coverage Gap Closure V1, 2026-08-25). A tagged Source is not coverage until
trusted Evidence exists.

| | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|
| Total tagged Sources | 135 | 102 | 96 | 97 |
| Discoverable (`discovery.adapter`) | 63 | 45 | 44 | 43 |

Three discoverable Sources are berry-unscoped (Blue Book Services, HortiDaily,
SanLucar Newsroom). Growing Produce remains explicitly blocked rather than
bypassed. See the mission section below for direct-path gaps that were
re-verified but deliberately not onboarded.

---

## Source `region_coverage` (intent, not Evidence geography)

| Region | Sources tagged |
|---|---:|
| Global | 86 |
| North America | 76 |
| South America | 33 |
| Europe | 33 |
| Asia-Pacific | 16 |
| Africa | 11 |

This is registry intent. Evidence-level geography is the table above
(`geography_ids` on records). No Asian domestic-market first-party breeder
source is onboarded.

---

## Patent Monitor recall (last measured 2026-08-20)

Google Patents JSON provider, per-berry `plant_named` query. Watchlist is
symmetric; curation is not.

| | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|
| Provider hits (most recent real run) | 55 | 80 | 26 | 15 |
| Kept (per-query cap) | 15 | 15 | 15 | 15 |
| Trusted patent **entities** curated | 37 | 0 | 0 | 0 |

Strawberry / raspberry / blackberry have real linked drafts in runtime
inbox; those are unpublished and are not coverage. See TD-REVIEW-001.

---

## Variety Intelligence Backbone (2026-08-21)

Full detail, methodology, and real query proof: `docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md`. This section is the numeric control-surface pointer, not a duplicate.

**Variety Knowledge — PARTIAL.** Identity contract (canonical name / commercial name / breeder code / PVR denomination, all via existing `name`+`aliases[]`, no schema change) proven with real data: 132 real CPVO queries against all 58 pre-mission variety names+aliases produced 28 real matches and **zero duplicate Variety entities created** — every match resolved to an existing id via the existing (already-generic) `entity_link.py` matcher. Ownership/rights model proven to separate breeder/owner/marketer without collapsing (`variety-drisblueseventeen`: real `develops` + real `owns`, same evidence, two distinct facts; `markets` added to the relationship schema enum after a real disclaimed-substitution case). Deep for blueberry (20+ competing varieties across 6 real companies via `competing_varieties_in_berry_market()`), genuinely thin for blackberry (1 variety, 0 rights filings, reported as such — not padded).

**PVR / Registry — PILOT -> PARTIAL.** Global audit (US/UPOV/CPVO/UK/Australia + 6 named country candidates, `docs/v2/VARIETY-INTELLIGENCE-BACKBONE.md` Part 4) found only one cleanly-public, unauthenticated, working API: CPVO's real public register (`online.plantvarieties.eu`) — UPOV PLUTO and the CPVO "Variety Finder" aggregator are both account-gated; IP Australia PBR has a public web UI but no discoverable API; UK PVRO has no unified public database at all. Integrated: `app/services/cpvo_registry.py` + `scripts/monitor_cpvo_registry.py`, real run = 28 real EU filings across blueberry/strawberry/raspberry (zero blackberry), all untrusted drafts, idempotent on a real second run (28 duplicates, 0 new). Not `OPERATIONAL`: single jurisdiction (EU only), no US+EU combined view yet, no developing-story threading of a variety's filing history.

**Retail / Commercial Observations — PILOT.** New additive `commercial_observation` Evidence object (schema, not a new entity type or parallel trust system). UK retail research across Tesco/Sainsbury's/Waitrose/M&S/Morrisons/Asda found variety-name exposure is genuinely rare (16 of 18 real observations correctly recorded no variety — own-label listings do not name cultivars; only 2 premium/named lines did: Driscoll's Zara, Driscoll's Victoria). 18 real observations captured (via Open Food Facts, a public open-licensed product database mirroring real retailer listings — not direct retailer scraping), all untrusted drafts. Not `OPERATIONAL`: one market (UK), one real acquisition mechanism proven at small scale, no automated/recurring collection.

---

## Global Trade / Customs Intelligence (2026-08-21)

Full detail, methodology, and real query proof: `docs/v2/TRADE-INTELLIGENCE-V1.md`. This section is the numeric control-surface pointer, not a duplicate.

**Customs / Trade — NONE -> PILOT.** Source audit (US Census, UN Comtrade, USDA/FAS, Eurostat, UK HMRC, national Mexico/Peru/Chile sources, Agronometrics-as-secondary-only) found UN Comtrade's keyless public preview API is the only source that is simultaneously official, unauthenticated, and live-verified working; integrated as this mission's one adapter (`app/services/trade_intelligence.py` + `scripts/monitor_trade_intelligence.py`). Real pilot: 6 lanes (US<-Mexico strawberry, US<-Peru blueberry, US<-Chile blueberry, UK<-Morocco blueberry, UK<-South Africa blueberry, US<-Mexico raspberry+blackberry combined), 12 months each (2025-01..06 + 2026-01..06 for real year-over-year comparability), all untrusted `inbox/evidence/` drafts, idempotent on a real second run (6/6 duplicates, 0 new). Real derived-metric findings: a 36.4%/56.2% (qty/value) YoY decline in US strawberry imports from Mexico in 2026-04, following the real Federal Register antidumping "Determination" by about a month (a real, proposed-only `follows_up` evidence_link was added, not auto-accepted); a sharp Chile-vs-Peru divergence in US blueberry imports (Chile -76.1% qty YoY in 2026-03 vs. Peru +33.1%); real volatility in the much-smaller Morocco/South Africa-to-UK lanes.

**Berry/HS honesty**: strawberry is cleanly HS-separable (fresh 081010, frozen 081110); raspberry and blackberry are **never separable** in official 6-digit HS data (combined at 081020/081120); blueberry shares its fresh code with cranberries/other *Vaccinium* (081040) and its frozen code is a generic "other fruit" basket (081190) not blueberry-specific at all. Every affected draft is tagged `berry_code_purity: "multi_berry_combined"` and states the limitation in `does_not_prove` directly.

Not `OPERATIONAL`: one adapter (UN Comtrade, 6-digit HS only), 7 geographies (the pilot's own required set, not a general lookup), no revision/resubmission handling, an unresolved US Census API-key gap that would add 10-digit granularity. See `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-024 through TD-029.

---

## Weather / Climate Context (2026-08-21)

Full detail, methodology, and real query proof: `docs/v2/WEATHER-CLIMATE-CONTEXT-V1.md`. This section is the numeric control-surface pointer, not a duplicate.

**Weather / Climate — NONE -> PILOT.** Source audit (NOAA CDO, ERA5/Copernicus CDS, USDA climate/drought products, NASA POWER) found NASA POWER's keyless public daily point API is the only source that is simultaneously global, unauthenticated, and live-verified working (NOAA CDO and ERA5/CDS both require a self-registered account/token, the same access-barrier pattern as Trade Intelligence V1's US Census gap); integrated as this mission's one adapter (`app/services/weather_intelligence.py` + `scripts/monitor_weather_intelligence.py`). Real pilot: 5 production regions (Chile-Maule blueberry, Peru-La Libertad blueberry, South Africa-Western Cape blueberry, Morocco-Gharb/Loukkos blueberry, Mexico-Michoacan/Guanajuato strawberry), each a real daily series (2025-01..2026-06) plus a compact 10-year (2015-2024) climatological baseline, all untrusted `inbox/evidence/` drafts, idempotent on a real second run (5/5 duplicates, 0 new).

**Real corroboration findings** (via `weather_context_for_trade_anomaly()` against Trade Intelligence V1's own real trade-anomaly periods): Chile's real -42.0%/-76.1% (Feb/Mar) YoY US blueberry export decline overlaps a real 3-day extreme-heat run (2025-12-29..31, +7.18C above baseline) roughly 8-13 weeks earlier, plus March precipitation at ~363% of the climatological baseline (heavy rain during a blueberry harvest window is a real, documented volume/quality risk) -- one real, proposed-only `corroborates` evidence_link was added from the weather draft to the Chile trade draft, not auto-accepted. South Africa's real -84.4% (Feb) decline has **no matching precipitation/frost/heat anomaly in its own window** -- reported honestly as no meaningful weather explanation found, not forced; a real extreme-heat run (2026-03-09..15, +8.61C) does overlap the +68.5% March recovery, noted as a real, honest observation without claiming it caused the rebound. Mexico's real regulatory-driven strawberry decline (already explained by the antidumping Determination in Trade Intelligence V1) was used as a **control**: no precipitation or frost anomaly was found in its window either, correctly demonstrating the system does not manufacture a weather narrative when a regulatory one already exists. Peru's real +10.3%/+33.1% growth also overlaps precipitation ~376-392% above baseline -- reported as a real, honest complexity (the same weather-condition type, excess precipitation, appears alongside both a decline in one country and growth in another), explicitly not treated as evidence that rain helps or hurts blueberry supply in general.

**Leading-indicator finding**: Chile's real December heat anomaly ended 59 real days before the Feb trade period's month-end and 90 real days before the March period's month-end -- a genuine, honestly-computed lead time, not a forecast claim (`leading_indicator_lead_time()`, a simple calendar calculation, conservative vs. Comtrade's real publication lag).

**Interpretation-risk finding**: this pilot's own bidirectional `unusual_temperature_window()` check, at default thresholds, flagged all 7 real test windows including Peru's growth cases and the Mexico control -- too low-specificity to feature as evidence; this mission's own findings above rely only on the more discriminating `extreme_heat_event`/`precipitation_deficit`/`precipitation_excess` functions (see TD-035).

Not `OPERATIONAL`: one adapter (NASA POWER, ~50km grid), 5 piloted production regions (4 more documented in config but not queried), a 10-year pragmatic baseline (not a 30-year climate normal), no revision/backfill handling for near-real-time dates. See `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-030 through TD-037.

---

## Global Qualitative Coverage Expansion (2026-08-21)

Full detail, methodology, source-gap map, and honest inbox-quality accounting: `docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V1.md`. This section is the numeric control-surface pointer, not a duplicate.

**Baseline re-confirmed, not re-derived from scratch.** No mainstream/regulatory source or acquisition ran between the Recall Benchmark V1 mission and this one (Variety Backbone, Trade, and Weather all added structured quantitative/registry data, never qualitative news sources), so the prior benchmark's own "after" state (15/50 = 30%) was mechanically unchanged and confirmed via file-timestamp/count evidence rather than re-run by hand.

**14 new Sources added** (`data/configuration/sources.json`, 150 -> 164), all bounded, reusable QUERY PATTERNS rather than one Source per benchmark URL: 13 Google News `news_search_rss` searches (Spanish-language Peru/Chile/Mexico, French-language Morocco, an English UK-growers query, a UK major-supermarket retailer-class query, South Africa production + trade queries, a Chile-Morocco trade-access query, two topic-only investment/acquisition queries, one labor/legal-risk topic query, a Spanish Spain query) and 1 new **`government_recall_json`** adapter (`app/services/media_discovery.py`) against openFDA's real, keyless food-enforcement/recall API. NOAA CDO and CFIA (Canada) were audited but not integrated (credential/search-capability gaps -- TD-036, TD-041).

**Real, generic acceptance-case proof (no headline hardcoding)**: every one of the 8 required categories was satisfied by a query that does not name the specific benchmark event -- Peru commercial (BM-M-04, via a Chile/Peru trade-tariff query -- proved the mechanism works, but the resulting draft duplicated an already-trusted record and was not counted for recall credit, see below), Chile (BM-T-10, via a Chile-Morocco market-access query), UK (BM-M-01, via a 4-retailer query), Morocco (same BM-T-10 article, both geographies), South Africa (BM-M-05 and BM-T-09, via production/market-access queries), food-safety (BM-R-07 E. coli and BM-R-08 Listeria, via a generic openFDA product-description search), acquisition/investment (BM-C-05 Colombia, via a topic-only query -- the mission's own named example, Unifrutti/BM-C-04, was discovered by the same mechanism but screened irrelevant, an honest finding not a hidden failure -- TD-040), regulatory/trade-response (BM-T-02/T-03/T-09/T-10, several). **10 benchmark events moved MISSED -> CAPTURED (draft); 1 more (BM-M-07) moved to CAPTURED INDIRECTLY.**

**Two real self-caught corrections, both fixed/handled in the course of this work, not merely reported**: (1) a load-bearing bug -- cross-pipeline duplicate detection stripped every URL's query string, which silently collapsed every distinct openFDA recall (identical path, different `?search=...` query) onto the first one processed; fixed in `article_dedup.normalize_canonical_url()`, regression-tested (TD-038, status `fixed`). (2) A real cross-pipeline duplicate cluster -- `build_static.py`'s own leak self-check surfaced 16 new drafts (including the Peru BM-M-04 one) sharing an exact title with an already-trusted record, the same structural gap the earlier PR #14 mission documented; removed as untracked-inbox cleanup per that same precedent, and excluded from the recall count rather than double-counted.

**Inbox quality, real measured numbers**: 1078 items discovered across the 14 new sources; 255 processed (23.7%) within this mission's bounded real-run window; of those, 180 (70.6%) passed relevance screening (164 net after the 16-item duplicate cleanup above), 53 (20.8%) were correctly screened irrelevant, 22 (8.6%) borderline. The irrelevant rate is in line with the prior Recall Benchmark mission's own 26% baseline -- this expansion did not degrade inbox quality. A random 25-item manual sample found zero noise; the only confirmed false-positive class across the full new-draft set (3 items) is the pre-existing, already-tracked "Berry Global"/packaging-company ambiguity (TD-015/TD-ACQ-006 precedent), not a new problem.

Not `OPERATIONAL`: relevance-screening can still miss a generically-discovered event when its metadata is thin (TD-040, Codex-coordination item); 823 of 1078 discovered items remain unprocessed, correctly staged (TD-008, no recurring collection yet); Google News RSS results are not fully deterministic request-to-request (TD-039); CFIA/Canada food-safety and several secondary geographies (California/Pacific Northwest/broader EU) remain unaddressed. See `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-038 through TD-042.

---

## Global Qualitative Coverage Expansion V2 (2026-08-22)

Full detail: `docs/v2/GLOBAL-QUALITATIVE-COVERAGE-EXPANSION-V2.md`. This section is the numeric control-surface pointer, not a duplicate.

**Baseline re-confirmed**: fetched canonical fresh at mission start; Round 1's own 26/50 (52%) state was mechanically unchanged (Variety Intelligence UI V1 and the Learner Mode roadmap integration, the two missions that landed since, touched product/documentation surfaces only).

**Two real, complementary improvements**: (1) processed a much larger share of Round 1's own real discovery backlog (up to 700 items per source class this time, vs. up to ~20 in Round 1's bounded first pass) -- a real, sitting-in-inbox Spanish-language Peru capture (BM-M-03) and other content surfaced purely from processing more of what was *already discovered*, no new source needed. (2) **4 new bounded, reusable-query sources added** (`data/configuration/sources.json`, 164 -> 168): a new **`government_alert_json`** adapter (`app/services/media_discovery.py`) against the UK Food Standards Agency's real, keyless food-alerts API -- a second, distinct authoritative food-safety jurisdiction alongside Round 1's openFDA -- plus 3 Google News queries (Peru organic-investment, UK grower-season-launch, USDA-GAIN-report Mexico), each chosen as a reusable geography/event-concept pattern, not a company name.

**4 real events moved MISSED -> CAPTURED (draft)**: BM-C-08 (NuBerry Peru investment, via the Peru-organic-investment query), BM-C-13 (Hall Hunter UK season launch, via the UK-grower-season query -- a different real publisher, Fruitnet, than the benchmark's own cited Inside Food & Drink), BM-M-03 (Peru 400,000t export forecast, Spanish-language, from the Round 1 backlog), BM-R-10 (Michigan blueberry-farm trafficking settlement -- **resolves Round 1's own TD-040 case**, via a differently-titled article, MLive's, that contains the word "blueberry" where the Bloomberg Law version Round 1 found did not). BM-C-04 (Unifrutti) stays MISSED -- a real, better-titled alternate article exists (Fruitnet) but this mission's queries did not reliably surface it (TD-045).

**Real, larger-scale duplicate cleanup**: processing ~600+ items surfaced 57 cross-pipeline duplicates of already-trusted content (the same structural gap as Round 1's 16, now confirmed to scale with volume -- TD-046); all removed before computing the results above.

**Inbox quality, real measured cumulative numbers** (across all 18 mainstream/regulatory sources from both rounds): 1317 items discovered, 863 processed (65.5%), 561 passed relevance screening (65.0% of processed), 229 correctly screened irrelevant (26.5%, essentially identical to the original Recall Benchmark mission's own 26% baseline), 73 borderline (8.5%). A random 25-item manual sample of the full current draft set found 24 of 25 clearly on-topic berry-industry content; the one exception was consumer-lifestyle content (a "why strawberries mold" article), not noise from source misconfiguration.

Not `OPERATIONAL`: TD-040/TD-045's relevance-screen boundary remains only partially, not reliably, mitigated; most discovered items across both missions remain unprocessed (TD-008); CFIA/Canada food-safety (BM-R-09) remains unresolved (TD-041); the duplicate-cleanup step remains manual, not automated (TD-046). See `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-045, TD-046.

---

## Relevance Screen Boundary V1 (2026-08-23)

Full detail: `docs/v2/RELEVANCE-SCREEN-BOUNDARY-V1.md`. This mission did not add sources -- it fixed the gate between discovery and useful review. Source volume is unchanged (168); this section records measured recall/precision impact only, per this matrix's own "source volume is not recall" discipline.

**Root cause, traced not inferred**: the actual documented operator workflow (`scripts/process_discovered_media.py`, `scripts/run_recent_batch.py`) never called the two-stage, body-aware relevance screen or fetched a real article body for `web_article` items at all -- it exclusively used a separate, older, single-stage, metadata-only module (`app/services/relevance_screening.py`). Within the better-engineered two-stage module itself (`app/services/relevance_screen.py`), a Stage A metadata screen scoring literally zero category signal was confidently, permanently rejected with no path to reconsideration.

**Fixed generically**: (1) both real-workflow scripts now route `web_article` items through the two-stage, body-aware screen the recurring pipeline already used; (2) query-provenance corroboration (a registered Geography/Company entity name + a corporate-action verb in an otherwise zero-signal title) keeps Stage B open instead of confidently rejecting -- query provenance alone never grants relevance; (3) a new explicitly-labeled `TIER_UNCERTAIN` untrusted draft state for the real, measured-dominant case where the article body is structurally unverifiable (Google News redirect pages); (4) French species vocabulary added to the berry-identity gate.

**Overall event-level recall: 30/50 (60%) -> 31/50 (62%)** -- 1 event (BM-C-04, Unifrutti/AvoAmerica Peru) moved MISSED -> CAPTURED (draft, uncertain). By class: Corporate 8/13 (62%) -> 9/13 (69%); all other classes unchanged. By geography: Peru 3/9 (33%) -> 4/9 (44%); all other geographies unchanged.

**Real value beyond the fixed benchmark**: 44 new real drafts from `source-news-search-morocco-berry-fr` (French vocabulary fix, 45/50 of that source's own backlog now review-ready) and a real, previously entirely-missed Driscoll's/Costa Group stake-acquisition cluster (5 independent articles, query-provenance corroboration) -- neither matches a specific fixed benchmark ID, so neither moves the 31/50 number; reported here as evidence the mechanism generalizes, not as a recall claim, per this benchmark's own no-redefinition discipline.

Not `OPERATIONAL`: query-provenance corroboration only rescues items whose title also names a registered entity (TD-058, ~5% of the real zero-signal `news_search_rss` backlog measured); real article-body verification remains structurally unavailable for Google-News-sourced items generally (TD-059); French blackberry identity remains unrecognized, a deliberate exclusion (TD-060).

---

## Unknown-Event Discovery + Query Coverage V3 (2026-08-23)

Full detail: `docs/v2/UNKNOWN-EVENT-DISCOVERY-V3.md`. Relevance Screen Boundary V1 established that 19 of the remaining 20 benchmark misses were never discovered at all -- this mission targeted discovery/source/query coverage, clustering the 19 into reusable mechanisms (regional trade/business press, SEC primary-source disclosure, industry-association feeds) rather than one query per event. Source count: 168 -> 171 (2 real authoritative publisher RSS feeds -- FreshPlaza, Fruitnet -- plus a new `sec_edgar_search_json` adapter, CIK-scoped to Mission Produce). A third, real, previously-undocumented finding: `source-20260819-international-blueberry-organization` had been correctly researched and configured on 2026-08-19 but never once actually discovered until this mission ran it for the first time (TD-065) -- source count is not the same as source activation.

**Overall event-level recall: 31/50 (62%) -> 33/50 (66%)** -- 2 events moved MISSED -> CAPTURED: BM-T-06 (Chile/Peru/Morocco duties response, via the never-before-run IBO source, `direct`) and BM-C-07 (Mission Produce Peru blueberry acreage, via the new SEC EDGAR source, `uncertain`, real content hand-verified). By class: Corporate 9/13 (69%) -> 10/13 (77%); Regulatory 5/11 (45%) -> 6/11 (55%); all other classes unchanged. By geography, the mission's own named weak geographies all moved from the single BM-T-06 capture: **Chile 50% -> 75%, Morocco 33% -> 67%, Peru 44% -> 67%**.

**Real value beyond the fixed benchmark**: 30 more real Mission Produce SEC filings (untrusted `uncertain` drafts, real quarterly blueberry-segment financial disclosure, none matching a specific benchmark ID); two more real, confirmed-by-hand benchmark events (BM-C-09, BM-G-02) whose real source is Fruitnet but are not retroactively reachable through the newly-onboarded live feed (TD-067, a structural limitation, not a defect) -- reported honestly as remaining misses despite the correct source now being monitored.

Not `OPERATIONAL`: SEC-sourced drafts cannot self-verify relevance (structurally unextractable filing format, TD-066) and depend entirely on human review; a newly-onboarded live RSS feed captures only future events of its type, not historical benchmark instances (TD-067); CFIA's recall API was re-tested and found to return stale, years-old data even from its "recent" endpoint, worse than the original audit finding -- not integrated.

---

## Regional Coverage V4 -- Live Market Recall (2026-08-22)

Full detail: `docs/v2/REGIONAL-LIVE-RECALL-SET-V1.md`. This mission introduced a second, permanent acceptance set separate from the fixed 50-event benchmark above: **Regional Live Recall Set V1**, testing whether the OS discovers real, unseen, *current* competitive events across UK/Mexico/Spain/Chile/Peru/Morocco/South Africa without an analyst naming the event first. No source or code changed -- every event came from re-running sources already configured before this mission.

**Fixed benchmark: unchanged at 33/50 (66%)** -- no code or source changes this mission. **Regional Live Recall Set V1: 23/25 core events CAPTURED (92%)** (UK 3/4, Mexico 4/4, Spain 3/3, Chile 4/4, Peru 4/4+1, Morocco 2/3, South Africa 3/3). The two numbers measure different things (historical headline recall vs. current unknown-event discovery) and are never combined.

**Geography**: Spain (previously zero fixed-benchmark coverage) now has 3 real `direct` captures via a pre-existing, previously-unprocessed source (`source-freshuelva-news`). Chile and Peru both proved real recurrence of prior-mission source investment (4/4 and 4/4+1 respectively) with zero new sources. Morocco's French-language discovery produced its first non-blueberry (strawberry) capture. South Africa's existing sources missed nothing tested; Zimbabwe's first-ever China blueberry export was captured as a real, regional-adjacent bonus event.

**Global trade press marginal value measured directly**: IBO 10/10 window items berry-relevant (100%, small single-topic feed); FreshPlaza 4-8/69 items berry-relevant by direct inspection (roughly 6-12%, large low-precision global horticulture firehose -- 66 of 69 currently-discovered items had never been screened at all before this mission, see TD-070); Fruitnet 0/2 this window (too sparse to judge). None of the three materially reduces the need for the region-specific `news_search_rss` sources that produced most of this mission's real recall.

**Berry distribution across the Regional Live Recall Set's 25 core events**: Blueberry 15/25 (60%), Strawberry 5/25 (20%), Blackberry 1/25 (4%), **Raspberry 0/25 (0%)** -- a real, honest finding that blueberry volume is masking caneberry blindness; no regional query source built or reused this mission targets raspberry specifically.

Registered `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-069 (major UK/global retailers not registered as Company entities, blocking corroboration for the retailer-commercial event class) and TD-070 (`article_rss` sources skip Stage A relevance screening at discovery time, unlike `news_search_rss`).

---

## Blackberry / Raspberry Vertical V1 (2026-08-22)

Full detail: `docs/v2/CANEBERRY-LIVE-RECALL-SET-V1.md`. Regional Live Recall Set V1 found raspberry at 0% and blackberry at 4% of 25 live regional events -- the clearest measured content-coverage imbalance on the platform. This mission asked empirically whether that reflects genuine system blindness or a sampling artifact from a geography-driven (not species-driven) sample.

**Canonical caneberry baseline** (by `berry_ids`, blueberry/strawberry shown as context only): Varieties 12 raspberry / 1 blackberry (vs. 41 blueberry); breeding programs 1 raspberry / **0 blackberry**; trusted Evidence 191 raspberry / 146 blackberry; CPVO-referencing evidence 4 raspberry / **0 blackberry**; Signals and Assessments **0 for both** raspberry and blackberry (100% blueberry). A separate, real measurement-integrity finding: ~45% of trusted Evidence (574/1,266 records) carries no `berry_ids` at all, and 27/21 of those untagged records mention raspberry/blackberry respectively in their own titles -- every berry-scoped count on this platform, including the ones in this paragraph, should be read as a floor, not exact (TD-071).

**Caneberry Live Recall Set V1: Raspberry 9/9 (100%), Blackberry 7/9 (78%) -- reported separately, never combined.** Both real misses (a Fall Creek acquisition story, a Google-News redirect failure; a Spain Huelva blackberry-acreage story, an RSS-window-snapshot limitation) share already-known root causes (TD-059/TD-067-style), not new architecture problems. Existing, previously-onboarded regional sources (`source-news-search-uk-berry-growers`, `source-news-search-morocco-berry-fr`) already carried 9 real, unread caneberry headlines before this mission looked for them -- the same "under-mined existing source" pattern Regional Coverage V4 established.

**Real bug found and fixed**: `screen_relevance()`'s `berry_identity` vocabulary was missing `zarzamora` (the term Mexican trade press actually uses for blackberry) and `caneberry` (a real, 100%-precision US/UK collective term, live-tested) -- three real, significant blackberry stories (including a real Planasa "Yosemite" variety launch) scored 0 and were silently rejected before this fix. Fixed additively in `app/services/relevance_screen.py` and `app/services/deterministic_tagging.py`; 30 existing tests for both modules pass unchanged.

**3 new sources added, each individually live-tested and justified before adding** (171 -> 174): `source-news-search-caneberry-global` (English, global company/breeder news no country query reaches), `source-news-search-mexico-zarzamora` (Spanish, proven distinct signal from the existing generic "mora"), `source-news-search-chile-frambuesa` (Spanish, Chile is a real major raspberry exporter with no prior raspberry-specific query). All three idempotent on re-run (0 duplicates).

**CPVO's real structural gap, precisely root-caused**: `cpvo_registry.py`'s `discover()` builds queries from the platform's own already-tracked Variety entity names/aliases, not a blanket species search -- with only 1 tracked blackberry Variety, CPVO monitoring can only ever issue ~1 real query for blackberry regardless of true CPVO activity. A real, previously-undiscovered chicken-and-egg architecture finding, not a source-access problem.

**No hardcoded blueberry/strawberry bias was found** in discovery, relevance-screening, patent-monitor, or CPVO code paths -- every mechanism examined is genuinely berry-parameterized; the measured imbalance traces to data volume and vocabulary completeness, not code-level bias.

Registered `docs/v2/TECHNICAL-DEBT-REGISTER.md` TD-071 (untagged trusted Evidence hides real per-berry content from every measurement) and TD-072 (`deterministic_tagging.py` has zero French vocabulary for any berry).

---

## Evidence Berry Tagging Backfill V1 (2026-08-22)

Full detail: `docs/v2/EVIDENCE-BERRY-TAGGING-BACKFILL-V1.md`. Data-quality repair directly answering TD-071/TD-072. All 574 untagged trusted records traced to one historical bulk-seed batch (`source_type: news_search`, `captured_date: 2026-08-06`) -- not an ongoing pipeline leak; the 3 trusted records captured since were already 100% tagged.

**Real bug found and fixed**: `deterministic_tagging.infer_berry_ids_from_text()` used a plain substring check, not word-boundary matching -- "mora" (blackberry) false-positive-matched inside ordinary Spanish words like "morado" (purple) and "enamorado" (in love). Fixed by reusing `relevance_screen.py`'s own proven-safe `_word_present()` pattern. `tests/test_deterministic_tagging.py` added (8 tests; this module had zero prior direct coverage). French and Italian species vocabulary added to `deterministic_tagging.py` for blueberry/strawberry/raspberry, matching `relevance_screen.py`; blackberry's French `mûre`/Italian `more` remain deliberately excluded (real "ripe"/"more"-the-English-word collision risk, unaffected by word-boundary matching).

**Dry-run then apply, deterministic title/summary text only, no article-body fetch**: 254 single-berry + 21 multi-berry = 275 of 574 untagged records backfilled; 299 correctly left untagged (company/category-only mentions, off-topic scraping noise -- verified by manual sample, not a missed vocabulary term). Second `--apply` run produced zero additional changes (idempotent). A rigorous, fully-programmatic key-by-key diff across all 275 changed files confirmed zero fields changed other than `berry_ids` and the new, additive `berry_tagging_provenance` audit object -- no trust/status/text mutation.

**Result**: trusted Evidence tagged rate 54.7% -> 76.4%. Blueberry 484->671 (+38.6%), Strawberry 292->367 (+25.7%), Raspberry 191->218 (+14.1%), Blackberry 146->167 (+14.4%) -- see the "Mainstream news" row above. Blackberry/Raspberry's Variety catalog depth (12/1 tracked entities) is unchanged -- this is metadata repair, not new intelligence; no recall claim is made.

TD-071 substantially resolved (legacy batch closed; general future-risk noted, not deleted). TD-072 resolved. New: TD-073 (a hypothetical future draft re-tagging pass would be poisoned by AI enrichment's own negation language -- real, evidenced, not currently causing wrong data, not fixed this mission).

---

## Caneberry Variety + Actor Expansion V1 (2026-08-22)

Full detail: `docs/v2/CANEBERRY-VARIETY-ACTOR-EXPANSION-V1.md`. Blackberry's Variety catalog (1 entity, 0 breeding programs, 0 CPVO filings) did not change after Evidence Berry Tagging Backfill V1 raised its Evidence depth (146->167) -- by design, since that mission was metadata repair only. This mission asked how much real blackberry/raspberry Variety-level graph depth the already-trusted Evidence base could support.

**Blackberry Varieties: 1 -> 5** (Victoria, + Ervin/NC State, Ponca/University of Arkansas, Ouachita/University of Arkansas, BK 6-13/Plant Sciences Genetics -- the named selection under PSG's Rejoice platform, modeled brand+variety per the existing BluGenix/Eterna precedent). **Raspberry Varieties: unchanged at 12** -- the one real gap found was a missing evidence link on the already-existing Malaika entity (a second, real, independent Spanish grower, Onubafruit, alongside the already-recorded Portugal relationship), not a missing entity. 2 new Organization entities created (NC State University, Onubafruit), each grounded in real trusted Evidence and needed for a real relationship -- no entity was created merely to improve matching. A real candidate (Yosemite, Planasa) was deliberately **not** created: its only grounding Evidence remains an untrusted, unreviewed draft, failing the same trust-gate every existing Variety entity meets.

**CPVO impact, measured**: a bounded dry-run + real apply (`scripts/monitor_cpvo_registry.py`) against the expanded catalog found 2 new, real, berry-relevant CPVO Community Plant Variety Right filings (Ouachita, Ponca; correct genus `Rubus subg. Rubus`) that were structurally unreachable before this mission, since CPVO's query mechanism is seeded from tracked Variety names. Both remain untrusted `inbox/evidence/` drafts pending human review -- not linked into trusted entities. **Patent cross-check**: the existing bounded watchlist found 15 real blackberry-plant-patent hits, all already known, none matching the 4 new varieties -- an honest negative, not a gap (Ponca/Ouachita, released 2003, predate the watchlist's own 2023 publication-date floor; a real, separate, non-CPVO reason for absence).

**Live UI/search verification**: `/entities/variety?berry=berry-blackberry` correctly renders all 5 varieties with correct breeder links; `/entities/variety/variety-malaika` correctly shows two separate `GROWER` entries (Onubafruit, The Summer Berry Company) without collapsing roles; `/search?q=PSG` and `/search?q=Onubafruit` each resolve to exactly one Company result with no duplicate rows; `/queues/commercial_position` and the Competition view both load without error against the expanded graph. One real, small code fix was needed and is itself a finding: `present_competition()` hardcoded `blackberry_thin = berry_id == "berry-blackberry"` regardless of actual Variety count -- a genuine bias case only observable once blackberry's real count changed. Fixed to be count-driven, matching the existing `berry_inventory()` threshold.

A second, real, pre-existing data-quality finding was corrected in passing (not this mission's primary purpose): `ev-20260806173539-9f2f-...` ("Herriot, a luscious new strawberry...") carried `berry_ids: ['berry-raspberry']`, traced to its source bucket being named "Raspberry variety license" rather than its actual content -- fixed to `berry-strawberry`. A second suspected mistag (`ev-abb-varieties`, tagged `berry-blueberry`) was investigated and found to be intentional "negative evidence" from an earlier pilot mission (proving ABB is *not* a blueberry breeder), not an error -- left untouched.

No new Technical Debt was registered -- TD-076 was confirmed the current highest immediately before writing, and this mission's own findings (Yosemite's trust-gate block, the 2003 patent-watchlist boundary) are reported as honest structural facts in-line rather than framed as new unresolved debt.

---

## Learner Mode capability maturity (2026-08-22)

Learner Mode (Workstream K, `docs/v2/feature-requests/LEARNER-MODE.md`) is a formalized product requirement, not an implemented capability. **Every cell below is `NONE`** -- no Learner Mode content, schema, source, or UI exists in canonical as of this entry. The feature request's own source citations (university extension guides, peer-reviewed journals, trade-fair sensory panels, Wikimedia Commons, etc.) are a recommended source base for a future mission, not evidence of current coverage -- a source appearing in a requirements document does not count toward this matrix.

| Capability | Blueberry | Strawberry | Raspberry | Blackberry | Maturity |
|---|---|---|---|---|---|
| Agronomy knowledge | 0 | 0 | 0 | 0 | NONE |
| Pest / IPM knowledge | 0 | 0 | 0 | 0 | NONE |
| Harvest / AgTech knowledge | 0 | 0 | 0 | 0 | NONE |
| Taste / consumer science | 0 | 0 | 0 | 0 | NONE |
| Licensed visual learning | 0 | 0 | 0 | 0 | NONE |

This is distinct from, and must not be conflated with, the existing Variety Knowledge / PVR / Retail-Observation rows above (Variety Intelligence Backbone, competitive identity and market footprint) or the Weather row (Trade/Weather, quantitative environmental observation). See `docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md` section 12a for the full boundary discussion. No implementation, schema change, source addition, or sample data was created by the mission that added this section -- documentation/governance only.

---

## Direct Source Upgrade + Coverage Gap Closure V1 (2026-08-25)

Full audit and probe record:
`docs/v2/DIRECT-SOURCE-UPGRADE-AND-COVERAGE-GAP-CLOSURE-V1.md`.

This was a selective path-quality change, not another broad expansion:
194 -> 196 registered Sources, 73 -> 75 machine-discoverable, and 51 -> 53
non-search direct paths. Explicit Company-linked non-search direct coverage
improved 14 -> 18 through two new exact-linked official RSS feeds (Advanced
Berry Breeding and The Summer Berry Company) plus exact Company linkage on
the existing Freshuelva and Nova Siri Genetics Sources without changing
either Source identity. Direct article RSS count is 31 -> 33.

Discoverable intent changed Blueberry 62 -> 63, Strawberry 44 -> 45,
Raspberry 42 -> 44, and Blackberry 42 -> 43. This does **not** promote any
trusted Evidence maturity cell and does not claim market completeness. The
material improvement is first-party Raspberry/caneberry monitoring and exact
actor attribution. Search remains as broader fallback and shared canonical
URL identity handles overlap.

The application collector proved both new feeds at 10/10 items with zero
item failures and then 0 new / 10 already-known on an exact repeat. United
Exports, Wish Farms, Mountain Blue Genetics, Onubafruit, Driscoll's,
Fruitist/Agrovision, Rijk Zwaan, and Eurosemillas were deliberately not added
after access, boundedness, richness, consumer-noise, or current-relevance
checks failed the mission's acceptance standard. No blocked mechanism was
bypassed; Growing Produce is unchanged. No new unresolved platform debt was
introduced—the remaining gaps are documented external endpoint/portfolio
limitations, not hidden operational state.

---

## Independent Missed Intelligence Recall Audit V1 (2026-08-31)

Full detail: `docs/v2/INDEPENDENT-MISSED-INTELLIGENCE-RECALL-AUDIT-V1.md`. This is **not** a coverage percentage and did not add Sources or trusted Evidence.

22 qualifying public genetics items scored against canonical `8226a5d`:

| Class | Count in this set |
|---|---:|
| FULLY REPRESENTED | 2 (SEKOYA Nova; RedSayra) |
| SOURCE UNKNOWN | 1 (Bayer / Baya Solara) |
| SOURCE KNOWN, NOT COLLECTED | 5 (Italian Berry ×3 rows; CFIA Skye; CPVO Malling Centenary) |
| SOURCE COLLECTED, ITEM MISSED | 8 |
| ITEM COLLECTED, ENTITY MISSED | 2 (NDA AzraBlue; Apex capture) |
| ENTITY FOUND, IDENTITY UNRESOLVED | 1 (`variety-fc11-164` / Everlast) |
| DATE/CHRONOLOGY FAILURE | 1 (MegaCrisp page vs MegaEarly 2025 harvest) |
| GEOGRAPHY LINKAGE FAILURE | 2 (Apex empty `geography_ids`; Victoria has none) |

Blackberry trusted Varieties remain sparse (Victoria exists; Clara/Kalika/Loch Katrine do not). Raspberry still has no Glen Mor / Glen Eden / Skye entities. Collection blueberries named on the NDA list and Fall Creek SA page (AzraBlue, AtlasBlue, …) are not trusted Varieties. Do not promote matrix maturity cells from this audit.

---

## Industry Pulse Discovery + News Recall V1 (2026-09-01)

Full detail: `docs/v2/INDUSTRY-PULSE-DISCOVERY-AND-NEWS-RECALL-V1.md`. This is a catch-net, not a maturity promotion and not a Source onboard.

Live Google News RSS on 2026-09-01 (32 generated queries): 24h 23 unique / 1 qualifying; 7d 79 unique / 4 qualifying (3 SOURCE_UNKNOWN, 1 SOURCE_KNOWN_NOT_COLLECTED). Regional RSS yield remains 1 unique URL per non-global geography. Do not mark Mainstream news STRONG from this.

Retrieval Provider Bake-Off V1 (same day): 18-slice comparable run. Google News 114 unique / 19 qualifying; Perplexity Search 104 unique / 20 qualifying; URL-identity overlap 0; host overlap 5. Exa/Firecrawl/Bright Data not live. Production pulse remains Google News. Full detail: `docs/v2/RETRIEVAL-PROVIDER-BAKE-OFF-V1.md`.

Industry Pulse Qualification + Editorial Relevance V1 (same day): provider-neutral layered qualifier. Frozen 34-row qualification benchmark precision 0.720 → 1.000 with 0 recall losses on expected-qualify rows. Genetics recall `benchmark.json` untouched. Not a coverage-maturity promotion. Full detail: `docs/v2/INDUSTRY-PULSE-QUALIFICATION-AND-EDITORIAL-RELEVANCE-V1.md`.

Authoritative Data + NewsCatcher CatchAll Expansion Bake-Off V1 (same day): USDA PVPO monthly XLSX is a live structured national registry (57 berry rows; no documented API). UPOV PLUTO is a paid normalization index with a 100-record distribution cap — not a SaaS derived database. USPTO ODP / BigQuery patents / CatchAll are prototyped; keys absent so not live-tested. HortiDaily remains the existing RSS Source. Not a coverage-maturity promotion. Full detail: `docs/v2/AUTHORITATIVE-DATA-NEWSCATCHER-CATCHALL-V1.md`.

---

## How to refresh the evidence-class counts

Re-count committed `data/evidence/*.json` by stored `source_type` /
`media_format` and explicit `berry_ids`. Do not hand-edit a cell without
re-running the inventory. Inbox drafts stay out of the class table.
