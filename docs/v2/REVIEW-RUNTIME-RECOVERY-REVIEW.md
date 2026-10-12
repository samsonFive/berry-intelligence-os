# Review runtime recovery — October 12, 2026

Preparing the combined review candidate exposed a recovery defect: a backup
created under the shared pipeline lock also copied that live lock. A restore
could then refuse a new collection operation for up to the six-hour lease age,
although the process that owned it no longer exists in the restored runtime.
The existing data-integrity guide already classified that lock as recreatable;
the backup implementation did not follow that boundary.

## Repair and evidence

- New backups exclude only `inbox/operations/collection.lock`. Run history and
  similarly named files elsewhere remain included. The original active lock is
  left intact throughout backup, and concurrent writers remain blocked.
- Older format-v1 archives remain checksum-verified in full, including the
  archived lease. Restore skips recreating that exact process lease, verifies
  every restored data file and reports its actual count and skipped path.
  A corrupt archived lease still fails before any target write.
- Explicit nonempty low-level restore does not delete or overwrite an existing
  target lease. Normal empty-target and exclusive-file rules are unchanged.
  No collector, human review gate, schema, provider or lock-expiry rule changes.

The initial isolated regression reproduced the defect: the active backup lease
appeared in the manifest. The repair passes **18 backup, pipeline-lock, package
and review-event tests**, 5.09 seconds. Record validation and the complete
**1,755-page public build with Pagefind** pass. Fresh current-head CI remains a
separate requirement; the parent photo draft's manifest-count repair passes
31 portfolio/photo tests and also needs fresh CI.

## Actual local recovery

The retained source-review runtime was backed up under its existing shared lock
and restored to a new empty private directory. **All 79 files matched their
manifest hashes**. The original runtime's file bytes were unchanged. All **32
source copies remain pending**, the original pending draft is unchanged, and a
new collection lease can be acquired and released in the restored copy.
No collection/model call, source decision, identity decision or qualification
was performed.

This rehearsal covers a **local review inbox**, whose data directory lives
outside that runtime. It is not a production backup or a complete production
data/inbox recovery. The private results and archives remain under
`inbox/european-portfolio-followup/combined-review-2026-10-12/`. They contain
retained source text and must not enter a PR, code package or public output.

An initial committed-code package separately verified 3,610 files and Linux
executable/newline bytes. The recovery fix changes that code, so the final
review package must be regenerated from the repaired committed head. Its hash,
complete review-runtime restore, browser walkthrough and exact-head CI must be
recorded before it is represented as the combined tested release.

## Remaining release gates

The [31-requirement checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md) and visual guide
retain the full redesign, consolidation and explainer scope. CAT-01/CAT-02 and
TD-116 remain open for comprehensive portfolios, original text, current rights,
photos, independent human recall and catalog decisions. Actual phone verification
of the newer views remains outstanding. Revised blueberry feedback gates other
Landscape berries; separate approval gates merge/deployment. A fresh verified
production backup and previous-image/configuration proof remain necessary before
an approved live change. Nothing is merged, deployed or restored over production.
