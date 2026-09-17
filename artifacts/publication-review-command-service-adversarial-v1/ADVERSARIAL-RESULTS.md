# Adversarial Results

All listed cases were mapped to existing command/domain/repository/crash tests. No speculative tests were added for behavior absent from the backend.

| Case | Protection / observed result | Severity |
|---|---|---|
| Double-click approval | durable actor+key receipt replays; one publication | Blocking |
| Retry after timeout | journal reconciliation plus idempotency | Blocking |
| Crash between writes | phase-injection recovery suite | Blocking |
| Two concurrent reviewers | draft lock/CAS; one winner | Blocking |
| Stale browser/version | version and content digest reject | Blocking |
| Wrong expected version | fail closed, no writes | Blocking |
| Missing actor / bot actor | authenticated human permission gate | Blocking |
| Missing reason | command-specific required reason validation | Blocking |
| Invalid transition | explicit transition table | Blocking |
| Duplicate URL / same content, different URL | duplicate eligibility and identity checks | Blocking |
| Superseded draft | terminal/superseded transition isolation | Blocking |
| Body upgrade after metadata review | content digest changes; stale review rejected | Blocking |
| Transcript replacement | provenance/content digest changes; stale review rejected | Blocking |
| Corrupted draft / tampered provenance | recomputation and schema/eligibility checks fail closed | Blocking |
| Publication succeeds but audit fails | journal recovery path | Blocking |
| Audit succeeds but publication fails | journal recovery path | Blocking |
| Evidence job starts early | command writes no Facts or Atomic Evidence; static safety coverage | Blocking |
| Static build sees partial record | atomic writes, static build and link validation pass | Blocking |
