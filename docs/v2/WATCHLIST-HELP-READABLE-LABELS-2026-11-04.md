# Explain Global Watchlist in Help

Global Watchlist is a top-level destination, but the Help explainer omitted its
purpose and PDF workflow. Some Watchlist labels also exposed storage values such
as `company_website`, and generated monitoring explanations named database fields.

Help now explains the Watchlist's table, company comparison, shared monitoring
groups and scoped PDF. It distinguishes these from Map, Landscape, Companies,
Personal Digest and a fresh competitor-news packet. The new sections are shown
only in the private authoring workspace. Existing sections remain; the public
snapshot does not acquire private Watchlist links or content.

The screen and PDF use the existing readable-label helper for roles, source and
event types, review classifications and monitoring states. Filter options retain
their original explicit values, and source monitoring decisions and state codes
are unchanged. Generated explanations use source names and plain language.
PDF scope uses known company, geography and group names while preserving source
URLs, reference IDs, original text and user-written notes. No stored record,
schema, account, permission or collection setting is changed.

## Validation

- 67 affected checks pass across Watchlist HTML/PDF, Help privacy, stakeholder
  labels and source monitoring. The offline runner records zero attempted
  external connections. A final grammar-only adjustment is included in CI.
- The sample PDF uses fictional test data. All three pages were rendered through
  Poppler and visually inspected; readable roles, scope names, source labels,
  original note wording and page layout are preserved. The renderer leaves its
  complete input model unchanged.
- Native desktop/phone review and current-head CI remain to be completed for
  this follow-up. It is stacked on frozen #506, not included in that release or
  its pending approval. Fresh release acceptance remains a separate gate.

Ignored evidence lives in `inbox/watchlist-help-labels-20261104/`; rendered PDF
samples are under `tmp/pdfs/watchlist-help-labels/`. Earlier diagnostics and the
initial failed wording assertion remain retained. The assertion was updated to
the intentionally broader “Source blocked” label; the blocking state is still
required.

## Consolidation still required

Global Watchlist's monitoring groups and imported berry-specific tiers currently
use different records from the shared favorites, assigned company tiers and
custom lists in Companies. Explaining that distinction does not satisfy CO-01's
requirement that company marks and lists carry into every view. Add those shared
filters to Watchlist without discarding existing groups, imported classifications
or edits; do not silently merge records that have different meanings. This stays
in the original mission and is not claimed complete by the Help change.
