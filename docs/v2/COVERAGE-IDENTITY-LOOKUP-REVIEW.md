# Coverage identity lookup review

The cold Coverage request repeats thousands of identity lookups against the
same catalog. Profiling the actual synchronous handler found 7,184 calls and
448,768 catalog rows considered. This narrowly scoped technical-debt follow-up
prepares name, registration and token indexes within one read-only Coverage
request, then sends relevant rows in their original order to the existing
matcher. The matcher still makes every decision. No result is cached.

This is a child of platform/startup #458 (`1ef1480a`), based on live #443
(`f76080d0`). Frozen #458, Reader #459, catalog/Map #449 and source #457 keep
their own review scopes. The existing unanswered release questions are not
repeated, superseded or treated as approval of this work.

## Boundaries and freshness

The documented blocker is cold Coverage latency, including a 10.24-second
first request on the isolated VPS copy. This justifies the otherwise protected
Variety backend change only as optional read-model preparation. Matching rules,
identity states, schemas, CPVO, footprints, Trade and Weather remain unchanged.
Only the Coverage GET handler opts in; candidate authoring and other handlers
retain the original path.

The index contains owned record copies and retains references to its inputs
for one request. Every reuse compares the complete current records with that
copy, so nested edits or reordering rebuild it. Fresh requests start empty;
threads use separate contexts. Tiny catalogs, unsupported inputs and excess
catalogs use the original matcher. Numeric identity fields also use that path:
Python considers `True`, `1` and `1.0` equal, but their identity strings differ.
Plain text/null matching inputs avoid that shortcut. This is preparation for
JSON-backed read models, not a new general-purpose identity cache.

Crop eligibility is applied before deciding whether exact matches exist. If
there is no eligible exact match, token sets supply a conservative superset of
every possible contiguous overlap. Duplicate rows, IDs, order, attribute roles,
registration precedence and raw display names are retained. Exact matches
remain possible aliases requiring human review; overlaps remain unknown.
No automated same-variety confirmation, publication promotion, source/name/role
acceptance, or rights/photo permission decision is added.

## Measurements and acceptance

The first runtime implementation rebuilt a material-field fingerprint for
every lookup. Its complete typed models and HTML matched, but the cold request
regressed from 6.58 to 8.26 seconds. That version was rejected. Complete-record
equality checks then reduced the first request to 4.15 seconds in the initial
local pair; repeat requests remained approximately two seconds. These are
fresh-process offline public-fixture measurements, not production percentiles
or a physical-phone speed claim. Reverse-order confirmation of the final runtime measured 8.53 to 4.03 seconds
for the cold request. Its three warm comparisons were 1.96 to 1.91, 1.88 to
1.94 and 2.83 to 2.13 seconds: overlapping/noisy samples, not a general warm
improvement claim. All four complete models match recursively in both value
and type (294,508 nodes for each Rutgers request, 159,171 for each Hortifrut
request); all HTML bytes match. All 2,974 public data files are unchanged and
there are zero outbound connections. No field is masked, truncated or omitted.

Final affected checks passed 348 tests in 39.61 seconds, including 255 differential cases
covering candidate names, registrations, crop scopes and input order, plus
same-request edits, next-request freshness, duplicate rows, output isolation,
thread separation and Personal Digest. Numeric-input fallback and account-private Digest checks pass. Record
validation passes. AST comparison confirms the matcher decision body remains
identical and its helpers are identical after expanding hoisted literal lists.
Native desktop/412px review confirms company/berry filters, source disclosures,
review labels and scoped candidate handoffs, with no horizontal page overflow.
The fixture's first login still opens Help. Viewport sizing is restored and
the successful review tab closed. These are emulated phone checks, not a
physical-device/network test. One existing ReportLab deprecation warning remains. All original 31 requirement
definitions/order and the governing guide remain unchanged.

TD-122 stays open for repeated graph/copy work, broad Coverage, specialist cold
loads and real network/device latency. Source/body/media quality, independent
catalog recall and wider Learn/Map content remain separate unfinished work.
This draft does not approve a merge or deployment. Current-head CI, native
desktop/phone review, preservation and a scoped release decision remain required.
