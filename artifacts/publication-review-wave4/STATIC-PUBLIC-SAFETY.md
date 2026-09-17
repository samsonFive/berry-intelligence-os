# Static and public safety

- Full deterministic gate: PASS.
- Static build: **1,665 pages**, matching the Wave 3 expected count.
- Pagefind: completed.
- Record validation: passed.
- `canonical_or_runtime_mutation`: false.
- No private review queue/index route was generated.
- No rehearsal draft ID, private review content, full acquired body or `/review-ops/publications` route appears in generated text/index inputs.
- No unpublished draft leakage was detected by the builder.
- Staged/incomplete promotion records are excluded by command-service visibility rules and focused static-safety tests.
- The read-only queue has `data-pagefind-ignore` and is not registered in `build_static.py`.

Evidence: `full-gate.json`, `browser-results.json`, and the focused static-safety tests.
