# Reader input key experiment — excluded from release

The implemented change preserves complete outputs but does not consistently
improve the tested workflow. It is excluded from release and retained only on
the experimental branch. No runtime change from this experiment is deployed.

Company Varieties and Candidates repeatedly prepare the same stored article
content. Their private Reader memo currently serializes every selected input
as sorted JSON on each lookup. This change uses a compact digest of a guarded,
locally encoded builtin graph, retaining every selected field and nested value.
The global article corpus, Reader classification and human decisions are intact.

Only `app/services/presentation_memo.py` changes at runtime. Keys remain private
to the process. This does not cache authenticated responses, write source data,
fetch articles, make provider calls or persist encoded objects. Key generation
does not unpickle anything and rejects custom reducers. Existing result-copy
ownership, item/total memory budgets and eviction remain unchanged.

Unsupported objects and oversized encodings use the original JSON path, with
its existing 128,000-character eligibility limit. This retains eligibility for
large Unicode inputs whose encoded byte length exceeds that limit. Builtin
container types remain distinguishable: a tuple is not silently conflated with
a list. Input edits invalidate the result even when a record ID is unchanged.
Dictionary insertion order can create an extra cache miss; it cannot hide an
input edit. Cyclic graphs use the original uncached fallback.

## Evidence so far

The process-only prototype compared eight fresh processes on a disposable
production-data copy: two samples per variant for both Company-first and
Candidates-first visits, including the next click. Complete typed article
bundles, the full unfiltered universe, complete typed response contexts and
rendered HTML match in every comparison. Snapshot bytes and the healthy live
site remain unchanged. Only derived candidate-creation timestamps were fixed
identically; source dates and human state were retained.

| Measured workflow | Baseline median | Prototype median |
| --- | ---: | ---: |
| Cold Company Varieties | 5.040 s | 4.581 s |
| Cold Candidates | 4.985 s | 4.396 s |
| Company then Candidates, total | 6.493 s | 5.974 s |
| Candidates then Company, total | 6.629 s | 5.869 s |

These are prototype measurements on the tested copy, not deployed performance
claims. The experiment used one
CPU, 1 GiB memory, no swap, no network or exposed ports and a 240-second bound.
Two samples per variant are limited evidence; cold loading still takes several
seconds. TD-122 remains open.

The subsequent exact-module comparison also preserves every complete typed
article bundle, unfiltered universe, typed context and HTML across eight fresh
processes. It verifies module SHA-256
`54c1d6d4bdaf0042c1fb11eeaf31ad099f5593fafa8462f55db23929ac381e01`.
Company cold loading is essentially flat (4.774 → 4.765 seconds) and its
two-page workflow is slightly worse (6.217 → 6.310). Candidates cold loading
improves modestly (4.512 → 4.355), as does its workflow (6.108 → 5.819).
These mixed results do not justify a release. The stronger prototype figures
must not be used as final-code or live claims. No repeated benchmark was used
to select a more favorable outcome.

The implementation passes 89 focused checks, including all existing snapshot
copy-isolation and Reader coverage tests. New cases check all seven selected
fields, nested edits, caller mutations, tuple/list Reader behavior, denied custom
reducers, large Unicode/ASCII inputs and cycles. Zero external socket attempts
were observed. Another 179 integration checks pass for source fidelity, Reader
classification and capture bounds, company article handoffs, publisher links
and patent document reading, also with zero attempted external connections.

Private evidence and exact artifact hashes remain in the durable continuation
ledger and ignored November 3 Reader-key inbox. The earlier guaranteed-oversize
shortcut had zero qualifying calls and was rejected. Its result is separate
from this successful key-encoding prototype. Neither experiment changes source
scope, identity merging, protected schemas, photo reuse or review gates.
