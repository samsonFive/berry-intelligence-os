# Clock contract

Module: `app/services/clock.py`

| Function | Contract |
|---|---|
| `utc_now()` | Current UTC-aware instant. **The only wall-clock seam tests should freeze.** |
| `as_utc(dt)` | Naive → assume UTC (`replace(tzinfo=UTC)`). Aware → `astimezone(UTC)`. Never call `.astimezone()` on a naive value (that would use the local zone). |
| `resolve_now(now=None)` | `None` → `utc_now()`. Otherwise `as_utc(now)`. |
| `utc_today(now=None)` | `resolve_now(now).date()` |

## `now=None`

Means “use the injectable current UTC instant,” not “undefined” and not “local midnight.” Callers that pass `now=None` (including GET `/today`) go through the same seam as an omitted argument.

## Production defaults

Unchanged: live requests still see the real current UTC time. Windows stay:

- Front Page / Today recency bands: 24h / 3 / 7 / **14 days inclusive** (`recency_band`, `days <= 14`).
- Pending triage Review now vs older backlog: **45 days inclusive** (`calendar_age <= 45`).

## Wired call sites

- `app.services.front_page.build_front_page`
- `app.services.today.build_today`
- `app.services.morning_brief.build_morning_brief` (`today` / `frontier_date` fallback)
- `app.services.morning_brief.pending_freshness_telemetry`

`morning_brief._now()` still stamps `last_seen_at` with naive `datetime.now()` when `mark_seen=True`. That is persistence of an analyst action, not a recency window, and is left alone.

Naive vs aware: matches `chronology.parse_stamp` (naive = UTC).
