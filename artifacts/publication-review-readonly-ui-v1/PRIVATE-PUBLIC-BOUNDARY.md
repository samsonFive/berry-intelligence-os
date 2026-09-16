# PRIVATE-PUBLIC-BOUNDARY

## Private operator surface

| Asset | Boundary |
| --- | --- |
| `GET /review-ops/publications` | Live/authoring only; same private ops family as `/review-ops` |
| `GET /review-ops/publications/{id}` | Live detail hydration (bodies stay private) |
| Template panels | `data-pagefind-ignore` |
| Sidebar | No new public Library/Monitor link; entry from Review Operations (`{% if not static_build %}`) |
| `scripts/build_static.py` | Does not register or render these routes |
| Rehearsal fixtures | `tests/fixtures/` only — never under `data/` as live records |

## Must not enter static / Pagefind

- Draft IDs and private titles from the review queue
- Acquired bodies / transcripts
- Reviewer history / digests used for concurrency
- Decision control chrome implying live mutations
- Rehearsal fixture content

## Public surfaces checked

- `/guide` must not contain rehearsal draft IDs/headlines
- Today/reader PVS CSS remains separate (`daily_briefing.css` / `pvs_tokens.css` unchanged in meaning)
- Static builder source has no `/review-ops/publications` registration

## Trust boundaries honored

- Publication review ≠ Atomic Evidence approval
- AI enrichment labeled untrusted
- Proposed entities are associations only
- No trusted publication or Atomic Evidence created by this slice
