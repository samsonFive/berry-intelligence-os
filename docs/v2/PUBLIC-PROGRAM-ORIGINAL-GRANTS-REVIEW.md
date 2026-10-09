# Historical releases: original grants and fruit figures

Onyx, APF-77 / Black Magic and Columbia Giant now have original US grant
references in their existing identity-review entries. Each reference opens
the actual cultivar claim page and shows the printed filing and grant dates.
APF-77 and Columbia Giant also have attributed original fruit figures, held
until the user chooses the existing session-only **Ignore permission** control.
No canonical variety or human review decision is created.

Review branch: `feature/public-program-original-grants`, stacked on
`feature/public-program-release-coverage` (#375).

## Original documents checked

| Cultivar | Original grant | Filed | Granted | Claim location | Fruit figure |
| --- | --- | --- | --- | --- | --- |
| Onyx | [USPP22358P2](https://patents.google.com/patent/USPP22358P2/en) | 2010-02-22 | 2011-12-20 | PDF page 3, column 6 | Figure 2, PDF page 5; document link only |
| APF-77 | [USPP24249P3](https://patents.google.com/patent/USPP24249P3/en) | 2011-12-29 | 2014-02-18 | PDF page 4, column 8 | Figure 2, PDF page 6 |
| Columbia Giant | [USPP28369P3](https://patents.google.com/patent/USPP28369P3/en) | 2015-09-28 | 2017-09-12 | PDF page 4, column 8 | Figure 3, PDF page 7 |

Browser-observed download URLs supplied the original PDFs. All 22 pages were
rendered and visually inspected; claim pages were inspected at full size.
Hashes, page counts, visual-review page lists and non-portfolio context are
retained in the observation manifest. Original PDF bodies and local renders
remain in ignored `inbox/`; the committed data contains metadata and links.

Onyx's ORUS 1523-4 selection wording remains source context rather than an
approved alias. Black Magic comes from the separately retained OSU release
list, not from the APF-77 grant claim. Columbia Giant's origin passage says
ORUS 1350-2 while its comparison passage says ORUS 1350-1; the inconsistency
stays explicit and creates no parent relationship. Other parents, ancestors
and comparators are excluded from the bounded focal-denomination scope.

Historical trial conditions do not become universal traits or commercial
growing regions. Printed assignees do not establish current owners or photo
reuse permission. No aggregator legal-status or expiry assumptions are copied;
current rights, licence terms and official current-status searches remain open.

## Photo behavior and actual browser review

The two original figures are low-resolution monochrome scans, useful for
source identification rather than polished marketing imagery. The source
and photographer-not-credited attribution remain visible. No reusable licence
was found, so permission stays `unknown`; no image is loaded by default.
Onyx's browser source exposes no separate figure URL. Its photograph remains
accessible inside the PDF; no asset URL or inline image is fabricated.

Native browser review on `http://127.0.0.1:18568` verified all three candidate
entries and claim-page links. APF-77 and Columbia Giant images both loaded
after **Ignore permission**. **Hide photo** returned each to its held state;
APF-77 reload retained the permission gate. No identity or publication form
was submitted. Actual review captures:

- [APF-77 session figure](../../artifacts/public-program-grants-review-2026-10-09/apf-77-session-photo.png)
- [Columbia Giant session figure](../../artifacts/public-program-grants-review-2026-10-09/columbia-giant-session-photo.png)
- [Onyx original claim reference](../../artifacts/public-program-grants-review-2026-10-09/onyx-claim-review.png)

## Coverage, preservation and validation

The read-only audit now reports **355 source sections / 1,132 name occurrences /
64 catalog-matched occurrences / 1,068 requiring review**. All three additions
enrich existing keys: **788** public derived candidates, **789** in the isolated
preview including its retained private pending article. Counts describe source
occurrences, not approved varieties or global completeness. The canonical
catalog remains 64 varieties. Photo references increase from 112 to 114, with
zero new reuse approvals. The 77-company roster remains 60 named / 14 partial /
one unreadable / zero not started / two identity holds.

- Reconciliation, catalog handoff and photo-gate tests: **92 passed**, one
  existing ReportLab warning, 73.19s. Tests cover stable candidate IDs, no
  inferred aliases/roles/regions, preserved human registration and notes,
  cultivar/species photo matching and held-image exclusion.
- Record validation passes. All 2,771 original data JSON files and the canonical
  expansion guide remain unchanged.
- Private audit preserves 32 pending source copies and their payload hashes,
  plus the real pending article bytes; no new source decision or extraction readiness.
- Static build and Pagefind pass: **1,755 HTML pages**, unpublished draft ID/title
  exclusion and the new observation/figure URL exclusion all pass.
- Parent #375 is all-green on `cf8272f2e81bea47dc47951f7aa28fbf89a7ec8d`:
  **4,525 passed / 11 skipped / two warnings / 458.38s**. New draft CI is separate.

CAT-01/CAT-02/TD-116 remain open: complete current/historical portfolios,
original corpus, deeper cited profiles, usable licensed photos, official current
rights, independent human-qualified recall and human catalog authoring. The
integrated release is not ready for merge or deployment. Revised blueberry
feedback still gates remaining Landscape rollout.
