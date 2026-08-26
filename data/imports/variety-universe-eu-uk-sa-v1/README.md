# Variety Universe Expansion V1 — EU / UK / South Africa import fixture

This directory is **not** trusted canonical data.

`registry_rows.json` holds structured public-source rows for the bounded
Variety Universe Expansion V1 pilot:

- EU: live CPVO public-register hits from a bounded denomination query
- UK: official Seeds Gazette collection URL (no PDF scrape, no invented national IDs)
- South Africa: deployment-class candidates citing DALRRD, not invented PBR grant numbers

Import:

    python scripts/import_variety_universe_pilot.py

Writes `inbox/variety_candidates/` only. Identity review is human-gated.
GET/render never promotes a candidate to `data/entities/varieties/`.
