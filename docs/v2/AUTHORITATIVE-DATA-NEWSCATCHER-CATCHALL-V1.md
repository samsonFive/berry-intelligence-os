# Authoritative Data + NewsCatcher CatchAll Expansion Bake-Off V1

Capability audit plus bounded prototypes. No trusted-Evidence promotion,
no Front Page work, no VPS deploy, no production monitors.

**As-of:** 2026-09-01. Started from `origin/v2/intelligence-os` @ `721dc9a`.

---

## 1. USDA PVPO access model

No documented public API. Do not claim one.

Verified 2026-09-01:

| Mechanism | What it is |
|---|---|
| Monthly Application Status Report XLSX | Structured public download. Live URL `https://www.ams.usda.gov/sites/default/files/media/PVPOApplicationStatus.xlsx` returned `200 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. |
| Certificate Management System | Search UI + PDF certificates. Not an API. |
| PVPO Online Dashboard (POD) | Public variety-detail UI launched 2025-09-01 after PII-driven removal of full applications from CMS. Not a documented API. |
| ePVP | Applicant filing/status system. Authenticated, not a public extract API. |
| GRIN application-status DB | ARS-maintained companion. Not used in this prototype. |
| UPOV feed | PVPO sends application updates to PLUTO monthly. |

Live workbook: 17,756 rows. Header row 2. Fields: Application #, Variety Name, Experimental Name, Scientific Name, Common Name, Applicant, Application Date, Certificate Status, Status Date, Issued Date, Years Protected.

Berry slice: **57 rows** (Strawberry 22, Raspberry 13, Blackberry 11, Blueberry 10, Blueberry rootstock 1). Status: 33 Application Pending, 24 Certificate Issued.

Licensing: US government public status list. Reuse as bibliographic registry data. Not a legal conclusion.

Update frequency: monthly (AMS statement).

## 2. USDA integration recommendation

**Activate first.** Parse the XLSX → existing `import_registry_rows` / inbox Variety candidates (`tier_1_national_register`). Shared qualifier is irrelevant here; this is an authoritative registry, not news.

Do not scrape CMS/POD HTML. Do not treat POD as an API until USDA documents one.

## 3. UPOV PLUTO access model

WIPO account required. No public consumer API. Do not scrape authenticated pages.

- **Standard:** free search, one results page, print/distribute up to 100 records, **no download**.
- **Premium:** CHF 750 / year / individual seat. UI Excel download of search results. Officials of UPOV members / designated contributors get Premium features without that fee.
- Bulk contribute path is for **data contributors**, not consumers.
- Completeness: members are not obliged to supply data or all fields. PLUTO is **not** the official publication.
- Cadence: updated after authorities send data; not a SLA.

## 4. UPOV cost / licensing

CHF 750 ≈ USD 850 / seat / year (FX varies). Auto-renews; 60-day written cancel.

Terms of use (UPOV, updated 2025-06-03) — **vendor-review flags, not legal advice**:

- Derivative databases from PLUTO data are a non-authorized use except ≤100 records.
- Commercial dissemination of PLUTO or its data is a non-authorized use.
- Premium users may download unlimited records but may **distribute** only up to 100; analysis/reports using more than 100 require **written UPOV permission**.
- Per-seat, non-transferable.

**SaaS implication:** productizing PLUTO as a customer-facing derived registry is not licensing-safe on the public ToS. Internal analyst reconciliation of ≤100 rows after Premium download is the only bounded prototype this repo implements.

## 5. UPOV integration recommendation

**Do not activate for production SaaS.** Keep as `NORMALIZATION_REFERENCE`. National PVPO/CPVO remain authoritative. Parser accepts an operator-exported file and hard-fails over 100 rows or HTML/login payloads.

## 6. USPTO best structured route (2026)

PatentsView PatentSearch API is in transition to USPTO Open Data Portal (`data.uspto.gov`). Legacy PatentsView keys are not ODP keys. ODP requires a USPTO.gov account + API key (`X-API-KEY`).

Best structured path already in-repo: `app/services/patent_monitor/uspto_odp.py` → `POST https://api.uspto.gov/api/v1/patent/applications/search`.

Do not automate Patent Public Search UI. Bulk datasets exist on ODP for offline jobs; not needed for a 25-row berry prototype.

This environment: `BIOS_USPTO_ODP_API_KEY` **absent**. No live ODP calls.

## 7. USPTO prototype results

Query builder (`berry_queries.py`) covers blueberry/Vaccinium, strawberry/Fragaria, raspberry, blackberry/Rubus, plus named assignees. `parse_odp_results` is fixture-proven. Live result: **not executed** (no key). Existing Google Patents JSON XHR path remains a discovery fallback in patent-monitor; this mission does not expand it.

## 8. Google Patents Public Datasets

Documented BigQuery datasets:

- `patents-public-data.patents.publications` — bibliographic
- `patents-public-data.google_patents_research.publications` — English title/abstract (possibly translated), `embedding_v1`, URL

On-demand price: **$6.25 / TiB** after **1 TiB / month free**. Minimum billable 10 MiB / query.

No giant scans. Bibliographic SQL is `LIMIT <= 50` with berry/assignee filters. Similarity uses `VECTOR_SEARCH` on a `LIMIT 2000` berry-title subset plus one query publication number.

## 9–10. Semantic patent prototype / BigQuery cost

`GOOGLE_CLOUD_PROJECT` and `gcloud` **absent**. No live bytes processed.

Dry-run fixture: 8,000,000 bytes → estimated **$0.000047** on-demand before the free-tier offset (effectively $0 inside the 1 TiB free month).

A full `VECTOR_SEARCH` on ~110M research rows without a prefilter would be an unacceptable scan and is refused by the module (`LIMIT` required).

## 11. CatchAll live-tested?

**No.** `NEWSCATCHER_API_KEY` / `CATCHALL_API_KEY` absent. Credentials were not invented.

CatchAll is an **async** job API (validate / initialize / submit / status / pull). Typical job: 10–15 minutes, billed **per validated record** (~$0.10). 50k+ pages scanned per job. Not a drop-in Google News RSS replacement.

`CatchAllDiscoveryProvider` implements `DiscoveryProvider` for bake-off compatibility. The default bake-off **does not slice-loop it** (54 jobs would be slow and expensive). Monitors are not created.

## 12–14. CatchAll benchmark / vs Google / Perplexity / unique gains

Not live. Bake-off reports `catchall_probe.tested = false`.

Documented commercial terms (vendor pages, 2026): 2,000 free credits on signup; paid from ~$50 / 6,000 credits; $0.10 per validated record. Identical queries are non-deterministic.

Google vs Perplexity remains the live pair from Retrieval Provider Bake-Off V1 (PR #207). APITube key absent.

Unique-source gains from CatchAll: **unmeasured**. Architecture is ready for one operator `CATCHALL_LIVE_PROBE` job later.

## 15. HortiDaily current collector state

Already collected: `source-20260819-hortidaily`, `article_rss`, `https://www.hortidaily.com/rss.xml`.

Live 2026-09-01: site-wide RSS 200. `rss.xml?section=breeding|retail|research|...` returns the **identical** 23,810-byte payload (sha `3b7a50738ab2`). Category RSS is not real coverage.

Sitemap index → leaf `https://www.hortidaily.com/sitemap/news/2026/` (urlset, Google news namespace, berry slugs in article paths).

robots.txt: `search=yes`, `ai-input=no`, `ai-train=no`. Collector stays body-light.

## 16. HortiDaily changes

No new Source onboard. No HortiDaily-only scraper.

Generic `sitemap_xml` now keeps `news:title` and `news:publication_date` when the leaf uses the news sitemap namespace. Operator can later add a sitemap Source with `include_url_patterns` for `blueberry|strawberr|raspberr|blackberr`. Existing RSS Source is unchanged.

## 17. Authoritative-layer architecture

| System | Class | Role |
|---|---|---|
| USDA PVPO XLSX | AUTHORITATIVE_REGISTRY | National PVP facts → Variety candidates |
| UPOV PLUTO | NORMALIZATION_REFERENCE | Cross-jurisdiction index; not official; ≤100-row operator export |
| USPTO ODP | AUTHORITATIVE_REGISTRY | Structured US patents/applications |
| Google Patents BigQuery | STRUCTURED_DATASET | Bibliographic + bounded similarity |
| Google Patents JSON (existing) | DISCOVERY_PROVIDER | Patent-monitor fallback |
| NewsCatcher CatchAll | DISCOVERY_PROVIDER | Async event enumeration; not news RSS |
| HortiDaily | SPECIALIST_SOURCE | Trade press; RSS now, sitemap filter later |

National registry → authoritative record. PLUTO → optional global normalization. Do not invert that.

## 18. SaaS licensing risks (flags, not conclusions)

- **UPOV:** derivative DB + commercial dissemination + >100-record reports. Written permission required. Highest SaaS risk.
- **CatchAll:** vendor ToS for storing/redistributing full text and validated events needs commercial review before production monitors or customer-facing resale.
- **BigQuery public patents:** Google public-dataset terms; query cost is the practical limit.
- **USPTO ODP:** free with account; key is personal/org; do not log it.
- **USDA XLSX:** public government table.
- **HortiDaily:** `ai-input=no` — do not feed article bodies into generative models.

## 19. Estimated monthly cost

FX: CHF 750 ≈ USD 850.

| | Dogfood | Small SaaS customer | Enterprise |
|---|---:|---:|---:|
| USDA PVPO | $0 | $0 | $0 |
| USPTO ODP | $0 | $0 | $0 |
| BigQuery (bounded) | $0 (free 1 TiB) | $0–20 | $50–200 if scans leak |
| CatchAll | $0 (no key) or trial credits | $50 (6k credits) | $500+ / custom |
| UPOV Premium | $0 (do not subscribe) | $850/seat **internal only** | $850×N + written permission; still not a derived product |
| **Recommended spend** | **$0** | **$50 if CatchAll trial earns its keep** | **CatchAll custom; UPOV legal first** |

## 20–22. Tests / CI / merge

See completion report.

## 23. Recommended activation order

1. USDA PVPO monthly XLSX → inbox Variety candidates
2. USPTO ODP when `BIOS_USPTO_ODP_API_KEY` exists
3. Optional HortiDaily current-year sitemap Source with berry slug filters (generic adapter)
4. Bounded BigQuery bibliographic when a GCP project exists
5. One CatchAll probe (`CATCHALL_LIVE_PROBE`) after commercial review — no production monitors
6. UPOV Premium only after legal review, operator-export, 100-row cap
