# Regression gate and focused validation

## Luna contract gate

| Run | Result | Tests | Other checks | Duration |
|---|---:|---:|---|---:|
| After Luna, quick | PASS | 244 | Record validation; zero detected record mutations | 111.4s |
| After all sources, quick | PASS | 244 | Record validation; zero detected record mutations | 114.7s |
| Full | PASS | 250 | Record validation, static build, Pagefind; zero detected record mutations | 203.1s |
| Final after focus fix, quick | PASS | 244 | Record validation; zero detected record mutations | 120.0s |

The full gate groups passed: roster/identity 108, Landscape 38, Daily Briefing 23, reader 20, trust 55, and build integrity 6.

## Focused suites

- R1 profile/identity/relationship sweep: **147 passed**, 1 warning.
- Claude acquisition/collection/publication/transcript/reader sweep: **336 passed, 1 inherited failure**. The failure is the pre-existing fixed Source-count assertion in `test_live_source_repository_includes_all_onboarded_sources_generically`; it is also one of the exact unchanged full-suite baseline failures.
- Product Visual System Slice 1 after the verification fix: **9 passed**, 1 warning.
- Record validation: **passed**.
- Build-integrity/static-link suite: **6 passed** inside the full gate.

## Full suite

Final candidate: **2,836 passed, 16 failed, 5 errors**, 3,772 warnings, 483.89s. R1 baseline: **2,823 passed, 16 failed, 5 errors**. Exact node comparison: 21 inherited and unchanged, 0 resolved, 0 newly introduced.

Machine-readable evidence is in `final-quick.json`, `luna-full.json`, `full-suite-comparison.json`, and `combined-current-state.json`; complete logs are retained beside this file.
