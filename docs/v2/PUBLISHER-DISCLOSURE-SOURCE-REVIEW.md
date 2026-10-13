# Preserve cultivar lists in expandable publisher sections

## Downstream list detection — October 13, 2026

Preserving the source text exposed a second omission: the existing name detector
did not recognize the publisher's labelled, line-by-line cultivar lists. On the
same unchanged pending Fall Creek copy, the detector at `f93aa702` returned zero
mentions. The current detector returns all 23 printed entries: ten match existing
catalog records and thirteen need identity review. These are not thirteen newly
approved varieties or necessarily thirteen new candidate keys.

The generic repair starts only under a literal Varieties/Cultivars heading.
Crop must be explicit in that heading or established by one unambiguous captured
article title consistent with the document. Publication tags cannot supply crop.
Chill categories are not names; prose, negation and malformed rows stop a list.
Quoted printed codes remain separate from names. Decorative registered/trademark
symbols do not enter names, but literal `EverlastTM` remains unchanged. The
1,024-row bound is reported explicitly. No alias, breeder, ownership, rights,
trait, geography or trusted catalog record is inferred.

Twenty-one synthetic parser/integration tests pass, including all four crops,
mixed documents, malformed/oversized lists, prior human rejection/notes/photos,
Reader and candidate routes, read-only GETs, explicit additive persistence and
public/private exclusion. The preceding affected-suite run passed 80 tests.
Native desktop and 412px viewport review of a clearly fictional pending draft
shows three names in the Reader and the original name/code/source handoff in
candidate review. No approval form was submitted; the original 32-copy human
worksheet packet and canonical 64 varieties remain unchanged. The real-copy
before/after diagnostic is not independent human recall qualification.

This detector change is additional to the verified capture release below and
requires a fresh pushed-head check set. The capture release at `f93aa702` passed
all four required checks (run `38363385489`, 4,972 passed / 11 skipped / two
existing warnings) and an isolated host rehearsal. That evidence does not cover
this later parser change. No merge or deployment.

## Result — October 13 UTC, 2026

The original Fall Creek Commercial Platforms page contains 23 cultivar entries
in public expandable sections. Precision article extraction captured surrounding
prose while silently omitting all 23. Switching to recall mode still omitted
later sections. This is a source-text problem before name detection, not proof
that those entries are missing from every existing portfolio observation.

The acquisition repair retains publisher disclosure text only when a public
control and region have a unique reciprocal ID pair, or use native
details/summary, within a section anchored to exact already extracted prose.
Navigation, sidebars, headers/footers, templates, hard-hidden ancestors and descendants,
interactive forms, broken/duplicate IDs and unanchored widgets stay excluded.
Literal printed names, codes, line breaks, repeated section labels and source
order survive. Fully retained lists are not duplicated. An oversized disclosure
fails the capture explicitly instead of returning silently shortened text.

The acquisition version is `article-acquisition-v4`. It applies to new captures;
existing stored articles, operator edits and source-review decisions are not
rewritten. The source-review stylesheet preserves captured line breaks, so a
multiline cultivar list renders as separate readable lines instead of one blurb.
No model, Source onboarding, catalog authoring, alias, role or trust action runs.

## Actual source proof and review

The exact privately retained public response was replayed offline. The old
capture has none of the 23 specified cultivar labels; the repaired capture has
all 23, including their printed codes. Its 35 indexed paragraphs contain 454
words, compared with 391 words previously. This is a bounded source-list
preservation test, not an independent detector recall score or global coverage
claim. The labels/codes remain unreviewed source assertions.

Original response:
[Fall Creek Commercial Platforms](https://fallcreekcatalogs.com/commercial-platforms/).
Response SHA-256:
`2207a462d727a9d5ca928f4c94089295e75c6564160745cc47a85becf17e725d`.
The full response, source bodies and audit passages remain in ignored inbox.
Only a synthetic structural fixture is committed.

The repaired copy is a separate **pending proposal**. The previous saved copy
is byte-identical. A separate copied-data browser runtime displays all three
cultivar sections without summaries, detector suggestions or decision controls.
Desktop review verifies four distinct lines in the first group. At 412×844
responsive emulation the document and scroll widths both measure 397px; the
viewport is reset. This is not a physical-phone test. No review form was submitted.

## Acquisition batch and gates

Twenty-two previously unattempted, stored high-availability HTML URLs were
captured through the existing bounded acquisition command: 20 pending copies,
one removed URL and one no-usable-body result. Copies remain in a separate local
review inbox. Current-page, changed-content and ambiguous-match classifications
are retained; capture does not establish historical authenticity. The original
32-copy independent-name worksheet packet and its source copies are unchanged.
No trusted Evidence was mutated, no new extraction-ready IDs were created and
no analyst decision was recorded. No private runtime was uploaded to the host.

Eighty-one acquisition, disclosure, recovery, publication-fidelity and Operations tests
pass (6.16 seconds, one existing ReportLab warning). They exercise multiple
sections, printed codes/order, native details, excluded navigation/templates,
hidden ancestors, malformed links, duplicate IDs, bounds, retained-list
idempotency, partially retained panel ordering, hidden/script descendants inside
otherwise valid paragraphs, source hashes/indexes and existing review gates. A
final synthetic exclusion check reproduced hidden script/span text entering a
valid list; the correction removes those descendants while preserving visible
text and tails. Exact-response replay still produces the same pending23-name
copy byte-for-byte. The new code still
requires its own required CI and release checks.

The initial full run on f499d8b8 passed 4,969 tests and failed two adjacent
tests that still expected acquisition v3. Their body, heading, menu-exclusion
and publication-date checks passed; the version assertions now expect v4.
All eight article test files plus the affected review/recovery suites pass:
160 tests / 99 existing Python 3.13 dependency warnings / 9.13 seconds.
Fresh checks on the corrected head remain mandatory.

The parent Landscape release, PR #396 head
`aa6a68fb32ee1059316a4de89f9f3766febdf1a2`, passes all four checks in run
`38355308016`: 4,956 passed / 11 skipped / two existing warnings / 687.62 seconds.
That is parent evidence, not verification of this newer acquisition code.
All 31 requirements, CAT-01/CAT-02, full portfolio/current-rights/profile/media
scope and unfinished independent human name review remain. No merge or deployment.
