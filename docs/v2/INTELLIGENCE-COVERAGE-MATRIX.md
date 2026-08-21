# Intelligence Coverage Matrix

Living **coverage-control** document for
`docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`. Counts come from committed
records and `data/configuration/sources.json`. This is not marketing.

**Do not fabricate coverage.** If a class is empty, write `NONE`.
If a class is blueberry-only with a live pipeline elsewhere, write `PILOT`.
Update this file when sources, entities, or trusted evidence change.

**As-of:** 2026-08-21 · published Evidence `1,264` · Sources `147` (142 plus
5 added same-day by the Mainstream News + Regulatory Coverage Recall
Benchmark V1 mission) · inbox drafts are runtime-only and noted separately.

Maturity labels (guide vocabulary):

| Label | Meaning |
|---|---|
| `NONE` | Zero trusted records and no dedicated source class in the corpus |
| `PILOT` | Few trusted records, one berry only, and/or unpublished pipeline only |
| `PARTIAL` | Real trusted records on more than one berry, still thin vs blueberry |
| `OPERATIONAL` | Material trusted corpus used in Live Intelligence / Company / Brief |
| `STRONG` | Not used yet. Requires a recall-benchmarked class, not volume alone |

Berry assignment uses **explicit `berry_ids`**. `574` published `news_search`
records have empty `berry_ids` (untagged mainstream news). They are counted
in Mainstream news as untagged, not invented into a berry.

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
| Mainstream news | 362 | 289 | 190 | 145 | 574 | **PARTIAL — now recall-benchmarked (see below); volume does not mean recall** |
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

`data/configuration/sources.json`: **147** sources (142 plus 5 added
2026-08-21 by the Mainstream News + Regulatory Coverage Recall Benchmark V1
mission).

| `type` | Count |
|---|---:|
| `reference` | 101 |
| `keyword` | 33 |
| `rss` | 13 |

`discovery.adapter` present on 29 sources: `article_rss` 12, `podcast_rss` 8,
`youtube_feed` 4, **`government_register_json` 2** (new), **`news_search_rss`
3** (new).

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

**Overall event-level recall: 11/50 (22%) before this mission -> 15/50
(30%) after**, all newly-captured events sitting as untrusted drafts
pending human review (the trust gate is untouched by this mission). Recall
by class ranges from 0% (Commercial/Market) to 83% (Genetics/Varieties);
Regulatory/Trade recall stayed at 9% despite 2 new Federal Register
sources, because most regulatory misses in the benchmark are separate
events/documents the new sources' specific queries did not happen to
surface, not a source-coverage-class gap. **Per the maturity legend above,
this is the real basis for marking Mainstream News PARTIAL (not
OPERATIONAL) and Regulatory/Government PILOT: a large keyword-news corpus
and 2 new government sources exist, but measured event-level recall does
not support a stronger label for either.**

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

`data/configuration/sources.json` (150 sources as of the Weather / Climate
Context V1 mission, 2026-08-21 -- see PROJECT-STATUS.md "Last completed" for
the full addition history). A tagged source is not coverage until trusted
Evidence exists.

| | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|
| Total tagged sources | 96 | 75 | 68 | 69 |
| Discoverable (`discovery.adapter`) | 24 | 18 | 16 | 15 |

Three discoverable sources are berry-unscoped (Blue Book Services,
HortiDaily, SanLucar Newsroom). Known gaps: Growing Produce 403
(TD-ACQ-002); NARBA empty feed (TD-ACQ-003).

---

## Source `region_coverage` (intent, not Evidence geography)

| Region | Sources tagged |
|---|---:|
| Global | 68 |
| North America | 60 |
| South America | 23 |
| Europe | 23 |
| Asia-Pacific | 14 |
| Africa | 7 |

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

## How to refresh the evidence-class counts

Re-count committed `data/evidence/*.json` by stored `source_type` /
`media_format` and explicit `berry_ids`. Do not hand-edit a cell without
re-running the inventory. Inbox drafts stay out of the class table.
