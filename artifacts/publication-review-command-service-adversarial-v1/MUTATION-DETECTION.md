# Mutation Detection

`validate_records.py` and `build_static.py` were run against the checkout with before/after recursive SHA-256 digests for `data/` and `inbox/`. Both digests were unchanged. Validation passed, static build passed, Pagefind completed, and 1,665 pages were generated.

The validator-owned tests independently compare isolated review/data/inbox digests around rejected actor and stale-review commands. No network, live model, canonical write, or generated-data import was used.
