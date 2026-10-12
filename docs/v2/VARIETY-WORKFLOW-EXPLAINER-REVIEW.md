# Make the source-to-variety workflow visible

The visual guide now shows **Read the source → Check the identity → Create the
entry → Build the profile** as four numbered cards. Each step has a concrete
output. It explains why a newly found name reaches review before becoming a
catalog record, and why marking it distinct does not automatically author a
variety, establish company roles or verify traits.

This extends the existing site-section, analyst-workflow and reporting explainer
at `/guide#variety-workflow`. Its eleven section cards, primary analyst workflow,
reporting outputs and separate review lifecycle remain. No new site section or
navigation home is introduced. The new jump link and three authoring-only
handoffs lead to existing profile coverage, candidate review and source authenticity
review. Public snapshots explain the process without exposing private action links.

The cards reuse the established Glasshouse guide layout: distinct headings,
numbered steps, connected columns, compact text and separate output labels.
Original source/identity/statement/photo gates remain intact. No form is submitted
by opening the guide; no source collection, provider call or canonical authoring
is added. Missing article text, current rights and image reuse stay explicit.

## Browser and validation evidence

- Native desktop review verifies the fifth guide section, its four cards and
  links to existing profile coverage, identity review and recovered-source review.
- [Desktop screenshot](../../artifacts/variety-workflow-guide-review-2026-10-09/desktop-workflow.png)
  shows the final hierarchy. A fresh native tab after a 390px viewport override
  still had an actual 1280px viewport. The override was reset and the temporary
  tab closed. **Phone visual verification remains open**; no desktop screenshot
  is presented as mobile evidence.
- **47 existing workflow/authoring-handoff tests pass**, one existing ReportLab
  warning, 54.86 seconds. The 1,755-page public static/Pagefind build passes and
  excludes unpublished drafts. Generated guide markup includes the explanatory
  section and live-workspace availability text without its three private links.
- The current requirements preamble is corrected to the same 366 sections /
  1,142 occurrences / 72 matches / 1,070 review needs / 789 public derived keys
  already recorded in the CAT-02 row and source audit. All 31 requirement IDs and
  their order remain. No new coverage, source acquisition or catalog additions
  are claimed by this guide change.

Parent field-inventory draft #381 is all-green on
`d737715c417aba5c1e65518657f10350175e5d22`, run 37991526395: **4,563 passed /
11 skipped / two warnings / 617.19 seconds**. Its initial stylesheet-assertion
failure remains recorded. Sun Belle source draft #382 is a separate current-head
CI gate; this application-template draft also requires its own full CI.

The initial guide CI head `a5531f850db9880910610ba16e00821e4db4865e`
failed the static fixture's old availability-label count: the new workflow adds
one explanatory live-workspace label (13 total, formerly 12). Its generated
snapshot passed the draft-leakage check; the failure did not identify exposed
private data. The count is corrected with explicit assertions that the new
section keeps profile-coverage, candidate-review and source-authenticity links
out of public markup. **All 16 CI public-safety fixture tests pass locally**,
one existing warning, 9.07 seconds.

The dependent guide branch includes the source-replay regression repair from
draft #382; that separate repair preserves existing identities and decisions,
without application identity or canonical-data changes. Both drafts require
fresh current-head CI before release. The earlier failures remain in their
verification artifacts rather than being presented as green runs.

## Remaining mission

The repaired current head `155bbff806805a4b5dfc2774f0e684d009cf0c0c` now passes
all four required checks, run 37994664784: **4,565 passed / 11 skipped / two
warnings / 628.63 seconds**. The earlier failed run remains recorded above and
in the verification artifact. This is draft-head validation, not integrated
release approval.

CAT-01/CAT-02/TD-116 remain open. Full current/historical portfolios, original
corpus, reviewed canonical additions, cited profiles/current rights and independent
human recall still require real evidence and decisions. The 32-copy source/name
packet is unfinished. Blueberry feedback still gates other Landscape berries;
phone review and the integrated tested release remain before merge/deploy approval.
