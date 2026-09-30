# PR title

Add Global Intelligence Explorer with evidence-backed Market Snapshots

# PR description

Users can now select multiple countries on a real boundary map, combine that
scope with a berry, investigate the resulting published intelligence in the
existing Reader, and compose/export a source-traceable Market Snapshot. Peru +
Chile + China + Blueberry remains one structured query through the explorer,
report composition, PDF export and return navigation.

## Architecture

Reuse the existing FastAPI/Jinja shell, canonical Evidence/Entity/Relationship
repositories, geography containment, intelligence cards, Reader and ReportLab
exporter. The immutable IntelligenceQuery composes country OR + commodity AND
before presentation. Explicit canonical descendants are included; titles,
company HQ, AI suggestions, ancestors and unpublished records are not inferred
into scope. Countries without a canonical record retain an ISO boundary
selector and honestly resolve to unavailable coverage.

The report uses the existing report/packet/coverage contract. Sections carry
citation IDs and the appendix retains original source URLs, reader links and
publication dates. The same query and provenance-bearing GeographicLayer
contract can support future overlays, retrieval/RAG interfaces and slide exports
without binding retrieval to the SVG map. This PR introduces no RAG or AI service.

## Product behavior

- Locally bundled real country boundaries; hover/focus previews, multi-select,
  keyboard/touch selection, chips, Clear All, zoom/pan and country-search fallback.
- All Berries, Strawberry, Blueberry, Raspberry and Blackberry filters.
- Automatic query updates and 48-record feed pagination using existing cards.
- Shared Reader bindings refresh after result replacement.
- Report inherits geography/berry/evidence and allows overview, developments,
  company activity and variety activity sections to be included/excluded.
- PDF export reuses the existing renderer, with optional source-URL provenance.
- Desktop, tablet and mobile layouts; explicit missing-data/map-failure states.
- Navigation entrypoints in current live shells; no private explorer links in
  public static output.

## Security and rollout

Published public evidence only; no inbox/private data, new model dependency,
external map service, analytics or data upload. Remote session protection applies
to HTML and PDF routes. No trusted-record/schema changes, migration, configuration
or new dependencies. Deployment is the normal code deployment; do not copy or
replace operator runtime data. Natural Earth/datasets boundary attribution is
bundled with the local asset.

## Validation

- Full clean canonical run: 3,327 passed, 9 skipped, one pre-existing War Room
  clock failure. The same failure was reproduced on untouched canonical 916b8f0.
  This PR fixes the one-line clock handoff: overlap retrieval now consumes the
  session's already-supplied date. The former failure and a stale-move exclusion
  regression pass; no trust/date-window behavior is weakened.
- Final focused query/Reader/report/War Room run: 90 passed.
- Static/private-state leakage fixtures: 16 passed.
- Canonical record validation: passed; no canonical data changes.
- Static build: 1,751 pages; no unpublished draft IDs/titles in public output.
- Browser acceptance: passed at desktop 1440px, tablet 820px and mobile 390px,
  including map keyboard/touch multi-select, composed berry query, shared Reader,
  report inheritance/section changes/PDF download/return, empty ISO-country scope,
  no horizontal overflow and map-load failure fallback; no browser errors.
- Python compilation and git diff whitespace checks: passed.
- No separate lint/type-check command is configured in this repository.
- GitHub current-head required checks must pass before merge. Final CI status is
  reported on the PR; local checks do not bypass that gate.

Reproduce with `python -m pytest`, `python scripts/validate_records.py`,
`python scripts/build_static.py`, and the opt-in
`python scripts/verify_global_explorer_browser.py` against localhost:18321.

## Screenshots

![Desktop explorer](https://raw.githubusercontent.com/samsonFive/berry-intelligence-os/feature/global-intelligence-explorer-pr/artifacts/global-explorer/desktop.png)
![Mobile explorer](https://raw.githubusercontent.com/samsonFive/berry-intelligence-os/feature/global-intelligence-explorer-pr/artifacts/global-explorer/mobile.png)
![Market Snapshot composition](https://raw.githubusercontent.com/samsonFive/berry-intelligence-os/feature/global-intelligence-explorer-pr/artifacts/global-explorer/snapshot.png)

## Deliberate limits

Coverage depends on canonical geography/berry tags; counts are platform evidence
coverage, not production scale, source independence or exhaustive recall.
Quantitative production/growing-region/seasonality layers and PowerPoint export
are deferred behind the query/layer/report contracts. Snapshots are deterministic
source inventories requiring analyst interpretation. URL composition re-resolves
current published records; PDF is the archival artifact. Boundaries without a
reliable ISO identity remain preview-only. No source/domain expansion is claimed.

## Key files

`app/services/global_explorer.py`, the three explorer routes in `app/main.py`,
`global_explorer.html` / `global_snapshot.html`, map CSS/JS/local GeoJSON,
shared Reader binding in `app/static/v2.js`, existing report PDF exporter,
live navigation templates, query/provenance/security tests, and the opt-in
browser acceptance script. Details: `docs/v2/GLOBAL-INTELLIGENCE-EXPLORER.md`.


### Design and review scope
Explorer and snapshots now use the newer navy/blue shell, compact spacing, distinct Reader typography and multi-select berries. Trusted includes only sources supporting active canonical facts; Unreviewed includes published raw news and existing cached feed records, with source preview images and the existing thumbs-up/down workflow. Thumbs up prepares candidates and requires human confirmation. Snapshots always use Trusted scope.

The separate site-wide design sprint is scoped in `docs/v2/SITE-WIDE-DESIGN-SPRINT.md`, including typography hierarchy and density across all pages.
