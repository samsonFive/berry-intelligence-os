# Original patent links on variety profiles

Variety profiles now expose reconciled original filing references in Rights / IP,
with separate links to the filing page, claims, original document and illustrations
when those URLs are actually recorded. The same presentation serves the current
and legacy profiles. Document scope stays collapsed; reference number, date and
unreviewed state remain visible. Existing `us_plant_patent` and `breeding_program`
attributes are displayed alongside the newer field conventions instead of being
silently ignored. No canonical records or field schemas are rewritten.

## Identity and review boundaries

The shared portfolio reconciliation had a genuine gate defect: an exact name
could attach a source row to a canonical variety despite an existing human
distinct or rejected decision. Those decisions now take precedence. A human
same-identity decision still requires an existing, crop-compatible canonical ID.
Ambiguous exact names, crop mismatches and unresolved source code/label conflicts
remain unlinked. This change does not manufacture reviews or catalog entries.

Private filing links reuse that reconciliation. It processes the 29 filing/register
sources while checking code/label discrepancies across the entire source set.
The local Colossus lookup fell from 3.126 to 0.661 seconds; these are isolated
helper timings, not total page-load or universal performance guarantees.
Private observations and the new reference panel are excluded from public static
output. Existing recorded numbers remain visible without becoming verified rights.

## Original Colossus grant

The [original filing](https://patents.google.com/patent/USPP33802P3/en) and its
linked nine-page grant were inspected. All nine pages had text extracted; pages
1, 3, 5 and 6 were visually reviewed. Claim 1 is on PDF page 3, printed column 6;
fruit figures are on pages 5 and 6. The source observation accounts for the focal
Colossus / FL11-35 record and four parent/comparison names separately. It does
not assign the focal grant to those other names or create new role/trait/region
decisions. The PDF hash and page scope are in the source observation manifest.

Native browser review confirms the profile's recorded number, UF breeding-program
link, unreviewed filing links and collapsed scope disclosure. The claims target
was opened and its claim text was read in the browser; the original PDF text and
selected pages were checked separately. Illustrations remain document links;
no patent image has been copied into a gallery or given reuse permission.

The bounded audit is now 367 sections / 1,143 name occurrences / 73 matched
occurrences / 1,070 requiring review / 789 public derived candidate keys. Canonical
varieties remain 64 and photo references remain 122. A new reference to an
existing variety is not catalog growth or a global-completeness claim.

## Verification and remaining mission

59 affected tests pass, one existing ReportLab warning, 69.46 seconds. They cover
human decision preservation, ambiguity/crop/conflict handling, URL safety,
current and legacy profile rendering, public exclusion, original-page accounting
and avoiding unrelated catalog reconciliation.
The final 1,755-page static/Pagefind build and record validation pass. All 1,755
generated HTML pages were scanned for the new private filing panel/source ID
and claim/figure links; none are present.

All 2,771 original canonical JSON
files and the expansion guide remain unchanged. The 32 pending source copies,
their earlier body hashes and the real pending draft bytes remain preserved;
no human source decisions or extraction-ready IDs were created.

The broader CAT-01/CAT-02/TD-116 requirements remain open: complete current and
historical portfolios, original corpus, current official rights, cited traits,
photos/regions, independent human recall and real human catalog authoring.
Phone visual review and the integrated tested release are still required.
Blueberry feedback gates other Landscape berries; this change is a draft, with
no merge or deployment. Exact-head CI must be checked after pushing.

The initial full CI on `49593bbc7b644226a4b74643d3b8bd44f303c9c2`, run
37998245608, passed scope, integrity and public safety but failed an older
missing-data wording assertion: **4,573 passed / one failed / 11 skipped / two
warnings / 638.24 seconds**. Arana still shows its missing trait and patent
reference states; the fixture expected the replaced text “no patent number
recorded.” It now checks “No patent reference linked.” and confirms that no
original filing panel is invented for that variety. Fresh repaired-head CI
remains required; this failed run is retained in the verification artifact.

All47 synthesis/profile regression checks pass after that fixture repair, one
existing warning,62.00 seconds. Application behavior and source data are unchanged
by the repair; fresh pushed-head CI remains required.
