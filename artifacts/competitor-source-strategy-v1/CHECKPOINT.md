# Competitor Source Strategy V1 — checkpoint (2026-09-15)

Branch: `research/competitor-source-strategy-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-source-strategy-v1`,
based on `4e54401da040be937cc68877f410b4da7b646d65`. Research and
import-planning mission only. No acquisition code implemented, no source
activated, no collection run, no canonical data changed.

## What was built

1. `data/imports/competitor-source-strategy-2026-09-15/competitor-source-strategy-v1.json`
   — the 33-row machine-readable contract, keyed to the existing
   `canonical_entity_id` from the prior mission's reconciliation matrix.
2. `data/imports/competitor-source-strategy-2026-09-15/competitor-source-strategy-matrix.md`
   — human-readable 33-row matrix plus per-row unresolved questions.
3. `data/imports/competitor-source-strategy-2026-09-15/candidate-source-import-proposal.json`
   — 21 explicitly `NONCANONICAL` Source-shaped proposals across 19
   companies with a confirmed live discovery mechanism.
4. `data/imports/competitor-source-strategy-2026-09-15/first-activation-wave.json`
   — 12 entries (8 already-configured, 4 new highest-confidence candidates).
5. `docs/v2/COMPETITOR-SOURCE-STRATEGY-V1.md` §5 — the required dedicated
   California Giant alternative-coverage assessment (re-citing, not
   re-diagnosing, the already-established `fix/astra-news-reader` finding).
6. `data/imports/competitor-source-strategy-2026-09-15/adapter-gap-analysis.json`
   — every confirmed candidate fits an existing adapter
   (`article_rss`/`sitemap_xml`); 4 real access-limitation findings
   (California Giant, UC Davis, Mountain Blue's Content-Signal robots.txt,
   Well-Pict's inconclusive connection failure) needing a policy/client
   decision, not a new adapter type.
7. `data/imports/competitor-source-strategy-2026-09-15/duplicate-risk-assessment.json`
   — 6 named risk categories (SunBelle's 3 domains, a possible
   AgroBerries/BerryWorld corporate-family overlap, a possible Gem-Pack/
   Well-Pict merger, aggregator-needs-entity-scoping for 5 no-website
   companies, expected-low-cadence sources, and The Berry Collective's
   identity ambiguity as a do-not-activate case).
8. `tests/test_competitor_source_strategy_v1.py` — 23 deterministic tests,
   all passing, making no network calls.
9. This checkpoint and `NEXT-AGENT-PROMPT.md`.
10. `scripts/_gen_competitor_source_strategy_v1.py` — the kept, documented,
    non-runtime generator that produced 1–4, 6, 7.

## Research method (summary — full detail in the doc)

Real public-web search (WebSearch) for each of the 33 roster labels'
official domain/newsroom, followed by direct `curl` checks of `robots.txt`,
homepage, and likely feed/sitemap paths using this project's own honest,
declared User-Agent (`berry-intelligence-os-article-acquisition/1.0`) —
never a spoofed browser identity, never a bulk crawl.

## Verification

- Focused: `tests/test_competitor_source_strategy_v1.py`: **23 passed**
  (`focused-tests.txt`).
- `scripts/validate_records.py`: **all validated records passed**
  (`record-validation.txt`) — confirms the prior mission's canonical data
  was not disturbed.
- `git status --porcelain` limited to `data/entities/`,
  `data/relationships/`, `data/evidence/`, and
  `data/configuration/sources.json` returns nothing (checked as part of
  the test suite itself, see `test_no_changes_to_sources_configuration_file`
  and `test_no_new_variety_entities_were_created`).
- Full suite was **not** run — out of this mission's explicit scope.

## Roster coverage

**SOURCE STRATEGY ROSTER: 33/33**
**SILENTLY OMITTED: 0**
**LIVE SOURCES ACTIVATED: 0**
**LIVE COLLECTION RUNS: 0**

## Tallies

- Official domains found: 28 of 33 (Denning Blueberries, Expoberries,
  Marionnet, Splendor Produce, and IQ Berries have no confirmed own
  domain — IQ Berries publishes through a licensing partner's page
  instead).
- Official newsrooms/press/blog sections found: 12 (Wish Farms, Ozblu,
  Oishii, Fruitist, plus 8 more with a real news/blog/press section
  identified even where not proposed for the first wave).
- Confirmed-live feeds (RSS/Atom, `HTTP 200`): 8 (Gem-Pack Berries,
  Oishii, Ozblu, Perfection Fresh, Smart Berries, SunBelle, The Berry
  Collective, Wish Farms).
- Confirmed-live sitemaps (`HTTP 200`): 5 (Australasian Plant Genetics,
  Fruitist, Mountain Blue, Plant Sciences, plus AgroBerries via its
  robots.txt-declared sitemap).
- Monitoring-state distribution: `source_configured_never_run` 8,
  `discovery_pending` 18, `no_supported_source` 5, `source_blocked` 2
  (California Giant, UC Davis).
- Existing-adapter compatible: all 21 candidates with a confirmed
  discovery mechanism (`article_rss` or `sitemap_xml`, both already in
  `app/services/media_discovery.py`'s `ADAPTER_TYPES`).
- New adapter required: 0 — this roster did not surface a need for a new
  adapter type.
- Manual monitoring recommended (no automated candidate at all): 5
  (Denning Blueberries, Expoberries, Marionnet, Splendor Produce, IQ
  Berries — each with a stated manual fallback, never fabricated).
- Blocked candidates: 2 confirmed (California Giant via a real A/B
  TLS-fingerprint test; UC Davis via a repeatable HTTP 403), plus 1
  inconclusive (Well-Pict — connection failure, not a confirmed block,
  needs a retry from a different network path).

## What is deliberately NOT done here

- No Source record was added to `data/configuration/sources.json`.
- No collection script was run.
- No entity, relationship, tier, priority, region, or alias was changed.
- No Variety entity or relationship was created.
- California Giant's TLS-fingerprint block was not bypassed, disguised,
  or worked around — only re-cited from the branch that already
  diagnosed it.
- The Berry Collective, despite a technically-ready feed, was NOT
  recommended for activation due to unresolved identity ambiguity.

## Next concrete acceptance test for a follow-up session

1. Human review of `candidate-source-import-proposal.json` — for each of
   the 12 first-wave entries, an operator decides whether to actually
   register a real Source record (through existing governance, not this
   branch) and, for the 8 already-configured ones, whether to simply run
   `scripts/run_collection.py` against them.
2. A deliberate policy decision on Mountain Blue's Content-Signal
   robots.txt convention before onboarding it.
3. A UC Davis access re-check (curl-vs-httpx A/B, the same diagnostic
   already proven on California Giant) before deciding whether it is a
   genuine block or something narrower.
4. A Well-Pict connectivity retry from the production/collection
   environment (this research environment's connection failure was
   inconclusive).
5. Resolve The Berry Collective's identity ambiguity with a human before
   ever proposing it for activation.
6. Do not silently expand the 5 `no_supported_source` entries (Denning
   Blueberries, Expoberries, Marionnet, Splendor Produce, IQ Berries)
   without new real evidence — no further speculative domain-guessing.
