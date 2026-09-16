# Validation results

Target: `c95c05e51b8247a0b22f417a877088c8d7f20e6b`.

| Command | Result | Count | Duration | Mutation result |
|---|---:|---:|---:|---|
| `python -m pytest -q -p no:cacheprovider` focused publication/review/trust/acquisition list | PASS | 70 | 27.14s | `data/` and live `inbox/` unchanged |
| `python scripts/validate_records.py` | PASS | N/A | 5.451s | no canonical/live mutation |
| `python scripts/wave2_contract_gate.py --mode quick` | PASS | 244 pytest tests | 537.6s total | isolated inbox / mutation detection |

The focused suite covered publication review, trusted-publication duplicate
handling, review events, AI enrichment, Atomic Evidence, trust feedback,
acquisition, source fidelity, review operations, and media evidence. No
network-dependent test was added and no live review action was performed.

The Wave 2 gate is composed rather than copied; its own reports remain the
source for the broader roster/landscape/brief/reader/build counts.
