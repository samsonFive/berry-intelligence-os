"""Suite defaults. /today must not poll live lanes during unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stub_feed_first_live_http(monkeypatch, request):
    if request.node.get_closest_marker("live_today"):
        return
    from app.services import feed_first_live

    monkeypatch.setattr(
        feed_first_live,
        "live_feed_bundle",
        lambda **kwargs: {
            "today": "2026-09-21",
            "fetched_at": "2026-09-21T12:00:00+00:00",
            "lanes": ["google_news_rss", "specialist_rss", "perplexity"],
            "lane_errors": [],
            "stats": {
                "same_day": 0,
                "discovered": 0,
                "qualified": 0,
                "dropped_not_today": 0,
                "dropped_undated": 0,
                "dropped_unqualified": 0,
            },
            "records": [],
        },
    )
