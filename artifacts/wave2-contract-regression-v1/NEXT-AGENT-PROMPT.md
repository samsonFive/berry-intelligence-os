# Next-agent prompt

Run `python scripts/wave2_contract_gate.py --mode full` after every cherry-pick.
If it fails, report the exact contract group, command, pytest count, duration,
output tail, and whether `data/` or `inbox/` changed. Separate failures that
also reproduce on exact base `85a157233674ee5cd3d2e358ea02924d3ac04790` from
new failures. Do not edit canonical records, import generated/live content,
or bypass the static Pagefind check.
