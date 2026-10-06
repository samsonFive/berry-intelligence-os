# Mission 17 — Named intelligence authoring

Built on draft #289 head `b7be3e352a4e3e47878c0ea713112ba4309fb967`, all four checks passed (3,585 tests / 11 skipped / two warnings). Continues the approved plain-language and hierarchy requirement into New Signal, New/Edit Assessment and New Recommendation. The original save/update routes and human-authored record schemas remain.

## Forms and reference selection

All three form templates share Glasshouse Intelligence navigation, distinct heading/field/help roles, a compact two-column reference layout and a one-column phone layout. Title, rationale/description, status/confidence/direction/priority, berry scope, dates, reviewer and action type retain their existing names and submitted values. Berry scope stays explicit, never inferred. Action examples now use human-readable language.

References can be searched by company/name/title/statement wording, rather than requiring users to paste internal IDs. The catalog contains only existing canonical subjects, questions, Signals, Assessments, statements and published sources. Source bodies, private candidate/draft text and AI output are not serialized into the catalog. Statement choices retain their actual classification; a claim never becomes a Fact by selection. Counterevidence offers both existing statements and published sources, matching the established backend validation.

Search displays at most 30 matching choices at a time, with the total and refinement hint. Multiple selections are visible, removable and keyboard accessible. Different company/program identities retain their original IDs. Selection updates only the original comma-separated form field; no new persistence contract, API or automatic save is introduced. Initial rendering never rewrites raw values. Legacy question titles resolve for display while retaining the original submitted value until an explicit selection change. Unavailable references remain visibly unresolved and in the original field until explicitly removed; they are never silently dropped.

Direct reference IDs remain in closed native disclosures, including the original text input as a no-JavaScript fallback. Search Enter cannot submit the authoring form accidentally. Choice toggles keep focus on the same choice after rerender; removal returns focus to its chooser. Catalog JSON uses the existing escaped template serializer; dynamic names/wording render through text nodes, not HTML injection.

## Gates and preservation

Read-only rendering hides form/catalog data and the catalog helper returns before loading records. Existing save/update authoring guards remain; same-origin/cross-site checks now run before canonical lookup or mutation. Existing reviewer requirements, reference validation, schemas, created/updated dates, unknown-reference errors and explicit save actions remain. Publication, atomic evidence, identity and model qualification decisions are untouched. This slice does not add recommendation editing or silently repair invalid stored references.

## Verification

Local combined form/catalog/privacy, assessment-scope, app and guided-analyst tests: **153 passed, 145 existing dependency warnings, in 35.97 seconds**. Tests cover unchanged literal qualifications and edit fields, unavailable-reference retention, metadata-only catalog serialization, actual claim classification, no read-only record access, and all four create/update endpoints denying cross-site before access/write. Existing isolated create/update tests exercise the unchanged record contracts. One old visible-label assertion was updated for Supporting sources while still asserting the original field name. One new fixture used the wrong update-helper name and was corrected; no application gate was weakened.

Canonical records validated and JavaScript syntax passed. Static generation wrote **1,755 pages** and reported no unpublished IDs or titles. Exact pushed-head CI remains required.

Browser review used the isolated loopback preview. Assessment named selection distinguished Planasa's breeding program from its company and retained `company-planasa`; adding Hortifrut retained both IDs and focus. Adding an intentionally unavailable form reference through the fallback retained it alongside both companies and displayed an unresolved chip. These were unsaved form edits, not canonical writes. Signal and Recommendation forms were reviewed on desktop/390px; all reference-ID disclosures started closed. At 390px the page measured 375px, choice containers had no horizontal overflow, and the Recommendation save button measured 45px high. Temporary viewport overrides were reset.

Screenshots under `artifacts/design-sprint/`: Assessment selection desktop/mobile and Signal/Recommendation forms desktop/mobile. No real save/update, human trust decision, web/model call or article fetch was performed during browser review. The production catalog is unpaginated metadata; browser option rendering is bounded. Larger-corpus loading/duplicate-label disambiguation and final account/release acceptance remain to be assessed.

## Remaining work

Final draft #290 head `aa76992cc08aae7e1f40f1d25c0483d19bf17b93` passed Change scope, Repository integrity, Static public safety and Python tests, run `37066747850`: **3,602 passed / 11 skipped / two warnings in 289.55 seconds**. The focused caption/form/scope rerun had 28 passed / one warning in 7.90 seconds. Combined canonical release remains open.

Initial draft #290 head `05a12af9128f097b920da7975e10253df6912d48` passed Change scope, Repository integrity and Static public safety. Python tests run `37065661356` had 3,601 passed / one failed / 11 skipped / two warnings in 253.18 seconds. The failure was another stale visible-caption assertion in the decision-workflow regression. Its expectation now uses Supporting statements while explicitly checking the unchanged `fact_ids` field and minimum-statement hint. A fresh exact-head check set is required; this result is not treated as a green release.

These forms close the everyday internal-ID authoring interface, not the entire specialist/static layout audit. Wider licensed learning visuals, manual-logo acceptance/protected enrichment, region/source suggestions, public market statistics, fresh news/article/media acquisition, packet compatibility, account/inter-process persistence and canonical/active-PR reconciliation remain on the checklist. Current canonical-targeting PRs #255, #270 and #271 are still open alongside the redesign stack and require deliberate reconciliation before release. Prepare a tested combined release/rollback review; do not merge/deploy without final human approval.
