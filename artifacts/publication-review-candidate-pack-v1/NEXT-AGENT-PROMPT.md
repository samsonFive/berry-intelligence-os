# Continue Berry Intelligence OS work — operator-safe review/promotion workflow

Work in a fresh isolated worktree from wherever this branch
(`research/publication-review-candidate-pack-v1`) or its integrated
successor lands. Read
`artifacts/publication-review-candidate-pack-v1/INVENTORY.md`,
`REHEARSAL-PACK-INDEX.md`, `ITEM-DECISION-MATRIX.md`,
`PROVENANCE-GAPS.md`, and `DUPLICATE-RISKS.md` first.

## Settled facts — do not re-derive

1. There is no persistent, committed publication-review backlog to
   inventory directly — `inbox/` is gitignored and does not exist in a
   fresh worktree. This mission's real counts come from one bounded,
   documented discovery + acquisition run (`--max-total 20`), not from
   any pre-existing state.
2. The acquisition pipeline works and correctly classifies content —
   confirmed again in this mission (2 independent Oishii items,
   identical `navigation_only_shell`; 1 real Fruitist/UF `empty_body`
   case each). Do not re-diagnose this or alter extraction code because
   some publisher pages lack body text.
3. The trusted corpus predates the pipeline; no readable draft has ever
   crossed mandatory human review. This remains the real explanation for
   "zero readable bodies in the trusted corpus," carried forward from
   `readable-acquisition-canary-v1` and the Wave 3 integration checkpoint.
4. This mission's own 10-item rehearsal pack
   (`data/imports/publication-review-rehearsal-2026-09-16/`) is
   noncanonical, review-required, and proven (by a committed, passing
   test suite) unreachable by any repository loader or record validator.
   Reuse it for future review-UI rehearsal or training rather than
   building a new one from scratch.

## Open items for a future mission (per Wave 3's own recommendation)

1. **Build an operator-safe review and promotion workflow** — the Wave 3
   checkpoint's own stated next step. This mission did not touch the
   review UI (`app/main.py`'s `/review/*` routes) or promotion logic at
   all, per its own non-goals. A future mission should design how an
   operator would actually work through a backlog shaped like this
   mission's inventory (mostly navigation-only-shells and metadata-only
   items, occasional duplicates, rare readable/transcript items) without
   ever bulk-approving or bypassing the human gate.
2. **Duplicate-match visibility gap** (`DUPLICATE-RISKS.md` §1, §4): a
   real `possible_evidence_matches` signal currently only reaches the
   discovery-staging JSON, never the review UI, and only if the matched
   item happens to also be selected for acquisition. Surfacing this in
   `/review` itself (read-only, informational) would close a real gap.
3. **Discovery-level failure visibility gap** (`PROVENANCE-GAPS.md` §4):
   Source Health's acquisition-outcome summary has no signal for a feed
   that 404s at the discovery step (confirmed live: two YouTube sources
   today). A separate discovery-health indicator, distinct from the
   existing acquisition-outcome ledger, would close this.
4. **"El Niño" reporting discrepancy** (`PROVENANCE-GAPS.md` §1): a
   `run_recent_batch.py`-reported `awaiting_publication_review` item with
   no corresponding draft file. Worth a focused look at
   `media_orchestration.py`'s draft-write path under same-source,
   same-batch processing of two items — not investigated further here
   (out of this mission's inventory-only scope).
5. Re-run `scripts/_gen_publication_review_rehearsal_pack_v1.py` any time
   a fresh rehearsal pack is needed — it is deterministic and idempotent,
   and its five real items already stay fixed (they were reproduced from
   this mission's own run, not re-fetched live).

## Runtime / housekeeping

Use `../berry-intelligence-os/.venv/Scripts/python.exe`. Git needs
`-c safe.directory=<worktree path>` per command. The bounded inventory run
used `scripts/run_recent_batch.py` (existing, unmodified) with explicit
`--max-per-source`/`--max-total`/`--max-tier` flags — reuse that pattern
rather than an uncapped `--all` discovery pass for any future inventory.
