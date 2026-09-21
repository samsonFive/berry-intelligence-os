# Berry Intelligence OS Office Dogfood Field Guide

Use this guide to test the production release at
<https://intel.johnnyaceii.com>. The release adds complete documented
resolution of the supplied 77-name competitor registry and a persistent
**Variety Database** navigation item. It also includes the separately reviewed
Entity Dossier Gate 3A change when the release report identifies PR #266 as
merged.

## Release record

- Production URL: <https://intel.johnnyaceii.com>
- Exact deployed SHA: use the immutable `canonical_sha` returned by production
  `/healthz`; it must equal the checkout, container environment, and exact SHA
  printed in the release report delivered with this guide.
- Test date: 2026-09-21
- Tester: ______________________________________________
- Browser and version: __________________________________
- Device and operating system: ___________________________
- Screen size: ___________________________________________

**Status choices:** PASS / PASS WITH FRICTION / FAIL / NOT TESTED

**Severity choices:** P0 demo stopper / P1 core workflow or trust failure /
P2 meaningful friction or UI problem / P3 polish

For every failure, capture the URL, action, screenshot, time, status, severity,
and what happened. Do not approve, publish, or confirm untrusted material merely
to complete a test.

## A Fifteen minute manager confidence pass

| Test ID | Action | Expected result | Status | Evidence or screenshot | Severity | Notes |
|---|---|---|---|---|---|---|
| M01 | Sign in at `/login`. | Login succeeds and `/` redirects to `/today`. |  |  |  |  |
| M02 | Review News without changing filters. | A populated seven-day experience appears; stored-news fallback is usable if live retrieval is unavailable. |  |  |  |  |
| M03 | Open one article in Reader, then close it. | Reader opens over the current view and returns focus on close. |  |  |  |  |
| M04 | Inspect headline, source, summary, dates, and article body cleanup. | Content is readable, attributed, and free of obvious navigation or boilerplate debris. |  |  |  |  |
| M05 | Apply one News filter and clear it. | Results and URL state update; clearing restores the seven-day view. |  |  |  |  |
| M06 | Open Entities from the left rail. | Dense roster loads with counts, filters, A-Z navigation, and search. |  |  |  |  |
| M07 | Search for `ABZ Seeds`. | One canonical ABZ Seeds card appears and opens a stable detail route. |  |  |  |  |
| M08 | Select one letter in A-Z navigation. | The roster moves to the expected records without losing shell navigation. |  |  |  |  |
| M09 | Open Planasa at `/entities/company/company-planasa`. | The Planasa dossier loads with identity and sourced intelligence sections. |  |  |  |  |
| M10 | Explain Planasa to another tester within 30 seconds. | The dossier makes company identity, genetics, geography, relationships, and evidence state understandable without invented conclusions. |  |  |  |  |
| M11 | Click **Variety Database** in the sidebar. | The existing `/entities/variety` database opens; no duplicate variety experience appears. |  |  |  |  |

Manager pass disposition: _________________________________________________

## B Complete competitor coverage test

The authoritative 77-row audit is
[`reconciliation-matrix.md`](../../data/imports/competitor-coverage-registry-2026-09-21/reconciliation-matrix.md),
with the machine-readable contract beside it in `reconciliation-matrix.json`.
It records canonical IDs, statuses, types, relationships, websites, actions,
and the two specific exclusions. The release outcome is 35 newly added
canonical entities, 40 existing/alias/relationship/corrected-duplicate
resolutions, and two justified exclusions.

Spot-check every row with `ADDED_CANONICAL_ENTITY`; do not infer that a website
or a sparse profile is missing if the matrix intentionally leaves the field
blank. A visible “Details to be confirmed” state is acceptable and safer than
fabricated profile data.

| Test ID | Action | Expected result | Status | Evidence or screenshot | Severity | Notes |
|---|---|---|---|---|---|---|
| C01 | Compare all 77 input lines with the linked matrix. | Exactly 77 unique inputs have one accepted resolution status and no unexplained omission. |  |  |  |  |
| C02 | Search every canonical name marked `ADDED_CANONICAL_ENTITY`. | Each represented canonical entity appears in Entities exactly once. |  |  |  |  |
| C03 | Search `Benning Blueberries`, then `Denning Blueberries`. | Both resolve to the single corrected Benning identity using stable ID `company-denning-blueberries`. |  |  |  |  |
| C04 | Search `Novisiri Genetics`, `Berryplant`, `FNM`, and `Berryum`. | Each alias resolves to Nova Siri Genetics, Fall Creek Italy, Fresas Nuevos Materiales, and BerrYum respectively. |  |  |  |  |
| C05 | Search `Fruitist` and `Agrovision`. | Both labels reach one Agrovision/Fruitist card, not duplicate cards. |  |  |  |  |
| C06 | Inspect AgroBerries / BerryWorld. | Two distinct canonical identities remain; acquisition context is documented without collapsing them. |  |  |  |  |
| C07 | Inspect Berryplant / Fall Creek. | Fall Creek Italy/Berryplant remains distinct from the Fall Creek parent identity. |  |  |  |  |
| C08 | Inspect Mountain Blue Orchards / The Berry Collective and the separate The Berry Collective row. | Distinct canonical identities are reused; the venture relationship does not create a duplicate Collective. |  |  |  |  |
| C09 | Check websites and entity types against the matrix. | Only documented websites/types appear; blank unsupported values remain blank. |  |  |  |  |
| C10 | Open each newly added entity detail route. | Every route returns successfully and preserves the canonical ID. |  |  |  |  |
| C11 | Inspect filters and A-Z navigation after several searches. | Counts remain honest and controls remain usable. |  |  |  |  |
| C12 | Look specifically for duplicate cards or confusing combined identities. | No obvious duplicate identity is present; report any ambiguous parent/brand/partnership display. |  |  |  |  |

## C Variety navigation test

| Test ID | Action | Expected result | Status | Evidence or screenshot | Severity | Notes |
|---|---|---|---|---|---|---|
| V01 | From News, click **Variety Database**. | `/entities/variety` opens. |  |  |  |  |
| V02 | From Entities, click **Variety Database**. | The same existing database opens. |  |  |  |  |
| V03 | From the Planasa dossier, click **Variety Database**. | The same existing database opens. |  |  |  |  |
| V04 | From Learn, click **Variety Database**. | The same existing database opens. |  |  |  |  |
| V05 | Repeat V01-V04 at desktop width. | The item is in persistent navigation, readable, and keyboard reachable. |  |  |  |  |
| V06 | Repeat from the mobile navigation at 360 x 800. | The item is present, tappable, and causes no horizontal overflow. |  |  |  |  |
| V07 | Observe navigation on the variety index and one variety detail. | Active/current state is visible where the shell supports it. |  |  |  |  |
| V08 | Confirm destination and page contents. | There is one canonical variety experience at `/entities/variety`; no new database or alternate route exists. |  |  |  |  |

## D Core analyst workflow

| Test ID | Action | Expected result | Status | Evidence or screenshot | Severity | Notes |
|---|---|---|---|---|---|---|
| A01 | Review the News default and dates. | The intended seven-day view is clear and freshness is not overstated. |  |  |  |  |
| A02 | Exercise berry, source, status, and time filters that are available. | Filters produce coherent subsets and can be cleared. |  |  |  |  |
| A03 | Scan ten compact cards. | Cards remain dense, readable, and distinguish record type from status marks. |  |  |  |  |
| A04 | Open Reader from a card. | Reader shows title, provenance, state, and readable content without changing trust. |  |  |  |  |
| A05 | Use Reader previous and next controls. | Adjacent items load in the same Reader. |  |  |  |  |
| A06 | Press Escape in Reader. | Reader closes and focus returns to the triggering control. |  |  |  |  |
| A07 | Try Save, Useful, and Not relevant on appropriate test items. | Each action has distinct copy and behavior; none implies publication or factual trust. |  |  |  |  |
| A08 | Inspect available extraction information. | Suggestions remain visibly untrusted and retain provenance. |  |  |  |  |
| A09 | Review a statement-confirmation workflow without confirming unless authorized. | Original wording, supporting evidence, and human gate are clear. |  |  |  |  |
| A10 | Trace Evidence provenance. | Source, date, link, and state are visible; no private draft appears as trusted. |  |  |  |  |
| A11 | Return to an entity dossier after reading related intelligence. | The dossier adds context without flattening Facts, Claims, Signals, Assessments, or educational knowledge. |  |  |  |  |

## E Supporting surfaces

| Test ID | Action | Expected result | Status | Evidence or screenshot | Severity | Notes |
|---|---|---|---|---|---|---|
| S01 | Open Following. | Monitored identities are understandable and roster counts remain honest. |  |  |  |  |
| S02 | Open Saved. | Saved work is distinct from trusted or published work. |  |  |  |  |
| S03 | Open Statements. | Statement state, provenance, and review controls are clear. |  |  |  |  |
| S04 | Open People. | Page loads and person identities do not masquerade as companies. |  |  |  |  |
| S05 | Open Landscapes. | Coverage caveats are visible; counts are not presented as strength scores. |  |  |  |  |
| S06 | Open This week. | Recent items are dated and state-labeled. |  |  |  |  |
| S07 | Open Learn. | Educational knowledge is labeled and never presented as Fact or Evidence. |  |  |  |  |
| S08 | Open War Room. | Page loads and retains the shared shell. |  |  |  |  |
| S09 | Open Watchtower. | Watches and alerts remain distinct; a Watch does not confirm a Signal. |  |  |  |  |
| S10 | Open Research Ops. | Operational state is separated from intelligence truth. |  |  |  |  |
| S11 | Open Settings. | Page loads without exposing secrets or private runtime paths. |  |  |  |  |
| S12 | Open Claim Testing. | Claims remain claims; pass/fail does not create a Fact. |  |  |  |  |

## F Feedback capture

### Defect log

| Defect ID | Test ID | Summary | URL | Status | Severity | Evidence | Owner | Notes |
|---|---|---|---|---|---|---|---|---|
| D01 |  |  |  |  |  |  |  |  |
| D02 |  |  |  |  |  |  |  |  |
| D03 |  |  |  |  |  |  |  |  |

### Iteration backlog

| Backlog ID | Observation | User impact | Proposed next step | Priority | Owner |
|---|---|---|---|---|---|
| B01 |  |  |  |  |  |
| B02 |  |  |  |  |  |
| B03 |  |  |  |  |  |

### Release reflection

Three strongest features:

1. ______________________________________________________________________
2. ______________________________________________________________________
3. ______________________________________________________________________

Three biggest confidence killers:

1. ______________________________________________________________________
2. ______________________________________________________________________
3. ______________________________________________________________________

What to demonstrate to the manager:

__________________________________________________________________________

What to avoid demonstrating until corrected:

__________________________________________________________________________

Next mission in one sentence:

__________________________________________________________________________

Final release disposition: PASS / PASS WITH FRICTION / FAIL / NOT TESTED

Tester name and date: _____________________________________________________
