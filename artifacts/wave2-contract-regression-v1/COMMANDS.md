# Commands

From the repository root:

```text
python scripts/wave2_contract_gate.py --mode quick --report artifacts/wave2-contract-regression-v1/quick-report.json
python scripts/wave2_contract_gate.py --mode full --report artifacts/wave2-contract-regression-v1/full-report.json
```

Install the repository development requirements and Pagefind before full mode:

```text
python -m pip install -r requirements-dev.txt
python -m pip install pagefind pagefind_bin
```

The gate stops at the first failure, prints the failing command and output
tail, counts tests from pytest summaries, and detects changes under `data/`
and `inbox/` after every command.
