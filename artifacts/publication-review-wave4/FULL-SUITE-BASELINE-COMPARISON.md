# Full-suite baseline comparison

| Measure | Wave 3 baseline | Wave 4 |
|---|---:|---:|
| Passed | 2,836 | 3,024 |
| Failed | 16 | 16 |
| Errors | 5 | 5 |
| Skipped | not baseline criterion | 9 intentional |
| Exact nonpassing node IDs | 21 | 21 |
| Newly introduced | — | **0** |
| Resolved | — | 0 |
| Inherited unchanged | — | 21 |

The 188 additional passing tests come from the publication contract, backend, adversarial, rehearsal and read-only UI coverage. Mechanical comparison against `artifacts/competitor-intelligence-wave3/full-suite-comparison.json` found the exact same 16 failed and five errored node IDs.

The inherited debt remains in export orphan fixtures, fixed-count source/relationship assertions, and superseded Today/front-page/navigation expectations. It is not attributed to Wave 4.

Machine-readable evidence: `full-suite-comparison.json`; complete output: `full-suite.txt`.
