# Contract Coverage

| Contract | Current executable coverage | Result |
|---|---|---|
| Durable state and restart | domain/repository/command suites; validator replay-after-reconstruction | PASS |
| Human actor authorization | command suite; validator missing/AI/service mutation test | PASS |
| Optimistic version/content/provenance checks | command and crash suites; validator stale digest test | PASS |
| Idempotency and duplicate publication | repository/command/crash suites; validator replay test | PASS |
| Immutable draft/provenance binding | command and crash suites | PASS |
| Approval side-effect boundary | static safety suite; validator zero-trusted-side-effect test | PASS |
| Content eligibility and honest states | domain/command suites | PASS |
| Crash recovery and complete-state isolation | crash recovery suite across documented journal phases | PASS |
| Valid state transitions and audit history | domain/command/repository suites | PASS |
| Offline no-mutation validation | record/build digest check; validator tmp-path snapshots | PASS |
