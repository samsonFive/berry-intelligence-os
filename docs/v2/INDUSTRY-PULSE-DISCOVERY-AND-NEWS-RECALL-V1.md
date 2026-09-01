# Industry Pulse Discovery + News Recall V1

Live-first catch-net so the authenticated front page has enough **fresh
material** to populate. This is not a homepage redesign. Hits are discovery
metadata only and never become trusted Evidence.

**As-of:** 2026-09-01. Canonical at implementation: `efd7c26`
(Source Coverage Gap Closure V1, PR #204, which already contains Collector
Recall Gap Closure V1 / PR #203). Frozen recall `benchmark.json` was not
edited.

## 1. Why ordinary Google search can beat the app

Italian Berry and BlueberryBreeding prove the **known-Source pipeline can
produce today's drafts** when collectors run (production: 17 Publication
drafts from those two Sources). The remaining gap is everything **outside**
those known collectors.

This worktree's trusted corpus, scored on `published_date` only:

| Slice | Newest `published_date` |
|---|---|
| Trusted Evidence | 2026-08-06 (Noposion / Meiming blueberry variety dispute) |
| Blueberry | 2026-08-06 |
| Strawberry | 2026-07-31 |
| Raspberry | 2026-07-29 |
| Blackberry | 2026-08-04 |
| Americas (explicit geography) | 2026-07-28 (includes a seed fixture) |
| Europe | 2026-07-17 |
| Africa | 2026-07-08 |
| APAC | 2026-07-28 |

A `captured_date` of 2026-09-01 exists (UN M49 geography record with **no**
`published_date`). Capture is not publication. Inbox `discovered_media` is
absent in this worktree, so newest discovered item is unknown here.

The 23 existing `news_search_rss` Source rows are **narrow**: named
companies, country+export lanes, caneberry breeding, `site:italianberry.it`.
They are not a berry × region × topic pulse. `app/main.py`
`google_news_rss_url()` is US-only. There was no provider-neutral
`discover(query, date_window, geography, berry, topic)` boundary.

So a human Google query for "blueberry harvest Kenya today" or "seedless
blackberry Pairwise" can still surface items the trusted corpus has not
published, even after Italian Berry / BlueberryBreeding are collecting.

## 2. Query matrix

32 live queries, generated from canonical dimensions, **not** 4×5×12=240
Source rows and not hundreds of redundant strings.

- 20 berry × geography pulse rows (blueberry / strawberry / raspberry /
  blackberry × americas / europe / africa / apac / global) with one bundled
  industry clause.
- 12 global topic intensifiers (all four berries OR'd): new variety,
  breeder/genetics, commercial launch, licensing, PBR/patent, acreage,
  trade, weather/crop, pricing, M&A, trials/academic, disease/regulation.

Regional Google editions: americas `en-US`, europe `en-GB`, africa `en-ZA`,
apac `en-AU`. `when:7d` is fetched once; 24h / 3d / 7d are sliced by
**actual `published_date`**. Unknown dates stay unknown and are out of
window.

## 3. Live results (2026-09-01, Google News RSS)

32 queries, 0 fetch failures. Provider is non-deterministic (existing
TD-039). These counts are this run, not a completeness score.

| Window | Discovered (unique) | Qualifying | Novel source | Known source | Duplicates |
|---|---:|---:|---:|---:|---:|
| 24h | 23 | 1 | 1 | 0 | 40 |
| 3d | 32 | 1 | 1 | 0 | 51 |
| 7d | 79 | 4 | 3 | 1 | 94 |

**24h qualifying (1):** Pairwise seedless cherries/blackberries —
`smartcherry.world` — `SOURCE_UNKNOWN`. This is the "can I log in today"
item. The other 22 unique 24h hits were correctly rejected (recipes,
Raspberry Pi, BlackBerry-the-device, milkshakes, real-estate, cafe menus).

**7d qualifying (4):**

| Date | Host | Taxonomy | Story |
|---|---|---|---|
| 2026-09-01 | smartcherry.world | SOURCE_UNKNOWN | Pairwise seedless blackberry/cherry |
| 2026-08-27 | verticalfarmdaily.com | SOURCE_UNKNOWN | Australian greenhouse genetics trials |
| 2026-08-26 | open.kg | SOURCE_UNKNOWN | Kyrgyzstan berry imports into Kirov |
| 2026-08-25 | east-fruit.com | SOURCE_KNOWN_NOT_COLLECTED | Ukraine blueberry variety strategy |

`SOURCE_COLLECTED_ITEM_MISSED` in this 7d window: **0**.
Novel hosts in-window: **3**. Known / not collected: **1**.

An earlier fetch in this session also returned Chile INIA blueberry
genetics (FreshPlaza) and Kakuzi Kenya orchards (KBC). Those did not
reappear on the final RSS pull. Do not treat Google News RSS as a stable
census.

## 4. Regional and berry breadth

The matrix queries all four berries and all four regions. Google News RSS
**yield** is still global-dominated:

7d query yield (unique URL per query geography, before cross-query collapse):

| Geography | Discovered | Qualifying |
|---|---:|---:|
| americas | 1 | 0 |
| europe | 1 | 1 |
| africa | 1 | 0 |
| apac | 1 | 0 |
| global | 109 | 5 |

7d unique stories after dedup (regional attribution preferred over global):

| Berry | Discovered | Qualifying |
|---|---:|---:|
| blueberry | 4 | 1 |
| strawberry | 26 | 2 |
| raspberry | 23 | 0 |
| blackberry | 26 | 1 |

This is **not** "US blueberry news" as a product bias — blueberry unique
discovered in 7d is 4 vs strawberry 26. It **is** a Google News RSS
limitation: regional editions rarely return distinct publisher URLs vs the
global intensifiers. APAC/Africa qualifying is 0 on this run. That is the
bake-off case for Exa / Firecrawl Search, not a reason to add 200 Source
rows.

## 5. Dedup

Canonical publisher URL first, then Google News wrapper, then
origin+title+date. Same story from 20 queries is one row. Distinct
publishers with similar titles stay separate. When global and regional
queries hit the same URL, the regional geography is kept.

## 6. Recall taxonomy

No tenth class. `NOT QUALIFYING` is `UNSUPPORTED_NOT_QUALIFYING`.
Adversarial 7d qualifying set vs newest trusted Evidence (2026-08-06):

| Class | Count |
|---|---:|
| SOURCE_UNKNOWN | 3 |
| SOURCE_KNOWN_NOT_COLLECTED | 1 |
| SOURCE_COLLECTED_ITEM_MISSED | 0 |
| FULLY_REPRESENTED | 0 |

All four qualifying items are newer than the trusted `published_date`
peak. None auto-onboard. None write Evidence.

## 7. Provider-neutral adapter

```text
discover(query, date_window, geography, berry, topic) -> hits
# title, url, source_domain, published_date, snippet,
# query provenance, provider
```

`GoogleNewsRssProvider` reuses existing `news_search_rss` fetch/normalize.
`MemoryProvider` is the substitution test double. Paid Exa / Firecrawl /
Bright Data credentials are **absent**; do not couple product logic to them.

Plug-in point: `app/services/industry_pulse/providers.py`. A later vendor
is one class implementing `DiscoveryProvider.discover` plus a constructor
argument to `run_pulse()`. Qualification, novelty, and the matrix stay
provider-agnostic.

## 8. Persistence and trust

GET `/industry-pulse` is authoring-only (403 otherwise) and **never**
fetches the web. POST `/industry-pulse/run` and `scripts/industry_pulse.py`
write `inbox/industry_pulse/latest.json` (gitignored metadata: titles, URLs,
dates, provenance). No page bodies. Absent from `scripts/build_static.py`.
Homepage `/` and `/today` were not modified.

## 9. Recommended next bake-off

1. **Exa** (or Firecrawl Search) behind the same `DiscoveryProvider` for
   APAC / Africa / Europe query yield — Google News RSS did not.
2. Keep Google News RSS as the free default.
3. Do not auto-onboard `smartcherry.world`, `verticalfarmdaily.com`,
   `open.kg`, or `east-fruit.com` from this catch-net. Operator Source
   Health remains the onboard path.
4. Do not treat production Italian Berry / BlueberryBreeding draft counts
   as proof that the catch-net is unnecessary; they prove known-Source
   freshness, which is a different layer.
