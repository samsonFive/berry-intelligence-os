# Global Week Recall Recovery V2 / Information Universe Activation V1

**Status:** Code complete 2026-09-02. Not deployed from Cursor.
**PRODUCT ACCEPTED:** NO
**DEMO READY:** NO

Keep `/week`. Do not build another product surface. This mission
activates the next information layers so the weekly edition can answer
“what changed in the berry industry this week?” without being obviously
beaten by a few minutes of ordinary web research.

## 1. Production state (verified, not assumed)

| Check | Result |
|---|---|
| Canonical `origin/v2/intelligence-os` | `11cd041543f7be8d7cfd09d7c8852d9b7af4eb21` (PR #220 merge) |
| PR #220 in canonical | Yes |
| Last recorded production deploy | `ffd6837` (PR #221 Trusted Freshness). Production `stakeholder.css` is **13525 bytes** = `ffd6837`, not `11cd041` (13563). |
| `/week` on production | **Not confirmed live.** Unauthenticated paths all 302 to `/login`, including unknown routes. CSS size says production is pre-#220. |
| Production Perplexity | Enabled for Competitor Pulse (PR #218). Cannot serve `/week` until `/week` is deployed. |
| Local Perplexity key | Present. NewsCatcher / CatchAll / Exa / APITube / USPTO ODP / GCP project **absent**. |

Do not treat merge as deploy.

## 2. Frozen-miss root causes

| Case | Window truth | V1 class | V2 recovery |
|---|---|---|---|
| A. Fruitnet FPJ British blueberry +11%, 2026-09-01 | In 7d | `SOURCE_NOT_SEARCHED` for Fresh Produce Journal + `DEDUP/RANKING_FAILURE` (Google News items collapsed to `fruitnet.com` homepage) | **FOUND** in-window via Google `site:fruitnet.com` after homepage-identity fix. Direct `45.rss` is Produce Plus (2 kiwi items) — wrong magazine. |
| B. Hortifrut / Naturipe / Mountain Blue | 2026-07-30 | `OTHER` — outside true 7d. Also `SOURCE_NOT_SEARCHED` on the live plane (Hortifrut newsroom RSS existed, `/week` never called it). | **FOUND** on specialist RSS / older circulating. Correctly **not** in What Matters. Do not hide weak coverage with July material. |
| C. Australia–Vietnam access | Oct 2025 / Dec 2025 | `OTHER` — outside window | Original remains older. Related in-window Vietnam blueberry-supply coverage found. |
| C. China price collapse | Apr 2026 | `OTHER` — outside window | Found as older circulating. Not this week. |
| C. Japan strawberry branding | Feb–Mar 2026 original; 2026-08-31 JP follow-through | `PROVIDER_DID_NOT_RETURN` / APAC language gap | **FOUND** in-window: Japanese coverage of illegal sale of branded strawberry seedlings in China (2026-08-31). |
| D. Guardian UK harvest 2026-08-27 | In 7d | `PROVIDER_DID_NOT_RETURN` (AOL/Yahoo syndication was found in V1) | **FOUND** via Perplexity (Yahoo syndication). Direct guardian.com URL still not required for the event to surface. |

## 3–5. Provider / specialist live state

### High-recall news providers

| Provider | Access | Live-tested this mission | Activated on `/week` | Notes |
|---|---|---|---|---|
| Google News RSS | Yes | Yes | Yes (primary) | 7d: 50 queries, 2273–3132 raw depending on run, ~106–691 unique qualifying (all dates). `when:` remains advisory. |
| Perplexity Search | Key present | Yes | Yes (catch-net, same public-only switch as Pulse) | 33 catch-net queries, 326 hits, **91–96 provider-unique qualifying**. No private intelligence sent. |
| Specialist RSS | Public feeds | Yes | Yes (new) | 13 feeds, 478 hits, **253 provider-unique qualifying**. |
| Exa | `EXA_API_KEY` absent | Adapter only | No | Operator: set `EXA_API_KEY`. Next paid activation candidate if specialist+Perplexity still miss mainstream. |
| APITube | `APITUBE_API_KEY` absent | Adapter written, auth-refuses without key | No | `GET https://api.apitube.io/v1/news/everything`, `X-API-Key`. |
| NewsCatcher CatchAll | Key absent | Not live | **No** | Async 10–15 min paid jobs. Unsuitable for request-time `/week`. Do not slice-loop. |

Recommended next paid activation: **APITube** (sync news, source.domain filters for Fruitnet/Packer) or **Exa** (neural web, better than CatchAll for `/week` latency). CatchAll stays bake-off/probe only.

### Specialist sources (current, not historical existence)

| Publisher | Source exists? | Active collector? | Mechanism | Live feed now? | Newest pub date (2026-09-02 probe) | Feeds live `/week`? | Feeds Publication Review? |
|---|---|---|---|---|---|---|---|
| Fruitnet / FPJ | Yes (`source-fruitnet-produce-plus`) | article_rss on **45.rss = Produce Plus** | RSS + new Google site-search | 45.rss 200, 2 items; site-search 100 items | 45.rss 2026-09-02 (kiwi); site-search **2026-09-01 FPJ blueberry** | Yes | Yes, if sent to review |
| FreshPlaza | Yes (duplicate IDs) | article_rss `rss.xml` | RSS | 200, 77 items | 2026-09-01 | Yes | Yes |
| The Packer | Reference + podcast; no first-party article RSS | news_search_rss | Google site-search (first-party `/rss.xml` and `/feed` **403**) | 200 via Google, 100 items | 2026-08-24 | Yes (search) | Yes |
| HortiDaily | Yes | article_rss `rss.xml` | RSS | 200, 30 items | 2026-09-01 | Yes | Yes |
| Italian Berry | Yes (`news_search_rss`) | Google site-search (no first-party RSS) | news_search_rss | 200, 100 items | 2026-08-28 | Yes | Yes |
| FreshFruitPortal | Yes | article_rss berries tag | RSS | 200, 10 items | 2026-09-01 | Yes | Yes |
| EastFruit | Reference only in registry; **en/feed now live** | article_rss added to week catalog | RSS | 200, 10 items | 2026-09-01 | Yes | Yes if reviewed |
| Produce Report | Yes | article_rss | RSS | 200, 10 items | 2026-09-01 | Yes | Yes |
| Perishable News | Yes | article_rss produce category | RSS | 200, 10 items | 2026-09-01 | Yes | Yes |

Collection `last_checked_at` on these Source records is still **null** in `sources.json`. That is registry metadata, not live-week telemetry. `/week` now fetches the feeds itself.

## 6. Date-window fix

Provider `when:` ≠ article `published_date`.

- Display window unchanged: 24h / 7d / 30d, default 7d.
- Retrieve window: 24h→7d, 7d→30d, 30d→30d.
- Inclusion uses normalized `published_date` only.
- Homepage Google News origins no longer collapse every Fruitnet story into one URL.

Measured live cost: ~20–22s vs V1 ~9s Google-only. Recall, not the 9s budget, is the constraint.

## 7–8. APAC and mainstream

APAC 7d in-window: **0 → 7**. Weak-region list empty.

Additions: richer APAC geo terms, `apac:en` / `zh-focus` / `ja-focus`, CJK crop/industry identity in `qualify_hit` and geography patterns, Produce Report + Berries Australia + EastFruit on the live plane.

Mainstream: Guardian harvest survives via syndication (Yahoo) + industry terms (`harvest`, `volumes`, `bumper`, `heatwave`). “Berry” in the headline is not required when title+snippet establish berry-industry relevance. Precision still rejects recipes, jobs, cannabis, Raspberry Pi.

## 9–12. Authoritative structured data

Existing prototypes reused. Not forced through news semantics.

| System | Layer | This PR | Live |
|---|---|---|---|
| USDA PVPO | AUTHORITATIVE_REGISTRY | Already parses monthly XLSX (57 berry rows). No public API. | Not fetched on `/week` GET (monthly, heavy). |
| USPTO ODP | AUTHORITATIVE_REGISTRY | Existing `uspto_odp.py`. | Key absent. |
| Google Patents BigQuery | STRUCTURED_DATASET | Existing bounded SQL (`LIMIT` required). | `GOOGLE_CLOUD_PROJECT` absent. On-demand $6.25/TiB, 1 TiB/month free. Do not full-scan. |
| UPOV PLUTO | NORMALIZATION_REFERENCE | Parser + 100-record cap. | **Do not productize.** Premium CHF 750/yr; derivative-database / SaaS resale flags. |
| CPVO | AUTHORITATIVE_REGISTRY | Existing monitor. | Interoperable; not mixed into news. |

`/week` gained dedicated **PBR / regulatory** and **Patents / genetics filings** sections for news-plane items that name those events. Structured registry rows stay on their adapters.

## 13–16. `/week` before / after (live, 2026-09-02)

V1 7d (Google-only, Perplexity off): raw 1607, qualifying 93, **in-window 6**, all four regions empty.

V2 7d (Google + specialist RSS + Perplexity):

| Window | Raw | Unique | Qualifying | In-window | Regions A/E/Af/APAC | Berries BB/ST/RB/BK | Latency |
|---|---:|---:|---:|---:|---|---|---:|
| 24h | 2957 | — | 981 | **41** | 10/8/5/6 | 13/19/8/4 | 20.7s |
| 7d | 3132 | 981+ | 1058 | **81** | 14/13/6/**7** | 39/26/14/6 | 21.3s |
| 30d | 3133 | — | 1063 | **248** | 54/30/26/30 | 140/82/35/31 | 18.6s |

7d provider-unique qualifying (all dates, not just in-window): Google 691, specialist 253, Perplexity 91.

## 17. Competitor Pulse

Shared `live_stack.py`: Google + optional Exa/APITube when keys exist + Perplexity. Specialist RSS stays week-only (industry feeds, not company-scoped). Pulse query path unchanged. `query_count() == 32` preserved.

## 18–20. Manual-web comparison (bounded, 2026-09-01/02)

| Manual finding | App |
|---|---|
| Fruitnet British blueberry +11% (1 Sep) | FOUND BY APP |
| Fruitnet UK strawberry volumes surge (1 Sep) | FOUND BY APP |
| FreshPlaza UK raspberry prices +12% (1 Sep) | FOUND BY APP |
| FreshPlaza / HortiDaily UV-C California strawberries | FOUND BY APP |
| FreshFruitPortal California strawberry 2026 | FOUND BY APP |
| Produce Report SanLucar China | FOUND BY APP |
| Guardian / Yahoo UK bumper harvest (27 Aug) | FOUND BY APP (syndication) |
| Japanese brand-strawberry seedling trafficking (31 Aug) | FOUND BY APP |
| Driscoll’s CEO (25–26 Aug) | FOUND BY APP |
| Hortifrut / MBO (30 Jul) | FOUND, older circulating |
| China price collapse (Apr) | FOUND, older circulating |
| Nourse blackberry plugs shipping Sep 2026 | Not scored in-window (nursery commerce) |
| Markon mixed-berry supply note (25 Aug) | Not confirmed in What Matters |

Remaining important misses: first-party The Packer RSS (403), Fruitnet magazine-specific RSS (robots `Disallow: /*.rss`; only 45.rss + 72.rss advertised), some Google wrapper URLs instead of article paths, occasional grocery/stock noise in emerging.

## 21–22. Licensing and cost (not legal advice)

| Vendor | Commercial / store / SaaS flags |
|---|---|
| Google News RSS | Public RSS; wrappers; attribution via link. Counsel if redistributing full text. |
| Perplexity Search | Existing production use for Pulse. Public queries only. Vendor ToS for caching snippets. |
| Specialist RSS | Publisher ToS. HortiDaily robots: `search=yes`, `ai-train=no`, `ai-input=no`. We use the declared RSS, not body scrape / AI-input. Fruitnet robots disallow `/*.rss` to crawlers; 45.rss still 200 and was already a Source. |
| APITube / Exa / CatchAll | Keys absent. Full-text retention and resale need vendor review. |
| UPOV PLUTO | Derivative database + commercial dissemination not authorized; 100-record distribution cap. |
| USDA PVPO XLSX | US government public status list. Bibliographic reuse. |

Dogfood / 10 / 100 customers (order-of-magnitude, list prices move):

| | Dogfood | 10 customers | 100 customers |
|---|---|---|---|
| Google News RSS | $0 | $0 | $0 |
| Perplexity Search | existing key; tens of `/week` loads/day | shared cache if ToS allows | shared public collection + rate budget |
| APITube | $0 until key | starter/basic | custom |
| Exa | $0 until key | search credits | custom |
| CatchAll | do not use on `/week` | $50 trial only as async probe | custom; not request-time |
| BigQuery Patents | $0 without project | free-tier 1 TiB/mo if bounded | keep LIMIT; no scans |
| UPOV | do not buy for SaaS | one analyst Premium seat only | **do not** productize |

Prefer one shared public-data collection across tenants where the vendor permits.

## 23–27. Tests / CI / PR

Focused tests: `tests/test_global_week_recall_recovery_v2.py` plus existing week/qualification/discovery identity tests during iteration.

One full suite at PR head. Four CI checks: Change scope, Python tests, Repository integrity, Static public safety.

No Cursor deploy.

## 28–31. Close-out

- Deployment state: **not deployed**
- CODE COMPLETE? **YES**
- PRODUCT ACCEPTED? **NO** — ordinary web research can still surface current specialist items the edition ranks poorly or represents only via wrappers; The Packer has no first-party RSS; some current commercial notes were not lead items.
- DEMO READY? **NO** until production deploy of `/week` + this SHA and a stakeholder can use the edition without immediately leaving for Google.
