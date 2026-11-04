# Send checked collection names to identity review

The existing public-collection comparison could send a missing blueberry name
to identity review, but offered no equivalent action for strawberries,
raspberries or blackberries. Its broad Rubus comparison could also suggest a
blackberry namesake for a source record explicitly classified as raspberry.
This follow-up closes those workflow gaps on the existing Coverage page.

## What changes

- **Strawberry:** retain the existing source-reported Fragaria genus scope.
- **Raspberry and blackberry:** use only five exact GDR organism labels whose
  nomenclature and English common names were checked in USDA GRIN on November 4,
  2026. Every reference for a label must establish the same crop.
- **Uncertain taxonomy:** keep the source label and accession references visible.
  Generic hybrids, mixed crops and unchecked species cannot enter this handoff.
  Broad Rubus name suggestions remain available for comparison, clearly held
  pending a crop check. The crop-check filter includes those suggestions;
  its hold count is separate from the disjoint name-match counts.
- **Identity review:** one explicit action adds one weak, unreviewed private
  candidate. It carries source capture date/hash, literal references and the
  separate crop-check provenance. Same-key conflicting labels stay visible.
  It does not approve an identity, source, breeder, rights, traits or footprint.
- **Replay:** existing edited, renamed, re-scoped and rejected records win.
  Current catalog/queue matches redirect to comparison or existing review;
  multiple matches never select an identity automatically. New GDR IDs include
  the genus and crop; existing blueberry IDs and their helper remain compatible.

## Original taxonomy checks

These links classify the source species for a research lead. They do not prove
that a particular accession is correctly identified or commercially released.

| Exact GDR organism label | Crop for this handoff | Checked GRIN common name / original record |
| --- | --- | --- |
| Rubus idaeus | Raspberry | [Red raspberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail.aspx?id=467361) |
| Rubus occidentalis | Raspberry | [Black raspberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail.aspx?id=32401) |
| Rubus argutus | Blackberry | [Southern blackberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail.aspx?id=104946) |
| Rubus laciniatus | Blackberry | [Evergreen blackberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail.aspx?id=32364) |
| Rubus ulmifolius | Blackberry | [Elm-leaf blackberry](https://npgsweb.ars-grin.gov/gringlobal/taxon/taxonomydetail.aspx?id=313548) |

All 12 printed Rubus organism labels in the retained export were accounted for.
`Rubus fruticosus` has multiple nomenclatural uses in GRIN; its authorless source
label is insufficient to choose one. `Rubus crataegifolius` and `Rubus neglectus`
did not supply a checked English crop label. `Rubus trivialis` is reported as
southern dewberry; this change does not silently coerce it into a four-crop
assignment. `Rubus spp.`, `Rubus sp.` and `Rubus hybrid` remain unassigned.
Neither related-species membership nor parentage fills these gaps.

## Accounted collection scope

The GDR capture remains **2,372 genus/name pairs** from October 7, 2026:
2,092 project to strawberry, 174 to raspberry and six to blackberry;
100 remain held. GRIN remains 148 checked blueberry name pairs plus 53
unassigned hybrid pairs. These are collection labels, including experimental
selections and historical material, not distinct approved commercial varieties.

All literal labels, source keys, accession/organism references, export counts,
source capture dates and input hashes are retained. The November taxonomy check
does not replace the October collection capture date. No new collection export,
source import, provider call or bulk candidate population occurs.

## Review and release boundaries

The existing authoring-only POST retains edit authorization and same-origin
checks. Public/static output has no review form. The table retains search,
crop/status filters and 50-row pagination; source context remains collapsible.

Focused and regression checks cover exact and mixed taxonomy, crop/genus
namesakes, stale/unknown input, multiple identities, escaping, additive writes,
replay of human edits, existing blueberry IDs and read-only comparison. Native
desktop/phone checks and the current-head CI results are recorded with the draft
PR. All existing source/schema JSON files and the five runtime files from the
tested Learn/performance parent are preserved.

This branch retains platform #499 and excludes source-only #498. Fresh private
production-data preservation, guarded workflow acceptance and separate release
approval remain required. It is not deployed. CAT-01/CAT-02/TD-116, independent
human recall, original source/rights/photo decisions and TD-122 remain open.
