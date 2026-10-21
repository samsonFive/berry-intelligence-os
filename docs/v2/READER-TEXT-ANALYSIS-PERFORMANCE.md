# Reader text analysis: avoid repeated display work

An isolated production-runtime profile after the bounded name-normalization
improvement recorded 5,004 calls to `reader_content`, taking 8.247 cumulative
seconds within an instrumented 18.835-second variety-discovery call. These are
profiling measurements, not ordinary route latency or a general speed guarantee.

The Reader previously cleaned the selected summary up to three times in one
call. It now cleans each candidate summary once, checks that same result and
returns it. Summary-before-publisher priority and consent/access rejection stay
unchanged. Reuse ends with the function call; later source or analyst edits are
read afresh. No records, review outcomes or article bodies are cached.

Interstitial classification now checks block membership through a local set.
The original list of wall blocks, including duplicates, still supplies the
dominance threshold. Repeated access-screen text is not deduplicated out of the
classifier's evidence. Both changes are display/read-time work only: no source
capture, identity, publication, Atomic or qualification decision changes.

## Evidence

- 21 focused Reader/source-state tests passed, followed by 98 existing capture,
  Firecrawl, safe URL/redirect, one-click and preview-continuity regressions.
- An alternating offline comparison covers all 1,270 known records in the
  retained local runtime. Every field of every Reader result matches the prior
  implementation; all source inputs remain unchanged. The projection digest is
  identical across all four runs. Reader-function times were 0.507/0.587 seconds
  before and 0.316/0.405 seconds after. These are local function timings, not
  whole-page or production improvements.
- New regressions retain literal decoded text, fallback priority, mutable
  analyst edits, input immutability and duplicate-wall dominance. A call-count
  check prevents the original repeated summary work returning.

This is an optimization parity diagnostic, not the independent human variety-name
recall benchmark. It supplies no expected-name answers, source acceptance or
approved extraction marker. Required current-head CI and release verification
remain separate. TD-122 still covers repeated corpus scans, large pages and
broader request contention; this change does not complete the performance mission.
