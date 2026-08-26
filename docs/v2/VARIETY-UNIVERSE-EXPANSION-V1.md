# Variety Universe Expansion V1

**Mission:** Global Variety Universe Expansion V1 (2026-08-26). Public-data
comprehensiveness of the Variety *universe*, not a Variety-profile redesign.

Canonical at start of this mission: **64** variety entities (62 production + 2
example fixtures). Blueberry 41 / raspberry 12 / strawberry 6 / blackberry 5.
That list is not representative of public cultivar disclosure in EU, UK, or
South Africa.

## What this mission added

- Inbox-only Variety candidates (`inbox/variety_candidates/`)
- Deterministic identity resolution: exact name/alias/code/registration →
  POSSIBLE ALIAS; token overlap → UNKNOWN; no match → DISTINCT.
  **CONFIRMED SAME is never automatic.**
- Structured registry import (no HTML scraping in templates/routes)
- Live coverage matrix (`/varieties/coverage`) with raw counts
- Authoring identity review (`/varieties/candidates`)
- EU/UK/South Africa pilot fixture under `data/imports/variety-universe-eu-uk-sa-v1/`

## Trust

Candidates never write `data/entities`, Facts, or Relationships.
GET/render does not mark identity decisions.
Static generation does not include candidate names.

## Pilot sources

| Geography | Source class | How used |
|---|---|---|
| EU | CPVO public register API (existing `source-cpvo-public-register`) | Bounded denomination queries; live hits stored as structured rows |
| UK | Plant Varieties and Seeds Gazette / APHA (`source-uk-pvro-seeds-gazette`) | Official collection URL; no gazette PDF scrape |
| South Africa | DALRRD PBR office (`source-za-pbr-dalrrd`) | Deployment-class candidates; no invented grant numbers |
