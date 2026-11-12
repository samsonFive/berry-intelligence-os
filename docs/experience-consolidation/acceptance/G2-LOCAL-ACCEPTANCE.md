# Local G2 acceptance

November 11, 2026. Integration lead review: **local functional and visual checks
accepted**. Required final-head CI and production acceptance remain open.

Source checkpoint `820fda87` is integrated onto canonical #558 (`0722e7da`),
including #553/#556. Its next committed head still requires fresh Linux CI.

Current emitted client: `index-XLX6kyu1.js`, SHA-256
`5F299D22E5266D90DF97F1AC4C07498882ABA06EF9A9A1381E043BC11B69B7C5`.
Entry HTML SHA-256:
`0E59D6092AF61F109F16DF49550440A2A40DA5A7BFAB0AE53574E6F98E5129AC`.
CSS: `index-7qD0DpA5.css`, SHA-256
`685FD10CDE4E4A6F7B1E75AD5F120F795486B5578DE6CF4D421B2A46A598B7F0`.
The main functional packets below use `index-Cp5PKdjN.js`. A subsequent copy-only
build corrected “frozen Brief Packs” to “live Brief Packs” in Workspaces. The
Learn crop-note build `index-BCSIw7In.js` has its own focused mounted receipt
below. The current client adds optional retained-link metadata presentation;
its focused proof is synthetic-only. Learn source is unchanged, but no Learn
replay on the current asset is claimed. Earlier full-flow receipts retain their
recorded asset and scope.

## Native surfaces and state

* Final direct investigation: all 16 checks passed with no defects, page errors
  or provider turns. Five populated image-ready states, narrow review and a
  44-second continuous recording are in
  `artifacts/experience-consolidation/v1/rehearsal-1794439040122/`.
* Briefing/cross-surface: six groups passed in
  `v1/briefing-rehearsal-1794438950288/`. Scoped developments use the accepted
  cards/Reader; Article/Brief/history/narrow return and outer selectors persist.
  All six compatibility destinations returned 200 with exact native returns.
* A fresh pending legacy News page opened from an investigation had
  `data-auto-recheck=false` and made zero automatic POSTs. Its explicit Recheck
  control was verified with one intercepted response; the classifier did not run.
* Workspaces: seven groups passed in `v1/workspaces-rehearsal-1794438812960/`,
  including actual save, native reopen, reload, update, concurrent-writer conflict
  freeze and explicit reload. Both typed cohorts, Reader section and demo selectors
  survive. Standard and explicit-annex PDFs came from the actual preview/download UI.
* Learn: 11 strict checks passed in `v1/learn-rehearsal-1794438842108/`. The actual
  library contains 27 concepts and no private lessons in the isolated QA store;
  supported private-lesson cases are covered separately by backend fixtures.
  Educational filters stay independent of the investigation search. A library
  position of 2,621px survived Back exactly; new concept/related reading starts at
  its visible heading with main focus. Deep reload, authored diagrams/cane controls,
  legacy return, narrow width and licensed-photo pixels/attribution were verified.
* Final Learn crop-note applicability: three focused mounted checks passed on
  `index-BCSIw7In.js` in
  `artifacts/experience-consolidation/v1/learn-crop-note-qa-1794441712227/acceptance.json`.
  Blueberry Cane shows “In Blueberry context” and the quiet absence note
  “No Blueberry-specific crop note is recorded,” then retains the actual authored
  Raspberry and Blackberry notes under “Also in other berries.” All berries keeps
  “By crop,” identical complete note text and original order, without the absence
  or other-berries headings. The viewport and document both measured 390px in the
  narrow check. All three screenshots were visually reviewed, with zero page
  errors and zero provider calls. The owned browser/server were closed and the
  private scratch inbox removed.
* Retained-link metadata: two synthetic-only mounted groups passed on
  `index-XLX6kyu1.js` in
  `artifacts/experience-consolidation/v1/synthetic-retained-links-1794444670632/acceptance.json`.
  The optional additional-link section starts collapsed. Keyboard expansion
  preserves exact original URL strings, labels and unresolved-link kinds, with
  safe external-link attributes and an explicit independence limitation.
  Additional links do not increase source or corroboration counts. Both groups
  passed with zero page errors and provider calls; this is not production-record
  or publisher-resolution evidence.

The lead inspected populated Workspaces, Briefing/Reader, Learn diagram/photo and
the final investigation frames. The citation with a canonical null URL remains
plain text; no URL was invented. All QA workers, browsers and runtimes were closed.

## Backend, build and packaging

These runs overlap; do not add them as unique test coverage.

* 88 frontend tests, including crop-note grouping and retained-link metadata,
  TypeScript and the current Vite build passed.
  Dependencies and normalized committed lockfile blobs are unchanged; Windows
  checkout line endings can change raw file SHA-256 without changing those Git blobs.
* 12 runtime tests passed. G1's actual funded command and exact direct-control
  equality remain recorded in `G1-V1-ACCEPTANCE.md`; no further model turn occurred.
* 195 integrated backend/auth/save/export/static/News/package regressions passed;
  48 final hardening regressions passed afterward.
* The missing Docker inputs were corrected and all four packaging tests pass. Both
  Dockerfiles' context inputs, exact committed bytes/modes, private-file exclusion,
  older refs and existing-package preservation are covered.
* Earlier Linux checkpoint `ff6a17e3` passed every required check in run
  `43125105819`: 7,431 Python tests passed / 11 skipped, both Docker builds and
  no-network metadata/import checks passed. It does not accept the current head.
* The unchanged 500ms warm Reader test failed on two Linux heads: 522.8ms on
  `60d9f0a1` (7,412 other passes / 11 skips), and 543.5ms on `43e5a730`
  (7,436 other passes / 11 skips). Logs:
  `artifacts/experience-consolidation/ci-python-60d9f0a1-failed.log` and
  `artifacts/experience-consolidation/ci-43e5a730-failed.log`. Neither is a
  passing final-head result.
* The current overlay Reader repair adapts public
  [PR #535](https://github.com/samsonFive/berry-intelligence-os/pull/535)'s reduced entity
  projection to current consumers while preserving repository signature
  invalidation, visibility, isolation and duplicate-ID behavior. All 49 focused
  tests passed, including the unchanged 500ms assertion and four new regressions.
  Sixteen paired complete HTML comparisons were byte-identical. Local medians:
  Atlantic Blue 336.08 → 296.07ms; BluGenix 343.73 → 274.66ms. Receipt:
  `artifacts/experience-consolidation/reader-projection-paired-current.json`.
  These bounded Windows/Python3.13 samples do not clear Linux CI or close TD-122.
* Record validation passed. The 2,429-page public build and unpublished-draft
  leakage check passed; the private client remains excluded from public output.
* Both Docker images and metadata/import smoke checks are added to the existing
  Linux frontend CI job. Smoke containers disable networking and use no real
  provider credentials. Local Docker is unavailable; final-head container checks
  remain part of the required CI gate.

The reviewed changes preserve canonical data, the expansion guide, coverage matrix,
auth boundaries, authored stores and existing trust/publication workflows.
Production services, records and configuration have not been changed by this
candidate. Production promotion and production paid commands remain separately
unauthorized.
