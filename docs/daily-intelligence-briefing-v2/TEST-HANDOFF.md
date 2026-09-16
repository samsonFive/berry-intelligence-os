# Focused test handoff — Slice 1

Run:

```bash
python -m pytest tests/test_daily_intelligence_briefing_slice1.py -q
python -m pytest tests/test_today.py tests/test_astra_news_reader.py tests/test_competitor_landscape_v1.py -q
```

Covers: fixture isolation, What Changed gate, attention honesty, recency vs capture date, implication discipline, query/reader state, ID validation, landscape handoff, non-company profiles, route rendering.

Full suite: NOT RUN
Live collection: NOT RUN
