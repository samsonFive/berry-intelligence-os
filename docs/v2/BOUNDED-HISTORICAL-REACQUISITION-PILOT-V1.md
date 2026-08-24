# Bounded Historical Reacquisition Pilot V1

## Result

The production `REACQUISITION-PILOT-10` was executed once against exactly its
existing ten Evidence IDs. Seven sources produced identity-supported useful
rich content, one produced a rich but identity-ambiguous artifact, and two
failed for potentially solvable technical reasons. No trusted Evidence,
review decision, extraction state, Atomic Evidence, Fact, Relationship,
Signal, or Assessment changed.

The identity-supported rich reacquisition yield is **7/10 (70%)**. Raw rich
body staging was 8/10 (80%), but the ambiguous deListed result is deliberately
excluded from useful yield. Hard no-artifact outcomes were 2/10 (20%);
ambiguous identity was 1/10 (10%).

## Implementation and canonical

PR #131 added exact-manifest execution, deterministic unsafe/duplicate URL
preflight, precise failure categories, timestamp-insensitive artifact
idempotency, conflict refusal, and a body-free private audit. It merged as
`af323a2101365c7f702a46dd4624ed2908a0a9ab` after all four required checks
passed. A final pre-network review found that execution still did not hold the
shared collection lock. PR #133 added that lock and its regression test,
rebased after Atomic Review Workbench V2 merged, passed a fresh four-check CI
set, and merged as
`15fe3a0a0013806eba5f6b1558311dc4d81385b2`.

The pilot ran at `15fe3a0`. Manager Brief Pack V1 then merged and was deployed
concurrently. Final canonical and the verified running image are
`94888f8af0cc728e9f816ebe0efd9612d12c5a21`; host/container hashes match for
both `app/main.py` and `scripts/reacquire_sources.py`. The mission did not
modify the Atomic Review or manager-facing lanes.

Local validation was 37 focused tests plus record validation, an exact-manifest
CLI dry run, `git diff --check`, and a 1,547-page static/leakage pass. The local
full suite exceeded its constrained eight-minute window; authoritative PR CI
passed the full Python suite (PR #131 about three minutes; rebased PR #133
3m21s), Repository Integrity, Static Public Safety, and Change Scope.

## Manifest and preflight

- Private manifest:
  `/opt/berry-intelligence-os/demo-runtime/inbox/operations/source-reacquisition/REACQUISITION-PILOT-10.json`
- SHA-256:
  `df9f084ad18b65fb73d8b07e48755e9848d68f75906bc43e8741e1f133f55e5f`
- Entries: 10, unchanged from the planning run; no substitutions.
- Berry mix: 1 Blackberry, 1 Raspberry, 1 Strawberry, 7 Blueberry.
- Grouped source mix: 3 company newsroom, 3 trade press, 3 other, 1 academic.
- Every URL passed direct HTTP(S) deterministic preflight; there was no Google
  News wrapper, consent endpoint, search page, invalid URL, already-recovered
  artifact, affirmation, duplicate selected URL, or extraction-ready record.
- Shared lock was absent before the run, held across network/staging, and
  absent afterward. The timer remained enabled and active.

## Outcomes

| Evidence | Berry | Source class | Outcome | Rich artifact |
|---|---|---|---|---:|
| `ev-hortweek-driscolls-victoria-award` | Blackberry | trade press | `ROBOTS_OR_ACCESS_BLOCKED` (403) | no |
| `ev-media-c8cdb7133db1cae0bf66` | Raspberry | discovered media / newsroom | `CONTENT_CHANGED` | yes |
| `ev-fruitnet-driscolls-zara-best-strawberry` | Strawberry | trade press | `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING` | yes |
| `ev-ciopora-united-exports-pbr-2020` | Blueberry | industry association | `CONTENT_CHANGED` | yes |
| `ev-sekoya-story` | Blueberry | company website | `CONTENT_CHANGED` | yes |
| `ev-producereport-blugenix-2026` | Blueberry | trade press | `CONTENT_CHANGED` | yes |
| `ev-uaex-blueberry-trial-2024` | Blueberry | academic | `NETWORK_FAILURE` (read timeout) | no |
| `ev-delisted-costa` | Blueberry | market data | `AMBIGUOUS` | yes, not counted useful |
| `ev-costa-african-blue-2023` | Blueberry | company newsroom | `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING` | yes |
| `ev-costa-ownership-2024` | Blueberry | company newsroom | `LIKELY_SAME_ARTICLE_CHANGED_FORMATTING` | yes |

There were zero paywalls, removals/404/410s, redirect failures,
consent/interstitial pages, unsupported sources, or malformed/thin bodies.
No production source met the trusted-record-only `EXACT_STABLE_SOURCE`
classifier. Pink Hudson is a useful additional cross-check: its newly fetched
body hash exactly equals the previously audited historical acquisition body
hash (`f7f439...269ec`), even though the conservative runtime comparison labels
it `CONTENT_CHANGED` because the thin trusted record itself carries no historic
body hash and its current extracted title differs.

## Rich artifact quality

All final URLs equal their requested publisher URLs. Every artifact has stable
paragraph indexes `0..N-1`; all remain private and `pending`.

| Evidence | Paragraphs | Words | Chars | Body SHA-256 | Author | Date | Language |
|---|---:|---:|---:|---|---:|---:|---:|
| Pink Hudson | 5 | 266 | 1,794 | `f7f439978358abf697426b109c12c85b6ee0434e3765f306b32606e6746269ec` | yes | yes | no |
| Fruitnet Zara | 9 | 251 | 1,578 | `b44dac5b7739702029617d291cd6658931a920cac26d60b357b6084bcfd8e45a` | yes | yes | no |
| CIOPORA PBR | 8 | 672 | 4,268 | `ba05801b46991d780d2e1f00e1f4b82dfbc333943dea5a6dfe9ad3c1a49af0a4` | yes | yes | no |
| SEKOYA story | 33 | 339 | 2,301 | `2880fac82a2fc8cdc51fc0ffbef9debfbe032dc1d6ac1c709d6d41bf48033f8e` | no | yes | no |
| Produce Report BluGenix | 6 | 338 | 2,094 | `5e0c0899028f220f96953ca718dfaa4bbe5ad3efeaae06f622c4ca188c96d338` | yes | yes | no |
| deListed Costa | 26 | 438 | 2,777 | `b18b0a57b180fb1aa01512b68733d5e3b396e8762c0dd14919d81b3fd5726720` | no | yes | no |
| Costa African Blue | 11 | 412 | 2,575 | `69ea8dfef5b09562c30bbe623cc507cc2d3689880655b55cb43080e257270717` | no | yes | no |
| Costa ownership | 11 | 450 | 3,020 | `b12f76ed2aeb140817ab659d9307be6b024eb61b306a6615b46a114cf8118cac` | no | yes | no |

Identity support is stronger than title alone. Fruitnet and both Costa releases
match canonical URL, title, and date, with summary-token overlap 0.6957,
0.7250, and 0.7556. Pink Hudson matches URL/date, has overlap 1.0000, and the
historic acquisition body-hash cross-check above. CIOPORA, SEKOYA, and Produce
Report retain their exact URL with overlap 0.7458, 0.8261, and 0.7679 but have
current metadata differences, so remain `CONTENT_CHANGED`. deListed has exact
URL but only 0.3077 overlap and no title/date match, so remains ambiguous.

## Caneberry acceptance

The Raspberry candidate succeeded. `ev-media-c8cdb7133db1cae0bf66` links the
Planasa company identities and `variety-pink-hudson`; its Planasa Newsroom URL
produced five paragraphs, 266 words, 1,794 characters, author/date present,
and the body hash above. Identity basis is exact URL, exact date, 1.0000
summary-token overlap, plus equality with the previously audited historical
body hash. Review state is pending.

The Blackberry candidate did not succeed. `ev-hortweek-driscolls-victoria-award`
links Driscoll's and `variety-victoria`, but HortWeek returned 403 and was
classified `ROBOTS_OR_ACCESS_BLOCKED`. No body or Source Fidelity artifact was
created, and no browser automation was added.

## Yield and readiness

Grouped source yield:

| Source group | Attempted | Useful rich | Other |
|---|---:|---:|---|
| Company newsroom | 3 | 3 (100%) | none |
| Trade press | 3 | 2 (66.7%) | 1 robots-blocked |
| Other | 3 | 2 (66.7%) | 1 rich but ambiguous |
| Academic | 1 | 0 | 1 timeout |

Current extraction-ready corpus remains 36. The prior historic-recovery audit
ceiling remains 39 after three human affirmations. An in-memory, non-persisted
simulation of this pilot makes readiness 43 if the seven non-ambiguous
artifacts are affirmed, or 44 if the ambiguous deListed artifact is also
affirmed. Pink Hudson overlaps one of the three prior historic recoveries, so
the combined unique ceiling is 45 for prior + seven non-ambiguous pilot
artifacts, or 46 if all eight pilot artifacts are ultimately affirmed. Pending
artifacts are not counted as currently ready.

The observed midpoint for 35 realistic high-priority candidates is
`35 * 0.70 = 24.5` useful rich artifacts. Given only ten observations, the
source-type imbalance, one ambiguous record, and two technical failures, a
cautious planning range is **20-30**, not a claim about analyst affirmation and
not an extrapolation to all thin records.

## Idempotency, audit, and production safety

The successful eight IDs were rerun explicitly without the two failures. All
eight returned `ALREADY_STAGED / unchanged` before network acquisition, kept
the same artifact IDs/body hashes, remained pending, and created no duplicate
artifact or review item. Conflicting artifacts remain overwrite-protected.

Private audit records:

- pilot run:
  `demo-runtime/inbox/operations/source-reacquisition/runs/REACQUISITION-PILOT-10-20260824T001436320335Z.json`,
  SHA-256 `98ac8b25ba5c2d46e64945c6d0dc4c21966cb6b718f2d202d73577bdb3938dd3`;
- idempotency run:
  `demo-runtime/inbox/operations/source-reacquisition/runs/BOUNDED-RUN-20260824T002028496371Z.json`,
  SHA-256 `8804e1bc60c83a4b9533c9d6421af07eb143e74234df5754f97e817801461cf5`.

Their outcome key set contains only IDs, URLs, classifications, metrics,
hashes, identity comparison, artifact paths/IDs, and review/staging state. A
scan found no paragraph, full-text, source-text, or body-content field.

The final pre-deploy backup is
`/var/backups/berry-intelligence-os/berry-runtime-20260824T001109Z.tar.gz`,
SHA-256
`1447dbc8e9f5f2b541edeb46fc0dcdacebe1fc78f0185fde908b4bcf837dbb53`,
independently verified with 11,891 manifest files across `data` and `inbox`.
The earlier pre-mutation backup
`berry-runtime-20260823T235635Z.tar.gz` also remains verified (SHA-256
`d3d3fa0be2a88d9ad7aea64dce4f65cb34778b6f8206b9c702235dddd86bfc81`,
11,889 files).

Post-pilot:

- `data/` remains 2,656 files with aggregate SHA-256
  `7f3bea317ff8a9e5b9e8e5bba406e173395f4ee06abfe9aff0f145f823c57588`;
- inbox Evidence remains 1,556 files with aggregate SHA-256
  `a9d6a93c56be9c4c9b5ed413424baacd8d9f425d3a4d7a0d0d4e8e4b2bdc945a`;
- eight Source Fidelity artifacts exist, all pending; zero
  `source_fidelity_review` events exist;
- audit assertions report identical selected trusted-Evidence hashes before
  and after, zero new extraction-ready IDs, and zero analyst decisions;
- extraction environment flags remain unset; qualification markers remain
  zero; the collection lock is absent after execution;
- local/public `/healthz` are 200, Docker is healthy, the timer is
  enabled/active, unauthenticated `/source-fidelity` redirects, and
  `collection_status.py` completes in 3.55 seconds.

A static build against the live runtime stopped on existing inbox titles/IDs
that collide with already-published pages. It did not deploy output. A separate
pilot-specific scan of the generated tree found zero matches for all eight
private artifact IDs, a representative private body hash, or any Source
Fidelity path. Canonical PR Static Public Safety passed. The broader
production-runtime self-check ambiguity is tracked separately as TD-098.

## Recommendation

**RUN PILOT-25**, but only after analysts review the eight current items so the
manual identity/fidelity cost is measured as well as fetch yield. Company
newsrooms were 3/3 and the Raspberry source succeeded; the Blackberry 403 and
academic timeout show why browser automation should remain out of scope.
PILOT-25 must remain bounded and must not be started by this mission.

Selective reacquisition can materially improve the tiny ready corpus (seven
identity-supported candidates would be a 19.4% increase over 36), so the 35
high-priority records are worth pursuing. It is not a credible path for the
whole thin backlog. Most acquisition effort should remain on future rich
capture, with historical work limited to explainably high-value sources.
