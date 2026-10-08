# Find named varieties while reading

The private Reader now offers **Varieties in this article → Find named
varieties**. It checks the selected article's available stored text against the
catalog and existing candidates, then opens identity review with its named
varieties together. Newly found names enter the private candidate inbox; they
do not enter the catalog automatically.

This addresses the source/catalog mismatch raised during the Hortifrut review:
an article can enumerate varieties that its short summary does not mention.
The action uses the existing deterministic declaration grammar, identity
resolution and candidate persistence, rather than a second catalog or a new
extraction provider.

## Behavior and safeguards

- One selected source only, using its stored article paragraphs/full text and
  exact-ID capture cache. A cache for a different original URL is refused.
  No publisher, AI, paid-provider, or refresh call occurs during this check.
- Explicit crop/name declarations and supported pipe tables retain whole names,
  crop scope and breeder codes. Line boundaries are preserved for the selected
  check; ordinary Reader and summary decoding retain their existing behavior.
  Arbitrary company names, countries and capitalized prose are not candidates.
- Empty, inaccessible, bot-screen or over-200,000-character article text produces
  a clear limitation instead of clipped identities. Missing captures still need
  the Reader's existing explicit loading action or manual intake.
- Published and unreviewed sources can yield identity leads. Each new candidate
  retains the original source URL/ID, matching declaration, and whether the
  source was reviewed for publication. Article links return to the Reader,
  including sources that have no published Evidence page yet.
- Catalog matches stay catalog matches. Existing candidate decisions, rejection
  notes, aliases and file bytes win. Repeating the action does not overwrite
  them. Read-only source-context projections make existing rejected names
  discoverable under the rejected filter without rewriting their provenance.
- The article context survives filters and alphabetical navigation. Normal
  candidate-list loads do not scan every article or hydrate the capture cache.
  A specifically requested selected-source preview is read-only.
- The action is hidden when usable article text is absent and on public Reader
  views. Writes require the existing private-workspace and same-origin checks.
  It approves no source, statement, identity, company role, rights or publication.

Native review found that new-tab form submission created candidates but failed
to show its redirect reliably in the in-app browser. The final action navigates
directly to review. Acceptance uses fictional names in a separate runtime;
no real review decisions are made.

## Coverage limits

The unchanged 24-case summary diagnostic still measures **60/64** expected
occurrences, zero unexpected names, and four raw top-level-body misses. It is
agent-curated, not independently human-verified or model-qualified. This feature
has separate selected-article tests; it does not redefine that fixture, interpret
an unsupported top-level `body` as an article, or claim automatic global recall.

Current default coverage remains 104 dated sections, 648 source-name occurrences,
52 catalog text matches, 596 review needs and 518 combined candidate keys before
private state. The canonical catalog remains 64. Forty-five of 77 source-plan
subjects still need an initial enumerated primary check; 17 source follow-ups,
independent recall, release/rights verification, catalog authoring, traits,
regions and photo population remain open under CAT-01/CAT-02/TD-116.

Local validation includes declaration formats, immutable human decisions,
catalog collisions, cache/URL isolation, public/cross-site guards, unavailable
content, Reader/digest/news regressions and static build. Browser acceptance
checks the direct action, four names, source links, alphabet context and narrow
screen containment. Exact check totals and screenshots are recorded in the local
continuation checkpoint. No new PR/remote CI, merge, deployment or other-berry
Landscape rollout is implied; the pinned parent push approval remains pending.

Validation: 157 affected regression checks passed. After final navigation/link
changes, 56 navigation/Reader checks, 42 Reader/static checks and 43 final
Reader/capture/discovery checks passed (overlapping runs, not an additive total).
One existing ReportLab deprecation warning remains. Canonical record validation
and diff checks pass; all 1,992 original canonical/runtime JSON files and the
expansion guide remain unchanged. Browser proof is retained at
`inbox/european-portfolio-followup/selected-article-review.png` and
`selected-article-mobile.png`; fictional acceptance names are isolated.
