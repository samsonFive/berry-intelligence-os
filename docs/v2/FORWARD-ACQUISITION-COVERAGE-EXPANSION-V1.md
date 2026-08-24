# Forward Acquisition Coverage Expansion V1

**Measured:** 2026-08-24

**Scope:** recurring forward discovery and rich-body acquisition only

**Trust boundary:** unchanged; every new item remains Discovery -> acquisition -> Publication Review -> trusted publication

This mission deliberately did not run historical `REACQUISITION-PILOT-25`, affirm any Source Fidelity artifact, call a model, create an Atomic proposal or qualification marker, or enable extraction. The eight Source Fidelity candidates created by the accepted PILOT-10 remain human-review work owned by the Source Fidelity Review UX lane.

## Coverage audit

The canonical registry began with 174 enabled Sources, 53 machine-discoverable Sources, and 14 direct `article_rss` Sources. Two of those 14 records point at the same FreshPlaza feed, so record count is not the same as unique publication-universe count. Only three direct article feeds were linked to monitored Company entities (Hortifrut, Planasa, SanLucar). The remaining recurring company monitoring was sparse or used Google News wrappers.

| Measure | Before | After | Change |
|---|---:|---:|---:|
| Enabled Sources | 174 | 194 | +20 |
| Machine-discoverable Sources | 53 | 73 | +20 |
| Direct article RSS | 14 | 31 | +17 |
| Bounded official sitemap | 0 | 3 | +3 |
| Direct Company/newsroom Sources | 3 | 9 | +6 |
| Blueberry discoverable Sources | 44 | 62 | +18 |
| Raspberry discoverable Sources | 28 | 42 | +14 |
| Blackberry discoverable Sources | 27 | 42 | +15 |
| Strawberry discoverable Sources | 31 | 44 | +13 |

The large all-source counts in the registry overstate operational coverage: 121 of the original 174 records had no discovery block. Actor classification therefore uses recurring direct coverage, not mere presence in `sources.json`:

- **GOOD SOURCE COVERAGE:** Hortifrut, Planasa, SanLucar; after expansion also Global Plant Genetics, BerryWorld, Fall Creek/SEKOYA, Naturipe, Costa Group, the University of Arkansas, James Hutton, UF IFAS, NC State, and USHBC.
- **SOME SOURCE COVERAGE:** Driscoll's and Costa previously had wrapper-based company search; several actors appeared indirectly in trade feeds.
- **NO DIRECT RECURRING SOURCE:** most monitored companies before this mission, including Global Plant Genetics, BerryWorld, Fall Creek, Naturipe, and the public breeding programs onboarded here.
- **NO RICH ARTICLE SOURCE:** actors whose official endpoint was absent, empty, blocked, or only exposed consumer/utility pages remain in this class (see rejected/watch inventory).

No competitor ranking was created.

## Deterministic expansion manifest

Every onboarded Source has an identifiable publisher, a direct machine-consumable endpoint, an explicit berry/geography/language scope, a per-poll cap of 10, and a real final-article acquisition probe. Broad institutional/trade feeds still pass through the existing deterministic relevance screen before body acquisition or draft creation.

| Source | Actor / publisher | Berry | Geography | Type | Discovery | Probe | Cadence | Action |
|---|---|---|---|---|---|---|---|---|
| Global Plant Genetics Newsroom | GPG | All four | Global | Company newsroom | RSS | 488 words / 3,625 chars | Weekly | ONBOARD |
| James Hutton Institute News | James Hutton | Raspberry, Blackberry | Europe | Research / breeder | RSS | 473 / 3,138 | Weekly | ONBOARD |
| Arkansas AAES News | University of Arkansas | Blackberry | North America | Research / breeder | RSS | 533 / 3,672 | Weekly | ONBOARD |
| UF IFAS News | University of Florida | Strawberry, Blueberry | North America | Research / breeder | RSS | 586 / 3,530 | Weekly | ONBOARD |
| NC State CALS News | NC State | All four | North America | Research / breeder | RSS | 804 / 4,939 | Weekly | ONBOARD |
| BerryWorld Newsroom | BerryWorld | All four | Global | Company newsroom | Official news sitemap | 221 / 1,414 | Weekly | ONBOARD |
| Fall Creek Newsroom | Fall Creek | Blueberry, Raspberry, Blackberry | Global | Company newsroom | Filtered official sitemap | 892 / 6,460 | Weekly | ONBOARD |
| Naturipe Farms Newsroom | Naturipe | All four | North America / global | Company newsroom | Filtered official post sitemap | 521 / 3,429 | Weekly | ONBOARD |
| SEKOYA News | Fall Creek / SEKOYA | Blueberry | Global | Company newsroom | RSS | 778 / 4,486 | Weekly | ONBOARD |
| Costa Group Newsroom | Costa Group | Blueberry | Asia-Pacific / global | Company newsroom | RSS | 300 / 2,065 | Weekly | ONBOARD |
| Blueberries Consulting Articles | Blueberries Consulting | Blueberry | Latin America / global | Trade press | RSS, Spanish | 972 / 6,143 | Daily | ONBOARD |
| British Berry Growers News | British Berry Growers | All four | Europe | Association | RSS | 510 / 3,576 | Weekly | ONBOARD |
| Perishable News - Produce | Perishable News | All four | North America / global | Trade press | RSS | 582 / 3,508 | Daily | ONBOARD |
| Produce Business | Produce Business | All four | North America / global | Trade press | RSS | 667 / 4,269 | Daily | ONBOARD |
| USHBC - Blueberry.org | USHBC | Blueberry | North America | Association | RSS | 471 / 3,001 | Weekly | ONBOARD |
| Specialty Crop Grower | Specialty Crop Grower | All four | North America | Trade press | RSS | 421 / 2,912 | Daily | ONBOARD |
| Berries Australia | Berries Australia | All four | Asia-Pacific | Association | RSS | 627 / 4,397 | Weekly | ONBOARD |
| Redagricola Articles | Redagricola | All four | Latin America / global | Trade press | RSS, Spanish | 1,897 / 12,123 | Daily | ONBOARD |
| PortalFruticola | PortalFruticola | All four | Latin America / global | Trade press | RSS, Spanish | 441 / 2,662 | Daily | ONBOARD |
| Aneberries Mexico | Aneberries | All four | North America | Association | RSS, Spanish | 70 / 485 | Weekly | ONBOARD |

The 20-source sequential adapter proof returned `status=ok` for all 20, with zero feed failures and zero item-normalization failures. The configured cap staged 197 private discovery items (19 x 10 plus SEKOYA's complete seven-item feed); it created no Evidence, draft, review event, transcript, or model artifact.

## Rich-body measurement

The standardized current-path probe produced a platform-classified full body for 20/20 accepted Sources (100%). To avoid overstating that single-page result, additional stress probes were retained: one older Fall Creek page was partial, and five Aneberries paths produced three full, one partial, and one empty body. Across every accepted-source article path exercised, including those stress probes, 22/25 were full bodies (88%), two were partial (8%), and one failed empty-body extraction (4%). This is acquisition capability, not review yield and not a prediction of analyst decisions.

Best measured source types were direct company/newsroom and publisher/association RSS. Direct company/newsroom paths were 6/6 full on the standardized current-path probe. Spanish-language direct trade feeds were particularly rich (Blueberries Consulting 6,143 chars; Redagricola 12,123; PortalFruticola 2,662). Sitemap discovery worked for official article pages, but only with URL filters, newest-first ordering, and a cap.

## Sitemap safety and Source Health

`sitemap_xml` accepts only a leaf `<urlset>`; it never follows a sitemap index or scrapes an HTML listing. Source configuration can include and exclude URL patterns, sort by publisher `lastmod`, and cap each poll. A live Fall Creek sitemap contained a corrupt future timestamp (`8842-08-23`). The adapter now rejects implausible pre-2000 or future dates; the corrected proof selected the real newest article dated 2026-08-19. Tests cover leaf-only behavior, filtering, newest-first capping, malformed future dates, and invalid limits.

This is an adapter in the existing discovery registry. It writes the same `inbox/discovered_media` items and `_state` files as every other source, so existing Source Health/cadence semantics remain authoritative. There is no second monitoring system.

## Duplicate and wrapper control

No FreshFruitPortal berry-tag subfeeds or Fruitnet regional feeds were added because they emit the same publisher universe as existing Sources. The existing duplicate FreshPlaza configuration was observed but not destructively reconciled in this mission. Written channels were added alongside existing podcast/video channels only where the medium and publication universe are distinct (USHBC, Redagricola, Blueberries Consulting).

Costa now has a direct official feed; its existing Google News source remains discovery-only and is no longer the only recurring company path. No new Google News source was added. Every new rich-article path is a publisher URL, never a Google News wrapper.

## Rejected / watch inventory

| Candidate | Probe result | Decision |
|---|---|---|
| Driscoll's sitemap | 984 URLs dominated by consumer recipes; no stable newsroom subset | WATCH / NEEDS WORK |
| Wish Farms feed | 403 under the application user agent | WATCH / NEEDS WORK |
| Florida Strawberry Growers feed | 403 under the application user agent | WATCH / NEEDS WORK |
| Produce Blue Book | Feed works; article path 403/blocked | REJECT for rich-body onboarding |
| TopFruit | Five paths: 2 full, 3 partial; newsletter landing pages mostly thin | WATCH / NEEDS WORK |
| Berries South Africa | Five paths: 0 full, 5 empty-body failures | REJECT |
| CIOPORA sitemap | Repeated 429 response | WATCH / NEEDS WORK |
| United Exports | Feed 403 | WATCH / NEEDS WORK |
| Rijk Zwaan | Feed/sitemap 403 | WATCH / NEEDS WORK |
| Eurosemillas | Feed 403; sitemap absent | WATCH / NEEDS WORK |
| Onubafruit | No usable feed; sitemap had no article inventory | WATCH / NEEDS WORK |
| Mountain Blue | Sitemap had no recurring news subset | WATCH / NEEDS WORK |
| California Giant | Valid feed with zero items | WATCH / NEEDS WORK |
| Agroberries | Feed absent/empty | WATCH / NEEDS WORK |
| International Raspberry Organization | Valid feed with zero items | WATCH / NEEDS WORK |
| North American Raspberry & Blackberry Association | Valid feed with zero items | WATCH / NEEDS WORK |
| UC ANR Strawberries and Caneberries | Publisher-declared feed returns 403 to the application client | WATCH / NEEDS WORK |
| Bloom Fresh | Rich feed, but sampled/current publication universe was not berry-relevant | REJECT for this mission |
| Ontario Berries | Current feed was consumer recipes, not competitive intelligence | REJECT |
| FreshFruitPortal berry-tag feeds | Working but duplicate the existing publisher universe | REJECT duplicate |
| Fruitnet regional feeds | Live probes returned the same Produce Plus articles/hash | REJECT duplicate |

## 30-day forward estimate

The capped discovery sample contained 110 items dated in the preceding 30 days. Metadata-only deterministic screening classified 20 as directly berry-relevant and 27 more as requiring a real body check. This is a truncated window for high-cadence feeds and includes broad-feed noise; it is not a claim of 110 useful items.

A cautious operating estimate is **20-40 new rich publication candidates per 30 days after relevance screening and deterministic deduplication**. The lower bound is anchored to the 20 directly relevant metadata hits in the real 30-day sample. The upper bound allows only part of the 27 body-check population to survive Stage B and discounts cross-publisher duplication. The 88% expanded-path rich-body result supports richness but does not establish relevance or analyst acceptance.

At that rate, forward collection is a credible path from dozens toward hundreds of rich source artifacts over several months. It is not evidence for hundreds of rich candidates per month, and human Publication Review remains the throughput/trust gate.

## Historical reacquisition stop gate

`REACQUISITION-PILOT-25` remains **RUN AFTER HUMAN REVIEW** of the existing eight Source Fidelity candidates. Nothing in this forward-source result changes that prerequisite.

## Production deployment proof

PR #138 merged cleanly as `adc1e5feabfca1c62b1e789a73da1ba0bfbbba0e` after all four required GitHub checks passed. Immediately before mutation, the production timer was paused and the established container-backed procedure created and independently verified `/var/backups/berry-intelligence-os/berry-runtime-20260824T025753Z.tar.gz`. Its SHA-256 is `ff6f0e85e3282a5dfe98af0c9c461740da879694e480e2173286b983cc127964`; its manifest covers `data` and `inbox` and contains 12,009 checksummed entries.

Production fast-forwarded from `b19c0dd5c4d5c26668c3075a8ccd20a1c0ea2626` to `adc1e5feabfca1c62b1e789a73da1ba0bfbbba0e` and rebuilt only the app service. Startup configuration sync reported `sources_added: 20`; all 2,656 pre-deploy data files, 9,352 inbox files, and 1,584 private Evidence files remained present before the bounded proof. Internal and public `/healthz` returned 200. The timer was restored enabled/active, its immediate dispatcher check exited `0/SUCCESS`, and its next invocation was scheduled normally. The fast operator status completed in 3.94 seconds, found no active collection lock, reported the new backup `HEALTHY` and verified, and confirmed extraction disabled, unconfigured, unqualified, and unrunnable.

The production registry now contains all 194 Sources. It exposes 70 machine-discoverable Sources rather than canonical's 73 because three pre-existing Source records had already diverged from their canonical configuration before this mission. Startup source sync is deliberately additive-only: it safely added all 20 new identities but did not overwrite those older runtime-owned records. This is the remaining Source-configuration ownership limitation; no destructive update or manual copying was used.

The one-source-at-a-time production proof used British Berry Growers with `--max-items 5` and external model access explicitly absent. Ten feed items were visible; the newest five were selected. Four were relevant, acquired, and staged as private Publication Review drafts; one zero-signal item was correctly skipped. All four acquired bodies were platform-classified `FULL_ARTICLE` (457-682 words, 13-19 paragraphs), with zero thin bodies, acquisition failures, enrichments, publications, trust changes, or Atomic artifacts. An identical bounded rerun created zero drafts and reported four duplicates plus the same irrelevant skip. Its normal `_state` record persisted `status: ok`, 10 already known, and zero feed/item failures. After this proof, trusted data remained at 2,656 files; inbox growth from 9,352 to 9,367 consisted of the expected ten discovered items, one Source Health record, and four private drafts, with Evidence count 1,584 to 1,588.

Cursor's separate Source Fidelity Review UX PR #139 merged after this deployment and advanced repository canonical to `35441458c256cd11ca42594f45f469a2f85771d2`. It was intentionally not deployed or modified by this lane. The acquisition proof therefore identifies deployed runtime `adc1e5fe` separately from the newer repository canonical, preserving the explicit lane boundary.
