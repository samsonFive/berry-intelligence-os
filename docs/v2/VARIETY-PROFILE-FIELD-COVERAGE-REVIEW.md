# Find the missing information in variety profiles

Variety coverage now includes a dense, alphabetical field table for each catalog
profile. Search by name, scope by berry, or show profiles without photo references,
patent/PVR references, cited traits or company role links. The variety and company
names open their existing profiles. Missing information is visible alongside
unreviewed references and permission-held photos, without a completeness score.

Review branch: `feature/variety-profile-field-coverage`, stacked on draft #380.
Actual isolated review: `http://127.0.0.1:18572/varieties/coverage#profile-field-coverage`.
Source polling is disabled. No identity/source/claim/photo forms were submitted.

## What the table measures

| Field | Counted information | Boundaries |
|---|---|---|
| Photos | Existing source gallery after user additions/hides/overrides | Unknown reuse remains visibly held; a reference is not a reusable image. The table does not load images or expose their asset URLs. |
| Patent / PVR references | Linked patent entities, including existing explicit patent/rights pointers; published rights-source records; separately labeled unreviewed original patent/register observations | A free-text number alone does not fill the gap. References can describe the same filing; they do not establish current status, enforceability or ownership. |
| Traits | Structured profile entries and retained trait statements with a citation to an existing published source | Missing/draft citations and proposed statements do not count. Entries can be owner claims; counts do not establish independent measurement. |
| Company roles | Existing company-to-variety relationship records, keeping breeder, rights holder, licensee, marketer, grower and distributor distinct | A breeder text string or a company name on a portfolio page does not create a role link. These are recorded links, not inferred commercial reach. |

The existing whole-source reconciliation supplies patent-observation matches,
including ambiguity, code/label discrepancy and saved human-decision handling.
Its results are reused independently of the separate portfolio table's filters.
The permission-aware photo gallery remains authoritative for user photo edits.
This is presentation over existing records, without new schemas, qualification,
canonical authoring, provider calls, footprint queries or persisted conclusions.

## Actual gaps and browser checks

Among the current **64 catalog profiles**, **53 have no photo reference, 36 have
no patent/PVR reference, 33 have no cited trait entry and 14 have no company role
link**. These categories overlap. They do not measure the 788 discovered candidate
keys, every possible profile field or the world's varieties. Missing references
do not mean that no photo or right exists elsewhere.

Native browser review verified all 64 rows, the 53-row missing-photo filter and
the actual Colossus search result. Colossus has one permission-held photo,
nine cited profile/statement entries and separate licensee/breeder links; it
has no linked patent reference in this bounded inventory. It is excluded from
the missing-photo result. No photos were revealed during this coverage review.
DrisBlueSeventeen shows two linked records, four cited entries and distinct
breeder/rights-holder links. Its existing explicit rights pointer contributes a
reference without inferring current legal status or treating two references as
two different filings. See the [rights result](../../artifacts/variety-profile-field-coverage-2026-10-09/drisblue-rights-review.png).

The [desktop table](../../artifacts/variety-profile-field-coverage-2026-10-09/desktop-missing-photos.png)
and [Colossus result](../../artifacts/variety-profile-field-coverage-2026-10-09/colossus-field-review.png)
show the final hierarchy and handoffs. The current native browser kept its actual
1280px viewport after a requested 390px override, including after navigation.
The override was reset; **phone visual verification is still outstanding**.
No desktop image is presented as phone proof. The stylesheet provides contained,
keyboard-focusable table scrolling and 44px phone filter controls, but CSS rules
are not a substitute for a real phone browser check before the combined release.

## Verification and performance

**84 affected tests pass**, one existing ReportLab warning, 103.45 seconds.
This includes all **ten field-inventory tests** and the final accessible labels
and explicit patent/rights pointers. Tests cover missing/draft citations, proposed
trait statements, number-only patents, distinct company roles, ambiguous aliases,
wrong crops, permission-held photos, user-hidden photos, unchanged inputs, scoped
denominators, reused unfiltered reconciliation, read-only GET and authoring-only
visibility. They do not certify source authenticity or independently reviewed recall.

The first implementation repeated reconciliation and took **11.346 seconds**
to inventory all 64 profiles. Reusing the existing request's whole-source result
reduced the final measured additional inventory work to **2.418 seconds**, with identical
gap counts. This measures the inventory function, not total route latency or a
production performance guarantee. No long-lived cache can mask changed edits.

Record validation, the 1,755-page static/Pagefind build and preservation checks
pass. The public snapshot excludes this private field table. All original 2,771
canonical JSON files, the expansion guide, 32 pending source copies and the real
pending draft remain unchanged. Parent photo draft #379 passes all four checks on
`b6b9e86389fea2ad6c24609fe487e4945eb0697b`: **4,553 passed / 11 skipped /
two warnings / 759.59 seconds**. Documentation draft #380 is all-green on
`46bbcba4ffa6ad4fc46c283956eb8c8b01db122d` via its required Markdown fast path.
This application draft requires its own full CI.

The first draft #381 full run passed scope, integrity and static safety, but its
Python job had **4,562 passed / one failed / 11 skipped / two warnings / 510.08
seconds**. The remaining source-status test expected the superseded stylesheet
version6 rather than the new version7. The explicit cache-version assertion was
repaired; a fresh exact-head full CI run is required before calling the draft green.
The repair passes all **18 source-status/field-inventory tests**, one existing
ReportLab warning, 32.95 seconds. It changes the test assertion only; the final
application code and native screenshots are unchanged.

## Remaining work

Use these gaps to prioritize actual source-backed profiles and human authoring.
CAT-01, CAT-02 and TD-116 remain open: complete current/historical portfolios,
original corpus, current official rights, attributed photos, growing regions,
independent multi-berry recall and actual human identity/catalog decisions are
still required. The 32-copy human expected-name packet remains unfinished.
Blueberry feedback still gates other Landscape berries. Integration, phone review
and exact-head release checks remain before separate merge/deploy approval.
