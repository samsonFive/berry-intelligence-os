# Candidate review: bounded name normalization

The candidate review page performs the same literal name normalization many
times while checking source observations against the catalog. An isolated
64-profile catalog run called it 579,425 times. This draft reuses the result of
that pure string transformation for at most 4,096 exact input strings, each no
longer than 256 characters. Longer inputs are processed without retention.

All matching and review logic still reads the current candidate, aliases,
codes, crop and catalog fields. No candidate result, human decision, source
body or mutable record is cached. The existing normalization algorithm and its
identity semantics are unchanged. No schema, record or qualification marker
changes, and no network acquisition is introduced.

## Validation

Regression checks cover repeated work, bounded retention, long-input bypass,
unchanged Unicode/code normalization, mutable name/alias/code/crop edits and
fresh result objects. Existing identity, portfolio and review-navigation tests
run alongside them. Required current-head CI remains the merge gate.

Alternating local runs with this string cache disabled/enabled produced equal
complete candidate projections: 64 profiles and 1,165 candidate keys under
current canonical code, including all match/review/provenance fields. Comparison
excludes only the generated `discovered_at` timestamp. Disabled runs took
8.816 and 7.235 seconds; enabled runs took 3.511 and 2.645 seconds. This repeat
ran after the regression tests finished to remove their CPU contention. These
are local discovery-function measurements, not production route timings or a
general latency guarantee. Private receipts retain the
projection digest and exact inputs. Catalog research drafts contain independent
identity-discrepancy fixes and can therefore project a different candidate count.

## Remaining performance work

The local research preview still returned approximately 4.1 MB of HTML for
1,157 rows. Filtering to one alphabet group reduced that to approximately
257 KB, but still rebuilt the candidate universe. This draft addresses repeated
normalization; large-page rendering, repeated discovery scans and other slow
routes remain measured follow-up work under TD-122. Existing fragment links,
A–Z navigation, source scope and human decisions remain available.

This draft is separate from catalog enrichment #399–400 and can be reviewed
against deployed canonical independently. It is not deployed by its tests.
