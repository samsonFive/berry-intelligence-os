# Mission 11 — Intelligence workspaces and the visual guide

Follow the accepted section audit and approved Glasshouse design. Mission 10 draft #283 is pushed; its repaired head is awaiting all four required checks. Canonical was freshly fetched on October 2 and remains `916b8f09f9ce2a1847335d7990ea80ff921f1cec`. Other open canonical-targeting PRs #255 (Learn), #270 (Varieties) and #271 (executive/mobile) need overlap reconciliation before the combined release. Do not merge, close them or deploy during this slice.

## Purpose and boundaries

Bring investigation and help pages into the existing shared navigation and readable hierarchy. The goal is source → meaning → analyst decision, with actual object status and return scope visible. Keep original routes, forms, stores, original source text and source links. Retain every human publication/proposition/identity gate. Company contacts stay inside company profiles. Do not migrate Sources configuration admin, add a second review model, create Facts from interpretation, or change Variety/Trade/Weather schemas.

## First controlled groups

1. Developments and company moves: `/radar`, its selected cached detail, `/moves` and company detail. These are captured interpretations, not source articles or confirmed claims. Their provider refresh is explicit; the existing Radar page currently has a separate script/refresh seam that must be audited before reuse. Raw trust codes, timestamps and provenance belong in readable labels and collapsed source context. Keep cached/stale/empty states honest; merely browsing cannot become acquisition.
2. Landscape concentration/coverage: `/whitespace` retains compatibility but receives a plain-language coverage-and-concentration label. Missing observation is not a business opportunity or market-share metric. Carry only supported scope into Reports/Meeting Prep.
3. Judgments and research: Statements, Signals, Assessments, Recommendations and Strategic Questions retain their different decisions. Reuse existing selectors/Reader; inspect their action/private/static boundaries before changing entry points. Ask Berry research keeps explicit provider/data-export scope.
4. Help and the visual explainer: update `/guide` around delivered News, Map, Companies, Learn, Digest, Landscape, Monitor, Operations and Reports & Briefings. Teach a real analyst reading/review/reporting loop with pictures/diagrams and accessible progressive detail. Use accurate output distinctions: current view, private working draft, dated saved file and export. Never imply that a future feature or isolated fixture is deployed functionality.

## Acceptance

- A selected cached change → supporting source/Reader or company → original context; no automatic provider call or review promotion.
- A pattern/proposition/assessment retains its own status and actionable authoritative route; collapsed detail cannot hide core article content.
- Plain-language dates and labels, compact full-width layout, clear headlines/answers, contrast, contained More menu/tables and mobile/keyboard return.
- Existing deep bookmarks and scoped handoffs stay usable; unsupported selectors are disclosed rather than ignored.
- No private review state or pending/provider material enters a static snapshot. Account/multi-worker review remains a release gate.
- Update the durable checklist, audit purpose/mechanism/proof/disposition notes and visual explainer. Test meaningful action and preservation boundaries; push a draft and verify all four exact-head checks.

## Subsequent required work stays in scope

Remaining sourced visual Learn coverage, source-assisted editable profile/region suggestions, broader sourced market statistics and refresh/revision paths, real news body/image/capture readiness, account/multi-worker assessment and migration, active-PR/canonical integration, final route/mobile/export walkthrough and release/rollback review. None is closed merely by styling the investigation pages. Photo identities and source/statement publication continue to require human review rather than simulated approval.

**Initial inspection finding:** `radar.html` currently fetches `/radar/live?fragment=1` automatically whenever its cache is missing/stale. That can invoke the provider on ordinary page entry, despite the intended explicit-refresh boundary. Before any empty-cache browser walkthrough, replace this automatic fetch with a visible deliberate refresh action, retain cached/stale/empty content honestly and cover the no-acquisition-on-browse boundary. The cached synthetic detail rehearsal in Mission 10 had a fresh edition and did not invoke this path.
