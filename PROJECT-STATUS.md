# Project Status

## Current checkpoint — October 9, 2026

The approved Glasshouse redesign and section consolidation were integrated in
[PR #312](https://github.com/samsonFive/berry-intelligence-os/pull/312).
The visual explainer of site sections, analyst workflow and reporting is at
`/guide`. Later Landscape and catalog improvements remain draft work; no merge
or deployment is included in the current mission phase.

The [durable requirements checklist](docs/v2/REDESIGN-REQUIREMENTS-CHECKLIST.md)
retains all 31 accepted requirements, their evidence and remaining work. Start
there rather than reconstructing the mission from historical progress reports.

## Outstanding work

| Area | Current state | Next action |
|---|---|---|
| Variety coverage | CAT-01/CAT-02/TD-116 open; source discovery and review handoffs work, but complete portfolios, corpus, rights and independent recall remain incomplete | Continue acquisition/reconciliation; retain every missing-source and identity gap; obtain actual human decisions through existing review |
| Blueberry Landscape | Dense revised checkpoint and visual guide available; user feedback pending | Obtain blueberry feedback before remaining-berry rollout; finish and verify the full retained brief |
| Integrated release | Post-redesign improvements form an unmerged draft stack | Reconcile canonical, test/browser-review the combined release and prepare backup/rollback proof before requesting merge/deploy approval |

## Latest reviewable changes

- [Draft #377](https://github.com/samsonFive/berry-intelligence-os/pull/377):
  explicit article/profile name detection; all required checks pass.
- [Draft #378](https://github.com/samsonFive/berry-intelligence-os/pull/378):
  audit explicitly supplied Article text against separate expected names;
  all required checks pass (4,553 passed / 11 skipped / two warnings).
- [Draft #379](https://github.com/samsonFive/berry-intelligence-os/pull/379):
  eight attributed UF cultivar photo references using the existing session-only
  permission-held preview; all required checks pass (4,553 passed / 11 skipped /
  two warnings).
- [Draft #381](https://github.com/samsonFive/berry-intelligence-os/pull/381),
  [profile-field coverage review](docs/v2/VARIETY-PROFILE-FIELD-COVERAGE-REVIEW.md):
  a dense per-variety inventory with gap filters, protected photo edits and cited
  trait/role/reference counts. All four CI checks pass (4,563 passed / 11 skipped /
  two warnings). Actual desktop review is
  complete. Phone visual verification remains before the combined release.
- [Variety workflow explainer](docs/v2/VARIETY-WORKFLOW-EXPLAINER-REVIEW.md):
  the guide now traces source names through identity review, separate catalog
  authoring and profile enrichment, with links to the existing private workflows.

The [latest bounded audit](docs/v2/SUNBELLE-ORIGINAL-VARIETY-SOURCES-REVIEW.md) has
366 source sections / 1,142 name occurrences / 72 matched occurrences / 1,070
requiring review, with 789 public derived candidate keys and 64 unchanged
canonical varieties. There are 122 photo references; the eight UF photos have unknown
reuse permission and remain excluded from public static output. Source mentions
are not approved varieties or a global completeness measure.

The 32 captured copies remain pending source review. The independent expected-name
packet is unfinished and has no human recall score. Preserve original data,
user edits, original URLs and source/identity/claim/extraction/photo gates.

[Full prior status history](PROJECT-STATUS-HISTORY.md) retains the original
status document verbatim, including dated production proof and decisions.
Historical deployments and CI runs are not current release approval.
