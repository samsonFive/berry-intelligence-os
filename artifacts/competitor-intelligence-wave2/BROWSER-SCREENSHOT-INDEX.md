# Browser screenshot index

All checks ran at 1440×1000 in Chromium. Production checks used the clean integrated worktree on port 8022. Every page returned HTTP 200 with no console errors.

| Check | Screenshot | Result |
|---|---|---|
| Canonical competitor landscape | `screenshots/competitor-landscape.png` | 33 entries, California Giant present, coverage states separated. |
| California Giant selected detail | `screenshots/california-giant-detail.png` | Official source blocked and no current usable coverage are explicit. |
| Daily Intelligence Briefing | `screenshots/daily-briefing.png` | Production `/today` loads and exposes Needs Attention honestly. |
| Readable article reader | `screenshots/readable-reader-isolated-fixture.png` | A temporary external-to-repo fixture proves acquired text opens in-app and retains Read original as secondary navigation. The real published corpus has zero readable bodies, so this check used an isolated data copy and did not mutate repository/application data. |
| Limited-content reader | `screenshots/limited-reader.png` | The reader labels limited source content and provides Read original. |
| Company/entity handoff | `screenshots/company-entity-handoff.png` | California Giant resolves to its canonical company page. |
| Source Health | `screenshots/source-health.png` | Discovery execution and article-body acquisition are visibly separate. |

Machine-readable results: `browser-checks.json`.

