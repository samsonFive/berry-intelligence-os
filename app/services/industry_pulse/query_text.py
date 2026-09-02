"""Date-window and query-text translation for non-Google providers.

Google News RSS keeps `when:7d` in the query string. Other providers use
their documented date filters instead of that Google-only syntax.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from app.services.industry_pulse.matrix import WINDOW_DAYS, PulseQuery

_GOOGLE_WHEN = re.compile(r"\s+when:\d+d\s*$")

GEO_ISO = {
    "americas": "US",
    "europe": "GB",
    "africa": "ZA",
    "apac": "AU",
    "global": None,
}

PERPLEXITY_RECENCY = {"24h": "day", "7d": "week"}
FIRECRAWL_TBS = {"24h": "qdr:d", "7d": "qdr:w"}


def semantic_query_text(query: PulseQuery) -> str:
    """Strip Google News `when:` so other providers see the same semantics."""
    return _GOOGLE_WHEN.sub("", query.text).strip()


def date_window_of(query: PulseQuery) -> str:
    if query.date_window in WINDOW_DAYS:
        return query.date_window
    for window in ("24h", "3d", "7d", "30d"):
        if query.id.endswith(f":{window}"):
            return window
    match = re.search(r"when:(\d+d)\s*$", query.text)
    if match and match.group(1) == "1d":
        return "24h"
    if match and match.group(1) == "3d":
        return "3d"
    if match and match.group(1) == "7d":
        return "7d"
    if match and match.group(1) == "30d":
        return "30d"
    return "7d"


def window_start(window: str, *, today: date) -> date:
    days = WINDOW_DAYS.get(window) or 7
    return today - timedelta(days=days)


def perplexity_date_kwargs(window: str, *, today: date) -> dict[str, str]:
    recency = PERPLEXITY_RECENCY.get(window)
    if recency:
        return {"search_recency_filter": recency}
    start = window_start(window, today=today)
    return {"search_after_date_filter": start.strftime("%m/%d/%Y")}


def firecrawl_tbs(window: str, *, today: date) -> str:
    if window in FIRECRAWL_TBS:
        return FIRECRAWL_TBS[window]
    start = window_start(window, today=today)
    return f"cdr:1,cd_min:{start.strftime('%m/%d/%Y')},cd_max:{today.strftime('%m/%d/%Y')}"


def exa_start_published(window: str, *, today: date) -> str:
    return window_start(window, today=today).isoformat() + "T00:00:00.000Z"


def iso_country(geography: str) -> str | None:
    return GEO_ISO.get(geography)
