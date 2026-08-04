# QA and validation report

Package: `blueberry-public-pilot-2026-08-03`
Validated: 2026-08-04
Python: 3.12 (`pydantic==2.11.7` does not build on 3.14)

**Result: PASSED.** Schema, naming conventions and referential integrity are all clean. 176
warnings, all advisory, all accounted for below.

---

## 1. What was checked

Four independent checks were run, each catching a different class of defect.

| Check | Scope | Result |
|---|---|---|
| `scripts/validate_package.py` | Package schema, id conventions, referential integrity, brief-specific rules | PASSED, 176 warnings |
| `scripts/import_package.py --dry-run` | Import feasibility, collision detection, file counts | PASS, 674 files, no collisions |
| Trial import into a scratch copy of the repository | Real write, then the repository's own validator | Clean |
| `pytest` after trial import | The repository's existing 28 tests | 28 passed |

Plus a custom orphan check for entities carrying no evidence, fact or relationship link, and an
application route smoke test.

## 2. Record counts

| Type | Count | Brief target | Status |
|---|---|---|---|
| Entity | 155 | - | - |
| - variety | 40 | 25-40 | at the top of range |
| - company | 32 | 8-12 organizations | **over**, see 6.1 |
| - patent | 38 | - | - |
| - geography | 16 | - | - |
| - trait | 10 | - | - |
| - breeding_program | 9 | - | - |
| - brand | 8 | - | - |
| - retailer | 1 | - | - |
| - berry | 1 | - | - |
| Evidence | 121 | 50-80 | **over**, see 6.2 |
| Fact | 186 | 75-150 | **over**, see 6.3 |
| Relationship | 204 | - | - |
| Strategic question | 8 | 5-8 | at the top of range |
| Signal | 6 | 3-6 | at the top of range, none `confirmed` |
| **JSON files in package** | **682** | - | 674 importable + 6 signals + `manifest.json` + `scripts/_stats.json` |
| Distinct source URLs | 121 | 20-30 monitored sources | **over**, see 6.4 |

## 3. Referential integrity

Every check below passed with zero failures.

- Every `fact.evidence_ids` entry resolves to a staged or pre-existing evidence record. Minimum one
  per fact, enforced by schema.
- Every `relationship.subject_id` and `object_id` resolves to a staged or pre-existing entity.
- Every `relationship.evidence_ids` entry resolves. Minimum one per relationship.
- Every `evidence.entity_ids` entry resolves.
- Every entity back-reference (`evidence_ids`, `fact_ids`, `relationship_ids`) resolves.
- Every signal's `evidence_ids`, `entity_ids` and `strategic_question_ids` resolve. Minimum two
  evidence records per signal, enforced by the package validator per the brief.
- No duplicate ids across the whole package - asserted at build time, re-checked at validation.
- Every entity id is prefixed with its own `entity_type`, so no detail route 404s.

## 4. Orphan analysis

A custom check looked for entities with no evidence, fact or relationship link at all. Twelve were
found and each was resolved:

| Finding | Count | Resolution |
|---|---|---|
| Patents cited as parents on another patent's front page | 3 | Added to the citing evidence record's `entity_ids`, so their presence is traceable. Also demoted to `unverified` |
| Wave 1 patents whose front page was never staged as evidence | 7 | Demoted to `status: "unverified"` with an explicit `verification_status` attribute. Logged in `coverage-gaps.md` |
| A brand with no supporting source (`brand-sweetest-batch`) | 1 | **Removed from the package.** Logged in `coverage-gaps.md` |
| A geography with evidence that had not been linked (`geography-zambia`) | 1 | Relationship `rel-united-exports-operates-in-zambia` added at `confidence=low` |

Seven patent entities remain without an evidence link. This is now **stated in the data itself**
rather than being an unflagged hole: each carries `status: "unverified"` and an attribute saying
that no evidence record captures the patent document. The build script prints them on every run.

## 5. Warnings: all 176 accounted for

### 5.1 Role-vocabulary advisories - 172 warnings

The validator compares each `roles[]` value against a proposed vocabulary and notes anything
outside it. **The entity schema does not constrain `roles[]`** - it is a free-form string array with
no enum - so these are style advisories, not defects.

Most frequent: `intellectual_property_right` (38), `cultivar` (17), `measurable_attribute` (10),
`competitor` (9), `private_breeding_program` (8), `genetics_licensor` (8), `rights_holder` (7),
`consumer_brand` (7), `production_or_regulatory_jurisdiction` (6), `grower` (6).

These roles were chosen deliberately to satisfy the brief's instruction not to classify every
organization as "competitor". Only 9 role assignments in the package are `competitor`. The rest
preserve the distinctions the brief asked for: breeder, licensor, licensee, nursery, grower,
marketer, retailer, regulator, registry, investor, industry body, research institution.

**Recommendation A5** in `priority-actions.md` proposes either adopting this vocabulary or
narrowing the package's roles, so that the warning stream becomes readable.

### 5.2 Claim-attribution heuristic false positives - 4 warnings

The validator warns when a fact classified `claim` has a statement that does not contain one of
`describes|claims|states|says|reports|markets|lists|promotes|positions|characterises|according to`.

Four statements trip the heuristic while being correctly attributed:

- `fact-fruitnet-ozblu-dispute-2020-2` - "United Exports **announced** a five-year South African
  investment plan..."
- `fact-italianberry-peru-varieties-2025-4` - "Trade and market sources **attribute** the Eureka
  brand name..."
- `fact-mbo-history-1` - "Mountain Blue **publishes** two different founding years..."
- `fact-ozblu-migiva-2019-1` - "United Exports **announced** on 25 March 2019 a joint venture..."

Each names the attributing party in its subject position. The verbs `announced`, `attribute` and
`publishes` are simply absent from the heuristic's list. Six other statements that tripped this
check during Wave 2 **were** rewritten, because in those cases the attribution was genuinely
implicit. These four are left as written; rewording them to satisfy a regex would make them less
accurate.

### 5.3 No errors

Zero validation errors. Zero schema violations. Zero broken references.

## 6. Scope deviations, with rationale

The package overshoots four of the brief's target ranges. Each overshoot is a consequence of
following another instruction in the brief, and none is a case of padding.

### 6.1 Organizations: 32 companies against a target of 8-12

The 32 `company` entities are not 32 competitors. Only **9** carry the `competitor` role. The most
frequent roles across the 32, counted from the staged records, are:

`breeder` 9, `competitor` 9, `genetics_licensor` 8, `marketer` 8, `rights_holder` 7, `grower` 6,
`patent_assignee` 5, `packer` 3, `exporter` 3, `genetics_sub_licensor` 3, then a long tail of
single- and double-count roles including `nursery`, `licensing_body`, `government_regulator`,
`plant_breeders_rights_registry`, `public_research_institution`, `extension_publisher`,
`private_equity_investor`, `industry_association` and `ip_advocacy_body`.

Eleven of the 32 are not market participants at all. They are regulators and registries (CFIA, IP
Australia), licensing bodies (Florida Foundation Seed Producers), an IP advocacy body (CIOPORA),
research institutions (University of Florida, University of Arkansas), financial owners (Paine
Schwartz Partners, BCI, Cinven) and administrative or holding entities. Removing them leaves **21**
market participants, still above the 8-12 target but for a defensible reason: the brief requires
role distinctions to be preserved rather than collapsed, and a registry that publishes a variety
record must exist as an entity for that evidence to attach to anything.

### 6.2 Evidence: 121 records against a target of 50-80

Driven directly by the brief's instruction that search-result snippets are not evidence and that
each source must be opened. Every distinct opened source became a record. The alternative would
have been to open fewer sources or to leave opened sources unrecorded, and both are worse.

More evidence strictly improves traceability; it does not dilute anything. 92 of 121 records are
tier-1 primary sources (patents, registries, court records, company primary documents), 27 tier-2,
2 tier-3.

### 6.3 Facts: 186 against a target of 75-150

Driven by the atomicity rule. A single patent front page yields separate facts for the assignee,
the inventor, the grant date, the parentage and each described characteristic, because a compound
statement cannot carry a single confidence value honestly. The count therefore reflects the
granularity rule as much as the breadth of coverage: 186 facts rest on 121 evidence records, an
average of about 1.5 facts per source.

132 are classified `fact`, 54 `claim`. 106 high confidence, 63 medium, 17 low. 10 disputed.

### 6.4 Monitored sources: 121 distinct URLs against a target of 20-30

The brief's "monitored sources" plausibly means recurring sources to watch, not total sources
consulted. Read that way the package is compliant: `next-research-waves.md` proposes **four**
standing monitored sources. The 121 figure is the count of distinct URLs opened, which is the
`source-coverage.csv` denominator.

### 6.5 Offer

If a tighter package is preferred, a trimmed variant can be produced by dropping the
lowest-confidence tier-2 and tier-3 evidence and the facts that depend only on it, which would land
near 80 evidence and 120 facts. **This is not recommended.** It would remove sourced material to
hit a number, and every dropped record would have to reappear in `coverage-gaps.md` anyway.

## 7. Application compatibility

After a trial import into a scratch copy of the repository:

- `scripts/validate_records.py`: `All validated records passed.`
- `pytest`: `28 passed`
- 23 application routes returned HTTP 200, covering all ten entity index pages, five company
  detail pages, four variety detail pages, the corrected Bonita-related patent page, two evidence
  detail pages, `/api/feed` and `/api/search`.
- `/api/feed` returned 124 items after `--approve` (121 staged plus 3 pre-existing).

No pre-existing record was modified. No test fixture was disturbed. The pilot was restricted to
blueberry partly to avoid changing the behaviour of the feed filter tests.

## 8. Known limitations carried into the data

Ten schema limitations are documented in `schema-assessment.md` (L-1 to L-10) with the fallback
representation used for each. The three with the widest reach:

- **L-2:** the relationship schema has no confidence field, so all 204 relationships encode it as a
  mandatory `confidence=<low|medium|high>; ` prefix in `notes`. This is a string convention that
  nothing enforces.
- **L-4:** claimed traits live in `variety.attributes.traits[]` with per-trait `provenance` and
  `evidence_ids`. Nothing in the application reads this yet.
- **L-7:** signals have no schema, so the six staged signals are excluded from import.

No production schema was modified, and no unsupported field was invented in any importable record.
