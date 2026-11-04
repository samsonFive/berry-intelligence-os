# Identity lookup shortlist performance

The cold Company and variety-candidate pages repeatedly checked crop compatibility
against the entire catalog before looking up a name. This follow-up first finds
the existing name, registration or token matches, then applies the same crop rule
to that smaller set. The original identity matcher still makes every decision.

An exact name from the wrong crop must not suppress a compatible token match.
That fallback, original row order, duplicate rows, registration precedence and
current in-place edits remain covered by the existing unindexed-matcher tests.
There is no new cache, stored index, source filtering or identity approval.

## Bounded private-data diagnostic

The comparison uses the reviewed #506 implementation at `ea79b610` as its
baseline, not the older live #505. It runs both variants in eight fresh processes
on one existing isolated production-data copy, alternating variant order across
two replicates of each route order. The filesystem is not guaranteed cold.
Handler timings exclude module imports and output-comparison work.

| Workflow | Baseline | Shortlist | Change |
| --- | ---: | ---: | ---: |
| Company first, three-page total | 11.36 s | 10.55 s | 7.2% faster |
| First Company visit | 5.95 s | 5.39 s | 0.55 s faster |
| Candidates first, three-page total | 10.76 s | 10.09 s | 6.3% faster |
| First Candidates visit | 5.52 s | 5.05 s | 0.48 s faster |

All 24 complete typed article bundles, candidate universes, page contexts and
HTML responses match. The comparison includes a new unreviewed article held
only in memory, proving that its candidate appears on the next rebuild.
All 25,633 input files remain byte-identical; no provider request or live-data
write occurs. These limited handler measurements are not universal live latency
claims or a new release-time preservation check.

Samples vary: one Candidates-first replicate regresses from 10.63 to 10.82
seconds in total, although its first visit improves. Two further counterbalanced
replicates per route order are being checked before accepting the performance
claim. The median improvements alone do not establish consistent live speed.

Evidence is retained under the #506 worktree's ignored
`inbox/cold506-profile-20261104/`: the current-head profile, prototype source,
guarded launch/terminal receipts and complete comparison results. The profile
adds cProfile overhead and is diagnostic only. The actual runtime method is
checked against the measured prototype independently of formatting and local
type annotations.

## Acceptance and remaining work

The existing 276 identity-oracle checks pass against the prototype. The actual
file passes 288 identity and portfolio-batch checks. A broader local route run
stalls on Windows and is not counted as a pass; full Linux CI remains required.
The release
remains a separate draft, stacked on #506; it does not change #506's reviewed
head or use its pending approval. Fresh preservation and a separate explicit
release approval remain necessary before deployment.

TD-122 remains open: the first deep catalog visit still takes several seconds.
Article classification, repeated catalog freshness comparisons and the remaining
source/profile-depth work are separate outstanding work in the same mission.


## Completed confirmation — November 4

The follow-up completed all four counterbalanced replicates per route order:
16 fresh processes and 48 complete typed article/universe/context/HTML responses
match, with all 25,633 input files unchanged. The combined median three-page
workflow improves from 11.70s to 10.91s for Company-first (6.7%) and from 11.33s
to 10.58s for Candidates-first (6.6%). First-visit medians are 5.52s and 5.10s
respectively. One Company-first pair regresses 2.6%, and one Candidates-first
pair 1.7%; this is bounded handler evidence on one existing copy with a warm
filesystem, not a guarantee of live latency or a release-time rehearsal.

The actual-file draft #509 subsequently passed all four current-head checks
(6,729 tests, 11 skipped), its 288 local identity/batch checks and native
desktop/390px review. Failed earlier Windows diagnostics remain retained. Its
single runtime change is now included in a separate local consolidation with
Help #510 and shared Watchlist tracking #511. This does not modify the frozen
heads or grant merging/deployment approval. Fresh combined checks and guarded
production-copy preservation remain required after the source-release window.
