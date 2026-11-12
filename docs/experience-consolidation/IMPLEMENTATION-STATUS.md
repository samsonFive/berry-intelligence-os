# Experience consolidation implementation

Updated November 11, 2026, Pacific. Presentation: November 12 morning.
**G1 passed. Earlier local functional checks passed. Visual acceptance is reopened;
the user rejected the sparse design. Production release remains held.**

The current revision follows the user's direct feedback: a light, dense analyst
workspace with stronger hierarchy, multiline and multicolumn data cells, a
ten-company review model, an uncapped paginated monitored company universe and a
Landscape News feed. The first dense prototype was described as “closer,” with
the further requirements above; it has not been accepted as the final design.
These direct user requirements supersede the archive's older visual suggestions.
All changes are local review work; no design revision has been deployed.

The monitored-company revision passes 112 frontend tests and TypeScript, plus
126 targeted backend tests covering investigation reads, export, saved routes
and workspace compatibility. The native News adapter now allowlists its card
metadata so unselected article excerpts remain in Reader only. Browser visual
review, current-canonical integration and final-head GitHub CI remain open.

## Source and scope

Isolated branch `feature/experience-consolidation-20261111`, originally based on
canonical #550 (`3f159639`), now integrated onto #559 (`0d42c764`), including #558
(`0722e7da`), #551
Strategy inputs, #552 News expansion, #554/#555 translation/noise fixes, #556
material News recovery and the published-review-link repair. Current source
checkpoint before the design revision: `1db5370d`. Its five required GitHub checks
passed, including frontend/runtime validation and both Docker smoke checks.
The current dense monitored-company revision is uncommitted review work and
requires a fresh final-head check set after integration with current canonical.
Canonical data, the expansion guide and coverage matrix are unchanged by this
candidate. The original checkout's unrelated changes remain untouched.

The supplied six planning documents remain in `specification/`. Their historical
planning-only text is reference context. The current user mission authorizes this
implementation; production promotion remains a separate concrete release step.
`G0-CONTRACT.md` records the versioned selectors, APIs, owners and boundaries.

## Accepted populated slice

* Persistent React/TypeScript shell, router, private QueryClient and one shared
  investigation action/history owner; focus and comparison pins stay separate.
* Curated Landscape, comparison, developments, options and selected-only Reader
  APIs reuse existing governed presenters. Company presence is not cultivar
  growing; publication review does not approve individual claims.
* Typed findings and relationship paths are visible before interaction. Actual
  AG Grid Community replaces the portfolio table. Connections, Portfolio,
  Geography, Comparison and isolated sensory replace one analytical field.
* One coordinated detail/Reader allocation preserves ancestry, source Article/Brief,
  scope, pins, lens, keyboard focus and pane/window position. It is suspended,
  rather than duplicated, while the command allocation is open.
* Account grid layouts persist widths/order/visibility/filter/sort/quick filter
  through the existing session-scoped API. Semantic keys, limits, optimistic
  conflicts, legacy fallback and logout cleanup preserve earlier preferences.
* Selector-only save/reopen/history/conflict APIs retain outer store version 1,
  `kind=explorer`, legacy semantics and explicit save-as-new conversion.
* Controlled real CopilotKit tools dispatch the same shared actions. Runtime and
  gateway use loopback, server-only token auth, explicit model, bounded commands,
  stale/cancel guards and no provider call on navigation.
* Dated cited PDF preview/export includes complete domain rows and a source
  appendix. Ordinary output excludes the synthetic fixture. An explicit annex
  resolves only selected fictitious specimens on the declared 1–9 scale.
* The React brand-media adapter consumes the existing curated official-reference
  API. Company/comparison imagery remains auxiliary; inspection expands in its
  existing gallery allocation, with no image modal or selector/history change.

## G1 and V1 evidence

Client used for the accepted real G1/V1 packet: `index-TMvSoonX.js`; SHA-256
`9B99CE8BFD6C68134E37ADE6B0248D81574CABF2BB81FDC6E8349CC761F3F0F3`.
Runtime source SHA-256 for that packet:
`C03E771606A72044E42F635504D3260511C481E263817321E26B986A996D72E9`.

The user explicitly approved one additional diagnostic after automatic review
rejected it pending specific authorization. That single turn succeeded:
**“Compare Fall Creek and Costa in China”** resolved the three catalog names,
applied `show_portfolio_comparison`, and produced exact normalized equality with
its direct-control equivalent. Three actual HTTP 200 / RUN_FINISHED completions
reported 4,379 input and 307 output tokens (4,686 total, including 143 reasoning
and zero cached tokens). No further paid turn followed; the runtime was stopped.
Provider-reported billed dollars were not exposed.

The real continuous packet is
`artifacts/experience-consolidation/v1/rehearsal-1794436693801/`, with five populated
screens, narrow/keyboard evidence and the 71-second recording
`page@c4767bcf70f325794f2d5a553e20d89a.webm`. All 16 interaction checks passed with
zero defects, page errors or unexpected provider turns. The lead accepted that
packet's functional behavior. The user subsequently rejected its sparse visual
design; current visual acceptance remains open.

Mounted account-layout proof is under
`artifacts/experience-consolidation/v1/grid-rehearsal-1794436607587/`: actual
resize/reorder/hide/filter/sort saves, lens return and reload, restoration without
extra POST, conflict freeze/reload, locked identity/pin and narrow keyboard use
passed. Preferences did not change scope, focus or cohorts.

Two earlier funded attempts failed. The first lost terminal diagnostics and its
usage/cause remain unknown. The second completed two provider turns (2,356 input,
219 output tokens) without a view change; its tool details were discarded.
A proven SDK-injected tool boundary and a separate catalog name-match information
gap were corrected. Do not claim either was the historical cause without evidence.

## Other verification

Runs overlap and must not be added as unique coverage:

* Focused integrated Python suite: 114 passed. Windows default temporary-directory
  setup errors cleared with a fresh workspace-owned `--basetemp`.
* Learning foundation: 27 tests; additional source-date/catalog regressions passed.
* At the pre-redesign functional checkpoint: 97 frontend tests passed, including brand-media API boundary checks.
  Runtime: 12 tests. TypeScript and Vite passed. That checkpoint's emitted client:
  `index-CTvq3HUT.js`, SHA-256
  `8D566190E628F14123D31AF9D83BC41EE7051123A02501AAFB586E610CA71CC6`.
  Entry HTML SHA-256:
  `0F795B88F4E8758BF0A69852C5E1B0A7F7101BCC2171BA75F2DE2CB46BD7C610`.
  CSS: `index-6haV-zm8.css`, SHA-256
  `490A8E2153EDBC108240EC9BFC9AB6B5D069265617A8D322B0820D2BF7A833AB`.
* Learn applicability review passed on `index-BCSIw7In.js`. Blueberry Cane
  quietly states that no Blueberry-specific crop note is recorded, while keeping
  the authored Raspberry and Blackberry notes under other berries. All berries
  retains the complete authored text and original order under By crop. The three
  mounted checks, including a 390px viewport, passed with no page errors or model
  turns. Receipt: `artifacts/experience-consolidation/v1/learn-crop-note-qa-1794441712227/acceptance.json`.
  That Learn source is unchanged; no Learn replay on the current asset is claimed.
* Retained-link metadata: two synthetic-only mounted groups passed on
  `index-XLX6kyu1.js`. The additional-link section starts collapsed; keyboard
  expansion preserves exact original URLs, labels and unresolved-link kinds,
  with source-independence wording and safe external-link attributes. Additional
  links do not increase source or corroboration counts. No provider call or page
  error occurred. Receipt:
  `artifacts/experience-consolidation/v1/synthetic-retained-links-1794444670632/acceptance.json`.
  That module is unchanged; this receipt retains its recorded asset and scope.
* Native brand media: seven local mounted groups passed on `index-CTvq3HUT.js`.
  The curated seed plan/apply used only the isolated QA store. API and image
  requests returned 200 for two logos and three official packaging references,
  loaded with `no-referrer`. Comparison/company imagery, in-flow expansion,
  Escape/focus, one primary detail host, selectors/pins and Back/Forward passed.
  The inspection measured 331px inside a 390px viewport. Five screenshots were
  visually reviewed; no HTTP mutation, provider call, unapproved external request
  or page error occurred. This is local proof, not production acceptance. Receipt:
  `artifacts/experience-consolidation/v1/native-brand-media-1794446371333/acceptance.json`.
  The post-brand focused backend run passed 69 tests.
* Joined offline actual browser/gateway/SDK/runtime/parallel tools/comparison/action
  proof passed with dummy credentials and external provider access blocked.
* Export: 16 tests. Authenticated 42-page PDF and explicit two-specimen annex
  rendered and inspected; anonymous preview access returned to login.
* Record validation and the 2,429-page static build/leak check passed earlier.
  The private client is excluded from public output. Canonical data diff is empty.
* Configured credential literal scan: no matches in 113 changed source files.
* Locked dependency hashes are unchanged. Initial SDK-inclusive bundle is about
  3.83 MB / 1.10 MB gzip, recorded as a performance limitation in the debt register.
* Packaging: all four regressions pass, including older refs and private-file
  exclusion. The earlier missing frontend/runtime inputs are corrected.
* Linux Reader-repair checkpoint `26f047e1` passed every required check in run
  `43131077177`: 7,445 Python tests passed, 11 skipped, including the unchanged
  500ms Reader assertion. Both container builds and no-network metadata/import
  checks passed. The newer canonical/brand-adapter head requires fresh CI.
* Two Linux runs failed the unchanged 500ms warm Reader assertion: `60d9f0a1`
  measured 522.8ms (7,412 other passes / 11 skips), and `43e5a730` measured
  543.5ms (7,436 other passes / 11 skips). Logs remain in
  `artifacts/experience-consolidation/ci-python-60d9f0a1-failed.log` and
  `artifacts/experience-consolidation/ci-43e5a730-failed.log`. These failures
  motivated the bounded Reader repair; they are not dismissed as flakes.
* The Reader repair adapts the existing public
  [PR #535](https://github.com/samsonFive/berry-intelligence-os/pull/535) method to current
  consumers: the overlay copies only display/attribution entity fields while
  retaining repository signature invalidation, visibility and duplicate-ID
  semantics. All 49 focused checks passed, including the unchanged 500ms test
  and four freshness/visibility/isolation/duplicate regressions. Sixteen paired
  full-index/projection HTML comparisons were byte-identical. Windows/Python3.13 median
  requests improved from 336.08 to 296.07ms for Atlantic Blue and 343.73 to
  274.66ms for BluGenix. Receipt:
  `artifacts/experience-consolidation/reader-projection-paired-current.json`.
  These local samples do not replace final-head Linux CI or close TD-122.

## Release work after local G2

Native bounded Briefing reading, Workspaces saved-investigation/output entry and
existing Learn consumption are mounted and locally accepted. Their browser,
save/conflict/export and cross-surface restoration receipts are recorded in
`acceptance/G2-LOCAL-ACCEPTANCE.md`. The final Learn crop-note labeling proof above
adds no authored facts and makes no provider request. Existing authored Workspace
and Learn research/edit/version workflows remain explicit governed compatibility
destinations with native return context.

Complete required checks on the final integrated head. The green Reader-repair
checkpoint does not substitute for the newer canonical/brand-adapter head or
close broader performance debt.
Prepare the concrete server build/backup/rollback receipt before
production promotion. The optional Node network-namespace deployment override is
source-ready. Local Docker is unavailable; final-head container checks and the
separately authorized live smoke remain release gates. No production service,
configuration, data or inbox change has been made by this candidate. Production
promotion and production paid commands remain separately unauthorized.
