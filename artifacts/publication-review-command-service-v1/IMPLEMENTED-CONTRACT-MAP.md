# Implemented contract map

Maps `design/publication-review-contract-v1` (`4c126a6e15d448c4be2f0dae73ddce879fbc0346`)
to what this mission actually built. The contract is authoritative; every
conflict or partial implementation is documented explicitly rather than
silently narrowed.

## Slices implemented

| Slice | Contract scope | Status | Where |
|---|---|---|---|
| 1 | Pure domain contract | **Implemented** | `app/services/publication_review_domain.py` |
| 2 | Review repository and recovery primitives | **Implemented** (filesystem-backed, no external infra) | `app/services/publication_review_repository.py` |
| 3 | Boundary-safe command service | **Implemented** | `app/services/publication_review_command.py` |
| 4 | Compatibility adapters (route HTML actions through the command service) | **Not implemented** — explicit non-goal ("No production mutation route exposed to users") | — |
| 5 | Trust and static projections | **Partially proven, not built** — a static-safety test proves no leak, but `scripts/build_static.py`/Today/reports were not modified to consume a new trust projection (none was needed: they already read only `data/evidence` with `status=published`, which this service already respects) | `tests/test_publication_review_static_safety.py` |
| 6 | Operator UI | **Not implemented** — explicit non-goal | — |
| 7 | Post-approval corrections/withdrawal | **Not implemented** — requires product authorization the mission brief does not grant; pre-approval correction (`request_publication_correction`/`submit_publication_correction`, both `pending_review`-side) IS implemented as part of Slice 3 | `app/services/publication_review_command.py` |

## Domain vocabulary reused vs. invented

| Concept | Source | Reused verbatim? |
|---|---|---|
| Content classification (`FULL_ARTICLE`/`FULL_TRANSCRIPT`/`STRUCTURED_REGISTRY`/`THIN_DESCRIPTION`/`NO_CONTENT`, failure categories, retryability) | `app.services.source_completeness.source_completeness()` | Yes, called directly |
| Body state (`body_available`/`body_partial`/`transcript_available`/`description_only`/`access_limited`/`body_unavailable`/`interstitial`) | `app.services.source_body.classify_source_body()` | Yes, called directly |
| Deterministic publication identity / duplicate detection (normalized canonical URL; else exact normalized title + source + date; no fuzzy match) | `app.services.article_dedup.normalize_canonical_url/normalize_title/find_duplicate_article` | Yes, called directly |
| Atomic file writes (temp file + `os.replace`) | `app.services.draft_delivery.atomic_write_json` | Yes, called directly (never reimplemented) |
| Append-only audit event ledger, with existing `idempotency_key`/`expected_version`/`state_version`/`source_surface` fields already on the schema | `app.services.review_events.append_review_event/load_review_events/remove_created_event` | Yes, called directly — the real, shared `inbox/review_events/` ledger, workflow tagged `publication_review_command_v1` to stay distinct from the legacy `publication_review` workflow's own events |
| Trusted-publication compatibility profile (`evidence_role=publication_artifact`, `status=published`, `fact_ids: []`, `relationship_ids: []`) | `PUBLICATION-REVIEW-CONTRACT-V1.md`'s own storage profile | New assembly, but written through the existing `evidence.schema.json`/`data/evidence/` compatibility store, never a new schema |
| Runtime directory resolution (`BIOS_RUNTIME_DIR` persistent-mount pattern) | `app.runtime_config.resolve_data_dir/resolve_inbox_dir` | Pattern followed exactly (`resolve_review_state_dir`), not literally called (a new, parallel directory: `review_state/`, distinct from `data/`/`inbox/`) |

New vocabulary this mission introduces, because nothing existing represents it: `INTEGRITY_STATES`-equivalent review states (`pending_review`/`correction_required`/`deferred`/`approved`/`rejected`/`superseded_duplicate`), the command names, the blocker/warning codes, and the `DraftState`/journal-phase shapes. All are named directly after the contract's own vocabulary (`STATE-MACHINE.md`, `COMMAND-CONTRACTS.md`), not invented independently.

## Documented conflicts / gaps found, not silently resolved

1. **`classify_source_body()`'s `access_limited` state only checks
   `discovery_provenance.failure_category`; real acquisition output
   stores `acquisition_failure_category` instead** (confirmed:
   `source_completeness()` itself checks both keys; `classify_source_body()`
   does not). This makes `access_limited` effectively unreachable for real
   drafts. **Not fixed** — `source_body.py` is a production file outside
   this mission's scope, and the contract's own instruction is "do not
   alter extraction code merely because some publisher pages lack body
   text," which extends here to not patching unrelated classification
   code as a side effect of building this service. `check_eligibility()`
   instead reads `source_completeness()`'s own already-correct
   `retryable`/`failure_category` fields directly for the
   retryable-vs-blocked distinction, documented in a code comment at the
   exact point of use (`publication_review_domain.py`).
2. **The command envelope does not carry a separate "reviewed provenance
   digest" field** (`COMMAND-CONTRACTS.md`'s own envelope only names
   `reviewed_content_digest`). This mission still implements a distinct
   provenance-digest *integrity* check (`_load_and_validate` recomputes
   `compute_provenance_digest(state.draft)` and compares it to the stored
   `provenance_digest`, failing closed on mismatch) to satisfy
   "changed-provenance rejection" — this catches provenance drift from
   *outside* the normal revise path (a tampered store, an inconsistent
   import) rather than requiring the caller to submit a second digest the
   contract's own envelope does not define.
3. **No separate canonical Publication schema was introduced** (per the
   contract's own decision log: "Is a second canonical Publication schema
   required for V1? No.") — the strict profile is written through the
   existing `evidence.schema.json`/`EvidenceRepository`-compatible
   `data/evidence/` folder, exactly as required.
4. **Slice 5's full scope (Today/reports/company coverage consuming a
   "strict trust/content projection")** was not built — out of scope for
   this mission (no production route/UI changes), and not required for
   this service's own safety: static-safety tests confirm no leak exists
   today with the current, unmodified `build_static.py`.

## Files this mission adds (all new; none of the following existing files were modified beyond `.gitignore`)

- `app/services/publication_review_domain.py`
- `app/services/publication_review_repository.py`
- `app/services/publication_review_command.py`
- `app/services/publication_review_migration.py`
- `tests/test_publication_review_domain.py`
- `tests/test_publication_review_repository.py`
- `tests/test_publication_review_command.py`
- `tests/test_publication_review_crash_recovery.py`
- `tests/test_publication_review_migration.py`
- `tests/test_publication_review_static_safety.py`
- `.gitignore` (added `review_state/`, the local-development default
  runtime directory, alongside the existing `inbox/` entry)
