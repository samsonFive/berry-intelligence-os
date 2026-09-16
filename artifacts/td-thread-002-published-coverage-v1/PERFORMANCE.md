# Performance / boundedness

Measured 2026-09-16 against the worktree corpus (JSON walk of `data/evidence/`, no FastAPI import).

| Metric | Result |
|---|---|
| Trusted published records | 1269 |
| Recency window | 14 days (`DATE_PROXIMITY_EXACT_TITLE_DAYS`) |
| Recent published in window | 0 (corpus is older than 14 days as of 2026-09-16) |
| JSON load | 1.737 s (existing `published_evidence()` cost; not new) |
| Recency filter + universe merge | 0.027 s |
| Seed + one-hop `expand_with_related` over all published | 0.407 s (pre-existing `/threads` cost) |
| `group_story_threads` on expanded seed universe | 0.002 s |
| `group_story_threads` on **all** 1269 published (rejected design) | 0.412 s, 1246 thread objects |

## Bound

The new work is a date filter over already-loaded published Evidence, then first-wins id merge. It does **not** put the historical corpus into the default candidate set. Older records enter only as:

- the currently viewed seed, or
- a one-hop `expand_with_related` match (stored same-event links / exact-title reprints of the seed).

Synthetic boundedness test: 200 stale published records + 2 recent reprints → universe size 2 (`test_recent_published_universe_is_bounded`).

Request path: `/threads/{id}` and full `/intelligence/{id}` only. Not Search, Landscape, or nav.
