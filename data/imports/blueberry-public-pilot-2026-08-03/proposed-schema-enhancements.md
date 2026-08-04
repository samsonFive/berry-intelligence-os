# Proposed Schema Enhancements

Every proposal below is **backward-compatible**: existing records continue to validate, and
the 28 existing tests continue to pass. Nothing here has been applied. These are proposals for
human decision, kept deliberately separate from the import package so that adopting the data
does not require adopting the schema changes.

Ordered by how much they cost you to keep living without.

---

## P-1 — Berry entity records (fixes A-3) · priority: high · effort: trivial

`berry` is already a legal `entity_type`, `berry_ids` are referenced by every record type, and
`ENTITY_FOLDER_OVERRIDES` already maps `berry → berries`. But no berry entity record exists —
the four berries live in a hard-coded `BERRIES` dict in `app/main.py`. Every `berry_ids` entry
in the repository today is a dangling reference, which directly contradicts ADR-0001
("JSON is authoritative").

**Change:** add `data/entities/berries/berry-{blueberry,raspberry,strawberry,blackberry}.json`
and change `BERRIES` to derive from them, falling back to the hard-coded dict if the folder is
empty.

This package **includes** `entities/berries/berry-blueberry.json` so the fix can be adopted
incrementally.

---

## P-2 — Relationship predicate additions (fixes L-4, L-5, L-8) · priority: high · effort: low

The current 10-value enum cannot express three relationships the domain genuinely needs, and
the substitutions this package was forced to make are lossy.

Add to `relationship.schema.json` `predicate`:

| Predicate | Subject → Object | Replaces the lossy fallback |
|---|---|---|
| `exhibits_claimed_trait` | variety → trait | L-4: no representation at all today |
| `protects` | patent → variety | L-5: no representation at all today |
| `markets` | company → variety/brand/product | L-8: currently squeezed into `sells` |
| `offers` | nursery → variety | L-8: currently squeezed into `distributes` |
| `administers_license_for` | company → variety | currently indistinguishable from `licenses` |
| `subsidiary_of` | company → company | currently indistinguishable from `owns` |

Purely additive to an enum — no existing record becomes invalid.

The distinction that matters most commercially is `licenses` vs `administers_license_for`.
A genetics owner licensing its own variety and a third party administering someone else's
licence program are very different market positions, and today they are the same edge.

---

## P-3 — Relationship confidence (fixes L-2) · priority: high · effort: trivial

```json
"confidence": {"enum": ["low", "medium", "high"]}
```

Optional, so existing records stay valid. Facts already carry confidence; relationships being
the one edge type without it is an inconsistency, and it forces confidence into free-text
`notes` where nothing can query it.

---

## P-4 — Evidence source quality and dates (fixes L-1, L-3, A-5, A-7) · priority: high · effort: low

Add to `evidence.schema.json`, all optional:

```json
"source_tier":        {"enum": ["tier_1_primary", "tier_2_specialist", "tier_3_corroborating", "low_authority"]},
"information_confidence": {"enum": ["low", "medium", "high"]},
"event_date":         {"type": ["string", "null"], "format": "date"},
"author":             {"type": "string"},
"geography_ids":      {"type": "array", "items": {"type": "string"}},
"provenance_notes":   {"type": "string"},
"attachments":        {"type": "array", "items": {"type": "object"}}
```

`source_tier` is the important one. The brief's entire source hierarchy (§6) currently has
nowhere to live, and "do not use low-authority sources as the sole support for material facts"
is unenforceable without it — this package encodes tier in `tags`, where it is a string among
unrelated strings.

`event_date` closes the §7 requirement to distinguish when something *happened* from when it
was *reported*. In blueberry intelligence this gap is routinely a full season: a licensing
agreement signed in one hemisphere's winter is often reported at the next northern trade show.

`attachments` is not new behaviour — it documents what `review_publish()` already writes (A-8).

Also recommended: give `source_type` a real enum (A-5), seeded with the seven values already in
use, and make `source_url` `"format": "uri"` (A-7).

---

## P-5 — Trait provenance on facts (fixes L-6) · priority: high · effort: low

`fact.classification` has two values, `fact` and `claim`. That is enough to stop marketing
language becoming truth — the single most important discipline in this domain — but not enough
to distinguish a measured trial result from a trade-press repetition of a press release.

**Option A (preferred, additive):** keep `classification` as-is, add optional

```json
"evidence_basis": {"enum": [
  "owner_or_marketer_claim",
  "named_trial_measurement",
  "independent_report",
  "regulatory_or_registry_record",
  "analyst_inference",
  "unresolved"
]}
```

**Option B:** widen `classification` itself. Not recommended — it would change the meaning of
existing records and the review UI's two-value dropdown.

This package preserves the full six-way distinction inside
`variety.attributes.traits[].provenance`, where it is unqueryable. Option A would make the
testing queue (Milestone 4) able to ask the question that actually matters: *which varieties
have measured trial data rather than catalog copy?*

---

## P-6 — Strategic question schema (fixes A-1, L-9) · priority: medium · effort: trivial

`data/strategic-questions/` holds a real record that nothing validates. Add
`schemas/strategic-question.schema.json` matching the existing record exactly, and add the
folder to `scripts/validate_records.py`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "strategic-question.schema.json",
  "title": "Strategic Question Record",
  "type": "object",
  "required": ["id", "record_type", "title", "status"],
  "properties": {
    "id": {"type": "string", "pattern": "^sq-[a-z0-9-]+$"},
    "record_type": {"const": "strategic_question"},
    "title": {"type": "string", "minLength": 1},
    "description": {"type": "string"},
    "status": {"enum": ["active", "answered", "retired"]},
    "berry_ids": {"type": "array", "items": {"type": "string"}},
    "evidence_ids": {"type": "array", "items": {"type": "string"}},
    "fact_ids": {"type": "array", "items": {"type": "string"}}
  }
}
```

Zero migration: the one existing record already conforms.

---

## P-7 — Signal schema (fixes L-7, A-2) · priority: medium (high before Milestone 4) · effort: medium

Signals are in the domain model and in Milestone 4, but have no representation. The brief
requires them with sixteen specific fields. This package stages six proposed signals in
`signals/` as **non-importable** JSON pending this schema.

Proposed `schemas/signal.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "signal.schema.json",
  "title": "Signal Record",
  "type": "object",
  "required": ["id", "record_type", "title", "hypothesis", "status",
               "evidence_ids", "strength", "confidence", "first_observed", "last_reviewed"],
  "properties": {
    "id": {"type": "string", "pattern": "^sig-[a-z0-9-]+$"},
    "record_type": {"const": "signal"},
    "title": {"type": "string", "minLength": 1},
    "hypothesis": {"type": "string", "minLength": 1},
    "status": {"enum": ["proposed", "monitoring", "confirmed", "refuted", "retired"]},
    "fact_ids": {"type": "array", "items": {"type": "string"}},
    "evidence_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2},
    "entity_ids": {"type": "array", "items": {"type": "string"}},
    "berry_ids": {"type": "array", "items": {"type": "string"}},
    "geography_ids": {"type": "array", "items": {"type": "string"}},
    "strategic_question_ids": {"type": "array", "items": {"type": "string"}},
    "first_observed": {"type": "string", "format": "date"},
    "last_reviewed": {"type": "string", "format": "date"},
    "strength": {"enum": ["weak", "moderate", "strong"]},
    "confidence": {"enum": ["low", "medium", "high"]},
    "counterevidence": {"type": "string"},
    "unresolved_questions": {"type": "array", "items": {"type": "string"}},
    "strategic_relevance": {"type": "string"},
    "next_monitoring_action": {"type": "string"},
    "reviewer": {"type": "string"}
  }
}
```

Two deliberate constraints worth keeping: `evidence_ids` has `minItems: 2`, enforcing the
brief's rule that a signal is a *pattern* rather than a single announcement; and `confirmed`
exists in the enum but this package uses only `proposed` and `monitoring`, per §12.

---

## P-8 — Assessment and recommendation records · priority: low (defer) · effort: medium

The domain model declares both. `DOMAIN-MODEL.md` requires the published lineage
`Recommendation → Assessment/Signal → Facts → Evidence → Source`, and that chain is currently
**unbuildable** — two of its five links have no schema.

Recommend deferring until Milestone 4 is scoped, with one caveat: the four `priority` dimensions
on evidence are already a recommendation mechanism, and if they remain the only one, the
domain model's `Recommendation` object should be formally retired rather than left as an
unimplemented promise. Choosing deliberately between "build it" and "drop it" is worth more
than leaving it ambiguous.

---

## P-9 — Controlled vocabulary for entity roles (fixes A-6) · priority: medium · effort: low

`entity.roles[]` is free strings, but brief §4 depends on role distinctions being reliable, and
`"Do not classify every organization simply as 'competitor'"` is unenforceable against free
text. Seed data already uses five values informally.

Proposed vocabulary, drawn from brief §4 and used consistently throughout this package:

`breeder`, `genetics_owner`, `nursery`, `propagator`, `license_administrator`, `marketer`,
`grower_shipper`, `exporter`, `importer`, `cooperative`, `branded_berry_company`,
`research_institution`, `university_breeding_program`, `retailer`, `distributor`, `packer`.

Implement as a `$defs` enum referenced by `roles.items`, or keep as documentation first and
tighten once the vocabulary has survived a few research waves. The seed value
`genetics_provider` should be reconciled with `genetics_owner` — they currently mean the same
thing under two names.

---

## P-10 — Entity ID prefix validation (fixes A-9) · priority: low · effort: trivial

Add to `scripts/validate_records.py`: assert `entity["id"].startswith(entity["entity_type"] + "-")`.

Today a mismatch produces a silent 404 on the entity page rather than a validation failure,
because `entity_detail()` matches on both `entity_type` and `entity_id`. Cheap to check, and it
fails loudly instead of quietly.

---

## P-11 — A real importer · priority: high · effort: medium

Not a schema change, but the biggest structural gap. There is no way to bring a curated,
externally-produced dataset into the repository. The review UI is single-record, human-driven,
caps at 3 facts and 2 relationships per evidence item, links facts to *all* entities on the item
rather than their own subjects (A-10), and cannot set entity descriptions, aliases, roles, or
attributes at all.

`scripts/import_package.py` in this package is a working reference implementation:
`--dry-run` / `--apply` / `--approve`, all-or-nothing writes, referential integrity checks
against both package and repository, and no writes into `data/` until validation passes.
Promoting something like it into `scripts/` would make every future research wave a
one-command operation.

Suggested addition to `scripts/validate_records.py`: also scan `data/imports/*/` so staged
packages are covered by the repository's own validator rather than needing their own.
