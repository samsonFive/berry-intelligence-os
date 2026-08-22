# Caneberry (Raspberry / Blackberry) Live Recall Set V1

**Mission:** Blackberry / Raspberry Vertical V1 (2026-08-22, branch `feature/blackberry-raspberry-vertical-v1`).
**Purpose:** Regional Live Recall Set V1 measured 23/25 (92%) live regional event recall, but berry distribution was blueberry 60%, strawberry 20%, blackberry 4%, raspberry 0% -- the clearest measured content-coverage imbalance on the platform. This mission asks empirically: **is the system genuinely blind to caneberry intelligence, or did the live regional sample simply contain fewer caneberry events?**

## 1. Methodology

Real, recent (2025-2026) raspberry and blackberry competitive events were researched first via live web search, independent of what the OS already had -- the same discipline established in Regional Live Recall Set V1. Events were then checked against the platform: existing sources' current windows first, then two small, empirically-justified new query sources, only after proving the gap was real. Raspberry and blackberry are reported and counted **separately** throughout, never combined into one caneberry percentage, per the mission's explicit instruction.

## 2. Terminology audit (Section 2)

Live-tested via direct Google News RSS queries before any vocabulary change:

| Term | Real hit rate (sample) | Verdict |
|---|---|---|
| `caneberry` (English) | 13/13 on-topic (100%) -- OSU/NC State/UC Extension bulletins, Fruit Growers News pricing survey | Real, high-precision US/UK trade term. **Added.** |
| `bramble fruit` (English) | 0/35 on-topic -- entirely wine-tasting-note noise ("Bramble" flavor descriptor) | Collision risk confirmed real. **Not added.** |
| `zarzamora` (Spanish, Mexico) | ~30-40% real signal on a 100-item sample (an initial 50-item spot-check showed higher, ~90%+, but the fuller sample surfaced real noise: recipes/desserts, farm tourism, a flamenco song, perfume notes, dream interpretation) | Real, net-positive, materially different term from the already-present generic `mora`. Genuinely surfaced content (the Planasa "Yosemite" blackberry variety, a real disease alert, a real Michoacan production statistic) that `mora` alone had never caught. **Added, with the noise rate honestly reported, not oversold.** |
| `frambuesa`/`frambuesas` (Spanish) | Already present | No change needed. |
| `framboise(s)`/`myrtille(s)`/`fraise(s)` (French) | Already present in `relevance_screen.py`'s berry-identity gate (added in Relevance Screen Boundary V1) | Confirmed still working; found a **separate, real gap**: `deterministic_tagging.py`'s `BERRY_TERMS` (used for auto-tagging `berry_ids` onto drafts/articles, a genuinely different code path from the relevance-screen gate) has **zero French vocabulary for any berry**, not just blackberry -- a French raspberry article can pass relevance screening correctly but still fail to get auto-tagged `berry-raspberry`. Registered as new debt (TD-072), not fixed this mission (scope: this mission's own proven gaps were Spanish/English). |
| French `mûre`/`mûres` (blackberry) | Not tested again | Remains deliberately excluded (TD-060, pre-existing) -- collides with the ordinary French adjective for "ripe." Still a real, undemonstrated gap. |

**Real, previously undocumented finding**: the gap was not just missing vocabulary in discovery *queries* -- it was missing vocabulary in the **relevance screen itself**. A new `zarzamora`-query source found three real, significant blackberry stories (including the Planasa "Yosemite" variety launch) that all scored **0** and were silently, confidently rejected by `screen_relevance()`, because `zarzamora` was never in the `berry_identity` category list -- only the discovery query recognized it, not the classifier deciding whether the discovered item was relevant. This is fixed (Section 9 below), not just documented.

## 3. Sources tested before adding anything new (Section 6)

| Source | Caneberry hits found (title scan of current window) |
|---|---|
| IBO | 0 (blueberry-only feed by design -- correct, not a gap) |
| FreshPlaza | 2 (already captured in Regional Coverage V4: global raspberry market overview, Finnish raspberry pricing) |
| Fruitnet | 0 in the sampled window (too sparse to judge, consistent with prior missions) |
| FreshFruitPortal | 3 (California raspberry harvest growth, PSG Rejoice blackberry platform -- already captured, Oregon blackberries) |
| Freshuelva | 0 (Huelva's current 10-item window is strawberry/general-focused; real, honest regional scarcity for caneberry specifically, not yet proven a discovery gap) |
| `source-news-search-uk-berry-growers` | 4 (heatwave blackberries, UK strawberry/raspberry pricing, "superfood" blackberries, UK raspberry best season) -- all pre-existing, never mined for caneberry before |
| `source-news-search-morocco-berry-fr` | 5 (multiple real, corroborated Moroccan raspberry export-record stories) -- pre-existing, never mined for caneberry before |
| `source-news-search-chile-morocco-trade` | 1 (Morocco frozen raspberry exports) |

This repeats Regional Coverage V4's own core finding exactly: **existing, blueberry-oriented regional query sources already carry real caneberry content -- they had simply never been read with caneberry in mind.** UK and Morocco alone yielded 9 real, previously-unmined caneberry headlines from sources onboarded for other reasons.

## 4. New mechanisms added (Section 9/10)

Three small, individually empirically-justified `news_search_rss` sources -- not a Cartesian query grid:

1. **`source-news-search-caneberry-global`** (English, global): `caneberry OR (raspberry OR blackberry) breeding OR variety OR acquisition OR licensing`. Justification: proven 100% precision on the bare term; existing sources are all country-scoped and structurally cannot reach company/breeder/university news that names no country (Fall Creek's acquisition, NC State's variety release, G-Berries' launch all fall in this gap). 100 items discovered, idempotent on re-run (0 new second pass).
2. **`source-news-search-mexico-zarzamora`** (Spanish, Mexico edition): `zarzamora`. Justification: Mexico is a major real caneberry producer (Jalisco/Michoacan); the existing generic `mora` vocabulary is real but the term Mexican trade press actually favors is `zarzamora`, proven to surface the real Yosemite variety story no other source found. 100 items discovered, idempotent (0 new second pass).
3. **`source-news-search-chile-frambuesa`** (Spanish, Chile edition): `frambuesa Chile exportacion OR congelada`. Justification: Chile is a real, major global raspberry exporter and a named priority geography, but the existing `source-news-search-chile-blueberry-es` query is blueberry-only and structurally cannot reach raspberry content. First live test found a real, on-topic result immediately. 37 items discovered, idempotent (0 new second pass).

All three passed `validate_records.py` after being added and were run twice each to prove idempotence (0 duplicates on the second pass, no trust bypass -- every discovered item still goes through the same two-stage relevance screen and human publication-review gate).

## 5. Relevance-screen vocabulary fix (Section 17)

`app/services/relevance_screen.py`'s `berry_identity` category gained `zarzamora`/`zarzamoras` and `caneberry`/`caneberries`. `app/services/deterministic_tagging.py`'s `BERRY_TERMS` gained the same two terms, with `caneberry`/`caneberries` deliberately listed under **both** `berry-raspberry` and `berry-blackberry` (it names the pair, not a single species) and `zarzamora`/`zarzamoras` under `berry-blackberry` only. This is a targeted, additive, data/vocabulary-level fix -- no schema change, no core-service rewrite, matching the mission's explicit preference for config/data fixes over core forks. `tests/` for both modules (30 tests) pass unchanged after the addition. Before the fix, the 3 real `zarzamora`-sourced items below scored 0 and were silently skipped; after the fix, identical inputs score 3 (`direct` tier) and are captured.

## 6. Caneberry Live Recall Set (Sections 3, 5)

18 real, dated, named-publisher events, geographically spread across UK, Mexico, Morocco, Spain, Chile, Netherlands, and the US/global company tier -- selected before checking capture status.

### Raspberry live recall -- 9/9 CAPTURED (100%)

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| Onubafruit scales Malaika raspberry plantings to 200 hectares (Spain, Huelva) | Hortidaily/Fruitnet, 2026-01-20 | Grower expansion | CAPTURED -- already trusted, published evidence (`ev-20260806173853-c7ff-...`), predates this mission. **Note:** `berry_ids: []` on this trusted record -- see Section 12. |
| UK raspberry growers celebrate best season in years | Fruitnet, 2025-06-19 | Production | CAPTURED (`ev-media-f5766ce7e2a24258c95e`) |
| Fall Creek Nursery adding blackberries and raspberries to its portfolio | Growing Produce, 2026-06-11 | Corporate strategy | CAPTURED (`ev-media-4fdb59e06a8ba94c8332`), tagged both `berry-raspberry` and `berry-blackberry` |
| WSU's new raspberry breeder begins, growers hope for new varieties | Capital Press/WSU Insider, 2026-04-28/05-04 | Breeder personnel | CAPTURED (`ev-media-7fe11d34a2c2c16d587e`) |
| FruitMasters hosts launch of Yumio raspberry brand | Fruitnet, 2026-02-10 | Variety/brand launch | CAPTURED (`ev-media-eb1644857fb0f2066d22`) |
| Morocco frozen raspberry exports hit a new record to France | AgriMaroc, 2025-12-18 | Export/trade | CAPTURED (`ev-media-4f86d98acadb7d99dc5c`) |
| Ava Monet raspberries launch across Aldi's Scotland stores | Fruitnet, 2026-07-14 | Retailer/commercial | CAPTURED (`ev-media-557f5523d982706cd103`) |
| Chile: frozen raspberry exports outperform despite fresh-fruit shipment decline | Diario Fruticola, 2026-05-13 | Export/trade | CAPTURED (`ev-media-546ff35899b064c7be46`) |
| Chile: the productive shift driving a raspberry renaissance | Portal Fruticola, 2026-03-27 | Production/strategy | CAPTURED (`ev-media-a8eb1f04ca47bcc96151`) |

### Blackberry live recall -- 7/9 CAPTURED (78%)

| Event | Publisher/date | Class | Result |
|---|---|---|---|
| Fall Creek Nursery adding blackberries and raspberries to its portfolio | Growing Produce, 2026-06-11 | Corporate strategy | CAPTURED (`ev-media-4fdb59e06a8ba94c8332`), same draft as the raspberry row above |
| Fall Creek readies for berry expansion with Berryplant and Berrytech acquisition | FreshFruitPortal, 2026-06-10 | Acquisition | **MISSED** -- Google News redirect returned no extractable article body (`empty_body`, TD-059 pattern) |
| NC State's Gina Fernandez launches latest blackberry variety | NC State University, 2026-07-22 | Breeder/university | CAPTURED -- already trusted (`ev-20260806173544-f46d-...`). **Note:** `berry_ids: []` -- see Section 12. |
| Genetic location of primocane-fruiting discovered in blackberries | EurekAlert!, 2026-05-11 | Scientific/breeding research | CAPTURED -- already trusted (`ev-20260806173540-b2b6-...`), correctly tagged `berry-blackberry` |
| Florida blackberry sector nears commercial viability, 4 varieties showing promise | FreshFruitPortal, 2026-05-22 | Grower/commercial viability | CAPTURED -- already trusted (`ev-20260806173540-d29c-...`), correctly tagged |
| Heatwaves make British blackberries sweeter than ever | Fruitnet, 2026-08-17 | Production/quality | CAPTURED (`ev-media-a91813437b19a33d5467`) |
| Planasa Mexico presents "Yosemite," a new high-yield blackberry variety | El Sol de Mexico, 2026-03-07/04-27 (3 corroborating sources) | New variety commercialization | CAPTURED (`ev-media-8aa83a0a3b75e8aaa3d9`) -- **only captured after the Section 5 vocabulary fix; scored 0 and was silently skipped before it** |
| Mexico: resistant fungus alert threatens blackberry production | AgroLatam, 2026-04-28 | Disease/agronomic impact | CAPTURED (`ev-media-bbcea5c31693e5e42e8f`) -- same fix-dependent capture |
| Michoacan leads Mexico's blackberry production at 242,000 tonnes | Gobierno del Estado de Michoacan, 2026-07-27 | Production statistic | CAPTURED (`ev-media-0321780152ec1969d8a9`) -- same fix-dependent capture |

A tenth real, well-corroborated Spain finding (Huelva blackberry acreage +2.4% to 172ha, tonnage +33% to 2,517t, Portal Fruticola/Fruitnet, Dec 2025) was verified via research but not found in Freshuelva's current 10-item RSS window or any other existing source -- reported as a real, honest **MISSED** with root cause "source window snapshot does not retroactively reach this dated article" (same structural limitation as TD-067), not pursued further since Freshuelva's current window has already been fully mined in this and the prior mission.

## 7. Off-sample generalization (Section 14)

Beyond the 18-event acceptance set, the three new sources' current windows contain real, additional, uncounted caneberry intelligence: a real Serbian raspberry-genetics investment story (Hortidaily), a real Wish Farms raspberry/blackberry breeding-trial story (already a fixed-benchmark event, BM-G-03, independently re-confirmed reachable via this new source), a real Spanish "Superior Taste Award" for Planasa's Pink Hudson raspberry variety, and a real EU BreedingValue Project consortium research story. This is exactly the generalization the mission asked for -- the fix and the sources are not tuned to the 18 selected events; they surface real caneberry news broadly.

## 8. Review economics (Section 15)

17 discovered items were run through the full relevance-gate pipeline this mission (14 new drafts created, 4 already matched existing trusted evidence with 0 new review burden, 1 real acquisition failure with 0 review burden). Zero items were discarded as duplicate/irrelevant after reaching the gate -- the same title-scan-before-processing discipline established in Regional Coverage V4 kept review cost proportional to real relevance. This is an operational-load count only; real analyst accept/reject history is Codex's separate review-outcome-instrumentation lane.

## 9. Canonical inventory baseline (Section 1)

Counted directly against canonical, by `berry_ids` tag (strawberry/blueberry shown only as context, per the mission's own instruction not to over-interpret raw differences):

| Class | Blueberry | Strawberry | Raspberry | Blackberry |
|---|---|---|---|---|
| Varieties | 41 | 6 | 12 | 1 |
| Companies | 36 | 11 | 12 | 7 |
| Breeding programs | 9 | 3 | 1 | **0** |
| Trusted Evidence | 484 | 292 | 191 | 146 |
| Inbox Evidence (drafts) | 378 | 299 | 70 | 54 |
| Facts (via entity/evidence linkage; company-level linkage over-counts multi-berry companies, see caveat below) | 186 | 41 | 19 | 13 |
| Relationships involving >=1 Variety entity (precise, no company over-tagging) | 89 | 6 | 12 | 1 |
| Signals | 6 | 0 | 0 | 0 |
| Assessments | 4 | 0 | 0 | 0 |
| Sources tagged | 116 | 88 | 78 | 79 |
| Commercial observations (inbox drafts) | 4 | 6 | 3 | 5 |
| Patent/PVR filings, `patent_filing` (inbox drafts) | 15 | 15 | 15 | 15 |
| CPVO-referencing evidence specifically | 23 | 4 | 4 | **0** |

**Caveat on Facts**: berry scope for Facts is resolved via linked entity/evidence `berry_ids`, and a Fact linked only to a multi-berry Company entity (e.g. Driscoll's, tagged all 4 berries) inherits all 4 tags even if the underlying fact is species-specific -- this inflates the blueberry figure. Relationships involving a Variety entity are precise (a Variety has exactly one `berry_ids` value) and are the more trustworthy per-species figure: 108 of 226 total relationships involve a Variety at all; of those, blueberry still dominates (89) but raspberry (12) clearly outpaces blackberry (1).

**Signals and Assessments are 100% blueberry** -- zero raspberry or blackberry Signal or Assessment exists in canonical. Given the underlying Evidence base for raspberry (191 trusted) and blackberry (146 trusted) is not trivially small, this is a real, notable gap worth naming even though this mission does not build Signal-generation logic.

**A separate, important measurement-integrity finding**: ~45% of all trusted Evidence (574 of 1,266 records) carries no `berry_ids` at all (a known, pre-existing fact, already noted in the Coverage Matrix). Checking those 574 untagged records' own titles/summaries for species keywords found 27 mentioning a raspberry term and 21 mentioning a blackberry term -- real caneberry content sitting invisible to any berry-filtered count, including every number in the table above and every number in Regional Live Recall Set V1's own berry-distribution tally. This does not reverse the overall finding (blueberry-mentioning untagged records number 187, proportionally larger still), but it means the true raspberry/blackberry baseline is understated by roughly 10-15% by any `berry_ids`-filtered measurement. Registered as new debt (TD-071).

## 10. Variety / breeding source coverage (Section 7, 11)

`app/services/cpvo_registry.py`'s `discover()` builds its query candidates **from the platform's own already-tracked Variety entities' names and aliases** -- it is not a blanket per-species search of CPVO's register. With only 1 tracked blackberry Variety entity in canonical (vs. 12 for raspberry, 41 for blueberry), CPVO monitoring structurally can only ever issue ~1 real query for blackberry, regardless of how much real blackberry breeding activity CPVO's own register actually contains. This is the precise, previously-undocumented root cause of blackberry's 0 CPVO hits: **not CPVO scarcity, but variety-catalog scarcity feeding a query mechanism that depends on already knowing the names it should search for** -- a real chicken-and-egg architecture finding, not a source-access problem. The same real, currently-untracked variety this mission found in trade press (Planasa's "Yosemite"/"Black Yosemite" blackberry) is a live, concrete test case for a future mission: adding it as a tracked Variety entity (once real evidence grounds it, which this mission's own captures now provide) would let CPVO monitoring query for it for the first time.

The 15/15/15/15 exactly-even split of `patent_filing` inbox drafts across all four berries (all US-jurisdiction plant patents, zero CPVO among them) indicates the underlying US patent-monitor query is deliberately per-berry-balanced by design, unlike news discovery's organically imbalanced volume -- confirms patent/PVR discovery mechanics are NOT currently a source of the caneberry imbalance; the imbalance is concentrated in news discovery and in the CPVO variety-name-seeded mechanism above.

## 11. Entity gaps (Section 8)

Already registered with real evidence backing: Planasa, Fall Creek Farm & Nursery, Advanced Berry Breeding, Wish Farms (all pre-existing Company entities, all now further corroborated by this mission's own real captures). **Not registered anywhere** (neither Company nor breeding_program): NC State University's caneberry breeding program (Gina Fernandez), Washington State University's raspberry breeding program, Onubafruit (Spain, real grower/marketer of the Malaika raspberry variety, corroborated by 2 independent real publishers), G-Berries, FruitMasters. Per the same evidence-grounding discipline upheld in Regional Coverage V4 (do not create entities from a single headline, only when real trusted Evidence already exists), **no new entities were created this mission** despite now having real Evidence for several of these -- the gap and its impact are documented here for a future mission's deliberate consideration, not acted on ad hoc. Missing-entity impact: without a registered entity, none of these actors' future coverage can benefit from query-provenance corroboration (the same mechanism TD-069 already documents for UK retailers) -- Onubafruit's real, 2-source-corroborated Malaika story is the clearest concrete case, and is also the story showing the `berry_ids: []` tagging gap (Section 12).

## 12. Untagged trusted Evidence found by this mission (new observation)

Two of this mission's "already captured" matches (Onubafruit/Malaika raspberry, NC State/Gina Fernandez blackberry) are real, correctly-existing trusted Evidence records with `berry_ids: []` -- genuinely about raspberry/blackberry but invisible to any berry-scoped view, search filter, or recall measurement (including this mission's own Section 9 baseline and Regional Live Recall Set V1's berry-distribution tally). This is the same class of gap as the broader 574-untagged-records finding in Section 9, caught here as two concrete, real, named instances rather than only an aggregate count. Not fixed in place this mission (editing already-trusted, published records is a deliberately higher-friction action reserved for a dedicated data-quality pass, not a side effect of an unrelated mission) -- registered as part of TD-071.

## 13. Architecture / berry-portability findings (Section 17)

- **Real bug found and fixed**: `relevance_screen.py`'s `berry_identity` vocabulary treats each berry symmetrically in principle (English + Spanish + Italian + French additions have all targeted "all four berries rather than patching strawberry alone," per the code's own comments) but in practice had silently accumulated two real caneberry gaps (`zarzamora`, `caneberry`) that made real blackberry/raspberry content score 0 and get silently dropped -- this was a genuine gap in an otherwise berry-neutral design, not a structural blueberry-first bias. Fixed additively.
- **Real, separate gap found, not fixed this mission**: `deterministic_tagging.py`'s `BERRY_TERMS` (the tagging vocabulary, a different code path from the relevance-screen gate) has zero French vocabulary for any berry -- this is symmetric across all four berries (not caneberry-specific) but was only discovered while auditing caneberry terminology. TD-072.
- **CPVO's variety-name-seeded query design** (Section 10) is a real, generalizable architecture pattern, not code that "assumes blueberry" -- but its practical effect is that any berry with a thin Variety catalog gets thin CPVO coverage regardless of real-world CPVO activity, a structural, self-reinforcing gap the mission was asked to identify.
- **No hardcoded blueberry/strawberry assumption was found** in the discovery, relevance-screening, or berry-tagging code paths themselves -- every mechanism examined (Stage A/B relevance screen, deterministic tagging, CPVO registry, patent monitor) is genuinely parameterized by berry, and the measured imbalance traces to **data volume and query/vocabulary completeness**, not code-level bias. This is a materially different, more encouraging finding than "the architecture assumes blueberry."

## 14. Deliberate stop cases (Section 18/19 synthesis)

- **Freshuelva** (Spain): current window carries 0 caneberry content; real regional scarcity (Huelva is predominantly strawberry/blueberry) more likely than a discovery gap, but not proven either way with only one 10-item window sampled -- not pursued further this mission.
- **Fall Creek/Berryplant acquisition** and the **Spain Huelva blackberry-acreage** story: both real, both verified via research, both currently unreachable (Google News redirect failure; RSS-window snapshot limitation respectively) -- both share already-known root causes (TD-059, TD-067-style limitation) rather than representing new architecture problems.
- **French blackberry vocabulary** (`mûre`/`mûres`): remains deliberately excluded (TD-060) -- this mission did not attempt to resolve the real collision risk with the French adjective "ripe."
- **New Company/breeding-program entities**: real gaps identified (Section 11), deliberately not created this mission per the established evidence-grounding discipline.

## 15. Answer to the mission's core question

**Both, in different proportions.** Raspberry's 0% in Regional Live Recall Set V1 was substantially a sampling artifact -- a dedicated, geography-spread search this mission found 9/9 real raspberry events captured, including from sources that were already active before this mission (UK, Morocco) and had simply never been read with raspberry in mind. Blackberry's 4% (1/25) reflects a real, smaller genuine gap: 7/9 events captured, but the two real misses are architecturally distinct (one relevance-screen vocabulary gap that is now fixed, one acquisition-access failure), and blackberry's own canonical baseline (0 breeding programs, 1 tracked variety, 0 CPVO filings, 0 Signals/Assessments) is measurably thinner than raspberry's across nearly every class in Section 9 -- a real, if smaller than feared, genuine coverage gap, not purely a sampling effect.
