# Rebase after PR #255

PR #255 (`fix/td-108-109-learner-ipm-v1`, HEAD `3c585f2`) is frozen, unmerged, and **must not** be incorporated into this branch to paper over CI.

## Why this branch will not be merge-ready until #255 lands

Canonical `origin/v2/intelligence-os` at this mission’s base (`c0de14c88960c22fee97a51fef0c71ffe386bcf9`) still contains calendar-sensitive failures that #255 repaired (Learner `/learn/stale`, `/today` clock freeze, related count 76→75). This branch deliberately does **not** copy those repairs.

## After #255 merges to `v2/intelligence-os`

1. Fetch canonical: `git fetch origin v2/intelligence-os`.
2. In this worktree: `git rebase origin/v2/intelligence-os`.
3. Expect conflicts only if #255 touched `app/services/story_threads.py`, `app/main.py` thread routes, or `tests/test_story_threads.py`. #255’s Learner / source / `/today` files should replay cleanly around this change.
4. Do **not** re-apply #255’s Learner EOF, `/learn/stale` rewrite, or date-frozen `/today` tests — they should arrive via the rebase.
5. Re-run:
   - `python -m pytest -q tests/test_story_threads.py`
   - `python -m pytest -q tests/test_build_static.py tests/test_global_search.py tests/test_landscape_v2.py tests/test_synthesis_views.py`
   - `python scripts/validate_records.py`
   - `python scripts/build_static.py`
   - full `python -m pytest -q`
6. Confirm the inherited Hortifrut brief test (`test_brief_review_soon_collapses_reprint_into_review_now_thread`) is either still classified as calendar-sensitive or has been independently repaired on canonical. Do not “fix” it here by widening thread membership.
7. Only then open a PR targeting `v2/intelligence-os`.

## Do not

- Merge or cherry-pick #255 onto this branch before it is canonical.
- Force-push.
- Open a PR while #255 remains the unmerged CI-repair vehicle.
