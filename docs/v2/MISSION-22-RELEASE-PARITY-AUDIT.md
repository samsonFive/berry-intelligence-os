# Mission 22 — Preserve correctness during release reconciliation

Read-only canonical refresh on October 2, 2026 remained at `916b8f09f9ce2a1847335d7990ea80ff921f1cec`, an ancestor of the approved redesign stack. The canonical expansion guide has no diff. This mission starts from repaired draft #294 head `27ed8cc`; its fresh required checks are still pending. Canonical and production were not changed.

## Open-PR overlap inspected

| Existing PR | Inspected head | Finding and disposition |
| --- | --- | --- |
| #255 | `3c585f23c39a4fd033bfc4fe944e89bb9626dea9` | The canonical Learner service, lesson records and TD-108/109 hygiene tests already match this branch. The redesign adds the visual presentation adapter; its Learner-test differences concern the approved company legacy view, verified image rights and new review-cadence copy. Retain the canonical curriculum and hygiene work. This is selected-file equivalence, not a claim that every historical PR file has been reconciled. |
| #270 | `4fbf3f596b08ed11e4b36a1e7e3fb3046029218d` | Introduces an older feed-first variety index/profile renderer and route selection. The approved native Varieties mission now has its own directory/profile, candidate workflow and retained specialist views. Do not replace that accepted layout with the older templates. Detailed feature parity remains to be checked before any recommendation to close or merge this PR. |
| #271 | `81439d87ef9d3fcfc9ab740f0936d5a173e76239` | Contains pending-index correctness, mobile async Reader work and transparent company news matching/diversity. The current pending index lacked its content digest. Carry that correctness fix forward separately; inspect the remaining Reader and company matching intent against the accepted implementation rather than importing the entire old interface. Nothing is auto-closed or merged. |

Other open PRs still require scoped overlap assessment. The new stack is not declared release-integrated merely because canonical is an ancestor or individual checks pass.

## Pending-review correction

The private pending index previously relied on modification/creation timestamps and file size. A changed file with retained metadata could reuse a stale source or review label. The signature now includes a SHA-256 content digest computed with bounded 64 KiB reads. Index version 6 rebuilds old version 5 metadata rather than retaining obsolete signatures. Unchanged entries still reuse their metadata projection across a restart. The sidecar contains metadata and the digest, not article/transcript bodies. Source files, private review history and canonical records are not edited by inventory reading.

The regression exercises a same-byte-size source change with deliberately preserved timestamp metadata, checks that the new source is reflected, confirms rich bodies remain absent from the projection and literal source bytes remain unchanged after reading, then verifies restart reuse. Existing attribution/filter/ranking/selected-body/review/public-safety behavior remains.

## Evidence and limits

Focused Pending tests: nine passed / one existing reportlab warning in 4.21 seconds. Combined Pending/triage/freshness/Morning Brief/attribution/private-public safety: **34 passed / one warning in 11.18 seconds**. No browser interface changed in this correction; the actual route/static restrictions remain covered by the combined tests. No provider, publication, statement, candidate or model qualification action was invoked.

A synthetic private benchmark used 500 source files totaling 36,241,780 bytes. Initial parsing/projection took 33.658 seconds; a new provider reused all 500 projections in 0.331 seconds, parsed zero records and omitted all rich bodies. This measures one local fixture run, not production latency or large-corpus capacity. Content hashing necessarily reads source bytes; it avoids rich-body hydration/parsing on a cache hit. Concurrent multi-process source/index writes still need the production persistence assessment; this change is not a transaction guarantee.

Required exact-head checks, full old-PR parity, public status/eligibility/source-quality review, remaining accepted source-assisted region/profile/metric workflows and the combined release/rollback packet remain open. Preserve runtime mounts, user edits/history and all human gates. No merge or deployment without final user approval.
Final exact-head CI: draft #295 head `58d6c21a1ad68a2970c03d6ebf20d8548fe7171f` passed Change scope, Repository integrity, Static public safety and Python tests, run `37088603587`: **3,637 passed / 11 skipped / two warnings in 347.12 seconds**. This verifies the cache/release-audit slice, not completion of the accepted requirements or canonical release integration.
