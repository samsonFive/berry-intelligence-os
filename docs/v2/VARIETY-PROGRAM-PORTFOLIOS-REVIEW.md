# Variety coverage: programs, clone selections and nursery assortments

This follow-up reconciles additional current primary pages through the existing
identity workflow. It expands source coverage rather than approving new varieties,
rights, traits, company roles or growing footprints. Landscape stays at the
blueberry checkpoint; the governing expansion guide remains unchanged.

## Names checked on October 7, 2026

| Source scope | Name occurrences | What the listing proves and leaves open |
| --- | ---: | --- |
| NIWA Varieties | 18 | Named selections in explicit crop groups. Black raspberry is raspberry. Ten labels link to coded selections; a code/name pairing does not prove an official denomination or commercial release. |
| NIWA Clones | 7 | Two raspberry and five blueberry clone codes. All ten cards are accounted for: three cards labeled only “Berries” are excluded with links and species-ambiguity reasons. No released-cultivar claim. |
| Vissers strawberries | 49 | All live unfiltered product-heading links. Own, licensed and public cultivars appear together; nursery supply is not breeding or ownership. |
| Vissers raspberries | 6 | All live product-heading links. Cached search text also named Primeberry Sugana; its absence now is not withdrawal, rejection or deletion. |
| Limgroup clonal strawberries | 3 | Limvalnera, Limalexia, Limadela. Climate/cultivation filters are not planted-region evidence. |
| Limgroup hybrid strawberries | 2 | Limore Fizz and Limore One, on a separate current F1 page. Linked brochure remains separate acquisition/review work. |
| ABZ three fresh-market pages | 3 | Soraya F1, Estavana F1 and Rowena F1, one literal product tab per page. |
| ABZ six garden/patio pages | 18 | All visible named tabs inside Patio Pleasure (3), Home Harvest (2), Early & Compact (3), Hanging Basket (4), Large Flower (3) and Semi-Double Flower (3). Series headings and image filenames are excluded. |

There are **106 added occurrences across 15 sections**. Combined primary coverage
is **381 occurrences / 25 catalog matches / 356 identity-review needs** in 32
sections (31 readable, one unreadable). Source occurrences are not unique cultivars.
The existing queue derives **341 candidate keys before private inbox state**:
68 stored-source candidates plus 273 additional primary-source keys. Four repeated
keys in this slice add provenance rather than another candidate. The approved
catalog remains 64. Fifteen of the 77 supplied registry rows have some checked
pages; **62 still need initial primary checks**. No global completeness score.

Source URLs, linked product pages, codes, literal display labels and bounded scope
are stored in `data/imports/variety-portfolio-observations-2026-10-07-programs/observations.json`.
ABZ entry URLs are retained separately from the final primary-page URLs reached
after navigation redirects. Trademark glyphs are omitted from identity strings,
while literal F1 suffixes are retained without automatic alias decisions. No
article bodies, promotional ratings, contact details or image files are imported.

NIWA's NR 1849002 appears as a code in Clones and paired with Baron in Varieties.
Both product URLs and both contexts remain on the shared candidate. Code/name
pairings are unreviewed, not a new rights filing. Explicit black-raspberry crop
groups do not create blackberry candidates. The three ambiguous NL codes do not
enter the candidate queue. Vissers candidates use the existing nursery source
tier, with no invented breeder/owner or relationship. Source absence never deletes
an existing record or private decision.

ABZ's new live pages do not resolve the previously unreadable 2024–2025 assortment
PDF: the historical failed capture remains visible. NIWA historical releases,
Vissers' primary-linked flipbook and Limgroup's brochure remain unenumerated.
Current page accounting is bounded to visible product headings/tabs, not the
company's complete historical releases or every country-specific assortment.

## Verification and remaining work

Reproduce the body-free audit with:

```text
python scripts/audit_variety_portfolios.py --output artifacts/variety-program-portfolios/coverage-audit.json
```

Final focused coverage/navigation validation passed 40 tests with one existing
ReportLab deprecation warning in 28.33 seconds. The first test run exposed a test selector
that accidentally counted ABZ's retained unreadable PDF alongside its nine readable
pages; the assertion now distinguishes capture states and keeps both scopes.
Browser review found ABZ's source-plan starting link still preferred the older
unreadable PDF. The shared read-only plan now prefers an enumerated page, then a
partial page, then a saved public website, with an attempted source as fallback.
Readable, partial and failed capture states remain intact. The integration test
checks ordering and preservation rather than treating a failed page as no varieties.

Desktop review verified 381 occurrences, 25 matches, 356 review needs and 62 rows
still needing primary checks. NIWA/Blueberry filtering showed five clone codes;
whole-page accounting retained all ten cards and all three exclusions. Raspberry
source handoff showed two of 341 candidates; NR 1849002 retained both code/name
and clone product URLs. At a 390px viewport, page scroll width was 375px and a
620px table stayed in a 349px scrolling panel. Native keyboard Enter opened ABZ's
one-row filtered source plan, and its link opened the checked greenhouse page.
No review action was submitted. Proof is in `artifacts/variety-program-portfolios/`;
preview is `http://127.0.0.1:18445/varieties/coverage`, localhost only, polling off,
task-private runtime. Canonical validation passed; exact-head required checks are
recorded with the draft PR. Existing data and operator-private state are not
rewritten. No provider or approval call is triggered by viewing coverage.

CAT-01/CAT-02 and TD-116 remain open. Continue remaining primary sources, official
denomination/rights checks, human identity decisions and canonical authoring,
cited profiles/images/growing regions, qualified full-text/table acquisition,
refresh reconciliation and an independent recall/comparison benchmark. No merge,
deployment or other-berry Landscape rollout is authorized by this slice.
