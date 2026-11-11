# Local G2 acceptance

November 11, 2026. Integration lead review: **local functional and visual checks
accepted**. Required final-head CI and production acceptance remain open.

Final client: `index-5VVPB8ZT.js`, SHA-256
`C4B61DA74193DE7A73BE0742291FF1B65060ABCB823F56DCD486C007867BEF16`.
CSS: `index-7qD0DpA5.css`, SHA-256
`685FD10CDE4E4A6F7B1E75AD5F120F795486B5578DE6CF4D421B2A46A598B7F0`.
The final rebuild changes only “frozen Brief Packs” to the correct “live Brief
Packs” in Workspaces. Functional packets below use the otherwise identical
`index-Cp5PKdjN.js` build; no behavior changed in that final copy correction.

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

The lead inspected populated Workspaces, Briefing/Reader, Learn diagram/photo and
the final investigation frames. The citation with a canonical null URL remains
plain text; no URL was invented. All QA workers, browsers and runtimes were closed.

## Backend, build and packaging

These runs overlap; do not add them as unique test coverage.

* 80 frontend tests, TypeScript and the final Vite build passed. Dependencies and
  normalized committed lockfile blobs are unchanged; Windows checkout line endings
  can change raw file SHA-256 without changing those Git blobs.
* 12 runtime tests passed. G1's actual funded command and exact direct-control
  equality remain recorded in `G1-V1-ACCEPTANCE.md`; no further model turn occurred.
* 195 integrated backend/auth/save/export/static/News/package regressions passed;
  48 final hardening regressions passed afterward.
* The broad Python run had 7,380 passes, 10 skips and one packaging failure. The
  missing Docker inputs were corrected and all four packaging tests pass. Both
  Dockerfiles' context inputs, exact committed bytes/modes, private-file exclusion,
  older refs and existing-package preservation are covered.
* Record validation passed. The 2,429-page public build and unpublished-draft
  leakage check passed; the private client remains excluded from public output.
* Both Docker images and metadata/import smoke checks are added to the existing
  Linux frontend CI job. Smoke containers disable networking and use no real
  provider credentials. Local Docker is unavailable, so actual image checks await CI.

The reviewed changes preserve canonical data, the expansion guide, coverage matrix,
auth boundaries, authored stores and existing trust/publication workflows.
Production services, records and configuration have not been changed by this work.
