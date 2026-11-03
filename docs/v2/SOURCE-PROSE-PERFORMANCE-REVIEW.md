# Source text preparation on cold catalog pages

Company Varieties and Candidates spend much of their first render preparing
source text and checking declaration formats. The isolated server profile found
19,173 article-format calls and 55,040 consent/UI predicate calls in one render.

The new preparation keeps the existing rules and all source data:

- Every supported article format requires an explicit variety/cultivar word.
  Paragraphs without those words return the same empty assertions/exclusions
  before preparing format patterns or crop context. Other discovery paths keep
  their existing grammar, source context and human review gates.
- The existing Reader UI predicate reuses decisions only for exact plain
  strings of at most 768 characters. Its process-local LRU holds at most 2,048
  strings. Long, opaque or changed text takes the original path. No record,
  identity, review state, permission or mutable result is cached.

Only `source_body.py` and `variety_universe/explicit_article_formats.py` change
at runtime. No data, schema, publication trust, identity, role, source-selection,
Atomic qualification, provider request or acquisition behavior changes.

## Measurement before implementation

The prototype ran on the unchanged tested #480 image using a cloned inactive
review snapshot. One CPU, 1 GiB memory, no swap, no network and no published ports
were retained. The test submitted no provider request and changed no runtime
file or live application state. This is an offline measurement, not deployment
or fresh final-code preservation evidence.

| Fresh process route | Original samples | Prototype samples |
| --- | --- | --- |
| Splendor Varieties | 6.58s, 6.17s | 4.94s, 5.14s |
| Company-scoped Candidates | 5.89s, 5.99s | 5.03s, 4.63s |

All eight renders preserve the exact HTML, complete typed template contexts and
11,326,567-byte typed discovery universe. The prototype avoids 18,785 empty
format checks while retaining all assertions and exclusions, including captured
article names. The short-text predicate records 40,479 hits and 14,546 misses;
retention remains capped at 2,048. Generated-candidate clocks are identical in
both controls; no result field is excluded to obtain equality.

The initial 87 focused checks pass, covering consent/access text, editorial
discussion, changed source text, opaque/long inputs, bounded retention, all four
crops, missing-crop exclusions, captured articles and company handoffs. The
broader Reader/News/article/source-fidelity suite passes 544 checks (overlapping
the focused count). Final-head CI, native review and fresh
production-copy preservation remain. The prototype does not claim universal
page latency or close TD-122; cold pages still take several seconds.

## Release and requirements

This child is based on frozen #480 (`53dd52e3`), which separately passes all
four checks/6,165 tests, native review and fresh preservation, and awaits its own
release approval. Approved #477 is live. The rejected #481 catalog-batch code is
excluded: its production-copy page timings did not improve usefully, and that
draft is closed without merge or deployment. Its receipts remain retained.

All original 31 definitions/order and the expansion guide remain. Current and
historical catalog completeness, independent expected-name review, unresolved
source/name/role/rights/photo and held Map figures remain human-owned work in
this same mission. Faster checks do not add a variety, verify a source, grant
photo permission or promote a claim. No additional paid Learn request is made.
