# Company + Genetics Relationships V1 — data contract

**Status:** Data-layer only. No UI was built in this mission — the visual
Landscape page that will eventually render this data is owned separately
(see `feature/competitor-landscape-v1`, an explicitly excluded branch for
this mission). This document is that page's data contract: what exists,
where it lives, and how to read it correctly.

**Branch:** `feature/company-genetics-relationships-v1`
**Base:** `bd96fca1231dc97ae4ec3fc316743b0a3f2e8427`
**Source material:** one competitor-registry spreadsheet screenshot (33
data rows) and five handwritten-note images, both provided directly by the
operator and imported as-is — not independently verified market research.

## 1. What this mission is and is not

- **Is:** a reconciled, honest representation of a 33-company internal
  competitor registry inside the existing Entity/Relationship/Evidence
  graph, plus a small set of pending-review company↔genetics-provider
  relationships transcribed from handwritten notes.
- **Is not:** a new trust object, a new review queue, a UI, a completeness
  claim, or externally-verified research. Every classification in the
  snapshot is exactly what the operator's own spreadsheet/notes say —
  never independently confirmed, never upgraded to trusted Evidence, and
  never presented as market research the way `data/imports/*/benchmark.json`
  recall audits (a different, externally-grounded mission) are.

## 2. Where the data lives

```
data/imports/competitor-registry-2026-09-15/
  snapshot.json                 -- the 33-row registry as transcribed (source of
                                    truth for competitor_type/priority/regions/tier)
  reconciliation-matrix.json    -- 33 rows: label -> canonical entity + resolution
                                    status + monitoring state (regenerated live by
                                    app/services/competitor_registry.py at read time
                                    for entity/monitoring fields; classification
                                    fields are frozen historical record)
  genetics-transcription.json   -- every handwritten row, seeded or withheld, with
                                    a stated reason either way
  unresolved-mapping-queue.json -- just the withheld rows, for a human review pass

data/entities/companies/company-<new>.json   -- 17 new roster entities, status="unverified"
data/evidence/ev-competitor-registry-2026-09-15-import.json          -- spreadsheet provenance
data/evidence/ev-competitor-genetics-handwritten-notes-2026-09-15.json -- handwritten-notes provenance
data/relationships/rel-*-genetics-*.json     -- 3 seeded, pending-review genetics relationships

app/services/competitor_registry.py -- the read-only service other code should call
```

A **future re-snapshot** (a newer spreadsheet export) creates a new
`data/imports/competitor-registry-<new-date>/` directory. It never
overwrites this one — `app.services.competitor_registry.load_latest_snapshot()`
picks the newest by its own `snapshot_date` field. This is how tier/priority
history survives without a bespoke versioning schema: git history plus a
dated directory per snapshot, the same pattern this codebase's recall-audit
and industry-pulse-qualification imports already use for their own frozen
benchmark files.

## 3. Reading the registry: `app/services/competitor_registry.py`

```python
from pathlib import Path
from app.services.competitor_registry import unfiltered_competitor_registry

rows = unfiltered_competitor_registry(
    data_dir=Path("data"), entities=all_entities, sources=all_sources,
)
# len(rows) == 33, always -- this is the mandatory roster, not a filtered view.
```

Each row combines the **frozen** classification (`competitor_type`,
`strategic_priority`, `regions`, `berry_tier`) from the snapshot with
**live** fields resolved against the current entity graph and Source
registry at call time: `entity_found`, `entity_status`,
`entity_name_current`, `entity_roles_current`, `monitoring_state`,
`monitoring_detail`. A row is *never* dropped for being sparse — a
freshly-added company with zero evidence still appears, with honest blank
fields.

**This is a different filter than Landscape's own "Actors to Watch".**
`app/services/berries/landscape.py`'s `actor_rows` deliberately excludes
any company with `"competitor"` in `roles` but zero signals/evidence/
varieties — correct for that page's "shown because of real activity"
framing, wrong for a mandatory-roster inventory. `unfiltered_competitor_registry()`
does not reuse that filter and does not touch that function; it is a
separate, additive read path over the same underlying entities.

Company↔genetics lookups are bidirectional and reuse the existing generic
`Relationship` record type (no parallel schema):

```python
from app.services.competitor_registry import (
    genetics_relationships_for_company, companies_for_genetics_provider,
)
genetics_relationships_for_company("company-agroberries", relationships=rels, entities=ents)
companies_for_genetics_provider("company-mountain-blue-orchards", relationships=rels, entities=ents)
```

## 4. Trust and review state — read this before wiring any UI

- Every new/updated entity, both Evidence provenance records, and all 3
  genetics relationships are **pending-review by construction**:
  - New entities: `status: "unverified"` (the existing entity.schema.json
    enum value; no new vocabulary).
  - Evidence: `status: "in_review"` (never `"published"` — these must
    never appear in `build_static.py`'s public output or be treated as
    trusted intelligence).
  - Genetics relationships: `status: "disputed"` — the closest existing
    `relationship.schema.json` enum value to "pending human confirmation,"
    reused deliberately rather than adding a new status value. **"Disputed"
    here means "not yet reviewed," not "the parties disagree."** A caller
    rendering relationship status text should say "Pending review," not
    literally "Disputed."
- **Priority vs. tier are separate fields, always.** `strategic_priority`
  (`"Top"` / `"Watch"` / `None`) and `berry_tier` (per-berry) never derive
  from each other — see `test_priority_is_a_separate_dimension_from_tier`.
- **Tier vocabulary:** `tier_1` / `tier_2` / `tier_3` / `present` /
  `unassigned` (blank cell) / `unknown` / `not_applicable`. `present` is
  never coerced to `tier_3`; `unassigned` is never coerced to `unknown` —
  they mean different things (no classification given vs. classification
  attempted and inconclusive) and no row in this snapshot currently uses
  `unknown` or `not_applicable`, but both are supported vocabulary for a
  future snapshot that needs them.
- **Regions are multi-valued, internal, verbatim codes** (`DOTA`,
  `DOA_DANZ`, `DEMEA`) — not mapped onto `data/entities/geographies/*`,
  since these are the operator's own internal market segments, not
  ISO/UN geography names. Do not invent a geography-entity mapping for
  them without operator confirmation.

## 5. Genetics relationships actually seeded (3 of 22 transcribed rows)

| Relationship | Predicate | Confidence | Source |
|---|---|---|---|
| AgroBerries → Mountain Blue Orchards | `partners_with` | medium | Tier 1 note |
| Agrovision (Fruitist) → Fall Creek Farm & Nursery | `partners_with` | medium | Tier 1 note (also names "Sekoya," an existing Fall Creek-linked source label, not a separate entity) |
| California Giant Berry Farms → Fall Creek Farm & Nursery | `partners_with` | medium | Tier 3 note |

All three use the generic `partners_with` predicate rather than a more
specific one (`licenses`/`grows`/`uses`) because **the handwritten note
does not state which specific relationship type applies** — the exact
scenario the mission brief's "uses / unknown association" category
describes, and forcing a more specific predicate than the evidence
supports would overstate the assertion. The specific nature (owns /
licenses / grows / uses) is left for a human reviewer to confirm before
this moves out of `status: "disputed"`.

**19 of 22 transcribed handwritten rows were deliberately withheld** —
self-mappings (a company naming itself, e.g. "Planasa — Planasa,"
suggesting proprietary genetics but never auto-converted to an `owns`
relationship per the mission's own explicit rule), explicit `??`/`???`
markers, one illegible company name, "public genetics" observations
(not a company-to-company relationship — no entity exists to point a
relationship at), scoped observations ("No blues" — a berry-specific
absence, not a global one), and names that do not match any of the 33
mandatory roster entries (`Dole`/`Inka Berries`/`Family Tree`/etc. — out
of this mission's mandated scope, not created as new entities). See
`data/imports/competitor-registry-2026-09-15/unresolved-mapping-queue.json`
for the full list with reasons.

## 6. Reconciliation highlights (see reconciliation-matrix.json for all 33)

- **16 existing entities** matched (exact name/alias or a documented
  parent/brand resolution); **17 new entities** created, all
  `status: "unverified"`.
- **Costa** → resolved to `company-costa-group-holdings` (the tracked
  parent), not the genetics subsidiary `company-costa-berry-international`
  — documented ambiguity, not a silent merge.
- **Fruitist** → resolved to `company-agrovision`, which already carries
  "Fruitist" as both alias and known brand; no new entity.
- **Ozblu** → resolved to the existing `brand-ozblu` entity (a licensed
  variety platform with 3 real companies already in owns/develops/licenses
  roles toward it), not modeled as a single company.
- **UC Davis** → resolved to `breeding_program-uc-davis-strawberry`
  (entity_type `breeding_program`), not a generic university company
  entity — this graph's existing convention for UC Davis specifically.
  University of Arkansas / University of Florida remain `entity_type:
  "company"`, matching *their* pre-existing convention; this mission did
  not retroactively unify the two conventions.
- Public/university entities (UC Davis, University of Arkansas, University
  of Florida) deliberately did **not** get the `"competitor"` role added,
  even though the spreadsheet tracks them competitively — that role feeds
  Landscape's own Actors-to-Watch filter, and tagging a research
  institution as a market "competitor" there would be a real, unintended
  side effect on an out-of-scope feature. This registry's own service does
  not depend on that role at all.

## 7. Monitoring / source-coverage state (see `monitoring_state_for_entity`)

Computed live, never fabricated:

| State | Meaning | Count in this roster (as of 2026-09-15) |
|---|---|---|
| `source_configured_never_run` | A discovery-eligible Source links this entity but has never run | 8 (Advanced Berry Breeding, BerryWorld, Costa, Fall Creek, Hortifrut, Planasa, University of Arkansas, University of Florida) |
| `source_blocked` | A diagnosed, cited acquisition block | 1 (California Giant — see `fix/astra-news-reader`, commit 721a20a) |
| `no_supported_source` | No linked Source at all; none researched or fabricated | 24 (the rest of the roster, including all 17 new entities) |

No entity in this roster currently reports `linked_to_runnable_source`,
`discovery_pending`, or `manual_monitoring_required` — an honest reflection
of this snapshot, not a code limitation (all six states are real,
recognized vocabulary in `MONITORING_STATES`).

## 8. What a future Landscape UI mission should and should not do with this

- **Should:** call `unfiltered_competitor_registry()` for a "full roster"
  view distinct from the existing filtered "Actors to Watch"; render
  `monitoring_state`/`monitoring_detail` honestly (never as a recall or
  completeness claim, per this codebase's Source Health rule); render
  `status: "disputed"` genetics relationships as "Pending review," not as
  confirmed fact.
- **Should not:** invent a blended competitive-strength/tier score across
  berries; auto-promote a `status: "unverified"` entity or a `status:
  "disputed"` relationship to trusted without an explicit human review
  step; assume `regions` codes map onto any existing geography entity;
  treat a `no_supported_source` company as "no competitive activity" (only
  "we have not captured anything about it yet").
