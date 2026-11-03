# Cold catalog loading and mission closeout

Company Varieties and Candidates still take roughly 4.5–5 seconds on the tested
server copy. The latest final-code experiments preserve the information but do not produce
a consistent page-level improvement. They are rejected, not release candidates.
TD-122 remains open.

## What is live and what is ready

| Release | State | What it delivers |
| --- | --- | --- |
| [#486](https://github.com/samsonFive/berry-intelligence-os/pull/486) | Earlier deployed `b8b8b008`; approved head `8c330d8f`, retained in live #488 | Company article-name handoffs, company hierarchy, visual presentation of the completed Learn request, honest Reader publisher destinations and source/declaration/crop preparation. All four final checks pass: 6,267 tests, desktop/phone review and fresh preservation. |
| [#477](https://github.com/samsonFive/berry-intelligence-os/pull/477) | Earlier deployed release `1ad5084f`, retained in #486 | Company tab preparation and compact profile header. Its approval is complete. |
| [#487](https://github.com/samsonFive/berry-intelligence-os/pull/487) | Approved `30861d83`; earlier deployed `892f84db`, retained in live #488 | Fixes News completion after optional tagging failure. All four final checks /6,271 tests, desktop/phone review and fresh preservation pass. Schedule and exact proxy restored; no data or provider changes. |
| [#488](https://github.com/samsonFive/berry-intelligence-os/pull/488) | Approved `22dcb869`; merged and independently verified live at `32eefbd5` | Five scoped PSG sections, 44 occurrences /34 printed names or codes, 18 extra review keys and 34 held photo references. All four final checks /6,277 tests, desktop/phone and fresh release-time preservation pass. Five accounts, 65 profiles, 10,539 existing JSON records, four databases and 1,115 research files remain; one source file added. No canonical identities or runtime code changes. |

Superseded #480/#482/#483/#484 are closed without merging. Their exact commits,
branches and evidence are retained in #486; their earlier approval requests
are superseded by the fulfilled combined approval. They are not remaining
release blockers.

The final #486 rehearsal and live checks preserve five accounts including
Chris.H, 65 profiles, 10,539 existing JSON records, four databases and 1,115
research files. No startup data additions, provider requests or human review
decisions were created. The release-time backup and rollback remain. The first
deployment stopped before an app switch because a failed optional tag job left
stale `running` status. Exact failed-job/status hashes, absence of workers and a
lease, an inactive service and a temporarily paused timer established an exited
job without clearing its state. The proxy and schedule were restored.

Unused Docker build cache older than 24 hours was removed to restore rehearsal
headroom; all 154 release images, backups and data volumes were retained.
Resource limits were not lowered.

The admitted necessary crop-prefix preparation differs from the rejected
experiments below. It retains the global corpus and original Unicode matcher.
Final-code medians improved about 5.09% and 4.20% on the tested Company Varieties
and Candidates routes, with all complete typed models/HTML unchanged. Prototype
12%/6% figures are not final-code claims. These modest gains do not close TD-122.

## Experiments rejected in this continuation

| Approach | Measured result | Why it is excluded |
| --- | --- | --- |
| Analyze only articles linked to the selected company | Hortifrut improved from 4.88 / 4.66 seconds to 2.00 / 2.36. The wider matrix found 10 different complete company models among 336 checks, affecting five companies. | Candidate link fragments changed. The global merge also combines spelling, codes and provenance across sources, so company-only analysis is not equivalent. The navigation workaround was also archived rather than shipped. |
| Prepare existing caches before the first page | Prepared page requests took 1.2–1.6 seconds, after 4.4–4.6 seconds of preparation. Complete cold work rose to 5.6–6.2 seconds, versus 4.6–5.0 without preparation. | It moves work earlier and increases total cold work. No startup or background warmup is added. |
| Whole-text regex hint before sentence-level consent checks | Company was slightly faster; Candidates was slower. All checked output remained identical. | Mixed end-to-end results do not justify a new runtime path. |
| Substring version of the same hint | Both cold routes were essentially flat, around 4.7–4.8 seconds. Local function-only results had looked better. | A faster function diagnostic did not translate into faster pages. |
| Delay the reporting-word check until a consent phrase matches | Company medians were 5.01 → 5.05 seconds; Candidates 4.80 → 4.70, with overlapping samples. | No consistent page-level gain. The original predicate remains. |
| ASCII-only crop matcher | Company was slightly faster; Candidates was slower. | Mixed page-level results; not retained. The admitted check preserves the original matcher instead. |

Each timing comparison uses two fresh processes per variant per route in ABBA
order, one CPU, 1 GiB memory, no swap, no network or exposed ports and a bounded
offline container. The full unfiltered discovery model, typed response context
and rendered HTML match within the preparation and text-check comparisons.
Original snapshot bytes and the healthy live release remain unchanged. The
company-scoping experiment has a different contract and explicitly fails its
all-company model comparison; its successful diagnostic exit is not acceptance.

The regex hint passed 114 focused tests and 295 affected tests; the changed
substring hint passed the 114 focused tests. Reporting-order changes passed 94
focused tests. Passing these controls does not make an ineffective optimization
worth shipping. All experimental runtime code and tests are archived privately
and reverted. No new classifier, cache, source scope or identity rule is retained.

Private evidence remains in the November 3 `company-body-scope-*`,
`catalog-preparation-warmup-20261103` and `source-ui-hint-preparation-20261103`
inbox artifacts. Their exact result hashes and decisions are recorded in the
durable continuation ledger. They contain no new production edits or approvals.

## Current-base diagnostic

A new bounded profile on the validated #488 copy (retaining live #487) leaves
all snapshot bytes and the healthy live site unchanged. Article preparation
and repeated presentation serialization remain significant costs. The roughly
8.3-second profiler runs include instrumentation overhead and are not latency
benchmarks. No company/source scope is narrowed.

The proposed guaranteed-oversize Reader-key shortcut is rejected: none of the
3,173 key calls in either selected route meets its lower-bound condition. The
largest raw string contribution is 53,105 characters. This measures whether
that proposed shortcut would trigger, not every JSON-escaped key length. No
runtime code or tests are retained for that ineffective shortcut. The separate Reader-key experiment below also remains excluded from release.

## Reader key encoding: final-code gains were mixed

The eight-process prototype preserved all complete typed article bundles,
unfiltered universes, response contexts and HTML and initially suggested gains.
Its Company/Candidates cold medians were 5.040 → 4.581 and 4.985 → 4.396 seconds.
The isolated implementation passed 89 focused and 179 integration checks with
zero external connection attempts. Its subsequent exact-module comparison also
preserved all eight complete outputs, source-copy bytes and healthy live state.

Final-code Company cold loading was essentially flat (4.774 → 4.765 seconds),
and Company→Candidates was slightly worse (6.217 → 6.310). Candidates cold
improved modestly (4.512 → 4.355), as did Candidates→Company (6.108 → 5.819).
These mixed results do not justify a new runtime path. PR #489 is closed without
merging; its branch, tests and exact evidence are retained. No code from it is
live. The stronger prototype figures must not be used as final-code or deployed
claims. TD-122 remains open. No repeated benchmark was used to select a more
favorable result.

The final implementation module SHA-256 is
`54c1d6d4bdaf0042c1fb11eeaf31ad099f5593fafa8462f55db23929ac381e01`;
its private final result SHA-256 is
`d6bad81b8dcd5afcfedbdb251eb3285a173135fe36c4f7486373f14713a7b12a`.
These identify the rejected artifact, not an approved release.

## Work still needed to finish this mission

- **Cold-page engineering:** profile the complete current request and next-click
  workflow. Require consistent end-to-end improvement, complete output/current-edit
  parity, browser review, required checks and fresh preservation before release.
  Do not replace this with a favorable microbenchmark or a narrower catalog.
- **News reliability:** #487 is deployed and its approval fulfilled. Its optional
  tagging failure no longer strands useful capture. Provider quota remains an
  operational dependency; no paid retry or purchase is authorized. No release
  permission for #487 is still pending.
- **Catalog and source depth:** retain the 77-subject plan, unreadable sections
  and source follow-ups. Complete the independent 32-source expected-name audit
  with human-supplied answers. Candidate occurrences are not approved varieties,
  company roles, complete inventories or proof of worldwide comprehensiveness.
- **Human review:** source/name/code/role/rights decisions, unclear supplied photo
  cells and photo permissions stay in their queues. The two UK Map discrepancies
  remain held until selected or resolved; no trusted figure is picked automatically.
- **Learn quality:** the one authorized real-provider request completed and remains
  an editable AI draft. Its reported cost was USD0.13679. More paid requests are
  not authorized. The delivered visual lessons do not establish that every source,
  external video or image permission has been verified.

The visual Help explainer, shared collaborative workspaces, private Personal
Digest/layout settings, original 31 requirement definitions and protected schemas
remain. These remaining items stay in this mission; this record neither hands
them off nor marks the ongoing goal complete.
