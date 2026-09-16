# State visibility

How this read model handles honest-but-awkward states: missing/stale
references, interrupted transactions, superseded duplicates, and legacy
imports. The unifying rule: **a reader is told exactly what the durable
repository currently proves, and nothing more.**

## Missing or stale referenced state

`get_detail()` accepts an optional `evidence_reader` port. When provided,
a draft's `publication_binding` (present once approved) is checked
against it:

| `publication_binding` | `evidence_reader` given? | `publication_verified` |
|---|---|---|
| `None` (never approved) | — | `None` (not applicable) |
| Present, evidence file exists | Yes | `True` |
| Present, evidence file missing/deleted | Yes | `False` |
| Present | No | `None` (unknown — never assumed true or false) |

The binding itself is **always** reported as stored — this module never
hides a stale reference, and never fabricates verification when it wasn't
asked to check. Proven by
`test_publication_binding_referencing_a_deleted_evidence_file_is_reported_unverified`
(a real evidence file is deleted out-of-band, and the read model correctly
reports `publication_verified: False` while still surfacing the binding)
and `test_detail_without_an_evidence_reader_reports_verification_as_unknown_not_false`.

## Interrupted transaction visibility

`promotion_status()` reads `DurableReviewRepository.pending_transactions()`
and `journal_phases_present()` directly — the same primitives
`PublicationReviewCommandService.reconcile_pending_transactions()` uses
for actual recovery. A draft with an in-flight, uncommitted approval
transaction is reported as:

```python
{
    "has_pending_transaction": True,
    "pending_transactions": [
        {"transaction_id": "...", "phases_present": [...], "resumable": True, "committed": False}
    ],
}
```

**Never** `"approved"`. `DraftState.state` itself is read as-is — this
module adds no inference layer that would flip it based on journal
contents. `test_interrupted_transaction_is_visible_but_never_reported_as_approved`
injects a real crash (a monkeypatched `append_review_event` that raises
after the real evidence file has already been atomically written, but
before the audit event and the draft's own compare-and-set to `approved`)
and confirms: the draft's `review_state` still reads `pending_review`, its
`publication_binding` is still `None`, and `promotion_status` honestly
reports the real, resumable, uncommitted transaction underneath. This is
the literal, concrete case the mission's "never treats staged/uncommitted
transactions as committed" requirement names.

## Superseded duplicates

A `superseded_duplicate` draft's detail view includes a `supersession`
dict (`{survivor_id, identity_basis}`), parsed from the terminal decision
event's own `reason_category` encoding
(`supersede_publication_duplicate`'s `"survivor=<id>:<basis>"` string —
see `CONTRACT-MAPPING.md`). Any other state's `supersession` is `None` —
this field is never populated speculatively.

## Legacy/imported records

`is_legacy_import()` is a best-effort heuristic: a record whose inner
`draft` payload still carries the exact inbox-shaped fields
(`record_type: "evidence"`, `status: "draft"`, `review_state: "in_review"`)
**and** has an empty `decision_history` is flagged `is_legacy_import: True`.
The moment any real decision is applied to it, the flag clears — an
imported-then-reviewed record is just a normal reviewed record with
imported provenance, not a permanently "legacy" one. Tested directly:
`test_imported_legacy_draft_is_readable_and_flagged`,
`test_legacy_draft_stops_being_flagged_once_it_has_a_real_decision`,
`test_natively_seeded_draft_is_not_flagged_as_legacy_import` (a
false-positive check — a normal record with the same inner shape by
coincidence would still be flagged, but a record that has been decided
never stays flagged).

## Missing draft entirely

`get_detail()` returns `None` for an unknown id — not an error, not an
empty-but-present dict. `list_queue()`/`status_summary()` simply reflect
zero rows for an empty store. No tombstone concept exists in this module;
whether an id "never existed" vs. "existed and was purged" is not a
distinction this read model makes (the durable repository itself keeps no
delete-tombstone either, per its own design in
`publication_review_repository.py`).
