# Mission 35 — Retained workflows in the shared design

The retained analyst tools now use the approved full-width Glasshouse header instead of the old global sidebar. Company and variety comparisons, claim testing, intake, publication history, identity checks, variety coverage and Reader settings keep their original routes and workflow controls.

## Navigation and hierarchy

`base.html` adapts existing content to the shared shell. `base_stakeholder.html` uses the same header, retaining its content styles. The More menu keeps the consolidated workspace homes and groups specialist destinations into Compare & reference, Review & data quality, and Collection & preferences. Specialist links start collapsed; the menu scrolls within the viewport. Existing available queue counts retain their meanings and do not trigger additional ranking. People stays off the navigation; compatibility destinations and data are retained.

The old secondary feed navigation rail is omitted under this shell; directory counts remain in a collapsed coverage disclosure. Berry context, its POST and return query, global search, shared Reader, session sign-out and the original static Pagefind implementation are retained. Placeholder company/geography controls are removed.

Light surfaces, distinct borders, readable headings, compact comparison columns and contained horizontal tables replace the remaining dark shell. Claim wording has a separate reading panel; review-history identifiers start collapsed. Publication history uses plain introductions, with fingerprints and action references folded. Comparison selection still uses the existing search and bookmark IDs. Reader settings now describes newest-first News, date options, company/list filters and Personal Digest; the obsolete ranked feed, separate saved-board and unbuilt-Learn instructions are corrected.

## Verification

193 focused tests passed (one existing ReportLab warning, 58.91 seconds). These include company/variety comparisons, native intake validation and literal-note preservation, query/cookie context, claim dispositions, source authenticity, global search, guide semantics, real static builds and private-body/review-state exclusion. Record validation and whitespace integrity passed. The expansion guide is unchanged; no domain/schema or canonical data edits were made.

Native browser review used canonical data read-only with isolated inbox/review state at `127.0.0.1:18329`. A fictional intake submission remained an unreviewed draft, preserving its literal brackets and source URL. A separate fictional pending publication populated the history view without a review decision. Real company/variety searches added Fall Creek and RedSayra to their comparison URLs. A comparison source opened the shared Reader; its unavailable body was disclosed honestly, with no capture attempted. Global search returned 35 stored results and closed with Escape.

At 390 pixels, tested company/variety comparisons, claim detail, identity checks, variety coverage, settings and intake detail had equal 375-pixel document/client widths after scrollbar allocation. Tables scroll within their own containers. Both grouped-menu columns and the expanded specialist menu stay inside the screen, with vertical overflow contained. Phone action wrapping was corrected. Research diagnostics also retained readable light panels without the old secondary rail. This is representative workflow/browser evidence, not a claim that every compatibility branch has received a separate editorial review.

Actual reviewed screenshots:

- [Company comparison](../../artifacts/design-sprint/retained-comparison-desktop.png)
- [Phone comparison](../../artifacts/design-sprint/retained-comparison-mobile.png)
- [Shared source Reader](../../artifacts/design-sprint/retained-comparison-reader.png)
- [Specialist menu](../../artifacts/design-sprint/retained-specialist-menu.png)
- [Claim review](../../artifacts/design-sprint/retained-claim-review.png)
- [Publication history](../../artifacts/design-sprint/retained-publication-history.png)
- [Phone intake detail](../../artifacts/design-sprint/retained-intake-mobile.png)
- [Phone settings](../../artifacts/design-sprint/retained-settings-mobile.png)

### Full-suite navigation follow-up

The initial pushed head passed Change scope, Repository integrity and Static public safety, but Python tests found twelve assertions tied to the superseded sidebar, stakeholder header or separate navigation names (3,826 passed, 11 skipped, two warnings; run 37246603593). These assertions now verify the approved shared navigation and follow its actual consolidated destinations: Monitor retains watches/alerts/plans; Intelligence retains Questions; Reports & Briefings retains Meeting Prep, brief construction and Executive view. The legacy weekly shell still tests that browse cannot start discovery. Review counters now assert actual pending action counts rather than old CSS classes or inventory labels. No implementation, decision controls or data changed in this repair.

All 198 tests in the nine affected workflow files passed locally (one existing ReportLab warning, 108.15 seconds). The repaired pushed head requires a fresh complete check set; the initial failed result is retained as evidence rather than described as a passing release.

## Release boundaries

No publication, statement, identity or extraction gate is changed. Pass/Fail/Defer remains the original private claim-testing workflow and does not create facts. Original source prose, analyst edits, dates, role distinctions and unknown coverage remain intact. There is no new acquisition, provider request, recurring job activation, merge or deployment. Public builds retain the published-only navigation and data boundary.

Broader selected-country/berry market-reference population, older open-PR parity, final combined guide and authenticated container/release/backup/rollback acceptance remain. This draft must pass its own four exact-head checks; local proof does not replace them. The user reviews the tested release before merge/deployment.

## Final required checks

Final #309 head `7a82b7bd52e3967fd383a04b97536bf6ec15ea62` passed all four required checks, run `37247720206`: 3,838 passed / 11 skipped / two warnings / 360.68 seconds. The initial twelve outdated navigation expectations were corrected to the actual consolidated homes while retaining specialist access and pending counts; 198 affected-workflow tests passed before final CI. No implementation, trust or data change in that test repair. The combined release is still separate.
