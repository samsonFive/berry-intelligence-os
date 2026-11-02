# Variety directory preparation review

The full variety directory remained slow after the Coverage performance work. A fresh server-copy visit took 10.12 seconds, without a controlled directory baseline. Profiling the actual directory handler then found repeated preparation: 23,606 raw photo validations and 58 source-identity/code-discrepancy rebuilds on a cold request. Profiler timings include overhead; they diagnose the repeated work rather than establish production latency.

This technical-debt child of presentation-copy #465 (`17a8197d`) changes only the existing `entity_list` handler in `app/main.py`. It uses the already-tested optional identity scope for the read-only candidate-count calculation, then exits that scope before photo processing. Multiple visible cards share the existing `SourcePhotoIndex` for that request. Single-card and empty results keep the original photo path. No matcher, validator, domain schema, source record, template or persistence contract changes.

There is no cross-request photo cache. Source edits, saved hides, catalog ambiguity and profile overrides are read again on the next request. Unknown reuse remains withheld by default; identity holds remain review-only. The read-only directory does not load private profiles or prepare private photos. All human publication, identity, photo and rights decisions remain separate.

## Controlled local results

Four fresh processes ran in baseline/candidate/candidate/baseline order against separate public-data copies. The baseline uses the exact parent handler with all other code held equal. Both pairs compare every typed business-context field, excluding only the framework Request object, and every unnormalized HTML byte.

| Directory request | Parent median | Candidate median |
| --- | ---: | ---: |
| Full directory, cold | 10.65 s | 2.25 s |
| Full directory, repeat | 7.03 s | 1.09 s |
| Blueberry, letter S | 1.85 s | 1.05 s |
| Single-name search | 1.37 s | 1.04 s |

All eight comparisons preserve complete models and HTML. Each broad result checks 105,422 typed nodes and 97,001 HTML bytes. All 2,974 source-data files are unchanged and no outbound connection occurs. These are local public-fixture measurements, not production percentiles or physical-phone timings.

All 396 affected tests pass, including six new request-boundary, source-edit, saved-hide, ambiguity, validation and read-only checks. Record validation passes; the static build emits 1,983 pages with no unpublished-content leakage. Native desktop and 412px review retain all 64 directory rows, crop filters, alphabetical navigation, the dense scrollable table and separate pending-name review. Selecting S shows nine of 64 varieties; the phone document has equal 397px client and scroll widths. A fictional account's first login opens Help. No real account is logged in and no review action is taken.

Exact-head CI and a fresh isolated server-data preservation/performance check are required before any separately approved release. The original 31 requirements and governing guide remain unchanged. Existing pending release questions retain their original scopes; this work grants no merge or deployment approval. TD-122 stays open for other slow paths and broader real-device measurements. Catalog enrichment and Learn #464 are excluded.
