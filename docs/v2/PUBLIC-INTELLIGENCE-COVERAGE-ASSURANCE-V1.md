# Public Intelligence Coverage Assurance V1

**Purpose:** Make likely public-intelligence blind spots visible. Do not claim the public universe is complete. Do not invent a coverage score.

**Route:** `/coverage-assurance` (authoring-only). GET is read-only.

**Why this exists:** Italian Berry already appeared in trusted Evidence (`ev-italianberry-peru-varieties-2025`, `ev-italianberry-mbo-chile-2020`) while the publisher was not an actively collected Source. Existing coverage counts therefore cannot be treated as evidence of comprehensiveness.

## What this extends

Coverage Assurance is a reconciliation layer over existing machinery:

- Source inventory: `data/configuration/sources.json`
- Collection eligibility: `app/services/source_lifecycle.py`
- Technical health: `app/services/source_freshness.py` (`classify_source_freshness`)
- Collection operations / run history: `/collection-ops`
- Miss classification: `app/services/recall_audit/classify.py` (Independent Missed
  Intelligence Discovery + Recall Audit V1's taxonomy -- reused directly here,
  never reimplemented, per this mission's own "do not build a competing
  taxonomy" instruction)
- Blocked / wrapper hosts: `blocked_domains.json`, `UNBLOCKABLE_DOMAINS`

It does not replace Source Health, Collection Ops, or Source Fidelity.

## Source Universe

`data/configuration/source_universe.json` is a body-free Coverage Registry. A row is a publisher, registry, or resource that is strategically relevant whether or not it is currently onboarded.

Runtime overlay adds onboarded publisher hosts from `sources.json`. GET never writes this file. Article bodies are forbidden.

Collection status is derived, not scored:

| Status | Meaning |
|---|---|
| COLLECTED | An onboarded Source is collection-eligible for this publisher host |
| KNOWN / NOT COLLECTED | Universe identity or onboarded-but-ineligible Source; no live collector |
| UNKNOWN SOURCE IDENTITY | Cited or observed host with no universe row and no matching Source |
| INTENTIONALLY EXCLUDED | Stored reason (example: `news.google.com` is a redirect host, not a publisher) |

Google News wrapper feeds do not count as collecting the wrapper host or any publisher that appears in search hits. That is the Italian Berry class of failure.

Gaps do not auto-onboard Sources. Operator path: inspect the gap → add a collector through existing `/sources` governance.

## Technical health vs intelligence yield

Technical health reuses freshness states (CURRENT / QUIET / DUE = healthy; FAILING / BLOCKED = broken).

Intelligence yield is separate:

- ACTIVE: relevant Evidence, Publications, or discovered items in the last 90 days
- DEGRADED: collector succeeds, zero relevant items in 90 days, and either earlier yield was observed or an explicit `yield_expectation_days` exists
- UNOBSERVED: collector succeeds, but there is no observed history and no explicit expectation
- NOT APPLICABLE / UNKNOWN: not collected, or the collector is broken

No publication frequency is invented.

## Coverage matrix

Raw counts by berry, geography, and source class:

- Known sources
- Active sources
- Healthy
- Yield degraded
- Cited but not collected
- Independent benchmark misses

Zero means none recorded. It is not a claim that the public universe is empty.

## Miss classification

The 9-class taxonomy from `app.services.recall_audit.classify` (`MISS_CLASSES`), used by every scored benchmark on this page:

- SOURCE UNKNOWN
- SOURCE KNOWN, NOT COLLECTED
- SOURCE COLLECTED, ITEM MISSED
- ITEM COLLECTED, ENTITY MISSED
- ENTITY FOUND, IDENTITY UNRESOLVED
- DATE/CHRONOLOGY FAILURE
- GEOGRAPHY LINKAGE FAILURE
- FULLY REPRESENTED
- UNSUPPORTED / NOT QUALIFYING

A benchmark reports those raw counts for that run. It is not "65% coverage."

## Independent recall benchmarks

Benchmarks load from two places, merged:

- Private, analyst-run ad-hoc benchmarks: `inbox/coverage_assurance/benchmarks/{id}.json`
- Committed, versioned benchmark files: `data/imports/*/benchmark.json` -- e.g.
  Independent Missed Intelligence Discovery + Recall Audit V1's own output
  lands here automatically once merged, with no code change on this page.

A benchmark is a coverage test generated outside the normal collector. Hidden provider reasoning is stripped on load. Results never become trusted Evidence. Discovery in a benchmark never onboards a Source.

## Scope boundaries (V1)

Deliberately not built in V1, to stay within this mission's bounded scope rather than compete with adjacent missions:

- No candidate-Source proposal mechanism (no `source_discovery.py`-style
  plumbing exists anywhere in this codebase yet; adding one is a real,
  separate feature, not a reconciliation-layer concern).
- No cross-page integration into `/today` or `/varieties/coverage` (both
  were touched by an earlier abandoned draft of this feature; left for a
  follow-up so this PR stays a single reviewable surface).
- No live web-search "catch-net" querying -- that is Independent Missed
  Intelligence Discovery + Recall Audit V1's job; this page only reconciles
  whatever benchmark results already exist against canonical data.

## Static / private

`/coverage-assurance` is authoring-only (`AUTHORING_MODE` gated, 403 otherwise) and is never emitted by `scripts/build_static.py`.
