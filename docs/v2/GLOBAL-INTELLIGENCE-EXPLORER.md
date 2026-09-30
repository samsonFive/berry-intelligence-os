# Global Intelligence Explorer

## Architecture and implementation

The application is FastAPI + Jinja, with canonical JSON Evidence/Entity/Relationship
repositories, a shared intelligence-card/Reader experience, explicit `part_of`
geography containment, and an existing ReportLab PDF exporter. The explorer
extends these systems; it adds no database, collector, AI gateway, or trust action.

- `/explorer`: locally bundled Natural Earth country boundaries, multi-country
  selection, keyboard/touch controls, zoom/pan, search/list fallback, removable
  chips, berry selection, and automatic scoped results with 48-item pagination.
- `IntelligenceQuery`: immutable canonical geography IDs + commodity ID. Countries
  compose with OR; berry composes with AND. Country scope includes only explicitly
  stored descendant relationships. Matching uses stored tags, never titles, HQ,
  suggested enrichment, or ancestor expansion. Structural citations and unpublished
  Evidence are excluded. Unknown IDs fail explicitly with 422.
- Country previews: real published Evidence, publication dates, berries and
  linked companies. Counts describe platform coverage, never production or recall.
- `/explorer/snapshot`: deterministic report composition inherits the exact query.
  Select overview, recent developments, company activity and variety activity.
  Every populated section retains evidence IDs; source records retain reader URLs,
  original URLs and publication dates. Empty sections explain unavailable coverage.
- `/explorer/snapshot.pdf`: reuses the existing PDF renderer and report/packet/
  coverage contract. Source URLs are now an optional citation-appendix field in
  that renderer. Future slide exporters can consume the same report contract.
- `GeographicLayer` / `GeographicLayerFeature`: future overlays accept the same
  query and expose evidence provenance. No production/seasonality/weather layer
  is synthesized in this feature.
- The existing Reader receives an explicit refresh event after result replacement,
  preserving article navigation after map/berry changes. Map keyboard events stay
  outside the feed's Enter shortcut.

## Data and security boundaries

Published public evidence only. No private drafts, internal imports, generated AI
prose, new remote calls, analytics, credentials, or third-party map tiles. The map
asset is bundled locally with attribution in `app/static/COUNTRY-BOUNDARIES.md`.
All routes inherit the app's remote session boundary. No schema migration,
configuration change, runtime mutation, or deployment is required. The feature is
live-only; navigation links are omitted from public static output.

## Deliberate limits

Country boundaries without a canonical ISO-linked Geography retain an ISO country
selector and show an explicit empty scope. They do not create or guess Entity IDs. Growing-region/production metrics,
seasonality overlays and PowerPoint export remain deferred. Reports are sourced
inventories requiring analyst interpretation, not automatic market assessments.
Snapshots are URL-composed and re-resolved against current published evidence;
the exported PDF is the archival artifact. PDF export may become large for global
scope. Berry/geography tagging gaps remain visible and can exclude relevant items.

## Verification

Run `python -m pytest`, `python scripts/validate_records.py`, and
`python scripts/build_static.py`. The opt-in browser acceptance script is
`python scripts/verify_global_explorer_browser.py` after starting a local server
on `127.0.0.1:18321`. It checks multi-country keyboard selection, blueberry query
composition, shared Reader, report inheritance/composition/PDF download/return,
mobile touch/list controls, tablet width, and map-failure fallback. It writes
screenshots/PDF under `artifacts/global-explorer/`; these are local verification
artifacts, not canonical intelligence.

Final check results and PR body are recorded in `GLOBAL-EXPLORER-PR.md`.

## Existing clock regression resolved

Full-suite validation found a pre-existing War Room overlap failure, reproduced
on untouched canonical 916b8f0: competitive-move retrieval used real wall time
instead of compose_war_room's injected session clock. Passing instant.date() into
the existing today parameter restores consistent time windows and deterministic
replay. Existing overlap coverage and a stale-move exclusion regression pass.
No War Room architecture or trust rules were changed.
