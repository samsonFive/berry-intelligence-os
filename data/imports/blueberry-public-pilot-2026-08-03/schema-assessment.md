# Schema Assessment — Berry Intelligence OS

Assessed: 2026-08-03
Assessed against: repository archive `berry-intelligence-os.zip` as supplied.
Baseline verified before assessment: `python scripts/validate_records.py` → "All validated records passed."; `python -m pytest` → 28 passed.

> **No commit hash available.** The supplied archive contains no `.git` directory, so the
> manifest records `repo_commit: null` and pins provenance to the four schema files' content
> hashes instead. Supply a commit hash if you want the manifest to carry one.

---

## 1. Authoritative artifacts

| Artifact | Path | Role |
|---|---|---|
| Entity schema | `schemas/entity.schema.json` | validated |
| Evidence schema | `schemas/evidence.schema.json` | validated |
| Fact schema | `schemas/fact.schema.json` | validated |
| Relationship schema | `schemas/relationship.schema.json` | validated |
| Validator | `scripts/validate_records.py` | scans 4 fixed folders |
| Loader / ID logic | `app/main.py` | **de facto authority for ID + folder conventions** |
| Domain model | `docs/03-information-architecture/DOMAIN-MODEL.md` | declares 8 object types |
| Architecture | `docs/04-technical-architecture/ARCHITECTURE.md` | Milestone 1–3 notes |

`app/main.py` is treated as co-authoritative with the schemas. Several conventions
(entity ID shape, folder pluralization, fact/relationship ID derivation) exist **only** in
code, not in any schema.

---

## 2. Supported record types

### Fully schema-backed and validated (4)

`entity`, `evidence`, `fact`, `relationship`.

### Present in data but **NOT schema-backed** (1)

`strategic_question` — `data/strategic-questions/sq-premium-flavor.json` exists with
`record_type: "strategic_question"`, but there is **no `strategic-question.schema.json`** and
`scripts/validate_records.py` does not scan that folder. The record is therefore unvalidated
and its field set is inferred from the single example:
`id, record_type, title, description, status, berry_ids, evidence_ids`.

`app/main.py::load_strategic_questions()` reads the folder and matches only on `id` or `title`.

### Declared in the domain model but **wholly unrepresented** (3)

`assessment`, `signal`, `recommendation`. No schema, no folder, no `entity_type` enum value,
no loader function. `BUILD-GUIDE.md` places signal and strategic-question pages in
**Milestone 4, which is not built.**

This is the single largest gap between the brief and the running code, and it is addressed in
`proposed-schema-enhancements.md`.

---

## 3. Required / optional fields

### entity.schema.json
Required: `id`, `record_type`("entity"), `entity_type`, `name`, `status`.
Optional: `aliases[]`, `description`, `roles[]`, `berry_ids[]`, `evidence_ids[]`, `fact_ids[]`, `relationship_ids[]`, `attributes{}`.

`entity_type` enum (12): `company, variety, source, brand, breeding_program, geography, retailer, trait, person, patent, product, berry`.
`status` enum (4): `active, inactive, historical, unverified`.
`roles[]` is **free-form strings — no controlled vocabulary.** Seed data uses
`breeder, genetics_provider, nursery, licensor, retailer`.
`attributes` is `{"type":"object"}` with no constraints — the only free-form extension point in the whole model.

### evidence.schema.json
Required (8): `id`, `record_type`, `status`, `source_type`, `title`, `captured_date`, `summary`, `submitted_by`, `priority`.
Optional: `source_name`, `source_url`, `published_date`(nullable date), `why_it_matters`, `berry_ids[]`, `entity_ids[]`, `fact_ids[]`, `relationship_ids[]`, `strategic_question_ids[]`, `tags[]`.
`id` pattern: `^ev-[a-z0-9-]+$`.
`status` enum (5): `draft, in_review, published, archived, rejected`.
`source_type` is a **bare `{"type":"string"}` — no enum.** Values observed in code/data:
`article, note_observation, uploaded_report, standalone_fact, press_release, patent, field_observation`.

`priority` is an object requiring **all four** dimensions — `reading`, `testing`,
`commercial_position`, `monitoring` — each an object requiring `level` ∈
`{none, low, medium, high}` **and** `rationale` (string).

> **Confirmed: the four independent priority dimensions ARE natively supported, with
> per-dimension rationale.** This was my main open question going in. Note the schema permits
> an empty-string rationale; only the *review UI* enforces non-empty rationale for
> non-`none` levels. This package applies the stricter UI rule.

### fact.schema.json
Required (9): `id`, `record_type`, `statement`, `classification`, `confidence`, `status`, `reviewer`, `created_at`, `evidence_ids`(**minItems 1**).
Optional: `entity_ids[]`, `supersedes`(nullable string).
`id` pattern: `^fact-[a-z0-9-]+$`.
`classification` enum: **`fact | claim` only (2 values)**.
`confidence` enum: `low | medium | high`.
`status` enum: `active | disputed | superseded | withdrawn`.

### relationship.schema.json
Required (7): `id`, `record_type`, `subject_id`, `predicate`, `object_id`, `status`, `evidence_ids`(**minItems 1**).
Optional: `effective_date`(nullable date), `notes`(string).
`id` pattern: `^rel-[a-z0-9-]+$`.
`predicate` enum (**10, closed**): `owns, develops, licenses, distributes, grows, trials, sells, carries, partners_with, operates_in`.
`status` enum: `active | historical | disputed`.
**There is no `confidence` field on relationships.**

---

## 4. Identifier conventions

Derived from `app/main.py` and confirmed against seed records.

| Type | Pattern | Source of truth | Example |
|---|---|---|---|
| entity | `{entity_type}-{slug(name)}` | `unique_entity_id()` | `company-example-genetics` |
| berry | `berry-{name}` | `BERRIES` dict | `berry-blueberry` |
| evidence | `^ev-[a-z0-9-]+$` | schema pattern | `ev-sample-variety-launch` |
| fact | `fact-{evidence_id minus "ev-"}-{n}` | `review_publish()` | `fact-sample-variety-launch-1` |
| relationship | `rel-{evidence_id minus "ev-"}-{n}` | `review_publish()` | `rel-sample-variety-launch-1` |
| strategic question | `sq-{slug}` | seed data only | `sq-premium-flavor` |

`slugify()` = lowercase → non-alphanumeric to `-` → collapse repeats → strip. Collisions get
`-2`, `-3` suffixes.

**The entity ID prefix must equal the `entity_type`.** `GET /entities/{entity_type}/{entity_id}`
matches on both fields, so a mismatch produces a silent 404 rather than a validation error.
This is a real referential trap and is checked explicitly by this package's validator.

The app's *runtime* evidence IDs are `ev-{timestamp}-{rand}-{slug}`, but the seed records use
semantic `ev-{slug}`. Both satisfy the pattern. **This package uses semantic IDs**, matching
seed convention, because curated research records need to be human-traceable and stable
across regeneration.

---

## 5. Folders

`ENTITY_FOLDER_OVERRIDES` in `app/main.py`: `company→companies`, `variety→varieties`,
`geography→geographies`, `person→people`, `berry→berries`; everything else `+s`
(`brand→brands`, `trait→traits`, `patent→patents`, `breeding_program→breeding_programs`,
`retailer→retailers`, `product→products`, `source→sources`).

Note `breeding_program → breeding_programs` keeps the **underscore**, since the override map
does not cover it and the default is bare `+s`. This package's directory is named
`breeding-programs` for readability and the import script maps it to `breeding_programs`
on promotion.

Both `load_json_files()` and the validator use `rglob("*.json")`, so nesting depth inside a
type folder is free.

---

## 6. Dates

All date fields use JSON Schema `"format": "date"` → **ISO `YYYY-MM-DD`**. `FormatChecker`
is active in both the validator and the app, so malformed dates fail loudly.

Available date fields, total, across all four schemas:
`evidence.published_date`, `evidence.captured_date`, `fact.created_at`,
`relationship.effective_date`.

**There is no `event_date` and no separate `access_date` anywhere.** `captured_date` serves
as access date. The brief's required distinction between publication date, event date,
effective date, capture date and access date is therefore **only partially representable** —
see limitation L-3.

---

## 7. Enumerations and controlled vocabularies

| Field | Closed enum? | Values |
|---|---|---|
| `entity.entity_type` | yes | 12 listed above |
| `entity.status` | yes | active, inactive, historical, unverified |
| `entity.roles[]` | **no** | free strings |
| `evidence.status` | yes | draft, in_review, published, archived, rejected |
| `evidence.source_type` | **no** | free string |
| `priority.*.level` | yes | none, low, medium, high |
| `fact.classification` | yes | **fact, claim** |
| `fact.confidence` | yes | low, medium, high |
| `fact.status` | yes | active, disputed, superseded, withdrawn |
| `relationship.predicate` | yes | **10 values, closed** |
| `relationship.status` | yes | active, historical, disputed |
| `evidence.tags[]` | **no** | free strings |

The two free-form arrays (`roles`, `tags`) and `entity.attributes` are the only places
additional structure can legally live. This package defines local controlled vocabularies for
all three and documents them in `README.md` so they can be promoted to real enums later.

**No schema sets `additionalProperties: false`.** Arbitrary top-level fields would technically
validate. Per the brief's instruction not to invent unsupported fields, **this package adds no
top-level field that the schema or `app/main.py` does not already write.** The one exception is
`attachments`, which `review_publish()` writes to published evidence despite its absence from
the schema — it is app-supported and therefore legitimate.

---

## 8. Relationship representation

Directed triple: `subject_id --predicate--> object_id`, plus `status`, `evidence_ids`,
optional `effective_date` and free-text `notes`.

Relationships are **not** stored on entities; `entity.relationship_ids[]` is a derived
back-reference that `review_publish()` populates for both endpoints. This package populates
it identically.

---

## 9. Source and attachment handling

Evidence carries `source_name` (string) and `source_url` (string, **not** `format: uri`, and
**not required** — the seed field-observation record uses `""`). There is no source *entity*
linkage: `entity_type` includes `source`, but nothing in the code links evidence to a source
entity. Publisher identity is a plain string.

Attachments: `data/attachments/{evidence_id}/`, served at
`GET /evidence/{id}/attachments/{filename}`. This package captures **no** attachments — all
evidence is public URLs — so no copyrighted material is stored.

---

## 10. Confidence representation

Exists in exactly one place: `fact.confidence` ∈ `{low, medium, high}`.

**Evidence has no confidence or source-quality field. Relationships have no confidence field.**
The brief requires both (§8 "trust or source-quality assessment", "information confidence";
§11 "confidence" on every relationship). See limitations L-1 and L-2.

---

## 11. Status and review workflow

Physical trust boundary: `inbox/` (untrusted, unvalidated, excluded from feed) →
review UI → `data/` (trusted, validated, published).

`published_evidence()` filters strictly on `status == "published"`. Any other status is
invisible to the feed and to entity pages.

**Consequence for this package:** records are staged with `status: "in_review"`, honouring
WELCOME.md principle 5 ("AI proposes; a human approves"). They will not appear in the feed
until a human approves them. The package's import script has a separate `--approve` step that
flips `in_review → published`. This is deliberate: a research agent should not be able to
publish into trusted data in one motion.

---

## 12. Import conventions

**There is no importer.** This is the most consequential finding.

The only ingestion path is the interactive `inbox/ → /review/{id}/publish` form, which is
single-record, human-driven, and cannot express: pre-assigned semantic IDs, more than 3 facts
or 2 relationships per evidence item, per-fact entity linkage, entity descriptions/aliases/
roles/attributes, or any entity type beyond company/variety/retailer.

`data/imports/` does not exist and no code reads it. `scripts/validate_records.py` targets four
fixed paths (`data/evidence`, `data/entities`, `data/facts`, `data/relationships`), so a package
staged at `data/imports/...` is **invisible to both the validator and the app** — safe to stage,
but it also means the repo's own validator cannot certify it.

This package therefore ships its own tooling, which reuses the repository's schemas verbatim
rather than reimplementing them:

- `scripts/validate_package.py` — schema validation + referential integrity + ID/convention checks
- `scripts/import_package.py` — dry-run / apply / approve, with atomic all-or-nothing writes

---

## 13. Validation commands

Repository baseline (both verified green before this package was built):

```
python scripts/validate_records.py
python -m pytest
```

Note: `requirements.txt` pins `pydantic==2.11.7`, which has no wheel for Python 3.14 and fails
to build from source. **Use Python 3.12** (matching `ARCHITECTURE.md`'s "Python 3.12+"), or
unpin pydantic to ≥2.12.

---

## 14. Inconsistencies and ambiguities found in the existing schema

| # | Finding | Impact |
|---|---|---|
| A-1 | `strategic_question` records exist but have no schema and are not validated | Unvalidated data in `data/`; field set inferable from one example only |
| A-2 | `signal`, `assessment`, `recommendation` are in the domain model with no representation anywhere | Brief §12 cannot be satisfied in-schema |
| A-3 | Berry IDs (`berry-blueberry`) are referenced throughout but **no berry entity records exist**; `BERRIES` is hard-coded in `app/main.py` despite `berry` being a valid `entity_type` | Dangling references today; contradicts "JSON is authoritative" (ADR-0001) |
| A-4 | `evidence.priority.*.rationale` may be `""` per schema, but the review UI rejects empty rationale for non-`none` levels | Schema is weaker than the enforced workflow |
| A-5 | `evidence.source_type` has no enum while five other status/type fields do | Vocabulary drift risk (`article` vs `press_release` vs `news`) |
| A-6 | `entity.roles[]` has no controlled vocabulary | Brief §4 depends on role distinctions being reliable |
| A-7 | `evidence.source_url` is not `format: uri` and not required | Broken/absent URLs validate cleanly |
| A-8 | `attachments` is written to published evidence by `review_publish()` but absent from the schema | Schema does not describe what the app writes |
| A-9 | Entity ID prefix must match `entity_type` for routing, but nothing validates this | Silent 404s instead of validation errors |
| A-10 | Facts link to **every** entity on their evidence item (`review_publish()` copies the full `entity_ids` list), not to their own subject | Fact→entity precision is lost via the UI path; this package assigns per-fact entities correctly |
| A-11 | `data/entities/retailers/` exists but `retailer` is not in `ENTITY_FOLDER_OVERRIDES` — it works only because the default `+s` happens to be right | Fragile by luck, not design |

---

## 15. Blocking limitations for this brief, and chosen fallbacks

Per brief §2: use the closest valid existing representation, document the limitation, propose a
backward-compatible enhancement separately, invent nothing.

| ID | Concept required | Schema support | Fallback used in this package |
|---|---|---|---|
| **L-1** | Evidence source-quality / trust tier (§6, §8) | none | Namespaced tag `tier-1` / `tier-2` / `tier-3` on `evidence.tags[]` |
| **L-2** | Relationship confidence (§11) | none | Structured prefix in `relationship.notes`: `confidence=high; ...` |
| **L-3** | Event date vs publication vs access date (§7) | only `published_date` + `captured_date` | Event date stated explicitly in the evidence `summary` text and, where the relationship is dated, in `relationship.effective_date` |
| **L-4** | `variety EXHIBITS_CLAIMED_TRAIT trait` (§11) | **no valid predicate** | Traits recorded in `variety.attributes.traits[]` with per-trait provenance, plus a `fact` per material trait with `classification: "claim"` |
| **L-5** | `patent PROTECTS variety` (§11) | **no valid predicate** | Patent as an `entity_type: patent` record, linked via shared `evidence.entity_ids`, plus an explicit fact stating the patent–variety relation |
| **L-6** | 5-way trait provenance: claimed / trial-observed / independently-reported / analyst-inference / unresolved (§10) | `fact.classification` has 2 values | `claim` for owner/marketer claims; `fact` for trial-measured and independently-reported; **analyst inference is excluded from facts entirely** and confined to signals; full 5-way value preserved in `variety.attributes.traits[].provenance` |
| **L-7** | Signals (§12) | none | Staged in `signals/` **outside** the four validated types, with a proposed schema. Not importable until the schema exists — flagged in the manifest as deferred |
| **L-8** | `organization MARKETS product`, `nursery OFFERS variety`, `brand OWNED_BY organization` (§11) | not in the 10-value enum | `markets`→`sells`; `offers`→`distributes`; `owned_by`→inverted to `owns`. Every substitution is recorded in `relationship.notes` |
| **L-9** | Strategic-question records | no schema | Follow the one seed example's field set exactly; propose a schema |
| **L-10** | Assessments, recommendations as records | none | Recommendations expressed only through the four `priority` dimensions + rationale on evidence, which is their intended home |

**Nothing in this list justified changing a production schema.** All ten fallbacks are legal
against the current schemas as shipped.

---

## 16. Vendor-neutrality check

ADR-0004 and WELCOME.md principle 9 require neutral treatment. The existing seed entities are
deliberately fictional ("Example Genetics", "Example Blue"). This package **adds** real
entities and **modifies or deletes nothing**, so the fictional demo records and the 28 tests
that depend on them remain intact. No organization in this package is marked as the user's
employer, and no `home`/`self` role is used.
