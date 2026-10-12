# Explicit variety lists: fewer silent discovery misses

Ten names in the existing diagnostic were missed despite having an explicit
crop/name table or a Spanish/Polish variety declaration in the stored summary.
The shared read-only detector now handles those formats. The unchanged fixture
improves from **50 to 60 of 64 expected occurrences**, with **zero unexpected
names**, and from **20 to 23 of 24 fully passing cases**. Four names mentioned
only in article bodies remain missed; acquisition and qualified extraction are
still necessary. This does not approve or add catalog varieties.

## What the detector recognizes

- Pipe-delimited crop/name tables, optionally with selection codes. Columns
  may be reordered and Markdown separators may be present. Every row supplies
  its own crop; a black raspberry cannot inherit blueberry publication tags.
- Explicit `Variedades de <crop>:` and `Odmiany <crop>:` declarations with bounded
  capitalized names. Accents, Polish capitals, quotes and long F1 labels survive.
  Conjunctions do not become part of the variety name. Ambiguous `mora`, untyped
  declarations and negated declarations are deliberately not guessed.
- Missing/unknown crop, invalid whole name, malformed code or row width remain
  source-linked exclusions. A following unsupported table cannot inherit the
  preceding table's crop/name/code layout. Unbalanced quotes do not emit a
  shortened identity.

These are literal **identity leads**, using the existing resolver and candidate
pipeline. They are not plant-IP decisions, translated Facts, alias approvals or
company-role assertions. Source URLs remain unchanged. Existing human decisions,
notes and private profile state win on replay. Bodies, drafts, PDFs and OCR are
not hydrated or scanned by this change; no provider or network call is added.
The live candidate queue remains authoring-only.

The original [NIWA Polish page](https://niwabrzezna.pl/odmiany/) was checked
natively for its crop labels and name/code pairings. It distinguishes black
raspberry from blackberry. The diagnostic's prose, translations and mixed table
are synthetic source-based snippets, not a captured table or verbatim article.
Expected lists and their fixture bytes remain unchanged. The fixture is agent
curated and **not independently human-verified**, an Atomic Gold Set, model
qualification or proof of internet-wide recall.

## Evidence and limits

The compact before/after report is
`artifacts/variety-explicit-list-recall/comparison.json`; rerun
`python scripts/audit_variety_name_recall.py --output <report-path>` to inspect
per-case errors. All supported diagnostic checks retain berry, code, ambiguity,
catalog-link, review-state and original-source checks. Adversarial regression
checks include invalid headers, adjacent unsupported tables, ambiguous crops,
malformed codes/quotes, negation, overlong names, identical labels on different
crops, unpublished drafts, body-only text and preserved human rejections.
The live-page acceptance check uses a clearly fictional source in isolated
state; it verifies the crop-filtered name/code/source handoff and no GET writes.

Actual stored-corpus counts are unchanged: **1,269 published sources / 95 name
observations / 32 catalog matches / 63 review needs**. Primary portfolios remain
**537 occurrences / 33 text matches / 504 review needs in 51 sections**. Catalog
remains **64** and combined derived candidate keys remain **448 before private
state**. Twenty-two of 77 registry rows have some enumerated checks; 55 initial
checks and seven source follow-ups remain. This is detector coverage progress,
not researched portfolio or canonical catalog growth.

Parent draft #333 passes all four exact-head checks with 4,138 passed / 11 skipped
/ two existing warnings. This executable draft requires its own checks. The final
focused suite passes 77 tests with one existing ReportLab warning (45.10 seconds).
Native isolated acceptance shows four correctly scoped fictional candidates;
Megan retains its spaced code and exact query-bearing source URL. Desktop and
phone are checked, phone content/scroll widths 360px/360px, normal viewport
restored, temporary acceptance server stopped and real preview retained.
Two initial test assertions used the wrong existing service return shape;
corrected before the passing runs. Canonical validation passes; expansion
guide and runtime data are preserved. No merge, deployment, identity/source
approval or other-berry Landscape rollout. CAT-01/CAT-02/TD-116 remain open.

The first full CI run found one stale assertion in the separate title-precision
suite: it still expected the preceding 50/64 diagnostic. The assertion now checks
60/64, all original case/fixture bytes, the three repaired formats and the four
remaining body-only misses. That repair and adjacent recall/title checks pass
33 tests with one existing warning (4.29 seconds). A fresh exact-head full CI
run is required; the failed run is not presented as passing.
