# Proposed import order

The importer (`scripts/import_package.py`) already writes in a dependency-safe order and validates
before writing anything. This document exists so a reviewer can see **why** the order is what it
is, and can reproduce it by hand if the package is ever imported piecemeal.

---

## Why order matters here

Records reference each other by id in four directions:

- `evidence.entity_ids` -> entity
- `fact.evidence_ids` -> evidence
- `relationship.subject_id` / `object_id` -> entity
- `relationship.evidence_ids` -> evidence
- `entity.evidence_ids` / `fact_ids` / `relationship_ids` -> back-references

Because entities carry back-references to facts and relationships that do not exist until later in
the sequence, the graph is genuinely circular. It is resolved by writing entities first and
accepting that their back-reference arrays point forward for the duration of the import. The
package validator checks that every one of those forward references lands, and it does so **before
any file is written**, so a partial import cannot leave dangling ids.

## The order

| Step | What | Count | Depends on |
|---|---|---|---|
| 0 | Validate the whole package | - | nothing |
| 1 | Entities | 155 | nothing (back-references point forward, checked in step 0) |
| 2 | Evidence | 121 | entities (step 1) |
| 3 | Facts | 186 | evidence (step 2) |
| 4 | Relationships | 204 | entities (step 1), evidence (step 2) |
| 5 | Strategic questions | 8 | entities, evidence, facts |
| 6 | Human review | - | steps 1-5 |
| 7 | Approve evidence | 121 | step 6 |

**Total written: 674 files.** Signals are not imported - see below.

### Within step 1, entities are written by type

The importer walks entity subdirectories alphabetically, which is safe because entities do not
reference each other except through relationships. For a manual import the useful order is
foundational first:

1. `berries` (1) - `berry-blueberry`, referenced by nearly everything via `berry_ids`
2. `geographies` (16)
3. `traits` (10)
4. `companies` (32)
5. `breeding_programs` (9)
6. `brands` (8)
7. `patents` (38)
8. `varieties` (40)
9. `retailers` (1)

Varieties come late because their `attributes.traits[]` reference trait entities, and patents come
before varieties because variety records point at the patents that protect them.

### Directory name mapping

The staging package uses hyphenated directory names; the repository uses underscores in one case.
The importer handles the translation:

| Staging | Repository |
|---|---|
| `entities/breeding-programs/` | `data/entities/breeding_programs/` |
| `entities/companies/` | `data/entities/companies/` |
| `entities/varieties/` | `data/entities/varieties/` |
| `entities/geographies/` | `data/entities/geographies/` |
| `entities/berries/` | `data/entities/berries/` |
| all others | `data/entities/<type>s/` |
| `strategic-questions/` | `data/strategic-questions/` |

Entity ids must be prefixed with their `entity_type` - `company-hortifrut`, not `hortifrut` -
because `app/main.py` resolves detail routes as `/entities/{entity_type}/{entity_id}`. An id whose
prefix does not match its type produces a 404 on an otherwise valid record. The package validator
enforces this.

### What is deliberately not imported

`signals/` is excluded by the importer's `DEFERRED` set. Six signal records live there. No signal
schema exists in the running repository (limitation L-7), so importing them would mean either
inventing a schema or writing records the application cannot read. Neither is acceptable under the
brief. They remain in the staging package for human review.

## Commands

Run from the repository root. Python 3.12 is required; `pydantic==2.11.7` does not build on 3.14.

```bash
# 1. Validate the package. Writes nothing. Exit code 0 means safe to proceed.
python data/imports/blueberry-public-pilot-2026-08-03/scripts/validate_package.py

# 1b. Same, with every warning listed.
python data/imports/blueberry-public-pilot-2026-08-03/scripts/validate_package.py --verbose

# 2. Dry run. Reports exactly what would be written, per directory. Writes nothing.
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --dry-run

# 3. Apply. Validates again first, then writes 674 files into data/.
#    All evidence lands as status='in_review' and is NOT in the feed.
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --apply

# 4. Confirm the repository's own validator is still clean.
python scripts/validate_records.py

# 5. Confirm the existing test suite is unaffected.
python -m pytest

# 6. Review the staged evidence in the application, then publish it.
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --approve

# 7. If anything is wrong, remove every file this package wrote. Touches nothing else.
python data/imports/blueberry-public-pilot-2026-08-03/scripts/import_package.py --rollback
```

## Expected output at each step

| Step | Expected |
|---|---|
| Validate | `PASSED -- schema, conventions, and referential integrity all clean.` with 176 warnings |
| Dry run | `674 file(s) would be written`, `Validation: PASS`, `Nothing was written.` |
| Apply | `Imported 674 file(s) into data/.` |
| `validate_records.py` | `All validated records passed.` |
| `pytest` | `28 passed` |
| Approve | `Approved 121 evidence record(s) -> status='published'.` |
| Rollback | removes exactly the 674 files, leaves pre-existing data untouched |

## Safety properties

- **Additive only.** The package creates new files. It modifies and deletes nothing that already
  exists in `data/`.
- **Validated before writing.** `--apply` re-runs the full validation and aborts on any error.
- **Not visible until approved.** Evidence lands as `in_review`. The feed and entity pages show
  published evidence only, so nothing appears to a user until a human runs `--approve`.
- **Reversible.** `--rollback` removes precisely the files this package wrote.
- **Invisible before import.** `data/imports/` is not read by `scripts/validate_records.py` or by
  the application, so the staged package cannot affect the running system while it sits there.
