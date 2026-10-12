# Audit explicit article text against separately supplied names

The offline recall scorer now forwards explicitly supplied supported Article
records to the existing name-discovery service. Previously it scored only
published summaries/facts, so article-profile recall could not be measured
through this repeatable command. This adds an audit input path, not acquisition,
source acceptance, identity approval or extraction qualification.

Review branch: `feature/article-source-recall-audit`, stacked on #377.

## Inputs and honest failures

Use `inputs.source_text_records` in a `variety-name-recall-v1` case to opt into
captured Article paragraphs or supported full text. Supplying an article only
inside `inputs.evidence` does not opt it in. URLs, source IDs, printed codes,
crop and pending publication status remain visible in the observed result.
The scorer deep-copies its inputs and never persists candidates or modifies
canonical records, reviewer decisions or the input fixture.

Expected names must be supplied separately. A missing/null list means unfinished
and fails before discovery or score output. An empty list explicitly means a
reviewer expects no cultivar names; unexpected detections still fail that case.
Wrong codes, crops, source references and extra names remain separate failures.
Successful synthetic examples do not become human-reviewed cases or model
qualification. The report preserves the fixture's stated review status.

The original 24-case synthetic fixture is unchanged: **60/64 expected occurrences,
zero extra names, 23/24 fully passing cases**. Its four legacy raw `body` names
remain intentionally outside the supported Article path. They stay visible in
the denominator; this change does not rewrite them to force a perfect result.

## Human review preparation

A private packet under ignored `inbox/european-portfolio-followup/` lists the
same 32 pending source copies with original URLs, review-page links and exact
body/artifact hashes. Every expected-name list is blank, with blank reviewer/date
and no independently-reviewed flag. No parser names were used to populate it.

The reviewer should enumerate literal names, crop, printed codes and locations
from each captured source before comparing parser output. Record image-only,
ambiguous, truncated and excluded material separately. Source authenticity
review is a distinct decision; neither the packet nor this scorer approves it.
The packet remains unfinished and has no recall score. It is not automatically
converted into an executable benchmark or a human approval marker.

Only synthetic controls are used in tests; private source bodies are not
committed or sent to CI/providers. The 32-copy field diagnostic in
[profile-name review](ARTICLE-PROFILE-NAME-RECALL-REVIEW.md) is separate from any
independently reviewed recall benchmark.

## Verification and remaining work

**54 affected tests passed**, one existing ReportLab warning, 4.77s. Tests
exercise an explicit unreviewed Article profile, exact code/source
provenance, opt-in boundaries, wrong-code/extra-name failures, deep-copy
preservation, unfinished expectations and absence of score output after CLI
failure. The original fixture and canonical data remain unchanged. Current
verification is retained in
[verification.json](../../artifacts/article-source-recall-audit-2026-10-09/verification.json).
No app UI or acquisition path changes; prior native source-name review remains
applicable. This offline script change does not require another local static
render; the new draft receives its own required CI checks.

Parent #377 has all four required checks successful on
`9ac78de0a87f342d9473c27fde977adcb1c601c6`: **4,543 passed / 11 skipped /
two warnings / 758.17s**. That success does not substitute for this draft's CI.

CAT-01/CAT-02/TD-116 stay open: independent human review and a balanced multi-berry
captured-source benchmark are still required, along with complete portfolios,
article corpus, cited profiles, current rights, photos and catalog authoring.
Blueberry feedback still gates the remaining Landscape rollout. No merge/deploy.
