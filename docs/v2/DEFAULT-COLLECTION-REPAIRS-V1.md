# Default collection repairs — review candidate, October 27, 2026

Deployment and merge remain on hold for the user's review. No trusted Evidence, Facts, Signals, registry identity, or production scheduler was changed.

## Implemented repairs

1. Official News searches retain the six-host request cap but reserve the least-recently-attempted eligible queries in a persistent private ledger. All hosts, including the previously fixed three, take turns. Attempts are recorded before network work so failures cannot monopolize slots; successful requests record last-success separately. A dedicated interprocess lease protects reservations. The settings catalog lists every host without advancing rotation, and pause/remove overrides apply before selection. The existing live cache still bounds refresh frequency.
2. The live specialist reader derives a bounded breeder/extension group from existing Source IDs and their current RSS URL, enabled flag and lifecycle. It reuses GPG, Hutton, NC State CALS, UF/IFAS and Planasa instead of registering duplicates. Registry-backed feed URLs are read-only in the feed editor; Sources owns the URL. Three newly verified indexed primary-program paths also join this group. The catalog grows from 17 to 25 paths, not an unbounded registry scan.
3. All 33 enabled legacy keywords without adapters are now deliberately disabled manual references with an explicit lifecycle reason. Their IDs, expressions and historical lineage remain. They are not claimed as 33 new collectors. The primocane Blackberry reference points analysts to its new scoped monitor; other broad topics retain existing matrix coverage without claiming exact replacement or a new provider call for each legacy row.

Ten scoped defaults were added, each with one owning workflow: Blackberry floricane; Blackberry primocane; Raspberry primocane/autumn fruiting; Strawberry disease resistance; Strawberry flowering/season; Blueberry warm-climate adaptation; postharvest traits; propagation/plant supply; Polish raspberry breeding; Portuguese berry developments. The first four use News's 30-day window; the remaining six use weekly discovery. They support edit, pause, remove, restore and explicit historical backfill. Saving never launches a historical sweep.

## Language and query handling

The scoped editor now has a search-language/edition control (region default, English, Polish or Portuguese). This selects an edition and crop vocabulary; it does not translate topic words or establish article geography. Polish inflections and Portuguese crop names are recognized in metadata qualification, publication screening, crop tags, captured-body backfill and archive retrieval. Variety, breeding and licensing terms normalize across the supported native vocabulary. Ambiguous unqualified `amora` is not introduced as a Blackberry alias.

Provider expressions stay compact: native crop alternatives are selected for the requested language instead of being appended to every English matrix query. The 32-row Industry Pulse matrix retains its shape. A live diagnosis also found Google News returning zero for a redundantly nested Boolean expression while the equivalent flatter expression returned results. The compiler now removes redundant grouping while retaining OR precedence and crop constraints.

Historical advanced expressions use a deterministic Boolean parser on captured bodies. Discovery planning no longer treats all alternative quoted phrases as mandatory. Provider-specific operators unsupported by the body matcher are rejected before starting backfill. Missing a trait in an RSS headline alone does not prove its absence from the article; body verification remains distinct from metadata triage.

## Verified primary-program paths

| Program | Enabled discovery path verified October 27 | Body acquisition result |
|---|---|---|
| NC State Rubus portal | Google News site-restricted RSS; HTTP 200, 21 indexed items | Ervin introduction: 351 words; original date February 8, 2026 |
| InHort | Polish Google News site-restricted RSS; HTTP 200, 60 indexed items | Direct portal capture blocked by remote connection reset; not a demonstrated readable article collector |
| Embrapa | Portuguese Google News site-restricted RSS; HTTP 200, 100 indexed items | Portuguese blackberry publication: 329 words; crop/relevance recognized, but no exact publication date extracted, so not admitted to dated backfill |
| GPG, existing Source | Existing publisher RSS reused; prior live feed check found the Ervin licensing introduction | Fresh capture: 333 words; original date September 1, 2026 |

The three new Sources use `news_search_rss`, clearly documented as indexed discovery, not invented publisher RSS feeds or complete archives. Agroscope and Small Fruit Consortium remain conditional candidates; no blocked path was bypassed. Primary pages: [NC State](https://rubus.ces.ncsu.edu/news/meet-ervin-blackberry/), [InHort](https://www.inhort.pl/odmiany-jagodowe/), [Embrapa](https://www.embrapa.br/en/busca-de-publicacoes/-/publicacao/1188101/amoreira-preta-historico-manejo-e-tecnologias-de-producao), [GPG](https://www.globalplantgenetics.com/introducing-ervin-the-latest-introduction-nc-states-breeding-programme/).

## Paired coverage check

A bounded, keyless public-feed snapshot compared the 54 existing News/weekly Google-query rows with ten new defaults. All 64 requests returned HTTP 200. Baseline raw results contained 2,389 distinct normalized titles. New queries returned 225 candidates. Conservative title-only crop/industry triage found 112 additional distinct titles absent from the baseline raw title set; most were older material. These are discovery candidates, not 112 verified relevant articles or independent developments.

| New monitor | Raw candidates | Title-level crop/industry triage | Additional titles vs baseline | Triage candidates in last 30 days |
|---|---:|---:|---:|---:|
| Blackberry floricane | 1 | 1 | 0 | 1 |
| Blackberry primocane | 3 | 3 | 0 | 3 |
| Raspberry primocane | 1 | 0 | 0 | 0 |
| Strawberry resistance | 7 | 0 | 0 | 0 |
| Strawberry flowering | 9 | 5 | 2 | 0 |
| Blueberry warm climate | 47 | 20 | 16 | 0 |
| Postharvest | 8 | 4 | 4 | 0 |
| Propagation | 9 | 1 | 1 | 0 |
| Polish raspberry | 40 | 22 | 22 | 0 |
| Portuguese berries | 100 | 67 | 67 | 2 |

Google's raw results can include old dates or relaxed Boolean matches. Existing local date gates remain necessary. Only two additional candidates were within 30 days; both came from Portuguese discovery. Follow-up acquisition found one readable secondary research article that failed the saved full topic/region scope, while the other publisher could not be captured. Therefore this sample demonstrates additional native-language discovery, **not a confirmed increase in recent full-scope article coverage**. News's current floricane candidate overlaps the baseline; it is not a new verified floricane development. Weekly eligibility uses the existing weekly window, not this diagnostic 30-day column.

The eight English defaults remain prospective hypotheses requiring yield measurement, rather than acceptance based on larger candidate counts. Polish native-body processing is tested deterministically, with actual indexed native headlines checked; direct InHort acquisition remains unverified. Portuguese native-body processing was exercised on the actual Embrapa text. Do not represent fixtures as live Polish capture or the publication's year as an exact source date.

## Floricane historical and regression validation

Freshly captured NC State and GPG primary bodies were replayed offline through the **new default** historical monitor in an isolated evaluation inbox: two staged pending publications, zero failures. Repeating the same acquisition reused two duplicates and staged zero new records. Archive retrieval returned both for `Blackberry Floricans`, `floricane blackberry`, and `blackberry fruiting on second-year canes`. Original dates survived; both remained `in_review`; trusted Evidence count stayed zero. This replay used zero provider searches and did not rerun paid historical discovery. The earlier six-article preview backfill remains preserved.

Validation includes persisted rotation across turns/failure, catalog purity, registry URL/lifecycle changes, language edition through editing/dispatch, native-only screen/tag/qualification/archive retrieval, Boolean alternatives, native backfill staging and publication review safety. The broader targeted suite passes 217 tests; specialist-reader, catch-net budget and sustainability checks pass another 35 (11 overlapping), for 241 distinct passing tests. Record validation, JavaScript syntax and diff checks are also required before pushing the review candidate.

Raw feeds, bodies, receipts and browser screenshots stay in gitignored `inbox/search-quality-evaluation/default-set-audit/` and `inbox/collection-settings-preview/`. No source body or private credential belongs in the public PR. This is an implementation and diagnostic checkpoint, not completion of the broader search mission or permission to deploy.


## Native region/date follow-up — pre-deployment review

The live language-monitor test found two concrete collection defects. A Polish Pola/Soten article described its location with `polskie` in the publisher headline; the old filter checked only body text against literal place names. Region checks now consider the article heading and body with bounded Polish and Portuguese country/adjective aliases. Crop and topic checks remain body-based. Language, search edition and publisher domain do not establish article geography; foreign-region articles, English “polish” as a verb, and substrings such as polyphenols remain ineligible.

Embrapa news renders an explicit `DD/MM/YY` publication date in its own `visualizacao-noticias` / `data-categoria` header, including on English URLs. A verified host/path/template profile now reads that header and records `publisher_display_date`. The displayed two-digit year follows the fixed 1969–2068 parsing convention, not the current crawl year. It requires the article's own heading and excludes sidebar/navigation/footer blocks. Invalid, incomplete or conflicting dates remain unknown. Other publishers and Embrapa search/publication-library pages do not inherit this format assumption. The Fênix recommendation now retains **2025-09-05**, rather than being left undated or replaced with a search-result date.

Historical topic capture now preserves the publisher headline, retaining the search title separately, so region checks can use the actual captured article heading. The capture-cache version changes to avoid reusing pre-fix captures with missing dates/headings; subsequent warm requests still issue zero additional searches.

Both saved language monitors were rerun using public Google RSS, with a separately labeled historical diagnostic. Returned dates still require local filtering: the normal retrieval sample contained no qualifying articles within the last 30 days; the separately requested historical diagnostic also surfaced two recent Portuguese candidates, neither established as a valid readable full-scope article in the preceding check. This is not a claim of improved current-week yield.

Six previously identified public article pages were freshly captured. Four passed full scope/date checks and entered the **isolated local preview** through normal discovery-item/publication staging, with no research model or paid search calls:

| Monitor | Captured article | Original publisher date | Local review state |
|---|---|---|---|
| Polish raspberry | G-Viva introduction, Jagodnik | 2026-09-01 | In review |
| Polish raspberry | Pola/Soten, Jagodnik (previously region-rejected) | 2026-01-15 | In review |
| Polish raspberry | Pola/Soten, Kobieta w Sadzie | 2026-01-11 | In review |
| Portuguese berries | Fênix recommendation, Embrapa (previously undated) | 2025-09-05 | In review |

These are four articles, including two accounts of the same Pola/Soten development. Repeat processing resolved all four existing pending drafts and left their files unchanged. All four records validate; zero trusted publications were added. Raw source captures, monitor receipts and local draft IDs remain private under `inbox/search-quality-evaluation/native-monitor-review/`.

The Expointer announcement's date also extracts correctly as 2026-08-27, but its captured text does not pass berry/topic scope, so it was not staged. The Revista Cultivar disease article still fails this monitor's full scope, and the current-week CompreRural page remains access-blocked. No access barrier was bypassed. Direct InHort acquisition, broader native inflection coverage, other date templates and representative recent-article recall remain open. Deployment and merge remain held for review.

Validation for the region/date follow-up: 144 affected tests passed; the final publisher-headline/cache propagation check and surrounding 36 tests also passed (145 distinct tests across both runs). Canonical record validation and diff checks pass. All four actual preview drafts validate against the publication schema and remain in review.

Draft CI inventory reconciliation: NC State Rubus, InHort and Embrapa now have matching Domain Pack collector templates. Registry totals are 268 sources, 99 with discovery configuration and 95 eligible for modern collection. Direct RSS/linked-company counts are unchanged. The three stale inventory assertions and subsequent per-berry counts are updated; 64 affected tests pass. This synchronizes existing defaults and does not activate additional sources or deployment.
