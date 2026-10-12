# Keep the variety name beside its profile details

Native phone review found that horizontal scrolling moved the variety name out
of the field table. Traits and company/program roles stayed visible, but the
reader could no longer tell which row they belonged to. The table remained
inside its 412px viewport; row context was the missing behavior.

The first column now stays pinned, with an opaque row background and a subtle
separator. The header corner remains above both scrolling headers and row
names. Phone names can wrap within a narrower column, leaving room to inspect
the other fields; alternating row contrast and semantic row headings remain.
The phone scroller also reserves the pinned-column width during keyboard focus
scrolling. The stylesheet URL advances to version 8 for existing browser caches.

This changes presentation only. Catalog identities, crop scope, sources,
rights/trait/organization counts, user notes/hides and every review gate stay
unchanged. A photo reference is still distinct from permission to use it.

## Verified checks and remaining visual review

All **21 existing profile-field/source-status tests pass**, one existing
ReportLab warning, 147.94 seconds. Record validation and the full **1,755-page
public/Pagefind build** pass. No new test duplicates a CSS declaration; the
intended pinned behavior still requires real browser observation.

The native browser established a real **412 × 915 Pixel 7 emulation** at 100%
preview scale, inspected the guide and its four workflow steps, and reproduced
the row-context loss in the field table. This is browser emulation, not a
physical-phone test. After the repair, the server returned the new stylesheet
with HTTP 200, but Computer Use stopped because it could not confidently verify
the Windows browser URL. That response is not visual proof. A supported Edge
launch then required app approval; its prompt expired. The final pinned-column
view and temporary device/inspector-state reset remain pending.

Screenshots with browser chrome stay in the ignored local
`inbox/european-portfolio-followup/combined-review-2026-10-12/browser-proof/`.
They are not published to the PR. Current private review uses the recovered
runtime with 32 pending source copies, not the original runtime or production.

Parent [PR #394](https://github.com/samsonFive/berry-intelligence-os/pull/394)
passes all four required checks on `5474d576bbe4d74739a4aa357b8448c0af02ecf5`:
**4,635 passed / 11 skipped / two warnings / 736.14 seconds**. Its exact committed
package and isolated complete recovery verify 3,610 code files and 2,956 runtime
files. Those prove the parent; this stylesheet child needs its own fresh CI and
new final package before combined release acceptance.

The full [31-requirement checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md) and visual
guide remain. CAT-01/CAT-02/TD-116, human source/name/catalog decisions, revised
blueberry acceptance and final release review remain open. No merge, deployment,
other-berry Landscape rollout or production restore is authorized by this fix.
