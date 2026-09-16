# Next-agent prompt — TD-THREAD-002 published coverage

You are continuing Berry Intelligence OS work after TD-THREAD-002.

## Frozen / do not touch

- PR #255 `fix/td-108-109-learner-ipm-v1` at `3c585f2` — no commits, no merge, no deploy.
- PRs #253 and #254 — untouched.
- Canonical `v2/intelligence-os` — do not commit to it.

## This branch

- Worktree: `.worktrees/td-thread-002-published-coverage-v1`
- Branch: `feature/td-thread-002-published-coverage-v1`
- Base: `c0de14c88960c22fee97a51fef0c71ffe386bcf9` (`origin/v2/intelligence-os` tip at mission start)
- Pushed, **no PR opened**.

## What already shipped on this branch

Recently published trusted Evidence participates in the live `/threads` candidate universe via `live_thread_candidate_universe()`. Matcher thresholds were not loosened. Overlay reader, Global Search, Landscape, and static build were not given `group_story_threads()`.

Read `artifacts/td-thread-002-published-coverage-v1/` before editing.

## If your mission is rebase / PR

Follow `REBASE-AFTER-255.md`. Do not copy Learner or `/today` clock repairs from #255 onto this branch.

## If your mission is a new TD

Create a **new** worktree from the current `origin/v2/intelligence-os` tip (or from this branch only if the new work depends on published-coverage threads). Do not pile unrelated work onto `feature/td-thread-002-published-coverage-v1`.
