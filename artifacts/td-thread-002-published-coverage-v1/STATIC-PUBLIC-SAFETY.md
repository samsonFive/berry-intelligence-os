# Static / public safety

## Guards kept

- `scripts/build_static.py` does not import or call `group_story_threads` / `live_thread_candidate_universe`.
- No `/threads` pages are emitted (`generated/threads` does not exist).
- Global Search still uses `_cheap_pending_threads()` and does not call `group_story_threads()`.
- Landscape does not call `group_story_threads()`.
- `app/main.py` does not call `group_story_threads()` on nav, search, or landscape paths; live `/threads` uses `thread_for_item()` on the bounded universe only.
- Overlay `/api/intelligence/{id}/reader` still skips thread assembly (`overlay=True`).
- Pending drafts remain inbox-only. Static build leak check: “Verified: no unpublished draft ids or titles appear in the output.”

## Tests

- `test_static_build_does_not_group_or_leak_private_threads` — source-level prohibition on Search / Landscape / static build.
- `test_static_output_excludes_pending_thread_members` — isolated static build with a pending sentinel title; sentinel and draft id absent from every generated HTML file; no `generated/threads` tree.
- Existing `tests/test_build_static.py` suite left passing.

## Pagefind

Pagefind indexes the trusted static snapshot only. No private thread index was added.
