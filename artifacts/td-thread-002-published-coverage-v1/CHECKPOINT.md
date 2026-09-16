# TD-THREAD-002 checkpoint

## Branch discipline

| Field | Value |
|---|---|
| Isolated worktree | `C:\Users\Johnny\Downloads\sscanar\berry-intelligence-os\.worktrees\td-thread-002-published-coverage-v1` |
| Base remote tip | `origin/v2/intelligence-os` |
| **Exact full base SHA** | `c0de14c88960c22fee97a51fef0c71ffe386bcf9` |
| Feature branch | `feature/td-thread-002-published-coverage-v1` |
| Based on PR #255? | No |
| Based on competitor-intelligence / publication-review branches? | No |
| PR #255 | Frozen at `fix/td-108-109-learner-ipm-v1` `3c585f2`. Untouched. |
| PRs #253 / #254 | Untouched |

## Product decision

Recently published trusted Evidence now participates in the live `/threads` candidate universe. Matcher membership rules are unchanged.

## Files touched (implementation)

- `app/services/story_threads.py` — `live_thread_candidate_universe()` and recency helpers; matcher predicates untouched
- `app/main.py` — `_live_story_thread_universe()` shared by `/threads/{id}` and `/intelligence/{id}`
- `tests/test_story_threads.py` — deterministic universe, matcher non-regression, route, and static-safety cases
- `docs/v2/TECHNICAL-DEBT-REGISTER.md` — TD-THREAD-002 marked resolved on this unmerged branch

## Non-goals honored

No Learner changes. No competitor-intelligence work. No publication-review workflow work. No source collection changes. No new trust actions. No PR opened. No merge. No deployment.
