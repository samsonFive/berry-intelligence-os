# Landscape feature contract

`LandscapePage.tsx` exports default and named `LandscapePage` for the shell's
`Landscape` feature slot. It uses the shared investigation provider and bounded
read APIs; it does not create another router, cache client, detail host or store.
`features/grids/BerryDataGrid.tsx` is the actual AG Grid Community portfolio
matrix. `features/demo/SensoryDemo.tsx` loads only the separate synthetic API.

Standing scope read models use explicit module cache keys. Scope inputs include
berry, countries, geographic basis, actor roles and relationship filters. The
base Landscape intentionally clears focus, comparison cohorts, detail path,
publication dates, query and save references: these do not alter standing
relationships. Developments keys preserve publication dates and source geography
selectors, then use comparison cohort or explicit in-scope focus according to
the agreed precedence. Comparison keys include both typed cohorts and the active
comparison kind. These are immutable read models; their captured request revision
is provenance. They never dispatch context. TanStack Query supplies abort signals;
new scope/subject keys do not show previous-scope placeholder data. Same-scope
cached records survive unrelated Reader/detail revisions.

Connection bands display only actual stored directed edges. Portrait program
edges are displayed with their true endpoints; a company-to-program link is not
invented. Recorded geographic activity and material caveats remain visible.
Source-named cultivars retain an explicit unassigned-role label. Company and
cultivar pin controls are separate from entity focus.

Grid row IDs are canonical cultivar IDs. Stable semantic column IDs are
`cultivar.identity`, `cultivar.comparison-pin`, and
`company.<canonical-id>.recorded-role`. Filtering is explicitly loaded-row only.
Rows/cells are read-only; cell relationship buttons open shared detail. No
Enterprise feature or independent business-selection state is used. Account
layout save/migration integration remains a separate owner-coordinated step;
the feature does not overwrite existing layout rows or serialize raw GridState.

The early sensory state declares synthetic namespace/metric and a visible 1–9
axis. Its specimen checkboxes are local demo state, independent of real company
and cultivar cohorts. It does not attach synthetic scores to canonical IDs or
write any data. It requires the dedicated authenticated demo endpoint.

Implementation source does not establish G1 or V1. Actual package compilation,
populated screenshots, keyboard/touch/focus restoration, continuous recording,
layout persistence, and real SDK/provider acceptance remain to be verified.
