# News metadata decision performance — November 2, 2026

A fresh public-data profile of the deployed company varieties handler identified
News metadata qualification as a substantial cold-request cost. The profile
includes instrumentation overhead and is diagnostic, not a production latency
measurement. Request-scoped corpus preparation was included in the confirmation
profile; the earlier direct-helper profile is retained separately.

News uses only the existing qualifier's Boolean result. The new read-only
projection shares that full qualifier and its exclusions. After those exclusions
and government-source checks pass, an explicit crop plus industry wording, or
an eligible source with a specific crop, already determines the positive result.
Only in those cases can the projection omit company/variety-name searches and
unused explanation construction. Every other case follows the full path. The
ordinary qualification adapter still returns its complete reasons, editorial
topic and source context. No filter criterion, review decision, source record,
date, image, cache admission or cache-invalidation input changes.

## Verification and measurements

The focused 55-test set passes. It compares the Boolean result with the full
qualifier across the frozen metadata benchmark, exclusions, named-only hits,
source classes and government/origin URLs, and verifies input nonmutation.
Existing qualification and News tests remain. A further 82 Digest/account,
Map, tag and company-research tests pass. These are deterministic metadata
tests, not Atomic Evidence or model qualification.

Four fresh processes run baseline/candidate/candidate/baseline. The reference
loads the exact deployed `d5b619b2` qualifier. All sixteen complete business
contexts and unnormalized HTML responses match; only the framework Request is
excluded. Each process preserves all 2,997 public input files, with network
connections blocked. Compared model sizes range from 54,231 to 93,501 typed
nodes and responses from 17,929 to 214,969 bytes.

| Request, in sequence | Baseline median | Candidate median |
| --- | ---: | ---: |
| Splendor varieties, first request in a fresh process | 4.68 s | 3.86 s |
| News after the company request | 2.24 s | 1.43 s |
| China/blueberry News, subsequent request | 0.59 s | 0.58 s |
| Hortifrut varieties, subsequent request | 1.31 s | 1.31 s |

These are small local public-fixture samples, not live-server, device or
percentile measurements. The first experiment retained parity but had mixed
timings and repeated fallback checks; it was revised. A later sample overlapped
the independent cross-view test run and is retained only as parity evidence,
not timing proof. The final table uses the confirmation without concurrent
pytest. An earlier comparison harness's incorrect Hortifrut ID returned 404;
that failure is retained and the verified canonical ID used thereafter.

TD-122 remains open for source reconciliation, broad cold loads and real-device
measurements. Exact-head required CI, browser review and fresh isolated live-data
preservation remain release gates. This draft does not alter deployed #473 or
Help #474 and has no merge/deployment approval. The governing expansion guide,
all original 31 requirement definitions/order, data and schemas remain unchanged.
