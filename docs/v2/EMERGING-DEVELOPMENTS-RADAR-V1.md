"""Emerging Developments Radar V1.

Stakeholder surface: /radar
Read seam: developments_for(...) in app/services/emerging_radar/research_desk.py

LIVE / UNREVIEWED DEVELOPMENT is not trusted Evidence. Radar never writes
Evidence, Signals, or Assessments. Watchlist matches emit inbox events for a
future alerter; this mission does not send email or Slack.

Retrieval (from the live provider bake-off, not a new vendor evaluation):

- REQUEST-TIME CORE: Google News RSS (8 theme queries), specialist RSS,
  Exa semantic radar (12 probes, not the Pulse 32).
- OPTIONAL: Perplexity, 3 catch-net themes when ENABLE_PERPLEXITY_PULSE is set.
- NOT REQUEST-TIME: APITube, live CatchAll submit.

/radar serves inbox/operations/radar/cache.json when fresh (1h TTL).
scripts/emerging_radar_refresh.py refreshes that cache in the background.

Tag provenance and the Inka Ica defect: see
`docs/v2/RADAR-DATA-QUALITY-AND-SCOPE-TAG-AUDIT-V1.md`.
Direct geography is event location (country noun or closed place alias).
"A Spanish firm" is nationality provenance, not Spain as the event geography.
"""
