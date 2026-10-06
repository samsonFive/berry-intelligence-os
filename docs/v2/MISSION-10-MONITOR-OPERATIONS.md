# Mission 10 — Monitor and Operations consolidation

Working implementation brief following the accepted section audit. This document records the state mapping before changing entry points; it is not evidence of completed UI migration. Mission 9 draft #282 is pushed at `9dd69112b7725e2111bed33035f5b1cd4be02020`; all four required checks passed on that head (run `37011755674`, 3,509 passed / 11 skipped / two warnings).

## Monitor: one home, different decisions

The user should open Monitor to see what they chose to track, what changed and what needs attention. Use the shared bright Glasshouse shell, dense readable rows, clear subject names/date/source context and collapsed technical detail. Existing routes remain compatible until equivalent behavior is demonstrated.

| Existing state or surface | Purpose and authority | Consolidation rule |
| --- | --- | --- |
| Company favorites, tiers and custom lists | Personal categorization/filtering; lists can be subscribed for Digest | Reuse the established personal store. Do not make favorites, tiers or list membership imply notification rules or watch creation. |
| Following / roster context | Company-following presentation and roster monitoring context | Explain how it differs from explicit typed watches. Never silently rewrite canonical company monitoring metadata into personal marks. |
| Typed watchlist, `watchlist_state.json` | Explicit company, variety, geography, berry, strategic-question or move-type interest; last-seen state | Show as a Watches view. Add/remove and explicit Open remain separate from publication review. Render/browse does not mark seen. Preserve object type, identity and dates. |
| Monitoring priority inventory, `analyst_queue_state.json` | Evidence-tagged monitoring intent and pause/remove/resume overlays | Keep its origin visible. Do not merge it into typed watch records, rewrite Evidence priority to dequeue, or imply that counts are uncleared work. |
| Watchtower alerts and notification decisions | Derived changes for watched subjects; read/dismiss/snooze/reopen | Present as Alerts with its identity/history and authoritative source link. These actions never confirm the underlying intelligence. Cached inputs remain visibly dated. |
| Proposed signals, signal candidates and source-health alerts | Existing distinct analytical/review/operations decisions | Link the authoritative review or health surface; do not invent bulk trust approval or treat proposed signals as trusted findings. Keep alert groups distinct from watch inventory. |

Current source inspection found two preservation issues to address while moving the family: `/watches/open` sends berry/move-type watches through the strategic-question fallback; watchlist read failures currently collapse to an empty list, which a later write could overwrite. Add meaningful regression tests and repair these within existing semantics. Avoid silently removing missing identities; show recovery/retained state where appropriate.

Acceptance: explicit watch → relevant captured change → underlying source/profile → explicit seen; alert → authoritative detail → notification disposition → reload; scoped filtering and Reader return; distinct favorites/list/tier/watch status; no collection/provider/trust action on browse; damaged-state preservation; keyboard/mobile layout; public/private boundaries. Use synthetic isolated fixtures for actions and preserve the production inbox.

## Operations: an operator home with named stages

Consolidate entry points into one operator workspace with four understandable groups: **Collect**, **Review**, **Data quality**, **Coverage & health**. Retain existing specialist workspaces and command paths, rather than replacing them with a second workflow.

- Collect: collection-run status and explicit bounded run action, intake/manual material, discovery diagnostics.
- Review: publication decisions, source-centered individual Atomic Evidence proposals, active sessions and Signal Review. Publication and proposition approval remain separate human gates.
- Data quality: source authenticity/body fidelity, company/variety identity exceptions and candidate adjudication. Authenticity is not proposition approval.
- Coverage & health: source health versus configuration permissions, known/intended/observed/excluded coverage and variety coverage. Healthy or quiet sources do not prove complete capture.

Opening the home reads existing statuses only. Keep private operator data behind the current authoring/session boundary. Show useful status first; put implementation diagnostics and provider configuration details behind disclosures. Label stale/blocked/quiet/missing states honestly. Collection and paid calls require explicit actions; missing credentials and failures need an actionable explanation without exposing secrets. Do not change collector maturity or source registry solely to make the dashboard appear active.

## Completion evidence to add

Record delivered routes, original-route compatibility, actual state/action tests and isolated browser walkthroughs. Update the requirements checklist, audit purpose cards and visual workflow guide. Broader integration/account/multi-worker and exact-head required CI remain release gates. Prepare the integrated tested release for the user's approval; no merge or deployment during this mission.

## Delivered slice and verification

- `/monitor` provides Watches, Alerts and Monitoring plans. Company favorite/tier/list scope uses the shared personal store and requires a single associated company to satisfy all selected marks. Multi-berry scope survives tab changes. Missing selected identities/lists fail visibly rather than broadening the view. Company profiles add a typed subject watch independently of personal marks.
- `/operations` groups Collect, Review, Data quality and Coverage & health. `/collection-ops`, `/review-ops` and `/coverage-assurance` retain controls in the shared shell. Deep identity, Radar, source and research diagnostic routes remain reachable and still need presentation review. No Sources configuration-admin migration.
- Watch corruption/malformed history now refuses reads/actions without overwrite. Atomically serialized local writes retain metadata/history. Berry and move-type Open targets are repaired; missing subjects stay in a recovery disclosure and are not marked seen. Alert actions and monitoring-plan commands enforce the existing authoring/same-origin edit boundary. Plan commands return to the selected Monitor scope.
- Browsing the new homes never triggers collection or a provider call; Monitor derives alert content without persisting it. The existing publication service may update only its derived pending metadata index. Published source counts stay distinct from unreviewed changes. Read/dismiss/snooze/reopen never approves underlying intelligence.
- **154 focused tests passed**, one existing Starlette deprecation warning; canonical record validation passed; static build produced **1,755 pages**, verifying no unpublished IDs/titles. Earlier failures found and corrected the unsafe-return fallback, test accounting for the existing derived index and a missing origin guard. Those failures are retained as verification history.
- Isolated browser at localhost:18323: company Watch → Open/check → Monitor; synthetic captured development → read/reopen and move notification → dismiss/reopen; source detail retained; plan Pause → reload → Resume → shared Reader → close/filter. Stored changes remain under ignored preview inbox, never production.
- Desktop Overview, Collect, Review, Coverage and Monitor checked visually. Technical details/age buckets and plan activity start collapsed. Operations and Review page widths were 375px in a 390px viewport. Remaining responsive checks encountered a browser-control timeout; do not claim those layouts accepted. Public-safe desktop screenshots: `operations-live.png`, `monitor-alerts-live.png` in `artifacts/design-sprint/` (notifications use a clearly labeled synthetic fixture).

## Remaining release work

Exact draft-head CI, remaining specialist UI and responsive checks, consolidated alert-event presentation (multiple triggers can describe one event), retained-route scope consistency, real collection/retry/provider acceptance, per-account state and multi-worker writes, combined canonical integration and final workflow explainer. Following/roster metadata is not silently converted into typed watches. Empty isolated review queues do not establish that production workflows are working. No merge/deployment.

**CI/browser follow-up:** First pushed head `c87e325` passed Change scope, Repository integrity and Static public safety, but Python tests found one coverage-copy regression: the explicit “not a completeness score” distinction was no longer present. 3,525 passed / 11 skipped / two warnings; the wording is restored without changing the safety test. A fresh browser tab recovered responsive review: Monitor page was 375px inside a 390px viewport, its 800px table scrolled inside 349px; Alerts retained two selected berries. Coverage tables scrolled inside 319px containers (620–749px content) while page width stayed 375px. Temporary viewport was reset. Initial browser interruption remains in the history; these recovered checks close that subset, not full mobile acceptance of every specialist tool.

**Final local repair checks:** 46 coverage/Monitor tests passed after restoring the completeness explanation and restricting rendered alert source links to safe public URLs. Original cached URLs remain unchanged. A malicious-link fixture verifies it cannot become a script link; no trust decision or URL-storage schema changes. Fresh draft-head CI remains required.

**Mission 10 exact-head CI:** Draft #283 final head `cf6798888d2daea1dc33e8c6d983726e695593d8` passed Change scope, Repository integrity, Static public safety and Python tests, run `37018754430`: 3,527 passed / 11 skipped / two warnings. Earlier c87e325 failure remains in the history; the combined release is still pending.
