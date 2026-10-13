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
scrolling. Phone columns use fixed table layout and wrap long values so the
company column can be read fully at the right edge, rather than disappearing
partly behind the pinned names. The stylesheet URL advances to version 9.

This changes presentation only. Catalog identities, crop scope, sources,
rights/trait/organization counts, user notes/hides and every review gate stay
unchanged. A photo reference is still distinct from permission to use it.

## Verified checks and remaining visual review

All **21 existing profile-field/source-status tests pass**, one existing
ReportLab warning, 147.94 seconds. Record validation and the full **1,755-page
public/Pagefind build** pass. No new test duplicates a CSS declaration; the
intended pinned behavior still requires real browser observation.

After the second column repair, all **eight source-status tests pass** in 166.34
seconds. Warnings are the existing ReportLab deprecation and a restricted local
pytest cache write; neither changes the test result. The initial 21-test run
and public build precede this refinement; its new public build and CI are
tracked separately rather than borrowed from the earlier commit.

The native browser established a real **412 × 915 Pixel 7 emulation** at 100%
preview scale, inspected the guide and its four workflow steps, and reproduced
the row-context loss in the field table. This is browser emulation, not a
physical-phone test. After the repair, the server returned the new stylesheet
with HTTP 200, but Computer Use stopped because it could not confidently verify
the Windows browser URL. That response was not visual proof. Following the
user's explicit Edge approval, native Edge review at **412 × 494 responsive
emulation** verified the pinned names while panning right and scrolling down.
It also found over-wide company cells obscuring their first words; fixed phone
columns repair that second defect. The final view shows full company names
beside the correct variety, with row contrast and header layering intact.
Edge device emulation is off and its inspector is closed. The earlier Opera
temporary inspector/device reset remains pending. This is not a physical-phone
test. Private proof files end in `field-table-edge-phone-412-right-v9.png` and
`field-table-edge-phone-412-later-v9.png`.

Screenshots with browser chrome stay in the ignored local
`inbox/european-portfolio-followup/combined-review-2026-10-12/browser-proof/`.
They are not published to the PR. Current private review uses the recovered
runtime with 32 pending source copies, not the original runtime or production.

Parent [PR #394](https://github.com/samsonFive/berry-intelligence-os/pull/394)
passes all four required checks on `5474d576bbe4d74739a4aa357b8448c0af02ecf5`:
**4,635 passed / 11 skipped / two warnings / 736.14 seconds**. Its exact committed
package and isolated complete recovery verify 3,610 code files and 2,956 runtime
files. The initial child commit `9853cc1` passes all four checks with **4,635
passed / 11 skipped / two warnings / 770.49 seconds**. Its exact 3,610-file
package is retained separately. The subsequent browser-found column refinement
needs a fresh current-head check set and package before release acceptance.

The full [31-requirement checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md) and visual
guide remain. CAT-01/CAT-02/TD-116, human source/name/catalog decisions, revised
blueberry acceptance and final release review remain open. No merge, deployment,
other-berry Landscape rollout or production restore is authorized by this fix.
