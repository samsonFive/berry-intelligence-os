# Competitor Intelligence canonical adapter contract

The `/competitors` surface reads the latest dated competitor-registry
reconciliation through `unfiltered_competitor_registry()`. Production does not
fall back to `tests/fixtures/competitor_landscape_registry_v1.json`; tests must
opt into that fixture by passing its path explicitly.

Each landscape row keeps the source spreadsheet label and resolves it through
`canonical_entity_id`. Canonical names, aliases, entity type, review state, and
profile route come from the current entity repository. This preserves `Ozblu`
as `brand-ozblu` and `UC Davis` as
`breeding_program-uc-davis-strawberry`; neither is converted into a company.

Classification fields remain the dated internal snapshot:

- `competitor_type`
- `strategic_priority`
- `regions`
- per-berry `berry_tier`

Monitoring is a live, read-only composition over current repositories and the
local runtime. These five facts remain separate:

1. `entity_represented`: canonical entity exists.
2. `discovery_configured`: an explicitly linked Source has a runnable adapter.
3. `discovery_operational`: linked runtime discovery state records a successful run.
4. `readable_content_acquired`: Sol's linked-source ledger records a readable body.
5. `current_coverage_available`: usable published evidence falls inside the 90-day window.

`maturity_level` is the highest consecutive stage reached. It is a coverage
maturity description, never a competitive score. Current coverage uses
`company_news_coverage()` and therefore excludes cookie walls, access screens,
empty shells, and other content that `reader_content()` marks unusable.

California Giant deliberately carries several simultaneous facts: its entity
is represented, the diagnosed official-source access restriction remains
visible, no Source is explicitly linked as runnable, no linked readable-body
outcome exists in this worktree, and no usable current published coverage is
available. The UI asks for manual acquisition or a compliant alternative
source without creating a synthetic acquisition result.

Genetics relationships remain existing graph records. A relationship with
`status: disputed` from the imported handwritten notes is rendered as
`Pending review`; integration does not promote, reject, or rewrite it.
