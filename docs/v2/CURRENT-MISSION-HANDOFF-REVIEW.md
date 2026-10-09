# Current mission handoff and preserved requirements

The current work and review gates were buried beneath hundreds of dated progress
updates. The status and requirements documents now lead with the remaining work,
the evidence required to finish it and the decisions still reserved for a human.
The prior updates remain in linked history files; no requirement or decision was
discarded.

Review branch: `feature/current-mission-handoff`, stacked on photo draft #379.

## Where to continue

- [Project Status](../../PROJECT-STATUS.md) gives the current checkpoint, latest
  reviewable drafts and outstanding catalog, Landscape and release work.
- [Requirements checklist](REDESIGN-REQUIREMENTS-CHECKLIST.md) retains all **31
  requirement IDs and every original table row**. CAT-01, CAT-02, LAND-02 and
  REL-01 are surfaced before the full table with their next action and evidence.
- [Catalog mission](VARIETY-CATALOG-COMPREHENSIVENESS-MISSION.md) retains its
  original acquisition, reconciliation and completion scope.
- [Coverage matrix](INTELLIGENCE-COVERAGE-MATRIX.md) separates the current bounded
  variety follow-up from the established, dated evidence-class matrix.
- [Debt register](TECHNICAL-DEBT-REGISTER.md) retains every active, resolved and
  intentional-limitation row; TD-116 remains open.

The visual explainer remains available at `/guide`. This documentation change
does not replace it, change app routes or claim new production verification.

## Preservation verification

Compared against parent head `b6b9e86389fea2ad6c24609fe487e4945eb0697b`, the
requirements table and implementation sequence, catalog mission core, coverage
matrix core and debt register core remain exact text matches. Each removed
introductory update is preserved exactly in a sibling history file, keeping its
relative link base. The full prior Project Status is preserved verbatim in
[Project Status history](../../PROJECT-STATUS-HISTORY.md).

| Document | Before | Current | Preserved core SHA-256 |
|---|---:|---:|---|
| Requirements checklist | 1,135 lines | 238 lines | `f2ae35bbcda8810081d803c5c7254e76bc249e81e69df37ffd6ee3130feb3b09` |
| Catalog mission | 885 lines | 171 lines | `188149ed3e97ec9dc1f736107da7461303c2aba774f777ecdfd5bf3820947d4c` |
| Coverage matrix | 1,612 lines | 677 lines | `92528e0d499ab2571b2c7923fadb7bed23cec0dbb941c742908c3d75dae5d7c1` |
| Debt register | 2,941 lines | 2,696 lines | `8379d4da8ee825786d2031c506a4f471e1558cf50a86f5137daada6c897ab176` |
| Project Status | 1,421 lines | 48 lines | Full original is archived; SHA-256 `38dbbf471398fcf2397babc3009bac1a3fd5da935a2b99e60f318b1e324bd693` |

Verification compares the text rather than relying on line counts. All 31
requirement IDs remain in their original order, with unchanged table rows. New
overview links resolve to existing files. No canonical data, operator edit,
source-copy body, review decision, app code, governance guide or visual-guide
content changed. A documentation-only update needs preservation/link review and
its required CI, not another app browser session or duplicated application tests.

Historical source counts, CI results and deployments remain dated history. They
do not approve the current stack. The 32-copy source/name packet stays unfinished;
catalog completeness, independent recall and current rights remain open.
Blueberry feedback still gates the remaining Landscape rollout. Integration and
release verification remain required; no merge, deployment or goal completion.
