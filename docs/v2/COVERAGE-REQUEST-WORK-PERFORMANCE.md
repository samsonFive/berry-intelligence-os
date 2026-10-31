# Reusing source work within one request

Coverage and variety profiles validate the same saved portfolio observations
more than once during a request. The profile-field inventory also builds a
candidate/provenance result that it never consumes. This performance follow-up
shares validated observations within the existing request corpus and lets
that inventory request source rows alone.

The next request validates current files again. CLI calls and other data
directories do not reuse the request snapshot. Failed validation is not cached
as success. There is no new process cache, stored response, serializer, source
capture or background job. Source-only reconciliation still evaluates every
name, crop, conflicting code and saved identity decision, and builds the same
candidate IDs needed by source rows. Its default full result is unchanged.

## Measured scope and limits

The private comparison alternates actual original implementations from
`3b0b4acca2d9e7e59823fb8b5b48f89a27a9c452` with this candidate in an
authenticated disposable public-seed copy. Each scope has three requests per
implementation; the table uses the median of the last two, omitting the first
cache-warming sample for each implementation.

| View | Original warm seconds | Candidate warm seconds | Identical HTML bytes |
| --- | ---: | ---: | ---: |
| Rutgers profile filter; all 522 source sections | 2.6450 | 2.5178 | 399,758 |
| Blueberry and Hortifrut | 2.3141 | 2.4406 | 90,148 |
| Planasa source detail | 1.4858 | 1.2111 | 19,060 |
| Blue Maldiva profile | 1.0766 | 0.8487 | 37,982 |

All 24 complete rendered responses match their respective original bytes.
The small, noisy sample supports a limited improvement to source/profile
reads, not a consistent Coverage-page speedup or a production/mobile latency
claim. The filtered Coverage sample is slightly slower. Reconciliation, large
mutable copies, cold startup and host contention remain open under TD-122.

Complete Coverage models also match for the unfiltered source inventory and
the company/berry view: 10,472,594 and 5,008,020 serialized bytes respectively.
Both implementations use the same synthetic candidate-builder clock in that
comparison; no fields are removed or normalized away. Separate unfrozen runs
showed differences only in newly generated `discovered_at` timestamps. A source
edit and byte-for-byte restoration become visible on subsequent requests.

## Verification and boundaries

Ninety focused tests pass, covering request lifetime, empty lists, validation
failures, another dataset, CLI edits, all saved source rows, same-label/code
conflicts, wrong crops, rejected/distinct/confirmed identities, unreviewed
patent references, photo holds and hidden-photo choices. Default candidate
provenance, stored user decisions and input records remain unchanged.

Native desktop and 412px review retains the dense source table, all 21 named
Hortifrut blueberry entries, lazy disclosure, original links, review handoffs
and the permission-held profile photo. The phone document and scroll widths
are both 397px. Only a fictional account is used. Record validation and the
1,797-page trusted static/Pagefind build pass without exposing drafts.

This branch adds no names, profiles, sources or market figures. Navigation
#443, source #444 and Map #446/#447 remain separate. All 31 accepted requirement
definitions/order and the expansion guide remain unchanged, as do schemas,
CPVO, footprints, Trade/Weather and shared/private workspace boundaries.
Exact-head required CI, current-canonical reconciliation and a fresh bounded
preservation/release review are still required before any deployment. Human
source, identity, role, current-rights and photo decisions remain separate.
