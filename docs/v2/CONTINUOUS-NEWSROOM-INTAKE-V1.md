# Continuous Newsroom Intake V1

**Status:** Shipped 2026-09-01.

## Problem

Industry Pulse (Discovery V1, Qualification V1, Perplexity Activation V1)
discovers and qualifies current berry-industry developments, but stopped
there by design: a qualifying `DiscoveryHit` was diagnostic metadata only,
never a Publication draft. Fresh discovery never reached Publication
Review or the Front Page's Emerging/Unreviewed section. An analyst opening
the homepage still saw nothing newer than the last reviewed Evidence, even
when Industry Pulse had already found and qualified something better.

## Architecture

```
Google News RSS  +  Perplexity catch-net (optional)
        |
provider-neutral qualification (qualify_hit / QualificationIndex)
        |
dedup / novelty (dedupe_hits, classify_hit)
        |
        v
app/services/industry_pulse/intake.py :: intake_qualified_hits()
        |
   novelty-before-acquisition check (article_dedup.find_duplicate_article)
        |
   bounded body acquisition (article_acquisition.fetch_article)
        |
   Publication draft construction (build_pulse_draft)
        |
        v
inbox/evidence/*.json  (status=draft, evidence_role=publication_artifact)
        |
        v
Publication Review  ->  Front Page Emerging/Unreviewed
```

`app/services/industry_pulse/newsroom_cycle.py::run_newsroom_cycle()` ties
discovery and intake together under a lock, and
`app/services/industry_pulse/intake.py::intake_qualified_hits()` is the
bridge itself.

## Why not fork `media_orchestration.prepare_publication_draft()`

That function pulls `source_name`/`source_url` from the *registered
Source* record. That is correct when the Source's own feed IS the
publisher (an RSS Source's articles are always from that publisher). It is
wrong here: the discovering provider (Google News RSS, Perplexity, or any
future one) is never the publisher, and a pulse hit's real publisher
domain frequently has no registered Source at all. `intake.py` builds an
equivalent draft by hand, reusing every real primitive underneath instead
of duplicating them: `article_dedup.find_duplicate_article`,
`article_acquisition.fetch_article`, `publication_enrichment.
enrich_publication_draft`, `source_completeness.with_source_completeness`.

## Unknown Sources

A qualifying hit's real publisher is looked up by hostname against
already-registered Sources. If found, the draft is correctly attributed
to that Source. If not, the draft is attributed to
`source-industry-pulse-catchnet` -- one shared, `enabled: false`,
no-`discovery.adapter` placeholder Source that exists *only* to satisfy
the Publication schema's Source-linkage requirement. It is never
collection-eligible, never scheduled, and never displayed as if it were
the actual publisher: every such draft's own `source_name`/`source_url`/
`pulse_provenance.publisher_domain` fields always carry the real
discovered publisher. No new *trusted* Source is ever silently created,
and no second Source repository exists.

## Provenance

`pulse_provenance` (a new, additive top-level field -- `evidence.
schema.json` has no `additionalProperties: false`) records:

```json
{
  "providers": ["perplexity"],
  "query_ids": ["pulse:blueberry:americas:7d"],
  "geography_query": "americas",
  "berry_query": "blueberry",
  "topic_query": "industry_pulse",
  "publisher_domain": "realpublisher.example",
  "wrapper_url": null,
  "discovered_at": "2026-09-01T12:00:00+00:00"
}
```

This is deliberately separate from `berry_ids`/`geography_ids`/
`entity_ids`, which stay content-verified via `enrich_publication_draft`'s
deterministic tagging against the acquired text -- a query's berry/topic
target is not the same claim as a confirmed link. `berry_query` is `None`
on the 12 global topic-intensifier matrix rows and set on the 20 berry x
geography rows, which gives a deterministic DIRECT-berry-intelligence
vs. BROADER-industry-context signal for free, without inventing a new
relevance tier.

## Trust labels

Every pulse-derived draft is `status: "draft"`, `evidence_role:
"publication_artifact"` -- the exact same shape `today.py`/`front_page.py`
already classify as FRESH/UNREVIEWED or SOURCE-BACKED/AWAITING REVIEW
(via the existing `source_completeness.class` field, unchanged). No new
trust state was invented; `front_page.py` has zero awareness that a draft
came from Industry Pulse at all.

## Locking, scheduling, telemetry

`run_newsroom_cycle()` reuses `CollectionRunner.CollectionRunLock`
verbatim at a separate lock path (`operations/industry_pulse_intake.lock`)
from the main collection lock -- pulse discovery and per-Source RSS
polling are independent resources that should only serialize against
themselves. `data/configuration/collection_pipelines.json`'s new
`industry_pulse_intake` entry (every 4 hours) needs no systemd/VPS
change: the existing 15-minute `run_due_pipelines.py` timer already polls
it. `scripts/industry_pulse_intake.py --json`'s output layers
`pipeline_health.py`-compatible top-level fields onto the full detailed
result so `/collection-ops` observes it with no special case.
`provider_telemetry`/`union_unique_count`/`overlap_qualifying_count`
record measured counts only -- no dollar cost is computed at runtime.

## Activation

`ENABLE_PERPLEXITY_PULSE` is the single switch, read identically by
`app/main.py`'s routes and `scripts/industry_pulse_intake.py`'s scheduled
CLI invocation -- setting it once in the deployment environment activates
both consistently. See `PROJECT-STATUS.md` for the current production
state and cost estimate.

## What this does not do

- Does not write trusted Evidence, ever.
- Does not bypass Publication Review.
- Does not auto-onboard a Source into `sources.json` or
  `data/configuration/source_universe.json`.
- Does not acquire every discovery hit -- only qualifying, novel,
  not-already-represented ones, bounded per run.
- Does not introduce Bright Data/Firecrawl (separate provider candidates,
  explicitly out of scope).
- Does not implement social/community ingestion (explicitly deferred);
  the provider/provenance model is generic enough (any `provider` string,
  `pulse_provenance.providers: list[str]`) that a future licensed social
  provider could normalize into the same discovery layer without
  rewriting Publication ingestion -- but no such provider exists yet, and
  representing unverified chatter would need its own explicit non-
  Publication trust state, not this one.

See TD-106 (Front Page dedup scope), TD-107 (The Packer has no article
collector), TD-108 (FreshPlaza duplicate Source records) for related
known gaps this mission's own production-acceptance audit surfaced but
did not fix.
