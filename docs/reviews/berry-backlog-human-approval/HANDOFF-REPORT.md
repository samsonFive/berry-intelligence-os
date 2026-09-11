# Berry backlog human-approval handoff

## Dataset actually reviewed

| Field | Value |
|---|---|
| Repo | `github.com/samsonFive/berry-intelligence-os` |
| Branch / commit | working tree on `cursor/berry-backlog-review-workbook-d16f` |
| Dataset | Checked-in `data/evidence/*.json` with `auto_captured=true` |
| Rows reviewed | **1139** |
| Not reviewed | Runtime `inbox/` queues (absent in this checkout) |

### Important status nuance

These 1139 rows already have `validated=true` from the **2026-08-06 validate/purge spreadsheet** (1139 keep / 446 purge). That pass was a coarse keep/delete screen.

They are **still commercially unreviewed**: every row’s `priority.*.rationale` still says *“not yet reviewed”*, and `why_it_matters` is empty. This workbook is that commercial batch review for offline approval while Astra repairs the app.

Historical file `review/review-backlog-2026-08-06.xlsx` was **not** re-used as the open backlog; prior `validate` decisions are preserved in `prior_human_decision` / `current_status`. `final_decision` is left blank for you.

## Queue inventory (kept distinct)

| Queue | Present? | Count | Notes |
|---|---|---|---|
| Legacy unvalidated / commercial evidence review | Yes | **1139** | Checked-in auto-captured corpus |
| Pending publication | No | 0 | No `inbox/` in this checkout |
| Source-fidelity / content-recovery queue | No | 0 | No fidelity artifacts here; recovery **recommendations** still appear as actions on thin snippets |
| Atomic / claim review | No | 0 | Approving a source here does **not** approve claims or create facts |

## Recommendation totals

| recommended_action | Count | Meaning |
|---|---|---|
| validate | 608 | Confirm keep as Evidence/source |
| reject_as_source | 175 | Recommend drop; **not** executable purge |
| needs_content_recovery | 95 | Likely relevant; recover body before trusting content |
| hold | 261 | Human judgment needed |
| **final_decision** | **all blank** | For your approval |

### Proposed batches

| Batch | Rows | Suggested action |
|---|---|---|
| B01_genetics_ip_varieties | 25 | validate |
| B02_trade_export_supply | 279 | validate |
| B03_company_maa_investment | 28 | validate |
| B04_production_agronomy | 81 | validate |
| B05_litigation_regulation | 24 | validate |
| B06_trade_press_general | 171 | validate |
| B07_consumer_fluff_reject | 15 | reject_as_source |
| B08_offtopic_produce_reject | 159 | reject_as_source |
| B09_false_match_reject | 1 | reject_as_source |
| B10_content_recovery | 95 | needs_content_recovery |
| B11_likely_duplicates | 5 | hold |
| B12_borderline_hold | 256 | hold |

Exceptions tab: **249** rows (thin content, duplicates, uncertain dates/identity, unresolved Google News wrappers, etc.).

## Decision mapping for the primary agent

| Workbook action | App transition |
|---|---|
| `validate` | `scripts/apply_review_decisions.py` → `validate` (confirm keep). No facts/claims/extraction. |
| `reject_as_source` | Recommendation only. Map to legacy `purge` **only** after explicit human confirmation. Do **not** auto-emit `purge` / `purge+block`. |
| `needs_content_recovery` | Not validate/purge. Route to content recovery / source-fidelity. Missing body ≠ automatic reject. |
| `hold` / blank `final_decision` | Leave untouched. |

Hard rule: source approval ≠ claim approval ≠ fact creation ≠ extraction authorization.

## How to use

1. Open `berry-backlog-review.xlsx`.
2. Start with **Batches** (filter Review by `proposed_batch`).
3. Skim **Exceptions** separately.
4. Enter `final_decision` only where you agree (or override).
5. Return the workbook + JSON to the primary coding agent for safe, queue-scoped apply.

## Limitations

- Judged from **title + stored snippet** only (almost all `source_url`s are Google News wrappers).
- Public pages were not opened for every row; uncertain cases are `hold` or `needs_content_recovery`.
- Company/geography columns only show linked entity IDs already on the record (often empty) — no inferred relationships.
- Publication / fidelity / atomic runtime queues were unavailable here; if production has additional pending rows, export those separately and merge.

## Deliverables

- `berry-backlog-review.xlsx`
- `berry-backlog-review.json`
- `build_workbook.py` (regenerator)
- this report
