# One owned catalog per portfolio calculation

Company and variety-candidate pages can construct about 900 source candidates
while reconciling a portfolio. Their original identity matcher already has a
conservative name shortlist, but each candidate still checks the same complete
catalog for changes. This draft snapshots the catalog once inside that explicitly
read-only calculation. The original matcher still decides every result, in the
original order. No matching result or index survives the calculation.

The existing complete-input/day memo remains outside this scope, so a normal
warm hit does not prepare another catalog. Ordinary request lookups retain their
per-lookup edit checks. New calculations take new snapshots, including changed
names, aliases, registrations, crops, ordering and deletions. Human decisions,
source/code conflicts, warnings and provenance are reapplied as before.

Preparation accepts only plain, acyclic input and supported matching fields;
opaque objects and generators keep the original path without extra coercion or
consumption. The calculation receives an owned copy, leaving caller data intact.
An unexpected catalog write or concurrent caller change refuses the result before
an outer memo can retain stale decisions. Nested and concurrent calculations
restore their prior contexts, including when a calculation raises an exception.

## Validation and limits

610 affected checks pass with external networking disabled. The original
unindexed matcher remains the complete-result oracle across names, codes,
registration precedence, crops, row ordering and duplicates. Full portfolio
comparisons additionally cover rejected, distinct and confirmed human decisions,
conflicting source codes, included/excluded sources and candidate projections.

The local comparison uses actual application files against exact #514 baseline
`577a23c9`, tracked public seed data and a separate empty inbox in each fresh
Python process. It alternates baseline/candidate order and compares complete
typed article bundles, candidate universes, page contexts and HTML. An invented
unreviewed article appears only after the next rebuild. All 3,444 tracked public
input files remain unchanged; there are no provider requests or production reads.

The completed four counterbalanced replicates per route order use 16 fresh
processes and compare 24 complete response pairs (48 individual responses).
All compared values match, and all eight complete workflow pairs improve.

| Workflow | Baseline median | Owned-catalog median | Change |
| --- | ---: | ---: | ---: |
| Company first, three-page total | 9.12 s | 7.93 s | 13.0% faster |
| Candidates first, three-page total | 8.68 s | 7.41 s | 14.7% faster |

First-visit medians improve for both route orders. One of four Candidates-first
cold samples regresses about 3.2%; subsequent warm visits also vary, with some
regressions. The complete-workflow gain does not establish that every individual
visit improves. All confirmation samples remain in the retained result.

These are bounded Windows handler measurements on an existing filesystem cache.
Imports and comparison work are excluded from the handler timings. They are not
private-data or live-site acceptance, a cold-filesystem guarantee, or a promise
that every visit is faster. TD-122 remains open pending current-copy performance
and preservation checks. Current-head CI and release approval remain required.

This local draft is isolated from #514's frozen staging candidate. Its testing
and deployment approvals are not inferred from any prior release. No catalog
record, schema, review gate, provider, data mount or deployment setting changes.
The canonical expansion guide and all 31 original requirements remain unchanged.

Ignored evidence: `inbox/owned-portfolio-performance-20261104/`.
