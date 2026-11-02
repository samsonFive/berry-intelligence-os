# Default sources and keyword effectiveness — pre-deployment review

October 27, 2026. Reviewed against `c93473f7`. Recommendation only: no default sources, monitors, schedules or production configuration were changed. Deployment remains on hold.

## Assessment

The current set has useful trade, corporate-action, Spanish-language, French-language, regulatory and specialist coverage. Its largest weaknesses are **collection-path gaps, short/general feed windows, missing crop-trait searches and limited native-language coverage**. Adding more broad berry queries alone would not resolve those weaknesses.

This audit checks configuration, code paths, eight live feed samples, two candidate primary pages and inspected public research sources. It is not a production yield audit: source-by-source discovered/relevant/body-acquired/reviewed counts and independent relevance judgments are unavailable in this worktree. Registry status fields are not a substitute for those measurements.

## Inventory

| Layer | Measured configuration | Interpretation |
|---|---:|---|
| Canonical Source registry | 265 entries | Includes manual references and historical research references |
| Enabled registry entries | 219 | Enabled does not imply an executable modern collector |
| Entries with discovery configuration | 96 | Four are not currently collection-eligible |
| Eligible for modern collection | 92 | Eligibility is not a successful latest fetch or acquired body |
| Enabled without discovery configuration | 123 | Some are intentionally manual; others are legacy keyword records |
| Legacy keyword entries without discovery adapters | 33 | Not modern collection paths; not proof of no indirect coverage |
| Deduplicated default discovery-query IDs | 94 | Excludes local custom examples and the new Floricane monitor |
| Industry/weekly shared default queries | 32 | Intentionally shared across workflows; do not delete as duplicates |
| Specialist reader paths | 17 across 15 hosts | Multiple paths to a host are not independent publishers |
| Official roster hosts | 103 | Only six get the current official-site News query path |

The 94 default-query IDs include six official-site rows. There are no exact duplicate expressions in that catalog. Near-overlap across broad crop queries, Radar, specialist search fallbacks and company monitors still needs incremental-yield measurement. Broad topic names do not establish that every specific trait or event is retrieved.

## Fix these before enlarging the set

1. **Official-site selection starves most of the roster.** `bounded_official_hosts()` takes three fixed hosts, then the first three alphabetically from the supplied roster, stopping at six. This run selected berries.net.au, britishberrygrowers.org.uk, hortifrut.com, abbreeding.nl, abz-strawberry.com and agricolaelbosque.com. GPG, Hutton, Planasa, NC State and most others therefore receive no turn through *this* path. They can have other paths; this is not a claim of universal publisher absence. Keep a request budget, but rotate by persisted last-attempt/last-success and coverage priority rather than alphabetical position.

2. **The registry and live reader have different feed catalogs.** GPG, Hutton, NC State CALS, UF/IFAS and Planasa have registry sources but are absent from the 17-entry specialist reader catalog. The GPG feed was live-readable and already contained the September 1 Ervin licensing article. Give the live reader a bounded breeder/extension feed group derived from the same registry IDs, instead of registering duplicate Sources. Preserve the difference between live, unreviewed discoveries and published Evidence.

3. **Resolve the 33 legacy keyword records.** Examples include Blackberry primocane variety, Raspberry variety license, Berry nursery partnership and Berry plant patent granted. These are enabled but have no discovery adapter, so they do not provide a modern collection path. Some overlap real active queries. Reconcile them into effective scoped monitors or deliberately mark them manual/legacy; do not blindly activate all 33 or inflate coverage claims using their count.

4. **Bind crop constraints to all search alternatives.** Several existing searches contain ungrouped alternatives such as `berry breeding partnership OR nursery license` or `Peru blueberry acquisition OR investment OR expands`. Crop/region terms should constrain every alternative. The earlier real broad Blackberry sample contained 81 RSS candidates; 46 titles matched finance/software markers such as stock, QNX or cybersecurity, and ten survived the News pipeline. That title-marker count is a diagnostic, not a source-inspected precision metric. Prefer fruit/cultivar/grower context at retrieval time, retaining downstream BlackBerry-company rejection as a second guard.

5. **Keep historical acquisition separate and visible.** New prospective defaults should receive an explicitly requested historical backfill where useful, with original source dates retained. A 30-day News query cannot reconstruct this year's breeding/licensing history. The new backfill path demonstrates this for Floricane/Blackberry; it does not establish complete history for every monitor.

## Live feed spot-checks

All eight sampled existing feeds returned HTTP 200 and parsed entries. Counts below describe the sampled current window only. Berry-title checks are literal indicators, not body-level relevance judgments.

| Existing feed | Entries returned | Titles with English berry terms | Latest entry |
|---|---:|---:|---|
| Global Plant Genetics | 10 | 6 | October 20, 2026 |
| Planasa | 10 | 5 | June 25, 2026 |
| FreshPlaza global | 63 | 5 | October 27, 2026 |
| Fruitnet /45.rss | 2 | 0 | October 27, 2026 |
| James Hutton general news | 10 | 0 | October 20, 2026 |
| Arkansas AAES general news | 10 | 0 | October 26, 2026 |
| UF/IFAS general news | 10 | 0 | October 22, 2026 |
| NC State CALS general news | 10 | 0 | October 27, 2026 |

Keep working general feeds, but supplement them with berry-specific paths. Their ten-item windows can be filled by unrelated subjects before the next berry item is available. Fruitnet's small feed window justifies retaining its existing site-search fallback and reviewing transport coverage; zero berry titles in two items does not prove failure. Planasa's older latest feed date needs comparison with its newsroom before calling the feed broken.

## Proposed additions: ten focused monitors

Retain broad discovery. Add these as bounded complements, using explicit crop and region columns. The eight English monitors are the first activation candidates; the two language monitors require downstream language support first. Expressions below are topic expressions; the saved Berry scope supplies the crop constraint. They are proposed examples for validation, not claims that every provider implements identical Boolean syntax.

| Monitor | Berry | Region / edition | Topic expression | Recommended path |
|---|---|---|---|---|
| Floricane developments | Blackberry | Global | `(floricane OR "second-year canes") AND (cultivar OR variety OR breeding OR trial OR licensing OR release)` | News; historical backfill separately |
| Primocane developments | Blackberry | Global | `(primocane OR "first-year canes" OR "double cropping") AND (cultivar OR breeding OR trial OR licensing OR release)` | News |
| Primocane / autumn-fruiting developments | Raspberry | Global | `(primocane OR "autumn fruiting" OR "fall bearing" OR remontant) AND (cultivar OR breeding OR trial OR licensing)` | News |
| Flowering habit and production season | Strawberry | Global | `("day neutral" OR day-neutral OR "short day" OR everbearing OR remontant) AND (cultivar OR breeding OR trial OR commercial)` | Weekly discovery |
| Warm-climate adaptation | Blueberry | Global | `("low chill" OR low-chill OR "zero chill" OR evergreen OR "heat tolerance") AND (cultivar OR breeding OR trial OR commercial)` | Weekly discovery |
| Disease resistance in new varieties | Strawberry | Global | `(Neopestalotiopsis OR Phytophthora OR Botrytis OR "disease resistance") AND (cultivar OR breeding OR resistance OR trial)` | News / weekly, one primary owning workflow |
| Postharvest traits | All four | Global | `(firmness OR "shelf life" OR postharvest OR "fruit reversion") AND (cultivar OR genetics OR trial OR breeder)` | Weekly; extends existing Exa-only emphasis |
| Propagation and plant supply | All four | Global | `("tissue culture" OR "clean plants" OR "virus indexed" OR "nursery capacity" OR "plant shortage") AND (trial OR production OR nursery OR commercial)` | Weekly discovery |
| Polish raspberry breeding | Raspberry | Europe; Polish | `(malina OR maliny) AND (odmiana OR hodowla OR licencja)` | Weekly, conditional on language support |
| Brazilian berry developments | All four | Americas; Portuguese | `(morango OR mirtilo OR framboesa OR "amora-preta") AND (cultivar OR variedade OR melhoramento OR licenciamento)` | Weekly, conditional on language support |

The catalog currently has no literal floricane, primocane, chilling, tissue-culture or robotics terms; shelf-life coverage exists in two Exa queries, so postharvest is an expansion of existing coverage, not a wholly missing topic. Existing disease, genetics, trials, labor, organic, retail and export searches provide broad/indirect coverage. The recommendations sharpen specific weak spots rather than claiming those subjects are absent everywhere.

**Language dependency:** adding Portuguese/Polish words only to a query is insufficient. Shared `BERRY_TERMS`, publication relevance screening, crop tagging, keyword-backfill crop checks and topic retrieval must consistently recognize the same crop aliases. The current crop expressions lack morango/mirtilo/framboesa/amora-preta and Polish terms; the guided builder's English crop clause could otherwise defeat a native-language search. Add language/search-edition controls rather than assuming an Americas or Europe scope selects Portuguese or Polish. Validate acquisition and archive retrieval on genuine native-only pages before enabling these defaults. Avoid ambiguous unqualified `mora` or `amora` as a generic blackberry synonym.

Phase two candidates after incremental-yield measurement: harvest automation/machine-harvest traits across crops; raspberry frozen/IQF supply and pricing in Serbia/Poland; targeted Turkish and Arabic coverage; direct non-English regulator/variety-register acquisition. These should not all become new always-on provider calls before the first batch is measured. CPVO/UPOV/USPTO references and a textual PBR query are not equivalent to complete registry monitoring; existing patent/register work should be assessed and reused before creating another collector.

## Primary-source additions and repairs

| Publisher / program | Current finding | Recommendation |
|---|---|---|
| [NC State Rubus portal](https://rubus.ces.ncsu.edu/news/meet-ervin-blackberry/) | Primary article fetched directly with HTTP 200; missing as a dedicated Source; CALS general feed is not this portal | Add a targeted portal path once its sitemap/feed or bounded discovery adapter is verified; no RSS URL was declared on the sampled page |
| [InHort, Poland](https://www.inhort.pl/odmiany-jagodowe/) | No dedicated Source; primary cultivar and licensing material available | Add a Polish research/breeding path, including dated announcement/PDF acquisition rather than just a homepage reference |
| [Embrapa berry research](https://www.embrapa.br/en/busca-de-publicacoes/-/publicacao/1188101/amoreira-preta-historico-manejo-e-tecnologias-de-producao) | Host exists in the official roster but no dedicated Source or Portuguese monitor | Add a verified Clima Temperado/publications path plus Portuguese crop aliases; a roster listing alone is insufficient |
| [Agroscope berries](https://www.agroscope.admin.ch/fr/cultures-de-baies) | No dedicated Source found | Stage as a European research candidate; verify a change/feed path before enabling collection |
| GPG | Registry RSS works; Ervin licensing present; missing from live specialist catalog | Reuse the existing source ID/feed in a bounded breeder live group |
| [Hutton fruit breeding](https://fruitbreeding.hutton.ac.uk/raspberry/varieties) and NIAB | Hutton general RSS is active; NIAB is a manual reference; roster participation does not guarantee site queries | Add targeted program coverage and fair host scheduling; do not duplicate the already configured Hutton general feed |
| [Southern Region Small Fruit Consortium](https://smallfruits.org/2026/01/sweet-ark-immaculate/) | Relevant primary research; direct server request returned 403 even though indexed content is readable in web search | Keep as a conditional discovery/review candidate; do not advertise a working RSS collector or bypass the access limitation |

New public primary examples justify these source classes, not headline-specific permanent search terms. NC State's Ervin introduction explicitly covers floricane habit and NC 740. InHort's [2026 Pola technical sheet](https://www.inhort.pl/wp-content/uploads/2026/01/Oferta-wdrozeniowa_Malina_M_14050E.pdf) identifies a new raspberry cultivar and its December 2025 register application. Embrapa has a 2026 blackberry production/technology publication. These are reasons to watch the programs and native vocabulary. Do not hard-code Ervin, NC 740, Pola or a benchmark article URL as the mechanism of general recall; use evidence-backed registry aliases for follow-ups.

## Recommended release sequence and acceptance

1. Repair host scheduling, catalog wiring and legacy-keyword status; retain all trusted records and stable IDs.
2. Add the eight English trait/propagation monitors and verified targeted primary paths. Keep one owning workflow per new monitor initially, with shared reuse where appropriate; do not activate every optional provider for every query.
3. Add Polish/Portuguese aliases end to end, validate native-only source acquisition, then enable those two monitors. Stage additional regional sources separately.
4. Use explicitly requested 2026 backfills for selected new monitors; do not launch a paid historical sweep as a side effect of deploying defaults.
5. Evaluate a shadow sample against the existing set: unique directly relevant articles and distinct developments added, primary-source acquisition rate, duplicate/irrelevant load, source-date accuracy, missed expected events, latency and provider cost. Hold publication review constant. A transport-healthy feed or larger candidate count alone does not pass the test.

The pre-deployment decision should depend on demonstrated incremental coverage and fair collection scheduling. This audit does not justify deploying the current set merely because configuration and regression tests pass. Public feed snapshots and the canonical inventory used here are captured under gitignored `inbox/search-quality-evaluation/default-set-audit/`; production runtime yield remains unmeasured.
