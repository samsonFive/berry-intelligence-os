# Candidate keyboard focus clearance

Keyboard navigation could focus a source link behind the floating alphabet bar.
The baseline was reproduced with native Shift+Tab on a 412x915 preview: the link
occupied y168.8-189.4 while the sticky bar occupied y133-193. Its center hit the
alphabet picker. The link was inside the browser viewport, so the browser's own
focus scrolling did not clear that obstruction.

The existing candidate script now checks the newly focused control after the
browser has handled focus. When the actual sticky shell/bar covers its top, the
page moves just enough to expose it with eight pixels of clearance. Controls in
the navigation are excluded. Already visible targets, stale/removed/zero-size
targets and ordinary manual scrolling keep their behavior. Before the bar sticks,
controls clear only the header. The existing measured header/bar heights are used
rather than a phone-specific constant.

The floating alphabet navigation, density, geometry, existing hash offsets,
Reader and authoring actions remain unchanged. There is no global scroll padding,
new library, network request, saved preference or data/review-state mutation.
The UI component changes only `app/static/variety_workspace.js` at runtime.
It follows tested platform #460 (`baf33dc2`); those thirteen runtime files remain
exact. The [combined platform review](PLATFORM-QUALITY-COMBINED-REVIEW.md) now also
includes the tested Reader #459 component. Source imports and catalog/Map #449
remain separate.

## Evidence and remaining acceptance

All 22 affected candidate/anchor checks pass in 57.97 seconds, including the
actual browser-script contract under Node. Cases cover covered/visible/nav
controls, rapid/stale focus, hidden targets, a bar below the fold, resize and
pages without candidate navigation. JavaScript syntax validation passes.

Native Shift+Tab on the fixed phone preview moves the same link to y200.8-221.4,
below the bar at y193. Its center now hits the link. Tab forward/back between
already visible controls retains scrollY1374. The alphabet picker still keeps
the source and search filters and selects M correctly. A longer desktop company
list puts the focused link at y124.2 below the bar at y116. Filter jumps retain
the company selection and clear the header. First-login Help still works with
a fictional account; no human review or photo-permission action was taken.

The native fixture uses public data copied from the separate #461 source draft
to exercise its original-document link. Those records are not included in this
platform branch. Baseline candidate JS/CSS bytes match between that source parent
and #460. Screenshots are isolated fixtures, not production or physical-phone
evidence. No real account was logged in.

Record validation and the 1,983-page static build/leakage check pass. Exact-head
full CI and a fresh isolated live-data preservation check remain. The original 31 requirement definitions/
order and governing guide remain verbatim. TD-122 stays open for broader cold
performance and real-device latency; the separate source, identity, rights and
photo decisions are unchanged. No merge, deployment or new approval question.
