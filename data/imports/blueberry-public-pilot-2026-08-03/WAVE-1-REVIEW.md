# Wave 1 — schema-conformance review checkpoint

Staging path: `data/imports/blueberry-public-pilot-2026-08-03/`
Nothing has been written into `data/entities/`, `data/evidence/`, `data/facts/`,
`data/relationships/` or `data/strategic-questions/`. The package is additive only and
modifies or deletes no existing record.

## What is in the package right now

| Record type | Count |
|---|---|
| entity — company | 8 |
| entity — variety | 23 |
| entity — patent | 20 |
| entity — geography | 10 |
| entity — trait | 8 |
| entity — brand | 5 |
| entity — breeding_program | 4 |
| entity — retailer | 1 |
| entity — berry | 1 |
| **entity total** | **80** |
| evidence | 71 |
| fact | 114 |
| relationship | 111 |
| strategic_question | 8 |
| **total files** | **384** |

Distinct source URLs: 71 (no URL is used by two evidence records).

## Verification results

All commands run under `/home/user/workspace/venv312/bin/python` (Python 3.12; the pinned
`pydantic==2.11.7` will not build on 3.14).

| Check | Command | Result |
|---|---|---|
| Package validation | `python data/imports/blueberry-public-pilot-2026-08-03/scripts/validate_package.py` | PASSED, 0 errors, 63 advisory warnings |
| Import dry run | `... /scripts/import_package.py --dry-run` | 384 files, 0 collisions with existing records |
| Repo validator after trial apply | `python scripts/validate_records.py` | All validated records passed |
| Repo test suite after trial apply | `python -m pytest` | 28 passed |
| Repo test suite after trial `--approve` | `python -m pytest` | 28 passed |
| App render smoke test | 21 routes incl. every new `entity_type` | all 200 |
| Feed isolation before approval | `/api/feed` | 3 items — the original seed records only |

The trial apply and approve were performed on a throwaway copy of the repository, which has
since been deleted. The working repository is untouched.

## Schema decisions you are being asked to confirm

1. **Staged evidence uses `status: "in_review"`, not `published`.** The feed only surfaces
   `published`, so nothing appears to users until a human runs `--approve`. This follows
   WELCOME.md principle 5.
2. **Entity id prefix always equals `entity_type`** (`patent-uspp025432p3`,
   `breeding_program-uf-ifas-blueberry-breeding`). This is required — `app/main.py` derives the
   folder from the type, so a mismatched prefix produces a silent 404.
3. **`classification` is only `fact` or `claim`.** Owner and marketer assertions are `claim`,
   registry and measured values are `fact`. Analyst inference is not represented as either and
   is deferred to the non-importable `signals/` folder.
4. **Relationship confidence is carried in `notes`**, which always begins
   `confidence=<low|medium|high>; `. The schema has no confidence field on relationships.
5. **Substituted predicates are declared in `notes`.** The predicate enum is closed at 10
   values, so `markets` became `sells`, `subsidiary_of` became `partners_with`, and the
   patent→variety `protects` link is carried by shared evidence plus an explicit fact rather
   than by a relationship.
6. **Per-trait provenance lives in `variety.attributes.traits[]`**, each entry carrying
   `provenance` ∈ {`owner_or_marketer_claim`, `named_trial_measurement`, `independent_report`,
   `regulatory_or_registry_record`, `analyst_inference`, `unresolved`} plus its own
   `evidence_ids`. Traits are also modelled as first-class `trait` entities so they can be
   browsed.
7. **Source tier is a namespaced tag** (`tier-1` / `tier-2` / `tier-3`) because evidence has no
   tier field. Exactly one tier tag per evidence record, enforced by the validator.

The 63 warnings are advisory only: 59 are `role` strings outside the vocabulary my own
validator proposes (the production schema leaves `roles[]` free-form), and 4 are false
positives where the validator's claim-attribution heuristic misses a claimant that is in fact
named in the statement.

## Research findings that changed the brief's premises

- **OZblu is not Eureka genetics.** The OZblu varieties (`EB##-##`, `NS##-##`) were bred by
  David and Leasa Mazzardis through Nature Select in Western Australia. United Exports is the
  exclusive sub-licensor and marketer, not the breeder. Mountain Blue's `Ridley` series is a
  separate, competing programme. The package records Nature Select and United Exports as
  distinct entities with distinct roles.
- **Eureka is `Ridley 1403`, not `Ridley 1111`.** `Ridley 1111` is Opi. The A$290,000
  Australian Federal Court judgment therefore attaches to Opi, and sources that attribute it to
  Eureka are recorded as being in conflict with the patent record.
- **"Eureka" is simultaneously a cultivar and an umbrella brand.** `variety-eureka` and
  `brand-eureka` are separate records and the naming hazard is stated on both.
- **Eureka Sunrise appears under two codes** (`Ridley 160` at 714 t and `Ridley 1602` at 183 t)
  in the same Proarandanos export table. The two figures are recorded but explicitly not summed.
- **Twilight's cultivar identity is unresolved.** It is recorded with
  `status: "unverified"`, `selection_code: null`, and the five candidate codes that were
  checked and rejected.
- **`FC11-164` has no published commercial name.** Also `status: "unverified"`.

## Open conflicts recorded rather than resolved

| Conflict | Sources | Handling |
|---|---|---|
| SEKOYA membership: 14 vs 15 | Fall Creek vs Produce Report | fact `status: "disputed"` |
| Mountain Blue founding: 1975 vs 1978 | Two pages of the same site | fact `status: "disputed"` |
| Optimus firmness/size/Brix | UF breeding programme vs FFSP | fact `status: "disputed"` |
| Sentinel machine harvest: "no data yet" vs "suitable" | Two UF publications | fact `status: "disputed"` |
| Patrecia patent inventors ≠ UF breeders | USPP027740P2 vs HS1245 | fact `status: "disputed"` |
| Eureka brand ↔ `Ridley 1403` mapping | Trade sources; IP Australia synonym field reads "N/A" | `claim`, medium confidence |

## What Wave 1 deliberately does not contain yet

- The remaining organisations (Hortifrut, Driscoll's, Planasa, Costa/BluGenix, Agrovision,
  Advanced Berry Breeding, and others) and their varieties.
- The individual OZblu cultivars. The Nature Select breeding relationship is currently attached
  to `brand-ozblu` as a placeholder and will be re-pointed at cultivar entities in Wave 2.
- `signals/`, `manifest.json`, `research-method.md`, `source-coverage.csv`, `qa-report.md`,
  `unresolved-questions.md` and the package `README.md`.
- Geographic coverage is currently skewed to North America, Australia and the licensed
  export origins. Latin America appears only through market data, and Asia only through
  litigation and stated market intent. This gap will be recorded explicitly rather than
  padded out.
