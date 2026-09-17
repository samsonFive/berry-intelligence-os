# Contract implementation map

| Contract requirement | Combined implementation | Verification |
|---|---|---|
| Durable review state | `publication_review_repository.py` uses runtime-resolved `review_state/`; the local inbox is not the authoritative store. | Restart/new-checkout repository tests. |
| Authorized human actor | Structured actor type and publication-review permission checks. | Missing, AI, bot, service and unauthorized actor tests. |
| Optimistic concurrency | Expected version, content digest and provenance digest validation. | Stale version/digest/provenance and concurrent-reviewer tests. |
| Immutable binding | Draft/version/content/provenance bind the decision, event and publication. | Tamper and upgraded-body tests. |
| Idempotent retry | Durable receipts and deterministic identity. | Duplicate click, response-loss and process-restart tests. |
| Crash recovery | Staged journal, visibility commit and reconciliation. | Ten crash-injection tests plus Luna adversarial cases. |
| Complete-state isolation | Readers see only committed publications; staged state is excluded. | Reader-isolation and static-safety tests. |
| Prohibited side effects | Approval never calls legacy `ReviewPublishService.publish()` and writes no Entity, Fact, Relationship, Signal, Assessment, Recommendation or Atomic Evidence. | Direct monkeypatch and directory snapshot proofs. |
| Human publication gate | Command service requires one authorized human decision. | Domain/command tests. |
| Separate Atomic gate | Approval creates a `publication_artifact` with empty fact/relationship IDs. | Prohibited-side-effect tests. |
| Read-only UI | GET-only queue/workspace; decision controls disabled; no mutation route. | UI route inventory, Playwright request capture and disabled-control checks. |
| Private/static boundary | Review routes are not built or indexed; fixtures remain under tests. | Static build, leak scans and Pagefind completion. |

The backend service exists in Wave 4 but no production HTTP/CLI/UI mutation adapter is connected. The legacy mutation route remains separate and was not redesigned in this integration.
