# Berry Intelligence Search Frontier Mission

## Outcome

Make Berry Intelligence the first place an analyst goes to understand what changed, what fits a market or production system, and what evidence supports the answer. Prove the reusable platform on the 2027 Northern Hemisphere commercial blackberry season, then test it across the four berries. A saved result must remain auditable against its dated source.

## Baseline

Global Search on the checked-in archive resolves Ervin and NC 740 but misses Blackberry Floricans, blackberry floricane, and the full season question. The Search form drops URL crop scope, malformed dates can throw, and newest-first sorts after truncation. Existing source observations already describe Ervin's fruiting habit and international license, while cultivar search lacks structured access to them. Production login prevented reproducing the reported dropdown crash. Release #411 shipped useful research improvements. Its historical benchmark showed 8/10 direct hits for the typo and a roughly 36-second cold discovery p95. Broader Google parity remains open. Preserve those historical scores.

## Workstreams and exit gates

1. **Reliable search.** Preserve explicit scope on submit, back, and reload. Label effective scope. Validate user dates. Sort before limiting and distinguish returned counts from total hits. Test from the normal HTML and API entry points, including crop switching and empty or invalid requests.
2. **Cited season pilot.** Build a filterable blackberry comparison using existing variety identities, evidence, rights, observations, and review controls. Expose fruiting habit separately from harvested cane, region, trial site and system, harvest window, market, and evidence status. Keep publication, trial, release, grant, license, listing, and confirmed stock dates distinct. Include Ervin / NC 740, Immaculate, Ponca, Caddo, Ouachita, Von, Loch Katrine, Marion and Columbia Star as source-backed cases. Fontana is a strict-filter negative. Horizon tests relevance to second-year production. Mark unknown 2027 stock and use the original source passages. Explain why each row matched.
3. **Shared retrieval.** Reuse the existing topic planner, identity registry, passage capture, source cache and review boundaries. Unify effective query and evidence semantics across Search, Varieties, Research and Reports incrementally. Preserve explicit archive and selected-source constraints. Return local results promptly. Make public discovery explicit and progressively display its state. Keep provider failure, extraction failure, thin coverage and a genuine zero separate.
4. **Source coverage.** Build a versioned list of up to 50 priority domains with crop, market, language, source type, permitted acquisition method, refresh cadence and coverage health. Start with NC State, Arkansas, Southern Region Small Fruit Consortium, Oregon State, James Hutton, Global Plant Genetics and official plant-rights sources. Prefer original breeder catalogs, trial publications and PDFs, nursery listings, CPVO/USDA PVPO records and scholarly metadata. Use multilingual open-web discovery to find gaps beyond the list. Compare Google organic, a curated Google search surface, existing providers and any authorized additional provider by incremental verified events. Review terms before persisting provider output or importing third-party material.
5. **Proof.** Reuse the existing search harness and add sealed holdouts across crops, markets and languages. Compare contemporaneous same-scope results by distinct-event recall, direct precision at ten, citation support, first useful result and complete-result latency, cold and warm, and actual provider cost. Keep unassessable cases visible. Track failure stage from discovery through ranking. Require reviewed evidence for trusted claims. Claim parity only for measured scope.

## Execution and review

Start with local reliability regressions, then deliver a browsable blackberry season pilot and evaluation packet. Work on an isolated branch from canonical. Preserve existing runtime and review gates. Public query transmission remains explicit. Continue local implementation, source inspection, tests and benchmarking autonomously. Bring a concrete diff, measured results and remaining tradeoffs for any required trust approval, production release or paid-provider decision.

## Execution evidence

- `f198dead` preserves crop scope, validates dates and sorts before capping. The local service checks passed. Full FastAPI tests cannot collect with the pinned `ijson` dependency missing from the current interpreter.
- `1c6cbd6d` adds the initial season comparison at `/varieties/blackberry-season` and links it from Search and Varieties. Five focused tests passed, including template rendering. This is a bounded source-reported pilot with nine floricane cultivars and two primocane comparison cases. It does not promote canonical traits.
- The first coverage audit matched exact URL hosts against the tracked source registry and compared fragment-stripped URLs against checked-in published Evidence. Four of eleven pilot hosts appear in the registry and none of the eleven exact URLs matched published Evidence. This excludes aliases, redirect equivalence, runtime records and alternate coverage. Use those distinctions in the next registry and benchmark pass.
- The [priority source inventory](SEARCH-FRONTIER-SOURCE-COVERAGE-V1.md) records the first acquisition and refresh candidates. Known pilot URLs are now eligible as bounded Research and combined Report discovery leads. Original captures still go through the existing passage checks and review gates.
- The nine-query [offline diagnostic](../../artifacts/search-research-quality/frontier-blackberry-local-baseline-2026-11-09.json) measured 0.805 seconds median and 1.326 seconds p95 for the local retrieval stage. The typo, corrected wording and second-year-cane paraphrase all returned zero archive results. It did not measure full-route latency, provider coverage or Google parity.
- The first [eight-query credit-free benchmark](../../artifacts/search-research-quality/frontier-holdout-2026-11-09.json) covered four crops and English, Spanish, Italian and French. All eight discovery runs reported provider failure in this environment. The snapshot records a connectivity baseline, with 5.123 seconds median and 9.379 seconds p95 including failed discovery. It provides no ranking or parity evidence. The baseline predates the repair that retains known primary-source leads during a metadata-provider outage. The next comparison needs reachable providers and contemporaneous Google organic results, followed by source-inspected pooled judgments.

## References

- [Previous search quality mission](SEARCH-RESEARCH-QUALITY-V1.md)
- [Release #411](SEARCH-RESEARCH-RELEASE-411-2026-11-03.md)
- [Intelligence expansion build guide](INTELLIGENCE-EXPANSION-BUILD-GUIDE.md)
- [NC State Ervin introduction](https://rubus.ces.ncsu.edu/news/meet-ervin-blackberry/)
- [Arkansas Immaculate trial update](https://smallfruits.org/2026/01/sweet-ark-immaculate/)
- [Google Custom Search API transition](https://developers.google.com/custom-search/v1/overview)
