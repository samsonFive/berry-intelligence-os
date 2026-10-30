# Faster collection and company coverage lookups

The coverage request repeatedly prepares the same catalog identity strings for
public collection labels and the same source/company scopes for roster entries.
This separate performance child removes that repeated read-only work. It does
not change the approved #440 release image or its acceptance evidence.

The collection comparison now prepares a literal-name index once per call and
shares it across that request's baselines. It uses the existing resolver's name
fields, folding, minimum length and crop scope. Every ambiguous exact suggestion
remains; token overlap still cannot count as a catalog name match. Unclassified
Vaccinium records remain outside the blueberry comparison. Nothing is stored
or trusted by this projection, and the next call uses current user edits.

The portfolio source plan prepares each source's company scope once, retaining
source order and the existing per-name company scopes. The same saved source
can still contribute to multiple companies. Named occurrences, company filters,
website overrides, source gaps and human review states retain their meanings.

## Measured comparison

The private comparison executes the original committed implementations from
`0f6bd657e8d05d31bc462e3949d5b23ab9254a24` and the candidate alternately on
the public seed. No production records or provider calls are involved.

| Collection projection, alternating order | Seconds |
| --- | ---: |
| Original | 0.6180 |
| Candidate | 0.0387 |
| Candidate | 0.0176 |
| Original | 0.4339 |

All four serialized projections are identical: 1,668,899 bytes, SHA256
`54d829808343a4690a48ebb54bddc4fa1a39f3b137b006b49f4dbe3efd3b3605`.
These are Windows function timings, not production response times.

Twelve unprofiled authenticated TestClient requests on a disposable public-seed
copy also preserve the complete read model and exact HTML for each scope:

| Scope | Original seconds | Candidate seconds | HTML bytes |
| --- | --- | --- | ---: |
| Rutgers profile filter; all source sections | 8.0654 / 6.7784 | 5.1076 / 6.4973 | 1,755,702 |
| Blueberry and one company | 5.2451 / 4.3035 | 3.5037 / 3.8675 | 84,929 |
| Oregon and raspberry | 3.5525 / 14.0231 | 3.3639 / 4.3354 | 90,301 |

The noisy last scope is not evidence of a consistent route-level speedup.
The comparison uses a fictional account, normal startup and no profiler. It
does not establish live/mobile latency or remove the oversized hidden HTML.
Request copies, discovery/reconciliation and wider host contention remain open
under TD-122. Source details remain fully present in the current page.

## Regression boundaries

Tests compare the projection with the existing resolver over every saved public
collection entry, including editable aliases, codes and registration fields,
same-name crops, ambiguity and unresolved taxonomy. A second call after edits
must immediately lose or regain the corresponding suggestion. A growing roster
test bounds repeated company-scope work while retaining distinct name/company
counts and unchanged input records. Existing read-only/private coverage, source
accounting, photo identity, source-gap, candidate decision and static-public
checks remain required. The durable private receipt retains actual final test
and exact-head CI results; no deployment approval is inherited from #440.

There are no schema, entity, Evidence, Fact, relationship, registry, footprint,
Trade/Weather, source-capture, permission or review-decision changes. The guide
and all 31 accepted definitions/order remain unchanged. Wider catalog coverage
and human source/name/photo decisions are separate unfinished work.
