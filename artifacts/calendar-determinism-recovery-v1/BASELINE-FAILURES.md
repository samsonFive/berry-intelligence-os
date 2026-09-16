# Baseline failures on untouched `c0de14c`

Exact base SHA: `c0de14c88960c22fee97a51fef0c71ffe386bcf9`  
Worktree: `.worktrees/calendar-determinism-recovery-v1`  
Reproduced 2026-09-16 before any edit: **FFFF** (4 failed, 0 passed) on the four named tests.

| # | Test | Assertion | Root cause |
|---|---|---|---|
| 1 | `tests/test_today.py::test_today_route_front_page_and_mobile_css` | `'REVIEWED EVIDENCE' in page.text` | GET `/today` calls `build_front_page(now=None)` → `datetime.now(UTC)`. Fixture published `2026-08-24` is 23 days before 2026-09-16, outside the 14-day `recency_band`. Service-level tests in the same file already freeze `now=NOW` (2026-08-24); the route test did not. **Stale route clock, not a product-policy defect.** |
| 2 | `tests/test_intelligence_front_page_v1.py::test_front_page_route_smoke` | `'FRESH / UNREVIEWED' in page.text` | Same route wall-clock. Fixtures dated `2026-08-31` (16 days before 2026-09-16). `_base_kwargs()` already passes `now=NOW` (2026-09-01) for service tests; the smoke route did not. **Stale route clock.** |
| 3 | `tests/test_perplexity_semantic_pulse_v1.py::test_front_page_publication_classification_is_provider_agnostic` | `matches` is empty | Explicit `now=None` meant “use wall clock” via `now or datetime.now(UTC)`. Draft `captured_date=2026-09-01` is 15 days before 2026-09-16 (`days <= 14` is inclusive, 15 is out). **`now=None` drifted to the current calendar.** No Perplexity network path involved. |
| 4 | `tests/test_story_threads.py::test_brief_review_soon_collapses_reprint_into_review_now_thread` | `review_now["count"] >= 1` | `build_morning_brief` used `date.today()` for `calendar_age`. Hortifrut fixtures `2026-07-30` are 48 days old on 2026-09-16; pending triage sends `calendar_age > 45` to `older_backlog`. Matcher unchanged. **Stale briefing clock.** |

## Not these

- Thread membership predicates (`items_form_thread`) were not the failure.
- 14-day and 45-day **windows** were behaving as specified.
- PR #255 repaired some of these by sliding fixture dates to `date.today()`. That approach is rejected here: fixtures stay, the clock is injected.
