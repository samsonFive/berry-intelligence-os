# Integration usage

After each Wave 2 cherry-pick, run quick mode first. Run full mode before
handing the integration branch to review or CI. Use the JSON report for an
auditable command, pass/fail, test-count, duration, and mutation record.

```text
python scripts/wave2_contract_gate.py --mode quick
python scripts/wave2_contract_gate.py --mode full
```

The gate is deterministic and offline: it uses committed records and pytest
fixtures only. It does not discover, download, call a model, publish, or
change trusted records. Static build output under ignored `generated/` is an
expected disposable side effect; any `data/` or `inbox/` change fails the run.

If a failure is pre-existing on the integration base, record it separately in
`BASELINE-RESULTS.md`; do not weaken the contract or classify a skipped command
as a pass.
