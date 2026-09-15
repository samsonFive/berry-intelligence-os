# Competitor Intelligence V1 integration checkpoint

Date: 2026-09-15

Branch: `integration/competitor-intelligence-v1`
Base: `bd96fca1231dc97ae4ec3fc316743b0a3f2e8427`
Integration reconciliation commit:
`ea6bc2ddb3f7eeba4940a695e00166c3e6f6b495`

## Integrated checkpoints

The exact source commits were cherry-picked in the required order and kept as
separate commits. There were no textual conflicts:

| Owner | Source SHA | Integrated SHA |
|---|---|---|
| Claude registry | `4e54401da040be937cc68877f410b4da7b646d65` | `9e2dcce5434cede3d6e86cddb6d3bea5b508f66f` |
| Sol acquisition code | `3fcfba8d6feb4218b2a5e9f6f0608dc6fe66b9d7` | `2848d193ce6389c7b9d500f8cbd7aaeb3b3cd8da` |
| Sol acquisition artifacts | `792e729df5d9a440df798b4fe55ac5e363963412` | `6d3ff8038ad60dd5a97c2ac8d9a1a9dc510df772` |
| Grok landscape UI | `d44e3e3d753e4f796151e75c6747214b92c8232e` | `d36f6785afbbb2785a3915c312dda45d87a71b14` |

## Reconciliation result

- Production `/competitors` now consumes Claude's latest 33-row canonical
  reconciliation. Grok's fixture requires an explicit test-only path.
- Spreadsheet labels and frozen classification remain intact. Names, aliases,
  entity types, review state, and profile routes resolve through the current
  entity repository.
- Ozblu remains `brand-ozblu`; UC Davis remains
  `breeding_program-uc-davis-strawberry`.
- Monitoring is presented as five separate live facts: entity represented,
  discovery configured, discovery operational, readable body acquired, and
  current usable coverage.
- California Giant renders all simultaneous states honestly and requests a
  manual or compliant alternative source. No synthetic outcome was created.
- The three disputed relationship assertions display as Pending review. The 19
  withheld handwritten rows remain in Claude's ambiguity queue.
- Source Health's separate discovery and article-body summaries remain intact.

## Current 33-row audit

Snapshot date: 2026-09-15. Coverage window: 90 days.

- 33/33 roster entries resolve to canonical entities.
- 25 are maturity level 1 (entity represented only).
- 8 are maturity level 2 (discovery configured, never successfully run in this runtime).
- 0 have a successful linked discovery run in this worktree.
- 0 have a readable linked acquisition in this worktree.
- 0 have current usable published coverage in this worktree's 90-day audit.

The checked-in Sol 11/33 audit remains a historical pre-Claude snapshot. It was
not overwritten or relabeled as current.

## Runtime and data mutations

No ignored canary runtime was copied or reconstructed. This worktree has no
`inbox/` directory. Therefore the integration imported zero of the 150 staged
discoveries, 5 discovery states, 10 operation items, 5 run records, 5
acquisition outcomes, or the unapproved BerryWorld draft. Git-tracked canonical
entities, provenance records, and pending relationships arrived only through
Claude's preserved commit.

## Validation

- Focused Claude + Sol + Grok + integration tests: 96 passed on Python 3.13.7.
- Record validation: passed.
- Static build: 1,650 pages completed in an isolated temporary output; private
  fixture IDs and imported pending evidence/relationship IDs were absent.
- Browser: seven required desktop/mobile screenshots captured; mobile width had
  no horizontal overflow.
- Full suite: not run. Python 3.12 handoff is ready.

## Remaining issues

- California Giant needs a compliant runnable source or legitimate publisher
  access change before current coverage can improve.
- Twenty-five roster entries have no runnable discovery coverage in this
  worktree; the eight configured entries still need an authorized operational run.
- Seventeen newly represented entities await identity review.
- Three genetics assertions await review; 19 handwritten mappings remain withheld.
- The pre-existing Planasa duplicate-identity concern remains unresolved.
- The default static output directory was locked by Windows during replacement;
  the isolated-output build succeeded and should be repeated by the Python 3.12 runner.

Nothing was pushed, merged, deployed, collected, approved, published, or emailed.

