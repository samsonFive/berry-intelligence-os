# Fix mapping

| Failure | Production change | Test change |
|---|---|---|
| `/today` route 14-day drift | `build_front_page` / `build_today` use `resolve_now(now)` | `test_today_route_front_page_and_mobile_css` freezes `utc_now` to existing `NOW` (2026-08-24). Fixture date unchanged. |
| Front-page route smoke | same | `test_front_page_route_smoke` freezes `utc_now` to existing `NOW` (2026-09-01). Fixtures stay `2026-08-31`. |
| Perplexity `now=None` | `resolve_now(None)` → `utc_now()` instead of a second `datetime.now(UTC)` | Freeze `utc_now` to 2026-09-01. **Keep `now=None`** so the None path is what is proven. |
| Hortifrut 45-day briefing | `build_morning_brief(..., now=)` + `utc_today(now)` instead of `date.today()` | Freeze clock to 2026-08-06. Hortifrut stays `2026-07-30`. Mexico conference fixture is `2026-08-06` (was `_today()`, which was a second wall-clock). |

## Boundary tests added

- `tests/test_clock.py` — None / naive / aware / repeat / 14-day inside-cutoff-outside / UTC rollover / `now=None` equals explicit frozen instant
- `tests/test_story_threads.py` — Hortifrut on day 45 stays Review now; day 46 is older backlog

## Explicitly not changed

- `app/services/story_threads.py` matcher
- Learner / PR #255 files
- Canonical `data/` records
- Freshness window numbers (14, 45)
- Perplexity providers / network
- GET `/today` product ranking
