# Reader text analysis: avoid repeated display work

October 23 follow-up: [the broader performance release](PERFORMANCE-READER-PUBLISHER-COVERAGE.md)
adds bounded, private exact-input memoization. Unchanged source projections can
now be reused between calls; edits invalidate immediately and mutable results
are copied. The original within-call-only implementation and measurements below
describe the prior baseline, not the current cache policy. No rendered page,
human review outcome or identity decision is cached by the Reader projection.

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

## Metadata-only article fast path

The private article-name audit now checks whether article text exists after
considering matching human-affirmed recoveries and exact-source Reader captures.
If there is no text, summary/description/transcript classification cannot make
that record an eligible article. It skips that display work while retaining the
known-source count and every other accounting field. Published summary-based
name discovery remains on its existing separate path. Current article edits and
captures are considered on every call; no eligibility decision is cached.

## Evidence

- The metadata-only server rehearsal now preserves all 3,440 Reader results and
  every 65-profile/1,164-candidate field except generated discovery time.
  Alternating discovery calls take 10.589 / 8.905 and 10.167 / 9.406 seconds
  without/with the fast path. The current follow-up also fixes the separately
  measured [entity-profile attribution scan](ENTITY-PROFILE-ATTRIBUTION-PERFORMANCE.md);
  its whole-page comparison must not be credited solely to Reader cleaning.

- Two fast-path regressions and the existing captured/pending/declared-article
  suites pass: 59 tests. Metadata-only and transcript-only inputs retain their
  accounting, newly added body text is visible immediately, and replacing that
  body with a consent wall excludes it again.
- An alternating comparison of the complete 64-profile/1,165-candidate local
  projection preserves every field except the excluded generated discovery time.
  Runs without/with the fast path took 6.532/3.790 and 4.202/3.051 seconds.
  This is local discovery-function evidence, not production page latency.

- 21 focused Reader/source-state tests passed, followed by 98 existing capture,
  Firecrawl, safe URL/redirect, one-click and preview-continuity regressions.
- An alternating offline comparison covers all 1,270 known records in the
  retained local runtime. Every field of every Reader result matches the prior
  implementation; all source inputs remain unchanged. The projection digest is
  identical across all four runs. Reader-function times were 0.507/0.587 seconds
  before and 0.316/0.405 seconds after. These are local function timings, not
  whole-page or production improvements. The initial Reader-only server
  comparison preserves all 3,440 Reader results and the 65-profile/1,164-candidate
  projection, but its timings do not demonstrate a repeatable whole-page speedup.
  The additional article fast path therefore needs its own server rehearsal and
  fresh exact-head CI rather than relying on that earlier green head.
- New regressions retain literal decoded text, fallback priority, mutable
  analyst edits, input immutability and duplicate-wall dominance. A call-count
  check prevents the original repeated summary work returning.

This is an optimization parity diagnostic, not the independent human variety-name
recall benchmark. It supplies no expected-name answers, source acceptance or
approved extraction marker. Required current-head CI and release verification
remain separate. TD-122 still covers repeated corpus scans, large pages and
broader request contention; this change does not complete the performance mission.
