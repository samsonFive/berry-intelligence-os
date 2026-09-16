# Checkpoint

## Frozen peers (untouched)

| Branch | HEAD |
|---|---|
| `feature/td-thread-002-published-coverage-v1` | `1b01aab6b8bf69714a831fa5406c88a0d745a724` |
| PR #255 `fix/td-108-109-learner-ipm-v1` | `3c585f2` (not used as a base or cherry-pick) |

## This mission

| Field | Value |
|---|---|
| Worktree | `.worktrees/calendar-determinism-recovery-v1` |
| Branch | `fix/calendar-determinism-recovery-v1` |
| Base | `c0de14c88960c22fee97a51fef0c71ffe386bcf9` |
| Kind | Determinism repair, not a feature |

## Production files

- `app/services/clock.py` (new)
- `app/services/front_page.py`
- `app/services/today.py`
- `app/services/morning_brief.py`

## Test files

- `tests/clock_helpers.py` (new)
- `tests/test_clock.py` (new)
- `tests/test_today.py`
- `tests/test_intelligence_front_page_v1.py`
- `tests/test_perplexity_semantic_pulse_v1.py`
- `tests/test_story_threads.py` (clock freeze + 45-day bounds only; matcher untouched)

No PR, merge, or deployment.
