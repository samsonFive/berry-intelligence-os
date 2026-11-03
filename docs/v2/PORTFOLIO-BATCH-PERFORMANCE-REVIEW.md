# Portfolio reconciliation: prepare once for a single batch

The cold company Varieties and Candidates paths repeatedly compare a complete
owned catalog to the current variety records. Those checks correctly protect
in-place edits, but reconciliation repeats them for thousands of names while
using the same read-only inputs.

This child of tested draft #480 prepares one privately owned catalog for a
single synchronous reconciliation call. The existing identity matcher still
makes every decision. The prepared object stays inside that call; the next call
rebuilds it from current inputs. Ordinary request-scoped matching retains its
complete per-call freshness checks. Unsupported or opaque inputs use the
original sequential matcher, without consuming iterators during admission.

Two runtime files change: `identity_read_model.py` and
`variety_portfolio_coverage.py`. The latter batches only the existing four-field
source-observation queries in their original order. Candidate construction,
human rejection/distinct/confirmed decisions, identity conflicts, source
accounting, warnings, labels and all output fields retain their existing paths.
No result cache, schema, source, canonical record or review decision is added.

## Evidence and limits

The offline public fixture contains 537 source sections, 2,029 literal name
occurrences and 64 variety entities. Complete reconciliation results and every
input field match the old path across three alternating pairs. Component times
are 1.36/1.66/2.15 seconds before and 0.93/0.89/1.45 seconds after. These are local
component samples, not live page latency or a catalog-coverage improvement.

Both controls use an identical generated-candidate clock. The first comparison
correctly refused differing `discovered_at` timestamps; no output field was
removed to obtain equality. All 2,997 public fixture files remain byte-identical,
with external connections forbidden and zero provider requests.

The affected regression run passes 532 checks. The eight explicit source-filter,
source-only/full-result and saved-decision controls also pass. The matcher tests
compare complete original results across crop filters, registration precedence,
ambiguous aliases, duplicate/order variants, nested edits, returned-result
mutation, opaque values and iterator inputs. These counts overlap and are not
an aggregate test total.

Complete fresh-process company/Candidates route comparisons pass across four
processes per route. They retain the full template context and exact HTML,
excluding only the HTTP
Request object. The existing `berry_label` template helper is accounted for by
its exact code hash and outputs for all crop labels and an unknown label; other
unaccounted objects still fail the comparison. The initial serializer refusal
and all successful company controls are retained. Operating-system disk cache
is uncontrolled, so these are fresh Python processes, not measured cold disks.

| Route | Original samples (seconds) | Batch samples (seconds) |
| --- | --- | --- |
| Splendor Varieties | 5.25, 4.43 | 3.19, 4.38 |
| Company-scoped Candidates | 4.43, 9.98 | 4.78, 6.08 |

The component saving is visible in the company samples, while Candidates ranges
overlap substantially. Local I/O/background-load variability prevents a reliable
overall speedup claim. A bounded production-copy measurement is still required.
All eight responses preserve every HTML byte and all template model fields;
367,861/411,951 bytes of full context are compared per route. No data record is
excluded or normalized to conceal a difference.

## Release boundary

This performance child is separate from pending #480 at `53dd52e3`. #480 already
passes all four checks (6,165 tests), native desktop/phone review and a fresh
isolated live-data preservation check; its own merge/deployment approval remains
pending. The #477 approval has been completed by its verified live release.
Neither approval includes this new performance change.

Native desktop and 412px company/Candidates checks pass: alphabet filtering,
the exact publisher link, historical/source caveats, untrusted/unsaved state and
human decision controls remain accessible without horizontal overflow. No
decision is submitted. Returning to the company retains company scope; its
local alphabet selection resets to All, an existing behavior, not a claimed
filter-persistence improvement. Normal viewport sizing is restored.

Final-head CI and fresh production-copy preservation remain for this child.
It is not merged or deployed. TD-122 remains open for broader cold
loads. Independent expected-name/source/identity/role/rights/photo and Map figure
decisions stay in their existing human queues. No extra paid Learn call is made.
The guide and all original 31 requirement definitions/order remain unchanged.
