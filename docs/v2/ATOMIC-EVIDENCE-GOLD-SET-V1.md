# Atomic Evidence Gold Set V1

A benchmark answering one question: **given a rich, already-trusted source
publication, what atomic competitive-intelligence claims should a good
extractor recover — and what should it correctly refuse to extract?**

This is a benchmark, not an extraction pipeline. It creates no Fact,
Relationship, trusted Atomic Evidence, or Assessment; it publishes nothing and
rejects nothing; it changes no Source, schema, or trust rule. Cursor owns
Publication Review UX V2 / Source Fidelity Acceptance; Codex owns Atomic
Extraction Qualification / Model Readiness. This document is deliberately
scoped so both can consume it without either implementation overlapping the
other.

## 1. Gold-set composition and selection method

18 real source items, all identified by reading actual repository files, none
invented:

- **16 scored items** drawn exclusively from `data/evidence/*.json` records
  with `status: "published"`. Every scored source ID below was opened and
  read in full before being included.
- **1 structural spoken-media item** (Section 10) that is trusted but cannot
  carry a scored timestamped proposition, because no real transcript text
  exists for it.
- **1 pending flagship item** (Section 1a) explicitly kept **outside** the
  scored set per this mission's own rule, because its source record is a
  draft (`status: "draft"`, `review_state: "in_review"`), not trusted.

Selection was not "the first 18 records found." A background survey read all
1,266 files under `data/evidence/` and classified every one by richness
(distinct extractable claims), `source_type`, structured-object presence
(`patent_filing`, `cpvo_filing`, `commercial_observation`, `article.paragraphs`,
`transcript`), and language. That survey is the basis for every honest
limitation reported in Sections 2 and 5 below — they are measured facts about
the corpus, not assumptions.

### 1a. Mandatory flagship case (pending source, outside the scored set)

**`ev-media-069f07925d20b2d93743`** — "Planasa varieties arise the interest of
major European retailers" (Planasa Newsroom, published 2024-03-26). Added at
explicit user direction as the canonical atomicity-vs-summarization test.
Verified word-for-word against the record's own real, already-acquired
`article.paragraphs` body text (not fabricated for this document):

| Variety | Berry | Attributed observations (exact source wording) |
|---|---|---|
| RedSayra | strawberry | "praised for the precocity and firmness it has shown to date, as well as its outstanding flavour" |
| Red Samantha | strawberry | "the high calibre and excellent flavour of Red Samantha" |
| Blue Maldiva | blueberry | "the size, texture, and bloom of Blue Maldiva" |
| Blue Madeira | blueberry | "the flavour of Blue Madeira" |
| Blue Manila | blueberry | "the flavour of ... Blue Manila" |
| Pink Hudson | raspberry | "its flavour, shelf life, bright colour, and versatility, as it can be planted for winter production or for double cropping" |
| Black Sultana | blackberry | "the remarkable quality of the fruit throughout its production cycle" |

**Mandatory attribution constraint**: paragraphs 0–1 establish these are
impressions from a visiting delegation (Tesco, Marks & Spencer, ASDA, Waitrose,
Bakker, Berrie's Pride) reported through Planasa's own newsroom — not
independent sensory testing, not a registry finding, not agronomic
measurement. The record's own (untrusted, AI-generated) enrichment caveat
independently reaches the same conclusion: "attributed to Planasa's commercial
claims and retailer feedback rather than independent verification." A correct
extraction preserves that chain (retailer impression, reported by the
breeder) on every one of the 7 claims; a `classification: "fact"` Fact-style
assertion for any of them would be wrong — these are `classification: "claim"`
at best, sourced to a single non-independent party.

**Minimum atomic decomposition**: 7 claims (one per variety-observation
cluster as it appears in one sentence of source text). A model may
legitimately split further (e.g. Pink Hudson's 4 attributes into 4 claims)
without penalty, but must not go below 7 or collapse below the
variety boundary — see Failure Type 1 and 2 in Section 12.

**Because this source is pending, not trusted, it is never scored as ground
truth by this benchmark.** It is cited by name in the Section 11 rubric as the
canonical worked example for the Atomicity dimension, and it should be
re-added as a real scored case the moment it clears human publication review
(a decision this mission explicitly does not make).

## 2. Corpus reality and richness bias (read before Section 3)

The trusted corpus does not evenly support "rich, multi-claim, all 4 berries."
Measured directly, not assumed:

- Every genuinely rich company-newsroom/trade-press record with 3+
  independent extractable claims is **blueberry**, with two exceptions
  (`ev-driscolls-cbc-appeal-2025`, strawberry; `ev-fruitnet-driscolls-zara-best-strawberry`,
  strawberry). There is no rich raspberry or blackberry newsroom/trade-press
  trusted record at all — the two caneberry items in this gold set
  (`ev-20260806173539-86c2-...`, `ev-hortweek-driscolls-victoria-award`) are
  included specifically *because* they are the best real caneberry material
  available, not because they are equally rich.
- **Zero** trusted records in any language other than English exist. A
  full-corpus scan for Spanish/French/Italian vocabulary found only English
  articles that happen to contain Spanish/Portuguese proper nouns
  (Proarándanos, El Niño). Mission Section 1's "English/Spanish/French where
  available" cannot be honestly satisfied for the scored set — there is
  nothing available. See TD-079.
- **Zero** trusted records carry the structured `patent_filing` or
  `cpvo_filing` object; all 30+20 records with that object populated are
  pending drafts in `inbox/evidence/`. The 22 `patent_record` and 8
  `plant_breeders_rights_record` trusted files used in Section 9 carry the
  same bibliographic facts only as prose inside `summary`/`why_it_matters`.
  See TD-080.
- **Zero** trusted records have `transcript.status: "available"` with real
  `transcript.text`, and zero have a populated `article.paragraphs` array.
  Every trusted record's only persisted text is `summary` (≈20–100 words) and
  `why_it_matters` (≈15–60 words) — see Section 5.

This is reported as fact, not framed as a defect to fix in this mission — see
the four new Technical Debt entries in Section 15.

## 3. Annotation contract per source

Every scored expected-claim entry in Sections 6–10 below is authored with
these fields, using only vocabulary that already exists in
`schemas/evidence.schema.json`, `schemas/fact.schema.json`, and
`schemas/relationship.schema.json` (no new schema, per Section 6):

| Field | Meaning | Existing vocabulary reused |
|---|---|---|
| `normalized_statement` | The atomic claim in plain text | mirrors `atomic-ci-v1`'s `normalized_statement` contract |
| `exact_excerpt` | Verbatim supporting text from the source's `summary`/`why_it_matters`/prose | mirrors `transcript_excerpt` |
| `source_location` | Which persisted field the excerpt was pulled from (`summary`, `why_it_matters`, or a numbered `article.paragraphs[i]` where one exists) | see Section 5 — most sources have no `article` body, so location is field-level, not paragraph-level |
| `subject_entity` / `object_entity` | Resolved `entity_ids` values already on the parent record | `evidence.entity_ids` |
| `berry_id` | One of the 4 tracked species | `evidence.berry_ids` |
| `geography_id` | Resolved `geography_ids` value, if any | `evidence.geography_ids` |
| `claim_type` | One of: `identity`, `attribute`/`trait`, `relationship`, `event`, `registry_filing`, `market_data`, `dispute` | derived from existing `Fact.classification` + `Relationship.predicate` categories, not invented |
| `relationship_predicate` | If the claim implies a Relationship, the exact enum value from `relationship.schema.json` (`owns, develops, licenses, distributes, grows, trials, sells, carries, partners_with, operates_in, markets`) or explicitly `none` | `relationship.schema.json` |
| `limitations` / `does_not_prove` | What the claim explicitly does not establish | `evidence.does_not_prove` |
| `atomicity_note` | Why this is one claim, not a bundle | new annotation field for this benchmark only — not a schema addition |

**Good/bad atomicity example** (from `ev-producereport-blugenix-2026`,
Section 6):

- **Good (atomic)**: "BluGenix was launched on 2026-05-29 as the brand for
  Costa's blueberry breeding programme, introduced with five varieties:
  Bounty, Breeze, Cascade, Delight and Eterna." — one event, cleanly
  reviewable, already exists verbatim as trusted `fact-blugenix-launch-2026`.
- **Bad (compound, not atomic)**: "BluGenix launched with five premium
  blueberry varieties boasting industry-leading 27-day shelf life across
  eight growing countries, extending Costa's 40-year breeding legacy." — four
  independently-reviewable claims (launch event, shelf-life figure with no
  stated method, growing-country list, disputed programme-age figure) forced
  into one sentence. A reviewer who disputes the shelf-life figure cannot
  reject only that part without rejecting the whole compound statement.

## 4. Negative / do-not-extract cases

Nine categories, each with a real example drawn from the gold set (not
hypothetical):

1. **Marketing adjectives presented as fact** — `ev-producereport-blugenix-2026`:
   do not extract "BluGenix varieties have industry-leading shelf life" as a
   fact; the source itself only supports "Costa claims 27 days at 4°C, no
   method stated" (already the real Fact wording, `fact-blugenix-shelf-life-claim`).
2. **Unsupported causal inference** — `ev-costa-ownership-2024`: do not infer
   "Driscoll's now controls Costa's variety-release decisions" from Driscoll's
   partial ownership stake; the source states ownership only, not operational
   control.
3. **Title overstates body** — `ev-hortifrut-mbo-genetics-2026`: the title
   says "expand... genetics platform," but the body names zero specific
   varieties transferred; do not extract a variety-transfer claim that the
   body does not contain (the real `why_it_matters` text flags this itself:
   "it rests on one originating announcement").
4. **Generic positioning language** — `ev-agrovision-10-years-2024`: "bringing
   the world a better berry" is a slogan, not an extractable claim about any
   specific variety or trait.
5. **Inferred ownership from co-occurrence** — `ev-blueberriesconsulting-agrovision-2024`:
   Agrovision growing Sekoya-programme varieties does not mean Agrovision
   owns or breeds them; the correct relationship predicate is `licenses` or
   `grows`, never `owns` or `develops` (the real Fact record,
   `fact-agrovision-licenses-not-breeds`, exists specifically to make this
   distinction explicit).
6. **Registry filing read as commercial success** — `ev-uspp031605-ridley-1602`:
   a granted plant patent proves an IP event and parentage; it does not prove
   Eureka Sunrise achieved any acreage, sales volume, or market share (see
   Section 9).
7. **Visit-as-purchase-commitment** — the Planasa flagship (Section 1a):
   retailers visiting an R&D centre and giving positive verbal feedback is
   not a signed supply agreement, listing commitment, or purchase order.
8. **Award-as-broad-preference** — `ev-fruitnet-eureka-sunrise-2023`: an
   86.5%, two-star sensory-panel score from one tasting institute is not
   evidence of general consumer preference across all markets; the source's
   own `why_it_matters` already draws this line ("a sensory panel result, not
   an agronomic measurement").
9. **Reprint read as independent corroboration** — structural, not tied to
   one source: `evidence_links.predicate: "duplicates"` already exists in
   schema precisely to keep a second pull of the same first-party release
   from being counted as independent confirmation (see TD-006). A model must
   not extract "two sources confirm X" when both are the same original
   Planasa/Costa/Driscoll's release carried by different outlets.

## 5. Source fidelity per source (what is actually scoreable)

Reported per source in Sections 6–9's tables via a `text basis` column. In
aggregate:

- **16 of 16 scored sources**: the only persisted text is `summary` +
  `why_it_matters` (prose, human/agent-authored synthesis of the original
  article, not the original article body itself). No original HTML/body was
  fetched or retained for any trusted record. This is sufficient to score
  claim-level precision/recall/atomicity/grounding against the *summary
  text as written*, but it is **not** the same task as extracting from raw
  publisher HTML — a model given only `summary`+`why_it_matters` is being
  asked to decompose an already-condensed synthesis, which is measurably
  easier than decomposing original prose. Report this distinction explicitly
  when interpreting benchmark results; do not claim the benchmark proves
  raw-article extraction competence.
- **1 pending source** (Planasa flagship, Section 1a) is the *only* item in
  this entire document with real, full original `article.paragraphs` body
  text — ironically the richest text basis in the set, and it is exactly the
  one item excluded from scoring by the trust rule. This asymmetry is real
  and worth Cursor/Codex's attention: acquisition pipelines already capture
  full body text on `web_article` drafts; nothing currently promotes that
  richer text forward when a draft is published (see TD-077 for the schema
  side of this gap).
- **1 structural spoken-media source** (`ev-lucentlands-...`, Section 10):
  `transcript.status: "not_available"` — zero scoreable text exists beyond a
  29-word summary. Flagged as insufficient for any timestamp-cited claim.

## 6. Scored gold-set sources: company newsroom / press release

| # | Source ID | Title | Berry | Date | Claims |
|---|---|---|---|---|---|
| 1 | `ev-hortifrut-mbo-genetics-2026` | Naturipe/Hortifrut expand genetics platform with Mountain Blue | blueberry | 2026-07-30 | 2 |
| 2 | `ev-costa-ownership-2024` | Costa enters new ownership phase | blueberry | 2024-02-26 | 3 |
| 3 | `ev-agrovision-10-years-2024` | Agrovision celebrates 10 years | blueberry | 2024-02-05 | 4 |
| 4 | `ev-driscolls-cbc-appeal-2025` | Driscoll's files appeal in strawberry patent case | strawberry | 2025-05-14 | 3 |

**Source 1 — `ev-hortifrut-mbo-genetics-2026`** (text basis: `summary`+`why_it_matters`, 70+43 words)

| Claim | Text | Type | Predicate | Limitation |
|---|---|---|---|---|
| 1a | Hortifrut and Naturipe Farms announced (2026-07-30) an expanded berry-genetics collaboration with Mountain Blue Orchards giving Hortifrut access to new elite blueberry selections for the US, Mexico, Peru and other Latin American countries. | event/relationship | `partners_with` | Names no specific variety transferred — do not extract a variety-identity claim (Failure Type 3). |
| 1b | The announcement itself is the sole originating source for this claim; no second independent confirmation exists in the gold set. | scope | none | Single-source — flag `verification_state: single_source`, not `corroborated`. |

**Source 2 — `ev-costa-ownership-2024`** (text basis: `summary`+`why_it_matters`, 73+47 words)

| Claim | Text | Type | Predicate | Limitation |
|---|---|---|---|---|
| 2a | A consortium of Paine Schwartz Partners, Driscoll's Inc. and BCI took control of Costa Group at A$3.20/share, effective 2024-02-26. | event | `owns` (Paine Schwartz→Costa, BCI→Costa, Driscoll's→Costa) | Ownership only — see negative case 2 (does not establish operational control over variety releases). |
| 2b | Harry Debney became interim chief executive of Costa Group. | event | none | Person-level fact; this platform deliberately does not model individuals as entities (mirrors TD-ENT-003's "leave unresolved rather than invent" discipline) — a correct extractor proposes it without inventing a Person entity. |
| 2c | Costa launched a record four new blueberry varieties during 2023. | market_data | none | Count claim, no variety names given — do not backfill variety identities not in source. |

**Source 3 — `ev-agrovision-10-years-2024`** (text basis: `summary`+`why_it_matters`, 76+41 words)

| Claim | Text | Type | Predicate | Limitation |
|---|---|---|---|---|
| 3a | Agrovision was established in 2013 and reports the tenth anniversary in this release (dated 2024-02-05). | identity | none | Date arithmetic mismatch (established 2013 → "10 years" in a 2024 release) exists in the real source itself; do not silently correct it — extract as-stated. |
| 3b | Agrovision reports more than US$350 million invested in operations over the prior six years and describes itself as the third-largest blueberry grower in Peru. | market_data | none | Self-reported figures, `source_authority` should be treated as low/owner-claim, not independently verified. |
| 3c | Agrovision states it "partners with leading breeders to develop a broad portfolio of premium varietals." | relationship | `licenses` (not `develops`) | This is the exact real distinction `fact-agrovision-licenses-not-breeds` already encodes — see negative case 5. Extracting `develops` here is a scoring failure. |
| 3d | Agrovision uses the Big Skye brand in China. | relationship | `markets` | Geography-scoped brand claim; do not generalize Big Skye to all Agrovision markets. |

**Source 4 — `ev-driscolls-cbc-appeal-2025`** (text basis: `summary`+`why_it_matters`, 95+43 words)

| Claim | Text | Type | Predicate | Limitation |
|---|---|---|---|---|
| 4a | Driscoll's filed a protective appeal against summary judgment for California Berry Cultivars in the Eastern District of California (2025-05-14). | event | `disputed`-status relationship, if modeled | This is strawberry litigation; do not let it leak into blueberry-scoped analysis (the source's own `why_it_matters` states this explicitly — a real, deliberate cross-berry-contamination guard). |
| 4b | Driscoll's states it develops exclusive patented berry varieties, does not sell its plants, and grows through more than 900 independent growers in 20+ countries, sold in 40+ countries. | relationship/market_data | `develops`, `grows` (via growers) | Owner's own characterization of its business model — extract as a `claim`, not an independently-verified `fact`. |
| 4c | Driscoll's names Soren Bjorn as chief executive. | identity | none | Person-level; same discipline as 2b. |

## 7. Scored gold-set sources: trade press

| # | Source ID | Title | Berry | Date | Claims |
|---|---|---|---|---|---|
| 5 | `ev-producereport-blugenix-2026` | Costa launches BluGenix | blueberry | 2026-06-08 | **6** (flagship multi-claim) |
| 6 | `ev-blueberriesconsulting-agrovision-2024` | Agrovision seeks year-round supply | blueberry | 2024-05-15 | **6** (flagship multi-claim) |
| 7 | `ev-italianberry-peru-varieties-2025` | Sekoya Pop dominates Peru exports | blueberry | (2025 season) | 4 |
| 8 | `ev-fruitnet-ozblu-dispute-2020` | Blueberry spat continues | blueberry | 2020-11-09 | 2 |
| 9 | `ev-leadersleague-atlantic-blue-2021` | Hortifrut acquires Atlantic Blue | blueberry | 2021-10-20 | 2 |
| 10 | `ev-fruitnet-eureka-sunrise-2023` | Taste of success for Eureka Sunrise | blueberry | 2023-01-20 | 5 (variety-role flagship, Section 8) |
| 11 | `ev-hortweek-driscolls-victoria-award` | Driscoll's Victoria wins Best New Variety | blackberry | 2017-08-01 | 2 |
| 12 | `ev-fruitnet-driscolls-zara-best-strawberry` | Driscoll's Zara named best supermarket strawberry | strawberry | 2026-06-23 | 2 |

**Source 5 — `ev-producereport-blugenix-2026`** (text basis: `summary`+`why_it_matters`, 103+62 words; already has 4 corresponding trusted Facts — reused verbatim below as ground truth, since these are real, already-approved decompositions of this exact article)

| Claim | Text (near-verbatim to the real trusted Fact) | Type | Predicate | Limitation |
|---|---|---|---|---|
| 5a | BluGenix was launched 2026-05-29 as the brand/platform for Costa's blueberry breeding programme, with five varieties: Bounty, Breeze, Cascade, Delight, Eterna. | event | `owns` (Costa→BluGenix) | = real `fact-blugenix-launch-2026` (confidence: high). |
| 5b | Costa claims 27-day shelf life at 4°C for all five varieties, up to 50 days for Eterna; no trial site, season, replication, or protocol stated. | attribute | none | = real `fact-blugenix-shelf-life-claim` (confidence: low) — owner claim, not independently measured (negative case 1). |
| 5c | South Africa, Zimbabwe, Morocco, US, Mexico, Peru, China, Australia are named as BluGenix growing countries. | market_data | `operates_in` | = real `fact-blugenix-growing-countries` (confidence: medium). |
| 5d | Costa's stated breeding-programme age is inconsistent: "more than 25 years" on Costa's own pages vs. "close to 40 years" in this article. | dispute | none | = real `fact-costa-vip-age-conflict` (confidence: low, status: disputed) — **this fact requires two OTHER evidence records** (`ev-costa-vip`, `ev-costa-heaviest-blueberry-2024`) in addition to this one; extracting it from `ev-producereport-blugenix-2026` alone is single-document overreach (Failure Type 3, Section 12). |
| 5e | Costa CEO Marc Werner and Costa Berry International regional director Leon Van Biljon are quoted in the announcement. | identity | none | Low CI value on its own — a good extractor should not spend a separate high-priority proposal slot on attribution existence alone (Section 13, proposal-density guidance). |
| 5f | The programme is described as drawing on "close to 40 years" of plant breeding expertise. | attribute | none | This is the source half of the 5d dispute — extractable alone as a plain claim; only becomes a dispute when paired with the other two sources. |

**Source 6 — `ev-blueberriesconsulting-agrovision-2024`** (text basis: `summary`+`why_it_matters`, 103+58 words)

| Claim | Text | Type | Predicate | Limitation |
|---|---|---|---|---|
| 6a | Agrovision's Peruvian operation began with varieties Biloxi and Ventura, later moving to Sekoya-programme varieties. | relationship | `licenses` | Do not extract `develops` — see negative case 5. |
| 6b | 2022 figures: 2,800 hectares of berries across Peru, Mexico, and Morocco. | market_data | none | Cross-country aggregate, do not split into per-country hectares not separately stated in this excerpt. |
| 6c | 2022 turnover of US$210 million and more than 2,500 containers exported, 40% to China. | market_data | none | Owner-reported figures. |
| 6d | Peruvian operations named at Olmos and Morrope, Lambayeque. | geography | `operates_in` | |
| 6e | Mexican operations in Jalisco, above 300 hectares. | geography | `operates_in` | |
| 6f | Moroccan operations in Souss-Massa, at 250 hectares. | geography | `operates_in` | |

**Source 7 — `ev-italianberry-peru-varieties-2025`** (text basis: `summary`+`why_it_matters`, third-party Proarándanos volume data)

| Claim | Text | Type | Limitation |
|---|---|---|---|
| 7a | Sekoya Pop led Peru's 2024/25-season blueberry exports at 2,514 tonnes (19% of national volume, to week 33). | market_data | Third-party data, closest available proxy for real adoption vs. announced launches — highest `information_confidence` item in the set. |
| 7b | Eureka accounted for 655 tonnes (~5%) in the same period. | market_data | |
| 7c | Eureka Sunrise appears under two separate codes in the same table — "Ridley 160" (714t) and "Ridley 1602" (183t). | dispute/data_quality | **Do not sum the two figures** — the source's own `why_it_matters` states this is itself a data-quality finding requiring confirmation before use. A correct extractor flags the duplicate coding rather than silently merging or silently picking one number. |
| 7d | The two Eureka Sunrise codes are the same PVR entity — cf. `ev-uspp031605-ridley-1602`'s parentage record (Section 9) confirming "Ridley 1602" is Eureka Sunrise's breeding designation. | entity_resolution | Cross-source resolution, correctly requires the registry record from Section 9 to confirm — do not resolve this from Source 7 alone. |

**Source 8 — `ev-fruitnet-ozblu-dispute-2020`** (text basis: `summary`+`why_it_matters`)

| Claim | Text | Type | Limitation |
|---|---|---|---|
| 8a | United Exports asserted PBR ownership in South Africa/EU and had ~27 tonnes across two containers seized in Rotterdam (2020-10-27 and 2020-11-05) from the Rossouw Group's Ross Berries operation. | dispute | Border enforcement event — real, but does not establish the dispute's legal outcome (not stated in source). |
| 8b | United Exports announced a 5-year, R1.3 billion (~US$85M) South African investment plan. | market_data | Explicitly a company announcement carried by trade press, not an audited commitment — negative case 1 applies. |

**Source 9 — `ev-leadersleague-atlantic-blue-2021`** (text basis: `summary`+`why_it_matters`)

| Claim | Text | Type | Predicate | Limitation |
|---|---|---|---|---|
| 9a | Hortifrut acquired 100% of Atlantic Blue (Huelva, Spain) at enterprise value €241M (~US$280M), including the SAT processing plant, 100% of the Euroberry commercial platform (~€200M annual sales), and Atlantic Blue's global blueberry/low-chill-cherry breeding programme. | event | `owns` | Single-source — Hortifrut's own transaction page was not retrievable, so this rests on one trade report (source's own `why_it_matters` states this). |
| 9b | The acquisition increased Hortifrut's growing area by ~20%. | market_data | none | |

**Source 10 — `ev-fruitnet-eureka-sunrise-2023`** — see Section 8 (variety-role flagship).

**Source 11 — `ev-hortweek-driscolls-victoria-award`** (text basis: `summary`+`why_it_matters`; carries real `does_not_prove`)

| Claim | Text | Type | Predicate | Limitation |
|---|---|---|---|---|
| 11a | Victoria, a large sweet blackberry variety in commercial production in California since 2005, won HortWeek's Best New Variety (Top/Soft Fruit) award; grown in the UK (Kent) by Berry Gardens/Salman's Farm, a Driscoll's growing partner. | identity/relationship | `grows` (Berry Gardens→Victoria) | Reuse the record's own real `does_not_prove`: does not establish market share, sales volume, or current (2026) UK acreage — the report dates to 2017. |

**Source 12 — `ev-fruitnet-driscolls-zara-best-strawberry`** (text basis: `summary`+`why_it_matters`; carries real `does_not_prove`)

| Claim | Text | Type | Limitation |
|---|---|---|---|
| 12a | The Guardian's 10-retailer taste test named Driscoll's Zara "best overall supermarket strawberry"; sold in the UK both under the Driscoll's brand and via retailer own-label (e.g. Tesco "British Zara Strawberries"). | attribute/market_data | Reuse the record's own real `does_not_prove`: does not establish market share/sales volume, and does not establish Zara is exclusive to Driscoll's-branded punnets. `verification_state: single_source` on the record itself — do not upgrade to corroborated. |

## 8. Variety-specific test cases (identity / breeder / owner / marketer / retailer-feedback / sensory / geography / commercial-interest, kept distinct)

**Flagship: `ev-fruitnet-eureka-sunrise-2023`** (text basis: `summary`+`why_it_matters`, richest single variety-role source in the trusted corpus)

| Dimension | Claim | Must NOT collapse into |
|---|---|---|
| Identity | The variety is "Eureka Sunrise," bred by Mountain Blue Orchards (`variety-eureka-sunrise`, `company-mountain-blue-orchards`). | ...the separate variety "Eureka" (`variety-eureka`) — related but distinct, per the real parentage record in Section 9. |
| Breeder | Mountain Blue Orchards developed it (`develops`). | ...the exclusive grower relationship below — breeding and growing are different predicates on different entities. |
| Exclusive grower/marketer | Grown **exclusively** by BerryWorld growers (`grows`/`sells`, `rel-berryworld-sells-eureka-sunrise`). | ...ownership of the variety itself — BerryWorld sells it, Mountain Blue Orchards bred and (per Section 9) owns the patent. |
| Sensory/independent award | Two-star Superior Taste Award, 86.5% score from the International Taste Institute. | ...an agronomic or yield measurement — the source's own `why_it_matters` explicitly flags "a sensory panel result, not an agronomic measurement" (negative case 8). |
| Geography | Grown in South Africa, Zimbabwe, Morocco, Spain, Portugal, with plantings in Egypt. | ...a single "global" claim — extract the named list, not a generalization beyond it. |
| Attribution | Adrian Olins, BerryWorld Group divisional chief executive, is quoted. | ...a Mountain Blue Orchards statement — the quote is from the marketer, not the breeder; do not misattribute. |

**Contrast case (single-role, correctly thin): `ev-uspp031605-ridley-1602` /
`variety-ponca` / `variety-ouachita`** — Ponca and Ouachita (University of
Arkansas) each have exactly one real relationship (`develops`, breeder only)
in the trusted graph — no separate owner, licensee, or marketer role exists in
real evidence for either. A correct extractor must not invent a marketer role
for these two just because Eureka Sunrise has one; absence of a role is a
real, reportable state, not a gap to fill by analogy.

**Contrast case (retailer-feedback, not sensory/registry): the Planasa
flagship, Section 1a** — the sharpest distinction case in the whole set.
Unlike Eureka Sunrise's *independent tasting-panel score* or Ridley 1602's
*registry filing*, the Planasa flagship's 7 claims are self-reported retailer
verbal impressions relayed by the breeder itself — the weakest evidentiary
tier of the three, and the one most likely to be over-trusted by a model that
does not track source-authority distinctions.

## 9. Registry test cases (APPLICATION / GRANT / RIGHTS-HOLDER / DENOMINATION, and what a filing does not establish)

Both sources below are real, trusted, but carry their registry facts only in
prose (`summary`) — neither has the structured `patent_filing`/`cpvo_filing`
object (TD-080). This is itself a meaningful, in-scope test: a good extractor
should recover these structured facts from prose exactly as reliably as it
would from a populated object.

**`ev-uspp031605-ridley-1602`** — USPP031605P3, "Ridley 1602" (Eureka Sunrise)

| Field | Value | Does NOT establish |
|---|---|---|
| APPLICATION | 15/732,875, filed 2018-01-09 | commercial production, acreage, or sales |
| GRANT | 2020-03-31 | market adoption (see Source 7's real volume data as the *separate*, independently-needed proof of that) |
| RIGHTS-HOLDER (assignee) | Mountain Blue Orchards Pty Ltd | that MBO is the exclusive seller — BerryWorld is the grower/marketer (Section 8); assignee and marketer are different roles on different entities |
| Inventor | Ridley Bell | — |
| DENOMINATION vs. breeding designation | Commercial name "Eureka Sunrise" vs. breeding code "M14-16-02" vs. patent title "'Ridley 1602'" — three distinct labels for one variety | that these three names are three different varieties (this is the exact ambiguity Source 7c/7d surfaces independently) |
| Parentage | 'Ridley 1403' (PP25,432) × 'Ridley 4609', bred Lindendale, NSW, 2011 | that Eureka Sunrise is a "variant" of Eureka rather than a distinct offspring cultivar — the source's own `why_it_matters` makes this exact distinction |

**`ev-cfia-pbr-sekoya-grande`** — Canadian PBR, breeding designation 'FC13-122' (Sekoya Grande)

| Field | Value | Does NOT establish |
|---|---|---|
| APPLICATION | 18-9614, dated 2018-09-20 | — |
| GRANT | 2023-10-06, certificate 6925 | — |
| Expiration | 2043-10-06 | current commercial status — a still-valid certificate says nothing about whether the variety is still in active production |
| RIGHTS-HOLDER | Named individual breeders (Peter Stefan Boches, Haley Belnap-McCall, Adam L. Wagner) | that Fall Creek Farm & Nursery is the rights-holder of record — the certificate names people, not the company; do not silently substitute the company entity for the named breeders without a separate assignment record |
| Parentage | 'ZF06-050' × 'ZF06-013', made 2010 Lowell, Oregon, selected 2013 | — |
| Independent examiner description | "very strong vigour, large fruit, very firm fruit, high sweetness and high acidity," 2022 Chilliwack BC trial, randomised complete block, 4 reps × 3 plants | market adoption, commercial volume, or grower count — an examiner trial description is the strongest *agronomic* evidence in this entire gold set (an independent, replicated, located, dated trial), but it is still not a commercial-success claim (negative case 6) |

## 10. Spoken media (structural finding, not a scored case)

**`ev-lucentlands-scaling-blueberry-industry-2025`** — the only trusted
`evidence_role: "publication_artifact"` / `media_format: "podcast"` record in
the entire corpus. `transcript.status: "not_available"`. The only text is a
29-word `summary` and 18-word `why_it_matters` naming the episode's general
topics (blueberry genetics, flavor, consumer preferences, investment,
professionalization, Southern Africa opportunity).

**No real trusted source in this corpus can support a scored,
timestamp-cited spoken-word claim.** This is not a gap this mission can close
— building or requesting real transcript acquisition is out of scope, and
using this podcast's summary to fabricate plausible-sounding timestamped
segments would violate the "no fabricated source IDs/excerpts" validation
rule as directly as inventing a fake article would.

The honest existing substitute is `benchmarks/atomic-ci-v1.json` — the
already-committed, company-neutral **synthetic** transcript-segment fixture
the real `atomic-ci-v1` extraction pipeline is evaluated against today,
precisely because no real trusted transcript exists (confirmed directly in
`docs/v2/ATOMIC-CI-EVALUATION.md`: "Company-neutral synthetic cases..."). This
gold set does not duplicate or replace that fixture; it defers to it as the
correct, already-proven spoken-word reference until a real trusted transcript
exists (see TD-078).

Code-switching / proper-noun-uncertainty test: not constructible from real
data for the same reason — no real trusted transcript exists to draw a real
example from. Flagged as blocked, not fabricated.

## 11. Deterministic scoring rubric

Eight dimensions, each 0–3, mirroring the already-proven human-review rubric
in `docs/v2/ATOMIC-CI-EVALUATION.md` (Grounding, Atomicity, Qualifier fidelity,
CI relevance, Normalization, Linking) extended with the two Mission 6
explicitly requires that the existing rubric does not yet separate out:

| Dimension | 0 | 1 | 2 | 3 | Worked example |
|---|---|---|---|---|---|
| Precision | Majority of proposed claims unsupported | Some unsupported claims mixed with supported ones | Nearly all supported, minor overreach | Every proposed claim directly supported | Failure: extracting Section 4 case 3 (title-overstates-body) as if the body supported it |
| Recall | Misses most real claims in source | Misses a material claim | Recovers all but a minor claim | Recovers every claim in the annotated set | Source 5 (BluGenix): missing 5a/5c/5d loses most of the article's real content |
| Atomicity | One compound summary sentence for a multi-claim source | Some bundling remains | Minor over/under-splitting | Matches the annotated atomic boundary | The Planasa flagship (Section 1a) is the canonical worked example: 7 varieties in ≤4 sentences must decompose to ≥7 claims, not 1 |
| Grounding | Statement not traceable to any source text | Traceable but with a material support gap | Traceable with minor ambiguity | Exact excerpt directly supports the statement | Source 5d requires citing the age-conflict, not inventing a resolution to it |
| Entity resolution | Wrong entity, or entity invented | Right entity family, wrong specific record (e.g. Eureka vs. Eureka Sunrise) | Correct with minor ambiguity flagged | Exact, correct `entity_ids` match | Source 7c/9 — Eureka vs. Eureka Sunrise vs. "Ridley 160"/"Ridley 1602" is the flagship confusion case |
| Scope | Claim applies far beyond what source supports | Minor scope overreach | Scope correct with minor imprecision | Scope exactly matches source (single-document, single-claim, dated) | Source 5d extracted from Source 5 alone, without the two corroborating articles it actually needs |
| Overreach | Confident claim the source explicitly disclaims or contradicts | Confident claim beyond stated limitation | Minor confidence overstatement | Confidence matches source's own hedging/attribution | Extracting Source 6a as `develops` instead of `licenses` |
| Duplication | Same claim proposed multiple times or across a reprint pair as if independent | Occasional near-duplicate | Rare, harmless near-duplicate | Clean, deduplicated candidate set | Negative case 9 — reprint-as-independent-corroboration |

**Acceptance is not chosen to make any current model pass.** No specific
numeric threshold is set in this document; Codex's qualification harness
determines pass/fail exactly as `scripts/qualify_extraction_model.py`
already requires explicit human approval regardless of automated score (see
Section 15).

## 12. High-value failure types (11), each grounded in a real gold-set item

1. **Summary collapse** — multi-claim source reduced to one generic sentence. Flagship: Planasa (1a), 7 claims → 1.
2. **Cross-entity attribute bleed** — an attribute correctly stated in source gets attached to the wrong variety. Flagship: Planasa (1a) — 7 varieties in close proximity is the maximum-risk configuration.
3. **Single-source overreach into a cross-source claim** — extracting a claim from one article that the real trusted Fact record shows actually requires multiple sources. Flagship: Source 5d (`fact-costa-vip-age-conflict` needs 3 evidence_ids, not 1).
4. **Non-transcript timestamp fabrication** — inventing a plausible `start_seconds` for a text article because `artifact_locator` currently requires one (TD-077). Every scored source in Sections 6–9 is text, none has real seconds-based timing.
5. **Owner claim laundered into fact** — a self-reported figure with no stated method presented with fact-level confidence. Flagship: Source 5b (BluGenix shelf-life).
6. **Registry filing read as commercial proof** — Section 9's core lesson, both worked examples.
7. **Feedback laundered into validation** — retailer/visitor impressions presented as sensory-panel or agronomic evidence. Flagship: Planasa (1a) vs. the genuine independent-panel case in Source 10/Section 8.
8. **Duplicate/reprint counted as corroboration** — negative case 9; the schema already has `evidence_links.predicate: "duplicates"` for exactly this.
9. **Entity-identity collision** — Eureka vs. Eureka Sunrise vs. two PVR codes for the same cultivar. Flagship: Source 7c/7d + Section 9's Ridley 1602 denomination table.
10. **Qualifier/attribution loss** — "partners with leading breeders" (self-description) silently rewritten as "is a breeder." Flagship: Source 3c / negative case 5.
11. **Proposal flooding on low-CI-value attribution** — turning "X was quoted" into its own separate high-priority proposal for every named spokesperson. Flagship: Source 5e; see Section 13.

## 13. Review economics / proposal-density expectations

A good extractor run against this gold set should produce a proposal count
close to the annotated claim count per source (Sections 6–9's per-source
tables), not a large multiple of it:

- Source 5 (BluGenix, richest scored source): 6 annotated claims. An
  acceptable run: 5–8 proposals. A run producing 20+ proposals from one
  103-word summary is flooding (Failure Type 11), even if every individual
  proposal is technically grounded — CI relevance and reviewer time are part
  of what this rubric protects, mirroring `ATOMIC-CI-EVALUATION.md`'s own
  "excessive proposal volume" metric and Section 13's own explicit "should
  not turn a 10-claim article into 50 noisy proposals" instruction.
- The Planasa flagship (1a), if it were ever scored: 7 annotated claims from
  ~300 words is the highest legitimate claim-density case in the set — a
  model that produces fewer than 7 is under-extracting (summary-collapse); a
  model producing 25+ is almost certainly re-deriving generic marketing
  language as if each adjective were its own claim.
- Thin single-claim sources (the raspberry/blackberry substitutes, Section
  14) should produce exactly 1 proposal, sometimes 0 if the model correctly
  judges the single sentence too generic to extract (an accurate 0-candidate
  run is graded correct, mirroring `atomic-ci-v1`'s own "zero-candidate
  correctness" metric).

## 14. Thin / single-claim sources (precision and zero-candidate calibration)

Included because at least some of the gold set must test restraint, not just
recall:

- **`ev-20260806173539-86c2-tsbc-partners-with-berrytech-on-new-rasp`**
  (raspberry, only real raspberry breeder/licensee example in the trusted
  corpus): 1 claim — TSBC signed an exclusive UK/Ireland/Portugal
  grow-and-distribute deal with Berrytech for raspberry variety Amalia Rossa
  (2023-10-20). `why_it_matters` is empty; `auto_captured: true` — this
  record itself is thinner than the curated "blueberry public pilot" batch,
  and that thinness should be recovered correctly (1 claim, not padded).
- **`ev-20260806173540-a6ec-new-year-round-premium-blackberry-platfo`**
  (blackberry, BK 6-13/Rejoice): 1 claim — "Built around the new BK 6-13
  variety, the company's [PSG's] program boasts steady supply and high-spec
  fruit year-round." Tests the brand-vs-variety distinction directly: Rejoice
  is the platform brand (`entity_type: "brand"`), BK 6-13 is the one named
  cultivar under it — a correct extractor names the specific variety, not
  just the brand.

## 15. New Technical Debt registered by this mission

TD-076 confirmed as the highest existing ID immediately before writing this
document (re-verified via `docs/v2/TECHNICAL-DEBT-REGISTER.md`, all `TD-###`
and `### TD-###` occurrences scanned). Four new entries, TD-077 through
TD-080, added there by this mission — each a real, previously-undocumented
structural finding surfaced while building this benchmark, not manufactured
to pad a debt count:

- **TD-077** — `artifact_locator` requires `start_seconds`; `article.paragraphs[].index`
  is the schema's own documented written-text locator equivalent (see
  `evidence.schema.json` line ~316: "a future qualified extraction step cites
  paragraph indexes, never an invented timestamp") but has no corresponding
  path through the `atomic_evidence` conditional requirement. A future
  text-article atomic Evidence proposal cannot validate without either a
  schema change or a fabricated timestamp.
- **TD-078** — Zero real trusted spoken-word source has persisted transcript
  text. The entire `atomic-ci-v1` pipeline has only ever been evaluated
  against the synthetic `benchmarks/atomic-ci-v1.json` fixture.
- **TD-079** — Zero non-English trusted Evidence text exists, despite live
  French/Spanish/Italian discovery vocabulary already in production
  (TD-072, TD-ACQ-004). No multilingual extraction case can be built from
  trusted data until a non-English source is captured and published.
- **TD-080** — No trusted Evidence carries the structured `patent_filing` or
  `cpvo_filing` object; every record that has one is a pending draft. All 30
  real registry trusted records (22 `patent_record` + 8
  `plant_breeders_rights_record`) carry the same bibliographic facts only as
  prose, never as the structured object.

## 16. Codex handoff

Everything needed to run a qualification pass, with no model execution
required from this mission:

- **Source IDs**: the 16 scored IDs listed in Sections 6–9 and 14,
  plus the 1 structural (`ev-lucentlands-scaling-blueberry-industry-2025`)
  and 1 pending-flagship (`ev-media-069f07925d20b2d93743`) IDs, clearly
  marked as out-of-scoring in Sections 1a/10.
- **Proposition tables**: every row in Sections 6–9 and 1a is a scoreable
  proposition with its own `normalized_statement`, `exact_excerpt` (quoted
  verbatim above), `claim_type`, `relationship_predicate` where applicable,
  and `limitations`/`does_not_prove`.
- **Forbidden claims**: Section 4's 9 categories, each with its real
  grounded example — a proposal matching any of these against its cited
  source should score 0 on Precision/Overreach regardless of grounding
  quality elsewhere.
- **Scoring rules**: Section 11's 8-dimension, 0–3 rubric.
- **Density expectations**: Section 13.
- **Pass criteria**: none fixed by this document, matching Mission 6's own
  instruction not to tune thresholds to a model. `scripts/qualify_extraction_model.py evaluate`
  already requires a human `approve` step regardless of automated score —
  this benchmark supplies better *evaluation material*, not a new
  automatic-approval path.
- **Known scope limit Codex should not try to close from this document
  alone**: this benchmark is text/prose-only (Sections 6–9) because that is
  what the trusted corpus actually contains (Section 2). It does not
  qualify a model for real transcript timestamp extraction (Section 10) or
  non-English extraction (Section 2) — those remain open per TD-078/TD-079.

## 17. Validation

- Every source ID cited above was opened and read directly from
  `data/evidence/*.json`, `data/facts/*.json`, or (for the flagship,
  explicitly marked pending) `inbox/evidence/*.json` in this session — none
  fabricated.
- Every quoted excerpt is copied verbatim from the record's own `summary`,
  `why_it_matters`, or `article.paragraphs` text, not paraphrased.
- No `data/`, `inbox/`, schema, Source, or trust-state file was modified by
  this mission. `git status` before writing this document showed no
  unrelated changes; this document and the Technical Debt Register update
  are the only files this mission touches.
- Claude's documentation pass added no machine-readable fixture. Codex's
  qualification-harness integration subsequently added
  `scripts/materialize_atomic_gold_set.py` and the mechanically derived
  `benchmarks/atomic-evidence-gold-set-v1.json`. The JSON records this
  document's SHA-256 and is reproducibly checked with `--check`; this document
  remains the human-owned benchmark rather than a competing annotation set.
- `pytest`, `validate_records.py`, and `build_static.py` are unaffected
  (docs-only change plus a Technical Debt Register edit); the CI Markdown-only
  fast path applies.

## 18. No-trust-mutation confirmation

This mission created zero Fact, Relationship, trusted Atomic Evidence,
Source-authority, or Assessment records; published nothing; rejected
nothing; changed no `review_state` anywhere in `data/` or `inbox/`. The one
pending record referenced (`ev-media-069f07925d20b2d93743`) was read, not
edited — its `status`/`review_state` are exactly as this mission found them.
Benchmark only.
