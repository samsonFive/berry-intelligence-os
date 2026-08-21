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
| Varieties | 58 | 41 | 5 | 12 | 0 |
| Breeding programs | 12 | 9 | 3 | 1 | 0 |

Raspberry Vertical V1 (PR #49) added real raspberry companies/varieties
(Wish Farms, Global Plant Genetics, James Hutton Ltd, Chambers, Berrytech,
Cornell raspberry releases, Advanced Berry Breeding cultivars). Blackberry
still has **no variety entities** and **no breeding-program entities**.

Geography entities on disk (18): Australia, Canada, Chile, China, Colombia,
Europe, Germany, Mexico, Morocco, Netherlands, North America, Peru, Portugal,
South Africa, Spain, United States, Zambia, Zimbabwe.

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
| PVR / variety registry | 16 | 0 | 0 | 0 | 0 | PILOT |
| Podcast / video | 1 | 0 | 0 | 0 | 0 | PILOT |
| Insider newsletter | 3 | 0 | 0 | 0 | 0 | PILOT |
| Retail observation | 1 | 0 | 0 | 0 | 0 | PILOT |
| Social | 0 | 0 | 0 | 0 | 0 | NONE |
| Careers / jobs | 0 | 0 | 0 | 0 | 0 | NONE |
| Conferences / events | 0 | 0 | 0 | 0 | 0 | NONE |
| Customs / trade | 0 | 0 | 0 | 0 | 0 | NONE |
| Weather | 0 | 0 | 0 | 0 | 0 | NONE |
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

`data/configuration/sources.json` (147 sources -- 142 plus 5 added
2026-08-21 by the Recall Benchmark mission). A tagged source is not
coverage until trusted Evidence exists.

| | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---:|---:|---:|---:|
| Total tagged sources | 93 | 72 | 65 | 66 |
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

## How to refresh the evidence-class counts

Re-count committed `data/evidence/*.json` by stored `source_type` /
`media_format` and explicit `berry_ids`. Do not hand-edit a cell without
re-running the inventory. Inbox drafts stay out of the class table.
