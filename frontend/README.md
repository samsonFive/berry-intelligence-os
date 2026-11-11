# Berry investigation frontend

One React root serves `/app/landscape`, `/app/briefing`, `/app/workspaces`, and
`/app/learn`. FastAPI serves the generated `app/static/investigation/index.html`
for these private routes. Existing application routes remain available.

The persistent root owns React Router, one private QueryClient, and the
investigation provider. Feature components consume `useInvestigation()` and the
versioned read APIs. They do not write browser history or initialize legacy
Reader/table controllers. `ExperienceApp` accepts zero-prop feature slots:
`Landscape`, `Briefing`, `Workspaces`, `Learn`, optional `Detail`, and optional
`Command`. One detail allocation is shared across all native routes.

Use Node 24 or later and pnpm 11.25.0. Exact package versions were checked against
the public npm registry on November 11, 2026. The committed lockfile comes from a
real dependency installation. TypeScript and Vite have built the populated
Landscape/detail slice; SDK/provider and whole-app acceptance remain separate.

```powershell
pnpm install --frozen-lockfile --ignore-scripts
pnpm test
pnpm typecheck
pnpm build
```

The state/API contract tests can run immediately without installed packages:

```powershell
node --test tests/*.test.mjs
```

The project uses a local `.pnpm-store` and rejects implicit dependency installation
when running scripts. In a restricted Windows shell, installed tools can also be
invoked directly with `node node_modules/typescript/bin/tsc --noEmit` and
`node node_modules/vite/bin/vite.js build`.

Vite emits browser assets under `/static/investigation/`. Its local development
server binds loopback and proxies APIs to `127.0.0.1:18000`; ordinary verified
local review should use FastAPI serving the built application and its existing
session login. No credentials, source bodies, or authored documents belong in
bundles, URL selectors, or model context.

Canonical berry IDs and bare canonical focus IDs are serialized explicitly.
Company and variety cohorts remain independent and preserve overflow IDs for
visible resolution. Invalid selector text remains visible with blocking issues;
consumers use `hasBlockingIssues()` before querying. Opening source detail never
changes focus. `expectedRevision` rejects late model actions, and the API client
rejects mismatched response revisions. API requests use same-origin credentials
and disable HTTP caching. The private query cache clears on session transition,
logout, or browser back-cache restoration.

Native surfaces call `useSurfaceReady(ready)` from `src/app/SurfaceScroll.tsx`
once their data DOM or final empty/error view is committed. The shell restores
window scroll after that signal and layout, retaining exact Back/Forward entry
positions and per-surface return positions across reloads. Its bounded session
memory stores only native surface names, opaque history keys and numeric
coordinates; session transition/logout clears it with the private query cache.
Detail/Reader pane positions remain owned by `DetailHost`.

Source detail references optionally end in `@brief`; bare references select
Article (`@article` normalizes to bare). `setDetailSection` pushes the active
source section into the shared URL, so nested source return, reload and sharing
preserve it. `demo_specimens` stores only synthetic `demo-specimen-*` IDs;
`setDemoCohort` changes that cohort independently of real company/variety pins.
Empty means all fixture specimens; the demo UI keeps at least one selected
specimen and diagnoses unknown fixture IDs without converting them into real
intelligence. Native Learn concept/lesson paths also preserve the global query.

Offline SDK regressions use the existing Python, Playwright and Chromium
installations. From the repository root:

```powershell
node frontend/e2e/copilot-offline.mjs
node frontend/e2e/copilot-fullstack-offline.mjs
```

Their file headers document executable/module/port overrides. The joined test
uses a real authenticated FastAPI gateway and Node runtime, dummy credentials,
and a locally intercepted provider stream. External provider access is blocked.
Only allowlisted tool/lookup/terminal receipts are retained. This verifies SDK
transport, catalog metadata and shared actions; it never substitutes for a real
approved provider command. The diagnostic leakage tests run in `pnpm test`.
