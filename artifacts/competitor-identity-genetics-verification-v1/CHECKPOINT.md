# Competitor Identity and Genetics Verification V1 — checkpoint (2026-09-15)

Branch: `research/competitor-identity-genetics-verification-v1` in
`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-competitor-identity-genetics-verification-v1`,
based on `origin/integration/competitor-intelligence-v1` at exact SHA
`031c9b6a80bd72ce3f271933d8a1ea302decb077`. Bounded canonical-data trust
mission. No merge, push, deploy, collection, or source activation
performed.

## What was verified and changed

### Scope A — 17 provisional identities
All 17 derived programmatically from the reconciliation matrix (not
memory) — see `data/imports/competitor-identity-genetics-verification-2026-09-15/provisional-identity-verification-matrix.json`.

- **8 promoted `unverified` -> `active`** (existing entity.schema.json
  vocabulary, no new status invented): Australasian Plant Genetics, Fresh
  Forward, Oishii, Pairwise, Perfection Fresh, Royakkers, Smart Berries,
  SunBelle. Each has an official primary-source domain, a clear
  single-organization identity, and no unresolved parent/child ambiguity.
- **9 retained provisional**, each with a stated reason: AgroBerries and
  Gem-Pack Berries and Well-Pict (real, well-documented companies, but
  each entangled in a real, unresolved corporate-affiliation question —
  AgroBerries/BerryWorld "family of companies" marketing language, and a
  possible Gem-Pack/Well-Pict merger/affiliation — held pending a primary
  source); Black Venture Farm and The Berry Collective (identity itself
  insufficiently verified / genuinely ambiguous — the latter has at least
  4 unrelated real-world organizations sharing its exact name); Denning
  Blueberries (not found at all, after two independent search passes
  across two missions); Expoberries and Splendor Produce (existence
  corroborated by government/trade-association sources, but no primary
  company-owned website found); Marionnet (real per US patent filings, but
  current legal identity unclear after a 2018 acquisition).
- Every one of the 17 (promoted or not) carries a new
  `attributes.identity_verification_2026_09_15` block with verdict,
  reason, evidence URLs, confidence, and verification date — even the
  ones left unpromoted, so the research is preserved either way.
- 12 real aliases added across the 17 (e.g. "APG", "Fresh Forward Breeding
  B.V.", "Pairwise Plants", "Sun Belle").

### Scope B — duplicate / structural identity review
Investigated all 10 named pairs. Result:
`data/imports/competitor-identity-genetics-verification-2026-09-15/duplicate-structural-identity-review.json`.

- **Planasa / Planasa-2 / Plantas de Navarra: RESOLVED, already fixed
  before this mission.** Discovered `data/configuration/entity-identity-redirects.json`
  — the repository's existing, real, non-destructive duplicate-resolution
  mechanism this mission was asked to look for — already recorded
  `company-planasa-2` as a confirmed duplicate of `company-planasa`,
  decided 2026-09-01. Re-ran the existing
  `app.services.entity_identity.audit_entity_identity()` auditor against
  the full 69-company graph: this is the **only** confirmed duplicate in
  the entire graph (zero exact_duplicates, alias_collisions, or
  unresolved_probable_duplicates otherwise). "Plantas de Navarra, S.A." is
  not a third entity — it is `company-planasa`'s own registered legal
  name. Corrected a stale ambiguity note in the reconciliation matrix that
  had been written without checking this file.
- The other 9 named pairs (Mountain Blue/MBO, Hortifrut/Hortifrut
  Genetica, California Giant/Giant, Ozblu/Mountain Blue, Plant Sciences,
  Fruitist/Agrovision, UC Davis institution/program, university/public
  generally, brand-vs-independent-row) were all confirmed to be **already
  correctly modeled** — real aliases, real company/brand distinctions, or
  a deliberate program-vs-institution choice — no duplicate, no action
  needed beyond documenting the confirmation and, where relevant, adding
  new corroborating evidence.

### Scope C — 3 seeded genetics assertions
`data/imports/competitor-identity-genetics-verification-2026-09-15/genetics-relationship-evidence-assessment.json`.

- **AgroBerries <-> Mountain Blue Orchards: UPGRADED.** FreshFruitPortal.com
  (2026-06-24) independently and explicitly states "AgroBerries Group has
  signed new licensing agreements with Mountain Blue Orchards (MBO) to
  grow and market their blueberry genetics." Predicate `partners_with` ->
  `licenses`; status `disputed` -> `active`; confidence `medium` -> `high`;
  a new Evidence record added (`ev-agroberries-mountain-blue-licensing-freshfruitportal-2026`)
  alongside — not replacing — the original handwritten-notes evidence.
- **Fruitist/Agrovision <-> Fall Creek: RETAINED PENDING**, unchanged.
  Search found no independent corroboration; the relationship's own notes
  now document that a search was attempted, per the mission's rule that
  absence of evidence does not disprove a handwritten assertion.
- **California Giant <-> Fall Creek: RETAINED PENDING**, unchanged, same
  treatment; search surfaced only Cal Giant's separately-tracked
  VentureFruit partnership, which is neither confirming nor disconfirming.

### Scope D — 19 withheld handwritten mappings
`data/imports/competitor-identity-genetics-verification-2026-09-15/withheld-mapping-review-update.json`.
All 19 reclassified into the mission's 8 categories. **Zero promoted to a
seeded relationship.** Two rows (Perfection Fresh, Well-Pict) moved into
"identity clarified but relationship still unverified" now that this
mission's Scope A work confirms those companies' own identities — but
their genetics-provider side remains an explicit author-marked `??`/`???`,
so nothing can be seeded regardless.

### Scope E — variety connections
None added. No new Variety entity or relationship was created; no
candidate-variety queue entry was added either — no authoritative evidence
this mission found named a specific variety alongside a company/program
and a relationship type at the bar this mission requires.

## Verification

- Focused: `tests/test_competitor_identity_genetics_verification_v1.py`
  (30 new tests) + `tests/test_competitor_registry_v1.py` (updated, 2
  assertions revised to reflect the intentional status changes): **65
  passed** (`focused-tests.txt`).
- Broader regression sweep run for safety (not a full-suite run):
  `test_entity_identity_integrity.py`, `test_competitor_intelligence_integration_v1.py`,
  `test_competitor_landscape_v1.py`, `test_company_compare.py`,
  `test_company_portfolio.py`, `test_synthesis_views.py` — **198 passed**
  combined, no regressions from the alias/status changes.
- `scripts/validate_records.py`: **all validated records passed**
  (`record-validation.txt`).
- Full suite was **not** run — Luna owns full-suite validation, per this
  mission's explicit scope.

## What is deliberately unchanged

- No competitor tier, priority, region, or internal competitor-type value
  was changed anywhere (`test_internal_classifications_unchanged`,
  `test_competitor_type_field_unchanged`).
- No Source record, acquisition code, collection execution, or Source
  Health presentation was touched.
- No `/competitors` visual design, Daily Intelligence Briefing prototype,
  or Radar behavior was touched.
- No canonical record was deleted. The one confirmed duplicate
  (Planasa-2) was already non-destructively resolved before this mission
  via the existing redirect mechanism — this mission only corrected a
  stale note about it.
- No Variety entity or relationship was created.

## CANONICAL ROSTER: 33/33 REMAINS REPRESENTED
## INTERNAL TIER/PRIORITY CHANGES: 0
## SOURCE ACTIVATIONS: 0
## LIVE COLLECTION RUNS: 0
## AMBIGUOUS HANDWRITING GUESSED: 0

## Next concrete steps for a follow-up session

1. A human should locate a primary source (official website or corporate
   registry filing) for AgroBerries' claimed "family of companies"
   relationship to BerryWorld, and for the Gem-Pack Berries / Well-Pict
   merger/affiliation question, before either pair's entities are
   promoted or a relationship is added between them.
2. A human should confirm which real-world organization "The Berry
   Collective" roster row actually refers to before any source or
   relationship work targets it.
3. Marionnet's current legal/organizational name (post-2018 Agri Finest
   Company group acquisition) needs a primary-source check.
4. This checkpoint's identity findings are compatible with, and were
   verified not to disturb, the canonical 33-entry landscape, alias
   search, entity/company profile routes, company<->genetics bidirectional
   lookup, and Sol's five-level monitoring model. No further integration
   work should be needed for these specific changes to surface correctly
   in `/competitors`.
