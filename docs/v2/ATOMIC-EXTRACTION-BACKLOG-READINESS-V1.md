# Atomic Extraction Backlog Readiness V1

Status: implementation complete; extraction remains disabled.

## Contract

`python scripts/extraction_backlog.py --status` applies
`atomic_extraction_source_text()` to every published Evidence record and
derives readiness without writing a new trust state. `--manifest 10`, `25`, or
`100` writes a reproducible private manifest beneath
`inbox/operations/extraction-backlog/`. Normal output and manifests never
contain source bodies.

Ready inputs are limited to full retained article bodies, retained transcript
text, and normalized structured-registry records. Summary-only, missing,
unsupported, known fictional seed, duplicate, and superseded inputs cannot
enter a pilot. Duplicate exclusion reuses the conservative canonical-URL and
exact-title contract. Exact content hashes may collapse only extraction-ready
inputs; repeated thin boilerplate is measured separately and is not mislabeled
as a reprint.

Every manifest binds ordered Evidence IDs to exact extraction-source hashes,
the extraction version, corpus fingerprint, and a qualification identity. The
current manifests deliberately use
`UNBOUND_REQUIRES_EXPLICIT_QUALIFICATION`. A future runner must refuse an
unbound manifest, verify every current source hash, require the matching human
qualification marker, resume by the bound identity tuple, isolate failures per
source, and create only untrusted review proposals. Auto-publish is false.

## Actual production corpus audit

The read-only 2026-08-23 production snapshot contained 1,268 published
Evidence records. The two production-only publication artifacts were included;
neither retained a full body or transcript. Results:

| Classification | Count |
|---|---:|
| Ready full article | 0 |
| Ready transcript | 0 |
| Ready structured registry | 36 |
| Thin description only | 1,227 |
| Missing source content | 0 |
| Unsupported known seed | 3 |
| Deterministic duplicate / superseded | 2 |

The 36 ready records are 35 Blueberry and one Strawberry, all structured
government/registry material, with no ready Raspberry, Blackberry,
multi-berry, or untagged input. No ready record has explicit language metadata;
all 36 are `undetermined`. Language is not guessed from page chrome or prose.

Structured-registry extraction input length is median 389.5 characters (97.5
estimated tokens), p75 429 (108), p90 673 (169), and maximum 967 (242). Article
and transcript distributions are empty.

Source-fidelity causes among non-ready records are 1,137 pre-body acquisition,
88 historic summary-only records, two spoken-media records without
transcript text, and three known fictional fixtures. Seventy-two excess records
share repeated thin boilerplate hashes; they remain thin-source failures rather
than false duplicate claims. The two actual duplicate pairs were identified by
the existing canonical-URL/exact-title contract.

## Bounded manifests

The private manifests use the failed local Qwen run's 121.874 seconds per
window only as a hypothetical timeout-exposure estimate. Proposal volume uses
the Gold Set's expected density, 54 propositions / 16 sources = 3.375 per
source; it is a planning proxy, not observed model yield.

| Manifest | Selected | Berry mix | Difficulty | Hypothetical runtime | Review proposals |
|---|---:|---|---|---:|---:|
| PILOT-10 | 10 | 9 Blueberry, 1 Strawberry | 2 easy, 3 medium, 5 hard | 1,218.740s (20m 19s) | 34 |
| PILOT-25 | 25 | 24 Blueberry, 1 Strawberry | 2 easy, 3 medium, 20 hard | 3,046.850s (50m 47s) | 85 |
| PILOT-100 | 36/100 capacity-limited | 35 Blueberry, 1 Strawberry | 2 easy, 3 medium, 31 hard | 4,387.464s (1h 13m 7s) | 122 |

The external-cost field uses input/output token counts and per-million-token
input/output rates. Rates remain unset until provider-authoritative
pricing is supplied; no pricing was fabricated or looked up.

## Recommendation and blockers

Recommend a first real pilot of **10**, after a model separately receives
explicit human qualification and a manifest-consuming proposal runner is
authorized. That bounds the planning review load to about 34 proposals while
still mixing easy, medium, hard, Blueberry, and the only ready Strawberry
record. It cannot provide caneberry or source-type diversity because the
trusted ready corpus does not contain it.

Do not run a pilot yet. The tested Qwen identity failed qualification, current
manifests are intentionally unbound, the collection extraction lane remains
transcript-oriented, no trusted transcript exists, written Evidence still
needs a paragraph locator contract, and the trusted corpus contains no retained
full article body.
