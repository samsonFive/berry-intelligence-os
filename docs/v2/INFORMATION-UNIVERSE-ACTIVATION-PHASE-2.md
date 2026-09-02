# Information Universe Activation Phase 2

**Status:** Code complete 2026-09-02. Not deployed from Cursor.
**PRODUCT ACCEPTED:** NO
**DEMO READY:** NO

Do not redesign `/week`. Do not touch review. Do not build reports.
This mission makes paid retrieval configuration-only and turns USDA PVPO /
USPTO / Google Patents into operational structured intelligence.

Canonical base: `fee65be2e89b042645ce121bc06865365f9e4bdb` (PR #224 merge).

## 1. Provider activation (one operator step each)

| Provider | Lane | Live now | Operator step |
|---|---|---|---|
| APITube | FAST request-time | No | `SET APITUBE_API_KEY` → available |
| Exa | FAST request-time | No | `SET EXA_API_KEY` → available |
| NewsCatcher CatchAll | BACKGROUND only | No | `SET NEWSCATCHER_API_KEY` or `CATCHALL_API_KEY` → scheduled recall writes the shared cache |
| Perplexity | FAST catch-net | Yes (local) | already set |
| USPTO ODP | REGISTRY | No | `SET BIOS_USPTO_ODP_API_KEY` → ODP live; public Google Patents JSON is the current fallback |
| Google Patents BigQuery | DATASET | No | `SET GOOGLE_CLOUD_PROJECT` + ADC |

No credential was invented. None of these keys are required at app boot.

### APITube contract (verified 2026 docs)

- Endpoint: `GET https://api.apitube.io/v1/news/everything`
- Auth: `X-API-Key`
- Free plan: 100 req/day, 10/min, `per_page` ≤ 10, first 5 pages, 200-character body preview
- No documented embargo delay on the free plan
- Adapter result cap: 10

### Exa contract (verified 2026 docs)

- Endpoint: `POST https://api.exa.ai/search`
- Auth: `Authorization: Bearer`
- Signup $20 credits; $10/month free; $7 / 1k searches (10 results included)
- Unknown-unknown queries (`week_unknown_unknown_queries`) run **only** against Exa when the key is present. They are not part of the Pulse 32 and are not sent to Google.

### CatchAll architecture

```
scheduled CollectionRunner job (catchall_recall, 6h)
  → submit/pull Base mode (10–15 min)
  → inbox/operations/catchall_recall/cache.json
  → /week merges already-fetched hits
```

Request-time `/week` never submits a CatchAll job. Without a key the pipeline
succeeds as `awaiting_key`.

## 2. Provider union

FAST: Google, Perplexity, APITube, Exa.
BACKGROUND: CatchAll cache.
DIRECT SPECIALIST: existing specialist RSS / site-search.

Publisher ≠ discovery provider. Dedup prefers first-party article URLs over
Google wrappers. Provider-unique counts stay on the edition stats.

## 3. USDA PVPO — live bounded import (2026-09-02)

Official file: `https://www.ams.usda.gov/sites/default/files/media/PVPOApplicationStatus.xlsx`.
Downloaded 1,346,585 bytes. No HTML scrape.

| Metric | Value |
|---|---:|
| Raw berry records | 57 |
| Distinct variety names | 57 |
| Canonical varieties checked | 64 |
| Matched canonical | 0 |
| Candidates written | 57 |
| Ambiguous identity | 0 |
| Distinct new | 57 |
| Newest filing | 2024-12-13 |
| Newest update | 2024-12-30 |
| PVP_APPLICATION_FILED | 33 |
| PVP_GRANTED | 24 |
| Auto-confirmed | no |
| Trust state | UNREVIEWED_REGISTRY |

No automatic canonical merge. Inbox Variety candidates only.

## 4. USPTO / Google Patents — live bounded retrieval (2026-09-02)

ODP key absent. Public Google Patents JSON used. Patent Public Search UI not automated.

| Metric | Value |
|---|---:|
| Provider | google_patents_json |
| Applications/grants kept | 61 |
| False positives dropped | 7 |
| Newest publication | 2026-03-26 |
| Canonical entity matches | 3 (`company-driscolls`, `company-florida-foundation-seed-producers`, `company-university-of-arkansas`) |
| Novel assignee strings | 21 |
| PATENT_GRANTED | 60 |
| PATENT_APPLICATION_PUBLISHED | 1 |
| Trust promotion | none |

Known-breeder portfolio: Driscoll's / Driscoll Strawberry Associates dominate
the sample. Some blueberry plant patents are also tagged `berry-strawberry`
because the assignee string contains “Strawberry” — reported as a false-positive
class, not cleaned by inventing a new relevance rule in this mission.

## 5. Google Patents / BigQuery

Templates ready, LIMIT-bounded: keyword, assignee, CPC/IPC (`A01H6/74`,
`A01H6/36`, `A01H5/08`), bibliographic, similarity.
`GOOGLE_CLOUD_PROJECT` absent. No live bytes processed.
Operator: create a GCP project, `gcloud auth application-default login`,
`SET GOOGLE_CLOUD_PROJECT`. $6.25/TiB, 1 TiB/month free.

## 6. Authoritative event model

**Decision: no new object type.**

Events are an overlay on existing records:

| Event | Host record |
|---|---|
| PVP_APPLICATION_FILED | variety_candidate |
| PVP_GRANTED | variety_candidate |
| PVP_STATUS_CHANGED | variety_candidate |
| PATENT_APPLICATION_PUBLISHED | patent_filing |
| PATENT_GRANTED | patent_filing |
| ASSIGNMENT_OWNERSHIP_CHANGE | patent_filing (only when assignment fields exist) |

Not Publications. Not news articles. No auto identity merge. No trust promotion.

UPOV PLUTO stays `NORMALIZATION_REFERENCE`. Not productized.

## 7. Specialist hardening

- Display URL prefers a first-party article path over a Google wrapper.
- Dedup keeps the specialist article when the same story also arrives as a wrapper/homepage pair.
- The Packer first-party `/rss.xml` and `/feed` remain 403. Site-search only. No scrape.
- Fruitnet `45.rss` remains Produce Plus. FPJ still via `site:fruitnet.com`. Robots `Disallow: /*.rss` respected.

## 8. Frozen corpus

`data/configuration/information_universe_frozen_corpus.json`

Lanes: NEWS, SPECIALIST_PRESS, PBR, PATENTS, APAC, MAINSTREAM_CONTEXT, COMPANY_RELEASES.

The Hortifrut / Mountain Blue 2026-07-30 case stays **outside** true 7d.
Expected outcomes were not changed to make tests pass.

## 9. Retrieval challenge

| Case | Found? | Provider | New vs previous? | Canonical? | Trust |
|---|---|---|---|---|---|
| 1 Specialist news | Yes | specialist_rss / site-search | URL quality, not a new surface | No | LIVE / UNREVIEWED |
| 2 Obscure company | No | CatchAll cache | Architecture only | No | AWAITING_KEY |
| 3 APAC | Yes | Perplexity / Google / specialist | V2 recovery; CatchAll APAC is background | No | LIVE / UNREVIEWED |
| 4 USDA PVP | **Yes** | usda_pvpo | **New category** — structured XLSX | 0/57 | UNREVIEWED_REGISTRY |
| 5 Recent berry patent | **Yes** | google_patents_json | **New category** vs news plane | Yes (3 entities) | UNREVIEWED_PATENT |
| 6 Breeder portfolio | **Yes** | google_patents_json | Assignee retrieval | Yes | UNREVIEWED_PATENT |
| 7 Unknown-unknown genetics | Adapter only | Exa queries | Not live | No | AWAITING_KEY |

## 10. Cost model (shared public collection; customer-private stays separate)

Assumptions: public intelligence collected once per cadence and reused across tenants where vendor terms allow. `/week` request-time providers are the cost that scales with traffic unless cached.

| Source | Unit | Dogfood | 10 customers | 100 customers |
|---|---|---|---|---|
| Google News RSS | $0 | $0 | $0 | $0 |
| Specialist RSS | $0 | $0 | $0 | $0 |
| USDA PVPO XLSX | $0 weekly | $0 | $0 | $0 |
| Google Patents JSON | $0 bounded | $0 | $0 | $0 |
| Perplexity | ~$0.005/search | ~$15–40/mo if `/week` is on | same if shared | same if shared |
| APITube free | 100 req/day | enough to evaluate | upgrade | paid plan |
| Exa | $7/1k | ~$10–30/mo with 6 unknown-unknown + subset of week | shared | shared |
| CatchAll Base | ~$0.10/validated record | $20–80/mo at 2 queries × 10–25 records × 4/day | shared | shared |
| USPTO ODP | key quota | evaluate | shared | shared |
| BigQuery | $6.25/TiB (1 TiB free) | ~$0 if bounded | ~$0–5 | ~$5–20 if weekly CPC |

Best-value production stack:

1. Keep Google + specialist + Perplexity (already unique).
2. Activate **APITube** first for news-spectrum recall (sync, cheap to evaluate).
3. Activate **Exa** second for unknown-unknown genetics/licensing.
4. CatchAll only as the 6-hour background net, never request-time.
5. Keep PVPO weekly + Google Patents JSON; add ODP and BigQuery when keys exist.
6. Do not buy UPOV PLUTO for SaaS.

## 11. Licensing

- APITube / Exa / CatchAll / Perplexity: vendor ToS; no full-text redistribution assumed.
- USDA PVPO XLSX: public AMS dataset; candidates only.
- USPTO / Google Patents: public records; drafts stay unreviewed.
- UPOV: still not productized (CHF 750, 100-record cap, derived-database flags).

## 12. Deployment

Not deployed from Cursor. Production remains whatever is on the VPS.
`/week` was not redesigned.
