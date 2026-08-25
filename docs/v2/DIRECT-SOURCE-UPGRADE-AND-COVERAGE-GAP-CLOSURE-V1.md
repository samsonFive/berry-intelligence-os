# Direct Source Upgrade + Coverage Gap Closure V1

## Scope and decision rule

This mission gap-audits the canonical Source portfolio after Forward Acquisition Coverage Expansion V1. It does not replace generic search, add a new adapter, change cadence/freshness/health semantics, run historical reacquisition, or make trust/review decisions. A candidate is accepted only when the application's real collector can read a bounded official endpoint and the existing acquisition path can obtain useful bodies.

## Canonical baseline

The implementation started from canonical `df938c4901c2a8942f9d80e7ef0268ef319d97a9` (2026-08-25). The 194 canonical Sources included 73 machine-discoverable Sources: 31 direct article RSS, three bounded sitemap feeds, 22 news-search RSS, and 17 other supported adapters. One discoverable Source, Growing Produce - Berries, remains intentionally fetch-ineligible and `OPERATOR_ACTION_REQUIRED`.

Discoverable berry coverage was Blueberry 62, Strawberry 44, Raspberry 42, and Blackberry 42. Fifty-one of the 73 machine paths were non-search direct mechanisms. Fourteen non-search direct Sources had explicit Company linkage.

Production's mounted registry was separately observed at 194 configured and 69 collection-eligible. Its known additive-only divergence (the older Fresh Fruit Portal, Fresh Plaza, and Produce Report records) is protected runtime state and is not rewritten by this mission. Growing Produce is unchanged.

## Search-dependency and decision map

| Actor / area | Current path | Direct gap | Decision / proposed upgrade | Expected benefit |
|---|---|---:|---|---|
| Advanced Berry Breeding | Generic global caneberry search | Yes | Add official bounded RSS; link exact existing Company | First-party Raspberry varieties, trials, licences, and launches |
| The Summer Berry Company | Generic search / trade press | Yes | Add official bounded RSS; link exact existing Company | First-party caneberry growing, trials, awards, and partnerships |
| Freshuelva | Existing direct RSS, no Company link | Linkage gap | Preserve Source identity; add exact existing Company link | Correct watchlist/actor health attribution without provenance rewrite |
| Nova Siri Genetics | Existing direct RSS, no Company link | Linkage gap | Preserve Source identity; add exact existing Company link | Correct Strawberry breeder attribution without provenance rewrite |
| United Exports | Generic search / trade press | Yes | Do not add: real collector receives HTTP 403 | Keep search fallback; avoid a predictably failing Source |
| Wish Farms | Generic search / trade press | Yes | Do not add: RSS is visible but article acquisition receives HTTP 403 | Keep search fallback; no access workaround |
| Mountain Blue Genetics | Generic search / trade press | Yes | Do not add: broad sitemap has no stable article/news subset; media is a listing/PDF surface | Avoid broad crawling and weak item semantics |
| Onubafruit | Generic search / trade press | Yes | Do not add: candidate feed endpoints are 404; advertised sitemap is empty/broken | Avoid unproven endpoint |
| Driscoll's | Generic Company search plus indirect publishers | Yes | Do not add: 985-URL broad sitemap, no stable newsroom subset, consumer-heavy | Avoid marketing/recipe volume |
| Fruitist / Agrovision | Generic search / trade press | Yes | Do not add: 39-URL newsroom sitemap is consumer/sports-heavy; article probes were only 135/161 characters | Avoid thin, noisy intake |
| Rijk Zwaan | Generic search / trade press | Low | Do not add: broad vegetable newsroom; only one berry Evidence record | Evidence-weighted lead is not sufficient importance by itself |
| Eurosemillas | Generic search / trade press | Low | Do not add: broad/citrus newsroom and historical Strawberry relationship is no longer current | Avoid stale actor semantics |
| Caneberry organizations | Hybrid association, research, and generic caneberry search | Residual | Existing British Berry Growers, Berries Australia, Arkansas AAES, James Hutton and new ABB/TSBC paths are retained | Improve caneberry balance selectively; do not inflate count |

## Bounded access probes

| Candidate | Access and items | Dates / language | Body result | Adapter / overlap decision |
|---|---|---|---|---|
| Advanced Berry Breeding | HTTP 200; 10/10 bounded RSS items; exact collector 10 new, 0 failures | 2024-2026; English | Two production-image probes: 371 and 584 words | Existing `article_rss`; UTM parameters collapse to canonical publisher identity |
| The Summer Berry Company | HTTP 200; 10/10 bounded RSS items; exact collector 10 new, 0 failures | 2025-2026; English | Two production-image probes: 164 and 372 words | Existing `article_rss`; generic caneberry search remains complementary |
| United Exports | Browser-like request saw 10 items, but exact application collector received HTTP 403 | English | Earlier production-image probes were 411 and 1,631 words | Rejected because real runtime access is unacceptable; no user-agent workaround |
| Wish Farms | Feed HTTP 200 and 10 visible items | English | Current and caneberry article probes both HTTP 403 | Rejected; no bypass |
| Mountain Blue Genetics | Sitemap HTTP 200, 47 broad URLs | English | No item-level newsroom path; media page links PDFs | Rejected as unbounded/semantically weak |
| Onubafruit | News archive present; feed candidates 404; sitemap empty/broken | Spanish | No stable item feed to probe | Rejected |
| Fruitist | 39 sitemap URLs, 20 under `/news/` | English | Two article probes failed useful-body threshold (135/161 characters) | Rejected as thin/noisy |

The accepted feeds repeated against the same disposable inbox as 0 new / 10 already known each. This proves feed-level idempotence. Shared canonical URL normalization removes ABB's RSS tracking parameters, so direct and generic-search references to the same publisher URL use one canonical article identity while retaining discovery provenance where applicable.

## Implemented coverage change

Two Sources are added: Advanced Berry Breeding and The Summer Berry Company. Two existing direct Source identities are upgraded only with exact Company linkage: Freshuelva and Nova Siri Genetics. No Source is removed and generic search remains enabled.

| Measure | Before | After |
|---|---:|---:|
| Registered Sources | 194 | 196 |
| Machine-discoverable | 73 | 75 |
| Collection-eligible (Growing Produce excluded) | 72 | 74 |
| Non-search direct paths | 51 | 53 |
| Direct article RSS | 31 | 33 |
| Explicit Company-linked non-search direct | 14 | 18 |
| Blueberry discoverable | 62 | 63 |
| Strawberry discoverable | 44 | 45 |
| Raspberry discoverable | 42 | 44 |
| Blackberry discoverable | 42 | 43 |

These are Source-path counts, not a claim of complete market coverage. The material gain is direct actor attribution and first-party caneberry access, not the raw increase of two Sources.

## Cadence, freshness, health, and safety

Both new feeds use the established weekly cadence (604,800 seconds) and item limit 10. With no run history they enter the authoritative freshness contract as stale/never-run rather than making coverage falsely healthy. They use the existing Source Health/lifecycle records; no parallel state was introduced. Discovery remains private and untrusted. No extraction, publication, review, model, UI, or trust behavior changes.

## Conservative yield expectation

The bounded windows contain 20 candidates, but they span roughly a year and are not a monthly-rate sample. A conservative operating expectation is approximately 1-4 newly discovered candidates per month across both feeds, with perhaps 1-3 rich, relevance-screened private candidates. This is not an estimate of analyst-reviewed or trusted intelligence yield.

## Validation and production proof

Implementation-time validation is green: 179 focused tests and 1,719 full-suite tests passed; canonical record validation passed; the static build wrote 1,618 pages and its private-draft leakage scan passed; `git diff --check` is clean. CI, safe deployment, bounded production pilot, authoritative production freshness counts, and protected-runtime hashes are recorded here only after they have actually run.
