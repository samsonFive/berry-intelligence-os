# Local continuous investigation rehearsal

11 November 2026. Current status: root reviewed the fresh actual packet and
recorded G1/V1 ACCEPTED. See `G1-V1-ACCEPTANCE.md` for exact asset hashes, current
evidence, real command parity, token receipts and scope limits. The earlier
packets below remain historical evidence; fixture-only checks do not pass V1.

The complete deterministic packet is
`artifacts/experience-consolidation/v1/rehearsal-1794433862446/`, mounted against
the frozen `index-DZvR_nf4.js` bundle. All 16 direct assertions passed with no
uncaught client errors or model-turn requests. It contains five populated desktop
PNG states, populated narrow detail, status-failure evidence, `acceptance.json`
and a continuous 70-second video. The full synthetic 1–9 axis was checked after
layout settled and inspected in the resulting screenshot. The lead reviewed all
five states as structurally/content appropriate, with two small source polish
changes still awaiting the next consolidated bundle.

The first funded comparison attempt is preserved separately under
`rehearsal-1794432686082/`. SDK metadata returned HTTP 200/default; the single
allowed agent/run POST returned HTTP 200/SSE, but no view change completed and
the command UI reported failure. No terminal receipt survived that attempt;
usage is unknown, not zero. The dedicated runtime was stopped.

The separately authorized instrumented retry is preserved under
`rehearsal-1794434187166/`. It completed two real HTTP 200/RUN_FINISHED responses
with 2,356 input tokens, 219 output tokens, 81 reasoning tokens and zero cached
input tokens reported. Three tool-call event sequences appeared; no RUN_ERROR or
uncaught page error occurred, but no supported view change was applied. G1 remains
FAILED. That trace retained event counts and usage only; the historical tool names
and results are irrecoverable and must not be inferred. The dedicated runtime was
stopped again. The safe tool/lookup recorder then passed the actual SDK offline
fixture: three interleaved search streams, actual local lookup statuses/counts,
continuation results, composite comparison and acknowledgement. This is provider
zero evidence under `offline-command-diagnostics.json`.

Automatic approval review rejected launching the proposed additional paid
diagnostic before a process or provider request started. Its stated reason was
that another paid workflow after prior attempts could send private investigation
selectors and spend credits, and the user had not explicitly approved that
additional retry. No workaround or further provider attempt was made. Explicit
user approval was subsequently obtained for exactly one additional real
diagnostic, which succeeded; the accepted receipt above supersedes this prior
block. Save/reopen remains NOT_RUN until the native UI is integrated.

The root starts one local authenticated server and loads ephemeral session state
in memory. Import `frontend/e2e/experience-rehearsal.mjs` into that session and call
`runRehearsal({baseURL, storageState, revision, outputDir})`; `storageState` is an
in-memory object, never a filename. An optional `cookies` array works similarly.
No secret value belongs in a command transcript, artifact or checked-in file.
The script rejects non-local server addresses.

The executed module uses bundled Playwright and Chromium 1234. It creates a fresh video
context, preserves actual authenticated records, and writes five desktop states,
a narrow-state screenshot, one continuous video and `acceptance.json`. It tests:

- Supported populated relationships before interaction, company focus without
  scope/readout/cohort changes, exact relationship-to-source ancestry.
- Source close, Back/Forward and reload restoring the same URL/state.
- Nested source Brief URL section and canonical Article reload round trips.
- Separate comparison pins, China scope, company comparison and actual AG Grid.
- Explicit synthetic metric/axis/specimens with independent demo selection.
- Saved-in-URL demo subset reload without changing real company pins.
- Narrow keyboard containment, Escape/focus return, click/touch equivalents and
  reduced-motion behavior.
- No provider turn during ordinary navigation. Unexpected runtime turns are
  blocked and recorded as defects; no mocked response is substituted.
- Native surface return, Back/Forward and reload preserve an actual nonzero
  viewport after all module DOM is ready. Earlier premature-scroll harness
  failures were reproduced and corrected; no SurfaceScroll product edit was
  required. Stored coordinates contain only paths/opaque keys, and logout clears
  that UI memory.
- A deliberately injected HTTP 503 for Copilot status alone leaves populated
  direct investigation controls available; domain APIs remain actual and unmocked.

Optional `approvedCopilotCommand` enables one real, explicitly approved provider
turn through the actual command UI, compares it with equivalent direct controls,
and records the real runtime request. Without this option, provider acceptance
stays NOT_RUN. A missing provider stays BLOCKED. SDK discovery requests are not
counted as model turns. The command's text may be retained in the acceptance
record, so it must contain only the approved public scenario and selectors.
The worker now retains only known structured runtime diagnostic types/fields,
terminal event counts and numeric usage receipts. Raw provider errors, prompts,
tool arguments, credentials and model text are discarded. These diagnostics do
not retroactively recover missing receipts from the first attempt.

Optional `saveAndReopen({page, context})` allows the root to add the actual native
save/reopen UI sequence after its owner integrates that surface. Until then,
save/reopen remains NOT_RUN rather than silently skipping a claimed gate.

An error records REWORK and the current failure screenshot. Completing the script
records REVIEW_REQUIRED: automated assertions and attractive isolated frames do
not constitute design acceptance. The lead reviews all five populated states,
the continuous recording and remaining G1/G2 dependencies before recording V1.

Initial read-only source review found these owner-assigned issues before runtime
evidence existed: DetailHost header structure versus horizontal CSS; structured
Article/media/document blocks not yet rendered; narrow focus selectors and
background inertness; nested preview Escape behavior. The root is implementing
those fixes. Recheck them in the mounted flow; do not assume source edits pass.
