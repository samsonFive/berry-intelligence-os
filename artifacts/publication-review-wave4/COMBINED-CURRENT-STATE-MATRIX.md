# Combined current-state matrix

| Area | Wave 4 state | Production exposure | Evidence |
|---|---|---|---|
| Publication review contract | Final V1 contract and durability addendum integrated. | Documentation governs later production wiring. | `CONTRACT-IMPLEMENTATION-MAP.md` |
| Review state | Durable repository abstraction, versioning, receipts, journal and recovery implemented. | Command-service layer only; no UI/HTTP/CLI adapter. | Focused backend and crash-recovery tests |
| Actor authorization | Structured human actor and permission checks enforced. | Required at command-service boundary. | Authorization/adversarial tests |
| Concurrency | Expected version plus content and provenance digests enforced. | Required at command-service boundary. | Stale/concurrent reviewer tests |
| Provenance binding | Reviewed draft, content, provenance, decision, event and publication are bound. | Cannot be replaced silently during review. | Tamper and upgraded-body tests |
| Idempotency | Durable deterministic receipts support retry after response loss or restart. | Command-service layer only. | Idempotency and restart tests |
| Crash consistency | Recoverable staged journal and visibility commit isolate incomplete transitions. | Readers see a prior or new complete state. | Crash-injection and reader-isolation tests |
| Prohibited effects | Approval cannot create entities, facts, relationships, signals, assessments, recommendations or trusted Atomic Evidence. | Enforced by service and regression tests. | Side-effect proof and mutation snapshot |
| Review queue UI | Private GET-only rehearsal queue and workspaces. | Available only in the private runtime; excluded from static output. | UI tests and browser verification |
| Decision UI | Controls are present for design review but disabled and disconnected. | No mutation request, route, receipt or production adapter. | Route inventory and Playwright request capture |
| AI content | Clearly marked untrusted. | Cannot publish itself or cross the Atomic Evidence gate. | Fixture-state and UI tests |
| Candidate pack | Ten bounded rehearsal items: six corpus-derived and four synthetic. | Test/rehearsal fixtures only; no live records imported. | Candidate-pack artifacts |
| Public static site | 1,665 pages; Pagefind completes. | No review queue, review body, acquired full body, unpublished draft or partial publication emitted. | Static public-safety artifact |
| Today and reader | Wave 3 content-honesty and in-app reader behavior retained. | Production read behavior unchanged. | Regression tests and browser check |
| Roster and profiles | Wave 3 33/33 roster/profile behavior retained. | No canonical entity changes. | Quick/full gates and browser profiles |
| Trust prototype | Remains unable to mutate production. | No production dependency introduced. | Full gate |
| Canonical/live data | No change in entities, facts, relationships, signals, assessments, recommendations, Evidence, configuration or publication data. | Mutation count zero. | `MUTATION-PROOF.md` |

Wave 4 is an integration and validation checkpoint. It deliberately stops before production decision wiring.
