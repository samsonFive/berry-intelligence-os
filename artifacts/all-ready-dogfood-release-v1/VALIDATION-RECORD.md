# Validation Record

## Focused integration validation

- Calendar/Today/front-page/story-thread slice: 103 passed.
- Publication Review domain, repository, command, crash recovery, migration, query, durable page, rehearsal UI, adversarial, static-safety, Review Operations, and source-body slice: 216 passed, 9 skipped.
- Collection Operations, Source Health, Watchtower, War Room, monitoring, Reading Queue adjacent checks: 215 passed after route restoration; final affected subset: 113 passed.
- Full pre-repair diagnostic run: 3,144 passed, 7 failed, 5 errors, 9 skipped. Every failure was repaired; none was accepted as inherited.
- Final repaired subset (export, domain pack, weekly navigation, guided analyst, Today shell): 71 passed.

## Repairs proven by the focused gates

- Source count is 205 and all 205 sources are represented by a collector template or documented exclusion.
- Relationship count is 255 and every predicate is declared.
- Portable published-only exports no longer contain dangling references to unpublished evidence; relationships supported only by unpublished evidence are explicitly excluded from the package manifest.
- Today exposes War Room, Watchtower, and This Week through the PVS navigation.
- Publication review has one durable production page, a separately gated fixture rehearsal, no mutation controls, and no full-body leak.

The complete exact-head suite, record validation, static build, leakage scan, mutation comparison, browser smoke, CI, and independent Luna result are recorded in the release PR and final release report because those checks must run after the final documentation commit fixes the candidate SHA.
