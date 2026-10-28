# Faster coverage photo inventory — October 27, 2026

The coverage page used to validate and match every portfolio photo again for
every catalog variety. A profiled request recorded 8,444 validations across 65
profiles. The coverage inventory now builds a request-local lookup once, using
the existing exact-name, berry, ambiguous-alias and code/label discrepancy gates.
The individual profile/candidate photo path is unchanged.

There is no cross-request cache: changed source metadata, names, aliases, crops,
private profile edits and permission details are read again on the next request.
The final gallery still applies user overrides and does not display a photo with
unknown reuse terms automatically. Invalid photo metadata remains a visible
validation failure, not a silently missing reference. Nothing is acquired or saved.

## Isolated comparison

Alternating baseline/prototype runs used the same retained production-data copy,
the existing #410 image as baseline, ordinary startup warm-up and fixture login,
and disabled network/collection. This isolates the additional coverage change
from #410's already-reviewed profile/Reader improvements.

| Full coverage response | Baseline runs | Optimized runs |
| --- | --- | --- |
| First after startup | 5.965 / 5.654 s | 4.771 / 4.817 s |
| Repeated | 3.929 / 3.925 s | 2.807 / 3.013 s |

The full 1,421,551-byte rendered page is identical across all four runs. The
missing-photo view also retains identical HTML, profile counts, links and all
field values. The complete individual photo projection matches for all 65
profiles, including fourteen available source references. All 9,774 original
protected JSON files and account rows remain unchanged. The prototype's additional
company query used an unknown ID and returned an empty scope; it is not evidence
of a populated company-filter workflow. Final current-head review must include
the actual company ID and a populated scope.

Seven new regression cases verify crop separation, ambiguous aliases, literal
code conflicts, explicit identity holds, duplicate-source ordering, source edits,
read-only inputs and rejecting invalid metadata. The quantitative regression
ensures one validation per source photo rather than per catalog variety. Together
with existing photo/profile/portfolio checks, 76 tests pass.

Private profiling and prototype receipts remain under ignored
`inbox/coverage-performance/` and the isolated host directories
`coverage-profile-022d8774-20261027-v2` and
`coverage-photos-prototype-20261027`. The first profiling helper was stopped after
an inefficient verification loop was found; only the corrected run is evidence.
The immutable guide and all 31 accepted requirement definitions/order remain.

Fresh exact-head CI, the committed-code preservation/valid-filter rehearsal,
final native browser review and release approval remain before deployment.
The large HTML response, other repeated source/catalog work, physical phone
performance and broader TD-122 scope remain open. This change does not approve
source text, names, identities, current rights or photo reuse.
