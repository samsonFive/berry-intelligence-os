# Original patent links for seven Florida blueberries

## Result

Seven profiles had a plant patent number but no linked original source: Emerald,
Farthing, Jewel, Meadowlark, Optimus, Patrecia and Sentinel. The original published
documents are now collected as unreviewed reference observations. Their first
pages were rendered and visually checked for patent number, printed cultivar
name or accepted code, blueberry scope, application number and historical dates.
The canonical 64 varieties, aliases, company roles, traits, locations and human
decisions are unchanged. These references do not establish current legal status.

| Profile | Printed denomination | Original document |
|---|---|---|
| Emerald | Emerald | [USPP12165P2](https://patentimages.storage.googleapis.com/ad/95/81/e9f943e5aea7e9/USPP12165.pdf) |
| Farthing | Farthing | [USPP19341P2](https://patentimages.storage.googleapis.com/55/0f/b6/3d3113484d984c/USPP19341.pdf) |
| Jewel | Jewel | [USPP11807P2](https://patentimages.storage.googleapis.com/d1/67/6d/f170d1593c0f4a/USPP11807.pdf) |
| Meadowlark | FL01-173, already an accepted catalog alias | [USPP21553P2](https://patentimages.storage.googleapis.com/1b/46/9a/cb357405a77ea2/USPP21553.pdf) |
| Optimus | OPTIMUS | [USPP32028P3](https://patentimages.storage.googleapis.com/15/3a/27/c7712b8f884baf/USPP32028.pdf) |
| Patrecia | Patrecia | [USPP27740P2](https://patentimages.storage.googleapis.com/4f/75/c2/cd7f8ee671e196/USPP27740.pdf) |
| Sentinel | Sentinel | [USPP33896P2](https://patents.google.com/patent/USPP33896P2/en) · original PDF pointer retained in the snapshot |

## False code conflicts

The existing matcher treated a denomination repeating its cultivar name as a
breeding code. For example, the Emerald filing's denomination Emerald conflicted
with the recorded selection code FL 95-209a, so the original link disappeared
when the whole portfolio corpus was included. A source containing only a legal
denomination does not assert another code or assert that no breeding code exists.

The correction preserves an explicit breeder code and checks real distinct
code/label pairs. Multiple actual codes, bare corporate names versus coded
releases, ambiguous catalog names, wrong crops and saved human identity decisions
still require review. No new alias, role, qualification or trusted record is
created. The original source dictionaries are unchanged.

## Validation and scope

Two new regressions fail before the correction; all six new cases and the
existing portfolio/original-reference suites pass afterward: 42 tests, one
existing ReportLab warning. A separate read-only check against the actual 395
portfolio sections, 49 register observations and saved candidate state links all
seven existing profiles without persisting decisions. Full CI and browser review
still gate this follow-up draft.

This work is isolated from the tested software release at 1fb75b61, which remains
unchanged while awaiting release approval. All 31 requirements, the original
32-source human worksheets and broader CAT-01/CAT-02 work remain. Public metadata
and document pointers are committed; raw HTML/PDFs and rendered source pages stay
in the ignored local review folder. No patent photographs receive reuse approval,
and no merge or deployment occurs.
