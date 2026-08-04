# Research method statement

Package: `blueberry-public-pilot-2026-08-03`
Berry scope: blueberry only (`berry-blueberry`)
Compiled: 2026-08-03 to 2026-08-04

## 1. Purpose and standing assumptions

This package is a first public-source research pass intended for human review before any of it
enters the trusted dataset. It makes no assumption about which organisation, if any, employs the
reader. Every organisation in it — including the largest and most frequently discussed — is
treated as an ordinary market entity subject to the same evidence, confidence and classification
rules. No record is marked as "us", "our company", or given preferential confidence.

## 2. What counts as what

The package keeps six concepts separate and never collapses them into a single unqualified
statement.

| Concept | Representation | Rule applied |
|---|---|---|
| Evidence | `evidence` record | One record per distinct source item that was opened and read. |
| Fact | `fact` record, `classification: "fact"` | A value stated by a registry, a government body, or an institution publishing its own measurements. |
| Attributed claim | `fact` record, `classification: "claim"` | A value asserted by an owner, marketer or interested party, or reported by a single source without corroboration. The statement names who is claiming. |
| Entity | `entity` record | A company, variety, patent, brand, breeding programme, trait, geography, retailer or berry. |
| Relationship | `relationship` record | A directed link between two entities, always with at least one supporting evidence record. |
| Assessment / signal / recommendation | `signals/` folder, and the four `priority` dimensions on each evidence record | Not importable. Analyst inference is never written into a `fact`. |

The controlling rule: an attributed claim is never turned into an independently supported fact.
Where an owner's claim and a registry description disagree — as with `Ridley 1403`, described as
medium-firm in the plant patent and in stronger terms in owner marketing — both are recorded and
the divergence is itself stated as a claim-classified fact.

## 3. Source tiering

The `evidence` schema has no tier field, so tier is carried as exactly one namespaced tag per
record. The package validator enforces that exactly one is present.

| Tag | Meaning | Examples used here |
|---|---|---|
| `tier-1` | Primary record, or an entity speaking authoritatively about itself in a form where accuracy is legally or institutionally constrained | Granted plant patents; Canadian plant breeders' rights examination reports; government export variety lists; a development finance institution's own transaction announcement; a breeding institution's published measurement pages; a company's own corporate facts and catalogue claims |
| `tier-2` | Established trade or industry publication with an identified author, reporting with some independence | Fruitnet titles, The Packer, FreshPlaza, FreshFruitPortal, Produce Report, Portalfruticola, Italian Berry, International Blueberry Organization reports, Agronometrics analysis |
| `tier-3` | Low-authority, self-published, unattributed, translated or otherwise unverifiable | An individual's LinkedIn analysis post; a blog translation of a patent document |

A company's own page is `tier-1` for what the company *is* (founding date, corporate structure,
stated rights position) and simultaneously a source of `claim`-classified statements for what the
company says its products *do*. The tier describes the authority of the document, not the truth of
every sentence in it.

Two rules constrain how tiers are used:

- A company press release and a trade article that merely republishes it are not independent
  sources. Where this happened — the SEKOYA Nova figures appear in both a Fall Creek press
  release and subsequent trade coverage — the derived article does not raise the confidence of
  the claim, and the evidence record says so explicitly.
- A `tier-3` source is never the sole support for a material fact. The one `tier-3` registration
  analysis in this package supports only a `claim`-classified, low-confidence record that is
  flagged for replacement by direct registry counts.

## 4. Confidence assignment

Confidence is a property of how well the statement is supported, not of how recent or how
interesting it is. Recency alone never raises confidence.

| Level | Applied when |
|---|---|
| `high` | A registry record, or two or more independent sources agreeing, or an institution publishing its own measurement with the measurement stated |
| `medium` | A single credible source, or a corporate fact from the company itself, or a registry-derived value reached through a secondary transcription |
| `low` | A single-source owner claim with no stated method; a disputed value; a value whose confidence interval spans the point of interest |

The four newest items in the package — the SEKOYA Nova announcement, the `FC11-164` claims, the
2026 Chilean validation list and the 2026 grower event — are the ones most likely to be mistaken
for high-confidence findings because they are recent. They are recorded at `low` and `medium`
confidence precisely because they rest on unreplicated company statements.

## 5. Identity resolution

Blueberry variety data is unusually hard to join because a single genetic object can carry four
different labels at once: a breeder selection code, a patented cultivar denomination, a trademark
and a retail brand. The package does not merge any two of these unless a retrieved source states
that they refer to the same object.

Rules applied:

- Breeder selection codes, patented cultivar names, trademark names and branded product names are
  kept distinct until evidence confirms identity.
- Ownership is never inferred from distribution, and breeding ownership is never inferred from
  nursery availability. United Exports appears as an exclusive sub-licensor and marketer of the
  OZblu varieties, and Nature Select as their breeder, because the sources support exactly that
  split and no more.
- Commercial success is never inferred from a launch announcement. The 2019 MIGIVA joint venture
  and the 2020 R1.3 billion South African plan are recorded as announcements of intent, not as
  realised production or investment.
- Where a brand name and a cultivar denomination are the same word — "Eureka" — they are two
  records, and both carry an explicit naming-hazard note.
- Where a single cultivar appears under two codes in one dataset — Eureka Sunrise as
  `Ridley 160` and `Ridley 1602` in the same Proarandanos table — both figures are recorded and
  the package states that they must not be summed without confirmation.
- Where identity could not be resolved at all — Twilight's selection code, the commercial name of
  `FC11-164` — the entity carries `status: "unverified"`, the unresolved field is `null`, and the
  candidates that were checked and rejected are listed in the record.

## 6. Trait provenance

Trait values are not comparable across sources, so each trait entry inside
`variety.attributes.traits[]` carries its own provenance marker and its own evidence references.

| Provenance | Meaning |
|---|---|
| `owner_or_marketer_claim` | Asserted by the party that owns or sells the variety |
| `named_trial_measurement` | Measured in a trial with a stated location and, where published, season and design |
| `independent_report` | Reported by a third party that neither owns nor markets the variety |
| `regulatory_or_registry_record` | Stated in a patent, plant breeders' rights record or government registry |
| `analyst_inference` | Reserved; not used in any importable record in this package |
| `unresolved` | Sources disagree and no basis for choosing between them was found |

Firmness illustrates why this matters. The University of Florida publishes a g/mm compression
index, US plant patents sometimes cite FirmTech instrument readings, and Canadian plant breeders'
rights reports use ordinal descriptors such as "very firm". These are three different
measurements. The package records all three and states, in the `trait-fruit-firmness` entity and
in the affected fact statements, that they are not directly comparable.

## 7. Dates

Dates are never invented. `published_date` is `null` where a source carries no publication date,
which is common for corporate and registry pages. `captured_date` is the date this package read
the source. Event dates in relationships use `effective_date` only where a source states the date
of the event itself, and the same date is restated in the evidence summary because the schema
provides no separate event-date field.

## 8. Geographic coverage

Coverage follows the public record rather than an even geographic quota. Where evidence is thin
for a region, the gap is recorded rather than filled by inference. The current distribution is
documented in the coverage-gaps deliverable.

## 9. Handling of copyrighted material

No long passages are reproduced. Evidence summaries are original descriptions of what a source
says, written to be usable without the source at hand, and every record carries the URL so a
reviewer can read the original.

## 10. What was deliberately not done

- Production schemas were not modified. Where the schema could not represent a concept, the
  closest valid existing representation was used, the limitation was documented, and a
  backward-compatible enhancement was proposed separately in `proposed-schema-enhancements.md`.
  No unsupported field was invented inside an import record.
- Nothing was written into `data/entities/`, `data/evidence/`, `data/facts/`,
  `data/relationships/` or `data/strategic-questions/`. The package is additive and stages
  everything under `data/imports/`.
- No evidence record was set to `published`. Approval is a separate, explicit human step.
- No signal is labelled "confirmed".
- No source requiring payment, registration or private access was used, and no private or
  non-public data was sought.
