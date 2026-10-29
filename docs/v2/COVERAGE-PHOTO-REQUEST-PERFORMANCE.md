# Faster variety profile coverage with the same photo decisions

The coverage table was repeating source-photo validation and code/name conflict
checks for each catalog profile. On the current public seed, 64 profiles scan
497 source sections. Instrumentation found 23,296 photo validations and 56
rebuilds of the same portfolio identity notes during one inventory calculation.
This is a measured bottleneck in the existing page, not a reason to weaken its
photo identity or reuse gates.

The inventory now prepares source references once per call. It reuses validated
photo details, larger-preview validation, exact catalog resolution and existing
code/name discrepancy notes within that call. The original validator, resolver,
gallery, human overrides and dispute rules remain authoritative. Single-profile
and candidate paths retain their existing behavior. A prepared index rejects
different source/catalog input objects; no index persists between requests.

## Actual comparison

The comparison loads the three original implementations from committed baseline
`f1f11d99c0e8ad54cfdf3dcd3a5bc47773e3295b`, wires their original photo/review
functions together and alternates them with the candidate over the same public
data. The runtime, protected user data and production are not involved.

| Alternating call | Before | After |
| --- | --- | --- |
| First pair | 6.606s | 0.5857s |
| Second pair | 4.8731s | 0.6256s |

All four return the same 40,819-byte serialized inventory, SHA256
`b3c200bf8ee57b102940f6c76eed264567af5dd48f152b84418d2f56203d13b9`.
Deep comparison confirms input records are unchanged. Photo/rights/trait/company
gap counts remain 10/13/33/10; no source coverage or catalog addition is claimed.
These are local function timings, not authenticated route timings or proof
that the entire application is fast. Source discovery, rendering, current-user
runtime volume and wider contention still need their own measurements.

## Verification and limits

Four new tests exercise the full real corpus, identity-held Rutgers photo,
larger original previews, ambiguous catalog names, later source edits, invalid
private image URLs, source-snapshot mismatch and saved hiding/revisions.
They compare every profile's exact source photos and review links against the
unshared path and check one identity-note calculation per inventory, with each
source photo validated once. The same name in a different crop cannot gain a
photo through this optimization.

The affected photo/editor/coverage/review/preview suite passes 69 tests with one
existing ReportLab deprecation warning in 40.17s. Native review verifies all64
rows and unchanged counts, the Rutgers missing-photo filter and the existing
review link to both NJ09-2-1 and Rutgers D'Light. At412px the397px document has
no horizontal page overflow; the720px table scrolls within349px, with no image
loaded by the coverage inventory. One fictional account was used and no review
decision submitted. Tab58 is closed and the temporary viewport reset. Exact-head
CI is still required before this separate draft is ready.
It does not inherit #421 or #426's production-copy or deployment proof. All31
accepted requirements/order, the immutable guide, existing records and human
source/identity/catalog/reuse decisions remain. No schema, registry, footprint,
hosted image pipeline or backend domain behavior is changed.
