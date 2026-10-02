# Mission 16 — Signal candidate review

Follow-up to draft #288 head `c2be282f8f770780c1012e68e5ca75352a209ea3`, all four checks green (3,578 passed / 11 skipped / two warnings). Continues the accepted hierarchy and consolidation requirements into the existing Signal candidate queue, detail and archived-history views. Authoring forms and wider release work remain open.

## Reading and decisions

The three review surfaces share Glasshouse Intelligence navigation. The detail leads with the proposed pattern's meaning, followed by source quality and explicit limitations. All original rationale, boundaries, source identities, independence/reprint analysis, relationships and editable notes remain. The repeated rationale is displayed once rather than twice. Review history/metadata and grouping methods are closed native disclosures. Populated queue groups retain their priority order and appear before compact closed empty groups; counts and original section anchors remain. The limited-evidence overlay remains distinct from the triage buckets.

The supporting-source table opens the shared Reader and retains the original publisher option. Unsafe publisher URLs stay in the record but cannot render as active links. **Confirm candidate** submits the same `confirm` decision as before; it records candidate review and never creates a trusted Signal. Edit, Defer, Dismiss and Dispute retain their original values, reviewer, notes and safe return path. Boundaries precede all decision controls. Archived candidates preserve prior decisions and original IDs, expose the reference on demand and retain the 410 status without a new decision form. Nothing is automatically confirmed, regenerated or promoted by these changes.

## Private boundaries

Read-only requests to the candidate queue/detail now return 403 before any private candidate/audit/support read. The existing authoring decision endpoint also rejects cross-origin/cross-site requests before reading a candidate or persisting a decision, using the established workspace guard. Existing individual human decisions, stale identity handling, audit preservation and publication/atomic/model-qualification gates are unchanged.

## Verification

Initial combined candidate/review/judgment/static run: 58 passed, one existing reportlab warning, in 100.30 seconds. After tightening populated/empty ordering and adding its preservation test: 47 focused candidate/review tests passed, one warning, in 4.63 seconds. **Final combined run: 59 passed, one existing warning, in 100.98 seconds**, including full static generation and published-counterevidence retention. Canonical validation passed; pushed-head four-check CI remains required.

Browser review used an explicitly unreviewed isolated sample, with the actual Hortifrut announcement and same-event FreshFruitPortal coverage, one underlying origin. The first sample mistakenly referenced an unrelated BluGenix article; inspection caught it and the ignored fixture was corrected before saved proof. No canonical association or real candidate decision was changed. The queue retained one Same-origin / weak candidate and all zero counts; empty groups were closed and the populated group led. Detail kept rationale and limits ahead of the decision controls, and Review history opened/closed with Enter.

Source drill-through opened the shared Reader, honestly disclosed unavailable article text and retained the publisher link. A locator waiting for the initial dialog name timed out because the loaded Reader changed its accessible name to Story reader; fresh state recovered it. Close returned to the same candidate; a fresh check confirmed no dialog remained. Reader progress affected only isolated sample personal state. No review decision, source fetch, model call or canonical write was performed.

At 390px, the page measured 375px; the 530px source table scrolled inside a 349px container. All five decision buttons measured 44px high. Queue counts/groups stayed inside the page. Viewport override was reset. Screenshots under `artifacts/design-sprint/`: candidate queue and reading desktop/mobile, plus source Reader.

## Remaining work

Named selection and hierarchy in authoring forms, deeper specialist/public-static consistency and final cross-family acceptance remain. Broader source/body/media/provider readiness, learning visuals, protected enrichment/regions, market statistics, packet compatibility, per-account/inter-process state and canonical/active-PR reconciliation stay on the durable checklist. This is a tested review presentation slice, not completion of the ongoing goal or approval to merge/deploy.
