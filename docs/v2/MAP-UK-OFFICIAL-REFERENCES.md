# UK official fruit-table references for Map

The Map reference workflow gains a separate **Check UK figures** action.
It reads the current Defra publication page, the linked official ODS workbook
and its matching release notice. Three named rows are supported: Strawberries,
Raspberries and Blueberry. Blackberry is not reported separately; mixed or other
soft fruit totals are never allocated to a named crop. No paid API or background schedule
is added, and opening any page never collects data.

The actual October 31 capture returns three 2025 country/crop references and
nine source-linked figures. Planted area is in hectares; marketed production is
in thousand tonnes; reported marketed yield is in tonnes/hectare. Yield is read
from Table 5, never calculated. These are provisional estimates, not verified
claims, current-year estimates or total-harvest measurements. The current source
is published June 25, 2026; that publication date remains separate from capture.

The workbook’s published cell rounding is retained for display. Every selected
cell keeps its untouched cached number, displayed text, sheet/row/column/year
locator and the original complete workbook in the private capture. No workbook
formula is evaluated or changed. Dates, year headers, crop labels, original
units and displayed/cached agreement are checked before creating proposals.
Older panels with repeated crop names cannot replace current-year data.

## A source difference remains visible

The source notice gives strawberry area as 4,602 hectares and raspberry area as
1,344 hectares, while the workbook gives 4,427 and 1,314 respectively. This
capture does not resolve the coverage/revision difference. Both originals are
linked and the differing figures appear above those crop comparisons. A missing
comparison remains explicitly unresolved; agreement or absence does not become
a fabricated discrepancy. Glasshouse fruit is tabulated separately, and no
whole-crop acreage total or country sum is inferred.

The saved references keep these qualifications. The analyst still must inspect
and select each country/crop; nothing is applied after collection alone. Shared
selection/history and stable IDs reuse the existing workflow. Eurostat jobs
without a source field remain readable without rewriting. A job cannot accept
figures from a different requested source. UK figures do not replace Eurostat,
USDA or other crops, and the public reference seed remains unchanged.

## Boundaries and validation

The transport has no credentials or redirects and streams each response under a
byte ceiling: 1MB for each of the two pages and 2MB for the workbook. Only the
publicly linked expected GOV.UK asset location is accepted. ODS XML has member,
expanded-size, row/column and ambiguity limits; entity declarations are rejected.
Source errors retain prior references and raw captures remain private. This is
an extension of the existing explicit manual statistics job, not an intelligence
collector, new schema, new review store, normalization change or trust shortcut.

All 159 affected checks pass with one existing ReportLab warning. Actual keyless
capture, canonical validation and desktop/412px native review pass; the phone
has no horizontal overflow. The final one-page app-export PDF passes visual review. A 1,797-page trusted
static/Pagefind build passes, with all 15 new unselected source URLs absent
from public HTML. Initial head0c7588ae passes all four checks and5,527 tests. Eight added
resource/failure checks now pass within the159-test affected set. Application,
source data, native/PDF and static outputs are unchanged; the final test-only
head needs its own full CI, tracked with the draft review. Full release acceptance still needs
then-current canonical integration, a bounded production-copy check and actual
scoped release approval. The 31 original accepted requirement definitions/order,
protected expansion guide and all canonical records remain unchanged.

This follows tested Map draft #446 at 785fb443. Navigation #443 and source #444
are excluded; live #442 is not changed by this draft. The combined review
captures offer 24 country/crop references and 51 figures across eight countries,
with different reporting bases kept separate. Wider world/crop coverage,
FAOSTAT access and actual human source/figure decisions remain open.

Sources:

- [Defra publication and original dataset](https://www.gov.uk/government/statistics/latest-horticulture-statistics)
- [2025 notice, methods and provisional/revision policy](https://www.gov.uk/government/statistics/latest-horticulture-statistics/horticulture-statistics-2025)
- [Original June 25 workbook](https://assets.publishing.service.gov.uk/media/6a327c196422bec01b1176a1/hort-dataset-25-20260625.ods)
