# Full-suite comparison with Wave 2 R1

| Measure | R1 baseline | Final Wave 3 candidate |
|---|---:|---:|
| Passed | 2,823 | 2,836 |
| Failed | 16 | 16 |
| Errors | 5 | 5 |
| Exact nonpassing node IDs | 21 | 21 |
| Newly introduced | — | **0** |
| Resolved | — | 0 |
| Inherited and unchanged | — | **21** |

The comparison is mechanical and uses exact `FAILED`/`ERROR` node IDs from `artifacts/competitor-intelligence-wave2-r1/full-suite.txt` and `full-suite-final.txt`. All 21 identities match. The 13 additional passing tests come from the integrated checkpoints and bounded focus regression coverage.

The inherited debt remains in older export fixtures, fixed-count Source/domain assertions, and superseded Today/front-page/navigation expectations. It is not attributed to Wave 3, but should be repaired in a separate bounded compatibility cleanup.

See `full-suite-comparison.json` for the complete classified node list.
