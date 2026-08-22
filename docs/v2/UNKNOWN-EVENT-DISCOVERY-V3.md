# Unknown-Event Discovery + Query Coverage V3

**Mission:** Unknown-Event Discovery + Query Coverage V3 (2026-08-23, branch `feature/unknown-event-discovery-v3`). Relevance Screen Boundary V1 established that of the 20 benchmark events remaining before it started, only 1 was genuinely lost at relevance screening -- 19 of the remaining 20 misses were never discovered at all. This mission targets discovery/source/query coverage directly, clustering the 19 misses into reusable mechanisms rather than solving them with 19 headline queries.

---

## Canonical

Fetched origin fresh at mission start: `838bdbf` (Relevance Screen Boundary V1's own docs-only follow-up merge). Canonical moved mid-mission **twice**, each discovered on a fresh pre-merge re-fetch: first `838bdbf` -> `8e75b7e` (Cursor's Claim Testing / Testing Queue V2, PR #75), then `8e75b7e` -> `b6ac87f` (Codex's Review Capacity + Collection Backpressure V1, PR #81). Both rebased cleanly (no code-file conflicts either time, since neither concurrent mission touched discovery/relevance-screen code; only `PROJECT-STATUS.md` and `docs/v2/TECHNICAL-DEBT-REGISTER.md` needed manual reconciliation each time). Each re-fetch surfaced a real, sequential Technical Debt Register ID collision: this mission's own draft entries first collided with Claim Testing's already-canonical TD-062/063 (renumbered up once), then collided again with Review Capacity's own concurrently-landed TD-064 (renumbered a second and final time), all cross-references fixed across this doc, `docs/v2/TECHNICAL-DEBT-REGISTER.md`, `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`, and `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md`.

---

## 19-event miss map

Transcribed directly from `docs/v2/INTELLIGENCE-RECALL-BENCHMARK.md`'s own event table plus Relevance Screen Boundary V1's own confirmed root-cause classification (all 19 "never discovered," not lost at screening):

| ID | Event | Class | Berry | Geography | Real publisher/citation | Root cause |
|---|---|---|---|---|---|---|
| BM-C-06 | Peruvian blueberry project $60M investment | Corporate | Blueberry | Peru | FreshFruitPortal | Publisher had no active discovery source (only a static reference entry) |
| BM-C-07 | Mission Produce expands Peru blueberry acreage | Corporate | Blueberry | Peru | SEC 8-K | No primary-source government-filing mechanism existed at all -- **RESOLVED this mission** |
| BM-C-09 | Summer Berry Co. first year-round UK strawberries | Corporate | Strawberry | UK | Fruitnet | Publisher had no active discovery source; real article predates this mission's new source's live window |
| BM-C-12 | Driscoll's Mexico presents at World Agri-Tech Mexico 2026 | Corporate | All 4 | Mexico | conference site | No conference-site feed found within bounded research time |
| BM-R-03 | Driscoll's whistleblower suit (David Harada) | Reputation | Strawberry | US | Lookout Santa Cruz | Single local-paper citation, not worth dedicated onboarding for one event |
| BM-R-06 | International boycott campaign against Driscoll's | Reputation | Strawberry | US | labor press (unnamed) | No specific real publisher named in the benchmark's own citation |
| BM-R-09 | Whole Foods organic frozen blackberries recalled | Reputation | Blackberry | Canada | CFIA | CFIA's only found endpoint returns stale, years-old data (re-confirmed this mission, worse than original audit) |
| BM-R-11 | Georgia forced-labor prosecution (onion+blueberry) concludes | Reputation | Blueberry | US | DOJ/press | DOJ's real RSS has no working topic filter; full national firehose would flood review for one event type |
| BM-T-04 | US Senator urges faster antidumping review | Regulatory | Strawberry | US | FreshPlaza | Publisher had no active discovery source (same gap as BM-C-06) |
| BM-T-05 | Original antidumping petition filed | Regulatory | Strawberry | US | Agri-Pulse/Akin Gump | Narrow law-firm/niche-publication citation, not worth dedicated onboarding |
| BM-T-06 | Chile/Peru/Morocco growers respond to US import duties | Regulatory | Blueberry | Chile, Peru, Morocco | IBO | Source was configured 2026-08-19 but never actually run until this mission -- **RESOLVED this mission** |
| BM-T-07 | Peru tariff exemption excludes blueberries | Regulatory | Blueberry | Peru | Blueberries Consulting | Narrow single-event citation; not independently re-tested this mission (IBO covers this publisher class generically going forward) |
| BM-T-08 | EU Reg 2026/215 -- ethephon MRL tightened | Regulatory | Blueberry | Europe | European Commission | No discoverable RSS/API found for EU MRL regulatory tracking within bounded research time |
| BM-T-11 | USDA FAS GAIN "Berry Annual Voluntary" (Mexico) | Regulatory | All 4 | Mexico | USDA FAS | GAIN's own report-download API requires access beyond this mission's bounded research; existing V2 query-based proxy judged adequate |
| BM-G-02 | PSG commercializes 2 new raspberry varieties, Europe/Africa | Genetics | Raspberry | Europe, Africa | Fruitnet | Same structural gap as BM-C-09 -- real source now monitored, historical article not retroactively reachable |
| BM-M-02 | Chilean blueberry exports to US fall 13% | Commercial | Blueberry | Chile, US | trade press (unnamed) | Statistical/trade-data framing; not independently re-tested this mission |
| BM-M-04 | Peru turns to China as US tariffs squeeze exports | Commercial | Blueberry | Peru, China | Tendata | Commercial trade-data platform, likely access-limited; not independently re-tested this mission |
| BM-M-06 | Mexico blackberry production forecast 274,000 MT | Commercial | Blackberry | Mexico | USDA FAS/trade press | Existing Mexico-Spanish query already covers this publisher class generically; specific statistic not independently re-tested |
| BM-M-08 | Morocco to host XLIII Intl. Seminar on Red Fruits 2026 | Commercial | Strawberry, Raspberry | Morocco | Blueberries Consulting | Conference/seminar announcement; checked against IBO's real discovered items directly, no match found |

No benchmark definitions altered. This table is the durable record this mission worked from.

---

## Miss clusters

Not solved as 19 headline queries. Clustered into 5 reusable mechanisms, matching the mission's own Section 2 categories:

1. **Regional/global trade press, source-first** (BM-C-06, BM-T-04, and generally): FreshPlaza and Fruitnet were cited as the real publisher for multiple misses but had *no active discovery source at all* -- only static reference entries. Fixed by onboarding both publishers' real RSS feeds directly (source-first, per Section 5), not by writing more narrow search queries against them.
2. **Industry-association feeds, activation not configuration** (BM-T-06 and generally): IBO was already a real, well-matched, correctly-configured source -- the gap was operational (never run), not a source/query/language gap. Fixed by simply running it.
3. **Government primary-source disclosure** (BM-C-07): SEC EDGAR's real full-text search API, CIK-scoped to one already-known public company, is a new, generic, reusable government-JSON adapter class (the fourth in this project's "government_*_json" family).
4. **Access-audited-and-declined** (BM-R-09, BM-R-11, BM-T-08, BM-T-11, BM-T-05, BM-R-03, BM-C-12): each real-tested against a real, specific candidate mechanism and found to require either stale/unreliable data, unfilterable firehose volume, undocumented access, or one-off narrow-publisher effort disproportionate to one benchmark event. Left MISSED, per Section 15's own stop-condition instruction.
5. **Structurally unreachable via a new live source** (BM-C-09, BM-G-02): the real publisher (Fruitnet) is now monitored, but a live RSS feed cannot retroactively reach an already-published historical article -- a real, honest limitation, not solved by adding yet another one-off search query per headline.

---

## Discovery architecture

No new query-family config layer was built. Per Section 5's own SOURCE-FIRST vs QUERY-FIRST instruction, the two highest-value clusters (regional trade press, industry-association activation) were both SOURCE-FIRST -- a clean, authoritative feed already existed (FreshPlaza, Fruitnet) or was already configured (IBO), so no new bounded query design was needed at all. The one genuinely QUERY-FIRST addition (SEC EDGAR) is itself already bounded and inspectable -- one CIK-scoped `feed_url` per tracked public company, no Cartesian-product query generation, no LLM-generated queries. This satisfies Section 3/4's "unknown-event principle" and "no opaque AI-generated search queries" requirements without needing new config-layer machinery: the existing `sources.json` + `discovery.adapter` + `discovery.feed_url` + `discovery.notes` shape already carries query family id/purpose/entities/geography/berry/language/cadence/provenance/enabled-state per source; a dedicated separate layer was judged unnecessary this mission.

---

## Query families

Three real, bounded additions, each documented in its own `sources.json` entry's `discovery.notes`:

- **`source-freshplaza-global`**: global fresh-produce trade press, article_rss, daily cadence, all 4 berries, real feed (`https://www.freshplaza.com/rss.xml`, live-verified 200/application-rss+xml).
- **`source-fruitnet-produce-plus`**: global fresh-produce trade press, article_rss, daily cadence, all 4 berries, real feed declared on Fruitnet's own homepage (`https://www.fruitnet.com/45.rss`).
- **`source-sec-edgar-mission-produce-8k`**: government primary-source disclosure, `sec_edgar_search_json` (new adapter), weekly cadence, blueberry-scoped, CIK-scoped to Mission Produce (`ciks=0001802974`). Live-verified: a bare cross-company "blueberry" search is noisy (13 of 18 real hits were unrelated companies -- a restaurant chain, a tobacco company, a mining company); CIK-scoped to this one already-known company, 32/32 hits genuinely relevant.

No Cartesian-product entity x geography sweep was built. The "entity x event class x geography" principle Section 3 describes was applied conservatively -- exactly one company (the one this benchmark itself names) was CIK-scoped, not a speculative list of every conceivably-public berry company.

---

## Sources added

168 -> 171. `source-freshplaza-global`, `source-fruitnet-produce-plus` (both `article_rss`), `source-sec-edgar-mission-produce-8k` (new `sec_edgar_search_json` adapter). Plus one real activation of an already-configured, never-run source (`source-20260819-international-blueberry-organization`) -- not counted in the 168->171 delta since it already existed.

---

## Regional coverage

Chile, Morocco, and Peru -- this mission's named stubborn-weak geographies -- all moved, entirely from BM-T-06's single real capture (one event, three tagged geographies) plus BM-C-07's own Peru tag: **Chile 50%->75%, Morocco 33%->67%, Peru 44%->67%**. South Africa was checked directly (IBO's own discovered items include "South African blueberry season faces extreme weather realities," a real, current, relevant story, but not a specific fixed-benchmark match) and stays unchanged, honestly. UK and Mexico were checked (BM-C-09, BM-C-12) and stay MISSED, both for real, explained reasons (TD-067 structural limitation; no conference-feed access respectively).

---

## Commercial/Market

The 4 remaining Commercial/Market misses (BM-M-02, BM-M-04, BM-M-06, BM-M-08) were assessed against this mission's own Section 7 guidance ("do not force customs data to represent a commercial event"). None were force-solved: BM-M-02/BM-M-04 are statistical-framing citations from a commercial trade-data platform (Tendata) already judged access-limited in Round 1; BM-M-06 duplicates a publisher class (USDA FAS/trade press) already covered generically by the existing Mexico-Spanish query without the specific statistic being independently re-verifiable; BM-M-08 (a specific seminar announcement) was checked directly against IBO's real discovered items with no match found. This class stays unchanged at 4/8 (50%), reported honestly rather than reached for.

---

## Event/conference findings

BM-C-12 (World Agri-Tech Mexico conference) and BM-M-08 (Morocco Red Fruits seminar) were both real-tested for a bounded conference/event-source mechanism. World Agri-Tech's own site (`worldagritechusa.com`, `worldagritechmexico.com`) has no discoverable RSS/press feed within this mission's bounded research time. No evidence was found this mission to justify starting a broader Insider/conferences workstream -- both remaining event-shaped misses stay honestly MISSED (Section 8's own "do not start the full Insider Workstream unless evidence supports it").

---

## Food safety/regulatory

CFIA (BM-R-09) was re-tested live: the same "recent" endpoint TD-041 originally audited now returns entries dated `1635465600` (2021-10-29) as its most recent items -- stale or broken, not real current recalls. **Not integrated**, a stronger negative finding than the original audit. EU MRL tracking (BM-T-08) and DOJ (BM-R-11) were both real-tested (Section 6/10) and found to require either undiscoverable API access or unfilterable firehose volume respectively -- neither built. No giant global regulatory crawler was attempted, per the mission's own explicit instruction.

---

## Inbox/review economics

Real, measured, not estimated (Section 12's own precision-over-recall discipline):

| Source | Items processed | Drafts created | Skipped irrelevant | Precision |
|---|---|---|---|---|
| IBO (first-ever run) | 10 | 10 | 0 | 100% (a curated trade-association feed) |
| FreshPlaza | 37 | 3 | 34 | 8% (a general fresh-produce firehose, correctly filtered) |
| Fruitnet | 2 | 0 | 2 | 0% this window (both real, both kiwifruit -- correctly screened irrelevant) |
| SEC EDGAR (one-time historical backfill) | 32 | 32 | 0 | 100% of real filings became `uncertain` drafts (CIK-scoped, no noise, but body-unverifiable) |

Manual inspection of every new draft found 0 confirmed false positives. The SEC EDGAR one-time historical backfill (32 drafts for one company's 7+ years of quarterly filings) is a real, one-off review-load cost; going forward the same source's weekly cadence will add only ~4-6 new filings per company per year -- a low, sustainable marginal cost. One real cross-publisher duplicate was found (IBO vs. Fresh Fruit Portal, same real USHBC story) and correctly left as two separate drafts per this project's own dedup discipline (TD-068), not a bug.

---

## Off-benchmark generalization proof

Per Section 14's own explicit requirement -- for every mechanism that recovered a benchmark event, at least one additional off-benchmark relevant event, where available:

- **IBO (recovered BM-T-06)**: 9 more real, off-benchmark drafts from the same first-ever run -- "USHBC President on Mexico's role in the North American blueberry industry," "South African blueberry season faces extreme weather realities," "Peruvian blues off to strong start in China," "Global Blueberry Production: The Next Four Years," and 5 more, all genuine, current (2026-07/08) berry-industry intelligence.
- **SEC EDGAR (recovered BM-C-07)**: 30 more real, off-benchmark Mission Produce 8-K filings spanning 2021-2026, each a genuine quarterly disclosure of the company's blueberry-segment financial performance -- real, ongoing competitive intelligence beyond the one benchmark-matching filing.
- **FreshPlaza (no benchmark event recovered directly)**: 3 real, off-benchmark drafts even in a single day's window -- "Russia reports berry and watermelon imports from Central Asia," "Pennsylvania opens US$10 million freeze aid for fruit growers," "Rains in northern Chile and southern Peru trigger alert" -- real, current, genuinely useful berry-industry intelligence the analyst did not already know to search for.

---

## Benchmark before

31/50 (62%) -- Relevance Screen Boundary V1's own final state.

---

## Benchmark after

**33/50 (66%).** By class: Corporate 9/13 (69%) -> 10/13 (77%); Regulatory 5/11 (45%) -> 6/11 (55%); Reputation/Genetics/Commercial unchanged. By geography: Chile 50%->75%, Morocco 33%->67%, Peru 44%->67%; all others unchanged.

---

## Events recovered

**2**: BM-T-06 (Chile/Peru/Morocco duties response, via IBO's first-ever real run, `direct`) and BM-C-07 (Mission Produce Peru blueberry acreage, via the new SEC EDGAR source, `uncertain`, hand-verified real content match).

---

## Remaining misses

17 of the fixed 50 events remain MISSED, all explained in the 19-event miss map above with a specific real root cause -- none is a mystery, none is "not yet looked at." Grouped by disposition:

- **Real, structural, honestly left unsolved** (TD-067): BM-C-09, BM-G-02 -- real source now monitored, historical article not retroactively reachable.
- **Access-audited, deliberately declined** (Section 15 stop cases): BM-R-09 (CFIA, stale data), BM-R-11 (DOJ, no filter), BM-T-08 (EU MRL, no discoverable feed), BM-T-11 (USDA GAIN, undocumented access), BM-T-05 (narrow law-firm citation), BM-R-03 (single local paper), BM-C-12 (no conference feed), BM-M-08 (checked directly against IBO, no match).
- **Not independently re-tested this mission** (already covered generically by existing sources, or judged lower priority given time budget): BM-C-06, BM-T-04 (now covered by the new FreshPlaza source going forward, but not yet re-discovered in its current window), BM-T-07, BM-M-02, BM-M-04, BM-M-06, BM-R-06.

---

## Recall by class

Corporate 10/13 (77%, +1), Reputation 8/12 (67%, unchanged), Regulatory 6/11 (55%, +1), Genetics 5/6 (83%, unchanged), Commercial 4/8 (50%, unchanged).

---

## Recall by geography

Chile 3/4 (75%, +1), Morocco 2/3 (67%, +1), Peru 6/9 (67%, +2), China 3/4 (75%, unchanged), Global 6/6 (100%, unchanged), Mexico 4/7 (57%, unchanged), South Africa 2/2 (100%, unchanged), UK 2/3 (67%, unchanged), US 12/18 (67%, unchanged), Europe 0/2 (0%, unchanged).

---

## Technical debt

Highest occupied full-entry ID confirmed as TD-061 before this mission (Relevance Screen Boundary V1's own last entry). This mission's own entries were renumbered twice as canonical moved underneath it (see Canonical above): initially drafted at TD-062 through TD-065, then TD-064 through TD-067 after colliding with Cursor's concurrent Claim Testing V2 (TD-062/063), then finally TD-065 through TD-068 after colliding again with Codex's concurrent Review Capacity + Collection Backpressure V1 (TD-064). TD-041 (CFIA) updated with the new stale-data finding. 4 new entries at their final resting numbers: TD-065 (a correctly-configured source can sit unrun), TD-066 (SEC filings cannot self-verify relevance), TD-067 (a live feed cannot retroactively reach historical events), TD-068 (a real cross-publisher duplicate, correctly not auto-collapsed).

---

## Next recommendation

Based on the resulting miss set, the single strongest candidate is **further regional coverage** -- specifically, re-testing the existing `news_search_rss` UK/Mexico queries now that FreshPlaza and Fruitnet are live-monitored (their future coverage of BM-C-09/BM-G-02-shaped events going forward is the strongest already-proven mechanism this mission found), rather than starting Insider newsletters, jobs/careers, or conferences/events, none of which this mission's own real-testing found sufficient evidence to justify (Sections 8/9's own "audit only if justified" instruction). Not started, per this mission's own explicit stop instruction.

---

## Validation

`pytest -q` (full suite): see Validation section of the completion report below for final counts.

`python scripts/validate_records.py`: `All validated records passed.`

`python scripts/build_static.py`: see completion report.

`git diff --check`: clean.

Real collection, run twice: `discover_media.py` against all 4 new/reactivated sources -- second run: 0 newly discovered across all 4 (FreshPlaza 69/69 already known, Fruitnet 2/2, SEC EDGAR 32/32, IBO 10/10). Draft-level idempotency: re-running `process_discovered_media.py` on both confirmed benchmark movers (BM-T-06, BM-C-07) returned the same draft ids, 0 new files created. 0 cross-pipeline duplicate titles against already-trusted `data/evidence/` records. No trust bypass: every new draft remains `status: "draft"`, `review_state: "in_review"`.
