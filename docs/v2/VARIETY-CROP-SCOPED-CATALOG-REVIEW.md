# Separate same-name varieties by berry

A reviewed strawberry candidate could not proceed to catalog authoring when a
blueberry already used its name. Earlier browser review removed the misleading
blueberry profile shortcut but left preparation blocked. The existing catalog
handoff now carries the human-checked name and berry through source review,
allowing a separate unverified variety record without attaching its source to
the other crop. This supersedes the authoring limitation recorded in
[the release/patent photo checkpoint](VARIETY-RELEASE-PATENT-PHOTO-REVIEW.md).

## Matching and review boundaries

Only the existing human-reviewed, distinct candidate workflow supplies the
explicit crop context. Matching still uses exact folded names and aliases.
Known disjoint crops can remain separate; same-crop, overlapping-crop,
unknown-crop and ambiguous matches block a new catalog entry. Current candidate
decisions and catalog matches are rechecked before publication. A compatible
record appearing after preparation also blocks writes.

Ordinary source review cannot silently link a single-crop article to a variety
recorded for another crop; it directs the analyst to identity review. It does
not gain unchecked cross-crop creation. Identity audit ignores name/code
collisions between known disjoint crops, keeps collisions within each crop or
with unknown crop, and retains registration-ID collisions across crops.

Review aids remain visible, but neither AI berry suggestions nor dossier
prefill can widen the name/berry already checked for this catalog handoff.
Human reviewer, source approval and separate claim approval remain mandatory.
New records are unverified; no roles, aliases, traits, rights or regions are
inferred. Scope metadata stays private and is not copied to published Evidence.
No domain/schema, CPVO, collection, qualification or expansion-guide changes.

## Verification and remaining work

The focused catalog, identity, photo and publication regressions pass: 74 tests
plus 28 existing source-fidelity, workbench and session checks, with the existing
ReportLab warning. Canonical records validate and the diff
passes whitespace checks. The PR records the final exact-head CI results.

Native desktop acceptance used an isolated fictional blueberry/strawberry pair:
identity review → intake → source review → separate claim gate. The checked
strawberry scope stayed selected despite a summary mentioning blueberry.
Comparison shows both distinct records; saved-file verification confirms the
original blueberry is unchanged, the new strawberry is unverified, only its own
source is linked, and no Fact or Relationship was created. No real identity or
source approvals were made. New mobile acceptance is unverified.

Actual coverage remains 64 catalog varieties, 53 bounded source sections,
540 occurrences, 34 text matches, 506 review needs and 450 derived candidate
keys before private state. Ten source photos include nine held and zero approved
public photos. Fifty-five initial company checks and seven follow-ups remain.
Stored-source and synthetic recall counts are unchanged; these tests establish
workflow behavior, not catalog completeness. CAT-01/CAT-02/TD-116 remain open.
No merge, deployment or other-berry Landscape rollout.
