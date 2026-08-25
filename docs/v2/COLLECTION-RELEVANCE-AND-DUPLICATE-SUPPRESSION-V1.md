# Collection Relevance + Duplicate Suppression V1

## Outcome

The recurring collector now rejects stable known web articles before expensive orchestration while retaining conservative update checks and every existing human trust boundary. It does not change Sources, queries, cadence, relevance policy, review decisions, trusted records, extraction qualification, or automatic throttling.

Implementation landed through PRs #169-#172. The production implementation canonical is `d91d9f6a9b8f68c6ebadfac1a3f8d37f4dcfb581`.

## Duplicate taxonomy and boundary

- Exact stable identity: same platform identity or normalized canonical/final URL. Rejected at discovery or the collection-runner boundary.
- Tracking/GUID variants: only allowlisted tracking parameters are removed; semantic parameters remain identity-bearing. Redirect-resolved identity participates when available.
- Search-wrapper versus direct publisher: deterministic equivalent matches prefer direct publisher lineage.
- Same-publisher article identity: exact publisher/title/date logic remains conservative.
- Cross-publisher syndication: not collapsed without deterministic identity. Review remains the safe boundary.
- Updated article: a due or semantically changed known item may be fetched and content-hash compared, but no trusted or pending record is overwritten.
- Retry/intervention state: remains eligible until resolved; structural wrapper blocks stop retry churn without becoming a false success.

Per-Source recent discovery memory is derived, bounded to 250 identities, and rebuildable from retained state. Discovery fingerprints exclude observation-only timestamps and carry an explicit version so deployment does not create a false refresh sweep.

## Relevance and recall audit

No relevance rule changed. Existing deterministic berry, Company, and Variety alias behavior remains intact, including Raspberry and Blackberry. Mexico, Morocco, and UK warning queries remain unchanged at their existing daily cadence. Google News wrapper handling is protected structurally, and rich-body acquisition for genuinely new items is unchanged.

## Validation

- Focused acquisition/relevance/freshness matrix: 171 passed.
- Final focused correction matrix: 103 passed.
- Full suite: 1,709 passed (572 warnings).
- Record validation: passed.
- Static build: 1,618 pages.
- Private-runtime leakage check: passed.
- `git diff --check`: clean.
- Required GitHub checks passed on PRs #169, #170, #171, and #172.

## Production proof

The final pre-deploy runtime backup is `/var/backups/berry-intelligence-os/berry-runtime-20260825T080830Z.tar.gz`, independently verified at 12,961 entries with SHA-256 `e7ec5dffb017cce34b4f8408f3bb326da3a3566509f5de4993949be9a74f9987`.

The first deployed probe correctly exposed migration-state defects instead of hiding them: volatile transcript observation time initially appeared as content change, and older retry state still crossed the late duplicate boundary. PRs #170-#172 made the fingerprint migration explicit and semantic. The correction reconciliation then classified all 229 representative items unchanged and safely drained 184 retained retry candidates without creating a draft.

The immediate stable repeat is the acceptance window:

| Source | Found | Unchanged | Processed | Body attempts | Drafts | Retry/operator |
|---|---:|---:|---:|---:|---:|---:|
| Mexico berry search | 81 | 81 | 0 | 0 | 0 | 0 / 0 |
| Morocco berry search | 48 | 48 | 0 | 0 | 0 | 0 / 0 |
| UK berry growers search | 100 | 100 | 0 | 0 | 0 | 0 / 0 |
| **Total** | **229** | **229** | **0** | **0** | **0** | **0 / 0** |

This is a 100% reduction in downstream item processing for this stable representative window. Historical pre-mission article-body attempt counts were not instrumented, so no fabricated historical fetch-savings number is claimed; the new contract directly records zero body attempts for the 229-item stable repeat.

Runtime integrity after proof:

- trusted data files: 2,657; trusted Evidence tree SHA-256 remains `7a6cc5fae89fa2034f65e2a784386dce3f3ce05673026359bdbd673078c54585`;
- private Evidence drafts: 1,673, exactly three above baseline from the first diagnostic deployment; later correction/repeat runs created zero and no pending decision was mutated;
- review events: 11 before and after; backup/current tree hash is `f989615948c2434f96c45cbec0bec0e0a5f106f338e18330b1da69f5d6f463f6`;
- `/healthz`, `/login`, and authenticated `/work-queue`: HTTP 200;
- app container: healthy; `bios-collection.timer`: enabled/active; service idle between runs;
- disk: 108 GB available (7% used);
- extraction: disabled, unconfigured, unqualified; automatic throttling: false;
- operator status remains fast; freshness computation is 0.968 seconds.

Freshness remains honestly `DEGRADED` for the previously known Growing Produce access block: 70 scheduled, 45 current, 24 due within grace, zero overdue/retrying/failing, one blocked. Scheduled coverage remains Blueberry 59, Strawberry 41, Raspberry 39, and Blackberry 39. The bounded proof advanced only the three representative Sources' attempt clocks; it did not change cadence, queries, or feed-window policy.

## Remaining limitation

Cross-publisher syndication without deterministic shared identity remains intentionally review-visible rather than fuzzily collapsed. Historical body-fetch cost was not recorded before this instrumentation, so future savings trends begin with these new per-run counters. The runtime still exposes 70 of 73 canonical discoverable Sources under TD-076's protected promotion behavior.
