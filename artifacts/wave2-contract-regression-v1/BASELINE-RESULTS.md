# Baseline and gate results

Validation target: `85a157233674ee5cd3d2e358ea02924d3ac04790` on
`integration/competitor-intelligence-wave2`.

## Full gate

Command:

```text
python scripts/wave2_contract_gate.py --mode full --report artifacts/wave2-contract-regression-v1/full-report.json
```

Result: **PASS**. Eight command groups completed in 332.2 seconds; 250
focused pytest tests passed. Record validation passed. Static build passed and
Pagefind completed. No `data/` or live `inbox/` mutation was detected by the
successful run.

| Contract group | Result | Tests | Duration |
|---|---:|---:|---:|
| Roster and identity | PASS | 108 | 36.015s |
| Landscape | PASS | 38 | 48.716s |
| Daily Briefing | PASS | 23 | 16.693s |
| Reader | PASS | 20 | 9.127s |
| Trust | PASS | 55 | 75.589s |
| Build integrity | PASS | 6 | 21.935s |
| Record validation | PASS | 0 | 4.031s |
| Static build and Pagefind | PASS | 0 | 89.333s |

## Quick gate

Command:

```text
python scripts/wave2_contract_gate.py --mode quick --report artifacts/wave2-contract-regression-v1/quick-report.json
```

Result: **PASS**. Six command groups completed in 287.3 seconds; 244 focused
pytest tests passed and record validation passed.

## Pre-existing/environment failures

No repository test failure remained after the validation environment was
prepared. Initial attempts were blocked by missing local dependencies
(`pytest`, `jsonschema`, `httpx`, `trafilatura`, `reportlab`) and a protected
default pytest temp/cache location under Python 3.14. Those are environment
conditions, not newly introduced failures. The gate now uses a disposable
workspace-local temp directory, disables pytest cache writes, and isolates the
runtime inbox for every subprocess.

The full report JSON is the detailed evidence for commands, return codes,
test counts, durations, output tails, Pagefind status, and mutation checks.
