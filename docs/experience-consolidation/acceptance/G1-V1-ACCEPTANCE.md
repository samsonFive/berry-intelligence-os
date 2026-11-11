# G1 / V1 accepted local rehearsal

11 November 2026. The root reviewer inspected all five fresh populated frames
and explicitly recorded **G1 and V1 ACCEPTED**. This covers the flagship local
Landscape/Reader/comparison/synthetic flow and real command parity, not an entire
application or production-release gate. Native saved-view UI/reopen and further
native surfaces remained pending at this checkpoint.

The mounted bundle was `index-TMvSoonX.js`, CSS `index-Cm9mpm9K.css`, integrated
onto canonical `1ebaab37`. W1 recorded:

- JS SHA-256 `9B99CE8BFD6C68134E37ADE6B0248D81574CABF2BB81FDC6E8349CC761F3F0F3`.
- CSS SHA-256 `E4D19D8639AFA510BD5F5B773A1B5E3635231CE9A1C0AC28B00B4EEE167555F8`.
- Runtime SHA-256 `C03E771606A72044E42F635504D3260511C481E263817321E26B986A996D72E9`.
- Frontend 58 tests and runtime 12 tests passed before this mounted run.

## Actual real command

The user explicitly answered **Approve one diagnostic retry** for one additional
literal command: `Compare Fall Creek and Costa in China`. That approval resolved
the earlier automatic-review block. There was one user command, with three SDK
continuation requests inside its bounded runtime window. No automatic additional
retry occurred, and its dedicated runtime was stopped afterward.

Actual browser → authenticated FastAPI gateway → dedicated Perplexity runtime →
registered frontend tools → actual read APIs → shared dispatcher → acknowledgement
completed. The approved provider/model remained `perplexity:openai/gpt-5.6-sol`.
All three provider responses were HTTP 200 / `RUN_FINISHED`, with no `RUN_ERROR`,
uncaught client error or unexpected model turn.

The recorded approved sequence was three `search_catalog` calls at revision 0:
company/Fall Creek, company/Costa and geography/China. Their frontend result counts
were 2, 2 and 1. `show_portfolio_comparison` then returned `ok:true, code:applied`,
followed by acknowledgement. The complete normalized Copilot context matched the
equivalent direct-control context exactly: China, Fall Creek then Costa company
cohort, company comparison lens, and all other selectors preserved.

| Continuation | Input tokens | Output tokens | Total tokens | Reasoning tokens | Cached input |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 1,153 | 112 | 1,265 | 22 | 0 |
| 2 | 1,561 | 56 | 1,617 | 0 | 0 |
| 3 | 1,665 | 139 | 1,804 | 121 | 0 |
| Total | 4,379 | 307 | 4,686 | 143 | 0 |

The runtime exposed token usage, not a billed USD receipt. No actual dollar cost
is asserted. The first failed attempt's usage remains unknown. The earlier
instrumented failed attempt reported 2,356 input / 219 output tokens but no view
change; its exact historical tool sequence was discarded and cannot be
reconstructed. The later success does not establish a unique cause for that
earlier failure.

## Reproducible evidence

`artifacts/experience-consolidation/v1/rehearsal-1794436693801/` contains
`acceptance.json`, five populated desktop PNGs, narrow keyboard detail, status
failure evidence, and the continuous 71-second
`page@c4767bcf70f325794f2d5a553e20d89a.webm` recording. All 16 direct assertions
passed, including source ancestry/Brief section/history/reload, explicit cohorts,
actual AG Grid, independent demo subset reload, narrow focus/Escape, reduced
motion, surface scroll restoration, SDK-status failure and logout clearing.

The mounted account-grid packet is documented in `GRID-LAYOUT-QA.md`. The root
also reviewed `initial-polish-current.png`: the main focus marker is localized,
and the first Costa paths show VIP and Eterna while qualified links remain
available with their caveats.

Reports retain only approved tool names, argument keys/revision/known catalog
labels, lookup/result status counts, token usage and endpoint/status/header-time
summaries. Raw provider text, tool argument payloads, source bodies and credentials
are not diagnostic artifacts. API timings are response-header latency during this
local warm-server run, not a separate cold-start or performance benchmark.
