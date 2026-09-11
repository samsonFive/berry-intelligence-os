# Berry backlog human-approval handoff

**Verdict:** The live article backlog was **not available** in this Cloud Agent checkout, so no article recommendations were produced. Deliverables are a ready-to-use workbook shell (Instructions + empty Review + Batches + Exceptions) plus this export request for the primary agent.

## Dataset actually inspected

| Field | Value |
|---|---|
| Repo | `github.com/samsonFive/berry-intelligence-os` |
| Branch / commit | `master` @ `ec801d538003c93b53679c8bcdcca5b3a3dba505` |
| Local astra-repair path | **Not mounted** (`C:/Users/Johnny/Downloads/sscanar/berry-intelligence-os-astra-repair`) |
| Branch `fix/astra-news-reader` | **Not on origin** |
| `artifacts/astra-repair/REVIEW-STATUS.md` | **Missing** |
| Runtime `inbox/` | **Missing** (gitignored; not present in checkout) |

Checked-in evidence inventory on this commit:

- `data/evidence/`: **1263** published JSON records
- Legacy unvalidated queue (`auto_captured` and not `validated`): **0**
- Historical spreadsheet `review/review-backlog-2026-08-06.xlsx`: **1585** rows, **already fully decided** (1139 `validate` / 446 `purge`) and applied to checked-in data — **not** treated as the current open backlog

## Queue inventory (keep distinct)

| # | Queue | Present here? | Live count | Storage / mechanism |
|---|---|---|---|---|
| 1 | Legacy unvalidated evidence | Yes (empty) | **0** | `data/evidence` + `scripts/export_for_review.py` / `apply_review_decisions.py` |
| 2 | Pending publication / article approval | No | unknown | `inbox/evidence/*.json` drafts → Promote / Reject / Dismiss |
| 3 | Source-fidelity / content-recovery | No | unknown | `inbox/source_fidelity/artifacts/*.json` → `affirmed` / `rejected` / `needs_investigation` |
| 4 | Atomic evidence / factual-claim review | No | unknown | drafts with `evidence_role=atomic_evidence` → approve/reject **separately** from source approval |

**Boundary enforced in Instructions:** approving an article as a source must not approve claims, create facts, or authorize extraction.

## Deliverables in this folder

1. `berry-backlog-review.xlsx` — tabs: Instructions, Review, Batches, Exceptions
2. `berry-backlog-review.json` — matching machine-readable scope + empty `records[]`
3. This report

`final_decision` is blank by design. No executable `purge` / `purge+block` recommendations were written.

## Exports required (precise)

Have the primary coding agent (on the astra-repair / production runtime machine) produce **one combined JSON export** (preferred) or four queue files, without applying decisions:

### A. Legacy unvalidated (if any remain on that machine)

```bash
python scripts/export_for_review.py review/legacy-unvalidated-export.xlsx
```

Also emit JSON lines with at least: `id`, `title`, `source_name`, `source_url`, `published_date`, `captured_date`, `summary`, `auto_captured`, `validated`, berry/company/geo ids, `origin_domain`.

### B. Pending publication drafts

From runtime inbox (do not commit secrets):

- Folder: `$INBOX_DIR/evidence/*.json` where status is not `published`/`rejected`
- Include: `id`, `title`, `source_name`/`publisher`, `source_url`/`canonical_url`, `published_date`, `captured_date`, `summary`, berry/company/geo fields, content completeness / `article` presence flag (not necessarily full body), any existing human decision fields

### C. Source-fidelity / content-recovery

- Folder: `$INBOX_DIR/source_fidelity/artifacts/*.json` with `review.status == pending` (and optionally non-pending for preservation)
- Include: `evidence_id`, `source_title`, `source_url`, `final_url`, `published_date`, `match_class`, `identity_proof`, `artifact_type`, `source_chars`, `review`, trust notices
- Optionally attach thin trusted Evidence metadata for the linked `evidence_id`

### D. Atomic / claim review

- Inbox (and trusted, if in review) records with `evidence_role == "atomic_evidence"` pending review
- Include parent publication id, claim text/summary, links, current status, any existing reviewer decision

### E. Repair context

Upload or push:

- `artifacts/astra-repair/REVIEW-STATUS.md`
- Branch `fix/astra-news-reader` (or the actual repair branch name)

### Preferred package shape

`berry-backlog-live-export.json`:

```json
{
  "exported_at": "ISO-8601",
  "runtime_label": "astra-repair|production|demo",
  "git_commit": "...",
  "queues": {
    "legacy_unvalidated_evidence": [],
    "pending_publication": [],
    "source_fidelity_recovery": [],
    "atomic_evidence_claim": []
  }
}
```

Re-run the backlog review against **that** package only. Do not substitute the 2026-08-06 snapshot.

## How the primary agent should interpret the workbook (once filled)

1. Apply only rows with non-blank `final_decision`.
2. Honor `queue_type` — no cross-queue side effects.
3. Map decisions per the Instructions tab (source promote ≠ fidelity affirm ≠ atomic approve).
4. Preserve IDs/URLs; skip missing ids; report them.
5. Do not run importers, alter blocklists, or invent company/geo/date facts.

## Limitations

- No pending rows were scored for commercial berry relevance.
- No public sources were opened.
- Feature-branch queue semantics were read from origin feature refs for mapping only; app code was not changed.
- Local checked-in records may differ from production; this report labels the inspected dataset explicitly.
