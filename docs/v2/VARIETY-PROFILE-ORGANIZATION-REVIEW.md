# Variety profiles: show existing companies and breeding programs

The profile-gap table omitted breeding programs and brands and counted inactive
or proposed company relationships. It now uses the directory's existing active
organization scope, preserving each recorded role and its typed profile link.
Trial operators are included. An active breeder relationship does not make a
proposed ownership relationship active.

Following the program link exposed a second discrepancy: a program without a
company portfolio showed zero varieties in its overview and Varieties tab. Those
two views now share active program/brand links from the same directory scope.
The program heading identifies its actual type; its table lists names, roles and
berries. It does not manufacture a company dossier, location coverage or competitor
metrics. Source-only discoveries stay separate. The unavailable company-portfolio
link is replaced by the existing variety directory.

This repairs presentation of existing records. It creates no identities, aliases,
roles, traits, region entries, patent approvals or photo permissions. Source-page
mentions and breeder text alone still do not count as linked organizations.
The `companies` filter key is retained so existing bookmarks continue to work.
The visible heading is **Companies & programs**, with brand scope explained in
the collapsed field guide.

## Measured catalog result

Across all **64 unchanged catalog profiles**, missing organization links fall
from **14 to 10**. The four corrected entries are **Rutgers D'Light, Crimson Night,
Crimson Treasure and Double Gold**. Other already-linked profiles also show their
existing program and trial roles. These counts describe field presence, not
independent validation, current ownership or complete commercial coverage.

The fresh whole-catalog inventory records **53 without photo references,
35 without patent/PVR references and 33 without cited traits**. These categories
overlap. The rights count reflects earlier original-filing work; this role fix
does not change any photo, rights or trait row. The ten remaining organization
gaps include two existing Example records, which are retained unchanged rather
than silently excluded.

## Verification

Native desktop review shows the [corrected Rutgers row](../../artifacts/variety-profile-organizations-2026-10-10/rutgers-program-link.png)
and the [ten remaining organization gaps](../../artifacts/variety-profile-organizations-2026-10-10/remaining-organization-gaps.png).
The catalog denominator stays 64; the other missing fields remain visible.
No review/edit forms were submitted. Actual phone verification remains open.

Record validation and the full 1,755-page render passed. Pagefind initially
failed with a Windows access-denied error; its failed output step was retried
successfully on the host. The initial test run had **55 passes and 17 fixture
setup errors** because the default temporary directory denied access. The final
retry uses a new workspace-local temporary directory and separate cache and
passes **72 tests**, with one existing ReportLab warning. Its wall-clock duration
includes a disconnected/sleeping host and is not a performance measurement.
The additional program overview/tab fix passes **77 affected tests**, one existing
ReportLab warning, 365.55 seconds. A fresh complete **1,755-page build and Pagefind
index** also pass on the final application code. Existing files and permissions
were not reset to bypass the earlier environment problem.

Native browser review confirms the program overview shows one linked variety and
its Varieties tab opens the existing Rutgers D'Light profile. The
[program table](../../artifacts/variety-profile-organizations-2026-10-10/program-variety-links.png)
keeps source-only discoveries separate. The
[verification manifest](../../artifacts/variety-profile-organizations-2026-10-10/verification.json)
records counts, tests and preservation. These checks do not complete phone review,
the whole combined release or independent source recall.

All 2,771 original data JSON files, the governing guide, 32 pending source copies
and original pending draft are preserved. Parent draft [#391](https://github.com/samsonFive/berry-intelligence-os/pull/391)
passes all four required checks, including **4,622 Python tests / 11 skipped**.
This change requires its own pushed-head checks.

The initial full CI run on `81612406515970c0a56bf5c2d3978db755a2d165`
reported **4,626 passed / one failed / 11 skipped / two warnings**. The remaining
failure expected the obsolete "Reviewed variety links" heading in the older
Georgia program/source-context regression. That assertion now expects "Recorded
variety links" and still verifies source-only names, the existing source handoff
and unchanged private state. The accurate heading does not approve source names.
All **16 affected source-context/program tests pass**, one existing ReportLab
warning, 108.80 seconds. The repaired head requires a fresh full CI result.

## Remaining mission

The [31-requirement checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md) retains the full
approved redesign, consolidation and explainer scope. CAT-01, CAT-02 and TD-116
remain open for full current/historical portfolios, original text, independently
reviewed recall, human catalog decisions and richer source-backed profiles.
The actual 32-source expected-name worksheet remains unfinished. Phone visual
verification and combined-release checks remain open. Blueberry feedback gates
other Landscape berries; separate approval gates merging and deployment.
