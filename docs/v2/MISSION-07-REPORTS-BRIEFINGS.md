# Mission 7 — Reports & Briefings / Meeting Prep

In progress on `feature/reports-briefings-consolidation`, stacked on Mission 6 (`1226e66`). Product/UI plus bounded workflow fixes. Final release verification remains pending; no merge or deployment.

The new `/briefings` home organizes existing outputs by task: prepare a meeting, build a selected brief, write an editable report, or create a scoped market snapshot. Executive view, saved briefs and competitor news packets remain linked destinations. A shared Glasshouse reporting shell now wraps the actual meeting, brief, saved-library, report-builder/workspace and live executive pages; it does not replace their query/composition/persistence services. Static Executive Readout continues through the original public base wrapper. Snapshot and News packet integration still need family-navigation review.

Meeting Prep is the product label; `/war-room` and its stored scope/takeaway paths remain compatible. Native repeated geography/company selections and CSV URLs now compose without losing selected IDs. Normal composition passes no AI completer; optional question suggestions require an explicit POST and stay labeled discussion prompts. The old `/war-room/live` bookmark presents a deliberate refresh form; POST invokes the existing bounded live feed refresh. No provider calls were run in browser review. Note matching retains its prior berry plus overlapping geographic/company scope semantics, not a new exact-session or time-window schema.

Report library now defaults to working reports (draft and active), with explicit Drafts/Edited/Archived/All choices. Saving an edit no longer removes the report from the default library. Generated and edited prose remain separate in the existing store. Coverage and known-gap detail is collapsed while report content stays visible. A reporting-family authoring boundary rejects private stores/actions in published-only mode; remote login protections remain unchanged. Default reporting navigation skips the legacy full-pending badge loader.

## Report-image review and preservation

User review rejected the first PDF as an internal-ID dump without hierarchy. Report display now removes only known generated record prefixes; analyst-written text remains literal. Original generated prose, IDs, citations and edited prose remain in their original store. Named scope labels replace slugs. Editing one field leaves unchanged fields untouched; deliberately empty edits no longer restore old generated content. Sources use numbered readable references and original URL links. The app emphasizes the summary and collapses secondary metadata and undrafted sections; available content stays exposed.

PDF now leads with the takeaway in a green highlight, separates title/section/body/metadata sizes, keeps coverage notes behind findings, preserves list breaks and groups source entries across page boundaries. Unavailable narrative is disclosed, not fabricated. A five-page isolated source-backed sample was rendered; its extracted text has no generated `[sig-…]`, `[assessment-…]` or `[ev-…]` prefixes, retains the sample edit and contains 23 original-source links. It is a layout sample with AI disabled, not completed analysis for distribution.

## Evidence so far

- 143 existing reporting/static checks pass before new tests. 161 checks pass including 18 new continuity/private-boundary/provider/scope checks, one known reportlab warning, using `inbox/reporting-test-temp-3`.
- Actual browser review: `/briefings` task home; two geography and two company selections retained in Meeting Prep's headline and report handoff; one sample takeaway persisted under the isolated preview store. The sample is explicitly labeled design review and has not touched production or canonical records.
- New regression tests cover pure default reads, repeated+CSV IDs, explicit feed refresh POST, deliberate AI-question POST, private read/write/export rejection, and edited report save/reopen/library visibility/PDF response without store mutation.
- Further checks cover named repeated report scope, display-only formatting, literal analyst text, deliberately blank edits, unchanged-field preservation, PDF escaping/list breaks and source layout. Latest focused reporting run: 111 pass, one known reportlab warning. An earlier complete local run found two presentation regressions among 3,451 passing checks; saved-pack title visibility was restored and the legacy navigation assertion now expects Meeting Prep. The final exact-head complete-suite rerun is still required.
- Browser verified brief composition/save/presentation/library/duplication, manual company scope → unavailable/structured report draft → saved summary → Working library → PDF download. Both home and report stayed inside a 390px viewport; the override was reset. No production or canonical state changed.
- Record validation passes; static output contains 1,755 pages and passes unpublished draft leakage checks. Final provider, print and combined-release checks remain separate.

## Required before checkpoint PR

- Complete browser brief save/reopen/duplicate/presentation and report manual scope/draft/edit/reopen/PDF download and visual inspection.
- Review 390px/mobile containment and restore temporary viewport overrides.
- Source-rich and sparse reporting views, shared Reader links and scope handoffs; verify refresh/error/unavailable states without paid live calls.
- Complete family navigation for News packets/Market Snapshot without dropping their date/review/region filters or duplicating acquisition.
- Update audit/debt/coverage notes and the visual guide to describe only delivered behavior.
- Records validation, static public-safety build, diff check, commit/push/draft PR and all four required exact-head CI gates.

The ongoing goal remains active beyond this mission. The completion ledger is `REDESIGN-REQUIREMENTS-CHECKLIST.md`. Reports are not a trust shortcut, saved brief selections are not frozen snapshots, and a passing UI slice is not production release integration.

Review images: [Report editor](../../artifacts/design-sprint/report-workspace-live.png) and [PDF layout sample](../../artifacts/design-sprint/report-export-live.png). Both use isolated sample state, not production user edits or completed AI analysis.
