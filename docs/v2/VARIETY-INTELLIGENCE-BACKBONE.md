# Variety Intelligence Backbone V1

**Mission:** Global Variety Intelligence Backbone V1 (2026-08-21, branch `feature/variety-intelligence-backbone`). Builds the data/service backbone connecting Genetics -> Variety Identity -> Rights/Ownership -> Geography -> Commercial Presence -> Market Observations -> Competitive Signal. Not a UI (Cursor owns Variety UI); not a cultivar-catalog expansion.

---

## 1. Existing variety architecture (audit)

Full detail from the mission's own architectural audit (Explore agent, verified against real records):

**Works today:**
- `entity_type: "variety"` shares the generic Entity envelope (`id`, `name`, `aliases[]`, `berry_ids[]`, `evidence_ids[]`, `fact_ids[]`, `relationship_ids[]`, free-form `attributes`). No variety-specific schema branch.
- Real Variety records (58) populate `attributes.breeder` (free text), sometimes `attributes.geography_note` (free text), and per-claim `attributes.traits[]` (`{trait, value, provenance, evidence_ids, conditions, asserted_by}` -- genuinely evidence-linked per entry, see Part 6).
- Story Thread and Signal generically support variety as a first-class primary-subject type (not bolted on) -- `_cross_subject_event_edge()` in `app/services/story_threads.py` was purpose-built for the company-vs-variety headline mismatch (PR #51).
- `app/services/berries/landscape.py`'s `landscape_variety_rollup()` is the closest existing "variety landscape" -- breeder, breeding program, trait count/labels, region (derived), patent-number presence, evidence count, signals, assessments.

**Genuine gaps found, not inferred from planning docs:**
1. **Variety is never a relationship *subject*** -- 0 of 223 (pre-mission) live relationships have a variety `subject_id`. Every variety-outbound edge (variety->trait, variety->geography) is absent from the relationship graph entirely.
2. **No BREEDER/OWNER/RIGHTS-HOLDER/LICENSEE/MARKETER distinction** -- real authors were substituting `sells` for a missing `markets` predicate, with an explicit disclaimer in `notes` (`rel-berryworld-sells-eureka.json`). `owns` was declared for `variety` as an object type in the domain-pack's own documentation but never schema-enforced.
3. **Patent/PVR<->Variety linkage is fuzzy-matched at render time, not stored** -- `app/services/berries/variety.py`'s `variety_patent_link()` explicitly documents itself as a "best-effort" workaround pending real `protects`-relationship data. One real record (`variety-drisblueseventeen.json`) already carries a structured `attributes.rights_id` pointer -- proving the pattern works, just not applied elsewhere.
4. **No dedicated PVR entity type** -- non-US rights (e.g. Canadian PBR) are stored as `entity_type: "patent"` with jurisdiction-specific `attributes` (`kind: "plant breeders' rights"`). This convention is fine and is reused, not replaced (Part 5).
5. **Trait-evidence linkage is a JSON convention, not schema-enforced** -- `attributes.traits[].evidence_ids` can be empty and the record still validates. No `exhibits_claimed_trait` relationship exists in live data (declared, zero use).
6. **Geography on a Variety is entirely derived**, never stored, via `entity_regions()` walking Evidence `geography_ids` + `entity_ids` intersection.
7. **Retail/market observation has no dedicated shape** -- one fictional seed Evidence record (`ev-sample-retail-placement`, `source_type: "field_observation"`) is the only precedent, unenforced by schema.

None of these are new information for the platform's own documentation -- (1)/(2) match TD-ENT-001's existing predicate-mismatch finding exactly, now updated with real substitution examples; the rest are new findings from this mission.

---

## 2. Variety identity contract

**No schema change was needed.** The existing `name` + `aliases[]` fields are sufficient and already correctly used on the one real record that needed the full contract (`variety-drisblueseventeen.json`: `name: "DrisBlueSeventeen"`, `aliases: ["Carlotta", "Drisblueseventeen"]` -- canonical cultivar name as `name`, the real commercial/trade name as an alias). What was missing was **consistent use**, not capability -- most real Variety records leave `aliases` empty even when a real commercial name exists (found and fixed for two varieties this mission: `variety-zara` and `variety-victoria`, both added with `name` = commercial name since no separate breeder denomination/PVR code was found for either -- see Part 13 for why that distinction matters).

**The contract** (documented here as the durable reference; not a new schema field):

| Concept | Where it lives | Example |
|---|---|---|
| Canonical/breeder denomination | `name` (or an `aliases[]` entry if a different name is more commonly used) | `DrisBlueSeventeen` |
| Protected/PVR denomination | Same as canonical when a PVR grant uses it directly; `attributes.denomination` when explicitly distinct | `DrisBlueSeventeen` (PBR certificate 7097) |
| Commercial/marketed (trade) name | `aliases[]`, and `attributes.trade_name` / `attributes.commercial_name` when the record wants to foreground it | `Carlotta`, `Zara`, `Victoria` |
| Breeder code | `aliases[]` (this mission proved it via real CPVO breeder-code matches: `FC11-164`, `BB05-251MI-14`, `Plablue 1542` all matched real varieties by breeder-code alias, not canonical name) | `FC11-164` -> Fall Creek's "Last Call"-adjacent trial code |
| PVR-office denomination if it differs from all of the above | `attributes.denomination` | -- |

**Deterministic matching, not fuzzy matching**: `app/services/patent_monitor/entity_link.py`'s `suggest_entity_links()`/`matched_entity_ids()` -- already generic, not patent-specific in its matching logic -- is the real identity-resolution mechanism this mission reused directly for CPVO (Part 5) rather than writing new matching code. It indexes every entity's `name` + every `aliases[]` entry, folds case/punctuation/legal-suffix noise, and requires either an exact fold match or a contiguous multi-token alias match -- never a similarity score. This is the concrete "do not create duplicate Variety entities simply because marketing names differ" mechanism the mission asked for: it already existed, generalized correctly to variety identity once exercised against real CPVO denominations.

**Real duplicate-prevention proof**: querying CPVO for all 58 tracked varieties' names+aliases (132 total queries) produced **zero new duplicate Variety entities** -- every genuine match (28 of them) resolved to an *existing* variety id via alias/name matching, never created a second "DrisBlueSeventeen (CPVO)" record alongside the real one.

---

## 3. Ownership / rights model

**The existing relationship architecture can represent BREEDER, OWNER/RIGHTS HOLDER, LICENSEE, and MARKETER separately -- proven with real data, not asserted.**

| Role | Predicate | Real proof this mission |
|---|---|---|
| Breeder | `develops` (already worked) | `company-driscolls develops variety-drisblueseventeen` (pre-existing) |
| Owner / rights holder | `owns` | **New real relationship added**: `rel-driscolls-owns-drisblueseventeen.json` -- same company, same variety, same underlying evidence (`ev-cfia-pbr-drisblueseventeen`, the PBR grant) as the pre-existing `develops` edge, but a legally distinct fact (a PBR grant establishes rights ownership, not breeding origin). Both edges coexist on the same variety without collapsing to one relationship. |
| Marketer | `markets` | **Schema change**: added `markets` to `relationship.schema.json`'s enum (it was already declared in the domain-pack taxonomy with real, disclaimed substitute-predicate usage -- `rel-berryworld-sells-eureka.json`'s own `notes` said *"Substituted predicate: 'sells' stands in for 'markets', which the schema does not provide"*). That record was corrected to the real predicate; two new real marketer relationships were added (`rel-driscolls-markets-zara`, `rel-driscolls-markets-victoria`). |
| Licensee | `licenses` (already worked, already used for a brand object; usable for variety identically) | Not exercised with new data this mission -- the existing mechanism needs no change. |

**Why only `markets` was added, not all 6 declared-but-unenforced predicates** (`exhibits_claimed_trait`, `protects`, `offers`, `administers_license_for`, `subsidiary_of`): per the mission's own instruction ("only propose a schema addition if real data cannot be represented honestly"), `markets` was the one predicate with a real, already-existing, disclaimed substitution in live data -- direct proof the gap was actively costing honesty, not a hypothetical. The other five remain declared-only, still tracked as debt (TD-ENT-001, updated this mission), not schema-added speculatively.

**Real ownership/rights nuance found**: a company can legitimately hold more than one role on the same variety (Driscoll's is both breeder and rights holder for DrisBlueSeventeen) -- `app/services/variety_footprint.py`'s `variety_footprint()` (Part 10) keeps every role in its own bucket for exactly this reason; collapsing to "owner" would have silently discarded the breeder fact or vice versa.

---

## 4. Global variety-rights registry audit

Real, live-tested access research, not documentation review. Every jurisdiction below was actually queried or its access path actually attempted during this mission.

| Jurisdiction | Public accessibility | API? | Notes |
|---|---|---|---|
| **US -- USPTO plant patents** | Public | Yes (already integrated, Patent Monitor v2) | No new work needed. |
| **International -- UPOV PLUTO** | Public search UI | Requires a WIPO user account for full access -- **not anonymously public** | Not integrated. |
| **EU -- CPVO "Variety Finder"** (the 70-country aggregator) | Public web UI | Explicitly registration-gated per CPVO's own documentation ("must register for an online account to obtain a username and password") | Not integrated -- this is the *aggregator*, distinct from the register below. |
| **EU -- CPVO public register** (`online.plantvarieties.eu/publicSearch`) | **Public, no login** | **Yes -- real, unauthenticated JSON API found and used live**: `GET https://online.plantvarieties.eu/api/publicSearch/v3/publicSearch?denomination=X&denominationSearchType=contains`. Live-verified 2026-08-21 (real hits for "Sonata"/strawberry, zero false hits for "Malaika"/raspberry -- a genuine negative, not a broken query). | **Integrated this mission** (Part 5). |
| **UK -- Plant Variety Rights Office (APHA)** | No unified public database found | No | Records exist only via monthly "Seeds Gazette" PDF publications and UPOV PRISMA (application-side only). Weakest of the researched options. |
| **Australia -- IP Australia PBR search** | Public web UI (`ipsearch.ipaustralia.gov.au`) | **No API discovered** in live testing -- the search UI is a Nuxt.js SPA; observed network traffic during a real search interaction showed only static asset loads, no data endpoint. IP Australia does publish annual bulk open-data products (IPGOD, IP RAPID) as an alternative, but those are not real-time search. | Not integrated. |
| Mexico (SNICS), Peru, Chile, Spain, Morocco, South Africa | Not individually live-tested this mission (time-bounded per the mission's own "do not build every adapter" instruction) | Unknown | Real candidates for a future registry-depth mission once one is prioritized; Spain-registered varieties are already partially reachable via the CPVO register itself (EU-wide). |

**Searchable fields (CPVO public register, confirmed live)**: `denomination` (equals/contains), `breedersReference` (contains), `species` (autocomplete UI field; the underlying `species`/`specieId` query params were tested and do **not** filter server-side -- a real, documented limitation, see Part 13), `applicationNumber`. Each result row: `denomination`, `speciesName`, `applicationNumber`, `grantNumber`, `applicationDate`, `grantingDate`, `expirationDate`, `applicationStatus`, `titleStatus`, `applicants[]`, `examOfficeCountry`, `examOfficeName`, `breedersReference`.

**Update cadence**: unknown/unpublished; treated as `event_driven` in this project's Source registry, matching the existing `source-uspto-plant-patents` convention (a registry is queried on demand, not polled on a fixed cadence).

**Legal/access restrictions**: none found for the public register endpoint itself (no terms-of-service gate encountered; standard "please don't hammer us" courtesy applies, honored via query-per-known-variety-name rather than a bulk crawl). The aggregator (Variety Finder) and UPOV PLUTO are explicitly account-gated and were not accessed.

**Ability to link breeder/applicant/denomination/filing status**: yes, directly -- every field above is present on every real result row.

---

## 5. Registry integration added: CPVO public register V1

`app/services/cpvo_registry.py` + `scripts/monitor_cpvo_registry.py`, architecturally parallel to Patent Monitor v2 (writes only untrusted `inbox/evidence/` drafts, never trusted data/Facts/Relationships) but a single lean module rather than a full sub-package, since CPVO's matching need (query-by-known-variety-name) is simpler than USPTO's (broad keyword search + assignee corroboration). Reuses `app/services/patent_monitor/entity_link.py`'s `suggest_entity_links()`/`matched_entity_ids()` directly -- proof that mechanism was already generic, not patent-specific.

**Real run results** (132 real queries -- every one of the 58 tracked varieties' names + aliases, live against `online.plantvarieties.eu`):

- **28 real, berry-relevant CPVO filings found**, all correctly species-filtered (strawberry/blueberry/raspberry -- zero blackberry hits, an honest finding, not a bug -- see Part 12) and correctly matched to already-known Variety entities.
- Notable real matches: `Shani`/`Rafiki`/`Sarafina` (raspberry) all assigned to **"Allberry B.V."** -- direct, real corroboration of the pre-existing `TD-ENT-002` identity-ambiguity finding (Allberry B.V. vs. Advanced Berry Breeding B.V.); `FC11-164`, `FC13-113`, `FC15-173` (Fall Creek's own internal breeding codes) all matched real Fall Creek blueberry varieties via breeder-code aliasing; `Plablue 1542`/`Plablue 1545` matched Costa/Mountain Blue Orchards varieties by breeder code.
- **Idempotency proven**: a second real run against the same 132 queries found the same 28 filings, all correctly recognized as duplicates (0 new drafts, 0 auto-trust).
- All drafts carry `source_authority: "high"`, `verification_state: "unverified"`, and an explicit `does_not_prove` list (commercialization, acreage, market success, that the applicant is the breeder, exclusive territory) -- the same discipline Patent Monitor v2 already established, reused rather than reinvented.

Real, honest limitations found and registered (Part 14): the `species`/`specieId` query parameters do not filter server-side (denomination-based query + client-side species filtering was the only working approach); no stable per-record deep-link/permalink was confirmed (the `source_url` recorded is the equivalent search query, documented as such, not a guessed permalink).

---

## 6. Trait model

**Audited, found structurally sound, left unchanged.** Traits are already a generic entity type (13 real trait entities) with per-claim evidence linkage inside `attributes.traits[]` (`{trait, value, provenance, evidence_ids, conditions, asserted_by}`), and `provenance` already distinguishes `"owner_or_marketer_claim"` from `"regulatory_or_registry_record"`/independent measurement -- exactly the "marketing language must not silently become trusted Fact" requirement. This is not a hardcoded Variety column (traits are named entities; a new trait requires only a new Trait entity, not a schema change).

**Real gap, not fixed this mission (scoped out, registered as debt)**: `attributes.traits[].evidence_ids` is a JSON convention, not schema-enforced -- a trait claim with no evidence would still validate. `exhibits_claimed_trait` (declared, `live_count: 0`) would make Variety->Trait a first-class relationship instead of an embedded array entry, but no real data this mission touched needed it, so it was not added speculatively (same discipline as Part 3's predicate decision). See TD-018.

---

## 7. Commercial Observation model

**Small additive schema, not a new entity type or a parallel trust system.** `evidence.schema.json` gained one optional object, `commercial_observation` (retailer/variety/marketer entity ids, brand, origin geography, price, currency, pack size, promotion, claims, observed_at, channel, observer_method, image_reference), present only on `source_type: "field_observation"` records -- mirroring the existing `patent_filing` object's precedent exactly (an optional, additive, generically-rendered structured-facts object). Confidence/verification/review state use the **existing** generic Evidence fields (`source_authority`, `verification_state`, `does_not_prove`, `review_state`) -- no parallel trust field was created.

An observation never auto-becomes a Fact. `variety_entity_id` and `retailer_entity_id` are both nullable and explicitly meant to stay null when a listing is genuinely ambiguous ("do not fabricate variety identity when packaging/listing is ambiguous," honored directly -- see Part 9).

---

## 8. UK retail research

Real, individually-verified research (not automated retailer scraping -- explicitly out of scope per the mission). Findings:

- **Variety-name exposure is the exception, not the rule.** Of the retailers checked (Tesco, Sainsbury's, Waitrose, M&S, Morrisons, Asda), the overwhelming majority of generic own-label listings ("Tesco Blueberries", "Sainsbury's Blackberries") name **no cultivar at all** -- only brand + retailer + pack size + (sometimes) country of origin.
- **Premium/named lines are where variety names actually appear.** Two real, independently-confirmed cases: **Driscoll's "Zara"** strawberries (sold at Tesco as "British Zara Strawberries" and via Waitrose's "No.1" premium range; named the Guardian's "best overall supermarket strawberry" in a 10-retailer taste test) and **Driscoll's "Victoria"** blackberries (HortWeek "Best New Variety" award winner, grown in Kent by Berry Gardens, a real Driscoll's UK growing partner; sold at Tesco as "Victoria Blackberries").
- **Origin-country disclosure is common** even when variety is not: Sainsbury's blueberry lines list Argentina/Chile/Morocco/Peru/Poland/Spain; Morrisons blueberries list Morocco; M&S blueberries list Surrey, UK.
- **Public accessibility / automation feasibility**: direct retailer-site fetching was not attempted (access-control discipline). **Open Food Facts** (`world.openfoodfacts.org`), a real, openly-licensed, crowd-sourced product database that mirrors real UK retailer packaging/listing data, was used instead -- its individual-product API (`/api/v2/product/{barcode}.json`) is public, stable, and worked reliably; its *search* endpoint returned HTTP 503 throughout this mission's research window (a real, live service issue at research time, not a code bug -- confirmed by testing both the v2 and legacy search endpoints identically failing while individual-product lookups succeeded). Product barcodes were found via targeted web search (`site:openfoodfacts.org ...`), not bulk crawling.
- **Stability**: individual-product lookups are stable; a future automated pilot should not depend on the search endpoint being available and should instead maintain a curated barcode list, or retry with backoff.

---

## 9. Real observation pilot

**18 real observations** (within the mission's 10-30 target), spanning all 4 berries and 6 real UK retailers (Tesco, Sainsbury's, Waitrose, M&S, Morrisons, Asda), created as untrusted `inbox/evidence/` drafts (`source_type: "field_observation"`, `intake_type: "commercial_observation"`, `status: "draft"`, `review_state: "in_review"` -- no auto-trust, human publication review required like every other draft this platform produces).

| # | Retailer | Berry | Variety identified? | Origin (as stated) |
|---|---|---|---|---|
| 1 | Tesco | Strawberry | **Zara** | UK |
| 2-4 | Sainsbury's / Tesco / Sainsbury's | Strawberry | none (own-label, no cultivar named) | UK |
| 5-6 | Waitrose x2 | Strawberry | none | France / South Africa |
| 7 | Tesco | Blueberry | none | Slovakia |
| 8 | Morrisons | Blueberry | none | Morocco |
| 9-10 | M&S x2 | Blueberry | none | UK (Surrey) / unstated |
| 11-13 | Tesco / Sainsbury's / Waitrose | Raspberry | none | UK (all 3) |
| 14 | Waitrose | Blackberry | none | unstated (listed origin field inconsistent -- see Part 13) |
| 15-16 | Sainsbury's / Tesco | Blackberry | none | UK |
| 17 | Tesco | Blackberry | **Victoria** | UK |
| 18 | Asda | Blackberry | none | UK |

**16 of 18 correctly recorded `variety_entity_id: null`** -- the listing genuinely did not disclose a cultivar, and none was guessed. This is the honest, expected shape given Part 8's finding, not a shortfall against a 30-observation target padded with fabricated identity.

---

## 10. Variety footprint service

`app/services/variety_footprint.py`, pure functions over caller-supplied record lists (no persistence, per the mission's own "do not persist derived conclusions" instruction -- a caller re-derives on every call). `variety_footprint(variety_id, ...)` returns: name/aliases/berries, roles (breeder/owner_rights_holder/licensee/marketer/grower/distributor, each a **separate, never-merged** list), rights filings (published vs. draft-pending-review, kept distinct), countries observed, retailers observed, first/latest observed dates, the supporting commercial-observation list (each tagged `trust: "published"` or `"draft (pending review)"`), related Story Threads, related Signals.

**Real proof, run against the live dataset** (not a fixture):

```
variety_footprint("variety-drisblueseventeen"):
  roles.breeder = ["company-driscolls"]
  roles.owner_rights_holder = ["company-driscolls"]     # both real, both separately evidenced
  rights_filings.published = [ev-cfia-pbr-drisblueseventeen]

variety_footprint("variety-zara"):
  roles.marketer = ["company-driscolls"]
  countries_observed = ["geography-united-kingdom"]
  retailers_observed = ["retailer-tesco"]
  commercial_observations = [{trust: "draft (pending review)", ...}]
```

This is the mission's own required end-to-end proof: **one real Variety can be followed from breeder -> rights -> geography -> commercial observation**, using only real, already-published or newly-added-this-mission data -- see Direct Answer 1.

---

## 11. Competitive query proof

All run against the real, live dataset (published Evidence + `inbox/evidence/` drafts + real entities/relationships), not synthetic fixtures -- fixtures exist only in `tests/test_variety_footprint.py` for fast, offline regression coverage.

| Question | Function | Real result |
|---|---|---|
| Which varieties have been observed in UK commercial channels? | `varieties_observed_in_market(country_geo_id="geography-united-kingdom")` | **Victoria, Zara** (the 2 variety-identified observations out of 18) |
| Which raspberry varieties have been observed in the UK? | same, `berry_id="berry-raspberry"` | **none** -- honest, matches Part 9 (no raspberry listing named a cultivar) |
| Which varieties have both IP activity and a commercial observation? | `varieties_with_ip_activity_and_commercial_observation()` | **none yet** -- an honest, real "not yet overlapping" finding: the 28 CPVO-matched varieties and the 2 variety-identified UK observations are currently disjoint sets. Registered, not hidden (Part 16). |
| Which companies have competing varieties in blueberry? | `competing_varieties_in_berry_market(berry_id="berry-blueberry")` | **Real, multi-company result**: Costa Group (Eterna, Arana), Driscoll's (DrisBlueSeventeen, DrisBlueTwentyOne, DrisBlueTwentyThree), Fall Creek (11 varieties), Mountain Blue Orchards (Eureka, Twilight, Opi, Eureka Sunrise), Berry Blue LLC (Keepsake, Medallion), BerryWorld (Eureka) |
| Which companies have competing varieties in blackberry? | same, `berry_id="berry-blackberry"` | **Driscoll's (Victoria)** -- correctly thin, matches Part 12 |

No question above returned a fabricated or padded answer; "none" is reported as a real result where that is what the data supports.

---

## 12. Cross-berry proof

The identity contract, ownership model, registry integration, trait model, and commercial-observation model are all berry-agnostic by construction -- no berry-specific schema, adapter, or matching logic was written anywhere in this mission. Real evidence per berry:

- **Blueberry**: deepest -- 28 CPVO matches include ~20 blueberry filings; rich competitive-query results (6 companies, 20+ varieties).
- **Strawberry**: real CPVO matches (Sonata-class, Melissa, Flavia, Dina); real UK observation with identified variety (Zara).
- **Raspberry**: real CPVO matches (Bella, Shani, Rafiki, Sarafina -- surfacing the Allberry B.V. identity question again); UK observations exist but none named a cultivar (honest gap, not fabricated).
- **Blackberry**: genuinely shallow, **and reported as such rather than padded** -- 0 CPVO matches (real, confirmed: none of the tracked blackberry-adjacent query names returned a `Rubus subg. Rubus`/`Rubus occidentalis` hit), 1 variety entity with a real UK observation (Victoria) and a real marketer relationship, 0 rights filings. Per the mission's own allowance ("Blackberry may remain shallow"), this is not a gap this mission tried to close artificially.

---

## 13. Identity / dedup findings

Real, observed examples (not hypothetical):

- **Same marketed name across different crops entirely**: CPVO's own register shows the denomination **"Sonata"** registered three separate times, for three unrelated species -- *Cynara cardunculus* (cardoon), *Fragaria x ananassa* (strawberry, the real match), and *Hordeum vulgare* (barley). Species filtering (Part 5) is not optional decoration -- without it, a denomination-only match would misattribute a barley variety's applicant to a strawberry Variety entity. Similarly, **"Malaika"** (the tracked raspberry) returned only a *Dracaena* (houseplant) hit at CPVO -- a real, correct negative, proving the raspberry Malaika genuinely has no EU CPVO filing rather than the query being broken.
- **Breeder code vs. denomination, resolved correctly**: `FC11-164`, `FC13-113`, `FC15-173`, `BB05-251MI-14`, `Plablue 1542/1545` are all real internal breeding/trial codes, not commercial denominations -- each correctly resolved to its owning Variety entity via the existing alias-matching mechanism (Part 2), because those codes were already recorded as `aliases[]` on the real entities from earlier missions' data entry.
- **Rights holder confirmed distinct from marketer in the same company**: Driscoll's is simultaneously breeder+owner of DrisBlueSeventeen (Part 3) and *only* marketer (no breeder/owner relationship recorded) of Zara and Victoria -- the same company, three different real role combinations, none collapsed.
- **Same denomination, two distinct real filings**: "Cargo" and "Blue Ribbon" (both Fall Creek blueberry varieties) each returned **two** separate CPVO register rows with different `applicationStatus`/`titleStatus` (one `approved`, one `noDecision`) and different application numbers -- two genuinely distinct real filings for the same denomination (e.g. an amendment or a second jurisdictional filing), correctly kept as two separate draft Evidence records by `canonical_filing_id()`'s office+application-number keying, not merged and not treated as a duplicate.
- **Breeding-program entity vs. its parent company, same varieties**: `competing_varieties_in_berry_market()`'s real blueberry output lists "Fall Creek Blueberry Breeding Program" and "Fall Creek Farm & Nursery, Inc." as two separate rows with identical variety lists -- both entities carry real, independent `develops` relationships to the same varieties. This is correct modeling (a breeding program and its parent company are legitimately distinct entities), not a duplicate, but is worth a reviewer's attention if it ever surfaces in a future UI without that context.
- **Rights holder != breeder, general case confirmed real**: `rel-fall-creek-trials-fc11-164-chile.json` (pre-existing) already documents a case where the trialing/growing party is explicitly not the breeder -- consistent with this mission's ownership-model findings, not a new discovery, cited here as corroboration.
- **A retailer-listing's stated origin can be internally inconsistent**: one real Open Food Facts record (Waitrose British Blackberries) lists `countries: "Singapore"` alongside a product name beginning "British" -- almost certainly a data-entry/geolocation artifact in the third-party database, not a real claim that the product is from Singapore. Recorded honestly in the observation (`origin_geography_id: null`, since the origin field was not trustworthy enough to resolve) rather than silently "corrected" to an assumed value.

---

## 14. Technical debt

New entries added to `docs/v2/TECHNICAL-DEBT-REGISTER.md` (continuing its existing ID sequence, not colliding with Cursor's TD-001..017/TD-THREAD-002/TD-ACQ-002..004/TD-ENT-001..003 etc.): TD-018 (trait-evidence linkage not schema-enforced), TD-019 (CPVO `species`/`specieId` query params don't filter server-side), TD-020 (no stable CPVO per-record permalink confirmed), TD-021 (Open Food Facts search endpoint instability), TD-022 (UK retail variety-name exposure is rare -- a real, structural limitation on future UK observation volume, not a bug), TD-023 (registry-matched varieties and observed varieties are currently disjoint sets), TD-ENT-004 (Fall Creek breeding-program vs. parent-company duplicate-looking-but-correct rows). TD-ENT-001 and TD-ENT-002 were updated in place with this mission's real corroborating evidence rather than duplicated.

---

## 15. Coverage Matrix

Updated `docs/v2/INTELLIGENCE-COVERAGE-MATRIX.md` with real, measured maturity for Variety Knowledge, PVR/Registry, and Retail/Commercial Observations -- **none marked OPERATIONAL**, per the mission's own instruction not to promote a small pilot. See that file for the full entries; summary: Variety Knowledge PARTIAL (deep for blueberry, thin for blackberry, identity contract now proven), PVR/Registry PARTIAL (was PILOT; real EU coverage now exists across 3 of 4 berries, still single-jurisdiction), Retail/Commercial Observations PILOT (18 real observations, 1 market, 2 of 4 berries with an identified-variety case).

---

## 16. Relation to the 0/8 Commercial/Market recall benchmark

The prior mission's benchmark found 0% recall on 8 Commercial/Market events (export percentages, production forecasts, retailer pricing/promotions -- e.g. "Peru blueberry production +25%", "Chilean exports fall 13%", "Sainsbury's GBP1 strawberry promotion"). **This backbone directly helps with exactly one of those 8** (BM-M-01, the Sainsbury's promotion) **in kind, not in fact** -- the Commercial Observation model built this mission is the right *shape* of record for a real future Sainsbury's-promotion observation, and the UK retail research proves the pilot mechanism can capture retailer+price+promotion+pack-size data when a listing states it. None of the 18 real observations gathered this mission happens to be that specific event (a live promotional price at one point in time), but the model is now ready to capture the next one.

**This backbone does NOT and cannot, by itself, solve**: aggregate export/production statistics (BM-M-02/M-03/M-04/M-05/M-06 -- these are trade-data-service facts, e.g. Tendata/USDA FAS aggregate figures, not observable at the level of one retail listing), supply-chain/acquisition events (Workstream A/B territory, not C), or trade-flow shifts (Customs/Trade, Workstream G, explicitly not started). The Commercial Observation model is a **listing-level** evidence class; it was never going to close aggregate-statistic recall, and this report does not claim it does.

**What remains**: Customs/Trade data ingestion (Workstream G) for the aggregate-statistic half of Commercial/Market recall; broader mainstream/trade-press acquisition (already partially addressed by the prior mission) for the remaining announcement-style events; and, if UK retail observation continues, either a stable Open Food Facts search integration or a small curated-barcode-list automation to move past this mission's manual, individually-researched pilot.

---

## 17. Cursor UI contract (Variety Intelligence)

For a future Variety Competition UI. **Not designed here** -- this is the backend contract only.

**Query services available** (all pure, read-only, no persistence):
- `app.services.variety_footprint.variety_footprint(variety_id, *, entities, relationships, published_evidence, inbox_drafts=None, story_threads=None, signals=None) -> dict` -- one variety's full footprint.
- `app.services.variety_footprint.varieties_observed_in_market(*, country_geo_id, berry_id=None, entities, published_evidence, inbox_drafts=None) -> list[dict]`
- `app.services.variety_footprint.varieties_with_ip_activity_and_commercial_observation(*, entities, published_evidence, inbox_drafts=None) -> list[dict]`
- `app.services.variety_footprint.competing_varieties_in_berry_market(*, berry_id, country_geo_id=None, entities, relationships, published_evidence, inbox_drafts=None) -> list[dict]`
- Pre-existing, still the right tool for non-footprint questions: `app.services.berries.variety.variety_trait_profile()`/`variety_patent_link()`, `app.services.berries.landscape.landscape_variety_rollup()`, `app.queries.entity_intelligence.EntityIntelligenceQueryService` (generic Facts/Signals/Assessments/Recommendations by entity id), `app.services.berries.geography.entity_regions()`.

**Record shapes**: `variety_footprint()`'s return dict (Part 10) is the primary shape to build a Variety Competition page against. `commercial_observation` is an optional object on Evidence (schema: `schemas/evidence.schema.json`, `$comment`-documented) -- always check `trust` ("published" vs. "draft (pending review)") before rendering; never present a draft observation with the same visual weight as trusted Evidence, matching this platform's existing publication-review discipline everywhere else.

**Derived fields**: `countries_observed`, `retailers_observed`, `first_observed`/`latest_observed` are all computed at call time from the current record set -- there is no cached/stored version to go stale, and none should be added without a real performance justification (none was found; the dataset is small).

**Trust/review semantics**: identical to every other Evidence-shaped record in this platform. A commercial observation is never a Fact. `does_not_prove` is populated on every observation draft and should be surfaced, not hidden, in any future UI (matching how `patent_filing`'s `does_not_prove` is already expected to render generically per `app/services/intelligence_feed.py`'s existing convention).

**Filters a UI will likely want**: berry, country/market (`geography_ids` on observations), retailer (`commercial_observation.retailer_entity_id`), and "has IP activity" / "has commercial observation" as independent toggles (Part 11's overlap query already answers "both" directly).

**Known limitations to design around, not silently around**:
- Variety-identified observations are currently rare (2 of 18) -- a UI should handle "no named variety on this listing" as a first-class, common state, not an edge case.
- No cross-source dedup exists yet between a CPVO-matched variety and a commercially-observed one beyond shared Variety entity ids -- if a future mission adds more registries or more retail markets, watch for the same denomination resolving to different entities across sources (Part 13's "Sonata" case is the concrete cautionary example).
- Blackberry is real but shallow across every dimension in this backbone -- a UI should not present blackberry variety-competition views with the same density expectation as blueberry.
