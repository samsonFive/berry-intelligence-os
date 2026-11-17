# Wide Portfolio account layouts

The 50-company and full-company Portfolio views previously kept column widths,
order, visibility, sorting and filters only in the browser session when the
matrix exceeded forty columns. They now use the existing private account layout
adapter, so leaving the browser and reopening the same company group restores
those display preferences.

This is a display-preference change. It keeps the existing view namespaces,
semantic hashes, wire schema, account isolation and optimistic revision checks.
An outdated tab receives a conflict and cannot write again until the analyst
explicitly reloads the saved layout. Restoring a layout does not save it, and
layouts for smaller or temporarily absent column groups remain intact.

Only exact existing Portfolio namespaces receive the larger limit:
`berry-portfolio-v1` and `berry-pg-v2-` plus 64 lowercase hex characters. They
support at most 512 columns, including the frozen Cultivar and Pin columns, and
128 KiB per request/response. Other sheets retain their forty-column / 20,000-byte
contract. Filter, sort, width and saved-view count limits are unchanged. Windows
beyond 512 columns retain the bounded session fallback and never truncate the
company matrix.

Local verification covers 50-company and 186-company save/reload with a new
controller, retained absent-column state, full bounded payloads above 20 KB,
concurrent-tab conflicts, real endpoint actor isolation, request limits and
unchanged generic-sheet behavior. Exact-head CI, canonical merge and production
verification remain separate release steps; source implementation is not a live
deployment claim.
