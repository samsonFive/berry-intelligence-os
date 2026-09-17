# PROTOTYPE-TO-PRODUCTION-MAP

Maps approved prototype patterns into production Slice 1 without wholesale copy.

| Prototype (`prototypes/publication-review-workflow-v1`) | Production Slice 1 |
| --- | --- |
| Static `index.html` shell | FastAPI template `publication_review_readonly.html` extending `base.html` |
| In-memory JS store + decisions | Server-rendered read model; decisions disconnected |
| `tokens.css` copy | Shared `app/static/pvs_tokens.css` + scoped `publication_review_readonly.css` |
| Fixture JSON as “live” demo data | Durable inbox drafts when present; else honest empty. Rehearsal JSON only under `tests/fixtures/` (+ env-gated verification) |
| Approve/reject/defer/correction dialogs with receipts | Disabled buttons + explicit `decisions_enabled: false` copy; no dialogs that fake saves |
| Filters all/readable/transcript/limited/problem | Same filter IDs via query `?filter=` |
| j/k keyboard queue nav | Retained (navigates to detail URLs) |
| Warn vs block badge copy | Retained in template warn/block lists |
| Trust: approve ≠ Evidence | Retained; Atomic Evidence called out as separate gate |
| Bulk approval absent | Retained (`bulk_approval_available: false`) |
| Private prototype note | Private `/review-ops/publications` under existing ops conventions; `data-pagefind-ignore`; not in static builder |

## Intentionally not migrated

- Client-side idempotency / success receipts (would masquerade as saved decisions)
- Prototype-only reset demo control
- Standalone rail navigation (uses production V2 shell)
- Any POST decision handlers
