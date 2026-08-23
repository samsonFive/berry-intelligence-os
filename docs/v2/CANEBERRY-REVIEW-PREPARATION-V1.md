# Caneberry Review Preparation V1

**Mission:** Review preparation only (2026-08-23, branch `docs/caneberry-review-preparation-v1`). The agent organizes; the analyst decides. **No publication status, trust state, Evidence, Fact, Relationship, Signal, Assessment, or Variety identity was changed by this mission.** Every item below remains exactly as discovered/tagged by prior missions -- `status: draft`, `review_state: in_review`.

## Caneberry backlog snapshot

**114 pending publication drafts** carry `berry-raspberry` and/or `berry-blackberry` in `berry_ids` (of 856 total `inbox/evidence/` drafts). Verified clean of the known negation-text false-positive trap (TD-073) -- zero of the 114 contain an AI-disclaimer "does not appear directly relevant to... blueberry, strawberry, raspberry, blackberry" pattern; all 114 are genuine content-based tags via the pre-enrichment `apply_deterministic_tags()` path.

| | Count |
|---|---:|
| Raspberry-only | 54 |
| Blackberry-only | 37 |
| Multi-berry (both raspberry + blackberry, or + blueberry/strawberry) | 23 |
| **Total** | **114** |
| `relevance_tier: direct` | 46 |
| `relevance_tier: None` (never Stage-A-screened; see TD-070) | 68 |
| Age | 1-4 days (all captured 2026-08-19 to 2026-08-22) |

**By source (top contributors):** USPTO plant patent via Google Patents (30), openFDA food recalls (12), Driscoll's mainstream-news search (8), Spain/Huelva Spanish-language search (8), UK berry-growers search (8), Open Food Facts retail listings (8), CPVO public register (6), Fresh Fruit Portal (4), Morocco French-language search (4), the new caneberry-global source (4).

**By geography:** US 40, none-tagged 33, UK 25, Europe 15, Spain 11, Mexico 6, North America 4, Morocco 4, Netherlands 3, France 2.

**A real, honest composition finding**: raw `berry_ids` correctness does not mean review-worthiness. 12 of the 114 are openFDA recalls of *raspberry-flavored consumer products* (honey spread, ice cream, croissants, coffee cake) -- real, correctly tagged, but not caneberry variety/actor/commercial intelligence in the sense this platform tracks. 8 of the 114 are generic Open Food Facts retail-listing observations (real but low individual signal). One item (`ev-media-46bcb6b1620f71432ccf`, "BlackBerry Bold 9780 now available from T-Mobile UK") is the **phone**, not the fruit -- a real pre-existing tagging-precision gap from the "Driscoll's"/"berry tar..." keyword source bucket, flagged here for future correction, not touched.

## Top review batch

16 items selected (within the 10-20 target), prioritized for variety identity, breeder/rights relationships, and significant company/production events. Every item is reachable at `/review/{id}` in the existing publication-review UI -- no parallel workflow created.

### 1-2. CPVO Ouachita and Ponca (the named targets) -- see dedicated packets below.

### 3. Pink Hudson raspberry -- Superior Taste Award
- **ID / URL**: `ev-media-c8cdb7133db1cae0bf66` / `/review/ev-media-c8cdb7133db1cae0bf66`
- **TITLE**: Planasa's Pink Hudson(R) raspberry awarded the Superior Taste Award by the International Taste Institute
- **SOURCE**: Planasa Newsroom (company's own primary source) | **DATE**: 2026-08-20 (captured)
- **BERRY**: Raspberry | **COMPANY**: Planasa (existing entity) | **VARIETY**: "Pink Hudson" -- not yet a tracked Variety entity
- **WHY THIS ITEM MATTERS**: A real, quantified, primary-source award claim for a raspberry variety Planasa has not yet been credited with in the platform's Variety catalog -- Planasa's only current raspberry-adjacent presence is via the Yosemite (blackberry) headline below.
- **EXACT SOURCE CLAIM**: "Planasa's Pink Hudson(R) raspberry variety received the Superior Taste Award (90.7 points, Three Stars) from the International Taste Institute."
- **RELEVANT EXCERPT**: "...recognizing exceptional sensory quality and consumer appeal. The award validates the breeding program's focus on combining agronomic performance (high yields, adaptability to double cropping and winter production) with superior taste attributes."
- **WHAT IT WOULD SUPPORT IF TRUSTED**: A new `variety-pink-hudson` entity (raspberry), a `develops` relationship to Planasa, and a real, quantified trait claim (90.7-point Superior Taste Award score).
- **EXISTING RELATED TRUSTED EVIDENCE**: None yet for Pink Hudson specifically; Planasa itself is an existing, evidence-grounded Company entity.
- **INDEPENDENT CORROBORATION**: None found in the current backlog beyond Planasa's own newsroom -- single-source, primary.
- **LIMITATIONS / DOES_NOT_PROVE**: Company's own press release; no independent trade-press corroboration found yet; does not establish commercial acreage or market share.
- **RECOMMENDED ANALYST QUESTION**: Is a single primary-source company announcement (with a real, specific, third-party-awarded score) sufficient standalone grounding for a new Variety entity, or should independent trade-press corroboration be sought first?

### 4. Planasa varieties -- European retailer interest (multi-berry, names Black Sultana blackberry)
- **ID**: `ev-media-069f07925d20b2d93743` / `/review/ev-media-069f07925d20b2d93743`
- **SOURCE**: Planasa Newsroom | **DATE**: 2026-08-20 | **BERRY**: multi (strawberry, blueberry, raspberry, blackberry)
- **WHY IT MATTERS**: Names a real, specific blackberry variety ("Black Sultana") and corroborates Pink Hudson (raspberry) from a second Planasa source, in a real retailer-facing commercial context (UK and Netherlands retail delegations).
- **EXACT SOURCE CLAIM**: "Key marketed varieties include... Pink Hudson raspberry, and Black Sultana blackberry, with emphasis on advanced breeding pipeline acceptance across European markets."
- **WHAT IT WOULD SUPPORT IF TRUSTED**: A new `variety-black-sultana` (blackberry) entity and a second, corroborating evidence link for Pink Hudson.
- **INDEPENDENT CORROBORATION**: Same publisher (Planasa) as item 3, not independent -- but a different specific article/event (a retail showcase, not the taste award).
- **LIMITATIONS**: Company's own marketing framing ("arise the interest of major European retailers"); no named retailer quoted directly; no acreage/volume figures.
- **RECOMMENDED ANALYST QUESTION**: Does this count as a second Planasa-sourced item (same publisher, different event) toward corroborating Pink Hudson, or should it be treated as fully independent grounding only for Black Sultana?

### 5. Planasa breeding programmes -- 2026 Superior Taste Award trend
- **ID**: `ev-media-d2406f3e7a6de96c4fa1` / `/review/ev-media-d2406f3e7a6de96c4fa1`
- **SOURCE**: Planasa Newsroom | **DATE**: 2026-08-20 | **BERRY**: blueberry/strawberry/raspberry (no blackberry)
- **WHY IT MATTERS**: Places Pink Hudson's award in a real, dated context ("six Superior Taste Awards... in 2026... building on the earlier Three-Star award for Pink Hudson(R) raspberry variety") -- a third, same-publisher reference reinforcing the same real award claim with a specific award count.
- **LIMITATIONS**: Same-publisher reinforcement, not independent corroboration.
- **RECOMMENDED ANALYST QUESTION**: Treat as supporting context for item 3, not a separate item requiring its own trust decision.

### 6. Yosemite -- see dedicated packet below.

### 7. Fall Creek adds raspberries and blackberries to its portfolio
- **ID**: `ev-media-4fdb59e06a8ba94c8332` / `/review/ev-media-4fdb59e06a8ba94c8332`
- **SOURCE**: Growing Produce | **DATE**: 2026-06-11 (published) | **BERRY**: raspberry + blackberry
- **COMPANY**: Fall Creek Farm & Nursery (existing entity, historically blueberry-focused)
- **WHY IT MATTERS**: A real, significant corporate-strategy expansion -- a major blueberry breeder entering caneberries for the first time. Directly corroborated by the Fall Creek/Berryplant/Berrytech acquisition story already found in a prior mission's own trusted-evidence audit.
- **WHAT IT WOULD SUPPORT IF TRUSTED**: A new `expands_into`/strategic-scope fact on the existing Fall Creek entity; potential future relationship once specific acquired varieties are named.
- **EXISTING RELATED TRUSTED EVIDENCE**: `ev-20260806173541-de69-fall-creek-acquires-berryplant-berrytech` (already trusted, published) covers the related Berryplant/Berrytech acquisition -- real, same real corporate story from a different angle.
- **INDEPENDENT CORROBORATION**: Yes -- the already-trusted acquisition article is independent corroboration of the same real strategic move.
- **RECOMMENDED ANALYST QUESTION**: Does the already-trusted acquisition Evidence make this specific "portfolio expansion" framing redundant, or does it add a distinct, citable claim (the portfolio-expansion framing itself)?

### 8. Ava Monet raspberries launch across Aldi's Scotland stores
- **ID**: `ev-media-557f5523d982706cd103` / `/review/ev-media-557f5523d982706cd103`
- **SOURCE**: Fruitnet | **DATE**: 2026-07-14 | **BERRY**: raspberry
- **WHY IT MATTERS**: Real, specific commercial retail launch naming a variety ("Ava Monet") not yet tracked.
- **WHAT IT WOULD SUPPORT IF TRUSTED**: A new `variety-ava-monet` (raspberry) entity and a real retailer/marketer relationship (Aldi Scotland).
- **INDEPENDENT CORROBORATION**: None found yet in the current backlog -- single source.
- **RECOMMENDED ANALYST QUESTION**: Is a single trade-press retail-launch article sufficient for a new Variety entity, matching the bar already used for Amalia Rossa/Malaika (also single- or few-source trade press)?

### 9. FruitMasters hosts launch of Yumio raspberry brand
- **ID**: `ev-media-eb1644857fb0f2066d22` / `/review/ev-media-eb1644857fb0f2066d22`
- **SOURCE**: Fruitnet | **DATE**: 2026-02-10 | **BERRY**: raspberry
- **WHY IT MATTERS**: A real, named raspberry brand/variety launch by a Dutch grower cooperative not yet represented as an entity.
- **LIMITATIONS**: Title/summary only in this draft; whether "Yumio" is a brand (platform) or a single cultivar, mirroring the Rejoice/BK-6-13 distinction already modeled for blackberry, is not yet clear from the stored text alone.
- **RECOMMENDED ANALYST QUESTION**: Does the full article (not yet fetched into this draft's summary) clarify whether Yumio is a brand or a specific cultivar?

### 10. Growers hope for new varieties from WSU's new raspberry breeder
- **ID**: `ev-media-7fe11d34a2c2c16d587e` / `/review/ev-media-7fe11d34a2c2c16d587e`
- **SOURCE**: Capital Press | **DATE**: 2026-08-22 | **BERRY**: raspberry
- **WHY IT MATTERS**: Real breeder-personnel/program news for Washington State University, a real public institution not yet an entity in the caneberry graph.
- **WHAT IT WOULD SUPPORT IF TRUSTED**: A new `company-washington-state-university` entity (breeder role), mirroring the University of Arkansas precedent.
- **RECOMMENDED ANALYST QUESTION**: Does this article name any specific released variety, or only a personnel/program-continuation story (in which case it grounds the institution, not yet a Variety)?

### 11. Zarzamora disease alert -- resistant fungus threatens Mexican production
- **ID**: `ev-media-bbcea5c31693e5e42e8f` / `/review/ev-media-bbcea5c31693e5e42e8f`
- **SOURCE**: AgroLatam | **DATE**: 2026-08-22 | **BERRY**: blackberry | **GEOGRAPHY**: Mexico
- **WHY IT MATTERS**: A real, significant agronomic-risk event (disease/agronomic commercial impact class) -- Mexico is a major real blackberry (zarzamora) producer.
- **LIMITATIONS**: Title-only summary (Google News redirect body-fetch limitation, TD-059) -- exact fungus species, affected acreage, and grower response are not yet captured.
- **RECOMMENDED ANALYST QUESTION**: Is the headline-level claim (a resistant fungus threatens production) sufficient for a Fact, or does this need body-text acquisition first?

### 12. Michoacán leads Mexico's blackberry (zarzamora) production at 242,000 tonnes
- **ID**: `ev-media-0321780152ec1969d8a9` / `/review/ev-media-0321780152ec1969d8a9`
- **SOURCE**: Gobierno del Estado de Michoacán (state government) | **DATE**: 2026-08-22 | **BERRY**: blackberry | **GEOGRAPHY**: Mexico
- **WHY IT MATTERS**: A real, quantified, government-sourced production statistic for the region most associated with Yosemite (item 6) and the disease alert (item 11) -- real regional context.
- **LIMITATIONS**: Title-only; the exact reporting period/methodology for "242,000 tonnes" is not captured in this draft.
- **RECOMMENDED ANALYST QUESTION**: Government-source authority is generally high -- does the source alone (a state government release) justify treating the tonnage figure as a citable Fact once trusted?

### 13. Chile: frozen raspberry exports outperform despite fresh-fruit decline
- **ID**: `ev-media-546ff35899b064c7be46` / `/review/ev-media-546ff35899b064c7be46`
- **SOURCE**: Diario Fruticola | **DATE**: 2026-05-13 | **BERRY**: raspberry | **GEOGRAPHY**: Chile
- **WHY IT MATTERS**: Real production/export-shift class event for a major raspberry-exporting country.
- **RECOMMENDED ANALYST QUESTION**: Ready for review as a market-context Fact; no entity/relationship unlock expected.

### 14. Chile: the productive shift driving a raspberry renaissance
- **ID**: `ev-media-a8eb1f04ca47bcc96151` / `/review/ev-media-a8eb1f04ca47bcc96151`
- **SOURCE**: Portal Fruticola | **DATE**: 2026-03-27 | **BERRY**: raspberry | **GEOGRAPHY**: Chile
- **WHY IT MATTERS**: Corroborates item 13's real Chile-raspberry trend from a second, independent Chilean publisher.
- **RECOMMENDED ANALYST QUESTION**: Treat items 13+14 as a real, two-source-independent Chile raspberry recovery story.

### 15. UK raspberry growers celebrate best season in years
- **ID**: `ev-media-f5766ce7e2a24258c95e` / `/review/ev-media-f5766ce7e2a24258c95e`
- **SOURCE**: Fruitnet | **DATE**: 2026-06-19 | **BERRY**: raspberry | **GEOGRAPHY**: UK
- **WHY IT MATTERS**: Real UK raspberry-sector production event, distinct geography from the Mexico/Chile items above.
- **RECOMMENDED ANALYST QUESTION**: Ready for review; no specific variety named, market-context only.

### 16. Naturipe/Hortifrut genetics platform expansion (names Vicentina raspberry award)
- **ID**: `ev-media-a97058df46f85e52e1a3` / `/review/ev-media-a97058df46f85e52e1a3`
- **SOURCE**: International Blueberry Organization (Spanish-language) | **DATE**: 2026-07-30 | **BERRY**: multi (blueberry/raspberry/blackberry)
- **COMPANY**: Naturipe Farms, Hortifrut (both existing entities)
- **WHY IT MATTERS**: Names a real, specific, awarded raspberry variety not yet tracked: "Hortifrut's raspberry variety Vicentina won first place at the 2026 UK National Cherry and Soft Fruit Show."
- **EXACT SOURCE CLAIM**: "...demonstrating market-recognized results from their Rubus breeding program."
- **WHAT IT WOULD SUPPORT IF TRUSTED**: A new `variety-vicentina` (raspberry) entity and a `develops` relationship to Hortifrut (a real, quantified competition placement, not just a company claim).
- **INDEPENDENT CORROBORATION**: None found yet in the current backlog for the Vicentina award specifically -- worth a targeted search before trusting.
- **RECOMMENDED ANALYST QUESTION**: Is a real, named competition placement (UK National Cherry and Soft Fruit Show, first place) sufficient standalone grounding for a new Variety entity?

## Yosemite packet

- **ID / URL**: `ev-media-8aa83a0a3b75e8aaa3d9` / `/review/ev-media-8aa83a0a3b75e8aaa3d9`
- **TITLE**: "Planasa México presenta Yosemite, nueva variedad de zarzamora con alto rendimiento y mayor vida de anaquel" (El Sol de México)
- **SOURCE**: Google News search (Spanish, Mexico): zarzamora | **DATE**: 2026-03-07 (published), 2026-08-22 (captured)
- **BERRY**: Blackberry (zarzamora) | **COMPANY**: Planasa (already an existing, evidence-grounded entity) | **GEOGRAPHY**: Mexico (not tagged on the record itself -- a real, minor gap)

**What source supports the Variety identity?** Only the headline text itself -- AI enrichment was **skipped** ("no completer or empty publisher text"), and the `summary` field is a literal repeat of the title. Full article body was never successfully extracted (Google News redirect `empty_body` pattern, TD-059). This is a genuinely thin record.

**Is the Planasa relationship explicit?** The headline names "Planasa México presenta Yosemite" (Planasa Mexico presents Yosemite) -- explicit at the headline level, but not independently confirmed by full article text since the body was never fetched.

**Berry species**: Blackberry, correctly tagged (zarzamora = blackberry in Mexican Spanish).

**Commercial vs. legal denomination**: Cannot be determined from this record. "Yosemite" is the only name given; no CPVO/USPTO filing under this name currently exists in the system (checked: no CPVO or patent draft for "Yosemite" was found in this backlog audit).

**Independent corroboration**: **None currently in the system.** A search of all 856 pending drafts for "Yosemite" found exactly this one record. (Real corroborating headlines for this same story were seen during live research in a prior mission but were never independently captured as separate Evidence records in this backlog.)

**What remains untrusted today**: Everything -- species-species identity, the Planasa relationship, and the variety's real-world existence all rest on one thin, unenriched headline. Per the established evidence-grounding discipline (every existing Variety entity requires trusted, published Evidence), **this item alone does not currently meet the bar that was used to create Ervin, Ponca, or Ouachita** (each of which has a real, if sometimes single-source, populated summary with substantive claim text) -- the Yosemite record's summary is empty of any claim beyond the headline. **No Variety entity was created for Yosemite by this or any prior mission, and this mission does not recommend treating a bare headline as sufficient even after human trust review** unless the analyst can independently verify the claim (e.g., via Planasa's own newsroom, which was searched for this mission's other picks and did not surface a Yosemite item).

## CPVO Ponca packet

- **ID / URL**: `ev-cpvo-cpvo-8ac7b2bd779acb96` / `/review/ev-cpvo-cpvo-8ac7b2bd779acb96`
- **Official registry provenance**: CPVO public register (`online.plantvarieties.eu`), live API acquisition, `source_tier: tier_1_primary`, `source_authority: high`.
- **Denomination**: Ponca | **Species/genus**: *Rubus subg. Rubus* (correct blackberry genus)
- **Applicant field**: "The Board of Trustees of the University of Arkansas" -- matches the existing `company-university-of-arkansas` entity (auto-suggested at `medium` confidence via alias match).
- **Filing/application status**: Application `20220270`, filed 2022-01-28; **granted** 2026-04-20, grant number `72077`; `title_status: approved`; expires 2056-12-31. Examined by Bundessortenamt (Germany).
- **Corresponding existing Variety entity**: `variety-ponca` (created in Caneberry Variety + Actor Expansion V1), already suggested at `high` confidence.
- **What this filing proves**: A real, granted, EU-wide plant variety right exists for "Ponca," applied for by the named University entity.
- **What it does NOT prove** (from the record's own `does_not_prove` field): commercialization or planted acreage; market adoption or sales success; commercial launch timing; that the applicant is necessarily the breeder (applicant/breeder can differ); licensee identity or exclusive territory; that this is the variety's only registered right in any jurisdiction.
- **Not auto-promoted**: remains `status: draft`, `review_state: in_review`, `verification_state: unverified`.

## CPVO Ouachita packet

- **ID / URL**: `ev-cpvo-cpvo-1e923ddc1c182018` / `/review/ev-cpvo-cpvo-1e923ddc1c182018`
- **Official registry provenance**: same source as Ponca, same tier/authority.
- **Denomination**: Ouachita | **Species/genus**: *Rubus subg. Rubus*
- **Applicant field**: "The Board of Trustees of the University of Arkansas" -- same match as Ponca.
- **Filing/application status**: Application `20062430`, filed 2007-03-29; **granted** 2012-05-07, grant number `32662`; `title_status: approved`; expires 2042-12-31. Same examination office.
- **Corresponding existing Variety entity**: `variety-ouachita`, `high`-confidence suggested match.
- **What this filing proves / does not prove**: identical caveats to Ponca above.
- **Real, additional context**: this is the *older* of the two grants (2012 vs. 2026) -- consistent with Ouachita being the 2003-released, already-recognized variety and Ponca being the newer release, both from the same real University of Arkansas program.

## Duplicate / reprint groups

Identified within the 114-item backlog (not force-collapsed; reported for analyst awareness):

- **Aldi/Driscoll's UK blackberry commitment** (5 items, real independent multi-publisher coverage of one commercial event): Grocery Gazette, Fruitnet, Hort News, plus 2 near-duplicate Good Housekeeping award articles. Genuinely independent angles (commit-to-stock, 20%-uplift-forecast, award), not exact reprints -- **not** included in the top batch; noted as a real corroboration cluster, one item would suffice if the analyst wants this story.
- **Huelva (Spain) 2025/26 red-fruit campaign wrap-up** (8 items across the Spanish-language search): "Las borrascas condicionan/reducen la campaña..." appears near-verbatim from at least 3 different Spanish publishers (Valencia Fruits-style wire reprints), plus 5 more distinct campaign-summary angles. Real, but heavily reprint-clustered -- **not** included in the top batch; already substantially covered by the already-trusted Freshuelva evidence from a prior mission.
- **Morocco raspberry export record** (4 items, French-language): "Le Maroc bat un nouveau record d'exportation..." reprinted/rephrased across AgriMaroc, YOP L-FRII, Linformation.ma, Le Matin.ma covering the same real underlying trade statistic -- **not** included in the top batch (already substantially corroborated in a prior mission's own trusted-evidence audit).
- **Lidl £500m UK berry commitment** (2 items, Sustainability Magazine + FarmingUK): same real press release, two publishers -- **not** included; generic-berry, not caneberry-variety-specific.

## Lower-priority pending items

Deliberately deferred from this packet, not because they are irrelevant, but because they are lower-value for a variety/actor-identity-focused review pass:

- **12 openFDA recall notices** (raspberry-flavored consumer products: honey spread, ice cream, coffee cake, croissants) -- real food-safety events, zero variety/breeder/company-relationship value.
- **8 Open Food Facts retail-listing observations** -- real but generic ("Tesco listing observed -- British Raspberries"); useful for future commercial-observation volume, not identity-unlocking on their own. One (`ev-obs-openfoodfacts-03257272`, "Victoria Blackberries") is already correctly linked to the existing `variety-victoria` entity.
- **~18 of the 30 USPTO plant-patent drafts** not already covered by the Blackberry/Raspberry Vertical V1 audit (e.g. "Simona," "Stella," "Finnberry," "PS-10.062-11," several "DrisRasp"-series numbers) -- real, but individually lower-priority than the CPVO grants above; a dedicated future patent-review pass would suit these better than folding them into this small batch.
- **UN Comtrade trade-flow record** (raspberry+blackberry combined HS code) -- real trade statistics, not species-separable (HS-6 limitation, already-known), not variety-identity-relevant.
- **Consumer-tips content** ("How to wash/store raspberries") -- real but not competitive intelligence.
- **1 mistagged item** (BlackBerry Bold 9780 phone) -- real tagging-precision gap, not a review candidate at all.

## Expected entity/relationship unlocks

If trusted, the top-16 batch would newly unlock (subject to the analyst's own trust decision, not asserted here as fact):

| New/strengthened object | From item(s) |
|---|---|
| `variety-pink-hudson` (raspberry) + `develops` to Planasa | 3, 4, 5 |
| `variety-black-sultana` (blackberry) + `develops` to Planasa | 4 |
| `variety-vicentina` (raspberry) + `develops` to Hortifrut | 16 |
| `variety-ava-monet` (raspberry) | 8 |
| `variety-yumio` (raspberry, pending body confirmation of brand-vs-cultivar) | 9 |
| `company-washington-state-university` (breeder) | 10 |
| CPVO-grounded rights confirmation for `variety-ponca`, `variety-ouachita` | 1, 2 |
| Fall Creek strategic-scope strengthening | 7 |
| Real Mexico/Chile/UK production-context Facts | 11, 12, 13, 14, 15 |

## Review UI accessibility

Every selected item is reachable at its existing `/review/{id}` URL (advanced publication review) and would also surface in `/review?kind=publication` and `/pending`'s existing triage buckets -- confirmed by route inspection (`app/main.py`), no new route or template created.

## Review-event instrumentation proof

Per `docs/v2/REVIEW-OUTCOME-INSTRUMENTATION-V1.md`, the `publication_review` workflow already instruments Publish and Reject, and `publication_triage` instruments Dismiss/Restore, for every item in this packet -- no code change needed. When a human later acts on any of these 16 (or any other pending item), a compact append-only event (actor, workflow, object ID, action, prior/new state, Source class/query/geography/berry context) will be recorded automatically under `inbox/review_events/`. **No events were generated by this mission** -- confirmed via `git status`/`inbox` inspection: zero files created under `inbox/review_events/` or any trusted `data/` path.

## Direct answers

1. **114** pending caneberry drafts (54 raspberry-only, 37 blackberry-only, 23 multi-berry).
2. **The 16 in the Top review batch above** -- 2 CPVO grants (Ponca, Ouachita), 3 Planasa primary-source variety/award items, 1 Yosemite (thin, flagged), 4 real company/variety events (Fall Creek, Ava Monet, Yumio, WSU), 2 Mexico production/disease events, 2 Chile production events, 1 UK production event, 1 Naturipe/Hortifrut genetics platform (names Vicentina).
3. **~19 duplicate/reprint items** identified across 4 real clusters (5 Aldi/Driscoll's, 8 Huelva campaign, 4 Morocco export-record, 2 Lidl) -- none occupy a batch slot; each cluster's real story is preserved via 1 representative note.
4. **The Naturipe/Hortifrut item (16)** and the **2 Planasa items (3, 4)** would unlock the most graph data -- each names a real, specific, previously-untracked variety (Vicentina, Pink Hudson, Black Sultana) tied to an already-existing Company entity, the exact pattern that unlocked Ervin/Ponca/Ouachita in the prior mission.
5. **Not yet.** Yosemite's only evidence is a bare, AI-enrichment-skipped headline with no independent corroboration in the system -- genuinely thinner than the bar met by every currently-trusted Variety entity. Ready for a human look, but this report does not recommend treating it as sufficient without further verification.
6. **Yes, both are genuinely ready.** Both carry complete, authoritative CPVO registry data (application/grant numbers, dates, examination office, applicant, `does_not_prove` caveats already populated) -- exactly the shape of record the existing review workflow is designed to adjudicate.
7. If Ponca/Ouachita are trusted: their CPVO grant becomes citable rights-confirmation Evidence for the existing Variety entities. If the Planasa/Naturipe items are trusted: 3 new Variety entities (Pink Hudson, Black Sultana, Vicentina) plus 1 new Organization entity (Washington State University, if item 10 is trusted) become creatable under the same evidence-grounding discipline used this mission.
8. **~98 of the 114 (86%)** can safely wait -- 12 recalls, 8 retail listings, ~18 lower-priority patents, ~19 duplicate/reprint items, plus remaining generic market-context items, none of which are time-sensitive or block a specific graph unlock.
