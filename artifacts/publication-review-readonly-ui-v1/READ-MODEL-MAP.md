# READ-MODEL-MAP

Aligned to `artifacts/publication-review-contract-v1/UI-DATA-CONTRACT.md` (contract branch).

## Queue projection (body-free)

| Contract field | Production key |
| --- | --- |
| draft ID | `draft_id` |
| title | `title` |
| source name / id | `source_name`, `source_id` |
| publication / capture dates | `publication_date`, `captured_at`, `discovered_at` |
| review state / version / updated | `review_state`, `version`, `updated_at` |
| content class / readable flag | `content_class`, `readable_content` |
| acquisition outcome | `acquisition_outcome` |
| blocker / warning codes | `blocking_warnings`, `provenance_warnings`, counts |
| duplicate state | `duplicate` |
| linked entities | `entity_match` |
| priority / attention | `needs_attention_rank`, `attention_reasons` |
| permitted commands | always `[]` in Slice 1 |
| Slice capability | `decisions_enabled: false` |

Queue items never include `body_text`, transcripts, or review comments.

## Detail projection

Adds: `source_url`, body/transcript/limited explanation, provenance chain, digests (`review_content_digest`, `provenance_digest`), review history, trust-band labels, AI enrichment (labeled untrusted), disabled `decision_controls`.

## Sources

1. **Durable** — `pending_publication_drafts()` publication artifacts from inbox.
2. **Rehearsal** — only when durable queue is empty **and** `BIOS_PUBLICATION_REVIEW_REHEARSAL_UI=1`.
3. **Empty** — honest empty message; no invented backlog.

Adapter: `app/services/publication_review_readonly.py`.
