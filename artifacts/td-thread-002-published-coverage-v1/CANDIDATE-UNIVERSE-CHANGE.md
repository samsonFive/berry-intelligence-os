# Candidate-universe change

## Recency policy reused, not invented

`THREAD_UNIVERSE_WINDOW_DAYS = DATE_PROXIMITY_EXACT_TITLE_DAYS` (14). Live `/threads` includes a published record when `item_date()` is within that window of `date.today()` (tests freeze `as_of`). Future-dated records are not auto-included; a current-record seed is always added separately.

Canonical trusted-published query remains `published_evidence()` (`status == "published"`).

## New helpers (`app/services/story_threads.py`)

- `in_thread_universe_window(record, as_of=)`
- `recent_published_for_threads(published, as_of=)`
- `merge_thread_universe(*groups)` — first-wins by id, pending then seed then recent published
- `live_thread_candidate_universe(pending=, seed=, published=, as_of=)` — copies records so annotation cannot mutate repository objects or trust status

## Route wiring (`app/main.py`)

`_live_story_thread_universe(seed, entities=, source_index=)` is the single live builder used by:

- `GET /threads/{item_id}`
- `GET /intelligence/{item_id}` (full reader only; overlay `/api/intelligence/{id}/reader` still skips threads)

Behavior:

1. Universe = pending drafts + seed + recent trusted published, id-deduped.
2. Pending / seed keep `attribute_draft` primary-subject resolution.
3. Extra published rows keep the existing first company/variety `entity_ids` convention.
4. `expand_with_related(universe, all published copies)` stays one-hop so **stored same-event links** to older published records still attach, without putting the whole historical corpus into the default universe.

## Dedup

If a pending draft and a published record share an id, the pending copy wins (it is merged first). Canonical-URL duplicates with distinct ids still form **one thread** via the unchanged `_same_url` predicate.

## Surfaces explicitly not wired

- Global Search
- Landscape / Executive Readout / nav badges
- `scripts/build_static.py`
- Pagefind
- Morning Brief (already grouped its own pending/reading pool)
