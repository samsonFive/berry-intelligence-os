# Changelog

All changes made while assembling `blueberry-public-pilot-2026-08-03`.

**Nothing outside `data/imports/blueberry-public-pilot-2026-08-03/` was modified.** No production
schema was changed. No pre-existing record was edited or deleted. The repository's own validator
and its 28 tests were run before and after a trial import and behave identically.

---

## 2026-08-03 - Wave 1: foundation

**Added**

- Staging directory `data/imports/blueberry-public-pilot-2026-08-03/` with `entities/`,
  `evidence/`, `facts/`, `relationships/`, `strategic-questions/`, `signals/`,
  `rejected-or-unusable-sources/` and `scripts/`.
- `scripts/validate_package.py` - schema, id-convention, referential-integrity and brief-rule
  validation. Reads the four production schemas from the repository; does not modify them.
- `scripts/import_package.py` - `--dry-run`, `--apply`, `--approve`, `--rollback`.
- `scripts/build_reports.py` - regenerates `manifest.json`, `source-coverage.csv` and
  `scripts/_stats.json` from the staged records.
- 80 entities, 71 evidence records, 114 facts, 111 relationships, 8 strategic questions covering
  Mountain Blue Orchards and the Eureka family, Fall Creek Farm & Nursery and the SEKOYA platform,
  the University of Florida programme with Florida Foundation Seed Producers, and the core
  geography and trait vocabulary.
- `schema-assessment.md` documenting limitations L-1 to L-10 and the fallback representation used
  for each.
- `proposed-schema-enhancements.md` - backward-compatible proposals, none applied.
- `research-method.md`, `README.md`, `WAVE-1-REVIEW.md`.

**Key corrections established in this wave**

- OZblu and Eureka are separate genetics. Prior material conflating them is wrong.
- Eureka is `'Ridley 1403'` (US PP25,432). `'Ridley 1111'` is Opi, so the A$290,000 Chellew
  judgment concerns Opi, not Eureka.
- "Eureka" functions as both a cultivar name and an umbrella brand. Both senses are staged, and
  they are not merged.

**Not done**

- No production directory written to.
- No schema modified.

## 2026-08-03 - User review checkpoint

Wave 1 was validated and presented for schema-conformance review before further work. Approved
without changes; Waves 2 and 3 authorised.

## 2026-08-04 - Wave 2: breadth

**Added**

- 76 entities, taking the total to 156 before later removals: 24 companies, 5 breeding programmes,
  4 brands, 6 geographies, 2 traits, 18 patents, 17 varieties.
- 50 evidence records (`captured_date: 2026-08-04`), taking the total to 121.
- 72 facts, taking the total to 186. 92 relationships, taking the total to 204 after later
  additions.
- Coverage of United Exports and OZblu, Hortifrut and Berry Blue LLC, Driscoll's, Planasa,
  Costa Group and BluGenix, Agrovision and Fruitist, IQ Berries and TopFruit, and the University
  of Arkansas trial.

**Corrections established in this wave**

- **OZblu Bonita 'EB 9-12' is US PP28,358, not US PP25,358.** PP25,358 is an Aglaonema ornamental
  patent. The mis-cited number is preserved as `patent-uspp025358p3` with `status: "historical"`,
  an empty `berry_ids` and an attribute recording the mis-citation, so the error stays traceable
  rather than being silently erased.
- The OZblu breeder of record is **Vincent David Mazzardis** of Yanchep, Western Australia. United
  Exports became joint titleholder in 2016.
- **Advanced Berry Breeding lists raspberry cultivars only.** It is not a blueberry breeder.
- **Agrovision, now Fruitist, is not a breeder.** It licenses Sekoya genetics.
- The "Mega" variety family belongs to **IQ Berries**, not Agrovision.
- **Michigan Blueberry Growers and Mountain Blue Orchards are different companies.** Hortifrut's
  Berry Blue joint venture is with the former; the 30 July 2026 transaction is with the latter.
- Driscoll's 2020-2026 litigation is a **strawberry** matter, not blueberry.
- Hortifrut's blueberry IP sits under Berry Blue, LLC and the acquired Atlantic Blue and Royal
  Berries programmes. No "Hortifrut Genetics" entity holding blueberry varieties exists in any
  retrieved source.
- Costa Group Holdings changed from Limited to Pty Ltd on 3 June 2024, following delisting on
  27 February 2024.

**Changed**

- Six Wave 2 fact statements classified `claim` were reworded to lead with an explicit attributor
  verb, so that the attribution is visible in the statement itself rather than only in the linked
  evidence. This reduced validator warnings from 184 to 178.

**Removed**

- `rel-united-exports-operates-in-south-africa` as drafted in Wave 2 - an exact duplicate of the
  Wave 1 relationship of the same id. Caught by the build-time duplicate-id assertion.

## 2026-08-04 - Orphan resolution

A custom check found twelve entities with no evidence, fact or relationship link. All twelve were
resolved rather than left in place.

**Changed**

- Three patents cited only as parents on another patent's front page - `patent-uspp025859p3`,
  `patent-uspp028334p3`, `patent-uspp028357p3` - were added to the `entity_ids` of the evidence
  records that cite them (`ev-uspp027142-eb12-19`, `ev-uspp033138-ns15-13`, `ev-uspp032897-ns16-2`),
  so the reason they exist in the graph is visible.
- Ten patent entities that no staged evidence record supports were demoted to
  `status: "unverified"` and given a `verification_status` attribute stating that the patent front
  page was not captured in this pilot and that the assignee and grant-date attributes are therefore
  unsupported within the package. Seven are Wave 1 patents (`patent-uspp033802p3`,
  `patent-uspp019341p2`, `patent-uspp032028p3`, `patent-uspp031793p3`, `patent-uspp033896p2`,
  `patent-uspp021553p2`, `patent-uspp012165p2`); three are the cited parents above. This demotion
  is applied automatically on every build, and the build prints the list.

**Added**

- `rel-united-exports-operates-in-zambia` at `confidence=low`, supported by
  [United Exports' own country list](https://united-exports.com/what-we-do/), which is self-reported
  and undated.

**Removed**

- `brand-sweetest-batch`. No source opened in this pilot names it. Recorded in `coverage-gaps.md`
  as a verification item rather than staged as an evidence-less entity.

Entity count moved from 156 to 155 as a result.

## 2026-08-04 - Wave 3: signals

**Added**

- Six signal records in `signals/`, all at `status: "proposed"`. Per the brief, no signal is
  labelled `confirmed` in an initial research package. Each cites at least two evidence records and
  states what would confirm it and what would falsify it:
  - `sig-breeding-programmes-becoming-consumer-platforms`
  - `sig-owner-published-quality-figures-exceed-independent-measurement`
  - `sig-financial-owners-taking-positions-in-berry-genetics`
  - `sig-southern-africa-as-licensing-and-enforcement-arena`
  - `sig-registry-participation-is-highly-uneven-between-breeders`
  - `sig-breeder-and-patent-attribution-drift-in-public-sources`
- Signals are excluded from import by the importer's `DEFERRED` set, because no signal schema
  exists in the running repository (limitation L-7).

**Not changed**

- Strategic questions remain at 8, within the brief's 5-8 target. No new ones were needed.

## 2026-08-04 - Documentation and reports

**Added**

- `qa-report.md`, `conflicting-claims.md`, `coverage-gaps.md`, `next-research-waves.md`,
  `import-order.md`, `priority-actions.md`, `EXECUTIVE-SUMMARY.md`, this changelog, and
  `rejected-or-unusable-sources/README.md`.

**Regenerated**

- `manifest.json` - 682 JSON files indexed (674 importable, 6 signals, plus `manifest.json` and `scripts/_stats.json`). `repo_commit` is `null`: the supplied repository
  archive contains no `.git` directory, so no commit hash could be recorded. This is stated rather
  than fabricated.
- `source-coverage.csv` - 121 rows, one per distinct source URL.
- `scripts/_stats.json` - record counts by type, tier, classification, confidence and status, plus
  the disputed-fact list, the unverified-entity list and the list of evidence records with no
  published date.

## Verification run at the end of the work

| Check | Result |
|---|---|
| `scripts/validate_package.py` | PASSED, 176 warnings, 0 errors |
| `scripts/import_package.py --dry-run` | 674 files, Validation: PASS, nothing written |
| Trial `--apply` into a scratch repository copy | 674 files imported |
| Trial `--approve` | 121 evidence records published |
| `scripts/validate_records.py` after trial import | All validated records passed |
| `pytest` after trial import | 28 passed |
| Application route smoke test | 23 routes, all HTTP 200; `/api/feed` returned 124 items |

The trial import was performed in a throwaway copy of the repository. The working repository still
holds the package unimported.
