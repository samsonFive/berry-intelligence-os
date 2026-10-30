# Combined catalog release review

Draft #430 now brings the tested catalog stack and its later follow-ups into
one review against canonical `e24b566b`. Platform #421 stays separate. Frozen
#426 remains the earlier catalog option; approval of it does not approve this
expanded candidate. No merge or deployment is performed by this preparation.

## What changes for the analyst

- Existing profiles gain original filing/claim/illustration links and credited
  image references. Unknown photo permission remains held; an explicit private
  session choice does not grant public reuse or resolve an identity.
- Related reports remain separate from exact original filings. Source dates
  and document inconsistencies remain literal, without implying current rights.
- An existing Rutgers photo lead reaches name review instead of appearing to
  need a new photo search. Coded and named leads remain together for review.
- Coverage shares repeated photo validation and identity checks within one
  inventory call. The 64-profile local comparison returns identical data in
  about 0.6 seconds instead of 4.9–6.6 seconds. This is not whole-app production latency proof.
- The requirements and release notes account for the later conversation
  requests while retaining all 31 original requirement definitions and order.

The source stack is #399/#400/#418/#419/#422/#423/#424/#425, followed by #427/
#428/#429 and the #430 inventory optimization. The original performance slice
at `15baed4b` passed all four checks and 5,341 tests. Final candidate checks must
run on its current head against canonical; earlier tests and preservation
receipts do not establish the new combined release's readiness.

## Data and review boundaries

There are 32 added import files relative to canonical. Existing entities,
Evidence, Facts, relationships, schemas and the governing guide are unchanged.
No inferred alias, organization role, verified trait, growing region, current
right, source acceptance, extraction qualification or photo permission is added.
The bounded source corpus has 497 sections and 1,785 name occurrences, not that
many distinct approved varieties. CAT-01/CAT-02 and actual human source/name/
catalog decisions remain open.

The public research seed has 64 varieties; live production previously had 65.
Release preparation must use a new copy of production and preserve its actual
accounts, user edits, database contents and records. The research seed must
never replace the live runtime. Startup may add only missing import files.

## Release evidence required

1. Re-read current canonical, exact head and all four required checks.
2. Make a new verified production snapshot: stable included ordinary files and
   individually consistent SQLite backups. Do not claim one global transaction.
3. Restore only into a new private review directory. Build a copy-only image
   from the exact running image plus the committed runtime delta.
4. Run one offline bounded rehearsal: 1 GiB/no swap, one CPU, 256 PIDs, no network or
   published ports, read-only root and a 600-second limit. Check every original
   account and protected record, first-login Help with a fictional user only,
   all original profiles and the actual new filing/photo-review/coverage paths.
5. Verify exact rehearsal-container cleanup, unchanged live receipt/image and
   health, and retained earlier candidate images. Retain the verified backup,
   original mounts and current image for rollback.

The current draft description and durable mission ledger hold the final
exact-head CI, snapshot, candidate-image and preservation receipts after these
steps complete. This document specifies the acceptance contract; it does not
claim an unperformed rehearsal. Actual approval of the intended exact release
is still needed before merging or deployment, followed by fresh release-time
preflight/backup. The already pending #421/#426 questions are not answered by
preparing this candidate.
