# Private catalog calculations across workers — implementation in progress

The current live release remains approved #490 at `3ffe5bad`. This branch adds
an opt-in private calculation store and an explicit preparation command. It is
not a release candidate: exact implementation timings, native review and fresh
preservation remain. New commits need their own checks. TD-122 is open. The separate
ready documentation #491 is retained here without approving either merge.

## Implemented boundary

Only the existing `build_discovered_candidates` and `reconcile_portfolios`
calculations can use artifacts. Every current source, capture/recovery choice,
canonical record and saved candidate still reaches their complete input keys.
The global corpus is not narrowed to a selected company. HTTP authentication,
personal layouts and Digest, rendered responses, catalog promotion and human
source/name/role/rights/photo/Map decisions are not cached as separate decisions.

The feature defaults off. A private authoring request with a bound request
corpus may opt in using `BIOS_PRIVATE_READ_MODELS=true`. Static/no-request and
readonly runtimes retain their existing paths. Unsupported platforms and input
graphs fall back to the original calculation. Readers never create, repair or
expire files, even when an artifact is absent, invalid or stale.

The native input key preserves values, types and order while ignoring incidental
sharing between equal immutable source values from different workers. Cycles
and unsupported objects use the old path. The current interpreter's optional
memo-free key-encoding capability is guarded by that fallback; no unqualified
decoder or third-party serialization dependency is introduced. Result snapshots
retain their normal sharing and caller-owned copy semantics.

The key binds the function's semantic code and defaults, the immutable app/schema
image, Python version/optimization flags, UTC/local freshness days and runtime
context. Local-midnight invalidation prevents stale freshness labels while the
UTC date stays unchanged. A test exposed that `marshal`
reference flags can vary after ordinary retained results; the implementation
instead serializes immutable semantic code fields, including nested code and
sorted frozenset constants. Worker hash-seed and reference-count checks cover it.

## Integrity and filesystem ownership

Signing material is derived with purpose separation from the configured private
session secret. No public fixture key ships and no new credential is exposed.
The cache leaf is private to its owner; public/generated/static, canonical data
and schema roots are refused by configuration. An optional
`BIOS_PRIVATE_MODEL_ROOT` selects an existing private parent for isolated review;
otherwise the owned leaf is below the private inbox.

The store authenticates the complete identity and bytes before the existing
class-denying decoder runs. Reader operations use descriptor-relative paths,
no-follow ancestor/file checks, private modes, regular-file checks and bounded
reads. A writer uses a nonblocking lock and atomic publication; it may expire
only authenticated artifacts from this exact owned leaf. Unknown files are
retained and count against the budget. The limits are 16 MB per payload,
32 entries and 128 MB total. Failure always permits current calculation instead
of serving a stale result or changing an operator record.

## Explicit preparation

```powershell
python scripts/prepare_private_read_models.py --prepare
```

The command runs only in a configured POSIX authoring runtime with private
signing material. It reuses the same current selector and model inputs. Network
connection and resolver APIs are blocked for the entire command, including app
imports: no collection, paid provider request or retry can occur. Its receipt
contains counts and total elapsed time, including import/preparation cost.
Only derived artifacts can be created or expired; no source, review or canonical
record is authored. No startup warmup or recurring job is installed.

The actual separate-command cost must be included in the next comparison.
The earlier prototype generated artifacts during calculations it already had
to perform; those creation figures do not prove that a separate preparer plus
readers will reduce total work. If the implementation merely moves or duplicates
cost, it will be rejected or revised before release. Prepared-worker speed alone
cannot close TD-122.

## Dates and saved edits

Generated `discovered_at` is retained from the actual daily model materialization,
as the existing daily memory memo already retains it within a process. A reused
model is not relabeled as newly calculated. Next-day reads miss. Source
publication/event/capture dates and saved candidate timestamps are untouched;
`merge_visible_candidates` continues to prefer operator-owned inbox rows.
Generated-clock control in a benchmark is not evidence of new source chronology.

## Evidence so far

Pushed `10a80034` passes all four checks /6,363 tests, including local-day and
real-catalog refinements. Its focused set has 39 tests: 22 pass on Windows and
17 POSIX cases skip; Linux CI covers the native cases. A further process-boundary
test runs the real offline command and a fresh private reader against committed
public seed data, checking two filesystem artifact hits, complete typed output,
unchanged sources/schemas and zero reader writes. Its own current-head results
must be checked; older totals are not evidence for a changed head.

Three new tests execute the actual corpus calculation through the integration,
not an imitation. They retain saved decisions/dates/notes/aliases, unreviewed
source status, caller ownership and current body/URL/review/deletion results
without reader writes or automatic catalog/statement promotion.

A separate public-seed comparison recreates both model memos between every
variant, rather than accidentally measuring warm memory. All four complete typed
universes match: 64 catalog rows, 1,333 visible candidate keys and 539 portfolio
sections. A caller mutation does not change the next reader's result. Both fresh
readers use two artifact hits, zero calculations and zero writes; 2,942 source
and schema JSON files remain unchanged. That comparison uses an in-memory store
adapter. It does not prove filesystem performance, account preservation or live
coverage. The public seed's 64 rows are distinct from the live 65 profile files.

- All 35 exact Linux unit contracts pass, with no skips: filesystem integrity,
  private scope, complete input/day/code/context invalidation, ownership,
  unsupported fallback, class/trailing-data rejection, concurrent publication,
  code identity across worker hash seeds, explicit writer and network refusal.
- The affected Windows suite passes 621 tests, with 17 POSIX skips and zero
  attempted external connections. Those skips do not establish Linux behavior;
  the separate exact-module Linux run above does.
- The earlier authenticated prototype preserves all 48 complete responses in
  creation/reuse tests. Its separate unseen-body/title control preserves 24
  further responses plus 12 pinned seed responses, actually recalculating changed
  inputs with zero reader writes. These are prototype results, not acceptance
  of this new key format, command cost or implementation.

The original 31 requirement definitions/order, governing guide and protected
schemas remain unchanged. Independent human recall, catalog/source/profile
depth, current rights, attributed photos, held Map decisions and wider Learn
quality remain in this mission. No new merge/deploy or paid-provider approval
is inferred from the fulfilled #490 release.
