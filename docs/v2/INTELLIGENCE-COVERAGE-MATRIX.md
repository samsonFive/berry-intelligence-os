# Intelligence Coverage Matrix

Living **coverage-control** document for
`docs/v2/INTELLIGENCE-EXPANSION-BUILD-GUIDE.md`. Counts come from committed
records and `data/configuration/sources.json`. This is not marketing.

**Do not fabricate coverage.** If a class is empty, write `NONE`.
If a class is blueberry-only with a live pipeline elsewhere, write `PILOT`.
Update this file when sources, entities, or trusted evidence change.

**As-of:** 2026-08-21 · published Evidence `1,264` · Sources `142` ·
inbox drafts are runtime-only and noted separately.

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
| Mainstream news | 362 | 289 | 190 | 145 | 574 | OPERATIONAL — keyword-news volume, not recall-benchmarked |
| Association | 6 | 0 | 0 | 0 | 0 | PILOT |
| Regulatory / government | 1 | 0 | 0 | 0 | 0 | PILOT |
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

`data/configuration/sources.json`: **142** sources.

| `type` | Count |
|---|---:|
| `reference` | 101 |
| `keyword` | 33 |
| `rss` | 8 |

`discovery.adapter` present on 24 sources: `article_rss` 12, `podcast_rss` 8,
`youtube_feed` 4.

Keyword monitors (33) drive the Mainstream news auto-capture that dominates
strawberry / raspberry / blackberry published counts. That is **keyword-news
volume**, not company-page or PVR coverage, and not a recall benchmark.

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
the cells. Next expansion mission after the V2 decision-workflow gate is
Mainstream News + Regulatory Recall Benchmark V1.
