# TEST-RESULTS — Publication Review read-only UI v1

## Focused suite

```
tests/test_publication_review_readonly_ui.py
25 passed
```

Coverage includes: ten rehearsal states, decisions_enabled false, body-free queue,
warn vs block, disabled controls, no mutation routes, private/static boundary,
Today/reader PVS CSS untouched, `/guide` leak check, honest empty state.

## Regression suite (this slice)

```
tests/test_publication_review_readonly_ui.py
tests/test_review_operations.py
tests/test_today.py
tests/test_ui_v2_shell.py
tests/test_build_static.py
59 passed
```

## Static / Pagefind safety

- `scripts/build_static.py` does not reference `/review-ops/publications` or `publication_review_readonly`
- Template uses `data-pagefind-ignore` on private root/panels
- Rehearsal fixtures live only under `tests/fixtures/`
- No new public sidebar link for the queue

## Mutation status

- No POST/PUT/PATCH/DELETE routes under `/review-ops/publications*`
- UI decision buttons `disabled` + `data-enabled="false"`
- Capability banner states decision service is not connected

## Browser

See `BROWSER-VERIFICATION.md` and screenshots/video in this directory.
