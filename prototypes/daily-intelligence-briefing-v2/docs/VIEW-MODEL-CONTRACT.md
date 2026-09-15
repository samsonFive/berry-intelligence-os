# Daily Intelligence Briefing V2 — View-model contract

Prototype contract for a future production briefing surface. This document does **not** change production schemas.

## Briefing page model

| Field | Type | Exists today | Derivable | Needs future analyst / product input |
|---|---|---|---|---|
| `briefing_title` | string | Partial (Morning Brief copy) | Yes | Final product naming |
| `briefing_subtitle` | string | Partial | Yes | Final framing |
| `as_of` | date | Yes (runtime clock) | Yes | — |
| `what_changed[]` | item[] | Partial via brief/feed | Partially | Ranking policy |
| `why_it_matters[]` | implication[] | Partial via assessments/signals | Partially | Explicit observed-vs-interpretation authoring |
| `needs_attention[]` | attention[] | Partial via queues/source health | Partially | Unified attention taxonomy |
| `unknown_date_appendix[]` | item[] | Partial (undated evidence exists) | Yes | Presentation rule only |
| `coverage_pulse` | object | Partial via source health + landscape | Yes | Exact competitor-universe denominator |

## Item model (`what_changed` / attention / appendix)

| Field | Exists today | Derivable | Future input required |
|---|---|---|---|
| `id` | Yes | — | — |
| `headline` | Yes (`title`) | — | — |
| `source` | Yes | — | — |
| `canonical_url` | Yes | — | — |
| `publication_date` | Yes (`published_date`) | — | Better extraction quality |
| `capture_date` | Yes (`captured_date`) | — | — |
| `recency_band` | No dedicated field | Yes from publication_date | Band thresholds (0–30 / 31–60 / 61–90 / older / unknown) |
| `berry` | Partial tags | Yes when tagged | Completeness |
| `regions` | Partial | Yes when present | Normalization to landscape codes |
| `topics` | Partial | Yes | Controlled vocabulary |
| `entity_ids` | Yes when linked | — | Linking quality |
| `readable_content_state` | Partial body/quality signals | Yes with fidelity classifiers | Explicit enum in API |
| `content_quality_state` | Partial | Yes | Consent/bot/empty taxonomy productization |
| `review_state` | Partial review queues | Yes | Unified review-state enum for briefing |
| `evidence_confidence` | Partial | Yes | Briefing-facing labels |
| `observed_change` | Rare / uneven | Sometimes | Analyst or curated extraction |
| `extracted_body` | When readable | — | Never invent for unreadable |
| `related_landscape_url` | No | Yes from berry/region/entity | Stable query contract |
| `profile_url` | Yes for known entities | Yes | — |
| `attention_reason` | Scattered across ops surfaces | Partially | Single attention taxonomy |
| `acquisition_outcome` | Partial source/body outcomes | Yes | — |
| `historical_or_current` | No | Yes from recency_band + review | Presentation policy |
| `operator_message` | Informal | — | Operator copy patterns |
| `prototype_synthetic` | N/A | N/A | Prototype-only marker |

## Implication model (`why_it_matters`)

| Field | Exists today | Derivable | Future input required |
|---|---|---|---|
| `observed_fact` | Evidence/fact text | Sometimes | Must remain distinct from interpretation |
| `analyst_interpretation` | Assessment/signal rationale | Sometimes | Required for this section |
| `decision_implication` | Partial assessment fields | Sometimes | Briefing-specific decision wording |
| `supporting_evidence_count` | Yes via links | Yes | — |
| `review_state=reviewed_implication` | No exact enum | Partially | Explicit reviewed-implication gate |

## Coverage pulse model

| Field | Exists today | Derivable |
|---|---|---|
| `represented_competitors` | Landscape roster / entities | Yes |
| `discovery_configured` | Source registry | Yes |
| `discovery_operational` | Source health execution | Yes |
| `readable_content_acquired` | Body/acquisition outcomes | Yes |
| `current_usable_coverage` | Readable + reviewed + current | Yes with policy |
| `competitors_with_no_current_coverage` | Gap vs roster | Yes |

## Content honesty rules (non-negotiable)

1. Only `readable_content_state=readable` and `review_state=trusted_usable` may enter **What Changed**.
2. Capture date must never be presented as publication freshness.
3. Unknown publication dates belong in the appendix, never as lead briefing.
4. Bot wall / cookie consent / body unavailable never receive intelligence summaries.
5. Observed fact and analyst interpretation remain visually and structurally separate.
6. Genetics / variety links appear only when verified; prototype marks unverified genetics explicitly.

## Landscape handoff query contract

```
./landscape-handoff.html?berry=blueberry&region=DOTA&tier=Tier%201&focus=company-fall-creek&from=briefing-v2
```

Production can map this onto the Competitor Landscape V1 filter query string without changing landscape semantics.
