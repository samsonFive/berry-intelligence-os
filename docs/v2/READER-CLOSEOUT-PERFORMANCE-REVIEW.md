# Reader closeout performance review

The first canonical-target #468 check failed its existing 500 ms warm-Reader
acceptance test: one request took 538.9 ms, while 5,864 other tests passed.
Earlier passing component runs do not erase that failure. The threshold and
test remain unchanged.

An isolated public-copy profile of the actual synchronous Reader handler found
1,051 repeated boundary-search calls, each rebuilding an escaped regex and
entering the regex engine's cache. The revision prepares the **same literal
pattern with the same flags**, without changing entity inventory order,
suggested subjects, regex word boundaries or Unicode case behavior.

Only builtin string needles of at most 256 characters enter a 4,096-entry
process-local pattern cache. Longer and nonbuiltin inputs keep the original
path. This holds compiled patterns only, not article bodies, user layouts,
Digest state, authenticated responses or trust decisions. Changed names and
aliases use their current literal keys; no cross-request record result is
retained. No matcher vocabulary, identity rule, repository, schema, source or
qualification changes.

## Evidence and limits

Four fresh processes run in parent/candidate/candidate/parent order. Twelve
comparisons cover a sample publication, a stored Hortifrut publication and an
explicitly fictional pending article. Every typed business-context value and
unnormalized HTML byte matches; only the framework Request object is excluded.
All 2,974 source-data files remain unchanged and outbound connections are blocked.

Warm medians were 153 → 113 ms, 151 → 116 ms and 119 → 93 ms respectively.
The first pair was nearly flat; the second was faster. Filesystem and host
variation remain material. These small local comparisons are not production
or physical-device percentiles, and cannot promise that scheduling never
exceeds 500 ms. Fresh exact-head CI and isolated server-data verification are
required before release.

Four regressions cover Unicode and punctuation boundaries, repeated literals,
updated names/aliases/source identity, long/nonbuiltin fallback, bounded cache
admission, full attribution and inventory order. The initial focused run passes
27 tests, including the unchanged warm-Reader test. The original 31 requirements
and governing guide stay intact. The failed CI log and complete comparison
receipts remain private.

This is a measured closeout repair within the platform release. Frozen #466
retains its original head and evidence; its exact-head image is not sufficient
to approve this revised release. Source #467, catalog/Map #449 and Learn #464
remain separate. A new tested head, release-time backup, rollback and explicit
release approval remain required. The current release base is now live #470
(`d2f6eb96`); its private research, spreadsheet integration and user records must be
retained. The original #443-based controls are component evidence, not final
acceptance of the reconciled release.
