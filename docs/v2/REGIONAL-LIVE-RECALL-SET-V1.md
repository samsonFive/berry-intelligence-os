# Regional Live Recall Set V1

**Mission:** Regional Coverage V4 -- Live Market Recall (2026-08-22, branch `feature/regional-coverage-v4`).
**Purpose:** A second, deliberately separate acceptance set from the fixed 50-event benchmark (`docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`). The fixed benchmark answers "does the OS recall specific historical headlines an analyst already knows about." This set answers a different question: **does the OS, right now, discover important real competitive events in weak/mixed geographies without an analyst first telling it what event to look for.**

## 1. Methodology

For each focus geography, the research order was always: (1) re-run the geography's existing, already-configured live sources against their current real window (`discover_media.py --source <id>`), (2) read the real resulting headlines with no prior knowledge of what "should" be there, (3) select 2-5 events that are independently real, dated, named-publisher, and significant, (4) only then run each through `process_discovered_media.py --item <id> --relevance-gate` (the real two-stage relevance screen + extraction pipeline) to see whether the OS actually captures it. Selection never used a benchmark headline as a starting point, and no candidate was rejected after the fact for having been MISSED -- misses are reported as misses.

No new source was created to build this set. Every event below came from a source that was already configured before this mission (`source-news-search-*` regional query sources onboarded in Global Qualitative Coverage Expansion V1/V2, plus `source-freshuelva-news` and `source-20260806173428-c710-fresh-fruit-portal-73` (FreshFruitPortal), both pre-existing, plus the three global trade-press sources onboarded in Unknown-Event Discovery V3: IBO, FreshPlaza, Fruitnet).

Two states are used: **CAPTURED** (real `direct`/scored `process`-tier draft exists in `inbox/evidence/`, verified by reading the actual persisted summary, not just the CLI's terse status line) and **MISSED**, with a root cause always given, never left unexplained.

## 2. Results by geography

### United Kingdom -- 3/4 CAPTURED

Source: existing `news_search_rss` UK sources (`source-news-search-uk-grower-season`, `-uk-retail-berry`, `-uk-berry-growers`), no FreshPlaza/Fruitnet UK item appeared in the current window at all (see Section 4).

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| AgriSound wins Innovate UK funding for berry-farm sensor tech | UK trade press, 2026-08 | Investment | CAPTURED (`ev-media-552555b186335509fed6`) |
| Bayer launches a new commercial strawberry variety | UK trade press, 2026-08 | New variety | CAPTURED, `direct` (`ev-media-ca17262a745c34759fd8`) |
| Co-op switches to 100% British strawberries | UK retail press, 2026-08 | Retailer-commercial | CAPTURED, `direct` (`ev-media-7060a9194c1c22c9d9f9`) |
| Sainsbury's signs five-year contracts with 62 UK berry farms | UK retail press, 2026-08 | Grower/marketer agreement | **MISSED** -- Stage A scored only 1 (generic "berry" match, no corroboration), then the Google News redirect URL returned no extractable body (`empty_body`); root cause is compound: Sainsbury's is not a registered Company entity at all (`data/entities/companies/` has no Sainsbury's/Tesco/Asda/Co-op/M&S/Morrisons file), so query-provenance corroboration could never trigger even if the body had resolved. |

### Mexico -- 4/4 CAPTURED

Source: FreshFruitPortal's existing backlog (`source-20260806173428-c710-fresh-fruit-portal-73`), already active before this mission, never fully exploited.

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| PSG expands Rejoice blackberry licensing platform | FreshFruitPortal, 2026 | New variety/commercialization | CAPTURED, `direct` (`ev-media-9cdd1a0c7c97e3fafea1`) -- **blackberry** |
| Mexican strawberry industry cautions on US antidumping ruling (Commerce prelim due 2026-08-18/24) | FreshFruitPortal, 2026 | Regulatory/trade | CAPTURED, `direct` (`ev-media-8cc69d52045f750290f7`) |
| Aneberries President commentary on industry conditions | FreshFruitPortal, 2026 | Executive/strategic | CAPTURED, `direct` (`ev-media-c7c22a01a23e07bb1a12`) |
| USHBC President on Mexico's role in the hemisphere | FreshFruitPortal, 2026 | Executive/strategic | CAPTURED (`ev-media-34daf4ac4d3aef9fa076`) -- confirmed real cross-publisher duplicate of the same story already found via IBO in Mission 3 (TD-068), not a new item |

### Spain -- 3/3 CAPTURED

Source: `source-freshuelva-news`, Spanish-language, pre-existing, never processed before this mission. Spain has **zero** fixed-benchmark coverage, so this is Spain's only recall evidence of any kind.

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| Jose Antonio Martin becomes new Freshuelva president | Freshuelva, 2026-07-16 | Executive/strategic | CAPTURED, `direct` (`ev-media-e8b3402197b93efa3723`) |
| Enrique Molina becomes new Interfresa president, replacing Francisco Jose Gomez | Freshuelva, 2026-07-30 | Executive/strategic | CAPTURED, `direct` (`ev-media-5d5629db990299a37982`) |
| Storms cut Huelva's 2025/26 red-fruit campaign: strawberry -3% to 204k t, blueberry -6% to 59.5k t | Freshuelva, 2026-07-14 | Trade disruption / crop-supply shift | CAPTURED, `direct` (`ev-media-9fb6fc269c5ef7143908`) -- **strawberry + blueberry** |

### Chile -- 4/4 CAPTURED (recurrence, not expansion)

Source: `source-news-search-chile-blueberry-es` and `-chile-morocco-trade`, both onboarded in a prior mission specifically to fix Chile's 0%-then-50% baseline. This mission deliberately tested recurrence rather than adding anything new, per the brief's own instruction.

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| Major Chilean berry producer (Hortifrut) exits cherries after heavy losses to refocus on berries | SanCarlosOnline, 2026-08-11 | Executive/strategic move | CAPTURED (`ev-media-6cba214cb348c40f9fdb`) |
| Chilean frozen blueberry exports grow 23.4% | reporteagricola.cl, 2026-08-18 | Production/export shift | CAPTURED (`ev-media-e3fd56bb64f9647d4a29`) |
| Biobio/Nuble blueberry growers advance Systems Approach export protocol | reporteagricola.cl, 2026-07-21 | Regulatory/export mechanism | CAPTURED, `direct` (`ev-media-686d6dddab32180b183b`) -- thin summary (title-only fallback; body extraction did not enrich this one, unlike the others) |
| Chile and Morocco strengthen agri-food market-access ties | FreshFruitPortal, 2026-08-18 | Trade | CAPTURED (`ev-media-b9720a38b0d52a839e6f`) -- **note:** same date/publisher as fixed-benchmark BM-T-10, whose original draft is no longer present in `inbox/evidence/`; reported here as a fresh, independent re-discovery, not claimed as new fixed-benchmark movement |

**Recurrence confirmed**: the same two Chile sources that first produced recall in a prior mission are still producing real, current, useful Chile events one mission later, with zero new source investment.

### Peru -- 5/5 CAPTURED (4 core + 1 corroboration)

Source: `source-news-search-peru-blueberry-es`, `-peru-organic-investment`, plus a FreshPlaza item as cross-publisher corroboration.

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| Peru opens Egypt as its 76th fresh-blueberry export market | hortidaily.es / MIDAGRI, 2026-08-13/14 | Market entry | CAPTURED (`ev-media-a870ac394fc029480c2a`) |
| Camposol's China blueberry shipments jump 631% at season start | Revista Lombriz, 2026-08-19 | Corporate/export surge | CAPTURED (`ev-media-f1e91ffd336177e288c0`) |
| El Nino threatens Peruvian blueberry production and could push world prices up | Bloomberg Linea, 2026-07-30 | Climate/trade disruption | CAPTURED (`ev-media-6d167d087771e4d24665`) |
| Oppy expands its Happy Berry line with a Peruvian blueberry program | The Packer, 2026-08-17 | Marketer/grower agreement | CAPTURED (`ev-media-5d0a2d92df0ffe4d7c41`) |
| *(corroboration)* Peruvian blueberry exports to China +74% at week 32 | FreshPlaza, 2026-08-20 | Production/export shift | CAPTURED (`ev-media-c91b421830af47595ce0`) -- independently confirms the Camposol/China story from a second real publisher |

**Recurrence confirmed**: same result as Chile -- Peru's existing Spanish-language query mechanism, built in a prior mission, is still finding a wide, current spread of real Peru events without new sources.

### Morocco -- 2/3 CAPTURED

Source: `source-news-search-morocco-berry-fr` (French-language, proven in Mission 3), plus `source-news-search-chile-morocco-trade`.

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| "Morocco: the new berry giant now facing the challenge of consolidating its leadership" | Hortidaily, 2026-08-18 | Strategic/market position | **MISSED** -- Google News redirect returned no extractable article body (`empty_body`), same structural pattern as the UK Sainsbury's miss and consistent with TD-059 |
| Moroccan fresh-strawberry exports collapse to a 6-year low | Hespress Francais, 2026-07-08 (corroborated independently by Bladi.net, Le Matin.ma, H24info, Le Desk the same week) | Production/trade disruption | CAPTURED (`ev-media-296244b9840ca6f1d44f`) -- **strawberry**, the first non-blueberry Morocco capture this engagement has produced |
| IBO assessment of the Moroccan blueberry model's strengths and structural challenges | AgriMaroc, 2026-05-19 | Industry structure | CAPTURED (`ev-media-a00d4fd864ec97cf8532`) |

French-language discovery is confirmed genuinely useful beyond backlog recovery: the strawberry-crisis story was independently corroborated by five separate French-language publishers in the same window, and the OS captured it on the first real French-language query, not via IBO's English feed.

### South Africa (+ Zimbabwe as regional-adjacent) -- 3/3 CAPTURED

Source: `source-news-search-south-africa-blueberry`, `-south-africa-trade`.

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| South African blueberry production reaches 38,900 t in 2026 | FreshPlaza, 2026-08-14 | Production | CAPTURED (`ev-media-73c3863c441173b69756`) -- **note:** this is the same underlying statistic as fixed-benchmark BM-M-05, already captured in a prior mission (2026-08-21); reported here as confirmation the story recurs across publishers/dates, not as new fixed-benchmark movement |
| SA blueberry season: bumper crop in the north, uncertain conditions in Western Cape | Farmer's Weekly SA, 2026-08-08 | Production/regional variance | CAPTURED (`ev-media-cb33af005d304e81f2e8`) |
| Zimbabwe ships its first-ever commercial blueberry export to China | Reuters, 2026-07-07 (corroborated by FreshPlaza, China Daily, Produce Report, NewZimbabwe.com, Business Insider Africa) | Market entry | CAPTURED (`ev-media-d7d2005c0887cc82e340`) -- a real, major, first-of-its-kind regional event; included because Zimbabwe's emergence as a new China-facing African blueberry exporter is directly competitively relevant to South Africa's own China-access position |

South Africa's existing English-language regional sources are working -- this mission found no case where a real South African event was missed.

### United States -- not separately re-tested

Per the mission's own scope ("include US only where a reusable regional mechanism is underperforming"), the US was not given a dedicated live-recall set this mission: its fixed-benchmark recall (67%) and existing source density did not present a specific underperforming mechanism to test. This is a deliberate scope decision, not an oversight.

## 3. Aggregate result

**23/25 core events CAPTURED (92%)**, 2 MISSED, across UK(3/4), Mexico(4/4), Spain(3/3), Chile(4/4), Peru(4/4 core + 1 corroboration), Morocco(2/3), South Africa(3/3). Both misses share the identical root cause pattern -- a Google News redirect URL that resolves to no extractable article body (TD-059) -- and the UK miss is compounded by a second, independent cause (Sainsbury's/major UK retailers not being registered Company entities, see TD-069 below).

This is a fundamentally different, and structurally higher, number than the fixed benchmark's 66%, and that gap is itself the finding: **when an event is currently sitting in a live, already-configured source's current window, the existing two-stage relevance screen captures it at a very high rate.** The fixed benchmark's lower number is a discovery/reachability problem (RSS windows don't reach back in time -- TD-067), not a relevance-screening weakness. The two numbers measure different things and must not be combined.

## 4. Global trade press marginal value (IBO / FreshPlaza / Fruitnet)

| Source | Current window size | Berry-relevant items | Direct-hit rate | Notes |
|---|---|---|---|---|
| IBO | 10 | 10/10 (100%) | High -- single-topic blueberry-only feed | All 10 already processed in Mission 3; 0 new items this mission (only 1 day elapsed) |
| FreshPlaza | 69 | 4/69 by title (5.8%), rising to 8/69 (11.6%) once the 4 processed genuinely-berry items are counted plus the earlier UK/Mexico/Peru items already drawn from it | Low signal density, high absolute value per hit | 65/69 items are general global produce/horticulture news (apples, avocados, citrus, potatoes, logistics) with zero berry relevance -- a real, broad firehose, not a berry-focused feed. Only 3/69 items had ever been processed before this mission; the other 66 had never been screened at all (see TD-070) |
| Fruitnet | 2 | 0/2 (0%) | None this window | Both current items are kiwifruit/general produce (Zespri, Seeka) -- confirms Fruitnet's real, structural low-volume limitation (~2 items/window) already found in Mission 3; too early to judge long-term value from one window |

**Geographic distribution of the FreshPlaza/trade-press items actually captured this mission**: global/Russia (1), Peru (1, corroboration), Europe/global (raspberry overview, 1), Finland (1). No UK item appeared in either FreshPlaza's or Fruitnet's current window at all, despite UK being a focus geography -- UK recall this mission came entirely from the pre-existing `news_search_rss` UK sources, not the new global trade press.

**Conclusion**: IBO is a small, extremely high-precision, single-topic feed. FreshPlaza is a large, low-precision, high-recall-when-it-hits global firehose whose berry-relevant fraction is genuinely low (~6-12%) but whose hits are real and otherwise-unreachable (the raspberry global-market-overview and Finnish strawberry/raspberry items have no other current source in this platform). Fruitnet remains too sparse to evaluate. None of the three materially reduces the need for the region-specific `news_search_rss` sources that produced the bulk of this mission's real recall -- they are complementary, not substitutes.

## 5. Berry distribution across the Live Recall Set

Counting only the 25 core geography events (Section 2), tagged berry per the captured draft's own `berry_ids`:

- **Blueberry**: 15/25 (60%)
- **Strawberry**: 5/25 (20%) -- Bayer variety, Co-op, Mexico antidumping, Spain storms (also blueberry), Morocco crisis
- **Blackberry**: 1/25 (4%) -- PSG Rejoice (Mexico) only
- **Raspberry**: 0/25 (0%) in the core geography set

Raspberry only appears in this mission's data via two of the *bonus* FreshPlaza items (global raspberry market overview, Finnish raspberry pricing) -- neither tied to a focus geography. **This confirms the mission's own stated concern directly: blueberry volume is masking real caneberry blindness.** Every regional query source built or reused this mission is phrased around berries generically or blueberry specifically; none is raspberry- or blackberry- targeted, and none of the 7 focus-geography live-recall sets produced a single raspberry event.

## 6. Review economics

All 24 new drafts this mission came from sources already configured before the mission began -- zero net-new review load was created by source onboarding (no new source was added). Per-mechanism marginal cost:

- UK `news_search_rss` (3 sources): 4 items reviewed, 3 real drafts, 1 acquisition failure (no review burden, self-excludes)
- Mexico FreshFruitPortal backlog: 4 items reviewed, 4 real drafts, 0 waste
- Spain Freshuelva backlog: 3 items reviewed, 3 real drafts, 0 waste
- Chile (2 sources): 4 items reviewed, 4 real drafts (1 thin/title-only, still real)
- Peru (2 sources + FreshPlaza): 5 items reviewed, 5 real drafts, 0 waste
- Morocco (2 sources): 3 items reviewed, 2 real drafts, 1 acquisition failure
- South Africa (2 sources): 3 items reviewed, 3 real drafts, 0 waste
- FreshPlaza direct sample: 4 berry-relevant items hand-identified out of 69 total titles scanned (65 correctly excluded as non-berry noise before any processing cost was spent on them)

No item processed this mission was discarded as a duplicate or as adjacent/irrelevant after reaching the relevance gate -- the pre-filtering (title scan before processing, Stage A screening where available) is doing real work keeping review load proportional to actual berry relevance. This is an operational-load count only, per the mission's own instruction; real analyst accept/reject outcome history is Codex's separate review-outcome-instrumentation lane (`docs/v2/PROJECT-STATUS.md`, PR #86, merged 2026-08-22), not duplicated here.

## 7. Deliberate stop cases

- **Fruitnet**: too sparse (2 items/window, 0% berry-hit this window) to justify further investment beyond continued passive monitoring; revisit after several more windows accumulate.
- **FreshPlaza's non-berry 94%**: not a source-quality problem to "fix" -- it is an inherent property of a global horticulture wire service. No action needed; the existing title-level pre-filter already keeps review cost low.
- **UK major retailers as Company entities**: the Sainsbury's miss's root cause requires either an entity-creation decision (see TD-069) or accepting that retailer-commercial-class UK events depending on corroboration will keep missing when a body-fetch also fails. Not fixed this mission -- flagged, not forced, per the established entity-grounding discipline (every entity must have real trusted evidence backing before creation).
- **Google News redirect body-fetch (TD-059)**: known, structural, affects any geography's `news_search_rss` sources equally; not specific to this mission's regions and not newly discovered here, just newly reconfirmed against two more real cases (Sainsbury's, Morocco/Hortidaily).
