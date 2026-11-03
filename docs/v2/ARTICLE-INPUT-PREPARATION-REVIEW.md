# Article preparation experiment — excluded from release

The final implementation preserves all eight complete outputs but makes the
Company workflow slower. It is excluded from release and retained only on the
experimental branch. No code from this experiment is merged or deployed.

Company Varieties and Candidates rebuild the same complete private article
selection on consecutive pages. This change reuses that selection within the
process when the full published and pending inputs and all five source-file
collections remain unchanged. It retains the global corpus and original
selection, identity and review rules.

The five collections are daily news archives, packet captures, Reader captures,
capture image previews and Source Fidelity artifacts. Input records are keyed
as an exact builtin graph, including container types and alias structure.
Metadata-change time, modification time, inode, size, ownership, mode and link
state invalidate file reuse. Fingerprints are checked before and after copying
or calculating a result. A changing or unreadable snapshot is recomputed, not
stored as unchanged. Replacement selectors also invalidate their memo.

One runtime file changes. There is no disk cache, GET write, acquisition,
provider call, background warmup or rendered-response cache. A bounded private
memo holds at most two entries, 32 MB total and 16 MB per result, using existing
owned-copy behavior. Unsupported inputs use the original selector; custom
reducers cannot run during key creation. Windows retains its original path
because its ctime may describe creation rather than metadata changes. This
restriction concerns performance, not visible content or review behavior.

## Evidence and limits

The process-only prototype preserves complete typed article bundles, the full
unfiltered universe, complete typed response contexts and HTML across eight
fresh-process comparisons on a disposable production copy. All source-copy
bytes and healthy live state remain unchanged. The second page is faster, but
initial prototype validation adds cold cost: Company-first total is 6.641 →
6.346 seconds, and Candidates-first is 6.452 → 6.305. Prototype cold medians
are 5.054 → 5.134 and 4.711 → 4.961 seconds. These are not final-code gains or
a claim that cold loading is solved.

The implementation avoids duplicate stat calls for ordinary files while
retaining link/target checks, preserves alias structure in its key and limits
reuse to platforms with POSIX change-time semantics. The exact-module comparison
then measures Company cold 4.616 → 5.187 seconds and its two-page workflow
6.013 → 6.434. Candidates cold is 4.595 → 4.742, while its workflow improves
slightly from 6.231 → 6.103. These mixed/regressing results do not justify a
release. The admitted memo occupies 9,271,581 bytes on the tested copy. Creating
and validating that additional representation costs too much on the first visit.
TD-122 remains open; faster later-page figures do not override this result.

The measured runtime module SHA-256 is
`c0f687c62d1eded5e42f8df0437ff0b517469b3e693530e148a2766ad0cd097b`;
the private final result SHA-256 is
`cb19e70d9a44bf5524d288cc875acd8c1297b9aa09681f6579d26f47d3b06d50`.
Complete typed article bundles, the unfiltered universe, complete typed contexts
and HTML match; source-copy bytes and healthy live state remain unchanged.

Initial local validation passes 108 checks with three POSIX-only skips and zero
attempted external connections. An additional fictional-source probe matches
the original selector across 15 input and file changes, including capture
deletion, image edits, consent fallback and pending review changes. Further
Source Fidelity decision cases pass locally; five cache-specific cases remain
POSIX-only. The final local memo file passes 17 cases with those five skips and
zero external attempts. Linux CI, browser and release rehearsal were not pursued
after the whole-workflow measurement rejected the implementation.

The separate offline restart-model experiment also preserves all 16 complete
outputs and improves reuse after a worker restart. It writes only inside a
disposable container's temporary folder. No durable model cache is implemented
or proposed for this release; its results do not prove first-install gains.
The earlier Reader-key experiment #489 remains closed and excluded.

Existing records, canonical varieties, source/identity/role/rights/photo/Map
decisions, private Digest/layout boundaries, original 31 requirement definitions
and protected schemas remain unchanged. This draft does not close the mission.
