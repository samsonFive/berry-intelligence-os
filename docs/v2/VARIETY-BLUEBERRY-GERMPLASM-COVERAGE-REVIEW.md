# Blueberry public-collection coverage review — October 7, 2026

The Hortifrut finding is a broader catalog coverage problem. An independent
USDA collection comparison now finds 133 blueberry names with no exact match
in the catalog or derived review queue, 13 with existing candidate matches and
two with catalog text matches. These counts are before private analyst state;
they measure names to investigate, not newly verified varieties.

## Source and accounting

The native [GRIN accession search](https://npgsweb.ars-grin.gov/gringlobal/search)
used Scientific Name = Vaccinium, any part or synonyms, all accessions including
historical, and a 10,000-row limit. Its 2,113 results reconcile to 2,113 distinct
exported accession labels. Read-only Artifact Tool import verified the workbook's
title row, 17-column header and 2,113 data rows. The raw workbook, full matrix,
query manifest and detailed operator comparison remain under ignored `inbox/`.

The query is not a genus or crop filter: 2,018 returned records have Vaccinium
taxonomy and 95 have other genera. The other-genus results have no Cultivar
classification in this export. Query membership never assigns a blueberry crop.

| Source classification/disposition | Records | Displayed group/name pairs |
| --- | ---: | ---: |
| Cultivar in four checked blueberry species | 178 | 148 |
| Cultivar, generic Vaccinium hybrid taxonomy | 57 | 53 |
| Cultivar in other taxa, outside the checked blueberry scope | 80 | Excluded |
| Wild, breeding, cultivated, genetic, clone, uncertain or unclassified material | 1,798 | Excluded |
| Total native export | 2,113 | 201 comparable/unresolved pairs |

All 315 Cultivar-classified records contain 273 distinct literal plant-name
labels. The displayed subset contains 200 literal labels / 201 group/name pairs:
Pearl River occurs in both a checked species and generic hybrid taxonomy and
stays separate. A source Cultivar designation can still describe a research code;
it does not establish a commercial release. Multiple accessions with the same
name are holdings, not additional varieties.

The four exact taxonomy assignments were checked in GRIN's visible Nomenclature
and Common Names tabs. Each belongs to section Cyanococcus and has an English
blueberry common name:

- [Vaccinium corymbosum L. — highbush blueberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail?id=41002)
- [Vaccinium virgatum Aiton — rabbit-eye blueberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail?id=41068)
- [Vaccinium angustifolium Aiton — lowbush blueberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail?id=40981)
- [Vaccinium darrowii Camp — Darrow's blueberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail?id=41007)

These four species do not enumerate all blueberry taxonomy or releases. The 57
hybrid records include useful blueberry leads and explicitly named non-blueberry
cross material; all 53 hybrid labels withhold matching until crop scope is checked.
An existing same-name blueberry is not evidence of the hybrid record's identity.

## Actionable review without automatic approval

The existing `/varieties/coverage` page now offers scoped blueberry counts,
name/accession search, 50-row pagination, original collection identifiers and a
separate unresolved-hybrid filter. The dense table keeps row actions inline on
desktop and horizontal overflow contained on a phone.

An individual **Add to identity review** POST can copy a scoped missing name into
the existing private candidate store. It reuses the existing candidate builder
and additive persistence. The lead retains the source, capture date, workbook
hash, literal name and accession/taxonomy references. Its tier is a weak,
noncanonical lead; it approves no identity, Source, company role or catalog record.
Existing catalog/candidate matches redirect to those records. Multiple matches
open the existing queue without selecting an identity. Stable source/name IDs
preserve edits and human decisions on replay. Stale input hashes, invented names,
unassigned hybrid crops and cross-origin/public-mode writes are rejected.

Canonical catalog remains 64. Primary portfolio accounting remains 495 source
occurrences / 33 matches / 462 review needs in 45 sections; 413 candidate keys
before private state, 57 initial registry checks and four source gaps remain.
No acquisition adapter, domain schema, CPVO integration, monitoring cadence,
public maturity classification, trait, alias, right or growing region changed.
Received/source years and collecting origins are not release dates or growing
footprints. Raw narratives, coordinates and collection sites are omitted.

## Validation and remaining work

77 focused checks passed with one existing ReportLab deprecation warning; record
validation passed. Native desktop review verified scoped counts, an individual
Aliceblue handoff with PI 554959 provenance, search and two separate USDA-Spiers
accession references. Native 390px phone review verified the hybrid warning and
contained horizontal table; page width retains the existing 1px rounding overflow.
The browser-created lead exists only in this mission's isolated preview inbox:
its local counts are 132 missing / 14 queued instead of the baseline 133 / 13.
No human identity decision or publication approval was simulated.

Parent draft #327 passed all four exact-head gates at
0a219a0b89413c8b15f676438cc18fd24116140a: 4,083 passed / 11 skipped /
two warnings / 474.00 seconds (run 37648531637). This draft's full CI is pending.

CAT-01/CAT-02 and TD-116 remain open: original release/rights verification,
hybrid crop resolution, actual human catalog authoring, remaining breeder
portfolios, full-article/table recall and cited profile depth still need work.
This source is an independent comparison, not a worldwide completeness score.
No merge/deployment or other-berry Landscape rollout is included.
