# Cold company and literal-text preparation

Company-scoped News was screening unrelated headlines before applying its company
filter. A direct Candidates visit also missed the existing request-local identity
preparation. Source-heavy pages repeatedly decode the same short text fragments.

This candidate applies the same conservative company link/mention rules earlier,
prepares identity lookup for one Candidates render, and bounds reuse of literal
HTML decoding to1,024 builtin strings of at most2,048 characters. Other values
retain their original coercion behavior. Unicode whitespace and paragraph breaks
remain equivalent to the prior decoder. No record, review decision or permission
is cached by the decoder; nothing is written to application data.

The full portfolio projection remains. Source selection, Reader cleanup and the
discovery grammar retain their exact existing code. Source-only and additional
Reader/discovery refactors were rejected because they moved work or did not
provide a reliable improvement over this smaller change.

## Development evidence

All363 final affected checks pass, including Unicode/paragraph preservation,
custom coercion/current edits, bounded admission, company mentions, malformed
legacy rows, source bodies, captured articles and identity matching. The original
31 requirement definitions/order and the governing guide are retained.

An isolated production-copy prototype passed32 complete response-model/raw-HTML
comparisons, with all original files unchanged and networking disabled:

| Measured path | Baseline | Candidate |
| --- | ---: | ---: |
| Cold company overview / News | 1.96s | 1.15s |
| Cold entry into Candidates | 7.67s | 6.17s |
| Cold company Varieties tab | 8.19s | 6.82s |
| Complete seven-request workflow, median of two fresh processes per version | 20.77s | 18.04s |
| Global News control | 3.30s | 3.35s |

These are development-copy measurements, not live post-deployment claims. The
frozen final head still needs its own required checks, native review and fresh
bounded production-copy acceptance. The32 response comparisons do not complete
the separate human-owned32-source expected-name worksheet.

TD-122 remains open: global News is essentially flat, and first source-heavy
visits remain slow. This candidate improves a specific path; it is not a claim
that every page is fast or that the broader mission is complete. Physical touch
hardware and real-provider Learn quality/cost remain unverified.

## Release boundary

Only Main, company News preparation and literal HTML decoding change at runtime.
No source/data/schema/provider additions or human review decisions are included.
Existing accounts, first-login history, edits, private research, settings and
persistent mounts must be preserved. Prepare a fresh backup and rollback and
obtain approval of the tested exact head before merging/deploying. Completed
release #475 and its approval are separate and must not be repeated.
