# Source Reliability Remediation V1

## Scope and invariants

This mission remediates one blocked direct publisher Source, audits three
yield-change warnings, and adds the smallest deterministic lifecycle contract
for Sources that become non-collectible. It does not change freshness grace,
failure thresholds, current-through semantics, trust, review, extraction,
queries, or collection cadence.

Implementation began from actual canonical `6fd8602861e96414826627d5b7e5c1626e357959`.

## Growing Produce root cause

Source identity: `source-20260819-growing-produce-berries`.

| Observation | Result |
|---|---|
| Adapter | `article_rss` |
| Configured feed | `https://www.growingproduce.com/fruits/berries/feed/` |
| Retained production attempts | 26 |
| First retained failure | `2026-08-19T08:07:45+00:00` |
| Latest retained failure | `2026-08-24T08:52:27+00:00` |
| Retained successful collection | None |
| HTTP/result class | HTTP 403 on every attempt; zero found/new/known items |
| Redirect behavior | No redirect; the configured URL itself returns 403 |
| Parsing behavior | Not reached because HTTP status validation fails first |
| Robots | `/robots.txt` is reachable and does not disallow the berry path |
| Source existence | The publisher and berry archive still exist |
| Berry category/archive | 403 from production egress |
| Berry RSS variants | 403 from production egress |
| Publisher-declared sitemap | 403 from production egress |
| Broad publisher RSS | 200, but intentionally rejected as a replacement because it is all-produce, not berry-scoped |

The registry's onboarding note records a 200 verification on 2026-08-19, but
the retained production history contains no success. The durable conclusion is
therefore not `SOURCE_REMOVED` or `FEED_MOVED`: the publisher is alive and the
path exists, while the production integration is persistently rejected by
path-specific access enforcement.

Explicit failure classification: `ROBOTS_OR_ACCESS_BLOCKED`.

## Resolution decision

The Source is not retired. It is now explicitly
`OPERATOR_ACTION_REQUIRED`, with reason and timestamp preserved in the Source
record. Automatic collection excludes it, but authoritative freshness keeps it
in scheduled coverage as `BLOCKED`. This pauses pointless retries without
creating a false green state.

The informational publisher-page URL was corrected from the obsolete
`/category/fruits/berries/` form to the current official
`/fruits/berries/` archive. This does not claim collection repair: the direct
berry RSS under that archive remains access-blocked from production.

There is no replacement Source relation. The reachable publisher-wide RSS was
not substituted because that would convert a berry-scoped direct Source into a
broad produce feed. No Google News fallback, scraper, access-control bypass, or
new Source was added.

Operational coverage consequently remains factual before deployment proof:

| Berry | Before | Expected after lifecycle resolution |
|---|---:|---:|
| Blueberry | 58/59 current | 58/59 current |
| Strawberry | 40/41 current | 40/41 current |
| Raspberry | 38/39 current | 38/39 current |
| Blackberry | 38/39 current | 38/39 current |

## Yield-drift audit

The three Sources each have nine retained successful operation results: one
initial population run and eight repeat runs. Their last three successes found
zero new items, which correctly triggered the conservative
`NEW_ITEM_YIELD_DEGRADED` condition. Those probes were closely spaced within
the Sources' daily cadence and remained successful with stable feed depth.

| Source | Items/run | New/repeat run | Duplicates/repeat run | Process-screened | Drafts/run | Rich bodies | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| Mexico berry news (Spanish) | 81.00 | 1.375 | 79.625 | 82/93 | 8.44 | 75/76 | WATCH; keep query and daily cadence |
| Morocco berry news (French) | 49.67 | 0.375 | 49.250 | 45/54 | 4.78 | 43/43 | WATCH; keep query and daily cadence |
| UK berry growers | 100.00 | 1.375 | 98.625 | 83 process + 8 borderline / 112 | 9.44 | 85/85 | WATCH; keep query and daily cadence |

The repeat-run figures exclude the initial population run. Drafts/run use all
nine retained runs because per-run draft attribution is not separately stored.
Mexico has one explicit thin draft; the other 203 measured drafts have rich
article bodies. Lower incremental yield is duplicate-heavy polling plus a
short quiet observation window, not evidence of lower market activity, endpoint
failure, relevance-filter regression, or rich-body collapse. Existing direct
Sources do not replace the regional-language discovery value of these searches.
No query, adapter, or cadence change is justified.

## Source lifecycle contract

Lifecycle configuration and observed runtime health remain separate:

- `ACTIVE`: eligible for collection and included in scheduled freshness.
- `DISABLED`: retained in the registry, excluded from collection and scheduled freshness.
- `RETIRED`: retained in the registry, excluded from collection and scheduled freshness; reason/timestamp required and replacement optional.
- `OPERATOR_ACTION_REQUIRED`: excluded from collection, retained in freshness as blocked coverage.
- `BLOCKED` and `FAILING`: observed Source Health states, not lifecycle aliases.

Legacy `enabled=false` maps to `DISABLED`. Unknown configured lifecycle values
fail closed as `OPERATOR_ACTION_REQUIRED`, so a typo cannot silently resume
collection. `scripts/set_source_lifecycle.py` is dry-run by default and requires
`--apply` for the selected Source only. It preserves Source id, discovery
configuration, historical records, Evidence references, inbox state, and all
other Source fields.

Returning a blocked Source to `ACTIVE` is not itself enough to claim current:
the existing freshness contract still requires a genuine successful collection
result. A failed probe remains degraded; only a real success resets the retained
failure streak.

## Validation and production proof

Pre-PR focused lifecycle/freshness/cadence/collection/discovery validation:
109 tests passed. Record validation passed; the static build produced 1,618
pages and passed its private-draft leakage check; `git diff --check` passed.
The full Windows suite completed with 1,675 passes and two failures: one
expected collection-eligibility count changed from 73 adapter-configured to 72
fetch-eligible plus one operator-action Source, and passed after correction;
the unrelated pre-existing Brief Pack warm-route timing assertion remained
environment-sensitive at 1.01-2.49 seconds against a 1-second threshold. No
Brief Pack code changed. Final CI, deployment backup, runtime integrity, and
post-deployment freshness proof are appended after merge and deployment.
