# Refine Profile Completeness Semantics V1

**Status:** Service/audit/test/documentation refinement only. No UI was
built or modified; no canonical data (entities, relationships, aliases,
tiers, priorities, regions, genetics relationships, Source records,
acquisition outcomes, application inbox data) was changed.

**Branch:** `fix/profile-completeness-semantics-v1`
**Base:** `516f1ee74a369fb59e0563341a0b9d75da6edf9e` (Competitor Profile Data
Service V1's completed, published checkpoint)
**Verification date:** 2026-09-15

## 1. The problem this fixes

The prior model (`app.services.competitor_profile.profile_completeness()`,
first version) reported 10 flat dimensions as `present`/`missing`/
`not_applicable` and summarized the roster as **"Complete profiles: 0/33"**.
That single number was **honest about the underlying data** but
**misleading about what "incomplete" meant**: it silently conflated eight
materially different situations behind one word, `missing`:

1. A required field literally absent from the record (a real defect).
2. A berry position legitimately Unknown/Unassigned (not a defect).
3. A value explicitly marked Not Applicable (not a defect — was even
   already distinguished from `missing`, but shared the same *counting*
   bucket as genuine gaps once rolled into `present_count`/`applicable_count`).
4. A provisional (`unverified`) identity awaiting confirmation (a
   verification task, not a malformed record).
5. An open duplicate/structural-review finding (an identity task, not a
   malformed record).
6. No Source configured for an entity yet (an operational setup gap).
7. A configured Source that has never successfully run (an operational
   readiness gap).
8. No current usable coverage window (an acquisition/collection gap).

A reader of "0/33 complete" had no way to tell "this profile is broken"
from "this profile is honestly showing an Unknown/Unassigned berry slot
and hasn't been monitored yet" — both looked identical: `missing`. This
mission separates those into **7 independent concerns**, none of which can
fail another, so a genuine structural defect is never hidden by (and never
hides) a legitimate uncertainty or operational gap.

## 2. The 7 concerns

`app.services.competitor_profile.profile_completeness(profile, *,
entities_by_id)` returns exactly these seven top-level keys plus `note`:

| # | Key | Question it answers | Can it ever block stakeholder display? |
|---|---|---|---|
| 1 | `record_integrity` | Is this profile itself structurally sound? | **Yes** — the only concern that can |
| 2 | `classification_coverage` | What do we know about berries/priority/regions/type? | No |
| 3 | `identity_verification` | How sure are we WHO this entity is? | No |
| 4 | `relationship_knowledge` | Do we know this entity's genetics/parent-brand/variety relationships? | No |
| 5 | `monitoring_maturity` | Is discovery SET UP for this entity? | No |
| 6 | `current_intelligence_coverage` | Do we currently HAVE usable acquired content? | No |
| 7 | `actionable_gaps` | A structured, triaged list of everything above that is not fully resolved | Each gap carries its own `blocks_stakeholder_display` |

### 2.1 Record integrity (`record_integrity`)

```python
{
  "status": "structurally_valid" | "missing_required_data" | "invalid_reference",
  "checks": [ {"check": str, "passed": bool, "category": str, "detail": str}, ... ],
  "failed_checks": [ ... subset of checks where passed is False ... ],
  "note": "...",
}
```

Nine checks, each blind to classification/identity/monitoring *content*:
`canonical_entity_id_present`, `display_name_present`,
`entity_type_present`, `roster_resolves_to_entity`,
`canonical_reference_not_retired`, `all_four_berry_slots_present`,
`classification_snapshot_valid`, `relationship_references_valid`,
`profile_route_present`, `filtered_landscape_routes_present`.

**Explicitly, per this mission's own rule:** *"A berry slot containing
Unknown/Unassigned still counts as structurally present. An unassigned
strategic priority is not automatically a malformed record."*
`all_four_berry_slots_present` checks that all four berry **keys** exist in
`classification.berry_tier` — never their values. A `Top`/`Watch`/`None`
strategic priority never appears in this block at all; it lives in
`classification_coverage` (§2.2), which cannot fail integrity.

`status` is `invalid_reference` if any `invalid_reference`-category check
fails (a dangling/retired reference — the most severe class), else
`missing_required_data` if any `missing_required_data`-category check
fails (a required field literally absent), else `structurally_valid`.

### 2.2 Classification coverage (`classification_coverage`)

```python
{
  "berry_positions": {
    "strawberry": {"raw": "unassigned", "display": "Unknown/Unassigned", "state": "unknown_unassigned"},
    "blueberry":  {"raw": "tier_1",     "display": "Tier 1",             "state": "assigned"},
    "raspberry":  {...}, "blackberry": {...},
  },
  "berry_summary": {"assigned": 1, "unknown_unassigned": 3, "not_applicable": 0},
  "strategic_priority": {"raw": "Top", "display": "Top", "state": "assigned"},
  "regions": {"assigned": ["DOTA"], "state": "assigned"},
  "competitor_types": {"assigned": ["Commercial"], "state": "assigned"},
  "has_unassigned": true,
  "note": "...",
}
```

Every berry is evaluated **independently** from its own raw snapshot
value only — `berry_positions["blueberry"]` never looks at
`berry_positions["strawberry"]`, per the mission's explicit *"Never infer
one berry from another"* rule. `display`/`state` reuse
`app.services.competitor_landscape.normalize_tier_status` (the same
normalizer the `/competitors` page itself uses) so a profile's berry
labels can never drift from what the landscape grid shows for the same
entity. `Unknown/Unassigned` and `Not Applicable` are always distinct
`state` values — never conflated with each other or with
`missing_required`.

> **Known, out-of-scope, pre-existing quirk:** `normalize_tier_status`
> (in `competitor_landscape.py`, a file every mission in this chain is
> instructed never to modify) recognizes `"not applicable"`, `"n/a"`, and
> `"na"` as Not Applicable, but **not** `"not_applicable"` (underscore) —
> that spelling falls through unchanged and would display as `"assigned"`.
> No real snapshot row uses any Not-Applicable spelling today, so this
> never triggers in production data; a future snapshot author should use
> `"n/a"` or `"not applicable"`, matching this normalizer's own alias
> table. Fixing the normalizer itself is out of scope for this mission
> (see `competitor_landscape.py`'s do-not-modify convention).

### 2.3 Identity verification (`identity_verification`)

```python
{"state": "active_verified" | "provisional" | "pending_duplicate_review" | "invalid_canonical_reference",
 "reason": "..."}
```

The same 4-value state also lives on `profile["identity"]["verification_state"]`
/`verification_state_reason"`, computed by
`_identity_verification_state()`:

1. `invalid_canonical_reference` — the roster row's `canonical_entity_id`
   resolves to no entity at all, **or** resolves to a retired/merged
   record instead of its living survivor (checked via
   `entity_identity.is_retired_entity`/`redirect_map`/`merged_into_id`
   against `data/configuration/entity-identity-redirects.json`, the same
   mechanism every other identity-aware service in this codebase reads).
   This is the only identity state that also makes `record_integrity`
   fail (`canonical_reference_not_retired`/`roster_resolves_to_entity`) —
   the two concerns describe the same underlying fact and never disagree.
2. `pending_duplicate_review` — `entity_identity.audit_entity_identity`
   flags an **unresolved** finding (not an already-decided
   `explicit_redirect`) touching this entity id.
3. `provisional` — `entity.status == "unverified"`. *"A provisional
   identity is a verification gap, not necessarily a malformed profile"* —
   `record_integrity` is unaffected.
4. `active_verified` — entity status is settled (`active`/`inactive`/
   `historical`) with no open review.

Reused, not reinvented: this is the entity schema's own `status` enum
(`active`/`inactive`/`historical`/`unverified`) wherever it already
answers the question, plus the two concepts that enum cannot express.

### 2.4 Relationship knowledge (`relationship_knowledge`)

```python
{
  "genetics_known": false, "genetics_state": "absent_optional",
  "verified_variety_relationships_known": false, "verified_variety_relationships_state": "absent_optional",
  "parent_brand_relationships_known": true, "parent_brand_relationships_state": "assigned",
  "note": "...",
}
```

Absence here (`absent_optional`) means "not yet known" — genetics,
verified-variety, and parent/brand relationships are never required for
`record_integrity`, since a real Relationship simply may not exist yet.

### 2.5 Monitoring maturity (`monitoring_maturity`)

```python
{"entity_represented": true, "discovery_configured": false, "discovery_operational": false,
 "linked_source_count": 0, "runnable_source_count": 0,
 "state": "not_configured" | "configured_not_operational" | "configured_and_operational", "note": "..."}
```

Whether discovery is **set up** — deliberately blind to whether current
news exists (that is §2.6). Sourced from
`competitor_registry.monitoring_maturity_for_entity`'s own
`entity_represented`/`discovery_configured`/`discovery_operational` facts,
unchanged.

### 2.6 Current intelligence coverage (`current_intelligence_coverage`)

```python
{"readable_content_acquired": false, "current_coverage_available": false,
 "current_usable_coverage_count": 0, "official_source_blocked": true,
 "official_source_block_detail": "...", "manual_or_alternative_source_required": true,
 "state": "no_readable_content" | "readable_but_not_current" | "current", "note": "..."}
```

Whether we currently **have** usable content — *"No current coverage is an
operational intelligence gap, not a profile-schema failure"*. Sourced from
the same `monitoring_maturity_for_entity` facts as §2.5, split out because
the mission names them as two separate concerns.

### 2.7 Actionable gaps (`actionable_gaps`)

A list of structured objects, each:

```python
{
  "dimension": "berry_position:strawberry",       # what this gap is about
  "state": "unknown_unassigned",                  # one of FIELD_STATES (see §3)
  "category": "informational_uncertainty",        # one of GAP_CATEGORIES (see §3)
  "severity": "informational",                    # blocking | attention | informational
  "why_it_matters": "...",
  "recommended_next_action": "...",
  "owning_workflow": "Analyst classification pass",
  "source_provenance": "internal_competitor_registry_spreadsheet, snapshot_date=2026-09-15",
  "blocks_stakeholder_display": false,
}
```

**Only a `record_integrity` failure ever sets `blocks_stakeholder_display=True`**
(`category` is then `missing_required_data` or `invalid_data`, `severity`
is `blocking`) — per the mission's explicit *"Only genuine integrity
errors should block profile rendering"* rule. Every other gap (Unknown/
Unassigned classification, a provisional identity, an unconfigured
source, zero current coverage) is real, reported, and traceable, but never
blocks rendering.

### UI-contract fields (`ui_flags`) — data only, no UI built

```python
{
  "profile_structurally_valid": true,
  "classification_incomplete_or_unassigned": true,
  "identity_provisional": false,
  "monitoring_not_configured": true,
  "coverage_unavailable": true,
  "action_required": true,
}
```

Six concise booleans for a future drill-down surface, exactly the set the
mission named. **No route, template, or UI was built or modified by this
mission** — these are plain data on the returned dict.

## 3. Vocabulary

Adapted to existing repository conventions wherever one already exists;
invented only where nothing already represents the concept.

**`INTEGRITY_STATES`** (new — nothing in the repo modeled "is this
record's own shape sound", as distinct from entity lifecycle):
`structurally_valid`, `missing_required_data`, `invalid_reference`.

**`IDENTITY_VERIFICATION_STATES`** (reuses the entity schema's `status`
enum wherever possible): `active_verified`, `provisional`,
`pending_duplicate_review`, `invalid_canonical_reference`.

**`FIELD_STATES`** (new, generic, reused across classification coverage,
relationship knowledge, and monitoring/coverage `state`-style fields —
equivalent to the mission's own listed vocabulary):
`assigned` (known/assigned), `unknown_unassigned`, `not_applicable`,
`pending_verification`, `unsupported_for_entity_type`, `absent_optional`,
`missing_required`, `invalid_or_inconsistent`.
(`unsupported_for_entity_type` exists in the vocabulary for a future
entity type where a dimension genuinely does not apply — brand and
breeding_program, the two non-company types in today's roster, do not
currently need it; see §4.)

**`GAP_CATEGORIES`** (new, distinguishes analyst/ops/engineering work from
benign uncertainty, per the mission's own list): `informational_uncertainty`,
`analyst_classification_work`, `identity_verification`,
`source_configuration`, `acquisition_failure`, `missing_required_data`,
`invalid_data`.

**`GAP_SEVERITIES`**: `blocking`, `attention`, `informational`.

## 4. Non-company entity applicability

Ozblu (`brand`) and UC Davis (`breeding_program`) are proven, via a
focused test (`tests/test_profile_completeness_semantics_v1.py::test_non_company_entity_types_get_correct_applicability`),
to receive `record_integrity.status == "structurally_valid"` and no
`entity_type`-driven check failure — entity_type never degrades or
special-cases any of the 9 integrity checks. Every underlying call this
service composes (`monitoring_maturity_for_entity`,
`genetics_relationships_for_company`, `_company_portfolio_roles`) already
accepted any entity id regardless of type (established by Competitor
Profile Data Service V1); this mission adds no new entity_type branching.

## 5. Roster summary (`profile_roster_summary`)

`app.services.competitor_profile.profile_roster_summary(profiles: list[dict])`
replaces the old single "Complete profiles: N/33" metric with a
multidimensional tally — never collapsed into one opaque percentage:

```python
{
  "profiles_returned": 33,
  "structurally_valid": 33,
  "missing_required_data": 0,
  "invalid_reference": 0,
  "unassigned_internal_classification": 32,
  "provisional_identity": 9,
  "lacking_genetics_information": 18,
  "no_configured_sources": 25,
  "no_operational_discovery": 33,
  "no_readable_coverage": 33,
  "no_current_usable_coverage": 33,
  "blocking_profile_defects": 0,
  "note": "...",
}
```

Audited across all 33 roster entries at
`data/imports/profile-completeness-semantics-2026-09-15/profile-completeness-semantics-audit.json`
(this mission's own dated import directory — the prior mission's
`data/imports/competitor-profile-data-2026-09-15/profile-completeness-audit.json`
is left untouched, per this codebase's convention that a re-modeled audit
gets a new dated directory rather than overwriting history).

**33/33 structurally valid, 0 missing required data, 0 invalid references,
0 blocking profile defects** — the roster's real, honestly-reported
classification/identity/monitoring gaps (32 profiles with at least one
Unknown/Unassigned classification, 9 provisional identities, 18 lacking
genetics information, 25 without a configured source, all 33 without
current usable coverage as of this snapshot) are visible in full, and none
of them degrade the structural-validity count.

## 6. What a future UI-adoption mission should do

- Read [`COMPETITOR-PROFILE-DATA-V1.md`](./COMPETITOR-PROFILE-DATA-V1.md)
  first for the base view-model contract (unchanged by this mission).
- Render each of the 7 concerns as visually distinct — never collapse
  `classification_coverage.has_unassigned`, `identity_verification.state
  != "active_verified"`, or a `monitoring_maturity`/
  `current_intelligence_coverage` gap into the same badge as a
  `record_integrity` defect. Use `ui_flags` for simple badge logic rather
  than re-deriving these booleans.
- Only ever treat a profile as "broken"/non-renderable when
  `record_integrity.status != "structurally_valid"` (equivalently: any
  `actionable_gaps` entry has `blocks_stakeholder_display: true`). Every
  other gap is real and worth surfacing, but must render normally.
- Use `profile_roster_summary()` for any roster-level dashboard number —
  never re-derive a single "X% complete" figure independently.
