# Competitor Pulse V1

**Status:** Shipped 2026-09-01.

## Problem

A user could not open a Company and answer "what's the current news/chatter
about this competitor?" without waiting for Publication Review or Evidence
Review -- durable trust is deliberately slow and human-gated, but that meant
there was no fast path to just-search-it-now, the single most basic thing a
competitive-intelligence tool should do.

## Architecture

```
Company (entity record: name + aliases + owned-brand relationships)
        |
        v
app/services/competitor_pulse.py :: company_query_terms()   -- explicit only, never invented
        |
        v
industry_pulse.providers.discover()   -- Google News RSS, optional Perplexity
        |
        v
industry_pulse.qualify.qualify_hit()  -- REUSED, plus two Competitor-Pulse-
        |                                 specific tightenings (see below)
        v
industry_pulse.dedup.dedupe_hits()    -- REUSED, unchanged
        |
        v
competitor_pulse.categorize_hit()     -- 8 deterministic content groups
        |
        v
competitor_pulse.generate_current_brief()  -- grounded "What should I know?"
        |
        v
        display (trust_label = "LIVE / UNREVIEWED")
        |
        v (optional)
industry_pulse.intake.intake_qualified_hits()  -- REUSED verbatim
        |
        v
inbox/evidence/*.json (status=draft, evidence_role=publication_artifact)
        -> Publication Review -> Evidence Review, unchanged
```

`GET /pulse/company/{company_id}` runs the live query directly and renders
immediately -- unlike Industry Pulse's 32-query matrix, this is one bounded,
company-scoped query per provider, so there is no separate "run" step.
`POST /pulse/company/{company_id}/promote` is the optional bridge into the
existing, completely unchanged Publication Review pipeline.

## Why `qualify_hit` needed two Competitor-Pulse-specific corrections

`qualify_hit`/`QualificationIndex` were built for industry-wide pulse, where
company names are a *secondary* signal among many berry/industry terms.
Reused unchanged for a company-*anchored* search, two real precision bugs
surfaced during production-acceptance testing (see below) and were fixed
locally in `competitor_pulse.py`, without touching the shared
`industry_pulse/qualify.py` module other missions depend on:

1. **Ambiguous short aliases** ("Fall Creek" is also a Wisconsin town) let
   through library/wildfire/obituary noise on a bare name match. Fixed by
   `distinctive_terms()`/`_corroborated()`: a hit qualifying *only* on a
   short alias match now needs a second signal (crop/industry term, or a
   match against the company's full/distinctive name) to count.
2. **Same-topic-different-company** hits (a blueberry-production story about
   a *different* company) could qualify on crop/industry terms alone without
   ever mentioning the target company at all. Fixed by `_mentions_company()`:
   every qualifying hit must literally mention one of the company's own
   query terms in title/snippet.
3. **Typographic apostrophe mismatch** -- Google News returns "smart quotes"
   (U+2019) while this system's own entity `aliases` use plain ASCII
   apostrophes, so a literal "Driscoll's" mention in a headline silently
   failed to match. Fixed by `_normalize_quotes()`, applied to both query
   terms and provider-returned title/snippet before qualification.

All three were caught by this mission's own required manual-web-challenge
acceptance step (see `PROJECT-STATUS.md` for the full before/after).

## Trust boundary

- Never writes Evidence.
- Never mutates Company (or any other entity) truth.
- Never creates a Signal or Assessment.
- Never silently creates a canonical entity or onboards a Source.
- Every result: `trust_label = "LIVE / UNREVIEWED"`, never "Reviewed
  Evidence."

## Synthesis security boundary

`generate_current_brief()` mirrors `report_builder/synthesis.py`'s existing
discipline exactly: only title/publisher/date/snippet of the already-
displayed live results are ever sent to the model; every returned
statement's `source_ids` are validated against the known displayed-item ids
before rendering, and an ungrounded or citation-less statement is dropped
rather than shown. Assessment rationale, Signal observations, private
notes, and internal Facts are never in scope of this function at all.

## What this does not do

- Does not require Publication Review or Evidence Review before display.
- Does not run a full berry x geography matrix -- one company-scoped query
  per provider.
- Does not invent company aliases -- only the entity's own `name`,
  `aliases`, and any brand it explicitly `owns` (relationship record).
- Does not introduce Bright Data/Firecrawl.
- Does not cache raw provider results between requests -- fully stateless;
  the optional promote action re-runs the same live query rather than
  trusting anything cached client-side.

See TD-109 (Hortifrut `aliases` containing a RUT tax-ID string, not a name
variant) for a related data-quality finding surfaced during acceptance.
