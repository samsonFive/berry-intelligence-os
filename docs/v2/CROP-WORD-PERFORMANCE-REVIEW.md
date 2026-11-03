# Avoid crop-word scans of unrelated source prose

This performance child retains frozen #483 at `d8a28e31` and #484 at `3b55827b`.
Both parents have passing required checks, desktop/phone review and fresh isolated
preservation. Neither has release approval; no parent's approval is extended here.
Approved #477 remains live at `1ad5084f`.

## Problem and behavior

The full current request profile calls `paragraph_crop_ids` 24,232 times.
Most calls scan a source paragraph that contains none of the supported crop words.
The profiler places substantial self time in those scans; profiler-overhead
seconds are diagnostic rather than page latency.

The new necessary-prefix check skips the regex only when no crop-word prefix is
present. A positive hint still uses the original Unicode regex on the original
text, with its original word boundaries and exact result construction. Dotted
and dotless I take the original path because Unicode case-insensitive matching
and casefolding differ for these characters. Non-plain strings and malformed
inputs retain their original handling. Existing unusual Unicode failures are
preserved, not silently converted into an empty crop result.

Prefixes are derived from every current crop key. There is no cache, shared
mutable result, source narrowing, new naming grammar or change to paragraph/title
scope. Canonical records, human decisions, source text, roles, rights, photos,
schemas, provider settings and acquisition remain unchanged.

## Prototype evidence

Eight fresh processes in a cloned inactive server snapshot compare the unchanged
#484 implementation with an in-memory prototype. Limits are one CPU, 1 GiB memory,
no swap, no network or exposed ports and a 240-second bound. Every full unfiltered
11,326,567-byte typed discovery model, complete response context and rendered
HTML matches within each route's comparisons. Snapshot/runtime hashes and the
healthy live release remain unchanged.

| Route | Original seconds | Prototype seconds |
| --- | --- | --- |
| Company Varieties | 5.010 / 5.308 | 4.454 / 4.599 |
| Company-scoped Candidates | 4.748 / 4.791 | 4.714 / 4.296 |

Median improvements are approximately 12% and 6%. There are only two samples per
variant per route, with visible variation, and the first Candidates pair is
nearly flat. These prototype figures do not prove final-code or production
latency. TD-122 remains open.

The simpler ASCII-only matcher prototype was rejected because Candidates slowed
down. Earlier company-only source scoping, startup warmup and consent-check
experiments were also rejected rather than shipped; their private evidence and
the documentation-only closeout draft #485 remain separate.

The private 10,022-input contract checks original values and failures, Unicode
boundaries and independent mutable results. An initial ASCII-probe harness
mistakenly expected every Unicode input to return a value; the original also
raises on two of those inputs. The corrected contract compares matching failures.
The separate prefix probe passed this contract before starting.

All initial 112 focused implementation tests pass, including literal/Unicode
crop boundaries, source edits, heading scope, all four crops and declarations.
Broader tests, final-code server comparison, browser review, exact-head required
checks and fresh preservation remain before a separate release review. No
catalog/source/name/photo/Map human decision or worldwide-completeness claim is
created by this performance work.
