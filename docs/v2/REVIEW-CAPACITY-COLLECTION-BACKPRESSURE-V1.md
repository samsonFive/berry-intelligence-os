# Review Capacity + Collection Backpressure V1

Date: 2026-08-22

## Outcome

V1 adds read-only backlog economics, deterministic aging and review-pressure warnings, source/query load reporting, and an inspectable backpressure simulation. Automatic throttling is **OFF**. No Source, schedule, draft, trust field, or trusted record is changed by these tools.

The production corpus does not contain enough recorded publication-review outcomes to calculate a defensible keep, publish, reject, or dismiss rate. Unreviewed drafts are inventory, never inferred analyst decisions. The report therefore keeps three categories separate:

1. `OBSERVED`: only persisted Pass, Fail, Publish, Reject, Dismiss, and Defer actions.
2. `DERIVED_OPERATIONAL_METRICS`: backlog size, age, arrivals, growth, composition, duplicates, and source/query load.
3. `SIMULATED_POLICY_EFFECT`: deterministic attention changes that *would* occur if the queue were critical. It does not predict analyst decisions.

## Operator commands

```bash
python scripts/review_capacity.py
python scripts/review_capacity.py --json
python scripts/review_capacity.py --json --include-items
python scripts/collection_status.py --json
```

The default capacity report is aggregate. `--include-items` is an explicit audit mode. `collection_status.py` exposes only the operational summary: pressure level, thresholds, median/oldest age, latest arrivals, net growth when persisted snapshots permit it, simulated deferrals, and `automatic_throttling_enabled: false`.

## Backlog composition and economics

The report derives counts by Source, source class, berry, geography, media type, relevance tier, direct/adjacent status, queue age, event age, exact duplicate/reprint cluster, query family, company, variety, review priority, and observed access limitation.

Source/query economics expose pending load, discovered and irrelevant counts when deeper input is supplied, direct/adjacent load, exact duplicate excess, and recorded outcomes. Publish/reject rates remain `null` until at least ten recorded publication decisions exist for the aggregate. Pending volume is never used as the denominator of a fabricated yield metric.

Arrival rate uses only persisted run records containing draft-creation counts and timestamps. Backlog growth uses persisted review-backlog snapshots where available. Manual creation outside recorded runs is explicitly unattributed. Review completions/day remains `null` until at least ten dated publication decisions span at least two days.

## Deterministic review priority

This is an attention policy, not a trust score:

- `Review Now`: recent direct intelligence with an existing strong context such as a high-priority Source, rare/regulatory class, or explicit Company/Variety.
- `Review Soon`: other protected direct/uncertain intelligence and important older protected work.
- `Backlog`: repetitive, adjacent, or older unprotected work.

Inputs are stored deterministic signals only: relevance tier, Source monitoring priority/class, explicit Company/Variety linkage, stored priority, age, and exact duplicate identity. There is no model call and no second relevance classifier.

Review priority never changes `source_authority`, `information_confidence`, `status`, `review_state`, or trusted data. Low priority does not mean false. High priority does not mean true.

## Aging and pressure levels

Queue age uses `discovery_provenance.first_seen_at`, then created/captured/published timestamps as declared fallbacks. Event age is separate so an old event newly discovered is not confused with a draft that waited a long time.

- 0–7 days: current
- 8–30 days: maturing
- 31–45 days: aging
- over 45 days: older backlog unless protected

Soft thresholds are warning at 750, high at 1,000, and critical at 1,500. They emit operating context only. Even at critical, V1 continues discovery and draft creation, emits a warning, and simulates attention deferral. It suppresses or deletes nothing.

## Simulated critical policy

The `as_if_backlog_were_critical` replay is deterministic and read-only. In order, it would:

1. keep one representative for each exact URL or exact normalized-title/date cluster;
2. defer non-regulatory exact reprint secondaries;
3. defer unprotected adjacent items beyond ten per Source;
4. defer unprotected items beyond 25 per Source;
5. defer unprotected items older than 45 days.

Direct and uncertain unique events, high-priority Sources, government/regulatory Sources, rare source classes, and explicitly linked Company/Variety items are protected. Deferred means “move analyst attention later,” not reject, discard, or make unavailable. Since V1 never activates the policy, no deferred state is written and the collection registry requires no new `THROTTLED` outcome. Any future activation must first define durable reversible deferral provenance and expose `THROTTLED`/`BACKLOG_LIMIT` in registry run state.

## Missing review-event instrumentation

True future keep/dismiss/publish-rate analytics require an append-only event ledger that does not currently exist. It must record:

- draft ID, action, timestamp, reviewer, Source ID, and pre-action queue bucket;
- an explicit Save/Keep decision distinct from editing a draft;
- consistent timestamps on every Publish and Reject outcome;
- reason/category for Dismiss and Defer;
- arrival-to-decision duration captured when the decision is made.

The current-state maps support UI state but cannot reconstruct every transition or an honest historical throughput series. This is TD-064.

## Production replay

Production replay results and deployment survival proof are recorded in `PROJECT-STATUS.md` after deployment. The activation decision remains **OFF** regardless of queue pressure because observed review outcomes are insufficient to validate real review economics.

## Safety boundaries

- No Sources or schedules added or modified.
- No automatic review, publication, rejection, or trust change.
- No Pending UI redesign or competing Coverage Matrix.
- No LLM ranking.
- No draft deletion or runtime-state mutation.

