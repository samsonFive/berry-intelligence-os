# Avoid parsing paragraphs with no declaration syntax

This performance child retains frozen release #483 at `d8a28e31`. That release
has all four checks, 6,214 passing tests, native desktop/phone review and fresh
isolated preservation; its merge/deployment approval remains separate. This
child does not change #483 or extend any approval.

The current-head server profile identifies source preparation and declaration
reconciliation as the largest remaining company Varieties/Candidates costs.
The base declaration parser is called more than 20,000 times on the tested
copy, although most paragraphs have no declaration syntax.

The implementation adds one necessary-syntax check after the existing berry
input normalization. English lists, denomination lists, selection codes,
Spanish and Polish declarations and any pipe table still enter the original
parser. The check uses the original Unicode case behavior and does not require
word boundaries absent from the original grammar. It does not run ahead of the
separate full-article paragraph/heading logic: singular cultivar declarations
and the four-paragraph heading scope remain intact. Future grammar additions
must also update this gate when they introduce another necessary literal.

No naming pattern, crop inference, identity match, exclusion, human decision,
source text, caption, canonical record or role changes. There is no new cache,
source fetch, provider call or write path. Invalid input normalization keeps its
existing failure behavior rather than being converted to an empty result.

## Measured prototype

Eight fresh processes on a cloned inactive production snapshot compare the
original #483 function with an in-memory prototype. The unchanged #483 image
is used, with one CPU, 1 GiB memory, no network/ports and a 240-second bound.
Complete typed contexts, the 11,326,563-byte discovery model and rendered HTML
match within every pair; original snapshot/runtime hashes remain unchanged.

| Route | Original seconds | Prototype seconds |
| --- | --- | --- |
| Company Varieties | 5.072 / 5.124 | 5.016 / 4.663 |
| Company-scoped Candidates | 5.517 / 4.960 | 4.550 / 4.925 |

The prototype bypasses 19,982 empty-result paths among 20,463 checks. Median
changes are about 5% and 10%, with visible timing variability. These are paired
prototype measurements, not a production latency guarantee or a claim that
cold loads are solved. TD-122 remains open.

The initial 99 focused tests pass, including multilingual tables/lists,
Unicode labels, concatenated delimiters, negation, exclusions, all four crops,
singular article names, heading expiry, source edits and invalid inputs. A test
setup error initially addressed the existing result as `name` rather than
`candidate_name`; only the test assertions needed correction. The broader 294 affected tests also pass (overlapping the focused set).
Final-code real-data comparison, browser verification, exact-head CI and later
release review remain. Human catalog/source/photo/Map decisions stay in their
existing queues, and worldwide completeness remains unproven.
