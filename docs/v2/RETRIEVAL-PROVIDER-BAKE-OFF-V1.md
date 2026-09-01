# Retrieval Provider Bake-Off V1

Evaluation + adapter architecture only. Production Industry Pulse remains
Google News RSS. This is not a Source onboard, not a trust mutation, and
not a homepage/front-page change.

**As-of:** 2026-09-01. Canonical baseline: PR #205 merge
`606ac843d3cbedb62940a42f8d3705050ecc60a6`.

**Pricing retrieval date:** 2026-09-01. List prices are documented here and
in the bake-off report only. They are not product-runtime constants.

## 1. Providers investigated

| Provider | Search API | Live this run | Adapter |
|---|---|---|---|
| Google News RSS | Yes (existing RSS) | Yes | `GoogleNewsRssProvider` (unchanged) |
| Exa | Yes (`POST https://api.exa.ai/search`) | No — `EXA_API_KEY` absent | `ExaSearchProvider` |
| Firecrawl Search | Yes (`POST https://api.firecrawl.dev/v2/search`) | No — `FIRECRAWL_API_KEY` absent | `FirecrawlSearchProvider` |
| Perplexity Search | Yes (`POST https://api.perplexity.ai/search`) | Yes | `PerplexitySearchProvider` |
| Bright Data SERP | Zone + `POST https://api.brightdata.com/request` | No — key/zone absent | `BrightDataSearchProvider` |

Do not treat the unavailable rows as failed bake-off losses. They were not
tested live.

## 2. Capability audit (docs as of 2026-09-01)

Claims below are vendor-doc / adapter-contract notes, not marketing.

### Google News RSS (baseline)

- Search: RSS `news.google.com/rss/search`.
- Freshness: query syntax `when:1d|3d|7d`. **Not a hard filter** — this
  run returned 2016–2025 items inside a requested 24h/7d window.
- Domain filter: no first-class API.
- Geography/language: edition `hl` / `gl` / `ceid`.
- News-specific: yes.
- Semantic/neural: no.
- Structured output: RSS items. Origin URLs are often publisher homepages.
- Full-page retrieval: no.
- Pagination: existing `_fetch_paginated_rss` (pulse uses 1 page).
- Latency (this run): mean 1.11s / query.
- Pricing: free.
- Rate: polite public RSS; no contract.
- SaaS/resale: public RSS; downstream still goes through canonical
  collection. Do not treat Google News wrappers as publisher URLs.
- Privacy: client-side fetch only.

### Exa (adapter only)

- Search: `POST /search`, Bearer `EXA_API_KEY`.
- Freshness: `startPublishedDate` / `endPublishedDate` ISO.
- Domain: `includeDomains` / `excludeDomains`.
- Geography: `userLocation` ISO country.
- News category available; bake-off adapter does **not** force `category:
  news` because PBR/breeder/university pages are in scope.
- Semantic/neural: yes (`type: auto`).
- Structured: title, url, publishedDate, highlights, score (score stays in
  `provider_metadata`).
- Full-page: optional contents; adapter requests highlights only.
- Pagination: `numResults` 1–100.
- Pricing (2026-09-01 docs): **$7 / 1k requests** (up to 10 results).
- Commercial terms: confirm current Exa ToS before any paid production
  activation. Do not send proprietary Assessments/Signals/Facts.
- Live benchmark: **unavailable**.

### Firecrawl Search (adapter only)

- Search: `POST /v2/search`.
- Freshness: `tbs` (`qdr:d`, `qdr:w`, custom `cdr` for 3d). Docs say `tbs`
  applies to web source.
- Domain / location: supported on the search endpoint.
- News-specific: optional `sources`; adapter uses `web`.
- Semantic: web index, not a neural-first API.
- Structured: title, url, description.
- Full-page: `scrapeOptions` or `/v2/scrape`. Acquisition probe is a
  separate method and was **not** run live.
- Pricing (2026-09-01 docs): search **2 credits / 10 results**; scrape +1
  credit/page. Hobby ~1000 free credits/month.
- Live benchmark: **unavailable**. Acquisition test: unavailable.

### Perplexity Search (live)

- Search: existing `PerplexitySearchClient` (`/search`).
- Freshness: `search_recency_filter` `day|week` for 24h/7d;
  `search_after_date_filter` MM/DD/YYYY for 3d (no native 3d recency).
- Domain: `search_domain_filter` exists; unused in this bake-off.
- Geography: optional `country` ISO (adapter maps europe→GB, africa→ZA,
  americas→US).
- News-specific: no; general web search.
- Semantic: ranking is vendor-side; this is not Agent/Sonar research.
- Structured: title, url, snippet, date.
- Full-page: no (Search API only).
- Pagination: `max_results` 1–20.
- Latency (this run): mean 1.98s / query.
- Pricing (2026-09-01): **$5 / 1k successful POST /search**.
- This bake-off used Search only. Agent/research completion was not called.
- Queries were public berry-industry strings. No Assessments, Signals,
  Facts, analyst notes, or private report prose.

### Bright Data SERP (stub)

- Intended as an alternate SERP index and/or blocked-page escalation.
- Requires `BRIGHTDATA_API_KEY` + `BRIGHTDATA_SERP_ZONE`.
- Pricing (2026-09-01 public pay-as-you-go note): about **$1.50 / 1k**
  successful SERP requests. Not confirmed live.
- Do not make Bright Data the default because it can bypass difficult
  pages. Respect robots and existing project ethics.
- Live benchmark: **unavailable**.

## 3. Methodology

Slices A–F × windows 24h / 3d / 7d = **18 queries per live provider**.

Same semantics across providers. Google News RSS required a documented
boolean/OR translation (`BERRY_TERMS` + edition terms + `TOPIC_TERMS` +
`when:`). A first live pass using the natural-language slice text returned
**0 Google hits** while the existing 32-query pulse matrix still yielded
(80 hits on `pulse:blackberry:europe:7d`). That is Google News syntax, not
a retune to make Google win. Other providers receive the natural-language
slice and their own date/geo API fields. `when:` is stripped.

Qualification, dedup, and miss labels reuse Industry Pulse + canonical
recall taxonomy. Unknown-unknown = host not in Sources, not in Source
Universe, not in trusted Evidence hosts. Those hosts are **not** onboarded.

No composite score.

## 4. Live results (2026-09-01, final comparable run)

| Metric | Google News RSS | Perplexity Search | Exa | Firecrawl | Bright Data |
|---|---:|---:|---|---|---|
| Live | yes | yes | no | no | no |
| Total results | 849 | 180 | — | — | — |
| Unique identities | 114 | 104 | — | — | — |
| Qualifying | 19 | 20 | — | — | — |
| Novel qualifying | 5 | 12 | — | — | — |
| Known-Source item missed | 6 | 6 | — | — | — |
| Unknown Source (qualifying) | 5 | 12 | — | — | — |
| Unknown-unknown hosts | 12 | 14 | — | — | — |
| Tier-1 hosts (rule+class) | 3 | 4 | — | — | — |
| Tier-2 hosts | 9 | 9 | — | — | — |
| Duplicates | 735 | 76 | — | — | — |
| Non-qualifying unique | 95 | 84 | — | — | — |
| Non-qualifying rate | 0.833 | 0.808 | — | — | — |
| Reliable published dates | 114 | 104 | — | — | — |
| Cultivar-dense unique | 5 | 17 | — | — | — |
| Mean latency (s) | 1.11 | 1.98 | — | — | — |
| API calls | 18 | 18 | 0 | 0 | 0 |
| Measured cost (USD) | 0.00 | 0.09 | — | — | — |

### Windows (unique identity inside that window, not collapsed across windows)

| Window | Google unique / qualifying | Perplexity unique / qualifying |
|---|---|---|
| 24h | 114 / 19 | 41 / 5 |
| 3d | 114 / 19 | 48 / 11 |
| 7d | 114 / 19 | 44 / 11 |

Google News `when:` did not change the result set across windows. Perplexity
recency/date filters did.

### Regional / berry breadth (unique identities)

| Dimension | Google News | Perplexity |
|---|---|---|
| Europe | 97 | 50 |
| Africa | 12 | 20 |
| Americas | 4 | 20 |
| Global | 1 | 14 |
| Blackberry | 31 | 21 |
| Raspberry | 6 | 18 |
| Blueberry | 16 | 40 |
| Strawberry | 60 | 11 |

Google News is Europe/strawberry-heavy on these slices. Perplexity is
broader on Africa, Americas, blueberry, and raspberry.

## 5. Authoritative-source recall

Neither live provider found PBR/PVP registry pages or breeder catalogue
tables on these slices.

Google News qualifying examples were mostly trade press and university news
(Fruitnet, Hortidaily, FreshFruitPortal, NC State, AndNowUKnow), plus some
aged or off-window items. Origin URLs were often the publisher homepage.

Perplexity found some academic/gov-adjacent hosts (`ars.usda.gov`,
`wur.nl`, `dergipark.org.tr`, `cals.ncsu.edu`) and also FDA-device /
Job Corps / cannabis / livestock / potato pages that the host-rule labeled
Tier-1 or qualifying. Host-rule Tier-1 is **not** the same as berry-PBR
recall.

## 6. Unknown-unknown discovery

Google unknown-unknown hosts included `agrospectrumindia.com`,
`heraldonline.co.zw`, `projects.research-and-innovation.ec.europa.eu`,
`news.uark.edu`, `theconversation.com`.

Perplexity unknown-unknown hosts included `wur.nl`, `ucanr.edu`,
`geneticliteracyproject.org`, `dergipark.org.tr`, plus noise
(`hightimes.com`, `cannoptikum.com`, `bebee.com`, `specialtyproduce.com`).

Do not auto-onboard any of these.

## 7. Date quality

Both providers attach a date to every unique row in this run. Quality
differs:

- Google News: dates include 2016, 2020, 2024, 2025 inside a requested
  24h/7d pulse. `when:` is advisory.
- Perplexity: qualifying examples clustered on 2026-08-26 … 2026-09-01.

## 8. Multi-provider union

URL-identity union (canonical URL / origin URL):

| | Count |
|---|---:|
| Google only | 114 |
| Perplexity only | 104 |
| Both | 0 |

Host-level union (fairer, because Google origin URLs are often homepages):

| | Count |
|---|---:|
| Google hosts | 114 |
| Perplexity hosts | 86 |
| Both hosts | 5 |
| Google-only hosts | 109 |
| Perplexity-only hosts | 81 |

Shared hosts: `bbc.com`, `cals.ncsu.edu`, `freshfruitportal.com`,
`freshplaza.com`, `perishablenews.com`.

Adding Perplexity Search increases recall. It is not a duplicate of Google
News cost at URL identity. Some trade-press hosts overlap.

## 9. Firecrawl acquisition

Not run. Probe URL list is in `slices.ACQUISITION_PROBE_URLS` (10 public
pages: static trade press, WAF/JS `growingproduce.com`, breeder catalogue,
cultivar table, USDA PVP, university, CPVO, DALRRD, APHA). Mocked scrape
tests exist.

## 10. Measured benchmark cost

Final comparable run: Google $0.00 + Perplexity 18 × $0.005 = **$0.09**.

This mission also ran two earlier Perplexity passes while fixing Google
syntax translation and window/union metrics. Those extra 36 Search calls
were about **$0.18**. Documented, not product runtime.

## 11. Projected monthly cost (pricing as of 2026-09-01)

Assumptions, not quotes. Google News remains free.

| Profile | Requests / day | Google | Perplexity Search | Exa (if keyed) | Firecrawl Search (if keyed) |
|---|---|---|---|---|---|
| DEV / dogfood (current 32-query pulse) | 32 Google; optional 18 Perplexity | $0 | ~$2.70 | ~$3.78 if 18 neural searches | credit-based; 18×2 = 36 credits/day |
| SMALL SaaS (4 berries, multi-region, daily) | 32 Google + 18 Perplexity | $0 | ~$2.70 | ~$3.78 | ~1,080 credits/month |
| ENTERPRISE (broader watch) | 100 paid searches/day | $0 | ~$15 | ~$21 | ~6,000 credits/month |

Firecrawl Hobby ~1,000 credits/month is not enough for daily SMALL search.
Do not hardcode these numbers into runtime.

## 12. SaaS architectural fit

If Exa disappears tomorrow, another `DiscoveryProvider` still satisfies
`discover(query, date_window, geography, berry, topic)`. That is already
true for Google News, Perplexity Search, Firecrawl, and the Bright Data
stub.

Vendor extras stay in `provider_metadata`. Downstream classify/qualify do
not read Exa scores.

Flow remains:

External discovery → normalized URL → canonical collection/acquisition →
Publication → Review → Evidence.

`run_pulse()` still constructs `GoogleNewsRssProvider()` when no provider
is passed.

## 13. Recommended production architecture

**F — evidence-supported, no production switch:**

1. Keep **Google News RSS** as the production Industry Pulse default.
2. Treat **Perplexity Search** as an optional semantic catch-net behind
   the existing interface. It improved Africa/Americas/blueberry/raspberry
   breadth, cultivar-dense hits, date adherence, and unknown-unknown count,
   at about $2.70/month for 18 queries/day.
3. Leave **Exa** and **Firecrawl** adapters dormant until credentials exist.
   Do not promote Exa to primary on docs-only evidence.
4. Do **not** enable Bright Data as a default.
5. If a follow-up activates Perplexity, union+dedup with Google News.
   Expect host overlap on a few trade-press domains and almost no URL
   identity overlap.
6. Tighten qualification before activation. Perplexity’s qualifying set
   still includes cannabis, jobs, livestock, and non-berry produce.

This is not option B or C (Exa primary / Exa catch-net): Exa was not live.

## 14. Activation mission (follow-up)

Only after an explicit product decision:

- Add a runtime flag (env or config) to run Perplexity Search **in
  addition to** Google News for operator pulse, not as a silent replace.
- Persist union metadata only (no bodies, no auto-onboard, no trust write).
- Re-run slices after any qualification change.
- If `EXA_API_KEY` or `FIRECRAWL_API_KEY` appears, run the same 18-query
  matrix live before choosing among Perplexity / Exa / Firecrawl.
- Firecrawl acquisition probe is a separate bounded job (10–20 URLs).

## 15. Tests

`tests/test_retrieval_provider_bakeoff_v1.py` covers the required adapter
contract, translations, failure/timeout/429, union, unknown-source, no
trust mutation, no static leakage, no proprietary prompt leakage, and
deterministic fallback. Existing Industry Pulse tests remain green.

## 16. What this PR does not do

- Does not replace production Industry Pulse with a paid provider.
- Does not deploy to VPS.
- Does not modify homepage `/` or `/today`.
- Does not onboard unknown-unknown hosts.
